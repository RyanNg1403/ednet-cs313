"""
05_eda_temporal.py
==================
Temporal pattern analysis of KT4 interactions.
Analyzes activity over time, day-of-week patterns, hourly patterns,
and session-level behavior.

Requires: processed/kt4_interactions.parquet
Output:   output/plots/04_*.png
          output/reports/04_temporal.txt
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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
    df = pd.read_parquet(PARQUET_FILE, columns=["timestamp", "action_type", "platform", "user_id"])
    log(f"Loaded {len(df):,} rows")

    # NOTE: EdNet timestamps are shifted from real values for security.
    # Relative patterns (day-of-week, hourly) are still meaningful,
    # but absolute dates should be interpreted with caution.
    log("\nConverting timestamps to datetime...")
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["date"] = df["datetime"].dt.date
    df["hour"] = df["datetime"].dt.hour
    df["day_of_week"] = df["datetime"].dt.dayofweek  # 0=Mon, 6=Sun
    df["month"] = df["datetime"].dt.to_period("M")

    log(f"\nTimestamp range:")
    log(f"  Earliest: {df['datetime'].min()}")
    log(f"  Latest:   {df['datetime'].max()}")
    log(f"  Span:     {(df['datetime'].max() - df['datetime'].min()).days} days")

    # ── 1. Daily activity over time ────────────────────────────────────
    log("\n" + "=" * 50)
    log("1. DAILY ACTIVITY OVER TIME")
    log("=" * 50)
    daily = df.groupby("date").size()
    log(f"  Total active days: {len(daily):,}")
    log(f"  Avg interactions/day: {daily.mean():,.0f}")
    log(f"  Max interactions/day: {daily.max():,} (on {daily.idxmax()})")
    log(f"  Min interactions/day: {daily.min():,} (on {daily.idxmin()})")

    fig, ax = plt.subplots(figsize=(16, 5))
    ax.plot(daily.index, daily.values, linewidth=0.5, alpha=0.7, color=PALETTE[0])
    # Add 7-day rolling average
    daily_series = pd.Series(daily.values, index=pd.to_datetime(daily.index))
    rolling = daily_series.rolling(7).mean()
    ax.plot(rolling.index, rolling.values, linewidth=2, color="red", label="7-day rolling avg")
    ax.set_xlabel("Date")
    ax.set_ylabel("Interactions")
    ax.set_title("Daily Interaction Volume Over Time")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1e3:.0f}K"))
    ax.legend()
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.xticks(rotation=45)
    save_fig("04_daily_activity.png")

    # ── 2. Monthly activity ────────────────────────────────────────────
    log("\n" + "=" * 50)
    log("2. MONTHLY ACTIVITY")
    log("=" * 50)
    monthly = df.groupby("month").size()
    for m, cnt in monthly.items():
        log(f"  {m}: {cnt:>10,}")

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(range(len(monthly)), monthly.values, color=PALETTE[1])
    ax.set_xticks(range(len(monthly)))
    ax.set_xticklabels([str(m) for m in monthly.index], rotation=45, ha="right")
    ax.set_xlabel("Month")
    ax.set_ylabel("Interactions")
    ax.set_title("Monthly Interaction Volume")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    save_fig("04_monthly_activity.png")

    # ── 3. Day-of-week patterns ────────────────────────────────────────
    log("\n" + "=" * 50)
    log("3. DAY-OF-WEEK PATTERNS")
    log("=" * 50)
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_counts = df["day_of_week"].value_counts().sort_index()
    for i, cnt in dow_counts.items():
        log(f"  {dow_names[i]}: {cnt:>12,}  ({cnt/len(df)*100:.2f}%)")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(dow_names, dow_counts.values, color=PALETTE[2])
    ax.set_xlabel("Day of Week")
    ax.set_ylabel("Total Interactions")
    ax.set_title("Activity by Day of Week")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    save_fig("04_day_of_week.png")

    # ── 4. Hourly patterns ─────────────────────────────────────────────
    log("\n" + "=" * 50)
    log("4. HOURLY PATTERNS")
    log("=" * 50)
    hour_counts = df["hour"].value_counts().sort_index()
    peak_hour = hour_counts.idxmax()
    log(f"  Peak hour: {peak_hour}:00 ({hour_counts.max():,} interactions)")
    quiet_hour = hour_counts.idxmin()
    log(f"  Quietest hour: {quiet_hour}:00 ({hour_counts.min():,} interactions)")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(hour_counts.index, hour_counts.values, color=PALETTE[3])
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Total Interactions")
    ax.set_title("Activity by Hour of Day")
    ax.set_xticks(range(24))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    save_fig("04_hourly_pattern.png")

    # ── 5. Hour × Day-of-week heatmap ──────────────────────────────────
    log("\n" + "=" * 50)
    log("5. HOUR × DAY-OF-WEEK HEATMAP")
    log("=" * 50)
    pivot = df.groupby(["day_of_week", "hour"]).size().unstack(fill_value=0)
    pivot.index = dow_names

    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(pivot / 1000, cmap="YlOrRd", ax=ax, fmt=".0f",
                xticklabels=range(24), yticklabels=dow_names)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Day of Week")
    ax.set_title("Interaction Density: Day × Hour (thousands)")
    save_fig("04_day_hour_heatmap.png")

    # ── 6. Daily active users (DAU) ────────────────────────────────────
    log("\n" + "=" * 50)
    log("6. DAILY ACTIVE USERS (DAU)")
    log("=" * 50)
    dau = df.groupby("date")["user_id"].nunique()
    log(f"  Avg DAU: {dau.mean():,.0f}")
    log(f"  Max DAU: {dau.max():,} (on {dau.idxmax()})")
    log(f"  Min DAU: {dau.min():,} (on {dau.idxmin()})")

    fig, ax = plt.subplots(figsize=(16, 5))
    ax.plot(dau.index, dau.values, linewidth=0.5, alpha=0.7, color=PALETTE[4])
    dau_series = pd.Series(dau.values, index=pd.to_datetime(dau.index))
    rolling_dau = dau_series.rolling(7).mean()
    ax.plot(rolling_dau.index, rolling_dau.values, linewidth=2, color="red",
            label="7-day rolling avg")
    ax.set_xlabel("Date")
    ax.set_ylabel("Unique Users")
    ax.set_title("Daily Active Users (DAU)")
    ax.legend()
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.xticks(rotation=45)
    save_fig("04_daily_active_users.png")

    # ── 7. Platform usage over time ────────────────────────────────────
    log("\n" + "=" * 50)
    log("7. PLATFORM USAGE OVER TIME")
    log("=" * 50)
    monthly_plat = df.groupby(["month", "platform"]).size().unstack(fill_value=0)
    log(monthly_plat.tail(6).to_string())

    fig, ax = plt.subplots(figsize=(14, 5))
    monthly_plat.plot.bar(ax=ax, stacked=True, color=["#66b3ff", "#ff9999"], width=0.8)
    ax.set_xlabel("Month")
    ax.set_ylabel("Interactions")
    ax.set_title("Platform Usage Over Time")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    ax.legend(title="Platform")
    # Reduce x-tick labels
    labels = [str(m) for m in monthly_plat.index]
    ax.set_xticklabels(labels, rotation=45, ha="right")
    save_fig("04_platform_over_time.png")

    # ── 8. New users over time ─────────────────────────────────────────
    log("\n" + "=" * 50)
    log("8. NEW USERS OVER TIME (first interaction date)")
    log("=" * 50)
    first_seen = df.groupby("user_id")["date"].min()
    new_users_daily = first_seen.value_counts().sort_index()

    fig, ax = plt.subplots(figsize=(16, 5))
    ax.bar(new_users_daily.index, new_users_daily.values, width=1, color=PALETTE[5], alpha=0.7)
    new_users_series = pd.Series(new_users_daily.values, index=pd.to_datetime(new_users_daily.index))
    rolling_new = new_users_series.rolling(7).mean()
    ax.plot(rolling_new.index, rolling_new.values, linewidth=2, color="red",
            label="7-day rolling avg")
    ax.set_xlabel("Date")
    ax.set_ylabel("New Users")
    ax.set_title("New User Registrations Over Time")
    ax.legend()
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.xticks(rotation=45)
    save_fig("04_new_users_over_time.png")

    # ── Save report ────────────────────────────────────────────────────
    report_path = os.path.join(REPORTS_DIR, "04_temporal.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    log(f"\n→ Report saved: {report_path}")


if __name__ == "__main__":
    main()
