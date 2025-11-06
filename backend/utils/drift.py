import pandas as pd
import numpy as np


KEY_COLUMNS = [
    "Total electricity consumption (kWh)",
    "Number of apartments",
    "Number of floors",
]


def _summarize(df: pd.DataFrame):  # noqa: F401 (kept for future use)
    return df[KEY_COLUMNS].describe().T[["mean", "std", "min", "max"]]


def simple_drift_report(candidate_csv: str, reference_csv: str, z_threshold: float = 2.0):
    new = pd.read_csv(candidate_csv)
    ref = pd.read_csv(reference_csv)
    report = {"columns": []}
    for col in KEY_COLUMNS:
        if col not in new.columns or col not in ref.columns:
            continue
        mu_ref = ref[col].mean()
        sd_ref = ref[col].std(ddof=1) if ref[col].std(ddof=1) > 0 else 1.0
        mu_new = new[col].mean()
        z = abs((mu_new - mu_ref) / sd_ref)
        report["columns"].append(
            {
                "column": col,
                "ref_mean": float(mu_ref),
                "new_mean": float(mu_new),
                "z_score": float(z),
                "drift_flag": bool(z > z_threshold),
            }
        )
    return report

