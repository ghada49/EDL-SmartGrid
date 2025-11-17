# tests/feature_engineering_test.py
# Purpose: Load raw data, run preprocessing + FeatureEngineering pipeline, and save processed CSV.

import os
import sys
import pandas as pd
import numpy as np

# ---------------- Paths ----------------
HERE = os.path.abspath(os.path.dirname(__file__))
BASE_DIR = os.path.abspath(os.path.join(HERE, ".."))  # repo root
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")

RAW_XLSX = os.path.join(RAW_DIR, "data.xlsx")
LATEST_CSV = os.path.join(BASE_DIR, "data", "latest_ingested.csv")
FALLBACK_XLSX = "/mnt/data/data.xlsx"  # for Colab/other envs
OUT_CSV = os.path.join(PROC_DIR, "processed_data.csv")

# Make sure src is importable
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# ---------------- Imports ----------------
try:
    from data_loading.load_data import DataLoader
    from data_loading.feature_engineering import FeatureEngineering
except Exception as e:
    raise ImportError(
        "Failed to import from src/. Check that your repo has src/data_loading/* "
        f"and that PYTHONPATH includes src/. Error: {e}"
    )

# OPTIONAL: if you’re still using the extra preprocessing utils
try:
    from preprocessing.utils_schema import standardize_columns
    from preprocessing.impute_rules import (
        fix_zero_to_nan,
        impute_floors_apartments,
        add_derived_building_ratios,
    )
    HAS_PRE = True
except Exception:
    HAS_PRE = False


def _resolve_raw_path() -> str:
    """
    Return the raw data path, preferring latest_ingested.csv (ingested dataset)
    if available, then data/raw/data.xlsx, then /mnt/data/data.xlsx.
    """
    if os.path.exists(LATEST_CSV):
        return LATEST_CSV
    if os.path.exists(RAW_XLSX):
        return RAW_XLSX
    if os.path.exists(FALLBACK_XLSX):
        return FALLBACK_XLSX
    raise FileNotFoundError(
        "No raw input file found.\n"
        f"Checked:\n  - {LATEST_CSV}\n  - {RAW_XLSX}\n  - {FALLBACK_XLSX}\n"
        "Please place the dataset in one of these locations."
    )


def _canonicalize_for_model(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the columns required by the anomaly model exist with the exact names it expects:
      - build_year
      - nb_appart
      - Total Electricity Consumption (kwH)
    and keep nb_floor, lat, long as-is.

    This is where we map human Excel names → model canonical names.
    """
    rename_map = {}

    # Year column
    if "build_year" not in df.columns:
        # common alternative from your logs
        if "Building's construction year" in df.columns:
            rename_map["Building's construction year"] = "build_year"

    # Apartments
    if "nb_appart" not in df.columns:
        if "Number of apartments" in df.columns:
            rename_map["Number of apartments"] = "nb_appart"

    # Total kWh – model expects "Total Electricity Consumption (kwH)"
    if "Total Electricity Consumption (kwH)" not in df.columns:
        # Your log shows: "Total electricity consumption (kWh)"
        if "Total electricity consumption (kWh)" in df.columns:
            rename_map["Total electricity consumption (kWh)"] = "Total Electricity Consumption (kwH)"

    if rename_map:
        print("[FE] Renaming columns for model compatibility:")
        for old, new in rename_map.items():
            print(f"   - {old!r} -> {new!r}")
        df = df.rename(columns=rename_map)

    return df


def main():
    # Ensure output directory
    os.makedirs(PROC_DIR, exist_ok=True)

    # 1) Load
    raw_path = _resolve_raw_path()
    print(f"[FE] Loading raw data from: {raw_path}")
    loader = DataLoader(raw_path)
    df = loader.load_data()
    print(f"[FE] Loaded shape: {df.shape}")

    # 2) Optional extra preprocessing (if those modules exist)
    if HAS_PRE:
        print("[FE] Applying schema + imputation + derived ratios")
        df = standardize_columns(df)
        df = fix_zero_to_nan(df)
        df = impute_floors_apartments(df, n_neighbors=5)
        df = add_derived_building_ratios(df)

    # 2.5) Canonicalize names for the anomaly model
    df = _canonicalize_for_model(df)

    # 2.6) Quick sanity checks
    if {"nb_floor", "nb_appart"}.issubset(df.columns):
        assert (df["nb_floor"].dropna() > 0).all(), "nb_floor has non-positive values after preprocessing."
        assert (df["nb_appart"].dropna() > 0).all(), "nb_appart has non-positive values after preprocessing."

    # 3) Feature Engineering pipeline
    fe = FeatureEngineering(df)
    fe.apply_pipeline(
        year_col="build_year",       # after rename this MUST exist
        year_out="year_norm",        # min-shifted column (gets skew fixes)
        add_year_z=True,             # adds year_norm_z
        skew_threshold=1.0,
        skew_exclude={"fid", "lat", "long"},
        corr_threshold=0.85,
        corr_exclude={"fid", "lat", "long", "kwh", "Total Electricity Consumption (kwH)"},
    )
    df_processed = fe.df

    # 4) Save
    df_processed.to_csv(OUT_CSV, index=False)
    print(f"[FE] Saved processed data to: {OUT_CSV}")
    print(f"[FE] Final shape: {df_processed.shape}")

    # 5) Diagnostics (post-transform skew + top correlations) – all ASCII only
    num_cols = df_processed.select_dtypes(include=[np.number]).columns.tolist()
    if num_cols:
        skew = df_processed[num_cols].skew().sort_values(ascending=False)
        print("\n[FE] Skewness (post-transforms):")
        print(skew)

        corr = df_processed[num_cols].corr().abs()
        if not corr.empty:
            mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
            upper = corr.where(mask)
            top_pairs = (
                upper.stack()
                     .sort_values(ascending=False)
                     .head(5)
            )
            if not top_pairs.empty:
                print("\n[FE] Top remaining absolute correlations:")
                for (a, b), v in top_pairs.items():
                    print(f"  - {a} <-> {b}: {v:.3f}")
    else:
        print("[FE] No numeric columns after processing.")

    # 6) Ratio sanity info (not assertions—just visibility)
    for c in ("kwh_per_m2", "kwh_per_appt", "area_per_appt", "appts_per_floor"):
        if c in df_processed.columns:
            bad = df_processed[c].replace([np.inf, -np.inf], np.nan).isna().mean()
            print(f"[FE] {c}: {bad:.1%} NaN/Inf (ok if due to missing denominators)")


if __name__ == "__main__":
    main()
