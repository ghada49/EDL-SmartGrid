# backend/ml/plots.py
from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")          # important for headless servers
import matplotlib.pyplot as plt
import matplotlib.cm as cm

from sklearn.preprocessing import RobustScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_samples, silhouette_score, davies_bouldin_score
from scipy.spatial.distance import pdist, squareform


def _dunn_index(X, labels):
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
        for lj in uniq[i+1:]:
            idx_j = np.where(labels == lj)[0]
            if len(idx_j) == 0 or len(idx_i) == 0:
                continue
            inter.append(np.min(D[np.ix_(idx_i, idx_j)]))
    if not intra or not inter:
        return np.nan
    max_intra = np.max(intra)
    min_inter = np.min(inter)
    return np.nan if max_intra == 0 else float(min_inter / max_intra)


def generate_model_plots(scores_csv: Path, out_dir: Path) -> None:
    scores_csv = Path(scores_csv)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(scores_csv)

    # --- choose labels & features ---
    label_col = "is_anomaly_fused"
    if label_col not in df.columns:
        raise ValueError(f"{label_col} not found in {scores_csv}")

    labels = df[label_col].astype(int).to_numpy()
    if len(np.unique(labels)) < 2:
        raise ValueError("Need both classes (0 and 1) for plots.")

    drop_cols = {"fid", "FID", "lat", "long"}
    num_cols = [c for c in df.select_dtypes(include=[np.number]).columns
                if c not in drop_cols]
    X = df[num_cols].to_numpy()

    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    # ---------- PCA projection ----------
    pca2 = PCA(n_components=2, random_state=42)
    X_2d = pca2.fit_transform(X_scaled)

    colors = np.where(labels == 1, "#d62728", "#1f77b4")  # anomalies red
    plt.figure(figsize=(7, 6))
    plt.scatter(
        X_2d[:, 0], X_2d[:, 1],
        c=colors, s=20, alpha=0.8, edgecolor="k", linewidths=0.3
    )
    plt.title("2D PCA projection (red = anomaly, blue = normal)")
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.tight_layout()
    plt.savefig(out_dir / "pca_projection.png", dpi=120)
    plt.close()

    # ---------- Fused rank histogram ----------
    fused = df["fused_rank"].to_numpy()
    contamination = df["is_anomaly_fused"].mean()  # just for the cutoff
    thr = np.percentile(fused, 100 * (1 - contamination))

    plt.figure(figsize=(7, 5))
    plt.hist(fused, bins=30, edgecolor="k", alpha=0.8)
    plt.axvline(thr, color="red", linestyle="--", label=f"cutoff (≈ top {contamination*100:.1f}%)")
    plt.title("Distribution of fused anomaly scores")
    plt.xlabel("Fused rank")
    plt.ylabel("Count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "fused_rank_hist.png", dpi=120)
    plt.close()

    # ---------- Method metrics bar chart ----------
    # Expect meta JSON to already exist
    meta_path = scores_csv.with_suffix("").with_name(scores_csv.stem + "_meta.json")
    if meta_path.exists():
        import json
        with open(meta_path, "r") as f:
            meta = json.load(f)
        evals = meta.get("evals", {})
        methods = []
        sils, dunns, dbis = [], [], []
        for name, m in evals.items():
            methods.append(name)
            sils.append(m.get("silhouette"))
            dunns.append(m.get("dunn"))
            dbis.append(m.get("dbi"))

        x = np.arange(len(methods))
        width = 0.25

        fig, ax1 = plt.subplots(figsize=(9, 5))
        ax1.bar(x - width, sils, width, label="Silhouette")
        ax1.bar(x, dunns, width, label="Dunn")
        ax1.bar(x + width, dbis, width, label="DBI")

        ax1.set_xticks(x)
        ax1.set_xticklabels(methods, rotation=30)
        ax1.set_title("Unsupervised metrics per method (higher Silhouette/Dunn, lower DBI)")
        ax1.legend()
        plt.tight_layout()
        plt.savefig(out_dir / "method_metrics.png", dpi=120)
        plt.close()
