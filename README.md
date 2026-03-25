# EdNet-KT4: CS313 Data Mining Project

> **Course**: CS313 — Data Mining and Applications, Spring 2026
> **University**: University of Information Technology, VNUHCM

## About

Data mining project built on **EdNet-KT4** — the largest public educational interaction dataset (131M interactions, 298K students), collected from [Santa](https://santatoeic.com/), a TOEIC preparation platform by Riiid.

## Repository Structure

```
scripts/                          # Reproducible Python pipeline
├── 01_convert_to_parquet.py      # 297K CSVs → single parquet (6.4GB → 1.3GB)
├── 02_eda_overview.py            # Structural overview & missing values
├── 03_eda_distributions.py       # Column distributions & cross-tabs
├── 04_eda_metadata.py            # Question difficulty, tags, lectures
├── 05_eda_temporal.py            # Temporal & user growth patterns
└── 06_preprocess.py              # Cleaning, integration, transformation
output/
├── plots/                        # 28 visualizations
└── reports/                      # Detailed Markdown reports (reference all plots)
```

Raw data (`KT4/`, `contents/`, `processed/`) is excluded from git due to size.

## Key Findings

Full reports with plots: [`output/reports/`](output/reports/)

- **Extremely skewed user activity**: median 31 interactions vs. mean 441
- **Sprint mode dominates** (71%) — students prefer self-directed practice over system recommendations
- **71% mobile, 29% web**; `undo_erase_choice` only exists on web
- **56.87% overall accuracy** across 23M responses
- **Part 5 (grammar) overrepresented** at 43% of all questions
- **Bimodal activity peaks** in Jan 2019 and Jul-Aug 2019 (TOEIC exam seasons)
- **461K exact duplicates** (0.35%) detected and removed; all missing values are structural

## Setup

1. Download [EdNet-KT4](http://bit.ly/ednet-kt4) and [Contents](http://bit.ly/ednet-content), extract into project root
2. Run:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install pandas pyarrow matplotlib seaborn numpy tqdm
   python scripts/01_convert_to_parquet.py    # ~5 min
   python scripts/02_eda_overview.py
   python scripts/03_eda_distributions.py
   python scripts/04_eda_metadata.py
   python scripts/05_eda_temporal.py
   python scripts/06_preprocess.py
   ```

## Acknowledgments

This project uses the **EdNet** dataset by Riiid (now Socra AI):

> Youngduck Choi, Youngnam Lee, Dongmin Shin, et al. *"EdNet: A Large-Scale Hierarchical Dataset in Education."* AIED, 2020. [[Paper]](https://arxiv.org/abs/1912.03072) [[Original Repo]](https://github.com/riiid/ednet)

Dataset licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
