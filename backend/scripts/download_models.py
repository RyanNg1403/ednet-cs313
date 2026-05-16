"""Download all model weights + the engineered-features parquet from Google Drive.

Run from `backend/`:

    python scripts/download_models.py

Idempotent — files already present are skipped. Source folders:

  Phương — https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_
    random_forest_final_model.pkl, xgboost_final_model.json, kt4_features_1.parquet

  Nguyễn — https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397
    lightgbm_final_model.pkl, ednet_lstm_11_features.keras,
    ednet_lstm_raw.keras, ednet_1d_cnn_raw.keras
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

try:
    import gdown
except ImportError:
    sys.exit("gdown is not installed. Run: pip install -r requirements.txt")


BACKEND_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BACKEND_DIR / "models"
DATA_DIR = BACKEND_DIR / "data"

PHUONG_FOLDER = "https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_"
NGUYEN_FOLDER = "https://drive.google.com/drive/folders/1Pye5N2NWknKhDchmHjkwv8sbtKO0Ewh0?usp=sharing"

# What we want to keep, and where to place it.
# Source filename → (destination directory, destination filename).
WANTED = {
    # From Phương's folder
    "xgboost_final_model.json":      (MODELS_DIR, "xgboost_final_model.json"),
    "random_forest_final_model.pkl": (MODELS_DIR, "random_forest_final_model.pkl"),
    "kt4_features_1.parquet":        (DATA_DIR,   "kt4_features_1.parquet"),
    # From Nguyễn's folder
    "lightgbm_final_model.pkl":      (MODELS_DIR, "lightgbm_final_model.pkl"),
    "ednet_lstm_11_features.keras":  (MODELS_DIR, "ednet_lstm_11_features.keras"),
    "ednet_lstm_raw.keras":          (MODELS_DIR, "ednet_lstm_raw.keras"),
    "ednet_1d_cnn_raw.keras":        (MODELS_DIR, "ednet_1d_cnn_raw.keras"),
}


def already_present() -> set[str]:
    return {
        src for src, (dst_dir, dst_name) in WANTED.items()
        if (dst_dir / dst_name).exists() and (dst_dir / dst_name).stat().st_size > 0
    }


def download_folder(url: str, label: str, scratch: Path) -> None:
    print(f"\n→ Downloading {label} folder into {scratch} ...")
    out = scratch / label
    out.mkdir(parents=True, exist_ok=True)
    gdown.download_folder(url=url, output=str(out), quiet=False, use_cookies=False)


def collect_from(scratch: Path, missing: set[str]) -> set[str]:
    """Move wanted files out of the scratch tree into their final homes."""
    placed: set[str] = set()
    for src_path in scratch.rglob("*"):
        if not src_path.is_file():
            continue
        if src_path.name in missing and src_path.name not in placed:
            dst_dir, dst_name = WANTED[src_path.name]
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_path = dst_dir / dst_name
            print(f"  + {src_path.name}  →  {dst_path.relative_to(BACKEND_DIR)}")
            shutil.move(str(src_path), str(dst_path))
            placed.add(src_path.name)
    return placed


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    have = already_present()
    missing = set(WANTED) - have

    print("Daily Challenge model + dataset downloader")
    print(f"  backend dir: {BACKEND_DIR}")
    print(f"  already present: {sorted(have) or '(none)'}")
    print(f"  to fetch: {sorted(missing) or '(nothing)'}")

    if not missing:
        print("\nAll files already present — nothing to do.")
        return 0

    # Use a single tempdir for both folders so we can clean up reliably.
    with tempfile.TemporaryDirectory(prefix="ednet_dl_") as scratch_str:
        scratch = Path(scratch_str)

        # We always pull both folders if any of their files are missing — the
        # folder downloader doesn't support a per-file allowlist.
        phuong_files = {"xgboost_final_model.json", "random_forest_final_model.pkl",
                        "kt4_features_1.parquet"}
        nguyen_files = {"lightgbm_final_model.pkl", "ednet_lstm_11_features.keras",
                        "ednet_lstm_raw.keras", "ednet_1d_cnn_raw.keras"}

        if missing & phuong_files:
            download_folder(PHUONG_FOLDER, "phuong", scratch)
        if missing & nguyen_files:
            download_folder(NGUYEN_FOLDER, "nguyen", scratch)

        placed = collect_from(scratch, missing)

    still_missing = missing - placed
    if still_missing:
        print(f"\n⚠ Still missing after download: {sorted(still_missing)}")
        print("Check the Drive folder URLs above — file may have been renamed/moved.")
        return 1

    print("\n✓ All files in place.")
    print("  Models:")
    for f in sorted(p.name for p in MODELS_DIR.iterdir() if p.is_file()):
        print(f"    backend/models/{f}")
    print("  Data:")
    for f in sorted(p.name for p in DATA_DIR.iterdir() if p.is_file()):
        print(f"    backend/data/{f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
