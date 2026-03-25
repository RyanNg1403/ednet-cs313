"""
02_eda_overview.py
==================
Structural overview of the KT4 dataset + contents metadata.
Produces a text report and basic summary visualizations.

Requires: processed/kt4_interactions.parquet (from 01_convert_to_parquet.py)
Output:   output/reports/01_overview.txt
          output/plots/01_missing_values.png
          output/plots/01_dtypes_summary.png
"""

import os
import sys
import pandas as pd
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARQUET_FILE = os.path.join(BASE_DIR, "processed", "kt4_interactions.parquet")
CONTENTS_DIR = os.path.join(BASE_DIR, "contents")
PLOTS_DIR = os.path.join(BASE_DIR, "output", "eda", "plots")
REPORTS_DIR = os.path.join(BASE_DIR, "output", "eda", "reports")
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.1)


def section(title: str) -> str:
    return f"\n{'=' * 60}\n{title}\n{'=' * 60}"


def main():
    report_lines = []

    def log(msg: str = ""):
        print(msg)
        report_lines.append(msg)

    # ── 1. KT4 Interactions ────────────────────────────────────────────
    log(section("KT4 INTERACTIONS — STRUCTURAL OVERVIEW"))

    if not os.path.exists(PARQUET_FILE):
        log(f"ERROR: {PARQUET_FILE} not found. Run 01_convert_to_parquet.py first.")
        sys.exit(1)

    # Read parquet metadata without loading data
    pf = pq.ParquetFile(PARQUET_FILE)
    metadata = pf.metadata
    schema = pf.schema_arrow

    log(f"\nFile: {PARQUET_FILE}")
    log(f"File size: {os.path.getsize(PARQUET_FILE) / (1024**2):,.1f} MB")
    log(f"Total rows: {metadata.num_rows:,}")
    log(f"Row groups: {metadata.num_row_groups}")
    log(f"Columns: {metadata.num_columns}")

    log(f"\nSchema:")
    for i in range(len(schema)):
        field = schema.field(i)
        log(f"  {field.name:20s}  {str(field.type):30s}  nullable={field.nullable}")

    # Load full dataset for analysis
    log("\nLoading data into memory...")
    df = pd.read_parquet(PARQUET_FILE)
    mem_mb = df.memory_usage(deep=True).sum() / (1024**2)
    log(f"In-memory size: {mem_mb:,.1f} MB")
    log(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")

    # ── 2. Data types ──────────────────────────────────────────────────
    log(section("COLUMN DATA TYPES"))
    for col in df.columns:
        log(f"  {col:20s}  dtype={str(df[col].dtype):20s}  "
            f"nunique={df[col].nunique():,}")

    # ── 3. Missing values ──────────────────────────────────────────────
    log(section("MISSING VALUES"))
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    for col in df.columns:
        log(f"  {col:20s}  {missing[col]:>12,} missing  ({missing_pct[col]:6.2f}%)")

    # Plot missing values
    fig, ax = plt.subplots(figsize=(10, 5))
    cols_with_missing = missing_pct[missing_pct > 0]
    if len(cols_with_missing) > 0:
        cols_with_missing.sort_values(ascending=True).plot.barh(ax=ax, color="salmon")
        ax.set_xlabel("Missing (%)")
        ax.set_title("Missing Values by Column")
        for i, (col, pct) in enumerate(cols_with_missing.sort_values(ascending=True).items()):
            ax.text(pct + 0.3, i, f"{pct:.1f}%", va="center", fontsize=10)
    else:
        ax.text(0.5, 0.5, "No missing values found!", ha="center", va="center",
                transform=ax.transAxes, fontsize=14)
        ax.set_title("Missing Values by Column")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "01_missing_values.png"), dpi=150)
    plt.close()
    log(f"\n  → Saved: output/plots/01_missing_values.png")

    # ── 4. Basic statistics for numeric columns ────────────────────────
    log(section("NUMERIC COLUMN STATISTICS"))
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        stats = df[col].describe()
        log(f"\n  {col}:")
        for stat_name, val in stats.items():
            log(f"    {stat_name:10s}  {val:>20,.2f}")

    # ── 5. Categorical column value counts (top 10) ────────────────────
    log(section("CATEGORICAL COLUMN VALUE COUNTS"))
    cat_cols = ["action_type", "source", "platform", "user_answer"]
    for col in cat_cols:
        vc = df[col].value_counts(dropna=False)
        log(f"\n  {col} ({vc.shape[0]} unique values):")
        for val, cnt in vc.head(15).items():
            pct = cnt / len(df) * 100
            label = val if pd.notna(val) else "<NaN>"
            log(f"    {str(label):30s}  {cnt:>12,}  ({pct:5.2f}%)")

    # ── 6. Contents metadata overview ──────────────────────────────────
    log(section("CONTENTS METADATA"))

    contents_files = {
        "questions": os.path.join(CONTENTS_DIR, "questions.csv"),
        "lectures": os.path.join(CONTENTS_DIR, "lectures.csv"),
        "payments": os.path.join(CONTENTS_DIR, "payments.csv"),
        "coupons": os.path.join(CONTENTS_DIR, "coupons.csv"),
    }

    for name, path in contents_files.items():
        if os.path.exists(path):
            cdf = pd.read_csv(path)
            log(f"\n  {name}.csv:")
            log(f"    Shape: {cdf.shape[0]:,} rows × {cdf.shape[1]} columns")
            log(f"    Columns: {', '.join(cdf.columns.tolist())}")
            missing_c = cdf.isnull().sum()
            cols_missing = missing_c[missing_c > 0]
            if len(cols_missing) > 0:
                log(f"    Missing values:")
                for c, cnt in cols_missing.items():
                    log(f"      {c}: {cnt:,} ({cnt / len(cdf) * 100:.1f}%)")
            else:
                log(f"    Missing values: none")

    # ── 7. User-level summary ──────────────────────────────────────────
    log(section("USER-LEVEL SUMMARY"))
    user_counts = df.groupby("user_id").size()
    log(f"  Total unique users: {user_counts.shape[0]:,}")
    log(f"  Interactions per user:")
    log(f"    Mean:   {user_counts.mean():,.1f}")
    log(f"    Median: {user_counts.median():,.1f}")
    log(f"    Std:    {user_counts.std():,.1f}")
    log(f"    Min:    {user_counts.min():,}")
    log(f"    Max:    {user_counts.max():,}")
    log(f"    Q1:     {user_counts.quantile(0.25):,.1f}")
    log(f"    Q3:     {user_counts.quantile(0.75):,.1f}")

    # ── Save report ────────────────────────────────────────────────────
    report_path = os.path.join(REPORTS_DIR, "01_overview.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    log(f"\n→ Report saved: {report_path}")

    del df


if __name__ == "__main__":
    main()
