import pandas as pd


def to_dataframe_one(b: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "building_code": b.get("building_code"),
            "electricity_kwh": b["electricity_kwh"],
            "area_m2": b["area_m2"],
            "year_construction": b["year_construction"],
            "num_floors": b["num_floors"],
            "num_apartments": b["num_apartments"],
            "function": b["function"],
            "longitude": b["longitude"],
            "latitude": b["latitude"],
        }
    ])


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["age"] = 2025 - df["year_construction"]
    df["kwh_per_m2"] = df["electricity_kwh"] / (df["area_m2"] + 1e-6)
    df["kwh_per_apartment"] = df["electricity_kwh"] / (df["num_apartments"] + 1e-6)
    df["kwh_per_floor"] = df["electricity_kwh"] / (df["num_floors"] + 1e-6)
    return df

