# EdNet-KT4: CS313 Data Mining Project

> **Course**: CS313 — Data Mining and Applications, Spring 2026
> **University**: University of Information Technology, VNUHCM
> **Instructor**: Vo Nguyen Le Duy (UIT-VNUHCM / RIKEN)

## About

This repository contains our team's data mining project for CS313, built on the **EdNet-KT4** dataset — the largest publicly available educational interaction dataset, collected from [Santa](https://santatoeic.com/), a TOEIC preparation platform by Riiid.

We use EdNet-KT4 to explore student learning behaviors, mine interesting patterns, and apply data mining techniques covered in the course curriculum.

### Dataset at a Glance

| Property | Value |
|---|---|
| Interactions | 131,441,538 |
| Students | 297,915 |
| Questions | 13,169 (across 7 TOEIC parts) |
| Lectures | 1,021 |
| Skill tags | 189 |
| Action types | 13 (respond, enter, submit, play/pause audio/video, erase_choice, pay, ...) |
| Time span | ~461 days (Aug 2018 – Dec 2019) |

## Project Structure

```
.
├── scripts/                        # Reproducible Python pipeline
│   ├── 01_convert_to_parquet.py    # Consolidate 297K CSVs → single parquet
│   ├── 02_eda_overview.py          # Structural overview & missing values
│   ├── 03_eda_distributions.py     # Column distributions & cross-tabs
│   ├── 04_eda_metadata.py          # Question difficulty, tags, lectures
│   ├── 05_eda_temporal.py          # Temporal & user growth patterns
│   └── 06_preprocess.py            # Cleaning, integration, transformation
├── output/
│   ├── plots/                      # 28 visualizations (referenced in reports)
│   └── reports/                    # Detailed Markdown reports
│       ├── 01_eda_overview.md
│       ├── 02_eda_distributions.md
│       ├── 03_eda_metadata.md
│       ├── 04_eda_temporal.md
│       └── 05_preprocessing.md
├── KT4/                            # Raw data (not committed, see below)
├── contents/                       # Content metadata (not committed)
├── processed/                      # Parquet outputs (not committed)
└── README.md
```

> **Note**: Raw data (`KT4/`, `contents/`, `processed/`) is excluded from git due to size. See [Data Setup](#data-setup) to reproduce locally.

## Project Progress

### Phase 1: EDA & Preprocessing (current)

- [x] Data conversion (297K CSVs → 1.3GB Parquet)
- [x] Exploratory data analysis (28 plots, 5 reports)
- [x] Data cleaning (461K duplicates removed, outlier flagging, consistency checks)
- [x] Data integration (merged with question/lecture metadata, computed correctness)
- [x] Data transformation (feature engineering, normalization, discretization, encoding)

### Phase 2: Pattern Mining (upcoming)

- [ ] Frequent itemset mining (skill co-occurrence patterns)
- [ ] Sequential pattern mining (learning behavior sequences)
- [ ] Association rule mining

### Phase 3: Machine Learning (upcoming)

- [ ] Correctness prediction (classification)
- [ ] Clustering (student behavior segmentation)
- [ ] Model evaluation & comparison

### Phase 4: Deliverables (upcoming)

- [ ] Web demo
- [ ] Final report (English)

## Key Findings (EDA)

Detailed reports with plots are in [`output/reports/`](output/reports/). Highlights:

- **User activity is extremely skewed**: median 31 interactions vs. mean 441. The top 1% of users account for a disproportionate share of data.
- **Sprint mode dominates** (71% of all activity) — students strongly prefer self-directed practice over system recommendations.
- **Mobile-first**: 71% mobile, 29% web. The `undo_erase_choice` action only exists on web (absent from mobile UI).
- **Overall accuracy is 56.87%** across 23M responses — well-calibrated difficulty.
- **Part 5 (grammar) is overrepresented** at 43% of all questions.
- **Bimodal activity peaks** in Jan 2019 and Jul-Aug 2019, likely aligned with TOEIC exam seasons.
- **461K exact duplicate rows** (0.35%) were detected and removed during preprocessing.
- All missing values are **structural** (column not applicable to that action type), not data quality issues.

## Data Setup

To reproduce the pipeline locally:

1. Download [EdNet-KT4](http://bit.ly/ednet-kt4) and [Contents](http://bit.ly/ednet-content)
2. Extract `KT4/` and `contents/` into the project root
3. Set up the environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install pandas pyarrow matplotlib seaborn numpy tqdm
   ```
4. Run the pipeline in order:
   ```bash
   python scripts/01_convert_to_parquet.py   # ~5 min, produces processed/kt4_interactions.parquet
   python scripts/02_eda_overview.py
   python scripts/03_eda_distributions.py
   python scripts/04_eda_metadata.py
   python scripts/05_eda_temporal.py
   python scripts/06_preprocess.py            # produces processed/kt4_preprocessed.parquet
   ```

## Acknowledgments

This project is built on the **EdNet** dataset by Riiid (now Socra AI). We thank the original authors for making this large-scale educational dataset publicly available.

> Youngduck Choi, Youngnam Lee, Dongmin Shin, Junghyun Cho, Seoyon Park, Seewoo Lee, Jineon Baek, Chan Bae, Byungsoo Kim, Jaewe Heo. *"EdNet: A Large-Scale Hierarchical Dataset in Education."* International Conference on Artificial Intelligence in Education (AIED), 2020.
>
> Paper: https://arxiv.org/abs/1912.03072
> Original repository: https://github.com/riiid/ednet

## License

The EdNet dataset is released under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) for research purposes. The code in this repository is for academic use as part of the CS313 course project.
