# EdNet-KT4: Random Forest & XGBoost Modeling Report

**Author**: Phương
**Notebook**: [`RandomForest_XGBoost_Models_fixed.ipynb`](https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_?usp=sharing) (Drive folder)
**Drive folder**: [models & artifacts](https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_?usp=sharing) — files dated 2026-05-14

## Overview

Two tree-based binary classifiers, both retrained on **2026-05-14** with a **user-level train/test split** to remove the row-level leakage from the original (May 12) version. The 11-feature input, hyperparameters, and overall pipeline are otherwise unchanged from the prior version.

**Input**: `kt4_features_1.parquet` (23,308,702 rows; byte-identical to Nguyễn's `kt4_features_ultimate.parquet`)
**Output 1**: `random_forest_final_model.pkl` (~155 MB)
**Output 2**: `xgboost_final_model.json` (~16.4 MB)
**Plots**: `random_forest_evaluation.png`, `xgboost_evaluation.png`, `benchmark_comparison.png`

All artifacts in the linked Drive folder.

---

## 1. Input Features

Same 11-feature subset for both models:

```
feat_question_difficulty, feat_current_part_accuracy, feat_answer_changes,
feat_overall_accuracy, feat_reading_accuracy, feat_recent_accuracy,
feat_is_rapid_guess, part, feat_total_attempts,
feat_listening_accuracy, feat_explanation_ratio
```

`fillna(0)` applied; no scaling (tree-invariant).

## 2. Train/Test Split — user-level (no leakage)

The notebook (cell 3) performs the split as:

```python
unique_users = df['user_id'].unique()
np.random.seed(42)
np.random.shuffle(unique_users)
n_test_users = int(len(unique_users) * 0.2)
test_users  = set(unique_users[:n_test_users])
train_users = set(unique_users[n_test_users:])
```

Result: **237,361 train users / 59,340 test users**. No user appears in both sides.

This is *equivalent within 1 user* to the team-canonical split (`sklearn.model_selection.train_test_split(unique_users, test_size=0.2, random_state=42)` → 237,360 / 59,341). All 59,340 of Phương's test users are inside the canonical 59,341-user test set; the 1-user difference is a rounding artifact.

> **Difference from the prior version**: the May 12 training used `train_test_split(X, y, ..., stratify=y)` on rows, which leaked ~99% of users across train and test. That problem is now resolved.

## 3. Random Forest

### Hyperparameters

| Parameter | Value | Notes |
|---|---|---|
| `n_estimators` | 300 | unchanged from prior version |
| `max_depth` | 12 | unchanged; binding for all 300 trees |
| `min_samples_leaf` | 50 | unchanged; rarely binding because of depth cap |
| `max_features` | `'sqrt'` | unchanged |
| `class_weight` | `'balanced'` | unchanged |
| `n_jobs` | -1 | All CPU cores |
| `random_state` | 42 | |

### Test-set metrics (last response per test user)

Scored on the **last response per test user** (59,341 predictions — the team-agreed evaluation protocol that aligns the trees with how the deep models predict):

| Metric | Value |
|---|---|
| **AUC-ROC** | **0.6831** |
| Accuracy | 0.6251 |
| Precision | 0.6797 |
| Recall | 0.3944 |
| F1-Score | 0.4991 |
| Log Loss | 0.6427 |

> **What Phương's own evaluation cell reports** (cell 8) is different: she evaluates on *all rows* of test users (~4.6M predictions), not last-row-only. Those numbers exist in her notebook output but are on a different prediction task and aren't directly comparable to the deep models. The metrics above (last response per user) are the apples-to-apples ones.

## 4. XGBoost

### Hyperparameters

| Parameter | Value |
|---|---|
| `objective` | `binary:logistic` |
| `eval_metric` | `auc` |
| `tree_method` | `hist` |
| `device` | `cpu` |
| `learning_rate` | 0.1 |
| `max_depth` | 9 |
| `min_child_weight` | 50 |
| `subsample` | 0.85 |
| `colsample_bytree` | 0.9942 |
| `scale_pos_weight` | computed from training class counts |
| `seed` | 42 |
| `num_boost_round` | 500 |
| `early_stopping_rounds` | 30 |

These are unchanged from the May 12 version. (The `colsample_bytree=0.9942` value is still the same Optuna-derived value Nguyễn used for his earlier LightGBM; Phương borrowed it without re-tuning. With the new user-level split, this isn't strictly principled but it's the value she used and the model trained around it.)

### Test-set metrics (last response per test user)

| Metric | Value |
|---|---|
| **AUC-ROC** | **0.6871** |
| Accuracy | 0.6304 |
| Precision | 0.6786 |
| Recall | 0.4176 |
| F1-Score | 0.5170 |
| Log Loss | 0.6392 |

XGBoost narrowly outperforms RF on the same test set (Δ = 0.004 AUC), but this gap is within the noise of a single 59,341-prediction evaluation and shouldn't be interpreted as a definitive ranking.

## 5. Reproducibility Notes

- All randomness pinned to `random_state=42` / `seed=42` / `np.random.seed(42)`.
- Data path inside notebook is `/content/drive/MyDrive/Colab Notebooks/data mining/kt4_features_1.parquet` (Phương's local copy of the canonical engineered table).
- The canonical engineered parquet (also distributed by Nguyễn as `kt4_features_ultimate.parquet`) is byte-identical: same MD5, same 18-column schema, same 23,308,702 rows.
- Saved models are loadable locally; the metrics above come from re-scoring the saved weights against each test user's last response.
