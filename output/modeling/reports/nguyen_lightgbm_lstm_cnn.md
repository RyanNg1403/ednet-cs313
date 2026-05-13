# EdNet-KT4: LightGBM, LSTM & 1D-CNN Modeling Report

**Author**: Nguyễn (Võ Thế Nguyễn)
**Drive folder (all artifacts)**: [folder](https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397?usp=sharing) — Colab notebook + 4 trained model files (see [§7](#7-artifact-status))
**Notebook**: [Colab](https://colab.research.google.com/drive/1d_wp7bnUi9LPoRd9xWUMmm_Rkfal6DNR?usp=drive_link) — local copy at `modeling/nguyen/nguyen_colab.ipynb`

## Overview

Four models were trained to predict `target_is_correct`, spanning gradient boosting and two deep-learning architectures:

1. **LightGBM** on the engineered 11-feature table (this is the headline result).
2. **LSTM "Fair Comparison"** on the same 11-feature table but reshaped into per-student sequences.
3. **LSTM (Chunking)** on the raw `kt4_preprocessed.parquet` with only 4 minimal columns, trained via chunked loop.
4. **1D CNN (Chunking)** on the same raw 4-column input as #3.

All four are re-evaluated against a common held-out user sample in the notebook's final benchmark cell.

In addition to model training, the notebook also implements **two upstream DuckDB feature-engineering pipelines** (cells 0 and 3) that produce `kt4_features_1.parquet` and `kt4_features_ultimate.parquet` on the author's Drive. These differ from the in-repo `feature_engineering/generate_features.py` (see [§7](#7-artifact-status)).

---

## 1. Upstream Feature Engineering (DuckDB)

The notebook contains two DuckDB pipelines that read `kt4_preprocessed.parquet` and emit feature tables:

- **Cell 0 → `kt4_features_1.parquet`** (per the `OUTPUT_FILE` variable in cell source): 13-column output projecting Long-term history, SAKT-style concept attention (`PARTITION BY user_id, part`), Recent-20-question window, Learning strategy (adaptive/explanation/lecture), and Session fatigue (60-min rolling).
- **Cell 3 → `kt4_features_ultimate.parquet`** (per `OUTPUT_FILE`): 18-column output that adds a leakage-corrected question difficulty (`q_attempts` / `q_incorrect` windows), separate listening (parts 1-4) and reading (parts 5-7) accuracy tracks, and an answer-changes column.

All cumulative features use `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING` to prevent same-row leakage.

> **Note on filename vs. content.** The file Phương consumes — *named* `kt4_features_1.parquet` in her Drive folder — has 18 columns matching the Cell 3 outer SELECT, not the 13 columns of the Cell 0 SELECT. Schema and row count (23,308,702) are identical to what Cell 3 should produce. So in practice both members train on the same Cell 3 output; the filename is misleading. Either the file was renamed before being shared with Phương, or Cell 0 was edited after the original file was generated.

## 2. LightGBM (Headline Model)

### Hyperparameter search

`Optuna` over 50 trials (cell 2), maximizing AUC on a 20M-row sample of `kt4_features_1.parquet`. Search space:

| Parameter | Range |
|---|---|
| `learning_rate` | 0.01 – 0.2 (log-uniform) |
| `num_leaves` | 31 – 256 |
| `max_depth` | 6 – 15 |
| `min_data_in_leaf` | 100 – 2000 |
| `feature_fraction` | 0.6 – 1.0 |

Inner training loop: `num_boost_round=300`, `early_stopping(stopping_rounds=20)`.

### Final training (cell 6)

Input: `kt4_features_ultimate.parquet`, 11 features (same list as Phương's):
```
feat_question_difficulty, feat_current_part_accuracy, feat_answer_changes,
feat_overall_accuracy, feat_reading_accuracy, feat_recent_accuracy,
feat_is_rapid_guess, part, feat_total_attempts,
feat_listening_accuracy, feat_explanation_ratio
```

Split: `train_test_split(X, y, test_size=0.2, random_state=42)` (random, **not** stratified, **not** grouped — see methodology note in [§5](#5-methodology-divergences)).

Best params from "Optuna Trial 2", loaded explicitly:

| Parameter | Value |
|---|---|
| `objective` | `binary` |
| `metric` | `auc` |
| `boosting_type` | `gbdt` |
| `learning_rate` | 0.1379900896401586 |
| `num_leaves` | 201 |
| `max_depth` | 9 |
| `min_data_in_leaf` | 249 |
| `feature_fraction` | 0.9942082330434625 |
| `num_boost_round` | 500 |
| `early_stopping_rounds` | 30 |

### Test-set metrics

| Metric | Value |
|---|---|
| AUC-ROC | **0.7223** |
| Accuracy | 0.6668 (66.68%) |

Saved to `lightgbm_final_model.pkl` on Drive (`DataMining_Project/`).

## 3. LSTM — "Fair Comparison" (cell 10)

A sequence model trained on the *same* engineered feature table as LightGBM, to isolate the effect of architecture vs. features.

### Sequence construction

- Per-student sequences sorted by `user_id`, `timestamp`.
- Features used per timestep: `part / 7.0`, `feat_question_difficulty`, `feat_is_rapid_guess`, `log1p(feat_answer_changes)`, and a **time-shifted** correctness signal `[0] + target_is_correct[:-1]` (only past labels visible).
- Padding: `pad_sequences(..., maxlen=100, padding='post', truncating='pre')`. The target `y` is the *last* response in each student's sequence.
- Final tensor shape: `(N_users, 100, 5)`.
- Split: `train_test_split(X_3D, y, test_size=0.2, random_state=42)`.

### Architecture

```
Input(shape=(100, 5))
Masking(mask_value=0.0)
LSTM(128, return_sequences=False)
BatchNormalization()
Dropout(0.3)
Dense(64, activation='relu')
Dropout(0.2)
Dense(1, activation='sigmoid')
```

Optimizer: `Adam(learning_rate=0.001)`. Loss: `binary_crossentropy`.

### Test-set metrics

| Metric | Value |
|---|---|
| AUC-ROC | 0.7035 |
| Accuracy | 0.6473 (64.73%) |

Saved to `ednet_lstm_fair_model.keras`.

## 4. LSTM (Chunking) and 1D CNN (Chunking) — Raw-feature variants

Both models stream the full `kt4_preprocessed.parquet` in user-grouped chunks of 80,000 students per chunk, training one epoch's worth of weights per chunk and looping for 10 outer epochs. Only 4 raw columns are used: `part`, `time_since_prev` (log1p-normalized), `hour`, and a shifted `is_correct`. Sentinel value `-99.0` is used for padding so the `Masking` layer can ignore it.

Split: **at the user level** — `train_test_split(all_users, test_size=0.2, random_state=42)` — which avoids the train/test leakage present in the LightGBM and LSTM-Fair runs.

### LSTM-Chunking architecture (cell 12)

```
Input(shape=(100, 4))
Masking(mask_value=-99.0)
LSTM(128, return_sequences=False)
BatchNormalization()
Dropout(0.3)
Dense(64, activation='relu')
Dropout(0.2)
Dense(1, activation='sigmoid')
```

Optimizer: `Adam(learning_rate=0.001)`. Training: 10 outer epochs × shuffled chunks, `batch_size=2048`.

### 1D-CNN-Chunking architecture (cell 14)

```
Input(shape=(100, 4))
Masking(mask_value=-99.0)
Conv1D(filters=64, kernel_size=3, padding='same')
BatchNormalization() -> ReLU() -> MaxPooling1D(pool_size=2)
Conv1D(filters=128, kernel_size=5, padding='same')
BatchNormalization() -> ReLU()
GlobalAveragePooling1D()
Dropout(0.3)
Dense(64, activation='relu')
Dropout(0.2)
Dense(1, activation='sigmoid')
```

Same optimizer, batch size, and 10-epoch chunking loop as the LSTM-Chunking model.

### Test-set metrics

| Model | AUC-ROC | Accuracy |
|---|---|---|
| LSTM (Chunking) | 0.6124 | N/A (not recorded) |
| 1D CNN (Chunking) | 0.6124 | N/A (not recorded) |

Saved to `ednet_lstm_chunking.keras` and `ednet_1d_cnn_chunking.keras`.

## 5. Methodology Divergences

| Concern | Detail |
|---|---|
| Split strategy | The LightGBM and LSTM-Fair runs use a **row-level random split** (`train_test_split(X, y, test_size=0.2, random_state=42)`) — interactions from the same student land in both train and test, which inflates metrics. The LSTM/CNN chunking variants split at the user level (`train_test_split(all_users, ...)`) and so do not have within-user leakage. |
| Common test set for benchmark | The final benchmark (cell 17) re-evaluates all four models on a **30,000-user sample** drawn from the same `test_users` produced by `train_test_split(all_users, ..., random_state=42)`. This is internally consistent across the four models in this notebook but is **not** the same test set used by Phương's RF / XGBoost notebook. |
| Upstream feature pipeline | The notebook regenerates the feature table from `kt4_preprocessed.parquet` rather than reusing the in-repo `feature_engineering/generate_features.py`. The resulting features overlap heavily by name but were produced by a different script with slightly different windowing definitions. |

These are flagged for awareness, not as blocking issues — they affect how the in-notebook metrics should be interpreted, not whether the models work.

## 6. Internal Benchmark (cell 17)

The notebook's own summary, re-scored on the 30k-user common test sample:

| Model | Dataset | AUC (Test) | Accuracy (Test) | Notes |
|---|---|---|---|---|
| **LightGBM** | `kt4_features_ultimate` | **0.7223** | **66.68%** | Best result; relies on the optimized feature set. |
| LSTM (Fair Comparison) | `kt4_features_ultimate` | 0.7035 | 64.73% | Same features as LightGBM, different architecture. |
| LSTM (Chunking) | `kt4_preprocessed` (raw) | 0.6124 | N/A | Raw features only; demonstrates chunked training on limited RAM. |
| 1D CNN (Chunking) | `kt4_preprocessed` (raw) | 0.6124 | N/A | Same raw input as LSTM-Chunking. |

The notebook's stated conclusion: feature engineering dominates architecture choice on this problem — LightGBM on engineered features beats a sequence model on the same features, which in turn beats deep models on raw features.

## 7. Artifact Status

All four trained model files are available in the author's [Drive folder](https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397?usp=sharing). Per-file links:

| Artifact | Size | Status |
|---|---|---|
| Training notebook (Colab) | 293 KB | Available — [in-folder Colab link](https://colab.research.google.com/drive/1d_wp7bnUi9LPoRd9xWUMmm_Rkfal6DNR?usp=drive_link) (same file also reachable via the original [Colab link](https://colab.research.google.com/drive/1FZ0_wIyGTxOGMTkpO-GwlQpTDU7rFUbD?usp=sharing); both IDs resolve to identical content by MD5). Local copy at `modeling/nguyen/nguyen_colab.ipynb`. |
| [`lightgbm_final_model.pkl`](https://drive.google.com/file/d/1AynYV3uTakHkn8ljsFa6XpnO2Zx7O6Gh/view?usp=sharing) | 11.1 MB | Available |
| [`ednet_lstm_fair_model.keras`](https://drive.google.com/file/d/1pt8N4jBP7MNRgEN7ffOcApPQCS1nWUwb/view?usp=sharing) | 969 KB | Available |
| [`ednet_lstm_chunking.keras`](https://drive.google.com/file/d/17uVZRRkVK1rvGwHimBbteVnjx5GtJ0U_/view?usp=sharing) | 963 KB | Available |
| [`ednet_1d_cnn_chunking.keras`](https://drive.google.com/file/d/1xgiK-z54v-KnlJm0-uFW5IWgqsvVcUiq/view?usp=sharing) | 668 KB | Available |
| `feature_importance_barchart.png` | — | **Not in folder.** Generated inside the notebook (cell 5) and saved to `DataMining_Project/feature_importance_barchart.png` on the author's Drive; not yet shared in the public folder. |
| `kt4_features_ultimate.parquet` (upstream input consumed by LightGBM & LSTM-Fair) | — | **Not in folder under this name.** But its content (18 cols, 23.3M rows, Cell 3 schema) is available as `kt4_features_1.parquet` in Phương's [Drive folder](https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_?usp=sharing). Needed to reproduce training but not to use the saved models. |
