# EdNet-KT4: LightGBM, LSTM & 1D-CNN Modeling Report

**Author**: Nguyễn (Võ Thế Nguyễn)
**Drive folder (all artifacts)**: [folder](https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397?usp=sharing) — files dated 2026-05-14
**v2 training notebook**: [Colab](https://colab.research.google.com/drive/1P768sw_p2qG13LUwcUSomdZOtiesDjEK?usp=drive_link) — 5 cells, this is the notebook that produced the current model files

## Overview

Four models, all retrained on **2026-05-14** under the team-agreed user-level split:

1. **LightGBM** on the 11-feature engineered table (chunked incremental training).
2. **LSTM-11-features** — new architecture, sees the same 11 engineered features as LightGBM, last-target supervision.
3. **LSTM-raw** — same architecture as the previous "LSTM-Chunking", retrained on the agreed split.
4. **1D-CNN-raw** — same architecture as the previous "1D-CNN-Chunking", retrained.

The deep models are all **last-target** supervised: each user's sequence (last up to 100 responses) produces one prediction (the correctness of the very last response). `MAX_LEN=100` so users with more than 100 responses have their early history truncated away.

The notebook also contains an upstream feature-engineering pass that produces `kt4_features_ultimate.parquet` (18 columns, 23,308,702 rows). This file is byte-identical to Phương's `kt4_features_1.parquet` — same MD5, same data.

---

## 1. Train/Test Split (cell 0 of v2 notebook)

```python
df_users = pd.read_parquet(FILE_ULTIMATE, columns=['user_id'])
all_users = df_users['user_id'].unique()
train_val_users, test_users = train_test_split(all_users, test_size=0.2, random_state=42)
train_users, valid_users = train_test_split(train_val_users, test_size=0.1, random_state=42)
np.save(SAVE_DIR + 'train_users.npy', train_users)
np.save(SAVE_DIR + 'valid_users.npy', valid_users)
np.save(SAVE_DIR + 'test_users.npy', test_users)
```

Result: **213,624 train / 23,737 valid / 59,341 test users**. All four models load these `.npy` files, so they share the split byte-identically. The valid users are used for early-stopping monitoring inside the deep training; they are *not* in the test set.

This is the team-canonical user split and produces test_users identical to `modeling/retrain/split.py`.

## 2. LightGBM (cell 1)

### Training pattern

Chunked incremental training on the 11-feature engineered table:

- 6 chunks of ~40,000 train users each
- 30 boost rounds per chunk
- `init_model=gbm` chained between chunks → resulting model has **180 trees total**
- Validation set: the 23,737 held-out valid users, monitored after each chunk

### Hyperparameters

| Parameter | Value |
|---|---|
| `objective` | `binary` |
| `metric` | `auc` |
| `boosting_type` | `gbdt` |
| `learning_rate` | 0.05 |
| `num_leaves` | 63 |
| `max_depth` | 8 |
| `feature_fraction` | 0.8 |
| `device_type` | `cpu` |
| `num_iterations` | 30 (per chunk) |

### Test-set metrics (last response per test user)

Scored on the **last response per test user** (59,341 predictions):

| Metric | Value |
|---|---|
| **AUC-ROC** | **0.6812** |
| Accuracy | 0.6330 |
| Precision | 0.6381 |
| Recall | 0.5205 |
| F1-Score | 0.5733 |
| Log Loss | 0.6368 |

> The earlier "AUC 0.7223" reported in older versions of this notebook was on a leaky row-level split. The current honest number is 0.6812 — about 0.04 AUC lower, exactly the typical leakage-removal magnitude in Knowledge Tracing literature.

## 3. LSTM-11-features (cell 2) — NEW architecture

A fresh sequence model that consumes the same 11 engineered features as LightGBM, reshaped per-timestep:

```
Input(shape=(100, 11))
Masking(mask_value=-99.0)
LSTM(128, return_sequences=False)
BatchNormalization()
Dropout(0.3)
Dense(64, activation='relu')
Dropout(0.2)
Dense(1, activation='sigmoid')
```

### Per-feature scaling at training time

Most engineered features are already in `[0, 1]` and used as-is. Three are rescaled before being fed to the LSTM:

- `part`: divided by 7
- `feat_answer_changes`: `log1p(x) / 5`
- `feat_total_attempts`: `log1p(x) / 10`

### Training pattern

5 outer epochs, each looping through 8 chunks of 30,000 train users. `model.fit()` is called once per chunk with `validation_data=valid` and `epochs=1`. No early stopping.

### Test-set metrics (last response per test user) — anomalous

| Metric | Value |
|---|---|
| **AUC-ROC** | **0.5011** (anomalous; see below) |
| Accuracy | 0.4805 |
| Precision | 0.4765 |
| Recall | 0.9803 |
| F1-Score | 0.6413 |
| Log Loss | 0.7462 |

**This model is essentially predicting "correct" for nearly every user** (Recall=0.98, Precision=0.48). The unified evaluation script applies the exact same per-feature scaling that Nguyễn's own cell-4 evaluation cell uses, so this isn't a scoring bug — the model itself is the issue.

Most plausible cause: a training-time preprocessing inconsistency that emerged when the architecture was extended from the previous 5-feature version. Worth investigating before relying on this model. Given LightGBM achieves 0.6812 on the same 11 features, an LSTM with comparable capacity should be able to reach at least 0.65.

## 4. LSTM-raw (cell 3) — same as previous "LSTM-Chunking", retrained

Same architecture as before, retrained on the agreed split:

```
Input(shape=(100, 4))
Masking(mask_value=-99.0)
LSTM(128, return_sequences=False)
BatchNormalization() → Dropout(0.3)
Dense(64, activation='relu') → Dropout(0.2)
Dense(1, activation='sigmoid')
```

Features per timestep: `part/7`, `log1p(time_since_prev)/15`, `hour/24`, shifted past `is_correct`. Reads from `kt4_preprocessed.parquet`, filtered to action_type=respond by checking that `is_correct ∈ {0, 1}`.

Training pattern: 5 outer epochs × 6 chunks of 40,000 train users; `model.fit(..., epochs=1)` per chunk.

### Test-set metrics (last response per test user)

| Metric | Value |
|---|---|
| AUC-ROC | **0.5732** |
| Accuracy | 0.5449 |
| Precision | 0.6652 |
| Recall | 0.0792 |
| F1-Score | 0.1416 |
| Log Loss | 0.9818 |

The 4 raw features don't include `feat_question_difficulty` (the dominant signal for the trees), so this model is structurally limited to a much lower AUC than the trees.

## 5. 1D-CNN-raw (cell 3) — same as previous "1D-CNN-Chunking", retrained

```
Input(shape=(100, 4))
Masking(mask_value=-99.0)              # silently dropped at the first Conv1D
Conv1D(64, 3, padding='same')
BatchNormalization() → ReLU() → MaxPooling1D(2)
Conv1D(128, 5, padding='same')
BatchNormalization() → ReLU()
GlobalAveragePooling1D() → Dropout(0.3)
Dense(64, activation='relu') → Dropout(0.2)
Dense(1, activation='sigmoid')
```

Same 4 raw features as LSTM-raw, same input parquet, same training loop. The `Masking` layer is architecturally bypassed at the first Conv1D (Conv1D doesn't propagate masks), but the trained weights are empirically padding-invariant on in-distribution inputs (verified previously).

### Test-set metrics (last response per test user)

| Metric | Value |
|---|---|
| AUC-ROC | **0.5992** |
| Accuracy | 0.5879 |
| Precision | 0.6020 |
| Recall | 0.3840 |
| F1-Score | 0.4689 |
| Log Loss | 0.7395 |

Slightly outperforms LSTM-raw on the same input — a small but consistent reversal from the earlier (leaky) benchmark where they were tied at AUC 0.6124.

## 6. Cross-model summary (unified benchmark)

All four of Nguyễn's models scored on the same 59,341 test users, last response per user:

| Model | AUC | Notes |
|---|---|---|
| LightGBM | **0.6812** | Best of the four |
| 1D-CNN-raw | 0.5992 | Best deep model on raw features |
| LSTM-raw | 0.5732 | |
| LSTM-11-features | 0.5011 | **Anomalously broken — needs debugging** |

For the cross-member comparison (vs Phương's RF / XGB), see [`cross_member_review.md`](cross_member_review.md).

## 7. Artifact Status

All artifacts are in [Nguyễn's Drive folder](https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397?usp=sharing), all dated 2026-05-14:

| Artifact | Status |
|---|---|
| Training notebook | Available — [v2 Colab](https://colab.research.google.com/drive/1P768sw_p2qG13LUwcUSomdZOtiesDjEK?usp=drive_link) (5 cells, byte-different from the older `nguyen_colab.ipynb` that's also still in the folder) |
| `lightgbm_final_model.pkl` | Available (1.29 MB, 180 trees) |
| `ednet_lstm_11_features.keras` | Available (1.0 MB, input `(100, 11)`) — **functionally broken, see §3** |
| `ednet_lstm_raw.keras` | Available (962 KB, input `(100, 4)`) |
| `ednet_1d_cnn_raw.keras` | Available (668 KB, input `(100, 4)`) |
| `kt4_features_ultimate.parquet` (upstream input) | Available (1 GB, byte-identical to Phương's `kt4_features_1.parquet`) |
| `train_users.npy` / `valid_users.npy` / `test_users.npy` | In `Splits/` subfolder on Drive (not pulled locally; reconstructible deterministically from `split.py`) |
