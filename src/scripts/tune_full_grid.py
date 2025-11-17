# Grid/Random tuning for run_pipeline with stability-aware objective.
# Produces a CSV of trials and prints the best config.

import os
import sys
import json
import hashlib
import itertools
import time
import shutil
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure we can import your pipeline
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.train_models import run_pipeline  # <- your enhanced run_pipeline


# ---------------- Configuration ----------------
INPUT_PATH = "data/processed/processed_data.csv"
OUT_DIR = Path("data/tuning_runs")     # unique per trial; safe to delete afterwards
OUT_DIR.mkdir(parents=True, exist_ok=True)

# === Primary parameter grid (feel free to expand) ===
param_grid = {
    'contamination':   [0.02, 0.04, 0.06, 0.08, 0.10],
    'use_pca':         [1, 0],         # when 0 you can try FactorAnalysis via use_fa=1
    'use_fa':          [0,1],            # set [0,1] if you want to try FA when use_pca=0
    'lof_neighbors':   [10, 20, 30, 50],
    'if_estimators':   [100, 200, 300, 400],
    'if_max_features': [0.6, 0.8, 1.0],
    'use_ae':          [1],            # set [0,1] to toggle AE
    'use_ocsvm':       [1],            # OCSVM on/off
    'use_copula':      [0, 1],
    'use_hdbscan':     [0],            # enable if installed
    'hdb_min_cluster': [20],           # only used if use_hdbscan=1
}

# Optional extra knobs (fixed defaults you can change)
DEFAULTS = dict(
    cv_folds=5,
    ae_epochs=60,
    ae_batch=64,
    seed=42,
    sweep_thresholds=0,
    if_bootstrap=0,
    use_vae=0,
    vae_latent=8,
    use_gmm=0,
    gmm_components=2,
    fuse_weights="",     # e.g., "IF:0.6,LOF:0.6,OCSVM:0.6,PPCA_MAH:0.4,COPULA:0.4,AE:0.4"
    audit_bootstrap=12,  # lighter audit for tuning
    audit_subsample=0.8,
    audit_seed_trials=3,
    audit_noise_sigma=0.01,
    audit_noise_trials=3,
)

# Composite score weights (tweak to taste)
W_SIL, W_DUNN, W_DBI = 0.50, 0.40, 0.10            # main partition quality (unsupervised)
W_RHO, W_JAC, W_SEED, W_NOISE = 0.20, 0.15, 0.10, 0.10  # stability bonuses
P_SIL_STD, P_DUNN_STD, P_DBI_STD = 0.10, 0.10, 0.05     # penalize dispersion across bootstraps


# ---------------- Utilities ----------------
def combo_hash(params: dict) -> str:
    """Deterministic short hash for a parameter combo (for unique output paths)."""
    key = json.dumps(params, sort_keys=True)
    return hashlib.md5(key.encode()).hexdigest()[:10]


def build_args(params: dict, output_base: Path) -> Namespace:
    """
    Build the argparse Namespace that run_pipeline expects.
    Each trial writes to a unique base so meta/stability JSON don't collide.
    """
    out_csv = output_base / "anomaly_scores.csv"
    a = dict(
        input=INPUT_PATH,
        output=str(out_csv),
        contamination=params['contamination'],
        cv_folds=DEFAULTS['cv_folds'],
        use_pca=bool(params['use_pca']),
        use_fa=bool(params.get('use_fa', 0)),
        if_estimators=params['if_estimators'],
        if_max_features=params['if_max_features'],
        if_bootstrap=bool(DEFAULTS['if_bootstrap']),
        lof_neighbors=params['lof_neighbors'],
        use_ae=bool(params['use_ae']),
        ae_epochs=DEFAULTS['ae_epochs'],
        ae_batch=DEFAULTS['ae_batch'],
        seed=DEFAULTS['seed'],
        sweep_thresholds=bool(DEFAULTS['sweep_thresholds']),
        quiet=True,                 # quiet during tuning
        skip_save=False,            # must save to read stability JSON
        use_ocsvm=bool(params.get('use_ocsvm', 1)),
        use_hdbscan=bool(params.get('use_hdbscan', 0)),
        hdb_min_cluster=int(params.get('hdb_min_cluster', 20)),
        hdb_min_samples=0,
        use_gmm=bool(DEFAULTS['use_gmm']),
        gmm_components=int(DEFAULTS['gmm_components']),
        use_copula=bool(params.get('use_copula', 0)),
        use_vae=bool(DEFAULTS['use_vae']),
        vae_latent=int(DEFAULTS['vae_latent']),
        fuse_weights=str(DEFAULTS['fuse_weights']),
        audit_bootstrap=int(DEFAULTS['audit_bootstrap']),
        audit_subsample=float(DEFAULTS['audit_subsample']),
        audit_seed_trials=int(DEFAULTS['audit_seed_trials']),
        audit_noise_sigma=float(DEFAULTS['audit_noise_sigma']),
        audit_noise_trials=int(DEFAULTS['audit_noise_trials']),
    )
    return Namespace(**a)


