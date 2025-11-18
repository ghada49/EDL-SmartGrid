# src/scripts/tune_slow.py
"""
Slow Mode Hyperparameter Tuner
Full brute-force sweep (choose random 850 configurations) of fused anomaly detection pipeline
Uses the enhanced run_pipeline() with stability audits.

Produces:
  - data/tuning_runs/tuning_results.csv
  - data/tuning_runs/best_config.json
  - per-trial artifacts in data/tuning_runs/<trial_id>/
"""

import os
import sys
import time
import json
import hashlib
import itertools
from pathlib import Path
from argparse import Namespace
import random
import numpy as np
import pandas as pd

# -------------------------------------------------------------------
# Import pipeline
# -------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT))

from src.models.train_models import run_pipeline   # <-- your fused pipeline


# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------
INPUT_PATH = REPO_ROOT / "data" / "processed" / "processed_data.csv"
TUNING_DIR = REPO_ROOT / "data" / "tuning_runs"
TUNING_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# Slow-mode brute-force parameter grid (≈960 trials)
# -------------------------------------------------------------------
PARAM_GRID = {
    "contamination":   [0.02, 0.04, 0.06, 0.08, 0.10],
    "use_pca":         [1, 0],
    "use_fa":          [0, 1],
    "lof_neighbors":   [10, 20, 30, 40, 50, 60],
    "if_estimators":   [100, 200, 300, 400],
    "if_max_features": [0.4, 0.6, 0.8, 1.0],
    "use_ae":          [0, 1],
    "use_ocsvm":       [0, 1],
    "use_copula":      [0, 1],
    "use_hdbscan":     [0, 1],
    "hdb_min_cluster": [10, 20, 30, 40, 50],
}

# -------------------------------------------------------------------
# Defaults for every run (light to moderate stability)
# -------------------------------------------------------------------
DEFAULTS = dict(
    cv_folds=5,
    ae_epochs=60,
    ae_batch=64,
    seed=42,
    sweep_thresholds=0,
    if_bootstrap=False,
    use_vae=0,
    vae_latent=8,
    use_gmm=0,
    gmm_components=2,
    fuse_weights="",
    audit_bootstrap=12,
    audit_subsample=0.8,
    audit_seed_trials=3,
    audit_noise_sigma=0.01,
    audit_noise_trials=3,
)


# -------------------------------------------------------------------
# Composite scoring (quality + stability)
# -------------------------------------------------------------------
def composite_score(sil, dunn, dbi, stab):
    """Combines clustering quality with stability metrics."""
    boot = stab.get("bootstrap", {})
    seed = stab.get("seed_sensitivity", {})
    noise = stab.get("noise_robustness", {})

    # Use safe fallback
    def nz(x, neutral=0):
        return x if (x is not None and np.isfinite(x)) else neutral

    rho = nz(boot.get("spearman_rho_mean"))
    jacc = nz(boot.get("jaccard_at_k_mean"))
    sil_std = nz(boot.get("silhouette_std"))
    dunn_std = nz(boot.get("dunn_std"))
    dbi_std = nz(boot.get("dbi_std"))
    rho_seed = nz(seed.get("spearman_rho_mean"))
    rho_noise = nz(noise.get("spearman_rho_mean"))

    return (
        0.50 * nz(sil)
        + 0.40 * nz(dunn)
        - 0.10 * nz(dbi)
        + 0.20 * rho
        + 0.15 * jacc
        + 0.10 * rho_seed
        + 0.10 * rho_noise
        - 0.10 * sil_std
        - 0.10 * dunn_std
        - 0.05 * dbi_std
    )


# -------------------------------------------------------------------
# Trial runner
# -------------------------------------------------------------------
def run_one_trial(params):
    """
    Runs one trial and returns:
    {
      **params,
      silhouette,
      dunn,
      dbi,
      score,
      time_sec,
      stability_metrics,
    }
    """
    trial_id = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
    output_base = TUNING_DIR / trial_id
    output_base.mkdir(parents=True, exist_ok=True)

    output_csv = output_base / "scores.csv"

    args = Namespace(
        input=str(INPUT_PATH),
        output=str(output_csv),
        contamination=params["contamination"],
        use_pca=bool(params["use_pca"]),
        use_fa=bool(params["use_fa"]),
        lof_neighbors=params["lof_neighbors"],
        if_estimators=params["if_estimators"],
        if_max_features=params["if_max_features"],
        use_ae=bool(params["use_ae"]),
        use_ocsvm=bool(params["use_ocsvm"]),
        use_copula=bool(params["use_copula"]),
        use_hdbscan=bool(params["use_hdbscan"]),
        hdb_min_cluster=int(params["hdb_min_cluster"]),
        hdb_min_samples=0,
        **DEFAULTS,
        quiet=True,
        skip_save=False,  # MUST save stability JSON
    )

    t0 = time.time()
    sil, dunn, dbi = run_pipeline(args)
    dt = time.time() - t0

    # Load stability JSON
    stab_path = str(output_csv).replace(".csv", "_stability.json")
    stability = {}
    if os.path.exists(stab_path):
        with open(stab_path, "r") as f:
            stability = json.load(f)

    score = composite_score(sil, dunn, dbi, stability)

    return {
        **params,
        "silhouette": sil,
        "dunn": dunn,
        "dbi": dbi,
        "score": score,
        "time_sec": round(dt, 2),
        "trial_id": trial_id,
    }


# -------------------------------------------------------------------
# Main brute-force sweep
# -------------------------------------------------------------------
def main():
    keys = list(PARAM_GRID.keys())
    
    # Generate all possible combos
    all_combos = list(itertools.product(*PARAM_GRID.values()))
    
    # Shuffle and sample a smaller subset
    random.shuffle(all_combos)
    sampled_combos = all_combos[:850]  # only run 850 trials
    
    print(f"SLOW MODE: Running {len(sampled_combos)} sampled configurations...\n")

    rows = []
    best = None

    for i, values in enumerate(sampled_combos, 1):
        params = dict(zip(keys, values))
        print(f"[{i}/{len(sampled_combos)}] {params}")

        try:
            row = run_one_trial(params)
            rows.append(row)

            print(
                f"   Score={row['score']:.4f} | "
                f"Sil={row['silhouette']:.3f} | "
                f"Dunn={row['dunn']:.3f} | DBI={row['dbi']:.3f}"
            )

            if best is None or row["score"] > best["score"]:
                best = row

        except Exception as e:
            print(f"Failed: {e}")
            rows.append({**params, "score": -1e9, "error": str(e)})

    # Save full results
    df = pd.DataFrame(rows)
    df.sort_values("score", ascending=False, inplace=True)
    results_csv = TUNING_DIR / "tuning_results.csv"
    df.to_csv(results_csv, index=False)

    # Save best config
    best_json = TUNING_DIR / "best_config.json"
    with open(best_json, "w") as f:
        json.dump(best, f, indent=2)

    print("\n====================================")
    print("SLOW MODE DONE")
    print("Best configuration:")
    print(best)
    print(f"Results CSV      : {results_csv}")
    print(f"Best config JSON : {best_json}")
    print("====================================")



if __name__ == "__main__":
    main()
