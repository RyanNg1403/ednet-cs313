# EdNet-KT4: Feature Selection Report

## Overview

This module evaluates the 13 engineered features generated during the Feature Engineering phase to construct the optimal feature set. The selection process ensures maximum predictive power while eliminating redundant information (multicollinearity) and noisy/sparse features.

**Script**: `feature_selection/feature_selection.py`
**Input**: `processed/kt4_features_1.parquet` (18.7M Train rows after split)
**Output 1**: `output/feature_selection/test_users_list.csv` (Holdout user IDs)
**Output 2**: `output/feature_selection/selected_features.json` (file containing 10 final features)

---

## 1. Train/Test Split Strategy

To prevent data leakage, a **Group-based split** (`GroupShuffleSplit`) was applied using `user_id`. This guarantees that a student's entire interaction history belongs strictly to either the training set or the testing set.

- **Train Set:** 18,752,725 rows (80%)
- **Test Set:** 4,555,977 rows (20%)
- **Test Users Record:** Extracted to `test_users_list.csv` to ensure consistency across the team's modeling pipelines without duplicating heavy data files.

## 2. Multicollinearity Analysis (Filter Method)

![Pearson Correlation Matrix](../plots/01_correlation_matrix.png)

A Pearson correlation matrix was calculated across all continuous features on the training set.

### Primary Alert

- **`overall_accuracy` & `reading_accuracy` (r = 0.84):** A severe collinearity was detected. As identified in `03_eda_metadata.md`, Part 5 (Reading) accounts for 43.3% of the entire question bank. Consequently, a student's overall accuracy is overwhelmingly dictated by their reading performance.

### Secondary & Contextual Correlations (Moderate to High)

With the introduction of new contextual features , moderate-to-high correlations were expected among the accuracy metrics.

- **The "Accuracy" Cluster (r = 0.65 to 0.78):** Strong correlations naturally exist between localized metrics like `feat_current_part_accuracy` or `feat_recent_accuracy` and the student's broader competencies.
- **Action Taken (Keep):** Unlike the extreme collinearity (r=0.84) which we dropped, we intentionally retained these features. While they are statistically correlated, they represent distinct educational dimensions:
  - `feat_reading_accuracy` measures long-term domain mastery.
  - `feat_recent_accuracy` acts as a temporal "short-term memory" or fatigue indicator.
  - `feat_current_part_accuracy` measures localized focus.
- **Algorithm Robustness:** Tree-based algorithms (LightGBM) are intrinsically robust to moderate collinearity. By retaining these, the model can cross-reference long-term ability against immediate temporal performance to predict correctness more accurately.

## 3. Statistical Power Analysis (Filter Methods)

Features were individually evaluated against the binary target (`target_is_correct`) using **ANOVA F-test** and **Chi-Square**. Due to the massive sample size (N > 18.5M), a strict p-value threshold (p < 0.001) was observed.

| Feature                      | Method     | Score     | Significance |
| ---------------------------- | ---------- | --------- | ------------ |
| `feat_question_difficulty`   | ANOVA      | 1,763,301 | **Highest**  |
| `feat_current_part_accuracy` | ANOVA      | 430,007   | Very High    |
| `feat_overall_accuracy`      | ANOVA      | 376,266   | Very High    |
| `feat_reading_accuracy`      | ANOVA      | 237,138   | High         |
| `feat_recent_accuracy`       | ANOVA      | 229,954   | High         |
| `feat_listening_accuracy`    | ANOVA      | 178,100   | High         |
| `feat_explanation_ratio`     | ANOVA      | 138,275   | Medium-High  |
| `feat_is_rapid_guess`        | Chi-Square | 57,162    | Medium       |
| `feat_answer_changes`        | ANOVA      | 15,793    | Medium-Low   |
| `feat_adaptive_ratio`        | ANOVA      | 8,785     | Low          |
| `feat_session_fatigue`       | ANOVA      | 4,000+    | Very Low     |
| `feat_lecture_watches`       | ANOVA      | 2,500+    | Very Low     |
| `feat_total_attempts`        | ANOVA      | < 500     | Lowest       |

## 4. Non-Linear Feature Importance (Embedded Method)

![LightGBM Importance](../plots/02_lightgbm_importance.png)

A LightGBM classifier was trained to capture non-linear relationships. Importance was measured using **Information Gain**.

- `feat_question_difficulty` completely dominates, contributing **59.64%** of the model's total information gain.
- `feat_current_part_accuracy` ranks 2nd (10.09%), proving that a student's immediate mastery of a specific domain is a highly reliable predictor.
- `feat_answer_changes`, despite scoring poorly in linear ANOVA, ranked 3rd in LightGBM (8.30%), demonstrating strong non-linear interaction with question difficulty (e.g., changing answers on a hard question strongly indicates uncertainty).

## 5. Synthesis & Final Selection

The final feature set bridges the gap between data-driven metrics and educational domain logic. **Tree-based models can aggregate independent components, but they cannot disentangle aggregated metrics.** Therefore, providing granular features is prioritized over aggregated ones.

### Selected Features (10 Features)

| Feature                      | Rationale                                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------------------------- |
| `feat_question_difficulty`   | **Core Driver:** The most powerful baseline predictor (59.64% Gain).                              |
| `feat_current_part_accuracy` | **Contextual:** Captures the student's mastery of the specific TOEIC Part currently being tested. |
| `feat_answer_changes`        | **Behavioral:** Captures non-linear hesitation signals effectively (8.30% Gain).                  |
| `feat_reading_accuracy`      | **Domain Selection:** Kept over `overall_accuracy` to maintain explainability.                    |
| `feat_recent_accuracy`       | **Temporal:** Captures short-term memory and immediate learning trajectory (3.38% Gain).          |
| `feat_is_rapid_guess`        | **Behavioral:** Robust identifier for random guessing behavior.                                   |
| `feat_total_attempts`        | **Weighting:** Acts as a confidence scalar for the accuracy features.                             |
| `feat_listening_accuracy`    | **Domain Selection:** Independent skill dimension.                                                |
| `feat_session_fatigue`       | **Contextual:** Captures the cognitive load degradation within a study session.                   |
| `feat_explanation_ratio`     | **Behavioral:** Indicator of student engagement and deep learning habits.                         |

### Dropped Features (3 Features)

| Feature                 | Drop Rationale                                                                                                                                                                                                         |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `feat_overall_accuracy` | Dropped to eliminate the severe multicollinearity (r=0.84) with Reading. Providing separate Reading/Listening inputs allows the system to generate actionable, targeted feedback for students.                         |
| `feat_adaptive_ratio`   | **Sparse Data & Low Variance:** Scored poorly (0.05% Gain). Root cause traced back to `02_eda_distributions.md`: the `adaptive_offer` source accounts for only 6.61% of data. For >90% of rows, this feature equals 0. |
| `feat_lecture_watches`  | **Low Predictive Power:** Ranked at the absolute bottom in Information Gain (0.02%). Adds dimensionality without improving accuracy.                                                                                   |

---