def composite_score(sil, dunn, dbi, stab: dict) -> float:
    """
    Combine unsupervised partition quality with stability audit into a single score.
    Higher is better.
    """
    # Unpack stability safely
    bs = stab.get("bootstrap", {})
    seed = stab.get("seed_sensitivity", {})
    noise = stab.get("noise_robustness", {})

    rho = bs.get("spearman_rho_mean", np.nan)
    jac = bs.get("jaccard_at_k_mean", np.nan)
    ari = bs.get("ari_mean", np.nan)  # not used directly, but you can include it
    sil_std = bs.get("silhouette_std", np.nan)
    dunn_std = bs.get("dunn_std", np.nan)
    dbi_std = bs.get("dbi_std", np.nan)

    rho_seed = seed.get("spearman_rho_mean", np.nan)
    rho_noise = noise.get("spearman_rho_mean", np.nan)

    # Replace NaNs with neutral values
    def nz(x, neutral=0.0):
        return x if (x is not None and np.isfinite(x)) else neutral

    sil, dunn, dbi = nz(sil), nz(dunn), nz(dbi)
    rho, jac, rho_seed, rho_noise = nz(rho), nz(jac), nz(rho_seed), nz(rho_noise)
    sil_std, dunn_std, dbi_std = nz(sil_std), nz(dunn_std), nz(dbi_std)

    score = (
        W_SIL * sil +
        W_DUNN * dunn -
        W_DBI * dbi +
        W_RHO * rho +
        W_JAC * jac +
        W_SEED * rho_seed +
        W_NOISE * rho_noise -
        P_SIL_STD * sil_std -
        P_DUNN_STD * dunn_std -
        P_DBI_STD * dbi_std
    )
    return float(score)


def run_trial(params: dict) -> dict:
    """Run a single configuration and return a result row (dict)."""
    t0 = time.time()
    out_base = OUT_DIR / combo_hash(params)
    out_base.mkdir(parents=True, exist_ok=True)

    args = build_args(params, out_base)
    sil, dunn, dbi = run_pipeline(args)

    # Read stability JSON
    stab_path = (out_base / "anomaly_scores_stability.json")
    if not stab_path.exists():
        # Try with the same naming used inside pipeline
        # (the pipeline saves to args.output.replace(".csv", "_stability.json"))
        alt = str(args.output).replace(".csv", "_stability.json")
        stab_path = Path(alt)

    stability = {}
    if stab_path.exists():
        with open(stab_path, "r") as f:
            stability = json.load(f)

    score = composite_score(sil, dunn, dbi, stability)
    dur = time.time() - t0

    row = {
        **params,
        "silhouette": sil,
        "dunn": dunn,
        "dbi": dbi,
        "score": score,
        "time_sec": round(dur, 2),
        # key stability summaries (safe if missing)
        "rho_bootstrap": stability.get("bootstrap", {}).get("spearman_rho_mean", np.nan),
        "jacc_topk": stability.get("bootstrap", {}).get("jaccard_at_k_mean", np.nan),
        "rho_seed": stability.get("seed_sensitivity", {}).get("spearman_rho_mean", np.nan),
        "rho_noise": stability.get("noise_robustness", {}).get("spearman_rho_mean", np.nan),
    }
    return row


# ---------------- Main (grid search) ----------------
def main():
    combos = list(itertools.product(*param_grid.values()))
    keys = list(param_grid.keys())

    results = []
    best = None

    print(f"Running {len(combos)} configurations...")
    for i, combo in enumerate(combos, 1):
        params = dict(zip(keys, combo))

        # Safety: if use_pca=0 and use_fa not provided in grid, keep FA off
        if not params['use_pca'] and ('use_fa' not in params):
            params['use_fa'] = 0

        print(f"[{i}/{len(combos)}] {params}")
        try:
            row = run_trial(params)
            results.append(row)
            if (best is None) or (row["score"] > best["score"]):
                best = row
            print(f"  → score={row['score']:.4f}  sil={row['silhouette']:.3f}  dunn={row['dunn']:.3f}  dbi={row['dbi']:.3f}")
        except Exception as e:
            print(f"  !! Failed: {e}")
            # Record failure row
            results.append({**params, "silhouette": np.nan, "dunn": np.nan, "dbi": np.nan, "score": -1e9, "error": str(e)})

    # Save results CSV
    df = pd.DataFrame(results)
    df.sort_values("score", ascending=False, inplace=True)
    out_csv = OUT_DIR / "tuning_results.csv"
    df.to_csv(out_csv, index=False)

    # Print best
    print("\n[OK] Best configuration:")
    if best is not None:
        best_params = {k: v for k, v in best.items() if k in param_grid.keys() or k == 'use_fa'}
        print(best_params)
        print(f"Score: {best['score']:.4f} | Sil={best['silhouette']:.3f} | Dunn={best['dunn']:.3f} | DBI={best['dbi']:.3f}")
    else:
        print("No successful runs.")

    print(f"\nAll trials saved to: {out_csv}")
    print(f"Per-trial artifacts under: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
