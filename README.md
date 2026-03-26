# EdNet-KT4: CS313 Data Mining Project

> **Course**: CS313 — Data Mining and Applications, Spring 2026
> **University**: University of Information Technology, VNUHCM

## About

Data mining project built on **EdNet-KT4** — the largest public educational interaction dataset (131M interactions, 298K students), collected from [Santa](https://santatoeic.com/), a TOEIC preparation platform by Riiid.

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
feature_engineering/              # Feature Extraction & Data Leakage Prevention
└── feature_creation/
    ├── feature_creation.md       # Methodology, correlation & distribution analysis
    └── plots/                    # Visualizations of engineered features
output/
├── eda/                          # EDA plots (26) & reports
│   ├── plots/
│   └── reports/
└── preprocessing/                # Preprocessing plots (2) & report
    ├── plots/
    └── reports/
```

Raw data (`KT4/`, `contents/`, `processed/`) and engineered features (`kt4_features.parquet`) are excluded from git due to size.

## Key Findings & Engineered Features

Full reports with plots: 
- EDA: [`output/eda/reports/`](output/eda/reports/) 
- Preprocessing: [`output/preprocessing/reports/`](output/preprocessing/reports/)
- Feature Engineering: [`feature_engineering/feature_creation/feature_creation.md`](feature_engineering/feature_creation/feature_creation.md)

**EDA Highlights:**
- **Extremely skewed user activity**: median 31 interactions vs. mean 441
- **Sprint mode dominates** (71%) — students prefer self-directed practice over system recommendations
- **71% mobile, 29% web**; `undo_erase_choice` only exists on web
- **56.87% overall accuracy** across 23M responses
- **Part 5 (grammar) overrepresented** at 43% of all questions
- **Bimodal activity peaks** in Jan 2019 and Jul-Aug 2019 (TOEIC exam seasons)
- **461K exact duplicates** (0.35%) detected and removed; all missing values are structural

**Feature Engineering Highlights:**
- Extracted 4 groups of features: Historical Mastery, Local/Skill Mastery, Pedagogical Strategy, and Behavioral Dynamics.
- Strictly prevented **Data Leakage** using out-of-core SQL Window Functions (`1 PRECEDING`).
- Created `feat_session_fatigue` (1-hour rolling window) and `feat_is_rapid_guess` (<3.2s gap) to capture student cognitive load and guessing behavior.

## Setup

1. Download [EdNet-KT4](http://bit.ly/ednet-kt4) and [Contents](http://bit.ly/ednet-content), extract into project root.
2. Run:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install pandas pyarrow matplotlib seaborn numpy tqdm duckdb polars
   python eda/01_convert_to_parquet.py    # ~5 min
   python eda/02_eda_overview.py
   python eda/03_eda_distributions.py
   python eda/04_eda_metadata.py
   python eda/05_eda_temporal.py
   python preprocessing/preprocess.py
   ```
*(Note: Feature engineering was executed out-of-core via DuckDB directly on the parquet files to optimize memory).*

## Acknowledgments

### Course Instructor

<img src="assets/ThayDuyCute.png" alt="Vo Nguyen Le Duy" width="180" align="right" />

This project was completed under the guidance of **Vo Nguyen Le Duy**, lecturer at the University of Information Technology (VNUHCM) and researcher at RIKEN, Japan. His CS313 course provided the theoretical foundation in data mining — from preprocessing techniques to pattern discovery — that shaped the methodology and analysis in this project. We are grateful for his instruction and the well-structured curriculum that made this work possible.

Contact: [duyvnl@uit.edu.vn](mailto:duyvnl@uit.edu.vn)

### Dataset

This project uses the **EdNet** dataset by Riiid (now Socra AI):

> Youngduck Choi, Youngnam Lee, Dongmin Shin, et al. *"EdNet: A Large-Scale Hierarchical Dataset in Education."* AIED, 2020. [[Paper]](https://arxiv.org/abs/1912.03072) [[Original Repo]](https://github.com/riiid/ednet)

Dataset licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).