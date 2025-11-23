import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
import os
import re
from ..models import ops as dbmodels


EXPECTED_COLUMNS = [
    "Building's construction year",
    "Number of floors",
    "Number of apartments",
    "Total electricity consumption (kWh)",
    "Latitude",
    "Longitude",
]


NA_VALUES = [
    "NA",
    "N/A",
    "na",
    "n/a",
    "null",
    "NULL",
    "None",
    "-",
    "—",
    "?",
]


def _norm_name(s: str) -> str:
    """Normalize a column name for fuzzy matching.
    - Lowercase and unify quotes
    - Tokenize and singularize (remove trailing 's')
    - Drop non-alphanumeric separators
    """
    s = str(s).strip().lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    tokens = re.findall(r"[a-z0-9]+", s)
    tokens = [re.sub(r"s$", "", t) for t in tokens]  # naive singularization
    return "".join(tokens)

# Common aliases keyed by normalized string -> expected canonical name
ALIASES: dict[str, str] = {
    # Building construction year
    _norm_name("building construction year"): "Building's construction year",
    _norm_name("construction year"): "Building's construction year",
    _norm_name("year built"): "Building's construction year",
    _norm_name("year of construction"): "Building's construction year",
}


def _load_tabular(path: str) -> pd.DataFrame:
    """Load CSV or Excel by extension into a DataFrame.
    Requires `openpyxl` for .xlsx files.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in {".xlsx", ".xls"}:
        # Engine auto-detected (openpyxl for .xlsx)
        return pd.read_excel(path)
    # Default: CSV
    return pd.read_csv(path, na_values=NA_VALUES, keep_default_na=True)


def validate_csv(path: str) -> pd.DataFrame:
    """
    Read CSV and normalize dtypes so downstream stats are meaningful.

    - Trim whitespace-only cells and treat them as missing (NaN)
    - Coerce expected numeric columns to numeric, invalids -> NaN
    """
    df = _load_tabular(path)

    # Try to auto-map common header variants to expected names
    expected_map = { _norm_name(c): c for c in EXPECTED_COLUMNS }
    rename: dict[str, str] = {}
    for c in list(df.columns):
        key = _norm_name(c)
        if key in expected_map:
            rename[c] = expected_map[key]
        elif key in ALIASES:
            rename[c] = ALIASES[key]
    if rename:
        df = df.rename(columns=rename)

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    # Treat empty strings / whitespace as NaN across the board
    df = df.replace(r"^\s*$", np.nan, regex=True)

    # Coerce numeric columns
    numeric_cols = [
        "Building's construction year",
        "Number of floors",
        "Number of apartments",
        "Total electricity consumption (kWh)",
        "Latitude",
        "Longitude",
    ]
    for col in numeric_cols:
        if col in df.columns:
            # Remove thousands separators and normalize before numeric coercion
            ser = df[col]
            if ser.dtype == object:
                ser = ser.astype(str).str.replace(",", "", regex=False).str.strip()
            df[col] = pd.to_numeric(ser, errors="coerce")

    return df

def compute_dq(df: pd.DataFrame) -> dict:
    """
    Full data-quality report for a tabular dataset.

    Returns a dict with:
      - row_count
      - duplicate_rows / duplicate_fraction
      - columns: per-column metrics
      - missingness: simple {col: effective_missing_fraction} for backward compat
    """
    from datetime import datetime

    n_rows = len(df)
    if n_rows == 0:
        return {
            "row_count": 0,
            "duplicate_rows": 0,
            "duplicate_fraction": 0.0,
            "columns": {},
            "missingness": {},
        }

    # ---------- Global metrics ----------
    duplicate_rows = int(df.duplicated().sum())
    duplicate_fraction = float(duplicate_rows / n_rows)

    numeric_expected = {
        "Building's construction year",
        "Number of floors",
        "Number of apartments",
        "Total electricity consumption (kWh)",
        "Latitude",
        "Longitude",
    }

    col_metrics: dict[str, dict] = {}

    # ---------- Helper for per-column metrics ----------
    def _col_dq(name: str, series: pd.Series) -> dict:
        s = series.copy()
        base_missing = s.isna()

        # Decide if we treat as numeric, and get numeric view
        treat_as_numeric = name in numeric_expected or pd.api.types.is_numeric_dtype(s)
        if treat_as_numeric:
            s_num = pd.to_numeric(s, errors="coerce")
        else:
            s_num = None

        invalid_mask = pd.Series(False, index=s.index)

        # ---- Domain-specific rules ----
        if name == "Building's construction year" and s_num is not None:
            current = datetime.utcnow().year + 1
            invalid_mask = invalid_mask | (s_num < 1200) | (s_num > current)

        elif name in ("Number of floors", "Number of apartments") and s_num is not None:
            invalid_mask = invalid_mask | (s_num <= 0)

        elif name == "Total electricity consumption (kWh)" and s_num is not None:
            invalid_mask = invalid_mask | (s_num <= 0)

        elif name in ("Latitude", "Longitude"):
            # Use both lat + lon to decide invalid
            lat = pd.to_numeric(
                df.get("Latitude"), errors="coerce"
            ) if "Latitude" in df.columns else None
            lon = pd.to_numeric(
                df.get("Longitude"), errors="coerce"
            ) if "Longitude" in df.columns else None

            if lat is not None and lon is not None:
                pair_zero = (lat.fillna(0) == 0) & (lon.fillna(0) == 0)
                out_range = (lat < -90) | (lat > 90) | (lon < -180) | (lon > 180)
                invalid_mask = invalid_mask | pair_zero | out_range

        # Effective missing = NaN OR invalid by rules
        effective_missing = base_missing | invalid_mask

        # ---- Numeric stats if applicable ----
        stats = {
            "missing_fraction": float(base_missing.mean()),
            "invalid_fraction": float(invalid_mask.mean()),
            "effective_missing_fraction": float(effective_missing.mean()),
            "distinct_count": int(s.nunique(dropna=True)),
            "dtype": str(s.dtype),
        }

        if treat_as_numeric and s_num is not None:
            x = s_num.dropna()
            if len(x) > 0:
                stats.update(
                    {
                        "min": float(x.min()),
                        "max": float(x.max()),
                        "mean": float(x.mean()),
                        "std": float(x.std(ddof=1)) if len(x) > 1 else 0.0,
                        "p25": float(x.quantile(0.25)),
                        "p50": float(x.quantile(0.50)),
                        "p75": float(x.quantile(0.75)),
                        "skewness": float(x.skew()),
                    }
                )

                # Z-score outliers
                z = (x - x.mean()) / (x.std(ddof=1) or 1.0)
                z_outlier = (z.abs() > 3).mean()
                stats["z_outlier_fraction"] = float(z_outlier)

                # IQR outliers
                Q1 = x.quantile(0.25)
                Q3 = x.quantile(0.75)
                IQR = Q3 - Q1
                if IQR > 0:
                    iqr_mask = (x < Q1 - 1.5 * IQR) | (x > Q3 + 1.5 * IQR)
                    stats["iqr_outlier_fraction"] = float(iqr_mask.mean())
                else:
                    stats["iqr_outlier_fraction"] = 0.0
            else:
                # No valid numeric data
                stats.update(
                    {
                        "min": None,
                        "max": None,
                        "mean": None,
                        "std": None,
                        "p25": None,
                        "p50": None,
                        "p75": None,
                        "skewness": None,
                        "z_outlier_fraction": 0.0,
                        "iqr_outlier_fraction": 0.0,
                    }
                )
        else:
            # Non-numeric: you might later add top-k category frequencies, etc.
            stats.update(
                {
                    "min": None,
                    "max": None,
                    "mean": None,
                    "std": None,
                    "p25": None,
                    "p50": None,
                    "p75": None,
                    "skewness": None,
                    "z_outlier_fraction": 0.0,
                    "iqr_outlier_fraction": 0.0,
                }
            )

        return stats

    # Build per-column metrics
    for col in df.columns:
        col_metrics[col] = _col_dq(col, df[col])

    # Backward-compatible missingness dict:
    # we use effective_missing_fraction.
    missingness_simple = {
        c: col_metrics[c]["effective_missing_fraction"]
        for c in EXPECTED_COLUMNS
        if c in col_metrics
    }

    dq = {
        "row_count": n_rows,
        "duplicate_rows": duplicate_rows,
        "duplicate_fraction": duplicate_fraction,
        "columns": col_metrics,
        "missingness": missingness_simple,
    }
    return dq


def calculate_missingness(df: pd.DataFrame) -> dict[str, float]:
    """
    Backward-compatible wrapper used by existing endpoints.
    Returns simple {column: effective_missing_fraction}.
    """
    dq = compute_dq(df)
    return dq["missingness"]


def df_to_buildings(df: pd.DataFrame, db: Session) -> int:
    n = 0
    for _, row in df.iterrows():
        b = dbmodels.Building(
            building_name=None,
            construction_year=int(row.get("Building's construction year", 0)) if pd.notna(row.get("Building's construction year")) else None,
            num_floors=int(row.get("Number of floors", 0)) if pd.notna(row.get("Number of floors")) else None,
            num_apartments=int(row.get("Number of apartments", 0)) if pd.notna(row.get("Number of apartments")) else None,
            longitude=float(row.get("Longitude", None)) if pd.notna(row.get("Longitude")) else None,
            latitude=float(row.get("Latitude", None)) if pd.notna(row.get("Latitude")) else None,
            total_kwh=float(row.get("Total electricity consumption (kWh)", None)) if pd.notna(row.get("Total electricity consumption (kWh)")) else None,
        )
        db.add(b)
        n += 1
    db.commit()
    return n

