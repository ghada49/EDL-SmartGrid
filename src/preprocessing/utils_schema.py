# utils_schema.py
import pandas as pd

CANONICAL_MAP = {
    # raw → canonical (adjust these to your sheet)
    "Building Construction Year": "build_year",
    "Number of floors": "nb_floor",
    "Number of Apartments": "nb_appart",
    "kwh": "kwh",
    "Area (m2)": "area_m2",
    "Latitude": "lat",
    "Longitude": "long",
    "Function": "function",
    "FID": "fid",
    "District": "district",
}

DTYPES = {
    "build_year": "Int64",
    "nb_floor": "Int64",
    "nb_appart": "Int64",
    "kwh": "float",
    "area_m2": "float",
    "lat": "float",
    "long": "float",
    "function": "string",
    "district": "string",
    "fid": "string",
}

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={k:v for k,v in CANONICAL_MAP.items() if k in df.columns})
    for c, dt in DTYPES.items():
        if c in df.columns:
            try:
                if dt == "Int64":
                    df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
                elif dt == "float":
                    df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
                else:
                    df[c] = df[c].astype(dt)
            except Exception:
                pass
    return df
