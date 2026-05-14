# EdNet-KT4: CS313 Data Mining Project

> **Course**: CS313 — Data Mining and Applications, Spring 2026
> **University**: University of Information Technology, VNUHCM

## About

Data mining project built on **EdNet-KT4** — the largest public educational interaction dataset (131M interactions, 298K students), collected from [Santa](https://santatoeic.com/), a TOEIC preparation platform by Riiid.

## Data

Raw data and processed outputs are excluded from git due to size. Download from the links below.

| File                       | Description                                                          | Source                                                                                                |
| -------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| EdNet-KT4 (raw)            | 297K per-user CSV files, 6.4 GB                                      | [Download](http://bit.ly/ednet-kt4)                                                                   |
| Contents (metadata)        | Questions, lectures, payments, coupons                               | [Download](http://bit.ly/ednet-content)                                                               |
| `kt4_preprocessed.parquet` | Cleaned & integrated dataset (131M rows, 30 cols)                    | [Google Drive](https://drive.google.com/file/d/1-y5GXRjb9xs1JMt8L0R_D6eOjzZpfvHI/view?usp=drive_link) |
| `kt4_features.parquet`     | Engineered features for correctness prediction (23.3M rows, 15 cols) | [Google Drive](https://drive.google.com/file/d/1CGxjrjg97-JZ602ll0tbRm3o2kAaD6H4/view?usp=drive_link) |

## Repository Structure

```text
eda/                              # Exploratory Data Analysis
├── 01_convert_to_parquet.py      # 297K CSVs → single parquet (6.4GB → 1.3GB)
├── 02_eda_overview.py            # Structural overview & missing values
├── 03_eda_distributions.py       # Column distributions & cross-tabs
├── 04_eda_metadata.py            # Question difficulty, tags, lectures
└── 05_eda_temporal.py            # Temporal & user growth patterns
preprocessing/                    # Data Cleaning, Integration, Transformation
└── preprocess.py
feature_engineering/              # Feature Extraction for Correctness Prediction
└── generate_features.py
feature_selection/                # Optimal Feature Set Selection
└── feature_selection.py
output/
├── eda/                          # EDA plots (26) & reports
│   ├── plots/
│   └── reports/
├── preprocessing/                # Preprocessing plots (2) & report
│   ├── plots/
│   └── reports/
├── feature_engineering/          # Feature engineering plots (2) & report
│   ├── plots/
│   └── reports/
├── feature_selection/            # Selection plots, metrics (CSV) & report
│   ├── metrics/
│   ├── plots/
│   └── reports/
└── modeling/                     # Per-model training methodology reports
    └── reports/
```

## Key Findings

Full reports with plots:

- EDA: [`output/eda/reports/`](output/eda/reports/)
- Preprocessing: [`output/preprocessing/reports/`](output/preprocessing/reports/)
- Feature Engineering: [`output/feature_engineering/reports/`](output/feature_engineering/reports/)
- Feature Selection: [`output/feature_selection/reports/`](output/feature_selection/reports/)
- Modeling: [`output/modeling/reports/`](output/modeling/reports/)

## EDA

- **Extremely skewed user activity**: median 31 interactions vs. mean 441
- **Sprint mode dominates** (71%) — students prefer self-directed practice over system recommendations
- **71% mobile, 29% web**; `undo_erase_choice` only exists on web
- **56.87% overall accuracy** across 23M responses
- **Part 5 (grammar) overrepresented** at 43% of all questions
- **Bimodal activity peaks** in Jan 2019 and Jul-Aug 2019 (TOEIC exam seasons)
- **461K exact duplicates** (0.35%) detected and removed; all missing values are structural

## Modeling

Both members retrained on **2026-05-14** with a shared user-level train/test split (`train_test_split(unique_users, test_size=0.2, random_state=42)` on `kt4_features_ultimate.parquet`). All six models scored on the same 59,341 test users (within 1 user), each user's last response.

| Author | Model | Plan B AUC | Source | Drive |
|---|---|---|---|---|
| Phương | XGBoost | **0.6871** | [notebook + folder](https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_?usp=sharing) | `xgboost_final_model.json` |
| Phương | Random Forest | 0.6831 | same | `random_forest_final_model.pkl` |
| Nguyễn | LightGBM | 0.6812 | [v2 Colab](https://colab.research.google.com/drive/1P768sw_p2qG13LUwcUSomdZOtiesDjEK?usp=drive_link) + [folder](https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397?usp=sharing) | `lightgbm_final_model.pkl` |
| Nguyễn | 1D-CNN-raw | 0.5992 | same | `ednet_1d_cnn_raw.keras` |
| Nguyễn | LSTM-raw | 0.5732 | same | `ednet_lstm_raw.keras` |
| Nguyễn | LSTM-11-features | 0.5011* | same | `ednet_lstm_11_features.keras` |

\* LSTM-11-features collapses to near-random AUC despite seeing the same 11 features as LightGBM — likely a training-time preprocessing bug; flagged for investigation. See [`cross_member_review.md`](output/modeling/reports/cross_member_review.md) §4.

Per-member methodology, hyperparameters, and per-task notes:

- [`phuong_random_forest_xgboost.md`](output/modeling/reports/phuong_random_forest_xgboost.md)
- [`nguyen_lightgbm_lstm_cnn.md`](output/modeling/reports/nguyen_lightgbm_lstm_cnn.md)
- [`cross_member_review.md`](output/modeling/reports/cross_member_review.md) — apples-to-apples comparison
- [`data_and_splits_per_model.md`](output/modeling/reports/data_and_splits_per_model.md) — exact train/test splits per model

## Setup

1. Download [EdNet-KT4](http://bit.ly/ednet-kt4) and [Contents](http://bit.ly/ednet-content), extract into project root
2. Run:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install pandas pyarrow matplotlib seaborn numpy tqdm lightgbm scikit-learn
   python eda/01_convert_to_parquet.py    # ~5 min
   python eda/02_eda_overview.py
   python eda/03_eda_distributions.py
   python eda/04_eda_metadata.py
   python eda/05_eda_temporal.py
   python preprocessing/preprocess.py
   python feature_engineering/generate_features.py
   python feature_selection/feature_selection.py
   ```
3. Model training: see the [Modeling](#modeling) table above. Each member's notebook runs on Google Colab against the shared Drive feature tables.

## Acknowledgments

### Course Instructor

<img src="assets/ThayDuyCute.png" alt="Vo Nguyen Le Duy" width="180" align="right" />

This project was completed under the guidance of **Vo Nguyen Le Duy**, lecturer at the University of Information Technology (VNUHCM) and researcher at RIKEN, Japan. His CS313 course provided the theoretical foundation in data mining — from preprocessing techniques to pattern discovery — that shaped the methodology and analysis in this project. We are grateful for his instruction and the well-structured curriculum that made this work possible.

Contact: [duyvnl@uit.edu.vn](mailto:duyvnl@uit.edu.vn)

### Dataset

This project uses the **EdNet** dataset by Riiid (now Socra AI):

> Youngduck Choi, Youngnam Lee, Dongmin Shin, et al. _"EdNet: A Large-Scale Hierarchical Dataset in Education."_ AIED, 2020. [[Paper]](https://arxiv.org/abs/1912.03072) [[Original Repo]](https://github.com/riiid/ednet)

Dataset licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
