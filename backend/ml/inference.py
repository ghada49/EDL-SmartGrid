# backend/ml/inference.py

from __future__ import annotations

from pathlib import Path
from typing import Tuple, List, Dict, Any

import json
import numpy as np
import pandas as pd
import joblib

from .shared_features import preprocess_like_training  # same FE as training
from .registry import get_current_model_card, REPO_ROOT


# ---------------- Exceptions ----------------

class InferenceError(RuntimeError):
    """Generic inference failure (wrapped in FastAPI as HTTP 400)."""


class NoActiveModelError(InferenceError):
    """Raised when there is no current model card in the registry."""


# ---------------- Artifact loader ----------------

def _load_active_artifacts():
    """
    Load scaler, optional PCA, and feature_columns from the active model card.

    Returns:
        scaler        : fitted sklearn scaler
        pca           : fitted PCA model or None
        feature_cols  : ordered list of feature column names
        card          : full model card dict
    """
    print(f"[INFER] Loading active model artifacts...")
    card = get_current_model_card()
    if card is None:
        raise NoActiveModelError("No active model found in registry. Train a model first.")

    print(f"[INFER] Model card keys: {list(card.keys())}")
    files = card.get("files", {})
    meta = card.get("meta", {}) or card.get("meta_json", {})
    print(f"[INFER] Model meta: {meta}")

    if not isinstance(files, dict):
        raise InferenceError("Model card is missing a valid 'files' dictionary.")

    scaler_rel = files.get("scaler")
    if not scaler_rel:
        raise InferenceError("Model card does not contain files['scaler'].")

    scaler_path = (REPO_ROOT / scaler_rel).resolve()
    if not scaler_path.exists():
        raise InferenceError(f"Scaler artifact not found at: {scaler_path}")

    print(f"[INFER] Loading scaler from: {scaler_path}")
    scaler = joblib.load(scaler_path)

    pca = None
    pca_rel = files.get("pca")
    if pca_rel:
        pca_path = (REPO_ROOT / pca_rel).resolve()
        if pca_path.exists():
            print(f"[INFER] Loading PCA from: {pca_path}")
            pca = joblib.load(pca_path)

    # Feature set that scaler/PCA were fit on
    feat_cols = meta.get("feature_columns") or []
    if not feat_cols:
        raise InferenceError("Active model meta does not define 'feature_columns'.")

    # Residual artifact (optional) - saved during training as _resid.joblib
    resid_art = None
    resid_rel = files.get("residual_model")
    if resid_rel:
        resid_path = (REPO_ROOT / resid_rel).resolve()
        if resid_path.exists():
            try:
                print(f"[INFER] Loading residual artifact from: {resid_path}")
                resid_art = joblib.load(resid_path)
            except Exception as e:
                print(f"[INFER] Warning: failed to load residual artifact: {e}")

    print(f"[INFER] Successfully loaded artifacts. feature_columns in model: {feat_cols}")
    return scaler, pca, feat_cols, card, resid_art


# ---------------- Scoring helpers (same math as training style) ----------------

def robust_mahalanobis_score(Z: np.ndarray) -> np.ndarray:
    """Mahalanobis^2 via robust covariance; higher = more anomalous."""
    from sklearn.covariance import MinCovDet

    Z = np.asarray(Z, float)
    if Z.shape[0] < Z.shape[1] + 2:
        mu = Z.mean(axis=0, keepdims=True)
        cov = np.cov(Z, rowvar=False) + 1e-6 * np.eye(Z.shape[1])
    else:
        mcd = MinCovDet().fit(Z)
        mu = mcd.location_.reshape(1, -1)
        cov = mcd.covariance_

    inv = np.linalg.pinv(cov)
    d2 = np.sum((Z - mu) @ inv * (Z - mu), axis=1)
    return d2.astype(float)


def gaussian_copula_score(Z: np.ndarray) -> np.ndarray:
    """
    Rank-transform each column → U(0,1) → Φ^{-1}(U) → Gaussian log-likelihood.
    Returns a negative log-likelihood–style score; higher = more anomalous.
    """
    from scipy.stats import norm

    X = np.asarray(Z, float)
    n, d = X.shape
    U = np.zeros_like(X, float)

    for j in range(d):
        r = np.argsort(np.argsort(X[:, j]))
        U[:, j] = (r + 0.5) / n

    Zg = norm.ppf(U.clip(1e-6, 1 - 1e-6))
    mu = Zg.mean(axis=0, keepdims=True)
    cov = np.cov(Zg, rowvar=False) + 1e-6 * np.eye(d)
    inv = np.linalg.pinv(cov)
    quad = np.sum((Zg - mu) @ inv * (Zg - mu), axis=1)
    logdet = np.log(np.linalg.det(cov) + 1e-12)
    nll = 0.5 * (quad + logdet)  # additive constants ignored
    return nll.astype(float)


