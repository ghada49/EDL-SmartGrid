import pandas as pd
from sqlalchemy.orm import Session
from app.db import models as dbmodels

EXPECTED_COLUMNS = [
    "Building's construction year",
    "Number of floors",
    "Number of apartments",
    "Total electricity consumption (kWh)",
    "Latitude",
    "Longitude"
]

def validate_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
    # basic cleaning
    return df

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