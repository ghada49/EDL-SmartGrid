# scripts/train_models.py
# End-to-end anomaly pipeline with residuals, winsorization, ratios, PCA, IF/LOF,
# optional AE/VAE, OCSVM, HDBSCAN, PPCA-Mahalanobis, Gaussian Copula, and GMM NLL.
# Evaluates with Silhouette, Dunn, Davies–Bouldin; adds Stability/Overfitting Audit.
# Saves ranked CSV + meta/stability JSON + persisted scaler/PCA.

from __future__ import annotations

import os
import json
from pathlib import Path

import argparse
import numpy as np
import pandas as pd

from scipy.stats import mstats, norm
from scipy.spatial.distance import pdist, squareform
from scipy.stats import spearmanr

from sklearn.covariance import MinCovDet
from sklearn.svm import OneClassSVM
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score, davies_bouldin_score, adjusted_rand_score
from sklearn.linear_model import HuberRegressor
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.decomposition import PCA, FactorAnalysis
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
import joblib

# Optional dependency
try:
    import hdbscan
    HDBSCAN_AVAILABLE = True
except Exception:
    HDBSCAN_AVAILABLE = False


# ---------------- Metrics & Utilities ----------------
def dunn_index(X, labels):
    """Dunn index: min inter-cluster distance / max intra-cluster distance (higher is better)."""
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
    if max_intra == 0:
        return np.nan
    return float(min_inter / max_intra)


def safe_silhouette(X, labels):
    try:
        labs = np.asarray(labels)
        uniq, counts = np.unique(labs, return_counts=True)
        if len(uniq) < 2 or np.any(counts < 2):
            return np.nan
        return float(silhouette_score(X, labs))
    except Exception:
        return np.nan


def safe_dbi(X, labels):
    try:
        labs = np.asarray(labels)
        if len(np.unique(labs)) < 2:
            return np.nan
        return float(davies_bouldin_score(X, labs))
    except Exception:
        return np.nan


def evaluate_partition(X, labels):
    return {
        "silhouette": safe_silhouette(X, labels),
        "dunn": dunn_index(X, labels),
        "dbi": safe_dbi(X, labels),
    }


def rank_0to1(arr):
    order = np.argsort(arr)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.linspace(0, 1, len(arr), endpoint=True)
    return ranks


# ---------------- Scores (Latent/Probabilistic) ----------------
def robust_mahalanobis_score(Z):
    """Z: latent (e.g., PCA). Return Mahalanobis^2 via robust covariance; higher=worse."""
    if Z.shape[0] < Z.shape[1] + 2:
        mu = Z.mean(axis=0, keepdims=True)
        cov = np.cov(Z, rowvar=False) + 1e-6*np.eye(Z.shape[1])
    else:
        mcd = MinCovDet().fit(Z)
        mu, cov = mcd.location_.reshape(1, -1), mcd.covariance_
    inv = np.linalg.pinv(cov)
    d2 = np.sum((Z - mu) @ inv * (Z - mu), axis=1)
    return d2.astype(float)


def gmm_nll_score(Z, n_components=2, seed=42):
    gm = GaussianMixture(n_components=n_components, covariance_type='full', random_state=seed)
    gm.fit(Z)
    return (-gm.score_samples(Z)).astype(float)


def gaussian_copula_score(X):
    """
    Rank-transform each column to U~(0,1), map to Z via Φ^{-1}(U), fit Gaussian, score by -loglik.
    Safe for mixed scales; handles heavy tails.
    """
    X = np.asarray(X, float)
    n, d = X.shape
    U = np.zeros_like(X, float)
    for j in range(d):
        r = np.argsort(np.argsort(X[:, j]))
        U[:, j] = (r + 0.5) / n
    Z = norm.ppf(U.clip(1e-6, 1-1e-6))
    mu = Z.mean(axis=0, keepdims=True)
    cov = np.cov(Z, rowvar=False) + 1e-6*np.eye(d)
    inv = np.linalg.pinv(cov)
    quad = np.sum((Z - mu) @ inv * (Z - mu), axis=1)
    logdet = np.log(np.linalg.det(cov) + 1e-12)
    nll = 0.5*(quad + logdet)  # constants omitted
    return nll.astype(float)


