import pandas as pd
import numpy as np


KEY_COLUMNS = [
    "Total electricity consumption (kWh)",
    "Number of apartments",
    "Number of floors",
]

DISCRETE_COLUMNS = {
    "Number of apartments",
    "Number of floors",
}


def _summarize(df: pd.DataFrame):  # noqa: F401 (kept for future use)
    return df[KEY_COLUMNS].describe().T[["mean", "std", "min", "max"]]


def _as_numeric(s: pd.Series) -> pd.Series:
    """Best‑effort numeric coercion for messy CSVs.
    - Remove thousands separators
    - Strip units/symbols, keep digits, sign, decimal, exponent
    - Coerce to float with NaNs for invalids
    """
    if s.dtype == object:
        s = s.astype(str).str.replace(",", "", regex=False)
        s = s.str.replace(r"[^0-9eE+\-\.]+", "", regex=True)
    return pd.to_numeric(s, errors="coerce")


def simple_drift_report(candidate_csv: str, reference_csv: str, z_threshold: float = 2.0):
    new = pd.read_csv(candidate_csv)
    ref = pd.read_csv(reference_csv)
    report = {"columns": []}
    for col in KEY_COLUMNS:
        if col not in new.columns or col not in ref.columns:
            continue
        new_col = _as_numeric(new[col]).dropna()
        ref_col = _as_numeric(ref[col]).dropna()
        if len(new_col) == 0 or len(ref_col) == 0:
            continue

        if col in DISCRETE_COLUMNS:
            # Use PSI for discrete/ordinal integer-like columns
            new_counts = new_col.value_counts(normalize=True)
            ref_counts = ref_col.value_counts(normalize=True)
            all_vals = sorted(set(new_counts.index.tolist()) | set(ref_counts.index.tolist()))
            eps = 1e-6
            psi = 0.0
            for v in all_vals:
                p = float(ref_counts.get(v, 0.0)) + eps
                q = float(new_counts.get(v, 0.0)) + eps
                psi += (q - p) * np.log(q / p)
            z_or_psi = float(abs(psi))
            drift = z_or_psi > 0.1  # common PSI threshold
            mu_ref = float(ref_col.mean())
            mu_new = float(new_col.mean())
            report["columns"].append(
                {
                    "column": col,
                    "ref_mean": mu_ref,
                    "new_mean": mu_new,
                    "z_score": z_or_psi,  # reuse field for UI; value is PSI
                    "drift_flag": drift,
                    "method": "psi",
                }
            )
        else:
            # Continuous columns: two-sample z using pooled SE
            mu_ref = float(ref_col.mean())
            mu_new = float(new_col.mean())
            sd_ref = float(ref_col.std(ddof=1)) if len(ref_col) > 1 else 0.0
            sd_new = float(new_col.std(ddof=1)) if len(new_col) > 1 else 0.0
            denom = (sd_ref ** 2) / max(len(ref_col), 1) + (sd_new ** 2) / max(len(new_col), 1)
            denom = float(np.sqrt(denom)) if denom > 0 else 1e-9
            z = abs(mu_new - mu_ref) / denom
            report["columns"].append(
                {
                    "column": col,
                    "ref_mean": float(mu_ref),
                    "new_mean": float(mu_new),
                    "z_score": float(z),
                    "drift_flag": bool(z > z_threshold),
                    "method": "z",
                }
            )
    return report

