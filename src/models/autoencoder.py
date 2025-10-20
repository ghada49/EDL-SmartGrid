# models/autoencoder.py
# -*- coding: utf-8 -*-

"""
Autoencoder anomaly detection for electricity usage (fraud) — refactored for notebook use.

Public API:
    run_autoencoder(
        data_path: str,
        features: list[str],
        assume_standardized: bool = True,
        yeo_cols: list[str] | None = None,
        quantile: float = 0.95,
        topN: int = 100,
        outdir: str | None = None,
        seed: int = 0,
        return_objects: bool = False,
    ) -> dict

Returns a dict with file paths, best params, and (optionally) in-memory results.
"""

from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Silence TF logs (optional)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, PowerTransformer
from sklearn.decomposition import PCA

import tensorflow as tf
from tensorflow.keras import layers, regularizers, Model, Input


# ----------------------------
# Small utilities
# ----------------------------
def _ts() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _save_fig(path: str) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


# ----------------------------
# Data helpers
# ----------------------------
def load_data(csv_path: str, features: Optional[List[str]] = None) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    df = pd.read_csv(csv_path)
    if features is None:
        features = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    X = df[features].copy()
    return df, X, features


def maybe_transform_and_scale(
    X: pd.DataFrame,
    assume_standardized: bool = True,
    yeo_johnson_cols: Optional[List[str]] = None,
) -> Tuple[np.ndarray, Optional[PowerTransformer], Optional[StandardScaler]]:
    """
    If assume_standardized=True: return X.values as-is (you already scaled upstream).
    Else: optional Yeo–Johnson on selected columns, then StandardScaler across all.
    """
    if assume_standardized:
        return X.values, None, None

    Xp = X.copy()
    pt = None
    if yeo_johnson_cols:
        pt = PowerTransformer(method="yeo-johnson")
        Xp[yeo_johnson_cols] = pt.fit_transform(Xp[yeo_johnson_cols])

    scaler = StandardScaler()
    Xs = scaler.fit_transform(Xp.values)
    return Xs, pt, scaler


# ----------------------------
# Autoencoder model
# ----------------------------
def build_autoencoder(
    n_features: int,
    encoder_layers: List[int],
    bottleneck_dim: int,
    l2_reg: float = 1e-4,
    dropout: float = 0.0,
    activation: str = "relu",
) -> tf.keras.Model:
    inputs = Input(shape=(n_features,), name="input")
    x = inputs
    for i, units in enumerate(encoder_layers):
        x = layers.Dense(
            units,
            activation=activation,
            kernel_regularizer=regularizers.l2(l2_reg),
            name=f"enc_{i}",
        )(x)
        if dropout > 0:
            x = layers.Dropout(dropout, name=f"enc_do_{i}")(x)

    bottleneck = layers.Dense(
        bottleneck_dim,
        activation=activation,
        kernel_regularizer=regularizers.l2(l2_reg),
        name="bottleneck",
    )(x)

    y = bottleneck
    for i, units in enumerate(reversed(encoder_layers)):
        y = layers.Dense(
            units,
            activation=activation,
            kernel_regularizer=regularizers.l2(l2_reg),
            name=f"dec_{i}",
        )(y)
        if dropout > 0:
            y = layers.Dropout(dropout, name=f"dec_do_{i}")(y)

    outputs = layers.Dense(n_features, activation="linear", name="recon")(y)

    model = Model(inputs=inputs, outputs=outputs, name="Autoencoder")
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="mse")
    return model


def train_one(
    X_train: np.ndarray,
    X_val: np.ndarray,
    params: Dict[str, Any],
    max_epochs: int = 300,
    patience: int = 20,
) -> Tuple[tf.keras.Model, tf.keras.callbacks.History, float]:
    model = build_autoencoder(
        n_features=X_train.shape[1],
        encoder_layers=params["encoder_layers"],
        bottleneck_dim=params["bottleneck_dim"],
        l2_reg=params["l2_reg"],
        dropout=params["dropout"],
        activation=params.get("activation", "relu"),
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", mode="min", patience=patience, restore_best_weights=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=max(5, patience // 2), min_lr=1e-5, verbose=0
        ),
    ]

    hist = model.fit(
        X_train, X_train,
        validation_data=(X_val, X_val),
        epochs=max_epochs,
        batch_size=params["batch_size"],
        shuffle=True,
        verbose=0,
        callbacks=callbacks,
    )
    best_val = float(min(hist.history["val_loss"]))
    return model, hist, best_val


