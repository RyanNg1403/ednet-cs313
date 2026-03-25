"""
03_eda_distributions.py
========================
Distribution analysis for all KT4 columns.
Produces visualizations for action types, sources, platforms,
user activity, and cursor_time.

Requires: processed/kt4_interactions.parquet
Output:   output/plots/02_*.png
          output/reports/02_distributions.txt
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARQUET_FILE = os.path.join(BASE_DIR, "processed", "kt4_interactions.parquet")
PLOTS_DIR = os.path.join(BASE_DIR, "output", "plots")
REPORTS_DIR = os.path.join(BASE_DIR, "output", "reports")
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

    if not os.path.exists(PARQUET_FILE):
        print(f"ERROR: {PARQUET_FILE} not found.")
        sys.exit(1)

    log("Loading data...")
    df = pd.read_parquet(PARQUET_FILE)
    log(f"Loaded {len(df):,} rows\n")

    # ── 1. Action Type Distribution ────────────────────────────────────
    log("=" * 50)
    log("1. ACTION TYPE DISTRIBUTION")
    log("=" * 50)
    action_vc = df["action_type"].value_counts()
    for act, cnt in action_vc.items():
        log(f"  {act:25s}  {cnt:>12,}  ({cnt/len(df)*100:5.2f}%)")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    # Bar chart
    action_vc.plot.barh(ax=axes[0], color=PALETTE[:len(action_vc)])
    axes[0].set_xlabel("Count")
    axes[0].set_title("Action Type — Count")
    axes[0].xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    # Pie chart
    action_vc.plot.pie(ax=axes[1], autopct="%1.1f%%", colors=PALETTE[:len(action_vc)],
                       startangle=90)
    axes[1].set_ylabel("")
    axes[1].set_title("Action Type — Proportion")
    save_fig("02_action_type_distribution.png")

    # ── 2. Source Distribution ─────────────────────────────────────────
    log("\n" + "=" * 50)
    log("2. SOURCE DISTRIBUTION")
    log("=" * 50)
    source_vc = df["source"].value_counts(dropna=False)
    for src, cnt in source_vc.items():
        label = src if pd.notna(src) else "<empty/NaN>"
        log(f"  {str(label):35s}  {cnt:>12,}  ({cnt/len(df)*100:5.2f}%)")

    # Filter out NaN/empty for plotting
    source_plot = df["source"].dropna().value_counts()
    fig, ax = plt.subplots(figsize=(12, 6))
    source_plot.plot.barh(ax=ax, color=PALETTE[1])
    ax.set_xlabel("Count")
    ax.set_title("Learning Source Distribution")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    save_fig("02_source_distribution.png")

    # ── 3. Platform Distribution ───────────────────────────────────────
    log("\n" + "=" * 50)
    log("3. PLATFORM DISTRIBUTION")
    log("=" * 50)
    plat_vc = df["platform"].value_counts(dropna=False)
    for p, cnt in plat_vc.items():
        label = p if pd.notna(p) else "<empty/NaN>"
        log(f"  {str(label):20s}  {cnt:>12,}  ({cnt/len(df)*100:5.2f}%)")

    fig, ax = plt.subplots(figsize=(7, 7))
    plat_clean = df["platform"].dropna().value_counts()
    plat_clean.plot.pie(ax=ax, autopct="%1.1f%%", colors=["#66b3ff", "#ff9999"],
                        startangle=90, textprops={"fontsize": 13})
    ax.set_ylabel("")
    ax.set_title("Platform Distribution (Mobile vs Web)")
    save_fig("02_platform_distribution.png")

    # ── 4. User Answer Distribution ────────────────────────────────────
    log("\n" + "=" * 50)
    log("4. USER ANSWER DISTRIBUTION")
    log("=" * 50)
    answer_vc = df["user_answer"].value_counts(dropna=False)
    for ans, cnt in answer_vc.items():
        label = ans if pd.notna(ans) else "<empty/NaN>"
        log(f"  {str(label):20s}  {cnt:>12,}  ({cnt/len(df)*100:5.2f}%)")

    # Only plot non-null answers
    ans_clean = df["user_answer"].dropna().value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(8, 5))
    ans_clean.plot.bar(ax=ax, color=PALETTE[2])
    ax.set_xlabel("Answer Choice")
    ax.set_ylabel("Count")
    ax.set_title("User Answer Distribution (respond + erase_choice actions)")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    plt.xticks(rotation=0)
    save_fig("02_user_answer_distribution.png")

    # ── 5. User Activity Distribution ──────────────────────────────────
    log("\n" + "=" * 50)
    log("5. USER ACTIVITY DISTRIBUTION (interactions per user)")
    log("=" * 50)
    user_counts = df.groupby("user_id").size()
    log(f"  Users: {len(user_counts):,}")
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        val = user_counts.quantile(p / 100)
        log(f"  P{p:02d}: {val:,.0f} interactions")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    # Histogram (log scale x)
    axes[0].hist(user_counts.values, bins=100, color=PALETTE[3], edgecolor="white", alpha=0.8)
    axes[0].set_xlabel("Interactions per User")
    axes[0].set_ylabel("Number of Users")
    axes[0].set_title("User Activity Distribution")
    axes[0].set_yscale("log")

    # Histogram (zoomed to P99)
    p99 = user_counts.quantile(0.99)
    axes[1].hist(user_counts[user_counts <= p99].values, bins=80,
                 color=PALETTE[4], edgecolor="white", alpha=0.8)
    axes[1].set_xlabel("Interactions per User")
    axes[1].set_ylabel("Number of Users")
    axes[1].set_title(f"User Activity Distribution (≤ P99 = {p99:,.0f})")
    axes[1].axvline(user_counts.median(), color="red", linestyle="--",
                    label=f"Median = {user_counts.median():,.0f}")
    axes[1].axvline(user_counts.mean(), color="blue", linestyle="--",
                    label=f"Mean = {user_counts.mean():,.0f}")
    axes[1].legend()
    save_fig("02_user_activity_distribution.png")

    # ── 6. Cursor Time Distribution ────────────────────────────────────
    log("\n" + "=" * 50)
    log("6. CURSOR TIME DISTRIBUTION (media actions only)")
    log("=" * 50)
    cursor_valid = df["cursor_time"].dropna()
    log(f"  Non-null cursor_time values: {len(cursor_valid):,} "
        f"({len(cursor_valid)/len(df)*100:.2f}% of all rows)")
    if len(cursor_valid) > 0:
        log(f"  Min:    {cursor_valid.min():,.0f} ms")
        log(f"  Max:    {cursor_valid.max():,.0f} ms")
        log(f"  Mean:   {cursor_valid.mean():,.0f} ms")
        log(f"  Median: {cursor_valid.median():,.0f} ms")

        fig, ax = plt.subplots(figsize=(10, 5))
        # Cap at P99 for visibility
        p99_cursor = cursor_valid.quantile(0.99)
        cursor_clipped = cursor_valid[cursor_valid <= p99_cursor]
        ax.hist(cursor_clipped / 1000, bins=80, color=PALETTE[5], edgecolor="white", alpha=0.8)
        ax.set_xlabel("Cursor Time (seconds)")
        ax.set_ylabel("Count")
        ax.set_title(f"Cursor Time Distribution (≤ P99 = {p99_cursor/1000:.0f}s)")
        save_fig("02_cursor_time_distribution.png")

    # ── 7. Action Type × Source Cross-tabulation ───────────────────────
    log("\n" + "=" * 50)
    log("7. ACTION TYPE × SOURCE CROSS-TAB (top combos)")
    log("=" * 50)
    cross = df.groupby(["action_type", "source"]).size().reset_index(name="count")
    cross = cross.sort_values("count", ascending=False)
    log(f"\n  Top 20 (action_type, source) combinations:")
    for _, row in cross.head(20).iterrows():
        log(f"    ({row['action_type']:20s}, {str(row['source']):25s})  {row['count']:>10,}")

    # Heatmap
    pivot = df.groupby(["action_type", "source"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(14, 8))
    # Log-scale for better visibility
    sns.heatmap(np.log10(pivot + 1), annot=False, fmt=".1f", cmap="YlOrRd", ax=ax)
    ax.set_title("Action Type × Source (log10 count)")
    ax.set_xlabel("Source")
    ax.set_ylabel("Action Type")
    save_fig("02_action_source_heatmap.png")

    # ── 8. Action Type × Platform ──────────────────────────────────────
    log("\n" + "=" * 50)
    log("8. ACTION TYPE × PLATFORM")
    log("=" * 50)
    cross_plat = pd.crosstab(df["action_type"], df["platform"])
    log(cross_plat.to_string())

    fig, ax = plt.subplots(figsize=(12, 6))
    cross_plat.plot.barh(ax=ax, stacked=True, color=["#66b3ff", "#ff9999"])
    ax.set_xlabel("Count")
    ax.set_title("Action Type by Platform")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    ax.legend(title="Platform")
    save_fig("02_action_platform_stacked.png")

    # ── Save report ────────────────────────────────────────────────────
    report_path = os.path.join(REPORTS_DIR, "02_distributions.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    log(f"\n→ Report saved: {report_path}")


if __name__ == "__main__":
    main()