def ocsvm_score(Z, contamination=0.05, seed=42):
    svm = OneClassSVM(kernel='rbf', nu=min(max(contamination, 1e-3), 0.49), gamma='scale')
    svm.fit(Z)
    return (-svm.decision_function(Z)).ravel().astype(float)


def hdbscan_scores(Z, min_cluster_size=15, min_samples=None):
    if not HDBSCAN_AVAILABLE:
        return None, None
    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size,
                                min_samples=min_samples or max(2, min_cluster_size//2))
    labels = clusterer.fit_predict(Z)
    scores = clusterer.outlier_scores_
    return scores.astype(float), labels


# ---------------- Autoencoder / VAE ----------------
def try_fit_autoencoder(X, epochs=60, batch_size=64, seed=42, verbose=0):
    """
    Autoencoder with EarlyStopping to avoid overfitting and save time.
    Uses training loss (unsupervised) as stopping signal and restores best weights.
    """
    try:
        import tensorflow as tf
        from tensorflow.keras import layers, models, callbacks
    except Exception:
        return None

    tf.keras.utils.set_random_seed(seed)

    # --- Architecture ---
    inp = layers.Input(shape=(X.shape[1],))
    x = layers.Dense(64, activation="relu")(inp)
    x = layers.Dense(16, activation="relu")(x)
    z = layers.Dense(4, activation="relu")(x)
    x = layers.Dense(16, activation="relu")(z)
    x = layers.Dense(64, activation="relu")(x)
    out = layers.Dense(X.shape[1])(x)
    ae = models.Model(inp, out)
    ae.compile(optimizer="adam", loss="mse")

    # --- Early stopping on training loss ---
    es = callbacks.EarlyStopping(
        monitor="loss",          # unsupervised → no val_loss
        patience=8,              # stop if no improvement for 8 epochs
        min_delta=1e-4,          # minimal improvement to count as progress
        restore_best_weights=True,
        verbose=verbose,
    )

    ae.fit(
        X, X,
        epochs=epochs,
        batch_size=batch_size,
        verbose=verbose,
        callbacks=[es],
    )

    recon = ae.predict(X, verbose=0)
    err = np.mean((X - recon) ** 2, axis=1)
    return err.astype(float)


def try_fit_vae(X, latent_dim=8, epochs=60, batch_size=64, seed=42, verbose=0):
    """
    VAE with EarlyStopping on total loss (recon + KL).
    Still returns reconstruction error as anomaly score.
    """
    try:
        import tensorflow as tf
        from tensorflow.keras import layers, models, callbacks
    except Exception:
        return None

    tf.keras.utils.set_random_seed(seed)

    inp = layers.Input(shape=(X.shape[1],))
    h = layers.Dense(64, activation='relu')(inp)
    h = layers.Dense(32, activation='relu')(h)
    z_mu = layers.Dense(latent_dim)(h)
    z_logvar = layers.Dense(latent_dim)(h)

    # Reparameterization trick
    eps = tf.random.normal(shape=(tf.shape(inp)[0], latent_dim))
    z = z_mu + tf.exp(0.5 * z_logvar) * eps

    # Decoder
    dec = layers.Dense(32, activation='relu')(z)
    dec = layers.Dense(64, activation='relu')(dec)
    out = layers.Dense(X.shape[1])(dec)

    vae = models.Model(inp, out)

    # ELBO ~ recon + KL
    recon_loss = tf.reduce_mean(tf.reduce_sum(tf.square(inp - out), axis=1))
    kl_loss = -0.5 * tf.reduce_mean(
        tf.reduce_sum(1 + z_logvar - tf.square(z_mu) - tf.exp(z_logvar), axis=1)
    )
    total_loss = recon_loss + kl_loss
    vae.add_loss(total_loss)
    vae.compile(optimizer='adam')

    es = callbacks.EarlyStopping(
        monitor="loss",
        patience=8,
        min_delta=1e-4,
        restore_best_weights=True,
        verbose=verbose,
    )

    vae.fit(
        X, None,
        epochs=epochs,
        batch_size=batch_size,
        verbose=verbose,
        callbacks=[es],
    )

    recon = vae.predict(X, verbose=0)
    recon_err = np.mean((X - recon) ** 2, axis=1)
    return recon_err.astype(float)


# ---------------- Core pipeline helpers ----------------
def build_residual(df, x_cols, y_col, seed=42):
    """
    Fit ONE global HuberRegressor + StandardScaler on the training set,
    use it to compute residuals, and RETURN the fitted artifacts.
    This lets us reuse the same residual model at inference time.
    """
    X = df[x_cols].copy()
    y = df[y_col].copy()

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    model = HuberRegressor()
    model.fit(Xs, y)

    y_pred = model.predict(Xs)
    df["kwh_residual"] = y - y_pred
    df["kwh_resid_abs"] = np.abs(df["kwh_residual"])

    # return df + artifacts so training can persist them
    return df, scaler, model


def winsorize_and_ratios(df):
    """Winsorize heavy tails and create ratio/intensity features."""
    cols_to_cap = ["Area in m^2", "nb_appart", "nb_floor", "appts_per_floor", "kwh_residual"]
    for c in cols_to_cap:
        if c in df.columns:
            df[c] = mstats.winsorize(df[c], limits=[0.01, 0.01])
    kwh = "Total Electricity Consumption (kwH)"
    df["kwh_per_m2"] = df[kwh] / df["Area in m^2"].replace(0, np.nan)
    df["kwh_per_appt"] = df[kwh] / df["nb_appart"].replace(0, np.nan)
    df["kwh_per_floor"] = df[kwh] / df["nb_floor"].replace(0, np.nan)
    df["resid_per_m2"] = df["kwh_residual"] / df["Area in m^2"].replace(0, np.nan)
    ratio_cols = ["kwh_per_m2", "kwh_per_appt", "kwh_per_floor", "resid_per_m2"]
    for c in ratio_cols:
        df[c] = df[c].replace([np.inf, -np.inf], np.nan)
        df[c] = df[c].fillna(df[c].median())
    return df


# ---------------- Stability helpers ----------------
def topk_indices(vals, k):
    k = max(1, int(k))
    order = np.argsort(vals)[::-1]
    return set(order[:k])


def jaccard_at_k(a_scores, b_scores, k):
    A = topk_indices(a_scores, k)
    B = topk_indices(b_scores, k)
    inter = len(A & B)
    union = len(A | B)
    return inter / union if union else 1.0


def percentile_label(scores, contamination):
    thr = np.percentile(scores, 100 * (1 - contamination))
    return (scores >= thr).astype(int), float(thr)


# ---------------- Main pipeline ----------------
def run_pipeline(args):
    # ---------- Load ----------
    df = pd.read_csv(args.input)
    if not args.quiet:
        print(f"Loaded: {df.shape} from {args.input}")

    # ---------- Residuals ----------
    # ---------- Residuals ----------
    y_col = "Total Electricity Consumption (kwH)"
    x_cols = ["Area in m^2", "nb_appart", "nb_floor", "year_norm_z"]
    missing = [c for c in x_cols + [y_col] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for residuals: {missing}")

    df, resid_scaler, resid_model = build_residual(
        df, x_cols=x_cols, y_col=y_col, seed=args.seed
    )


    # ---------- Winsorization + ratios ----------
    df = winsorize_and_ratios(df)

    # ---------- Feature matrix ----------
    drop_cols = {c for c in ["fid", "FID"] if c in df.columns}
    num_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in drop_cols]
    if len(num_cols) < 2:
        raise ValueError(f"Not enough numeric columns after dropping {drop_cols}. Found: {num_cols}")
    X = df[num_cols].to_numpy()

    # ---------- Scale & PCA (or FA) ----------
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)
    if args.use_pca:
        pca = PCA(n_components=0.95, random_state=args.seed)
        X_model = pca.fit_transform(X_scaled)
        pca_model = pca
        if not args.quiet:
            print(f"PCA reduced dim: {X_scaled.shape[1]} -> {X_model.shape[1]} (95% var)")
    else:
        # Optionally use FactorAnalysis as a probabilistic PCA-like model
        if args.use_fa:
            fa = FactorAnalysis(n_components=min(20, X_scaled.shape[1]), random_state=args.seed)
            X_model = fa.fit_transform(X_scaled)
            pca_model = None
            if not args.quiet:
                print(f"FA reduced dim: {X_scaled.shape[1]} -> {X_model.shape[1]}")
        else:
            X_model = X_scaled
            pca_model = None

    # ---------- Method registry ----------
    method_scores = {}
    method_labels = {}

    # 1) Isolation Forest
    iso = IsolationForest(
        n_estimators=args.if_estimators,
        contamination=args.contamination,
        random_state=args.seed,
        max_features=args.if_max_features,
        bootstrap=args.if_bootstrap,
        n_jobs=-1,
    ).fit(X_model)
    method_scores["IF"] = (-iso.score_samples(X_model)).astype(float)

    # 2) LOF
    lof = LocalOutlierFactor(n_neighbors=args.lof_neighbors, contamination=args.contamination)
    lof.fit_predict(X_model)
    method_scores["LOF"] = (-lof.negative_outlier_factor_).astype(float)

    # 3) AE (optional)
    if args.use_ae:
        ae_score = try_fit_autoencoder(X_model, epochs=args.ae_epochs, batch_size=args.ae_batch,
                                       seed=args.seed, verbose=0)
        if ae_score is not None:
            method_scores["AE"] = ae_score

    # 4) VAE (optional)
    if args.use_vae:
        vae_score = try_fit_vae(X_model, latent_dim=args.vae_latent, epochs=args.ae_epochs,
                                batch_size=args.ae_batch, seed=args.seed, verbose=0)
        if vae_score is not None:
            method_scores["VAE"] = vae_score

    # 5) PPCA-style robust Mahalanobis in latent space
    method_scores["PPCA_MAH"] = robust_mahalanobis_score(X_model)

    # 6) GMM NLL (latent)
    if args.use_gmm:
        method_scores["GMM_NLL"] = gmm_nll_score(X_model, n_components=args.gmm_components, seed=args.seed)

    # 7) One-Class SVM
    if args.use_ocsvm:
        method_scores["OCSVM"] = ocsvm_score(X_model, contamination=args.contamination, seed=args.seed)

    # 8) HDBSCAN
    if args.use_hdbscan and HDBSCAN_AVAILABLE:
        hdb_scores, _ = hdbscan_scores(X_model, min_cluster_size=args.hdb_min_cluster, min_samples=args.hdb_min_samples)
        if hdb_scores is not None:
            method_scores["HDBSCAN"] = hdb_scores

    # 9) Gaussian Copula (on scaled original)
    if args.use_copula:
        method_scores["COPULA"] = gaussian_copula_score(X_model)

    # ---------- Rank fusion ----------
    # CLI weights: "IF:0.6,LOF:0.6,AE:0.4"
    weights = {}
    if args.fuse_weights:
        for token in args.fuse_weights.split(','):
            name, w = token.split(':')
            weights[name.strip().upper()] = float(w)

    ranks = []
    wts = []
    for name, score in method_scores.items():
        ranks.append(rank_0to1(score))
        wts.append(weights.get(name, 1.0))
    fused = np.average(np.column_stack(ranks), axis=1, weights=wts)
    thr_fused = np.percentile(fused, 100 * (1 - args.contamination))
    lab_fused = (fused >= thr_fused).astype(int)

    # Individual labels (for diagnostics)
    for name, score in method_scores.items():
        thr = np.percentile(score, 100 * (1 - args.contamination))
        method_labels[name] = (score >= thr).astype(int)

    # ---------- Metrics ----------
    def fmt(m): return f"S={m['silhouette']:.3f} | D={m['dunn']:.3f} | DBI={m['dbi']:.3f}"
    evals = {name: evaluate_partition(X_model, lab) for name, lab in method_labels.items()}
    evals["FUSED"] = evaluate_partition(X_model, lab_fused)

    if not args.quiet:
        print("\n=== Unsupervised Evaluation (Silhouette/Dunn/DBI) ===")
        for name in sorted(evals.keys()):
            print(f"{name:<9}: {fmt(evals[name])}")

    # ---------- Stability & Overfitting Audit ----------
    if not args.quiet:
        print("\n=== Stability & Overfitting Audit ===")

    base_fused = fused
    base_labels = lab_fused
    n = X_model.shape[0]
    k_top = max(1, int(args.contamination * n))

    B = args.audit_bootstrap
    subsample = args.audit_subsample
    rng = np.random.default_rng(args.seed)

    rho_list, jac_list, ari_list = [], [], []
    sil_list, dunn_list, dbi_list = [], [], []

    # Small refit function that mirrors selected methods and fusion
    def _refit_on_subset(X_subset, seed_offset=0):
        local_scores = {}

        iso_ = IsolationForest(
            n_estimators=args.if_estimators,
            contamination=args.contamination,
            random_state=args.seed + seed_offset,
            max_features=args.if_max_features,
            bootstrap=args.if_bootstrap,
            n_jobs=-1,
        ).fit(X_subset)
        local_scores["IF"] = (-iso_.score_samples(X_subset)).astype(float)

        lof_ = LocalOutlierFactor(n_neighbors=args.lof_neighbors, contamination=args.contamination)
        lof_.fit_predict(X_subset)
        local_scores["LOF"] = (-lof_.negative_outlier_factor_).astype(float)

        if args.use_ae:
            ae_sc = try_fit_autoencoder(X_subset, epochs=args.ae_epochs, batch_size=args.ae_batch,
                                        seed=args.seed + seed_offset, verbose=0)
            if ae_sc is not None:
                local_scores["AE"] = ae_sc

        if args.use_vae:
            vae_sc = try_fit_vae(X_subset, latent_dim=args.vae_latent, epochs=args.ae_epochs,
                                 batch_size=args.ae_batch, seed=args.seed + seed_offset, verbose=0)
            if vae_sc is not None:
                local_scores["VAE"] = vae_sc

        local_scores["PPCA_MAH"] = robust_mahalanobis_score(X_subset)

        if args.use_gmm:
            local_scores["GMM_NLL"] = gmm_nll_score(X_subset, n_components=args.gmm_components, seed=args.seed + seed_offset)

        if args.use_ocsvm:
            local_scores["OCSVM"] = ocsvm_score(X_subset, contamination=args.contamination, seed=args.seed + seed_offset)

        if args.use_hdbscan and HDBSCAN_AVAILABLE:
            hdb_sc, _ = hdbscan_scores(X_subset, min_cluster_size=args.hdb_min_cluster, min_samples=args.hdb_min_samples)
            if hdb_sc is not None:
                local_scores["HDBSCAN"] = hdb_sc

        if args.use_copula:
            local_scores["COPULA"] = gaussian_copula_score(X_subset)

        wts_ = []
        ranks_ = []
        for nm, sc in local_scores.items():
            ranks_.append(rank_0to1(sc))
            wts_.append(weights.get(nm, 1.0))
        fused_local = np.average(np.column_stack(ranks_), axis=1, weights=wts_)
        labels_local, _ = percentile_label(fused_local, args.contamination)
        eval_local = evaluate_partition(X_subset, labels_local)
        return local_scores, fused_local, labels_local, eval_local

    # Bootstraps (subsample with refits)
    for b in range(B):
        idx = rng.choice(n, int(subsample * n), replace=False)
        Xb = X_model[idx]
        _, fused_b, lab_b, eval_b = _refit_on_subset(Xb, seed_offset=1000 + b)

        base_fused_b = base_fused[idx]
        base_lab_b = base_labels[idx]

        rho, _ = spearmanr(base_fused_b, fused_b)
        rho_list.append(float(rho) if np.isfinite(rho) else np.nan)

        k_b = max(1, int(args.contamination * len(idx)))
        jac = jaccard_at_k(base_fused_b, fused_b, k_b)
        jac_list.append(float(jac))

        ari = adjusted_rand_score(base_lab_b, lab_b)
        ari_list.append(float(ari))

        sil_list.append(float(eval_b["silhouette"]) if eval_b["silhouette"] == eval_b["silhouette"] else np.nan)
        dunn_list.append(float(eval_b["dunn"]) if eval_b["dunn"] == eval_b["dunn"] else np.nan)
        dbi_list.append(float(eval_b["dbi"]) if eval_b["dbi"] == eval_b["dbi"] else np.nan)

    # Seed sensitivity
    seed_rhos = []
    for s in range(args.audit_seed_trials):
        _, fused_s, _, _ = _refit_on_subset(X_model, seed_offset=2000 + s)
        r_s, _ = spearmanr(base_fused, fused_s)
        seed_rhos.append(float(r_s) if np.isfinite(r_s) else np.nan)

    # Noise robustness
    noise_rhos = []
    noise_sigma = args.audit_noise_sigma
    for t in range(args.audit_noise_trials):
        Z_noisy = X_model + noise_sigma * rng.standard_normal(X_model.shape)
        _, fused_n, _, _ = _refit_on_subset(Z_noisy, seed_offset=3000 + t)
        r_n, _ = spearmanr(base_fused, fused_n)
        noise_rhos.append(float(r_n) if np.isfinite(r_n) else np.nan)

    stability_report = {
        "bootstrap": {
            "spearman_rho_mean": float(np.nanmean(rho_list)),
            "spearman_rho_std": float(np.nanstd(rho_list)),
            "jaccard_at_k_mean": float(np.nanmean(jac_list)),
            "jaccard_at_k_std": float(np.nanstd(jac_list)),
            "ari_mean": float(np.nanmean(ari_list)),
            "ari_std": float(np.nanstd(ari_list)),
            "silhouette_std": float(np.nanstd([x for x in sil_list if x==x])),
            "dunn_std": float(np.nanstd([x for x in dunn_list if x==x])),
            "dbi_std": float(np.nanstd([x for x in dbi_list if x==x])),
            "B": int(B),
            "subsample": float(subsample),
        },
        "seed_sensitivity": {
            "spearman_rho_mean": float(np.nanmean(seed_rhos)),
            "spearman_rho_std": float(np.nanstd(seed_rhos)),
            "trials": int(len(seed_rhos)),
        },
        "noise_robustness": {
            "spearman_rho_mean": float(np.nanmean(noise_rhos)),
            "spearman_rho_std": float(np.nanstd(noise_rhos)),
            "sigma": float(noise_sigma),
            "trials": int(len(noise_rhos)),
        },
        "k_top": int(k_top),
        "n_samples": int(n),
        "contamination": float(args.contamination),
    }

    if not args.quiet:
        sr = stability_report
        print(
            "Bootstrap rho: "
            f"{sr['bootstrap']['spearman_rho_mean']:.3f} +/- {sr['bootstrap']['spearman_rho_std']:.3f}"
        )
        print(
            "Jaccard@k: "
            f"{sr['bootstrap']['jaccard_at_k_mean']:.3f} +/- {sr['bootstrap']['jaccard_at_k_std']:.3f}"
        )
        print(
            "ARI: "
            f"{sr['bootstrap']['ari_mean']:.3f} +/- {sr['bootstrap']['ari_std']:.3f}"
        )
        print(
            "Metric std: "
            f"Sil={sr['bootstrap']['silhouette_std']:.3f} | "
            f"Dunn={sr['bootstrap']['dunn_std']:.3f} | "
            f"DBI={sr['bootstrap']['dbi_std']:.3f}"
        )
        print(
            "Seeds rho: "
            f"{sr['seed_sensitivity']['spearman_rho_mean']:.3f} +/- {sr['seed_sensitivity']['spearman_rho_std']:.3f}"
        )
        print(
            "Noise rho: "
            f"{sr['noise_robustness']['spearman_rho_mean']:.3f} +/- {sr['noise_robustness']['spearman_rho_std']:.3f}"
        )

    # ---------- Threshold sweep (console) ----------
    if args.sweep_thresholds and not args.quiet:
        print("\n=== Threshold sweep (percentile cutoffs) ===")
        percent_list = [4, 6, 8, 10, 12, 15, 20]
        temp = pd.DataFrame({f"{k.lower()}_score": v for k, v in method_scores.items()})
        temp["fused_rank"] = fused
        for col in temp.columns:
            vals = temp[col].to_numpy()
            print(f"\n[{col}]")
            for pct in percent_list:
                thr = np.percentile(vals, 100 - pct)
                flagged_pct = (vals >= thr).mean() * 100.0
                print(f"  {pct:>2}% cutoff -> flags ≈ {flagged_pct:5.1f}% (thr={thr:.6f})")

    # ---------- Save outputs ----------
    if not args.skip_save:
        out = df.copy()
        for name, score in method_scores.items():
            out[f"{name.lower()}_score"] = score
            out[f"is_anomaly_{name.lower()}"] = method_labels.get(name, np.zeros_like(fused))
        out["fused_rank"] = fused
        out["is_anomaly_fused"] = lab_fused

        Path(os.path.dirname(args.output)).mkdir(parents=True, exist_ok=True)
        out.sort_values("fused_rank", ascending=False).to_csv(args.output, index=False)

        meta = {
            "contamination": args.contamination,
            "methods": list(method_scores.keys()),
            "thresholds": {name: float(np.percentile(s, 100*(1-args.contamination))) for name, s in method_scores.items()},
            "fused_threshold": float(thr_fused),
            "evals": {k: {m: float(v[m]) if v[m]==v[m] else None for m in v} for k, v in evals.items()},
            "weights": weights,
            "use_pca": bool(args.use_pca),
            "use_fa": bool(args.use_fa),
            "pca_components": int(X_model.shape[1]) if (args.use_pca or args.use_fa) else None,
            "feature_columns": num_cols,
        }
        with open(args.output.replace(".csv", "_meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        with open(args.output.replace(".csv", "_stability.json"), "w") as f:
            json.dump(stability_report, f, indent=2)

        joblib.dump(scaler, args.output.replace(".csv", "_scaler.joblib"))
        if pca_model is not None:
            joblib.dump(pca_model, args.output.replace(".csv", "_pca.joblib"))
        resid_path = args.output.replace(".csv", "_resid.joblib")
        joblib.dump(
            {
                "x_cols": x_cols,
                "scaler": resid_scaler,
                "model": resid_model,
            },
            resid_path,
        )

        if not args.quiet:
            print(f"\nSaved: {args.output}")
            print(f"Saved meta: {args.output.replace('.csv', '_meta.json')}")
            print(f"Saved stability: {args.output.replace('.csv', '_stability.json')}")

    # Return fused metrics
    ef = evals["FUSED"]
    return ef["silhouette"], ef["dunn"], ef["dbi"]


# ---------------- CLI ----------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Unsupervised anomaly detection with residuals, ratios, PCA/FA, IF/LOF/(AE/VAE), and stability audit.")
    ap.add_argument("--input", default="data/processed/processed_data.csv", help="Processed CSV path.")
    ap.add_argument("--output", default="data/processed/anomaly_scores.csv", help="Where to save ranked anomalies.")

    # Core
    ap.add_argument("--contamination", type=float, default=0.05, help="Expected anomaly fraction.")
    ap.add_argument("--cv_folds", type=int, default=5, help="Folds for residual regression.")
    ap.add_argument("--use_pca", type=int, default=1, help="Use PCA 95%% variance (1/0).")
    ap.add_argument("--use_fa", type=int, default=0, help="Use Factor Analysis instead of PCA when --use_pca=0 (1/0).")

    # IF/LOF
    ap.add_argument("--if_estimators", type=int, default=400, help="Isolation Forest trees.")
    ap.add_argument("--if_max_features", type=float, default=1.0, help="IF max_features fraction (0-1].")
    ap.add_argument("--if_bootstrap", type=int, default=0, help="IF bootstrap (1/0).")
    ap.add_argument("--lof_neighbors", type=int, default=30, help="LOF k neighbors.")

    # AE/VAE
    ap.add_argument("--use_ae", type=int, default=1, help="Train Autoencoder (1/0).")
    ap.add_argument("--ae_epochs", type=int, default=60, help="AE/VAE epochs.")
    ap.add_argument("--ae_batch", type=int, default=64, help="AE/VAE batch size.")
    ap.add_argument("--use_vae", type=int, default=0, help="Enable VAE scoring (1/0).")
    ap.add_argument("--vae_latent", type=int, default=8, help="VAE latent dimension.")

    # Optional methods
    ap.add_argument("--use_ocsvm", type=int, default=1, help="Enable One-Class SVM (1/0).")
    ap.add_argument("--use_hdbscan", type=int, default=0, help="Enable HDBSCAN (1/0).")
    ap.add_argument("--hdb_min_cluster", type=int, default=15, help="HDBSCAN min_cluster_size.")
    ap.add_argument("--hdb_min_samples", type=int, default=0, help="HDBSCAN min_samples (0=auto).")
    ap.add_argument("--use_gmm", type=int, default=0, help="Enable GMM NLL score (1/0).")
    ap.add_argument("--gmm_components", type=int, default=2, help="GMM components in latent space.")
    ap.add_argument("--use_copula", type=int, default=0, help="Enable Gaussian copula scoring (1/0).")

    # Fusion
    ap.add_argument("--fuse_weights", type=str, default="", help="Comma list like 'IF:0.6,LOF:0.6,AE:0.4'.")

    # Audit & I/O
    ap.add_argument("--seed", type=int, default=42, help="Random seed.")
    ap.add_argument("--sweep_thresholds", type=int, default=1, help="Print 4/6/8/10/12/15/20%% cutoffs (1/0).")
    ap.add_argument("--quiet", type=int, default=0, help="Silence most prints (1/0).")
    ap.add_argument("--skip_save", type=int, default=0, help="Skip writing outputs to CSV (1/0).")

    # Stability audit knobs
    ap.add_argument("--audit_bootstrap", type=int, default=20, help="Number of bootstrap refits.")
    ap.add_argument("--audit_subsample", type=float, default=0.8, help="Bootstrap subsample fraction (0-1].")
    ap.add_argument("--audit_seed_trials", type=int, default=5, help="Seed sensitivity trials.")
    ap.add_argument("--audit_noise_sigma", type=float, default=0.01, help="Gaussian noise std for robustness test.")
    ap.add_argument("--audit_noise_trials", type=int, default=5, help="Noise robustness trials.")

    args = ap.parse_args()
    args.use_pca = bool(args.use_pca)
    args.use_fa = bool(args.use_fa)
    args.if_bootstrap = bool(args.if_bootstrap)
    args.use_ae = bool(args.use_ae)
    args.use_vae = bool(args.use_vae)
    args.use_ocsvm = bool(args.use_ocsvm)
    args.use_hdbscan = bool(args.use_hdbscan)
    args.use_gmm = bool(args.use_gmm)
    args.use_copula = bool(args.use_copula)
    args.sweep_thresholds = bool(args.sweep_thresholds)
    args.quiet = bool(args.quiet)
    args.skip_save = bool(args.skip_save)

    run_pipeline(args)

