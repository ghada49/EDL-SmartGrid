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


def calculate_missingness(df: pd.DataFrame) -> dict[str, float]:
    """Compute fraction missing per expected column using rule-aware logic.
    Assumes the DataFrame has been normalized by validate_csv.
    """
    import pandas as pd
    from datetime import datetime

    def col_missing(series: pd.Series, name: str) -> float:
        s = series.copy()
        miss = s.isna()
        if name == "Building's construction year":
            year = pd.to_numeric(s, errors="coerce")
            current = datetime.utcnow().year + 1
            miss = miss | (year < 1900) | (year > current)
        elif name in ("Number of floors", "Number of apartments"):
            val = pd.to_numeric(s, errors="coerce")
            miss = miss | (val <= 0)
        elif name == "Total electricity consumption (kWh)":
            val = pd.to_numeric(s, errors="coerce")
            miss = miss | (val <= 0)
        elif name in ("Latitude", "Longitude"):
            lat = pd.to_numeric(df.get("Latitude"), errors="coerce") if "Latitude" in df.columns else None
            lon = pd.to_numeric(df.get("Longitude"), errors="coerce") if "Longitude" in df.columns else None
            if lat is not None and lon is not None:
                pair_zero = (lat.fillna(0) == 0) & (lon.fillna(0) == 0)
                out_range = (lat < -90) | (lat > 90) | (lon < -180) | (lon > 180)
                miss = miss | pair_zero | out_range
        return float(miss.mean()) if len(s) else 0.0

    return {c: (col_missing(df[c], c) if c in df.columns else 1.0) for c in EXPECTED_COLUMNS}


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

