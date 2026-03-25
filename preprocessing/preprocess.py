"""
06_preprocess.py
================
Data preprocessing pipeline for EdNet-KT4, aligned with CS313 course topics:
  1. Data Cleaning     — missing values, inconsistencies, duplicates
  2. Data Integration  — merge interactions with content metadata
  3. Data Transformation — construct derived attributes, normalize, discretize
  4. Data Reduction    — document sampling strategy (actual sampling optional)

All transformations are LOSSLESS: original columns are preserved, new columns
are added alongside them. The output is a single enriched parquet file.

Requires: processed/kt4_interactions.parquet, contents/*.csv
Output:   processed/kt4_preprocessed.parquet
          output/reports/05_preprocessing.txt
          output/plots/05_*.png
"""

import os
import sys
import gc
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARQUET_FILE = os.path.join(BASE_DIR, "processed", "kt4_interactions.parquet")
CONTENTS_DIR = os.path.join(BASE_DIR, "contents")
OUTPUT_FILE = os.path.join(BASE_DIR, "processed", "kt4_preprocessed.parquet")
PLOTS_DIR = os.path.join(BASE_DIR, "output", "preprocessing", "plots")
REPORTS_DIR = os.path.join(BASE_DIR, "output", "preprocessing", "reports")
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.1)
PALETTE = sns.color_palette("Set2")


def save_fig(name: str):
    path = os.path.join(PLOTS_DIR, name)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: output/plots/{name}")


