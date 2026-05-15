# EdNet-KT4: LightGBM & LSTM Modeling Report

**Author**: Nguyễn (Võ Thế Nguyễn)

## Overview

The notebook contains the following relevant models:

1. LightGBM with engineered features
2. LSTM with engineered features
3. LSTM with raw sequential features
4. Baseline LightGBM with raw features


# 1. Train / Validation / Test Split

The notebook first creates a user-level split to avoid data leakage between train and test users.

```python
df_users = pd.read_parquet(FILE_ULTIMATE, columns=['user_id'])
all_users = df_users['user_id'].unique()

train_val_users, test_users = train_test_split(
    all_users,
    test_size=0.2,
    random_state=42
)

train_users, valid_users = train_test_split(
    train_val_users,
    test_size=0.1,
    random_state=42
)

np.save(SAVE_DIR + 'train_users.npy', train_users)
np.save(SAVE_DIR + 'valid_users.npy', valid_users)
np.save(SAVE_DIR + 'test_users.npy', test_users)
```

### Split summary

| Dataset | Description |
|---|---|
| Train | Used for model training |
| Validation | Used for monitoring neural-network training |
| Test | Completely isolated for final evaluation |

This user-level split is shared across all models in the notebook.

---

# 2. LightGBM (11 Engineered Features)

## Training Configuration

The notebook trains a LightGBM model using 11 engineered features extracted from the processed EdNet-KT4 dataset.

### Features used

```python
FEATURES_11 = [
    'feat_question_difficulty',
    'feat_current_part_accuracy',
    'feat_answer_changes',
    'feat_overall_accuracy',
    'feat_reading_accuracy',
    'feat_recent_accuracy',
    'feat_is_rapid_guess',
    'part',
    'feat_total_attempts',
    'feat_listening_accuracy',
    'feat_explanation_ratio'
]
```

### Model parameters

```python
params = {
    'objective': 'binary',
    'metric': 'auc',
    'boosting_type': 'gbdt',
    'learning_rate': 0.05,
    'num_leaves': 63,
    'max_depth': 8,
    'feature_fraction': 0.8,
    'device_type': 'cpu',
    'verbose': -1
}
```

### Training strategy

- Chunked incremental training
- Chunk size: 40,000 users
- Validation users loaded separately
- Boosting continued between chunks using `init_model`

---

## LightGBM Results

### Final evaluation metrics

| Metric | Value |
|---|---|
| AUC-ROC | **0.6812** |
| Accuracy | 0.6330 |
| Precision | 0.6381 |
| Recall | 0.5205 |
| F1-Score | 0.5733 |
| Log Loss | 0.6368 |

---

# 3. LSTM Hybrid (11 Engineered Features)

## Model Architecture

The notebook implements an LSTM sequence model using the same 11 engineered features as LightGBM.

```python
model = Sequential([
    Input(shape=(MAX_LEN, len(FEATURES_11))),
    Masking(mask_value=-99.0),

    LSTM(128, return_sequences=False),

    BatchNormalization(),
    Dropout(0.3),

    Dense(64, activation='relu'),
    Dropout(0.2),

    Dense(1, activation='sigmoid')
])
```

---

## Feature preprocessing

Several features are rescaled before training:

```python
X[:,:,7] = X[:,:,7] / 7.0
X[:,:,2] = np.log1p(X[:,:,2]) / 5.0
X[:,:,8] = np.log1p(X[:,:,8]) / 10.0
```

### Meaning of transformed features

| Feature Index | Feature | Transformation |
|---|---|---|
| 7 | `part` | divide by 7 |
| 2 | `feat_answer_changes` | `log1p(x)/5` |
| 8 | `feat_total_attempts` | `log1p(x)/10` |

---

## Training Strategy

- Sequence length: 100
- Chunk size: 30,000 users
- 5 outer training epochs
- Validation monitoring enabled
- Padding value: `-99.0`

---

## LSTM Hybrid Results

| Metric | Value |
|---|---|
| AUC-ROC | **0.6868** |
| Accuracy | 0.6354 |
| Precision | 0.6847 |
| Recall | 0.4209 |
| F1-Score | 0.5214 |
| Log Loss | 0.6580 |

---

## Analysis

The engineered-feature LSTM achieved the highest AUC-ROC among Nguyễn's notebook models.

Key observations:

- The model benefits significantly from engineered statistical features.
- Sequential modeling allows the network to learn temporal learning behavior.
- The model performs better than the raw-feature LSTM by a large margin.
- The engineered features appear to provide stronger predictive signals than raw interaction features alone.

However:

- Recall remains relatively low compared to precision.
- The model may still under-utilize long historical context because only the last 100 interactions are retained.

---

# 4. LSTM Raw Sequential Model

## Raw input features

The raw LSTM model uses four sequential features:

```python
['part', 'time_since_prev', 'hour', 'is_correct']
```

The notebook preprocesses them as:

```python
df['part'] = df['part'] / 7.0
df['time_since_prev'] = np.log1p(df['time_since_prev']) / 15.0
df['hour'] = df['hour'] / 24.0
```

---

## Model Architecture

```python
model_lstm = Sequential([
    Input(shape=(MAX_LEN, 4)),
    Masking(mask_value=-99.0),

    LSTM(128, return_sequences=False),

    BatchNormalization(),
    Dropout(0.3),

    Dense(64, activation='relu'),
    Dropout(0.2),

    Dense(1, activation='sigmoid')
])
```

---

## Training Strategy

- Sequence length: 100
- Chunk size: 40,000 users
- Trained incrementally across chunks
- Validation data used during training

---

## LSTM Raw Results

| Metric | Value |
|---|---|
| AUC-ROC | **0.6107** |
| Accuracy | 0.5871 |
| Precision | 0.6370 |
| Recall | 0.2898 |
| F1-Score | 0.3984 |
| Log Loss | 0.6779 |

---

## Analysis

The raw-feature LSTM performs substantially worse than the engineered-feature LSTM.

Reasons include:

- The raw features contain much less semantic information.
- No explicit difficulty-related features are available.
- The model must infer behavior patterns directly from sparse interaction signals.
- Engineered statistics such as recent accuracy and question difficulty are absent.

Despite lower overall performance, the raw LSTM still demonstrates that sequential learning behavior contains useful predictive information.

---

# 5. Baseline LightGBM (Raw Features)

The notebook also includes a baseline LightGBM model trained directly on raw features.

## Features

```python
RAW_FEATURES = [
    'part',
    'time_since_prev',
    'hour'
]
```

---

## Training Strategy

- Chunk-based training
- Chunk size: 50,000 users
- Incremental boosting between chunks
- Validation monitoring enabled

---

## Baseline LightGBM Results

| Metric | Value |
|---|---|
| AUC-ROC | **0.5893** |
| Accuracy | 0.5355 |
| F1-Score | 0.6124 |
| Log Loss | 0.6913 |

---

## Analysis

The baseline LightGBM model achieves the weakest AUC among the retained models.

Main limitations:

- Only three raw numerical features are available.
- No temporal sequence modeling is used.
- No engineered knowledge-tracing statistics are included.

This result highlights the importance of both:

1. Feature engineering
2. Sequential modeling

for educational knowledge tracing tasks.

---

# 6. Cross-Model Comparison

## Unified benchmark table

| Model | AUC-ROC | Accuracy | F1-Score | Log Loss |
|---|---|---|---|---|
| Baseline LightGBM (Raw) | 0.5893 | 0.5355 | 0.6124 | 0.6913 |
| LSTM (Raw) | 0.6107 | 0.5871 | 0.3984 | 0.6779 |
| LSTM (Engineered) | **0.6868** | **0.6354** | 0.5214 | 0.6580 |
| LightGBM (Engineered) | 0.6812 | 0.6330 | **0.5733** | **0.6368** |

---

# 7. Final Discussion

The notebook demonstrates several important findings for EdNet-KT4 knowledge tracing:

## Best-performing approaches

### Best AUC-ROC
- LSTM with engineered features: **0.6868**

### Best F1-Score
- LightGBM with engineered features: **0.5733**

### Lowest Log Loss
- LightGBM with engineered features: **0.6368**

---

## Key conclusions

### Engineered features are highly important

The strongest models are both trained on engineered educational statistics rather than raw interaction data.

Important signals include:

- Question difficulty
- Recent student accuracy
- Overall student performance
- Attempt behavior
- Rapid guessing indicators

---

### Sequential modeling improves representation learning

The LSTM models successfully capture temporal learning patterns across student interactions.

Using ordered interaction histories allows the model to learn:

- Behavioral consistency
- Knowledge progression
- Recent performance trends

---

### Raw features alone are insufficient

Models trained only on raw interaction attributes perform significantly worse than engineered-feature models.

This suggests that:

- Educational feature engineering remains critical
- Statistical student-history summaries provide strong predictive power
- Temporal structure alone cannot fully compensate for weak input features

---

# 8. Artifact Summary

| Artifact | Description |
|---|---|
| `train_users.npy` | Train user split |
| `valid_users.npy` | Validation user split |
| `test_users.npy` | Test user split |
| `lightgbm_final_model.pkl` | Engineered-feature LightGBM model |
| `ednet_lstm_11_features.keras` | Engineered-feature LSTM model |
| `ednet_lstm_raw.keras` | Raw-feature LSTM model |
| `kt4_features_ultimate.parquet` | Engineered-feature dataset |
| `kt4_preprocessed.parquet` | Raw interaction dataset |

