# src/models/ocsvm_baseline.py
"""
One-Class SVM baseline for electricity fraud detection.

- Consumes: data/processed/processed_data.csv
  (produced by your preprocessing + FeatureEngineering pipeline).
- Steps:
  * select numeric features (drop obvious IDs if present)
  * scale (RobustScaler or StandardScaler)
  * optional PCA (keep X% of variance)
  * fit One-Class SVM
  * compute anomaly scores + percentile-based labels
  * evaluate unsupervised metrics: Silhouette, Dunn, Davies–Bouldin
  * optionally save scores + meta JSON

This file is intentionally independent of the fused ensemble
(src/models/train_models.py) to keep the baseline conceptually clean.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.decomposition import PCA
from sklearn.svm import OneClassSVM
from sklearn.metrics import silhouette_score, davies_bouldin_score
from scipy.spatial.distance import pdist, squareform


# ---------------- Metrics & utilities ----------------

def dunn_index(X: np.ndarray, labels: np.ndarray) -> float:
    """
    Dunn index: min inter-cluster distance / max intra-cluster distance (higher is better).
    Defined on the binary partition {normal, anomaly} induced by the threshold.
    """
    labels = np.asarray(labels)
    uniq = np.unique(labels)
    if len(uniq) < 2:
        return np.nan
    D = squareform(pdist(X))
    intra, inter = [], []
    for i, li in enumerate(uniq):
        idx_i = np.where(labels == li)[0]
        if len(idx_i) < 2:
            intra.append(0.0)
        else:
            intra.append(np.max(D[np.ix_(idx_i, idx_i)]))
        for lj in uniq[i + 1:]:
            idx_j = np.where(labels == lj)[0]
            if len(idx_j) == 0 or len(idx_i) == 0:
                continue
            inter.append(np.min(D[np.ix_(idx_i, idx_j)]))
    if not intra or not inter:
        return np.nan
    max_intra = float(np.max(intra))
    min_inter = float(np.min(inter))
    if max_intra == 0:
        return np.nan
    return float(min_inter / max_intra)


def safe_silhouette(X: np.ndarray, labels: np.ndarray) -> float:
    try:
        labs = np.asarray(labels)
        uniq, counts = np.unique(labs, return_counts=True)
        if len(uniq) < 2 or np.any(counts < 2):
            return np.nan
        return float(silhouette_score(X, labs))
    except Exception:
        return np.nan


def safe_dbi(X: np.ndarray, labels: np.ndarray) -> float:
    try:
        labs = np.asarray(labels)
        if len(np.unique(labs)) < 2:
            return np.nan
        return float(davies_bouldin_score(X, labs))
    except Exception:
        return np.nan


def evaluate_partition(X: np.ndarray, labels: np.ndarray) -> dict:
    return {
        "silhouette": safe_silhouette(X, labels),
        "dunn": dunn_index(X, labels),
        "dbi": safe_dbi(X, labels),
    }


def percentile_label(scores: np.ndarray, contamination: float) -> Tuple[np.ndarray, float]:
    """
    Convert continuous anomaly scores → binary labels using a top-p% rule.
    contamination = expected anomaly fraction (e.g. 0.03 → top 3% flagged).
    """
    thr = np.percentile(scores, 100.0 * (1.0 - contamination))
    labels = (scores >= thr).astype(int)
    return labels, float(thr)


# ---------------- Core OCSVM baseline pipeline ----------------

def _select_numeric_features(df: pd.DataFrame) -> Tuple[np.ndarray, list]:
    """
    Select numeric columns for modeling, dropping obvious identifiers if present.
    You can adjust drop_cols if you add more ID-like fields later.
    """
    drop_cols = {"fid", "FID"}  # keep lat/long; they carry spatial info
    num_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if c not in drop_cols
    ]
    if len(num_cols) < 2:
        raise ValueError(f"Not enough numeric columns after dropping {drop_cols}. Found: {num_cols}")
    X = df[num_cols].to_numpy()
    return X, num_cols


def run_ocsvm_baseline(
    input_csv: str,
    output_csv: str,
    *,
    contamination: float = 0.03,
    nu: float = 0.05,
    kernel: str = "rbf",
    gamma: str | float = "scale",
    degree: int = 3,
    coef0: float = 0.0,
    use_pca: bool = True,
    pca_var: float = 0.98,
    scaler_type: str = "robust",  # "robust" or "standard"
    seed: int = 42,
    quiet: bool = False,
    skip_save: bool = False,
) -> Tuple[float, float, float]:
    """
    Fit One-Class SVM on processed_data.csv and compute unsupervised metrics.

    Returns:
        (silhouette, dunn, dbi)
    """
    df = pd.read_csv(input_csv)
    if not quiet:
        print(f"[OCSVM] Loaded: {df.shape} from {input_csv}")

    # ----- Features -----
    X_raw, feat_cols = _select_numeric_features(df)

    # ----- Scaling -----
    if scaler_type.lower() == "standard":
        scaler = StandardScaler()
    else:
        scaler = RobustScaler()

    X_scaled = scaler.fit_transform(X_raw)

    # ----- PCA (optional) -----
    pca_model = None
    X_model = X_scaled
    if use_pca:
        pca_model = PCA(n_components=pca_var, svd_solver="full", random_state=seed)
        X_model = pca_model.fit_transform(X_scaled)
        if not quiet:
            print(f"[OCSVM] PCA: {X_scaled.shape[1]} → {X_model.shape[1]} "
                  f"(keep {pca_var:.2%} variance)")

    # ----- One-Class SVM -----
    nu_clipped = float(np.clip(nu, 1e-3, 0.49))
    oc = OneClassSVM(
        kernel=kernel,
        nu=nu_clipped,
        gamma=gamma,
        degree=degree,
        coef0=coef0,
    )
    oc.fit(X_model)

    # Larger scores = more anomalous
    scores = (-oc.decision_function(X_model)).ravel().astype(float)

    # ----- Threshold & metrics -----
    labels, thr = percentile_label(scores, contamination=contamination)
    metrics = evaluate_partition(X_model, labels)

    if not quiet:
        print(f"[OCSVM] thr={thr:.6f}, contamination={contamination:.3f}, "
              f"flags={labels.mean():.3f}")
        print(f"[OCSVM] Sil={metrics['silhouette']:.3f} | "
              f"Dunn={metrics['dunn']:.3f} | DBI={metrics['dbi']:.3f}")

    # ----- Save outputs -----
    if not skip_save:
        out_df = df.copy()
        out_df["ocsvm_score"] = scores
        out_df["is_anomaly_ocsvm"] = labels

        out_path = Path(output_csv)
        os.makedirs(out_path.parent, exist_ok=True)
        out_df.sort_values("ocsvm_score", ascending=False).to_csv(out_path, index=False)

        meta = {
            "model": "one_class_svm_baseline",
            "input_csv": input_csv,
            "output_csv": str(out_path),
            "n_samples": int(X_model.shape[0]),
            "n_features": int(X_model.shape[1]),
            "contamination": float(contamination),
            "decision_threshold": float(thr),
            "hyperparams": {
                "nu": float(nu_clipped),
                "kernel": kernel,
                "gamma": gamma,
                "degree": int(degree),
                "coef0": float(coef0),
                "use_pca": bool(use_pca),
                "pca_var": float(pca_var),
                "scaler": scaler_type,
                "seed": int(seed),
            },
            "metrics": {
                "silhouette": float(metrics["silhouette"]) if metrics["silhouette"] == metrics["silhouette"] else None,
                "dunn": float(metrics["dunn"]) if metrics["dunn"] == metrics["dunn"] else None,
                "dbi": float(metrics["dbi"]) if metrics["dbi"] == metrics["dbi"] else None,
            },
        }
        meta_path = out_path.with_name(out_path.stem + "_meta.json")

        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        if not quiet:
            print(f"[OCSVM] Saved scores → {out_path}")
            print(f"[OCSVM] Saved meta   → {meta_path}")

    return metrics["silhouette"], metrics["dunn"], metrics["dbi"]


# ---------------- CLI wrapper ----------------

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="One-Class SVM baseline on processed_data.csv")
    ap.add_argument("--input", default="data/processed/processed_data.csv")
    ap.add_argument("--output", default="data/processed/ocsvm_baseline_scores.csv")

    ap.add_argument("--contamination", type=float, default=0.03)
    ap.add_argument("--nu", type=float, default=0.045)
    ap.add_argument("--kernel", type=str, default="sigmoid")  # you can change default to your best
    ap.add_argument("--gamma", type=str, default="scale")
    ap.add_argument("--degree", type=int, default=3)
    ap.add_argument("--coef0", type=float, default=1.0)

    ap.add_argument("--use_pca", type=int, default=1)
    ap.add_argument("--pca_var", type=float, default=0.98)
    ap.add_argument("--scaler", type=str, default="robust")  # "robust" or "standard"
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--quiet", type=int, default=0)
    ap.add_argument("--skip_save", type=int, default=0)

    args = ap.parse_args()

    sil, dunn, dbi = run_ocsvm_baseline(
        input_csv=args.input,
        output_csv=args.output,
        contamination=args.contamination,
        nu=args.nu,
        kernel=args.kernel,
        gamma=args.gamma,
        degree=args.degree,
        coef0=args.coef0,
        use_pca=bool(args.use_pca),
        pca_var=args.pca_var,
        scaler_type=args.scaler,
        seed=args.seed,
        quiet=bool(args.quiet),
        skip_save=bool(args.skip_save),
    )
    if not args.quiet:
        print(f"[OCSVM] Final metrics → Sil={sil:.3f}, Dunn={dunn:.3f}, DBI={dbi:.3f}")
