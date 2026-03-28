"""
generate_features.py
====================
Generate features for answer correctness prediction from EdNet-KT4
preprocessed data.

Produces a feature table where each row is a single student response,
enriched with 10 engineered features across 4 groups:
  - Question properties (difficulty)
  - Student mastery (cumulative accuracy, listening/reading split)
  - Behavioral signals (answer changes, rapid guessing, adaptive ratio)
  - Engagement & fatigue (lecture watches, session fatigue)

All cumulative features use strict leakage prevention: only data from
interactions 1..t-1 are used to compute features at time t.

Requires: processed/kt4_preprocessed.parquet (from preprocessing/preprocess.py)
Output:   processed/kt4_features.parquet
          output/feature_engineering/plots/*.png
          output/feature_engineering/reports/feature_engineering.md
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREPROCESSED_FILE = os.path.join(BASE_DIR, "processed", "kt4_preprocessed.parquet")
OUTPUT_FILE = os.path.join(BASE_DIR, "processed", "kt4_features.parquet")
PLOTS_DIR = os.path.join(BASE_DIR, "output", "feature_engineering", "plots")
REPORTS_DIR = os.path.join(BASE_DIR, "output", "feature_engineering", "reports")
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.1)


def save_fig(name: str):
    path = os.path.join(PLOTS_DIR, name)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: output/feature_engineering/plots/{name}")


def main():
    report = []

    def log(msg: str = ""):
        print(msg)
        report.append(msg)

    log("=" * 60)
    log("FEATURE GENERATION — EdNet KT4")
    log("=" * 60)

    # ── Load preprocessed data ─────────────────────────────────────────
    log("\n[0] Loading preprocessed data...")
    df = pd.read_parquet(
        PREPROCESSED_FILE,
        columns=["user_id", "timestamp", "action_type", "item_id", "item_type",
                 "source", "is_correct", "part", "time_since_prev"],
    )
    log(f"  Loaded {len(df):,} rows")

    # ── Filter to respond actions with correctness ─────────────────────
    responds = df[
        (df["action_type"] == "respond") & df["is_correct"].notna()
    ].copy()
    responds = responds.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    log(f"  Respond actions with correctness: {len(responds):,}")
    log(f"  Unique users: {responds['user_id'].nunique():,}")
    log(f"  Unique questions: {responds['item_id'].nunique():,}")

    # ── Target variable ────────────────────────────────────────────────
    responds["target_is_correct"] = responds["is_correct"].astype(np.int8)

    # ==================================================================
    # QUESTION PROPERTIES
    # ==================================================================
    log("\n" + "=" * 50)
    log("QUESTION PROPERTIES")
    log("=" * 50)

    # feat_question_difficulty: historical accuracy-based difficulty
    # This is a question property (not student-specific), no leakage concern
    q_accuracy = responds.groupby("item_id")["is_correct"].mean()
    q_difficulty = (1 - q_accuracy).rename("feat_question_difficulty")
    responds = responds.merge(q_difficulty, left_on="item_id", right_index=True, how="left")
    responds["feat_question_difficulty"] = responds["feat_question_difficulty"].astype(np.float32)
    log(f"  feat_question_difficulty: mean={responds['feat_question_difficulty'].mean():.4f}, "
        f"range=[{responds['feat_question_difficulty'].min():.3f}, "
        f"{responds['feat_question_difficulty'].max():.3f}]")

    # ==================================================================
    # STUDENT MASTERY (cumulative, leakage-safe)
    # ==================================================================
    log("\n" + "=" * 50)
    log("STUDENT MASTERY")
    log("=" * 50)

    # feat_total_attempts: cumulative respond count up to t-1
    responds["feat_total_attempts"] = responds.groupby("user_id").cumcount().astype(np.int32)
    log(f"  feat_total_attempts: range=[{responds['feat_total_attempts'].min()}, "
        f"{responds['feat_total_attempts'].max():,}]")

    # feat_overall_accuracy: cumulative correct / total up to t-1
    cum_correct = responds.groupby("user_id")["is_correct"].transform(
        lambda x: x.cumsum().shift(1, fill_value=0)
    )
    responds["feat_overall_accuracy"] = np.where(
        responds["feat_total_attempts"] > 0,
        cum_correct / responds["feat_total_attempts"],
        0.0,
    ).astype(np.float32)
    log(f"  feat_overall_accuracy: mean={responds['feat_overall_accuracy'].mean():.4f}")

    # feat_listening_accuracy: cumulative accuracy on Parts 1-4
    # feat_reading_accuracy: cumulative accuracy on Parts 5-7
    responds["is_listening"] = responds["part"].isin([1, 2, 3, 4]).astype(np.int8)
    responds["is_reading"] = responds["part"].isin([5, 6, 7]).astype(np.int8)
    responds["listening_correct"] = (responds["is_listening"] * responds["is_correct"]).astype(np.float32)
    responds["reading_correct"] = (responds["is_reading"] * responds["is_correct"]).astype(np.float32)

    for prefix in ["listening", "reading"]:
        cum_count = responds.groupby("user_id")[f"is_{prefix}"].transform(
            lambda x: x.cumsum().shift(1, fill_value=0)
        )
        cum_corr = responds.groupby("user_id")[f"{prefix}_correct"].transform(
            lambda x: x.cumsum().shift(1, fill_value=0)
        )
        responds[f"feat_{prefix}_accuracy"] = np.where(
            cum_count > 0, cum_corr / cum_count, 0.0
        ).astype(np.float32)
        log(f"  feat_{prefix}_accuracy: mean={responds[f'feat_{prefix}_accuracy'].mean():.4f}")

    # Drop helper columns
    responds = responds.drop(columns=["is_listening", "is_reading",
                                       "listening_correct", "reading_correct"])

    # ==================================================================
    # BEHAVIORAL SIGNALS
    # ==================================================================
    log("\n" + "=" * 50)
    log("BEHAVIORAL SIGNALS")
    log("=" * 50)

    # feat_answer_changes: cumulative count of prior respond actions on the same
    # question by the same user (temporal ordering, no future leakage)
    responds = responds.sort_values(["user_id", "item_id", "timestamp"])
    responds["feat_answer_changes"] = responds.groupby(
        ["user_id", "item_id"]
    ).cumcount().astype(np.int16)
    responds = responds.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    log(f"  feat_answer_changes: {(responds['feat_answer_changes'] > 0).mean()*100:.1f}% "
        f"of responses have >= 1 prior attempt")

    # feat_is_rapid_guess: response faster than P10 of time_since_prev
    p10_threshold = responds["time_since_prev"].dropna().quantile(0.10)
    responds["feat_is_rapid_guess"] = (responds["time_since_prev"] < p10_threshold).astype(np.int8)
    responds.loc[responds["time_since_prev"].isna(), "feat_is_rapid_guess"] = 0
    log(f"  feat_is_rapid_guess: threshold={p10_threshold:,.0f}ms (P10), "
        f"flags {responds['feat_is_rapid_guess'].mean()*100:.1f}%")

    # feat_adaptive_ratio: proportion of attempts from adaptive_offer up to t-1
    responds["is_adaptive"] = (responds["source"] == "adaptive_offer").astype(np.int8)
    cum_adaptive = responds.groupby("user_id")["is_adaptive"].transform(
        lambda x: x.cumsum().shift(1, fill_value=0)
    )
    responds["feat_adaptive_ratio"] = np.where(
        responds["feat_total_attempts"] > 0,
        cum_adaptive / responds["feat_total_attempts"],
        0.0,
    ).astype(np.float32)
    responds = responds.drop(columns=["is_adaptive"])
    log(f"  feat_adaptive_ratio: mean={responds['feat_adaptive_ratio'].mean():.4f}")

    # ==================================================================
    # ENGAGEMENT & FATIGUE
    # ==================================================================
    log("\n" + "=" * 50)
    log("ENGAGEMENT & FATIGUE")
    log("=" * 50)

    # feat_lecture_watches: cumulative count of lectures consumed before each respond
    # Uses binary search on sorted per-user lecture timestamps (no future leakage)
    lecture_actions = df[(df["action_type"] == "enter") & (df["item_type"] == "lecture")]
    lecture_ts = lecture_actions[["user_id", "timestamp"]].sort_values(["user_id", "timestamp"])
    user_lec_ts = lecture_ts.groupby("user_id")["timestamp"].apply(np.array).to_dict()

    respond_keys = responds[["user_id", "timestamp"]].values
    lec_counts = np.zeros(len(responds), dtype=np.uint32)
    for i in range(len(responds)):
        uid = respond_keys[i, 0]
        ts = respond_keys[i, 1]
        lec_times = user_lec_ts.get(uid)
        if lec_times is not None:
            lec_counts[i] = np.searchsorted(lec_times, ts, side="left")
        if (i + 1) % 5_000_000 == 0:
            log(f"    {i + 1:,}/{len(responds):,}...")

    responds["feat_lecture_watches"] = lec_counts
    del lecture_ts, user_lec_ts, lec_counts
    log(f"  feat_lecture_watches: mean={responds['feat_lecture_watches'].mean():.1f}, "
        f"max={responds['feat_lecture_watches'].max():,}")

    # feat_log_session_fatigue: log of action count within last 60 minutes
    # Count ALL actions (not just responds) in the 1-hour window before each respond
    # For memory efficiency, compute from preprocessed data per user
    log("  Computing session fatigue (1-hour window)...")
    HOUR_MS = 3_600_000

    # Build a timestamp index of all actions per user
    all_actions = df[["user_id", "timestamp"]].copy()
    all_actions = all_actions.sort_values(["user_id", "timestamp"]).reset_index(drop=True)

    # For each respond, count actions in [timestamp - 1hr, timestamp)
    # Use merge_asof approach: for each respond timestamp, find how many actions fall in window
    # More efficient: per-user rolling count
    fatigue_values = []
    respond_keys = responds[["user_id", "timestamp"]].values

    # Group all actions by user for fast lookup
    user_action_ts = all_actions.groupby("user_id")["timestamp"].apply(np.array).to_dict()

    batch_size = 50_000
    n_batches = (len(responds) + batch_size - 1) // batch_size
    for batch_idx in range(n_batches):
        lo = batch_idx * batch_size
        hi = min(lo + batch_size, len(responds))
        batch_fatigue = []
        for i in range(lo, hi):
            uid = respond_keys[i, 0]
            ts = respond_keys[i, 1]
            actions_ts = user_action_ts.get(uid, np.array([]))
            count = np.sum((actions_ts >= ts - HOUR_MS) & (actions_ts < ts))
            batch_fatigue.append(count)
        fatigue_values.extend(batch_fatigue)
        if (batch_idx + 1) % 100 == 0:
            print(f"    Batch {batch_idx + 1}/{n_batches}...")

    responds["feat_session_fatigue_raw"] = np.array(fatigue_values, dtype=np.uint32)
    responds["feat_log_session_fatigue"] = np.log1p(
        responds["feat_session_fatigue_raw"].astype(float)
    ).astype(np.float32)
    responds = responds.drop(columns=["feat_session_fatigue_raw"])
    log(f"  feat_log_session_fatigue: mean={responds['feat_log_session_fatigue'].mean():.2f}, "
        f"max={responds['feat_log_session_fatigue'].max():.2f}")

    del df, all_actions, user_action_ts

    # ==================================================================
    # FINALIZE & SAVE
    # ==================================================================
    log("\n" + "=" * 50)
    log("SAVING OUTPUT")
    log("=" * 50)

    # Zero out first-row features for each user (no prior history)
    first_idx = responds.groupby("user_id").head(1).index
    historical_features = ["feat_overall_accuracy", "feat_listening_accuracy",
                           "feat_reading_accuracy", "feat_adaptive_ratio",
                           "feat_total_attempts"]
    for col in historical_features:
        responds.loc[first_idx, col] = 0
    responds.loc[first_idx, "feat_is_rapid_guess"] = 0

    # Select and order final columns
    col_order = [
        "user_id", "timestamp", "item_id", "part",
        "target_is_correct",
        "feat_total_attempts",
        "feat_overall_accuracy",
        "feat_listening_accuracy",
        "feat_reading_accuracy",
        "feat_question_difficulty",
        "feat_answer_changes",
        "feat_adaptive_ratio",
        "feat_lecture_watches",
        "feat_log_session_fatigue",
        "feat_is_rapid_guess",
    ]
    out = responds[col_order].copy()
    log(f"  Shape: {out.shape[0]:,} rows × {out.shape[1]} columns")
    log(f"  Nulls: {out.isnull().sum().sum()}")

    out.to_parquet(OUTPUT_FILE, compression="snappy", index=False)
    size_mb = os.path.getsize(OUTPUT_FILE) / (1024**2)
    log(f"  Saved: {OUTPUT_FILE} ({size_mb:,.1f} MB)")

    # ==================================================================
    # VALIDATION & PLOTS
    # ==================================================================
    log("\n" + "=" * 50)
    log("VALIDATION")
    log("=" * 50)

    # Correlation with target
    log("\n  Feature correlations with target_is_correct:")
    feat_cols = [c for c in out.columns if c.startswith("feat_")]
    for col in sorted(feat_cols, key=lambda c: abs(out[c].corr(out["target_is_correct"])),
                      reverse=True):
        corr = out[col].corr(out["target_is_correct"])
        log(f"    {col:35s}  {corr:+.4f}")

    # Leakage check
    first_acc = out.groupby("user_id")["feat_overall_accuracy"].first()
    log(f"\n  Leakage check: users with first accuracy != 0: {(first_acc != 0).sum()}")

    # Monotonicity check
    sample_users = out["user_id"].drop_duplicates().sample(
        min(1000, out["user_id"].nunique()), random_state=42)
    non_mono = 0
    for uid in sample_users:
        attempts = out.loc[out["user_id"] == uid, "feat_total_attempts"].values
        if not np.all(np.diff(attempts) >= 0):
            non_mono += 1
    log(f"  Monotonicity check (1K users): {non_mono} violations")

    # Rapid guess stats
    rapid_acc = out.loc[out["feat_is_rapid_guess"] == 1, "target_is_correct"].mean()
    normal_acc = out.loc[out["feat_is_rapid_guess"] == 0, "target_is_correct"].mean()
    log(f"  Rapid guess rate: {out['feat_is_rapid_guess'].mean()*100:.1f}%")
    log(f"  Rapid guess accuracy: {rapid_acc:.4f} vs normal: {normal_acc:.4f}")

    # ── Correlation matrix plot ────────────────────────────────────────
    all_feat = [c for c in out.columns if c.startswith("feat_") or c == "target_is_correct"]
    corr_matrix = out[all_feat].corr()

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                ax=ax, vmin=-1, vmax=1, square=True)
    ax.set_title("Feature Correlation Matrix")
    save_fig("correlation_matrix.png")

    # ── Distribution plots ─────────────────────────────────────────────
    plot_feats = ["feat_question_difficulty", "feat_overall_accuracy",
                  "feat_listening_accuracy", "feat_reading_accuracy",
                  "feat_answer_changes", "feat_log_session_fatigue"]
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    for ax, col in zip(axes.flat, plot_feats):
        for val, color, label in [(1, "green", "Correct"), (0, "orange", "Incorrect")]:
            subset = out.loc[out["target_is_correct"] == val, col]
            if col == "feat_answer_changes":
                subset = subset.clip(upper=10)
            ax.hist(subset, bins=50, alpha=0.5, color=color, label=label, density=True)
        ax.set_title(col.replace("feat_", ""), fontsize=11)
        ax.legend(fontsize=9)
    plt.suptitle("Feature Distributions by Correctness", fontsize=14)
    save_fig("feature_distributions.png")

    # ── Save report ────────────────────────────────────────────────────
    report_path = os.path.join(REPORTS_DIR, "feature_engineering.md")
    with open(report_path, "w") as f:
        f.write("# Feature Engineering Report\n\n")
        f.write("```\n")
        f.write("\n".join(report))
        f.write("\n```\n")
    log(f"\n→ Report saved: {report_path}")
    log("Done!")


if __name__ == "__main__":
    main()
