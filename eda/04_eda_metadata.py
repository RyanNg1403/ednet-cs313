"""
04_eda_metadata.py
==================
Analysis of content metadata: questions, lectures, payments, coupons.
Focuses on question difficulty estimation, part/tag distributions,
and content coverage.

Requires: processed/kt4_interactions.parquet, contents/*.csv
Output:   output/plots/03_*.png
          output/reports/03_metadata.txt
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import numpy as np
from collections import Counter

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARQUET_FILE = os.path.join(BASE_DIR, "processed", "kt4_interactions.parquet")
CONTENTS_DIR = os.path.join(BASE_DIR, "contents")
PLOTS_DIR = os.path.join(BASE_DIR, "output", "eda", "plots")
REPORTS_DIR = os.path.join(BASE_DIR, "output", "eda", "reports")
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
    report_lines = []

    def log(msg: str = ""):
        print(msg)
        report_lines.append(msg)

    # ── Load content metadata ──────────────────────────────────────────
    questions = pd.read_csv(os.path.join(CONTENTS_DIR, "questions.csv"))
    lectures = pd.read_csv(os.path.join(CONTENTS_DIR, "lectures.csv"))
    payments = pd.read_csv(os.path.join(CONTENTS_DIR, "payments.csv"))
    coupons = pd.read_csv(os.path.join(CONTENTS_DIR, "coupons.csv"))

    # ================================================================
    # QUESTIONS ANALYSIS
    # ================================================================
    log("=" * 60)
    log("QUESTIONS METADATA ANALYSIS")
    log("=" * 60)
    log(f"\nTotal questions: {len(questions):,}")
    log(f"Total bundles:  {questions['bundle_id'].nunique():,}")

    # ── 1. Questions per Part ──────────────────────────────────────────
    log("\n--- Questions per Part (TOEIC sections) ---")
    part_counts = questions["part"].value_counts().sort_index()
    toeic_parts = {
        1: "Part 1: Photo Descriptions",
        2: "Part 2: Question-Response",
        3: "Part 3: Short Conversations",
        4: "Part 4: Short Talks",
        5: "Part 5: Incomplete Sentences",
        6: "Part 6: Text Completion",
        7: "Part 7: Reading Comprehension",
    }
    for part, cnt in part_counts.items():
        name = toeic_parts.get(part, f"Part {part}")
        log(f"  Part {part} ({name}):  {cnt:>6,} questions  ({cnt/len(questions)*100:5.1f}%)")

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(part_counts.index.astype(str), part_counts.values, color=PALETTE[:7])
    ax.set_xlabel("TOEIC Part")
    ax.set_ylabel("Number of Questions")
    ax.set_title("Questions Distribution by TOEIC Part")
    for bar, cnt in zip(bars, part_counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 30,
                f"{cnt:,}", ha="center", va="bottom", fontsize=10)
    save_fig("03_questions_per_part.png")

    # ── 2. Questions per Bundle ────────────────────────────────────────
    log("\n--- Questions per Bundle ---")
    bundle_sizes = questions.groupby("bundle_id").size()
    bsize_vc = bundle_sizes.value_counts().sort_index()
    for size, cnt in bsize_vc.items():
        log(f"  {size} question(s) per bundle: {cnt:,} bundles")

    fig, ax = plt.subplots(figsize=(8, 5))
    bsize_vc.plot.bar(ax=ax, color=PALETTE[1])
    ax.set_xlabel("Questions per Bundle")
    ax.set_ylabel("Number of Bundles")
    ax.set_title("Bundle Size Distribution")
    plt.xticks(rotation=0)
    save_fig("03_bundle_size_distribution.png")

    # ── 3. Correct Answer Distribution ─────────────────────────────────
    log("\n--- Correct Answer Distribution ---")
    ans_vc = questions["correct_answer"].value_counts().sort_index()
    for ans, cnt in ans_vc.items():
        log(f"  {ans}: {cnt:,}  ({cnt/len(questions)*100:.1f}%)")

    fig, ax = plt.subplots(figsize=(7, 5))
    ans_vc.plot.bar(ax=ax, color=PALETTE[2])
    ax.set_xlabel("Correct Answer")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of Correct Answers")
    plt.xticks(rotation=0)
    save_fig("03_correct_answer_distribution.png")

    # ── 4. Tag Frequency Analysis ──────────────────────────────────────
    log("\n--- Tag Frequency Analysis ---")
    all_tags = []
    for tags_str in questions["tags"].dropna():
        all_tags.extend([int(t) for t in str(tags_str).split(";")])
    tag_counter = Counter(all_tags)
    log(f"  Total unique tags: {len(tag_counter)}")
    log(f"  Top 20 most common tags:")
    for tag, cnt in tag_counter.most_common(20):
        log(f"    Tag {tag:>4d}: {cnt:>6,} questions")

    # Plot top 30 tags
    top_tags = tag_counter.most_common(30)
    fig, ax = plt.subplots(figsize=(14, 6))
    tags_labels = [str(t[0]) for t in top_tags]
    tags_counts = [t[1] for t in top_tags]
    ax.bar(tags_labels, tags_counts, color=PALETTE[3])
    ax.set_xlabel("Tag ID")
    ax.set_ylabel("Number of Questions")
    ax.set_title("Top 30 Most Common Question Tags (Skills)")
    plt.xticks(rotation=45, ha="right")
    save_fig("03_top_tags.png")

    # Tags per question distribution
    tags_per_q = questions["tags"].dropna().apply(lambda x: len(str(x).split(";")))
    log(f"\n  Tags per question:")
    log(f"    Mean:   {tags_per_q.mean():.2f}")
    log(f"    Median: {tags_per_q.median():.0f}")
    log(f"    Min:    {tags_per_q.min()}")
    log(f"    Max:    {tags_per_q.max()}")

    fig, ax = plt.subplots(figsize=(8, 5))
    tags_per_q.value_counts().sort_index().plot.bar(ax=ax, color=PALETTE[4])
    ax.set_xlabel("Number of Tags per Question")
    ax.set_ylabel("Number of Questions")
    ax.set_title("Tags per Question Distribution")
    plt.xticks(rotation=0)
    save_fig("03_tags_per_question.png")

    # ── 5. Question Difficulty Estimation ──────────────────────────────
    log("\n--- Question Difficulty Estimation ---")
    log("  (Computing from KT4 interactions + correct answers...)")

    # Load only the columns we need from parquet
    df = pd.read_parquet(PARQUET_FILE, columns=["action_type", "item_id", "user_answer"])

    # Filter to 'respond' actions — last response before submit counts
    # For simplicity, we use ALL respond actions and compare to correct answers
    responds = df[df["action_type"] == "respond"].copy()
    del df  # free memory

    # Map question_id → correct_answer
    q_correct = questions.set_index("question_id")["correct_answer"].to_dict()
    q_part = questions.set_index("question_id")["part"].to_dict()

    # Only keep responses to known questions
    responds = responds[responds["item_id"].isin(q_correct)].copy()
    responds["correct_answer"] = responds["item_id"].map(q_correct)
    responds["is_correct"] = (responds["user_answer"] == responds["correct_answer"]).astype(int)

    overall_acc = responds["is_correct"].mean()
    log(f"\n  Overall accuracy (all respond actions): {overall_acc:.4f} ({overall_acc*100:.2f}%)")
    log(f"  Total responses matched to questions: {len(responds):,}")

    # Difficulty per question
    q_diff = responds.groupby("item_id").agg(
        total_attempts=("is_correct", "size"),
        correct_count=("is_correct", "sum"),
    )
    q_diff["accuracy"] = q_diff["correct_count"] / q_diff["total_attempts"]
    q_diff["difficulty"] = 1 - q_diff["accuracy"]  # higher = harder

    log(f"\n  Questions with at least 1 attempt: {len(q_diff):,}")
    log(f"  Difficulty (1 - accuracy) statistics:")
    for stat, val in q_diff["difficulty"].describe().items():
        log(f"    {stat:10s}  {val:.4f}")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    # Difficulty histogram
    axes[0].hist(q_diff["difficulty"], bins=50, color=PALETTE[5], edgecolor="white", alpha=0.8)
    axes[0].set_xlabel("Difficulty (1 - accuracy rate)")
    axes[0].set_ylabel("Number of Questions")
    axes[0].set_title("Question Difficulty Distribution")
    axes[0].axvline(q_diff["difficulty"].median(), color="red", linestyle="--",
                    label=f"Median = {q_diff['difficulty'].median():.3f}")
    axes[0].legend()

    # Difficulty by part
    q_diff["part"] = q_diff.index.map(q_part)
    part_diff = q_diff.groupby("part")["difficulty"].mean().sort_index()
    bars = axes[1].bar(part_diff.index.astype(str), part_diff.values, color=PALETTE[:7])
    axes[1].set_xlabel("TOEIC Part")
    axes[1].set_ylabel("Average Difficulty")
    axes[1].set_title("Average Question Difficulty by Part")
    for bar, val in zip(bars, part_diff.values):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                     f"{val:.3f}", ha="center", va="bottom", fontsize=10)
    save_fig("03_question_difficulty.png")

    # Difficulty vs number of attempts scatter
    fig, ax = plt.subplots(figsize=(10, 6))
    sample = q_diff.sample(min(5000, len(q_diff)), random_state=42)
    ax.scatter(sample["total_attempts"], sample["difficulty"], alpha=0.3, s=10, c=PALETTE[0])
    ax.set_xlabel("Total Attempts")
    ax.set_ylabel("Difficulty (1 - accuracy)")
    ax.set_title("Question Difficulty vs. Number of Attempts")
    ax.set_xscale("log")
    save_fig("03_difficulty_vs_attempts.png")

    del responds

    # ================================================================
    # LECTURES ANALYSIS
    # ================================================================
    log("\n" + "=" * 60)
    log("LECTURES METADATA ANALYSIS")
    log("=" * 60)
    log(f"\nTotal lectures: {len(lectures):,}")

    # Lectures per part
    log("\n--- Lectures per Part ---")
    lec_part = lectures["part"].value_counts().sort_index()
    for part, cnt in lec_part.items():
        log(f"  Part {part}: {cnt:,} lectures")

    fig, ax = plt.subplots(figsize=(10, 5))
    lec_part.plot.bar(ax=ax, color=PALETTE[6])
    ax.set_xlabel("Part (0 = no specific part)")
    ax.set_ylabel("Number of Lectures")
    ax.set_title("Lectures by Part")
    plt.xticks(rotation=0)
    save_fig("03_lectures_per_part.png")

    # Video length distribution
    valid_lengths = lectures[lectures["video_length"] > 0]["video_length"]
    log(f"\n--- Video Length Distribution ---")
    log(f"  Lectures with valid video_length: {len(valid_lengths):,} / {len(lectures):,}")
    if len(valid_lengths) > 0:
        log(f"  Min:    {valid_lengths.min()/1000:.0f}s ({valid_lengths.min()/60000:.1f}min)")
        log(f"  Max:    {valid_lengths.max()/1000:.0f}s ({valid_lengths.max()/60000:.1f}min)")
        log(f"  Mean:   {valid_lengths.mean()/1000:.0f}s ({valid_lengths.mean()/60000:.1f}min)")
        log(f"  Median: {valid_lengths.median()/1000:.0f}s ({valid_lengths.median()/60000:.1f}min)")

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(valid_lengths / 60000, bins=40, color=PALETTE[0], edgecolor="white", alpha=0.8)
        ax.set_xlabel("Video Length (minutes)")
        ax.set_ylabel("Number of Lectures")
        ax.set_title("Lecture Video Length Distribution")
        save_fig("03_lecture_video_length.png")

    # ================================================================
    # PAYMENTS & COUPONS
    # ================================================================
    log("\n" + "=" * 60)
    log("PAYMENTS & COUPONS SUMMARY")
    log("=" * 60)

    log(f"\nPayment items: {len(payments):,}")
    log(f"  Columns: {payments.columns.tolist()}")
    # Column is 'type' (not 'payment_type') and 'duaration' (typo in original data)
    type_col = "type" if "type" in payments.columns else "payment_type"
    dur_col = "duaration" if "duaration" in payments.columns else "duration"
    log(f"  Types: {payments[type_col].value_counts().to_dict()}")
    log(f"\nCoupons: {len(coupons):,}")
    log(f"  Types: {coupons['coupon_type'].value_counts().to_dict()}")

    # Duration distribution for passes
    passes = payments[payments[type_col] == "pass"]
    if len(passes) > 0:
        log(f"\n  Pass duration range (days):")
        durations = passes[dur_col] / (1000 * 60 * 60 * 24)
        log(f"    Min: {durations.min():.0f} days")
        log(f"    Max: {durations.max():.0f} days")
        log(f"    Mean: {durations.mean():.0f} days")

    # ── Save report ────────────────────────────────────────────────────
    report_path = os.path.join(REPORTS_DIR, "03_metadata.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    log(f"\n→ Report saved: {report_path}")


if __name__ == "__main__":
    main()