# ----------------------------
# Evaluation & plotting
# ----------------------------
def reconstruction_errors(model: tf.keras.Model, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    recon = model.predict(X, verbose=0)
    mse = np.mean(np.square(X - recon), axis=1)
    return mse, recon


def plot_history(history: tf.keras.callbacks.History, outpath: str) -> None:
    plt.figure(figsize=(6, 4))
    plt.plot(history.history["loss"], label="train")
    plt.plot(history.history["val_loss"], label="val")
    plt.xlabel("Epoch"); plt.ylabel("MSE loss"); plt.title("Training history")
    plt.legend()
    _save_fig(outpath)


def plot_error_hist(errors: np.ndarray, threshold: float, outpath: str) -> None:
    plt.figure(figsize=(6, 4))
    plt.hist(errors, bins=50)
    plt.axvline(threshold, color="red", linestyle="--", label=f"threshold={threshold:.4g}")
    plt.xlabel("Reconstruction error (MSE)"); plt.ylabel("Count")
    plt.title("Autoencoder reconstruction errors")
    plt.legend()
    _save_fig(outpath)


def plot_pca_scatter(X: np.ndarray, errors: np.ndarray, outpath: str) -> None:
    if X.shape[1] < 2:
        return
    pca = PCA(n_components=2, random_state=0)
    X2 = pca.fit_transform(X)
    plt.figure(figsize=(6, 5))
    sc = plt.scatter(X2[:, 0], X2[:, 1], c=errors, s=18)
    plt.colorbar(sc, label="recon error")
    plt.title("PCA projection colored by reconstruction error")
    plt.xlabel("PC1"); plt.ylabel("PC2")
    _save_fig(outpath)


# ----------------------------
# Grid search
# ----------------------------
def grid_search(X: np.ndarray, seed: int = 0):
    np.random.seed(seed)
    tf.random.set_seed(seed)

    param_grid = [
        dict(encoder_layers=[8],    bottleneck_dim=3, l2_reg=1e-4, dropout=0.00, batch_size=64),
        dict(encoder_layers=[12],   bottleneck_dim=3, l2_reg=1e-4, dropout=0.00, batch_size=64),
        dict(encoder_layers=[12,6], bottleneck_dim=3, l2_reg=1e-4, dropout=0.00, batch_size=64),
        dict(encoder_layers=[12,6], bottleneck_dim=4, l2_reg=1e-4, dropout=0.00, batch_size=64),
        dict(encoder_layers=[12,6], bottleneck_dim=3, l2_reg=5e-4, dropout=0.10, batch_size=64),
        dict(encoder_layers=[16,8], bottleneck_dim=4, l2_reg=1e-4, dropout=0.10, batch_size=64),
    ]

    X_train, X_val = train_test_split(X, test_size=0.15, random_state=seed, shuffle=True)

    records, trained = [], []
    for i, params in enumerate(param_grid):
        model, hist, best_val = train_one(X_train, X_val, params, max_epochs=300, patience=20)
        records.append(dict(idx=i, best_val_loss=best_val, **params))
        trained.append((model, hist, params))

    results_df = pd.DataFrame(records).sort_values("best_val_loss", ascending=True).reset_index(drop=True)
    best_idx = int(results_df.loc[0, "idx"])
    best_model, best_hist, best_params = trained[best_idx][0], trained[best_idx][1], trained[best_idx][2]
    return results_df, best_model, best_hist, best_params


# ----------------------------
# Public API: run_autoencoder
# ----------------------------
def run_autoencoder(
    data_path: str,
    features: List[str],
    assume_standardized: bool = True,
    yeo_cols: Optional[List[str]] = None,
    quantile: float = 0.95,
    topN: int = 100,
    outdir: Optional[str] = None,
    seed: int = 0,
    return_objects: bool = False,
) -> Dict[str, Any]:
    """
    High-level pipeline for notebooks or scripts.

    Returns a dict with:
        - outdir, paths to CSVs/PNGs/Keras model
        - best_params, best_val_loss
        - counts (n_rows, n_anomalies)
        - (optional) objects: results_df, df_out, model
    """
    if outdir is None:
        outdir = f"ae_out_{_ts()}"
    _ensure_dir(outdir)

    # 1) Load
    df, Xdf, feats = load_data(data_path, features=features)
    with open(os.path.join(outdir, "features.json"), "w") as f:
        json.dump({"features": feats}, f, indent=2)

    # 2) Transform/scale if needed
    X, pt, scaler = maybe_transform_and_scale(Xdf, assume_standardized=assume_standardized, yeo_johnson_cols=yeo_cols)

    # 3) Grid search
    results_df, model, history, best_params = grid_search(X, seed=seed)
    results_path = os.path.join(outdir, "ae_grid_results.csv")
    results_df.to_csv(results_path, index=False)

    # 4) Train diagnostics
    plot_history(history, os.path.join(outdir, "train_history.png"))

    # 5) Reconstruction errors on ALL data
    errors, _ = reconstruction_errors(model, X)
    df_out = df.copy()
    df_out["recon_error"] = errors

    # 6) Thresholding
    thr = float(np.quantile(errors, quantile))
    df_out["anomaly"] = (df_out["recon_error"] > thr).astype(int)

    # 7) Save reports
    all_ranked_path = os.path.join(outdir, "anomaly_ranked_all.csv")
    top_path = os.path.join(outdir, f"top_{topN}_anomalies.csv")
    df_out.sort_values("recon_error", ascending=False).to_csv(all_ranked_path, index=False)
    df_out[df_out["anomaly"] == 1].sort_values("recon_error", ascending=False).head(topN).to_csv(top_path, index=False)

    # 8) Plots
    plot_error_hist(errors, thr, os.path.join(outdir, "error_hist.png"))
    plot_pca_scatter(X, errors, os.path.join(outdir, "pca_error_scatter.png"))

    # 9) Save model + params
    model_path = os.path.join(outdir, "best_autoencoder.keras")
    model.save(model_path)
    with open(os.path.join(outdir, "best_params.json"), "w") as f:
        json.dump(best_params, f, indent=2)

    # 10) Summary dictionary
    summary = {
        "outdir": outdir,
        "paths": {
            "grid_results_csv": results_path,
            "all_ranked_csv": all_ranked_path,
            "top_anomalies_csv": top_path,
            "train_history_png": os.path.join(outdir, "train_history.png"),
            "error_hist_png": os.path.join(outdir, "error_hist.png"),
            "pca_error_scatter_png": os.path.join(outdir, "pca_error_scatter.png"),
            "keras_model": model_path,
            "features_json": os.path.join(outdir, "features.json"),
            "best_params_json": os.path.join(outdir, "best_params.json"),
        },
        "best_params": best_params,
        "best_val_loss": float(results_df.loc[0, "best_val_loss"]),
        "counts": {
            "n_rows": int(len(df_out)),
            "n_anomalies": int((df_out["anomaly"] == 1).sum()),
        },
        "threshold": {"quantile": float(quantile), "value": float(thr)},
    }

    if return_objects:
        summary["objects"] = {
            "results_df": results_df,
            "df_out": df_out,
            "model": model,
        }

    return summary


# ----------------------------
# CLI support (optional)
# ----------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autoencoder anomaly detection (grid + reports).")
    parser.add_argument("--data", type=str, default="processed_data.csv")
    parser.add_argument("--features", type=str, nargs="*", required=False)
    parser.add_argument("--assume_standardized", action="store_true", default=True)
    parser.add_argument("--yeo_cols", type=str, nargs="*", default=None)
    parser.add_argument("--quantile", type=float, default=0.95)
    parser.add_argument("--topN", type=int, default=100)
    parser.add_argument("--outdir", type=str, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--return_objects", action="store_true", default=False)

    args = parser.parse_args()

    feats = args.features
    if feats is None:
        # If not passed, auto-pick numeric columns inside load_data()
        pass

    result = run_autoencoder(
        data_path=args.data,
        features=feats,
        assume_standardized=args.assume_standardized,
        yeo_cols=args.yeo_cols,
        quantile=args.quantile,
        topN=args.topN,
        outdir=args.outdir,
        seed=args.seed,
        return_objects=args.return_objects,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "objects"}, indent=2))


if __name__ == "__main__":
    main()
