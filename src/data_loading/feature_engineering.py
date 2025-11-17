# src/data_loading/feature_engineering.py

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, PowerTransformer
from typing import Optional, Set


class FeatureEngineering:
    """
    Post-loading feature engineering utilities.
    Designed to be used after your DataLoader finishes loading/cleaning.

    Desired behavior for year columns:
      - Keep original `build_year` untouched (semantics preserved).
      - Create `year_out` (default: 'Year_Normalized') by min-shifting: min→0, max→max-min.
      - Apply skew fixes to `year_out` (NOT to `build_year`).
      - Compute z-score for the (possibly transformed) `year_out` → `year_out + "_z"`.
      - Protect the z-scored year from correlation pruning.
    """

    def __init__(self, df: pd.DataFrame):
        if df is None or not isinstance(df, pd.DataFrame):
            raise ValueError("FeatureEngineering expects a non-empty pandas DataFrame.")
        self.df = df

    # ------------- Utilities -------------

    def add_zscore(self, col: str, z_col: Optional[str] = None):
        """
        Create a z-score column for `col` (after all intended transforms on `col`).
        """
        if col not in self.df.columns:
            print(f"[WARN] '{col}' not found; cannot add z-score.")
            return self
        z_col = z_col or (col + "_z")
        scaler = StandardScaler()
        self.df[z_col] = scaler.fit_transform(self.df[[col]])
        print(f"[SCALE] Added z-score column: {z_col} (from {col})")
        return self

    # ------------- Year normalization -------------

    def normalize_construction_year(
        self,
        year_col: str = "Building Construction Year",
        out_col: str = "Year_Normalized",
        add_zscore: bool = True,
    ):
        """
        Min-shifts construction year so min becomes 0 (max becomes max-min).
        Keeps the original year column; writes to `out_col`.
        Optionally adds z-score column `<out_col>_z`.
        """
        if year_col not in self.df.columns:
            print(f"[WARN] Column '{year_col}' not found; skipping normalization.")
            return self

        min_year = self.df[year_col].min()
        self.df[out_col] = self.df[year_col] - min_year
        print(f"[NORM] {year_col} -> {out_col}: min={min_year}, range=[0 .. {int(self.df[out_col].max())}]")

        if add_zscore:
            self.add_zscore(out_col, out_col + "_z")

        return self

    # ------------- Skewness handling -------------

    def handle_skewness_auto(
        self,
        threshold: float = 1.0,
        exclude: Optional[Set[str]] = None,
    ):
        """
        Auto-transform skewed numeric columns:
          - If skew >  threshold → apply log1p (clip negatives to 0 first)
          - If skew < -threshold → apply Yeo–Johnson
        Only keep the transform if abs(skew) improves. Overwrites original column.
        """
        exclude = set() if exclude is None else set(exclude)

        numeric_cols = [
            c for c in self.df.select_dtypes(include=[np.number]).columns if c not in exclude
        ]

        if not numeric_cols:
            print("[WARN] No numeric columns to process for skewness.")
            return self

        init_skew = self.df[numeric_cols].skew().to_dict()
        changes = []

        for col in numeric_cols:
            vals = self.df[col]
            if not np.isfinite(vals).all():
                print(f"[SKIP] Skipping '{col}' due to non-finite values.")
                continue

            s = init_skew[col]

            # Positive skew → log1p
            if s > threshold:
                tmp = np.log1p(vals.clip(lower=0))  # guard against negatives/zeros
                new_skew = pd.Series(tmp).skew()
                if abs(new_skew) < abs(s):
                    self.df[col] = tmp
                    changes.append((col, s, new_skew, "log1p"))

            # Negative skew → Yeo–Johnson
            elif s < -threshold:
                pt = PowerTransformer(method="yeo-johnson", standardize=False)
                try:
                    tmp = pt.fit_transform(vals.values.reshape(-1, 1)).ravel()
                    new_skew = pd.Series(tmp).skew()
                    if abs(new_skew) < abs(s):
                        self.df[col] = tmp
                        changes.append((col, s, new_skew, "yeo-johnson"))
                except Exception as e:
                    print(f"[WARN] Yeo-Johnson failed for '{col}': {e}. Skipping.")

        if changes:
            print("\n[FIX] Skewness fixes applied (kept only if improved):")
            for col, old_s, new_s, how in changes:
                print(f"  • {col}: skew {old_s:.3f} -> {new_s:.3f} via {how}")
        else:
            print("\n[INFO] No skewness transforms improved columns (or none exceeded threshold).")

        return self

    # ------------- Correlation pruning -------------

    def drop_highly_correlated(
        self,
        threshold: float = 0.8,
        exclude: Optional[Set[str]] = None,
    ):
        """
        Drop one of each pair of numeric features with |corr| > threshold.
        Priority rules per pair (order-independent):
          1) If the pair is ('Number of Apartments', 'Number of floors'): drop 'Number of floors'
          2) If one col is in `exclude`, drop the other (never drop excluded)
          3) Otherwise, keep the earlier (leftmost) column and drop the later one
        """
        import numpy as np

        exclude = set() if exclude is None else set(exclude)

        corr = self.df.corr(numeric_only=True).abs()
        if corr.empty:
            print("[WARN] No numeric correlation matrix available.")
            return self

        cols = list(corr.columns)
        col_index = {c: i for i, c in enumerate(cols)}
        to_drop = set()

        # Gather all pairs with |r| > threshold, order-independent
        pairs = []
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a, b = cols[i], cols[j]
                r = corr.iat[i, j]
                if np.isfinite(r) and r > threshold:
                    pairs.append((a, b, r))

        def choose_drop(a: str, b: str) -> Optional[str]:
            """Return which column to drop for pair (a,b), or None to skip."""
            # If already decided for either, respect prior drop
            if a in to_drop or b in to_drop:
                return None

            # 1) Hard preference: keep Apartments, drop Floors
            apartments = "Number of Apartments"
            floors = "Number of floors"
            if (a == apartments and b == floors) or (a == floors and b == apartments):
                if floors not in exclude:
                    return floors
                if apartments not in exclude:
                    return apartments
                return None  # both protected

            # 2) Exclusions: never drop excluded; drop the other
            if a in exclude and b not in exclude:
                return b
            if b in exclude and a not in exclude:
                return a
            if a in exclude and b in exclude:
                return None  # both protected

            # 3) Default: keep earlier (leftmost), drop later
            return b if col_index[a] < col_index[b] else a

        # Resolve drops
        for a, b, r in pairs:
            d = choose_drop(a, b)
            if d is not None:
                to_drop.add(d)

        # Always ignore-drop FID if present
        self.df.drop(columns=["FID"], inplace=True, errors="ignore")

        if to_drop:
            self.df.drop(columns=list(to_drop), inplace=True, errors="ignore")
            print(f"[CORR] Dropped highly correlated columns (|r|>{threshold}): {sorted(list(to_drop))}")
        else:
            print(f"[INFO] No columns exceeded correlation threshold |r|>{threshold}.")

        return self

    # ------------- One-shot pipeline (UPDATED ORDER) -------------

    def apply_pipeline(
        self,
        year_col: str = "Building Construction Year",
        year_out: str = "Year_Normalized",
        add_year_z: bool = True,
        skew_threshold: float = 1.0,
        skew_exclude: Optional[Set[str]] = None,
        corr_threshold: float = 0.8,
        corr_exclude: Optional[Set[str]] = None,
    ):
        """
        Desired behavior:
          1) normalize years to [0 .. max-min] into `year_out`
          2) apply skew transforms to `year_out` (NOT to `year_col`)
          3) compute z-score for `year_out` AFTER skew handling
          4) drop correlated (protect z by default)
        """
        skew_exclude = set() if skew_exclude is None else set(skew_exclude)
        corr_exclude = set() if corr_exclude is None else set(corr_exclude)

        # 1) Normalize year (NO z-score here; we add it after skew handling)
        self.normalize_construction_year(year_col, out_col=year_out, add_zscore=False)

        # 2) Skew handling:
        #    - NEVER touch the original `year_col`
        #    - DO allow transforms on `year_out`
        #    - Respect any user-provided exclusions
        skew_exclude = skew_exclude.union({year_col})
        self.handle_skewness_auto(threshold=skew_threshold, exclude=skew_exclude)

        # 3) Add z-score for the (possibly transformed) `year_out`
        if add_year_z and (year_out in self.df.columns):
            self.add_zscore(year_out, z_col=year_out + "_z")

        # 4) Correlation pruning:
        #    - Protect the z-scored year feature by default
        corr_exclude = corr_exclude.union({year_out + "_z"})
        self.drop_highly_correlated(threshold=corr_threshold, exclude=corr_exclude)

        return self
