# tests/test_preprocessing_alignment.py

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import joblib

# ---------------- Path setup ----------------

REPO_ROOT = Path(__file__).resolve().parent.parent

SRC_DIR = REPO_ROOT / "src"
BACKEND_DIR = REPO_ROOT / "backend"

for p in [REPO_ROOT, SRC_DIR, BACKEND_DIR]:
    if str(p) not in sys.path:
        sys.path.append(str(p))

# ---------------- Imports from your repo ----------------

from src.data_loading.load_data import DataLoader
from src.data_loading.feature_engineering import FeatureEngineering
from src.models.train_models import build_residual, winsorize_and_ratios

from tests.feature_engineering_test import _canonicalize_for_model

from backend.ml.shared_features import preprocess_like_training
from backend.ml.inference import preprocess_for_inference
from backend.ml.registry import get_current_model_card, REPO_ROOT as BACKEND_REPO_ROOT


# ---------------- Helpers ----------------

def _load_raw_df() -> pd.DataFrame:
    """
    Load the same raw data used for training:
    - Prefer data/latest_ingested.csv (ingested dataset)
    - Fallback to data/raw/data.xlsx
    """
    latest = REPO_ROOT / "data" / "latest_ingested.csv"
    raw_xlsx = REPO_ROOT / "data" / "raw" / "data.xlsx"

    if latest.exists():
        path = latest
    elif raw_xlsx.exists():
        path = raw_xlsx
    else:
        pytest.skip(
            "No raw input found (expected data/latest_ingested.csv or data/raw/data.xlsx)."
        )

    loader = DataLoader(str(path))
    df = loader.load_data()
    assert not df.empty, "Loaded raw dataframe is empty"
    return df


def _training_style_full_preproc(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Rebuild the *canonical* training preprocessing pipeline inline,
    matching what you do in:
      - tests/feature_engineering_test.main
      - src/models/train_models.run_pipeline

    Steps:
    1) Canonicalize names for the anomaly model.
    2) FeatureEngineering.apply_pipeline with the same args as in tests.main.
    3) Residuals (HuberRegressor) with x_cols / y_col identical to training.
    4) Winsorization + ratio features.
    """
    df = df_raw.copy()

    # 1) Canonical names (same helper used everywhere)
    df = _canonicalize_for_model(df)

    # 2) Feature engineering (exactly as in tests/feature_engineering_test.main)
    fe = FeatureEngineering(df)
    fe.apply_pipeline(
        year_col="build_year",
        year_out="year_norm",
        add_year_z=True,
        skew_threshold=1.0,
        skew_exclude={"fid", "lat", "long", "Latitude", "Longitude"},
        corr_threshold=0.85,
        corr_exclude={"fid", "Latitude", "Longitude", "Total Electricity Consumption (kwH)"},
    )
    df_fe = fe.df

    # 3) Residuals (same as run_pipeline)
    y_col = "Total Electricity Consumption (kwH)"
    x_cols = ["Area in m^2", "nb_appart", "nb_floor", "year_norm_z"]
    missing = [c for c in x_cols + [y_col] if c not in df_fe.columns]
    if missing:
        raise RuntimeError(f"Training-style FE is missing required columns: {missing}")

    df_resid, _, _ = build_residual(
        df_fe,
        x_cols=x_cols,
        y_col=y_col,
        seed=42,
    )


    # 4) Winsorization + ratios
    df_full = winsorize_and_ratios(df_resid)

    return df_full


# ---------------- Tests ----------------

def test_shared_preprocess_matches_training_style():
    """
    Validate that backend/ml/shared_features.preprocess_like_training
    produces the *same* engineered features as the canonical training
    pipeline (up to correlation pruning).

    We enable drop_corr=True so that shared_features drops highly
    correlated columns like training.
    """
    df_raw = _load_raw_df()

    # Use a subset to keep test light
    df_raw_sample = df_raw.sample(n=min(200, len(df_raw)), random_state=123)

    df_train = _training_style_full_preproc(df_raw_sample)
    df_shared = preprocess_like_training(
        df_raw_sample,
        cv_folds=5,
        seed=42,
        drop_corr=True,
        residual_art=None,
    )

    # Columns may differ slightly if correlation pruning logic diverges,
    # but there should be a strong overlap.
    common_cols = sorted(set(df_train.columns) & set(df_shared.columns))
    assert common_cols, "No overlapping columns between training-style and shared FE"

    # Compare numeric columns; we expect them to be almost identical.
    numeric_common = [
        c for c in common_cols
        if pd.api.types.is_numeric_dtype(df_train[c]) and pd.api.types.is_numeric_dtype(df_shared[c])
    ]
    assert numeric_common, "No overlapping numeric columns to compare"

    for col in numeric_common:
        a = df_train[col].to_numpy()
        b = df_shared[col].to_numpy()
        # Allow tiny floating differences
        assert np.allclose(a, b, atol=1e-6, equal_nan=True), f"Column '{col}' differs between training FE and shared FE"


def test_model_card_feature_columns_match_scaler():
    """
    Ensure the active model card's feature_columns are consistent with
    the saved scaler artifact.
    """
    card = get_current_model_card()
    assert card is not None, "No active model card found in registry; run training first."

    meta = card.get("meta") or {}
    feat_cols = meta.get("feature_columns")
    assert feat_cols, "Model card meta does not define 'feature_columns'."

    files = card.get("files") or {}
    scaler_rel = files.get("scaler")
    assert scaler_rel, "Model card files['scaler'] is missing."

    scaler_path = (BACKEND_REPO_ROOT / scaler_rel).resolve()
    assert scaler_path.exists(), f"Scaler artifact not found at: {scaler_path}"

    scaler = joblib.load(scaler_path)
    n_scaler = getattr(scaler, "n_features_in_", None)
    assert n_scaler is not None, "Scaler does not expose n_features_in_."

    assert n_scaler == len(feat_cols), (
        f"Scaler expects {n_scaler} features, but model card lists "
        f"{len(feat_cols)} feature_columns."
    )


def test_inference_preprocessing_uses_same_features_and_latent_dim():
    """
    Smoke test: preprocess_for_inference should:
      - Use the same feature_columns as the active model card.
      - Produce a latent representation Z with consistent dimensionality
        (matching pca_components when PCA is enabled).
    """
    card = get_current_model_card()
    if card is None:
        pytest.skip("No active model card found; run training first.")

    meta = card.get("meta") or {}
    feat_cols = meta.get("feature_columns")
    assert feat_cols, "Model meta has no 'feature_columns'; cannot validate inference alignment."

    use_pca = bool(meta.get("use_pca", False))
    pca_components = meta.get("pca_components")

    df_raw = _load_raw_df()
    df_raw_sample = df_raw.sample(n=min(200, len(df_raw)), random_state=321)

    df_proc, Z = preprocess_for_inference(df_raw_sample)

    # 1) All feature_columns used at training must be present in df_proc
    missing = [c for c in feat_cols if c not in df_proc.columns]
    assert not missing, f"Inference preprocessing missing feature columns: {missing}"

    # 2) Ensure latent shape is consistent
    assert Z.shape[0] == df_proc.shape[0], "Latent rows must match number of samples."

    if use_pca and pca_components is not None:
        # With PCA we expect latent dimension to match pca_components
        assert Z.shape[1] == int(
            pca_components
        ), f"Z.shape[1]={Z.shape[1]} but meta.pca_components={pca_components}"
    # If PCA is off, we don't enforce a specific Z.shape[1] here, since it
    # depends on the scaler input dimension only.


