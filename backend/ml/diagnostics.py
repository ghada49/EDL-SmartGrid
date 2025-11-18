# backend/ml/diagnostics.py
"""
Generate static PNG diagnostics for the current anomaly model.

Inputs:
  - anomaly_scores.csv
  - its _meta.json and _stability.json (from run_anomaly_pipeline)
Outputs (overwritten each training run):
  - data/plots/current_pca_fused.png
  - data/plots/current_fused_hist.png
  - data/plots/current_method_metrics.png
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import RobustScaler
from sklearn.decomposition import PCA

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
PLOTS_DIR = REPO_ROOT / "data" / "plots"


def _safe_close(fig):
    """Close a matplotlib figure to avoid memory leaks."""
    try:
        plt.close(fig)
    except Exception:
        pass


def _pick_label_column(df: pd.DataFrame) -> str:
    """
    Try to pick the best anomaly label column.
    Prefer is_anomaly_fused, fall back to is_anomaly_if, else raise.
    """
    for col in ["is_anomaly_fused", "is_anomaly_if"]:
        if col in df.columns:
            return col
    raise ValueError("No suitable anomaly label column found (expected is_anomaly_fused or is_anomaly_if).")


def generate_pca_scatter(scores_csv: Path) -> None:
    """
    PCA(2D) scatter: red anomalies vs blue normals.
    Saved to data/plots/current_pca_fused.png
    """
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(scores_csv)

    label_col = _pick_label_column(df)
    labels = df[label_col].astype(int).to_numpy()

    # Build numeric matrix, dropping obvious non-feature columns
    drop_cols = {
        "fid", "FID", "lat", "long",
        "is_anomaly_if", "is_anomaly_lof", "is_anomaly_ae",
        "is_anomaly_ppca_mah", "is_anomaly_ocsvm",
        "is_anomaly_copula", "is_anomaly_fused",
    }
    num_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if c not in drop_cols
    ]
    if len(num_cols) < 2:
        print("[DIAG] Not enough numeric columns for PCA scatter; skipping.")
        return

    X = df[num_cols].to_numpy()
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    pca = PCA(n_components=2, random_state=42)
    X_2d = pca.fit_transform(X_scaled)

    fig, ax = plt.subplots(figsize=(7, 6))
    # 0 = normal (blue), 1 = anomaly (red)
    normal_mask = (labels == 0)
    anom_mask = (labels == 1)

    ax.scatter(
        X_2d[normal_mask, 0],
        X_2d[normal_mask, 1],
        s=20,
        alpha=0.7,
        edgecolor="k",
        linewidths=0.3,
        label="Normal",
    )
    ax.scatter(
        X_2d[anom_mask, 0],
        X_2d[anom_mask, 1],
        s=24,
        alpha=0.9,
        edgecolor="k",
        linewidths=0.3,
        label="Anomaly",
    )
    ax.set_title("PCA projection (red = anomaly, blue = normal)")
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.legend(loc="best")

    out_path = PLOTS_DIR / "current_pca_fused.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    _safe_close(fig)
    print(f"[DIAG] Saved PCA scatter -> {out_path}")


def generate_fused_hist(scores_csv: Path, meta_path: Path) -> None:
    """
    Histogram of fused_rank with anomaly cutoff vertical line.
    Saved to data/plots/current_fused_hist.png
    """
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(scores_csv)
    if "fused_rank" not in df.columns:
        print("[DIAG] fused_rank column not found; skipping fused histogram.")
        return

    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
        thr_fused = meta.get("fused_threshold", None)
    except Exception:
        meta = {}
        thr_fused = None

    fused = df["fused_rank"].to_numpy()

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(fused, bins=40, alpha=0.8, edgecolor="k")
    ax.set_title("Distribution of fused_rank")
    ax.set_xlabel("fused_rank (0–1)")
    ax.set_ylabel("Count")

    if thr_fused is not None:
        # Show threshold in terms of fused_rank
        ax.axvline(x=thr_fused, color="red", linestyle="--", label=f"cutoff ≈ {thr_fused:.3f}")
        ax.legend(loc="best")

    out_path = PLOTS_DIR / "current_fused_hist.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    _safe_close(fig)
    print(f"[DIAG] Saved fused_rank histogram -> {out_path}")


def generate_method_metrics(meta_path: Path) -> None:
    """
    Bar chart of Silhouette / Dunn / DBI per method (including FUSED),
    using meta['evals'].
    Saved to data/plots/current_method_metrics.png
    """
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    if not meta_path.exists():
        print(f"[DIAG] No meta JSON at {meta_path}; skipping metrics plot.")
        return

    with open(meta_path, "r") as f:
        meta = json.load(f)

    evals = meta.get("evals", {})
    if not evals:
        print("[DIAG] meta['evals'] is empty; skipping metrics plot.")
        return

    methods = sorted(evals.keys())
    silhouettes = []
    dunns = []
    dbis = []

    for m in methods:
        em = evals.get(m, {})
        silhouettes.append(em.get("silhouette"))
        dunns.append(em.get("dunn"))
        dbis.append(em.get("dbi"))

    x = np.arange(len(methods))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width, silhouettes, width, label="Silhouette")
    ax.bar(x, dunns, width, label="Dunn")
    ax.bar(x + width, dbis, width, label="DBI")

    ax.set_xticks(x)
    ax.set_xticklabels(methods, rotation=30)
    ax.set_ylabel("Metric value")
    ax.set_title("Unsupervised metrics per method (higher Sil/Dunn, lower DBI)")
    ax.legend()

    out_path = PLOTS_DIR / "current_method_metrics.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    _safe_close(fig)
    print(f"[DIAG] Saved metrics bar chart -> {out_path}")


def generate_all_diagnostics(scores_csv: Path, card: dict | None = None) -> None:
    """
    Orchestrate all diagnostics for the current model.
    """
    scores_csv = Path(scores_csv).resolve()
    base = scores_csv.with_suffix("")  # .../anomaly_scores
    meta_path = Path(str(base) + "_meta.json")

    print(f"[DIAG] Generating diagnostics from: {scores_csv}")
    generate_pca_scatter(scores_csv)
    generate_fused_hist(scores_csv, meta_path)
    generate_method_metrics(meta_path)

    # Optional: if you want versioned copies as well:
    if card is not None:
        try:
            version = card.get("version")
            if version is not None:
                PLOTS_DIR.mkdir(parents=True, exist_ok=True)
                for fname in [
                    "current_pca_fused.png",
                    "current_fused_hist.png",
                    "current_method_metrics.png",
                ]:
                    src = PLOTS_DIR / fname
                    if src.exists():
                        dst = PLOTS_DIR / f"v{version}_{fname}"
                        dst.write_bytes(src.read_bytes())
                        print(f"[DIAG] Also saved versioned copy -> {dst}")
        except Exception as e:
            print(f"[DIAG] Warning: failed to save versioned copies: {e}")