def rank_0to1(arr: np.ndarray) -> np.ndarray:
    """Map raw scores to [0,1] by rank (0 = least anomalous, 1 = most)."""
    arr = np.asarray(arr, float)
    order = np.argsort(arr)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.linspace(0.0, 1.0, len(arr), endpoint=True)
    return ranks


# ---------------- Core preprocessing for inference ----------------

def preprocess_for_inference(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Full preprocessing for inference:

    1) Apply *exactly the same* preprocessing as training:
       - canonical renaming
       - FeatureEngineering.apply_pipeline(...)
       - residuals + winsorization + ratios
       (via backend/ml/shared_features.preprocess_like_training)

    2) Load scaler + PCA + feature_columns from active model card.

    3) Build X = df_proc[feature_columns], apply scaler (+ PCA).

    Returns:
        df_proc : fully engineered dataframe
        Z       : latent feature matrix used for scoring
    """
    # 1) Load artifacts (so we can reuse residual artifact if present)
    print(f"[INFER] Starting preprocess_for_inference with input shape {df_raw.shape}")
    scaler, pca, feat_cols, card, resid_art = _load_active_artifacts()
    print(f"[INFER] Loaded model card: {card.get('name', 'unknown')}")
    print(f"[INFER] Scaler type: {type(scaler).__name__}, PCA: {type(pca).__name__ if pca else 'None'}")
    print(f"[INFER] Expected feature_columns from model card: {feat_cols}")

    # 2) Same feature engineering as training (pass residual artifact when available)
    df_proc = preprocess_like_training(df_raw, residual_art=resid_art)
    print(f"[INFER] After preprocess_like_training: df_proc shape = {df_proc.shape}, columns = {sorted(df_proc.columns.tolist())}")

    # 3) Feature matrix with same columns as training
    missing = [c for c in feat_cols if c not in df_proc.columns]
    extra = [c for c in df_proc.columns if c not in feat_cols]
    
    print(f"[INFER] Column alignment check:")
    print(f"  - Missing (in feat_cols but not df_proc): {missing}")
    print(f"  - Extra (in df_proc but not feat_cols): {extra}")
    print(f"  - Match count: {len([c for c in feat_cols if c in df_proc.columns])}/{len(feat_cols)}")
    
    if missing:
        print(f"[INFER] ERROR: Missing required feature columns!")
        print(f"[INFER]   Expected: {sorted(feat_cols)}")
        print(f"[INFER]   Available: {sorted(df_proc.columns.tolist())}")
        raise InferenceError(f"Missing required feature columns for inference: {missing}")
    
    if extra:
        print(f"[INFER] Note: Extra columns will be ignored: {extra}")

    print(f"[INFER] Selecting {len(feat_cols)} feature columns for scaler")
    X = df_proc[feat_cols].to_numpy()
    print(f"[INFER] X shape before scaling: {X.shape}")
    X_scaled = scaler.transform(X)
    print(f"[INFER] X shape after scaling: {X_scaled.shape}")
    Z = pca.transform(X_scaled) if pca is not None else X_scaled
    print(f"[INFER] Z shape after PCA: {Z.shape}")

    return df_proc, Z


# ---------------- Public API: score a new dataset ----------------

def score_new_dataset(
    df_raw: pd.DataFrame,
    top_percent: float = 5.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Score a new dataframe with the active model:

    - Runs full preprocessing (identical to training).
    - Uses the same scaler/PCA and feature_columns as training.
    - Computes two unsupervised scores in latent space:
        * Mahalanobis (robust)
        * Gaussian copula
    - Fuses their ranks into fused_score.
    - Flags the top `top_percent` percent as anomalies.

    Returns:
        df_scored : full dataframe with added columns:
                    ['mah_score', 'copula_score', 'fused_score',
                     'is_anomaly', 'rank']
        df_top    : subset of df_scored with is_anomaly == 1 (ranked)
    """
    if not (0 < top_percent <= 100):
        raise InferenceError(f"top_percent must be in (0, 100], got {top_percent}.")

    # Preprocess + latent representation
    df_proc, Z = preprocess_for_inference(df_raw)

    # Scores
    mah = robust_mahalanobis_score(Z)
    cop = gaussian_copula_score(Z)

    # Rank-based fusion
    r_mah = rank_0to1(mah)
    r_cop = rank_0to1(cop)
    fused = 0.5 * r_mah + 0.5 * r_cop

    df_scored = df_proc.copy()
    df_scored["mah_score"] = mah
    df_scored["copula_score"] = cop
    df_scored["fused_score"] = fused

    # Rank descending
    df_scored = df_scored.sort_values("fused_score", ascending=False).reset_index(drop=True)
    df_scored["rank"] = df_scored.index + 1

    # Top-k
    n = len(df_scored)
    k = max(1, int(round(n * (top_percent / 100.0))))
    df_scored["is_anomaly"] = 0
    df_scored.loc[: k - 1, "is_anomaly"] = 1

    df_top = df_scored.head(k).copy()
    return df_scored, df_top