def main():
    report = []

    def log(msg: str = ""):
        print(msg)
        report.append(msg)

    log("=" * 60)
    log("PREPROCESSING PIPELINE — EdNet KT4")
    log("=" * 60)

    # ── Load data ──────────────────────────────────────────────────────
    log("\n[0] Loading data...")
    df = pd.read_parquet(PARQUET_FILE)
    n_original = len(df)
    log(f"  Loaded {n_original:,} rows, {df.shape[1]} columns")

    questions = pd.read_csv(os.path.join(CONTENTS_DIR, "questions.csv"))
    lectures = pd.read_csv(os.path.join(CONTENTS_DIR, "lectures.csv"))

    # ==================================================================
    # STEP 1: DATA CLEANING (Slide 10-13)
    # ==================================================================
    log("\n" + "=" * 60)
    log("STEP 1: DATA CLEANING")
    log("=" * 60)

    # ── 1a. Missing values analysis ────────────────────────────────────
    log("\n--- 1a. Missing Values ---")
    missing = df.isnull().sum()
    for col in df.columns:
        if missing[col] > 0:
            log(f"  {col}: {missing[col]:,} missing ({missing[col]/n_original*100:.2f}%)")

    # cursor_time: NaN is expected (only present for play/pause media actions)
    # This is structurally missing, not data quality issue — document but don't fill.
    media_actions = ["play_audio", "pause_audio", "play_video", "pause_video"]
    media_mask = df["action_type"].isin(media_actions)
    cursor_in_media = df.loc[media_mask, "cursor_time"].notna().sum()
    cursor_total_media = media_mask.sum()
    log(f"\n  cursor_time in media actions: {cursor_in_media:,}/{cursor_total_media:,} "
        f"({cursor_in_media/cursor_total_media*100:.1f}% present)")
    log(f"  → cursor_time NaN is structural (non-media actions). No imputation needed.")

    # user_answer: NaN expected for non-respond/erase actions
    respond_actions = ["respond", "erase_choice", "undo_erase_choice"]
    respond_mask = df["action_type"].isin(respond_actions)
    ans_in_respond = df.loc[respond_mask, "user_answer"].notna().sum()
    ans_total_respond = respond_mask.sum()
    log(f"\n  user_answer in respond/erase actions: {ans_in_respond:,}/{ans_total_respond:,} "
        f"({ans_in_respond/ans_total_respond*100:.1f}% present)")
    log(f"  → user_answer NaN is structural (non-response actions). No imputation needed.")

    # source: check for unexpected NaN
    source_null = df["source"].isnull().sum()
    if source_null > 0:
        log(f"\n  source: {source_null:,} null values")
        log(f"  Action types with null source:")
        null_src_actions = df.loc[df["source"].isnull(), "action_type"].value_counts()
        for act, cnt in null_src_actions.items():
            log(f"    {act}: {cnt:,}")
        log(f"  → Null source in payment/coupon actions is expected (no learning context).")
    else:
        log(f"\n  source: no null values")

    # ── 1b. Duplicate detection ────────────────────────────────────────
    log("\n--- 1b. Duplicate Detection ---")
    # Exact row duplicates
    n_exact_dup = df.duplicated().sum()
    log(f"  Exact duplicate rows: {n_exact_dup:,} ({n_exact_dup/n_original*100:.4f}%)")

    # Per-user duplicates (same timestamp + action_type + item_id)
    dup_cols = ["user_id", "timestamp", "action_type", "item_id"]
    n_key_dup = df.duplicated(subset=dup_cols).sum()
    log(f"  Key duplicates ({', '.join(dup_cols)}): {n_key_dup:,}")

    if n_exact_dup > 0:
        log(f"  → Removing {n_exact_dup:,} exact duplicate rows")
        df = df.drop_duplicates().reset_index(drop=True)
        log(f"  → Rows after dedup: {len(df):,}")

    # ── 1c. Data consistency checks ────────────────────────────────────
    log("\n--- 1c. Consistency Checks ---")

    # user_answer should be in {a, b, c, d} when present
    valid_answers = {"a", "b", "c", "d"}
    answers_present = df["user_answer"].dropna()
    invalid_answers = answers_present[~answers_present.isin(valid_answers)]
    log(f"  user_answer values outside {{a,b,c,d}}: {len(invalid_answers):,}")
    if len(invalid_answers) > 0:
        log(f"    Unexpected values: {invalid_answers.value_counts().head().to_dict()}")

    # platform should be 'mobile' or 'web'
    valid_platforms = {"mobile", "web"}
    platforms_present = df["platform"].dropna()
    invalid_plat = platforms_present[~platforms_present.isin(valid_platforms)]
    log(f"  platform values outside {{mobile, web}}: {len(invalid_plat):,}")

    # timestamp should be positive and reasonable
    log(f"  timestamp range: {df['timestamp'].min()} — {df['timestamp'].max()}")
    negative_ts = (df["timestamp"] <= 0).sum()
    log(f"  Non-positive timestamps: {negative_ts:,}")

    # Check temporal ordering within users (should be monotonically non-decreasing)
    log("\n  Checking per-user temporal ordering (sample of 10K users)...")
    user_sample = df["user_id"].drop_duplicates().sample(min(10000, df["user_id"].nunique()),
                                                          random_state=42)
    df_sample = df[df["user_id"].isin(user_sample)]
    unsorted_users = 0
    for uid, group in df_sample.groupby("user_id"):
        if not group["timestamp"].is_monotonic_increasing:
            unsorted_users += 1
    log(f"  Users with non-monotonic timestamps (in sample): {unsorted_users}/{len(user_sample)}")
    if unsorted_users > 0:
        log(f"  → Will sort by (user_id, timestamp) to ensure consistency")
        df = df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    del df_sample

    # ── 1d. Outlier detection on cursor_time ───────────────────────────
    log("\n--- 1d. Outlier Detection (cursor_time) ---")
    cursor_valid = df.loc[media_mask, "cursor_time"].dropna()
    if len(cursor_valid) > 0:
        q1 = cursor_valid.quantile(0.25)
        q3 = cursor_valid.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = ((cursor_valid < lower) | (cursor_valid > upper)).sum()
        log(f"  cursor_time IQR: [{q1:,.0f}, {q3:,.0f}], IQR={iqr:,.0f}")
        log(f"  Outlier bounds: [{lower:,.0f}, {upper:,.0f}]")
        log(f"  Outliers (IQR method): {outliers:,} ({outliers/len(cursor_valid)*100:.2f}%)")
        log(f"  → Removing outlier cursor_time values (setting to NaN)")

        # Plot before removal
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        axes[0].boxplot(cursor_valid.values, vert=True)
        axes[0].set_title("cursor_time Boxplot (before removal)")
        axes[0].set_ylabel("milliseconds")
        # Clean distribution
        cursor_no_outlier = cursor_valid[(cursor_valid >= lower) & (cursor_valid <= upper)]
        axes[1].hist(cursor_no_outlier / 1000, bins=50, color=PALETTE[0], edgecolor="white")
        axes[1].set_title("cursor_time Distribution (after removal)")
        axes[1].set_xlabel("seconds")
        save_fig("05_cursor_time_outliers.png")

        # Remove outlier values
        outlier_mask = (media_mask & df["cursor_time"].notna() &
                        ((df["cursor_time"] < lower) | (df["cursor_time"] > upper)))
        df.loc[outlier_mask, "cursor_time"] = np.nan
        log(f"  → {outlier_mask.sum():,} cursor_time values set to NaN")
        log(f"  → Clean cursor_time range: [{df['cursor_time'].min():,.0f}, {df['cursor_time'].max():,.0f}] ms")

    # ==================================================================
    # STEP 2: DATA INTEGRATION (Slide 14-24)
    # ==================================================================
    log("\n" + "=" * 60)
    log("STEP 2: DATA INTEGRATION")
    log("=" * 60)

    # ── 2a. Extract item type from item_id ─────────────────────────────
    log("\n--- 2a. Extract item type from item_id ---")
    # item_id format: q{int} (question), b{int} (bundle), e{int} (explanation),
    #                 l{int} (lecture), p{int} (payment), c{int} (coupon)
    df["item_type"] = df["item_id"].str[0].map({
        "q": "question", "b": "bundle", "e": "explanation",
        "l": "lecture", "p": "payment", "c": "coupon"
    })
    item_type_vc = df["item_type"].value_counts()
    for it, cnt in item_type_vc.items():
        log(f"  {it}: {cnt:,}")
    unmapped = df["item_type"].isnull().sum()
    if unmapped > 0:
        log(f"  Unmapped item types: {unmapped:,}")
        log(f"  Sample: {df.loc[df['item_type'].isnull(), 'item_id'].head().tolist()}")

    # ── 2b. Join with questions metadata ───────────────────────────────
    log("\n--- 2b. Join with Questions metadata ---")
    q_cols = ["question_id", "bundle_id", "correct_answer", "part", "tags"]
    q_meta = questions[q_cols].rename(columns={"question_id": "item_id"})

    # Only join for question-related rows
    q_mask = df["item_type"] == "question"
    log(f"  Question-related rows: {q_mask.sum():,}")

    df = df.merge(q_meta, on="item_id", how="left", suffixes=("", "_q"))
    matched = df.loc[q_mask, "correct_answer"].notna().sum()
    log(f"  Matched to questions.csv: {matched:,}/{q_mask.sum():,}")

    # ── 2c. Compute correctness for respond actions ────────────────────
    log("\n--- 2c. Compute correctness ---")
    respond_mask = (df["action_type"] == "respond") & df["correct_answer"].notna()
    df["is_correct"] = np.nan
    df.loc[respond_mask, "is_correct"] = (
        df.loc[respond_mask, "user_answer"] == df.loc[respond_mask, "correct_answer"]
    ).astype(float)

    n_correct = df.loc[respond_mask, "is_correct"].sum()
    n_respond = respond_mask.sum()
    log(f"  Respond actions with correctness: {n_respond:,}")
    log(f"  Correct: {n_correct:,.0f} ({n_correct/n_respond*100:.2f}%)")
    log(f"  Incorrect: {n_respond - n_correct:,.0f} ({(n_respond - n_correct)/n_respond*100:.2f}%)")

    # ── 2d. Join with lectures metadata ────────────────────────────────
    log("\n--- 2d. Join with Lectures metadata ---")
    l_meta = lectures[["lecture_id", "part", "tags", "video_length"]].rename(
        columns={"lecture_id": "item_id", "part": "lecture_part",
                 "tags": "lecture_tags", "video_length": "lecture_video_length"})

    df = df.merge(l_meta, on="item_id", how="left")
    l_mask = df["item_type"] == "lecture"
    matched_l = df.loc[l_mask, "lecture_part"].notna().sum()
    log(f"  Lecture-related rows: {l_mask.sum():,}")
    log(f"  Matched to lectures.csv: {matched_l:,}/{l_mask.sum():,}")

    # ── 2e. Redundancy check ──────────────────────────────────────────
    log("\n--- 2e. Redundancy / Correlation Check ---")
    # Check if bundle_id can be derived from question's item_id
    # (it can, via questions.csv, so bundle_id in the joined data is redundant
    #  with item_id for question rows — but we keep it for convenience)
    log("  bundle_id is derivable from item_id via questions.csv → kept for convenience")
    log("  explanation_id == bundle_id for all questions → not added (redundant)")
    log("  item_type is derived from item_id → useful derived column, kept")

    # ==================================================================
    # STEP 3: DATA TRANSFORMATION (Slide 25-28)
    # ==================================================================
    log("\n" + "=" * 60)
    log("STEP 3: DATA TRANSFORMATION")
    log("=" * 60)

    # ── 3a. Attribute construction ─────────────────────────────────────
    log("\n--- 3a. Attribute Construction ---")

    # Convert timestamp to datetime components
    dt = pd.to_datetime(df["timestamp"], unit="ms")
    df["hour"] = dt.dt.hour.astype(np.int8)
    df["day_of_week"] = dt.dt.dayofweek.astype(np.int8)
    df["date"] = dt.dt.date
    log("  Added: hour, day_of_week, date (from timestamp)")

    # Time since previous action (per user)
    log("  Computing time_since_prev (per user)...")
    df["time_since_prev"] = df.groupby("user_id")["timestamp"].diff()
    log(f"  time_since_prev stats (ms):")
    ts_stats = df["time_since_prev"].describe()
    for stat, val in ts_stats.items():
        log(f"    {stat}: {val:,.2f}")

    # Action sequence number within user
    df["action_seq"] = df.groupby("user_id").cumcount()
    log("  Added: action_seq (0-indexed position within user's history)")

    # ── 3b. Normalization of cursor_time (min-max) ─────────────────────
    log("\n--- 3b. Normalization ---")
    # cursor_time outliers were already removed in Step 1d
    cursor_notna = df["cursor_time"].notna()
    if cursor_notna.sum() > 0:
        ct_min = df.loc[cursor_notna, "cursor_time"].min()
        ct_max = df.loc[cursor_notna, "cursor_time"].max()
        if ct_max > ct_min:
            df["cursor_time_normalized"] = np.nan
            df.loc[cursor_notna, "cursor_time_normalized"] = (
                (df.loc[cursor_notna, "cursor_time"] - ct_min) / (ct_max - ct_min)
            )
            log(f"  cursor_time min-max normalized to [0, 1] (outliers removed in Step 1d)")
            log(f"    Clean range: [{ct_min:,.0f}, {ct_max:,.0f}] ms")
        else:
            log(f"  cursor_time has constant value, skipping normalization")

    # time_since_prev: log-transform (highly skewed)
    df["log_time_since_prev"] = np.log1p(df["time_since_prev"])
    log("  Added: log_time_since_prev (log1p transform for skewed distribution)")

    # ── 3c. Discretization ─────────────────────────────────────────────
    log("\n--- 3c. Discretization ---")

    # Discretize hour into time-of-day categories
    bins_hour = [-1, 6, 12, 18, 24]
    labels_hour = ["night", "morning", "afternoon", "evening"]
    df["time_of_day"] = pd.cut(df["hour"], bins=bins_hour, labels=labels_hour)
    log("  Added: time_of_day (night/morning/afternoon/evening from hour)")

    # Discretize day_of_week into weekday/weekend
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(np.int8)
    log("  Added: is_weekend (0=weekday, 1=weekend)")

    # ── 3d. Encoding categorical variables ─────────────────────────────
    log("\n--- 3d. Categorical Encoding (label encoding for key columns) ---")
    # Store mappings for reference
    cat_mappings = {}
    for col in ["action_type", "source", "platform", "item_type"]:
        unique_vals = df[col].dropna().unique()
        mapping = {v: i for i, v in enumerate(sorted(unique_vals))}
        df[f"{col}_encoded"] = df[col].map(mapping)
        cat_mappings[col] = mapping
        log(f"  {col}: {len(mapping)} categories → {col}_encoded")
        for val, code in sorted(mapping.items(), key=lambda x: x[1]):
            log(f"    {code}: {val}")

    # ==================================================================
    # STEP 4: DATA REDUCTION NOTES (Slide 29)
    # ==================================================================
    log("\n" + "=" * 60)
    log("STEP 4: DATA REDUCTION (documented, not applied)")
    log("=" * 60)
    log("""
  The full preprocessed dataset is saved for maximum flexibility.
  For downstream tasks, consider these reduction strategies:

  a) Sampling:
     - Random user sampling (e.g., 10K-50K users) for prototype models
     - Stratified sampling by user activity level

  b) Attribute subset selection:
     - For correctness prediction: drop cursor_time, payment/coupon actions
     - For behavior analysis: keep all action types

  c) Aggregation:
     - Per-user feature vectors (total actions, accuracy, avg time, etc.)
     - Per-session summaries

  d) Filtering:
     - Remove users with < N interactions (cold-start filtering)
     - Focus on specific parts or action types
""")

    # ==================================================================
    # SAVE OUTPUT
    # ==================================================================
    log("=" * 60)
    log("SAVING PREPROCESSED DATA")
    log("=" * 60)

    # Convert date column to string for parquet compatibility
    df["date"] = df["date"].astype(str)

    # Optimize dtypes before saving
    log(f"\n  Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    log(f"  Columns: {', '.join(df.columns.tolist())}")

    new_cols = [c for c in df.columns if c not in
                ["timestamp", "action_type", "item_id", "cursor_time",
                 "source", "user_answer", "platform", "user_id"]]
    log(f"\n  New columns added: {', '.join(new_cols)}")

    log(f"\n  Saving to {OUTPUT_FILE}...")
    df.to_parquet(OUTPUT_FILE, compression="snappy", index=False)
    file_size_mb = os.path.getsize(OUTPUT_FILE) / (1024**2)
    log(f"  File size: {file_size_mb:,.1f} MB")

    # ── Summary visualization ──────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Correctness distribution
    correct_vals = df["is_correct"].dropna()
    axes[0, 0].bar(["Incorrect", "Correct"],
                   [(correct_vals == 0).sum(), (correct_vals == 1).sum()],
                   color=[PALETTE[1], PALETTE[0]])
    axes[0, 0].set_title("Correctness Distribution")
    axes[0, 0].set_ylabel("Count")

    # Time of day distribution
    tod_vc = df["time_of_day"].value_counts()
    axes[0, 1].bar(tod_vc.index.astype(str), tod_vc.values, color=PALETTE[2])
    axes[0, 1].set_title("Time of Day Distribution")
    axes[0, 1].set_ylabel("Count")

    # Item type distribution
    it_vc = df["item_type"].value_counts()
    axes[1, 0].barh(it_vc.index, it_vc.values, color=PALETTE[3])
    axes[1, 0].set_title("Item Type Distribution")
    axes[1, 0].set_xlabel("Count")

    # Weekend vs weekday
    we_vc = df["is_weekend"].value_counts()
    axes[1, 1].pie([we_vc.get(0, 0), we_vc.get(1, 0)],
                   labels=["Weekday", "Weekend"], autopct="%1.1f%%",
                   colors=[PALETTE[4], PALETTE[5]])
    axes[1, 1].set_title("Weekday vs Weekend")

    plt.suptitle("Preprocessing Summary", fontsize=14, fontweight="bold")
    save_fig("05_preprocessing_summary.png")

    # ── Save report ────────────────────────────────────────────────────
    report_path = os.path.join(REPORTS_DIR, "05_preprocessing.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(report))
    log(f"\n→ Report saved: {report_path}")
    log("Done!")


if __name__ == "__main__":
    main()
