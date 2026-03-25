"""
01_convert_to_parquet.py
========================
Consolidate 297,915 per-user KT4 CSV files into a single Parquet file.
Adds a `user_id` column extracted from the filename.

Processes in batches to stay within memory limits (~16GB RAM).
Output: processed/kt4_interactions.parquet (snappy compressed)
"""

import os
import glob
import time
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KT4_DIR = os.path.join(BASE_DIR, "KT4")
OUTPUT_DIR = os.path.join(BASE_DIR, "processed")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "kt4_interactions.parquet")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Config ─────────────────────────────────────────────────────────────
BATCH_SIZE = 10_000  # users per batch

# ── Schema ─────────────────────────────────────────────────────────────
# Keep all original columns + add user_id
ARROW_SCHEMA = pa.schema([
    ("timestamp", pa.int64()),
    ("action_type", pa.dictionary(pa.int8(), pa.string())),
    ("item_id", pa.string()),
    ("cursor_time", pa.float64()),      # nullable: empty for non-media actions
    ("source", pa.dictionary(pa.int8(), pa.string())),
    ("user_answer", pa.dictionary(pa.int8(), pa.string())),
    ("platform", pa.dictionary(pa.int8(), pa.string())),
    ("user_id", pa.int32()),
])

# Pandas dtypes for reading CSVs efficiently
CSV_DTYPES = {
    "timestamp": "int64",
    "action_type": "str",
    "item_id": "str",
    "cursor_time": "str",   # read as string first, convert later (handles empty)
    "source": "str",
    "user_answer": "str",
    "platform": "str",
}


def extract_user_id(filepath: str) -> int:
    """Extract numeric user_id from filename like 'u12345.csv'."""
    basename = os.path.basename(filepath)
    return int(basename[1:].replace(".csv", ""))


def process_batch(csv_files: list[str]) -> pd.DataFrame:
    """Read a batch of CSV files and concatenate into a single DataFrame."""
    frames = []
    for fpath in csv_files:
        uid = extract_user_id(fpath)
        try:
            df = pd.read_csv(fpath, dtype=CSV_DTYPES)
            df["user_id"] = uid
            frames.append(df)
        except pd.errors.EmptyDataError:
            continue  # skip empty files
        except Exception as e:
            print(f"  Warning: skipping {fpath}: {e}")
            continue

    if not frames:
        return pd.DataFrame()

    batch_df = pd.concat(frames, ignore_index=True)

    # Convert cursor_time: empty string / NaN → NaN, otherwise float
    batch_df["cursor_time"] = pd.to_numeric(batch_df["cursor_time"], errors="coerce")

    return batch_df


def main():
    print("=" * 60)
    print("KT4 CSV → Parquet Conversion")
    print("=" * 60)

    # Discover all user CSV files
    csv_files = sorted(glob.glob(os.path.join(KT4_DIR, "u*.csv")))
    n_files = len(csv_files)
    print(f"Found {n_files:,} user CSV files in {KT4_DIR}")

    if n_files == 0:
        print("ERROR: No CSV files found. Check KT4_DIR path.")
        return

    n_batches = (n_files + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Processing in {n_batches} batches of up to {BATCH_SIZE:,} files each\n")

    writer = None
    total_rows = 0
    skipped_empty = 0
    start_time = time.time()

    for batch_idx in range(n_batches):
        lo = batch_idx * BATCH_SIZE
        hi = min(lo + BATCH_SIZE, n_files)
        batch_files = csv_files[lo:hi]

        print(f"Batch {batch_idx + 1}/{n_batches} "
              f"(files {lo + 1:,}–{hi:,})")

        batch_df = process_batch(batch_files)

        if batch_df.empty:
            skipped_empty += len(batch_files)
            continue

        n_rows = len(batch_df)
        total_rows += n_rows

        # Convert to Arrow table with target schema
        table = pa.Table.from_pandas(batch_df, schema=ARROW_SCHEMA, preserve_index=False)

        if writer is None:
            writer = pq.ParquetWriter(
                OUTPUT_FILE,
                schema=ARROW_SCHEMA,
                compression="snappy",
                version="2.6",
            )

        writer.write_table(table)
        elapsed = time.time() - start_time
        rate = total_rows / elapsed if elapsed > 0 else 0
        print(f"  → {n_rows:,} rows  |  cumulative: {total_rows:,}  |  "
              f"{rate:,.0f} rows/sec  |  {elapsed:.0f}s elapsed")

    if writer:
        writer.close()

    elapsed_total = time.time() - start_time
    file_size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)

    print("\n" + "=" * 60)
    print("Conversion complete!")
    print(f"  Total rows:     {total_rows:,}")
    print(f"  Output file:    {OUTPUT_FILE}")
    print(f"  File size:      {file_size_mb:,.1f} MB")
    print(f"  Time elapsed:   {elapsed_total:.1f}s")
    print(f"  Compression:    snappy")
    if skipped_empty:
        print(f"  Skipped empty:  {skipped_empty}")
    print("=" * 60)


if __name__ == "__main__":
    main()
