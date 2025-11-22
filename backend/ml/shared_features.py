# backend/ml/shared_features.py

import pandas as pd

from src.data_loading.feature_engineering import FeatureEngineering
from tests.feature_engineering_test import _canonicalize_for_model
from src.models.train_models import build_residual, winsorize_and_ratios


def preprocess_like_training(
    df: pd.DataFrame,
    cv_folds: int = 5,
    seed: int = 42,
    drop_corr: bool = False,
    residual_art: dict | None = None,
) -> pd.DataFrame:
    # NOTE: accepts optional residual_art dict when running inference so we can
    # reuse the residual scaler+model fitted during training instead of refitting.
    """
    Apply *the same* preprocessing as training:
    - canonical rename (build_year, nb_appart, Total Electricity Consumption (kwH))
    - FeatureEngineering.apply_pipeline(...)
    - residuals + winsorization + ratios
    """
    df = df.copy()
    print(f"[PREPROC] Starting with df shape: {df.shape}")

    # 1) Canonical names
    df = _canonicalize_for_model(df)
    print(f"[PREPROC] After canonicalize: columns = {sorted(df.columns.tolist())}")

    # 2) FeatureEngineering (same args as tests/feature_engineering_test.main)
    fe = FeatureEngineering(df)
    fe.apply_pipeline(
        year_col="build_year",
        year_out="year_norm",
        add_year_z=True,
        skew_threshold=1.0,
        skew_exclude={"fid", "lat", "long"},
        corr_threshold=0.85 if drop_corr else None,
        corr_exclude={"fid", "lat", "long", "kwh", "Total Electricity Consumption (kwH)"},
    )
    df_fe = fe.df
    print(f"[PREPROC] After FeatureEngineering: columns = {sorted(df_fe.columns.tolist())}")

    # 3) Residuals (same x_cols / y_col as run_anomaly_pipeline)
    y_col = "Total Electricity Consumption (kwH)"
    x_cols = ["Area in m^2", "nb_appart", "nb_floor", "year_norm_z"]
    missing = [c for c in x_cols + [y_col] if c not in df_fe.columns]
    if missing:
        print(f"[PREPROC] ERROR: Missing columns for residuals: {missing}")
        raise ValueError(f"Missing required columns for residuals: {missing}")
    print(f"[PREPROC] Building residuals with x_cols: {x_cols}, y_col: {y_col}")
    # If a residual artifact is provided (from training), apply it instead of refitting
    # `residual_art` is expected to be a dict with keys: 'x_cols', 'scaler', 'model'
    if residual_art is not None:
        try:
            res_x_cols = residual_art.get("x_cols") or x_cols
            res_scaler = residual_art.get("scaler")
            res_model = residual_art.get("model")
            # validate columns
            missing_res = [c for c in res_x_cols + [y_col] if c not in df_fe.columns]
            if missing_res:
                print(f"[PREPROC] Residual artifact x_cols missing in df: {missing_res}")
                # fall back to refit
                df_resid, _, _ = build_residual(df_fe, x_cols=x_cols, y_col=y_col, seed=seed)
            else:
                X = df_fe[res_x_cols].copy()
                Xs = res_scaler.transform(X)
                y = df_fe[y_col].copy()
                y_pred = res_model.predict(Xs)
                df_fe["kwh_residual"] = y - y_pred
                df_fe["kwh_resid_abs"] = df_fe["kwh_residual"].abs()
                df_resid = df_fe
        except Exception as e:
            print(f"[PREPROC] ERROR applying residual artifact: {e}; falling back to fit")
            df_resid, _, _ = build_residual(df_fe, x_cols=x_cols, y_col=y_col, seed=seed)
    else:
        df_resid, _, _ = build_residual(df_fe, x_cols=x_cols, y_col=y_col, seed=seed)
    print(f"[PREPROC] After build_residual: columns = {sorted(df_resid.columns.tolist())}")

    # 4) Winsorization + ratios (same as training)
    df_full = winsorize_and_ratios(df_resid)
    print(f"[PREPROC] After winsorize_and_ratios: columns = {sorted(df_full.columns.tolist())}, shape = {df_full.shape}")

    return df_full
