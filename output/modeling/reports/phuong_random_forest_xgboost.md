# EdNet-KT4: Random Forest & XGBoost Modeling Report

**Author**: Phương
**Notebook**: [`RandomForest_XGBoost_Models.ipynb`](https://drive.google.com/file/d/1PSdFzMcT8W18zOvOcG9p0Sk64Fyiogca/view?usp=sharing) (Google Drive)
**Drive folder**: [models & artifacts](https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_?usp=sharing)

## Overview

Two tree-based binary classifiers were trained to predict `target_is_correct` on the engineered EdNet-KT4 feature table: a **Random Forest** (scikit-learn) and a **gradient-boosted XGBoost**. Both models share the same 11-feature input, target, and train/test split, so the evaluation is directly comparable.

**Input**: `kt4_features_1.parquet` (23,308,702 rows) — [Google Drive](https://drive.google.com/file/d/1RUVv9P6SZ0kb1M4sCr0jSH6KQnAXDYmv/view?usp=sharing)
**Output 1**: `random_forest_final_model.pkl` (~154 MB) — [Google Drive](https://drive.google.com/file/d/1CA3BxvcUCKfWuU5EPipd1KsNAPS4Wsfl/view?usp=sharing)
**Output 2**: `xgboost_final_model.json` (~18 MB) — [Google Drive](https://drive.google.com/file/d/1hVVKA0zQ_yKMwYaEOi9W7eQcb5JTdiXX/view?usp=sharing)
**Plots**: [RF evaluation](https://drive.google.com/file/d/1FY6zNtw_EW9BrnMd9poJ7azUBIjB0e-_/view?usp=sharing) · [XGBoost evaluation](https://drive.google.com/file/d/16fYYjXbzuABCyrds9tMfwqFG60tLhLjY/view?usp=sharing) · [Benchmark comparison](https://drive.google.com/file/d/1NBNxL-SrVbipIAYgeQ2ViukUH9xsWoz8/view?usp=sharing)

---

## 1. Input Features

The same 11-feature set used by both models:

```
feat_question_difficulty, feat_current_part_accuracy, feat_answer_changes,
feat_overall_accuracy, feat_reading_accuracy, feat_recent_accuracy,
feat_is_rapid_guess, part, feat_total_attempts,
feat_listening_accuracy, feat_explanation_ratio
```

Missing values are filled with 0 via `df.fillna(0)`. No additional scaling is applied (tree models are scale-invariant).

## 2. Train/Test Split

```python
train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
```

- **Train**: 18,646,961 rows (80%)
- **Test**: 4,661,741 rows (20%)
- Class ratio preserved: 56.87% correct / 43.13% incorrect

> **Methodology note.** This is a **row-level stratified split**, not the `GroupShuffleSplit` by `user_id` that the team's [feature selection report](../../feature_selection/reports/feature_selection_report.md) defined as the canonical split. As a result, interactions from the same student can appear in both training and test sets, which inflates evaluation metrics relative to a true held-out user split. The `test_users_list.csv` produced by feature selection is not consumed here. This divergence should be reconciled if the project requires apples-to-apples comparison across team members' models.

## 3. Random Forest

### Hyperparameters

| Parameter | Value | Rationale (per notebook) |
|---|---|---|
| `n_estimators` | 300 | 300 decision trees |
| `max_depth` | 12 | Cap tree depth |
| `min_samples_leaf` | 50 | Minimum 50 samples per leaf (anti-overfit) |
| `max_features` | `'sqrt'` | sqrt(n_features) per split |
| `class_weight` | `'balanced'` | Compensate for class imbalance |
| `n_jobs` | -1 | All CPU cores |
| `random_state` | 42 | |

### Training

- Wall-clock time: **313.80 minutes** (~5.2 h) on Colab CPU (`n_jobs=-1`, observed 2 concurrent workers).

### Test-set metrics

| Metric | Value |
|---|---|
| AUC-ROC | **0.7146** |
| Accuracy | 0.6520 (65.20%) |
| Precision | 0.7203 |
| Recall | 0.6343 |
| F1-Score | 0.6746 |
| Log Loss | 0.6183 |

### Plots produced

- Feature importance (Mean Decrease in Impurity)
- ROC curve
- Confusion matrix
- Predicted-probability distribution by class

Saved together as `random_forest_evaluation.png` (linked above).

## 4. XGBoost

### Data preparation

The training and test matrices are converted to `xgb.DMatrix` (with `feature_names` retained) for memory efficiency. `scale_pos_weight` is computed from the training class counts:

```
scale_pos_weight = neg_count / pos_count = 0.7585
```

### Hyperparameters

| Parameter | Value |
|---|---|
| `objective` | `binary:logistic` |
| `eval_metric` | `auc` |
| `tree_method` | `hist` (histogram-based; LightGBM-style) |
| `device` | `cpu` |
| `learning_rate` | 0.1 |
| `max_depth` | 9 |
| `min_child_weight` | 50 |
| `subsample` | 0.85 |
| `colsample_bytree` | 0.9942 |
| `scale_pos_weight` | 0.7585 |
| `seed` | 42 |
| `num_boost_round` | 500 |
| `early_stopping_rounds` | 30 |

### Training

- Wall-clock time: **85.37 minutes**.
- Best iteration: **499** (early stopping never triggered — the model was still improving when the round budget ran out).
- Best test AUC during boosting: 0.7220.

Train/test AUC trajectory (selected):

| Round | Train AUC | Test AUC |
|---|---|---|
| 0 | 0.7075 | 0.7070 |
| 100 | 0.7218 | 0.7204 |
| 250 | 0.7243 | 0.7215 |
| 499 | 0.7270 | 0.7220 |

The narrow train–test gap (~0.005 AUC) indicates the model is not overfitting at this depth/min-child-weight setting.

### Test-set metrics

| Metric | Value |
|---|---|
| AUC-ROC | **0.7220** |
| Accuracy | 0.6580 (65.80%) |
| Precision | 0.7242 |
| Recall | 0.6438 |
| F1-Score | 0.6816 |
| Log Loss | 0.6116 |

### Plots produced

- Feature importance by Information Gain (also weight and cover computed)
- Learning curve (AUC vs. boosting rounds for train & test, with best-iteration marker)
- ROC curve
- Confusion matrix
- Predicted-probability distribution by class

Saved together as `xgboost_evaluation.png` (linked above).

## 5. Benchmark Comparison

A consolidated comparison plot (`benchmark_comparison.png`) overlays:

- Bar chart of AUC-ROC, Accuracy, F1-Score (RF vs. XGBoost)
- ROC curves overlaid
- Normalized feature importance side-by-side

| Model | AUC-ROC | Accuracy | F1-Score | Log Loss | Train Time |
|---|---|---|---|---|---|
| Random Forest | 0.7146 | 0.6520 | 0.6746 | 0.6183 | 313.80 min |
| XGBoost | **0.7220** | **0.6580** | **0.6816** | **0.6116** | 85.37 min |

XGBoost is uniformly better across every metric and trains **~3.7× faster** than the Random Forest on the same data and machine.

A LightGBM reference (AUC 0.7223, Accuracy 66.68%) from the team's prior LightGBM run is cited in the comparison bar chart but is not re-trained inside this notebook — see [Nguyễn's report](nguyen_lightgbm_lstm_cnn.md).

## 6. Reproducibility Notes

- All randomness pinned to `random_state=42` / `seed=42`.
- Data path inside notebook is hard-coded to `/content/drive/MyDrive/Colab Notebooks/data mining/`.
- The feature table consumed (`kt4_features_1.parquet`) was produced by Nguyễn's Colab feature-engineering pipeline, **not** by the in-repo `feature_engineering/generate_features.py` (which produces a different file, `kt4_features.parquet`, with a different feature set).
- Re-running the Random Forest cell sequentially takes ~5 h of compute; the saved `.pkl` is provided to skip retraining.
