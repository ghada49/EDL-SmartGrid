# impute_rules.py
import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer

def fix_zero_to_nan(df: pd.DataFrame) -> pd.DataFrame:
    for c in ("nb_floor", "nb_appart", "area_m2"):
        if c in df.columns:
            df.loc[df[c].fillna(0) == 0, c] = np.nan
    return df

def impute_floors_apartments(df: pd.DataFrame, n_neighbors: int = 5) -> pd.DataFrame:
    """KNN on area, year, lat/long to fill nb_floor/nb_appart."""
    cols = [c for c in ["nb_floor","nb_appart","area_m2","build_year","lat","long"] if c in df.columns]
    work = df[cols].copy()
    imputer = KNNImputer(n_neighbors=n_neighbors, weights="distance")
    imputed = imputer.fit_transform(work)
    work[:] = imputed
    # round back integer columns
    if "nb_floor" in work:  work["nb_floor"]  = np.clip(np.rint(work["nb_floor"]), 1, None).astype(int)
    if "nb_appart" in work: work["nb_appart"] = np.clip(np.rint(work["nb_appart"]), 1, None).astype(int)
    df[work.columns] = work
    return df

def add_derived_building_ratios(df: pd.DataFrame) -> pd.DataFrame:
    if {"kwh","area_m2"}.issubset(df):    df["kwh_per_m2"] = df["kwh"] / df["area_m2"].replace(0,np.nan)
    if {"kwh","nb_appart"}.issubset(df):  df["kwh_per_appt"] = df["kwh"] / df["nb_appart"].replace(0,np.nan)
    if {"area_m2","nb_appart"}.issubset(df): df["area_per_appt"] = df["area_m2"] / df["nb_appart"].replace(0,np.nan)
    if {"nb_floor","nb_appart"}.issubset(df): df["appts_per_floor"] = df["nb_appart"] / df["nb_floor"].replace(0,np.nan)
    return df
