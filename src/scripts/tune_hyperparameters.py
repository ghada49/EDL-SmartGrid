# scripts/tune_hyperparameters.py 
# Fast tuner for run_pipeline using Sobol sampling + Successive Halving (ASHA-like).
# - Covers many distinct configs without brute-force grid (no 960 runs!)
# - Stage 1: many candidates, small data subsample + light audit
# - Stage 2: top fraction promoted, larger subsample + medium audit
# - Stage 3: finalists, full data + deeper audit
# - Parallel execution; caching via hash folders

import os
import sys
import json
import time
import shutil
import hashlib
import multiprocessing as mp
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure we can import your pipeline
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.train_models import run_pipeline  # your enhanced run_pipeline

# Optional: Sobol sequences for good coverage without repetition
try:
    from scipy.stats import qmc
    HAS_QMC = True
except Exception:
    HAS_QMC = False


# ------------- CONFIG -------------
INPUT_PATH = "data/processed/processed_data.csv"
RUNS_DIR = Path("data/tuning_runs_asha")
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# Discrete search space (broad but sensible)
SPACE = {
    "contamination":   [0.02, 0.03, 0.04, 0.05, 0.07],
    "use_pca":         [1, 0],          # if 1 -> use_fa ignored
    "use_fa":          [0, 1],          # only when use_pca=0
    "lof_neighbors":   [10, 20, 30, 50],
    "if_estimators":   [100,200, 300, 400],
    "if_max_features": [0.6, 0.8, 1.0],
    "use_ae":          [1,0],             # keep on; set [0,1] if you want to test off
    "use_ocsvm":       [1,0],
    "use_copula":      [0, 1],
    "use_hdbscan":     [0,1],             # enable if you installed hdbscan and want it
    "hdb_min_cluster": [5,10,20,30],            # only used if use_hdbscan=1
}

# ASHA-like stages: (row_subsample, audit_bootstrap, seed_trials, noise_trials)
STAGES = [
    (0.40, 4, 1, 1),   # Stage 1: many candidates, very fast
    (0.75, 6, 2, 2),   # Stage 2: fewer candidates, medium audit
    (1.00, 12, 3, 3),  # Stage 3: finalists, deeper audit
]
# Promotion ratio per stage: keep top fraction
KEEP_FRAC = 0.33  # keep top 33% each stage

# Candidate counts (you can tweak N1 higher if you want broader coverage)
N1 = 60   # Stage 1 candidate count
SEED = 42

# Base AE epoch budget (before scaling per stage)
BASE_AE_EPOCHS = 60

# Composite score weights (reuse logic from previous tuner)
W_SIL, W_DUNN, W_DBI = 0.50, 0.40, 0.10
W_RHO, W_JAC, W_SEED, W_NOISE = 0.20, 0.15, 0.10, 0.10
P_SIL_STD, P_DUNN_STD, P_DBI_STD = 0.10, 0.10, 0.05

# Parallelism
N_WORKERS = max(1, min(4, mp.cpu_count() - 1))

# Fixed defaults not tuned here
DEFAULTS = dict(
    cv_folds=5,
    ae_batch=64,
    if_bootstrap=0,
    use_vae=0,
    vae_latent=8,
    use_gmm=0,
    gmm_components=2,
    fuse_weights="",  # e.g., "IF:0.6,LOF:0.6,OCSVM:0.6,PPCA_MAH:0.4,COPULA:0.4,AE:0.4"
    sweep_thresholds=0,
)


# ------------- UTILS -------------
def combo_hash(params: dict) -> str:
    key = json.dumps(params, sort_keys=True)
    return hashlib.md5(key.encode()).hexdigest()[:10]


def discrete_sample_sobol(space: dict, n: int, seed: int) -> list[dict]:
    """
    Quasi-randomly sample 'n' configurations without repetition using Sobol
    (falls back to RNG if qmc unavailable).
    Applies conditional logic to avoid meaningless duplicates (use_fa only when use_pca=0).
    """
    keys = list(space.keys())

    def snap(u, options):
        idx = min(int(u * len(options)), len(options) - 1)
        return options[idx]

    configs = []
    seen = set()
    if HAS_QMC:
        dim = len(keys)
        sampler = qmc.Sobol(d=dim, scramble=True, seed=seed)
        U = sampler.random_base2(int(np.ceil(np.log2(max(1, n)))))
        U = U[:n]
    else:
        rng = np.random.default_rng(seed)
        U = rng.random((n, len(keys)))

    for row in U:
        cand = {}
        for j, k in enumerate(keys):
            cand[k] = snap(row[j], space[k])

        # Conditional cleanup:
        if cand["use_pca"] == 1:
            cand["use_fa"] = 0
        if cand["use_hdbscan"] == 0:
            cand["hdb_min_cluster"] = SPACE["hdb_min_cluster"][0]

        cano = json.dumps(cand, sort_keys=True)
        if cano in seen:
            continue
        seen.add(cano)
        configs.append(cand)
    return configs


def subsample_csv(input_csv: str, out_csv: Path, frac: float, seed: int) -> int:
    """Write a subsampled CSV for quick stages. Returns number of rows."""
    df = pd.read_csv(input_csv)
    if frac >= 0.999:
        df_out = df
    else:
        df_out = df.sample(frac=frac, random_state=seed)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out_csv, index=False)
    return len(df_out)


def build_args(
    params: dict,
    stage_dir: Path,
    input_path: str,
    audit_bootstrap: int,
    seed_trials: int,
    noise_trials: int,
    ae_epochs: int,
) -> Namespace:
    """
    Build the argparse Namespace that run_pipeline expects.
    ae_epochs is now stage-dependent (dynamic epoch scaling).
    """
    out_csv = stage_dir / "anomaly_scores.csv"
    return Namespace(
        input=str(input_path),
        output=str(out_csv),
        contamination=params['contamination'],
        cv_folds=DEFAULTS['cv_folds'],
        use_pca=bool(params['use_pca']),
        use_fa=bool(params['use_fa']),
        if_estimators=params['if_estimators'],
        if_max_features=params['if_max_features'],
        if_bootstrap=bool(DEFAULTS['if_bootstrap']),
        lof_neighbors=params['lof_neighbors'],
        use_ae=bool(params['use_ae']),
        ae_epochs=int(ae_epochs),
        ae_batch=DEFAULTS['ae_batch'],
        seed=SEED,
        sweep_thresholds=bool(DEFAULTS['sweep_thresholds']),
        quiet=True,
        skip_save=False,
        use_ocsvm=bool(params['use_ocsvm']),
        use_hdbscan=bool(params['use_hdbscan']),
        hdb_min_cluster=int(params['hdb_min_cluster']),
        hdb_min_samples=0,
        use_gmm=bool(DEFAULTS['use_gmm']),
        gmm_components=int(DEFAULTS['gmm_components']),
        use_copula=bool(params['use_copula']),
        use_vae=bool(DEFAULTS['use_vae']),
        vae_latent=int(DEFAULTS['vae_latent']),
        fuse_weights=str(DEFAULTS['fuse_weights']),
        audit_bootstrap=int(audit_bootstrap),
        audit_subsample=0.8,
        audit_seed_trials=int(seed_trials),
        audit_noise_sigma=0.01,
        audit_noise_trials=int(noise_trials),
    )


def composite_score(sil, dunn, dbi, stab: dict) -> float:
    bs = stab.get("bootstrap", {})
    seed = stab.get("seed_sensitivity", {})
    noise = stab.get("noise_robustness", {})

    def nz(x, neutral=0.0):
        return x if (x is not None and np.isfinite(x)) else neutral

    rho = nz(bs.get("spearman_rho_mean"))
    jac = nz(bs.get("jaccard_at_k_mean"))
    sil_std = nz(bs.get("silhouette_std"))
    dunn_std = nz(bs.get("dunn_std"))
    dbi_std = nz(bs.get("dbi_std"))
    rho_seed = nz(seed.get("spearman_rho_mean"))
    rho_noise = nz(noise.get("spearman_rho_mean"))

    sil = nz(sil); dunn = nz(dunn); dbi = nz(dbi)

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


def read_stability(output_csv_path: Path) -> dict:
    stab_path = Path(str(output_csv_path).replace(".csv", "_stability.json"))
    if stab_path.exists():
        with open(stab_path, "r") as f:
            return json.load(f)
    return {}


def run_one(args_tuple):
    """
    Worker for parallel pool:
    (stage_idx, params, stage_dir, input_csv, audit_bootstrap, seed_trials, noise_trials, ae_epochs)
    """
    stage_idx, params, stage_dir, input_csv, audit_bootstrap, seed_trials, noise_trials, ae_epochs = args_tuple
    t0 = time.time()
    try:
        args = build_args(
            params,
            stage_dir,
            input_csv,
            audit_bootstrap,
            seed_trials,
            noise_trials,
            ae_epochs=ae_epochs,
        )
        sil, dunn, dbi = run_pipeline(args)

        stab = read_stability(Path(args.output))
        score = composite_score(sil, dunn, dbi, stab)
        dur = time.time() - t0

        row = {
            **params,
            "stage": stage_idx,
            "silhouette": sil,
            "dunn": dunn,
            "dbi": dbi,
            "score": score,
            "time_sec": round(dur, 2),
            "rho_bootstrap": stab.get("bootstrap", {}).get("spearman_rho_mean", np.nan),
            "jacc_topk": stab.get("bootstrap", {}).get("jaccard_at_k_mean", np.nan),
            "rho_seed": stab.get("seed_sensitivity", {}).get("spearman_rho_mean", np.nan),
            "rho_noise": stab.get("noise_robustness", {}).get("spearman_rho_mean", np.nan),
            "out_dir": str(stage_dir),
        }
        return row
    except Exception as e:
        return {**params, "stage": stage_idx, "error": str(e), "score": -1e9}


def _epochs_for_stage(row_frac: float) -> int:
    """
    Simple dynamic scaling rule:
      - Stage with ~40% rows → 0.5 * BASE
      - Stage with ~75% rows → 0.75 * BASE
      - Stage with 100% rows → 1.0 * BASE
    """
    if row_frac >= 0.99:
        factor = 1.0
    elif row_frac >= 0.7:
        factor = 0.75
    else:
        factor = 0.5
    return max(15, int(BASE_AE_EPOCHS * factor))


def stage_run(
    stage_idx: int,
    params_list: list[dict],
    row_frac: float,
    audit_bootstrap: int,
    seed_trials: int,
    noise_trials: int,
    label: str,
):
    """
    Run a stage on a list of params with subsampled input and specified audit;
    returns results DataFrame.
    """
    stage_root = RUNS_DIR / f"stage{stage_idx}_{label}"
    stage_root.mkdir(parents=True, exist_ok=True)

    input_csv = stage_root / "input.csv"
    n_rows = subsample_csv(INPUT_PATH, input_csv, row_frac, seed=SEED + stage_idx)

    # Compute AE epochs for this stage
    stage_ae_epochs = _epochs_for_stage(row_frac)

    jobs = []
    for p in params_list:
        trial_dir = stage_root / combo_hash(p)
        trial_dir.mkdir(parents=True, exist_ok=True)
        jobs.append(
            (
                stage_idx,
                p,
                trial_dir,
                str(input_csv),
                audit_bootstrap,
                seed_trials,
                noise_trials,
                stage_ae_epochs,
            )
        )

    print(f"\n[Stage {stage_idx}] {len(params_list)} configs | rows={n_rows} | "
          f"audit_bootstrap={audit_bootstrap} | seed_trials={seed_trials} | "
          f"noise_trials={noise_trials} | ae_epochs={stage_ae_epochs}")

    with mp.Pool(processes=N_WORKERS) as pool:
        rows = pool.map(run_one, jobs)

    df = pd.DataFrame(rows)
    df.sort_values("score", ascending=False, inplace=True)
    df.to_csv(stage_root / "results.csv", index=False)

    # Just to show something meaningful, print top 3 (if any rows exist)
    if not df.empty:
        cols_for_print = ["score", "silhouette", "dunn", "dbi"]
        extra_keys = [k for k in SPACE.keys() if k in df.columns]
        print(f"[Stage {stage_idx}] Top 3:")
        print(df[cols_for_print + extra_keys].head(3))

    return df


def main():
    # Stage 1: sample N1 candidates via Sobol (or RNG)
    np.random.seed(SEED)
    candidates = discrete_sample_sobol(SPACE, N1, SEED)
    if len(candidates) < N1:
        # pad with RNG if sobol dedup shrank count
        needed = N1 - len(candidates)
        rng = np.random.default_rng(SEED + 99)
        keys = list(SPACE.keys())
        existing = {json.dumps(c, sort_keys=True) for c in candidates}
        while needed > 0:
            cand = {k: SPACE[k][rng.integers(0, len(SPACE[k]))] for k in keys}
            if cand["use_pca"] == 1:
                cand["use_fa"] = 0
            if cand["use_hdbscan"] == 0:
                cand["hdb_min_cluster"] = SPACE["hdb_min_cluster"][0]
            cano = json.dumps(cand, sort_keys=True)
            if cano not in existing:
                candidates.append(cand)
                existing.add(cano)
                needed -= 1

    # Stage 1 run
    s1_frac, s1_bs, s1_seed, s1_noise = STAGES[0]
    df1 = stage_run(
        stage_idx=1,
        params_list=candidates,
        row_frac=s1_frac,
        audit_bootstrap=s1_bs,
        seed_trials=s1_seed,
        noise_trials=s1_noise,
        label="wide",
    )

    # Promote top fraction
    k2 = max(6, int(np.ceil(len(df1) * KEEP_FRAC)))
    params2 = df1.head(k2)[[k for k in SPACE.keys()]].to_dict(orient="records")

    # Stage 2 run
    s2_frac, s2_bs, s2_seed, s2_noise = STAGES[1]
    df2 = stage_run(
        stage_idx=2,
        params_list=params2,
        row_frac=s2_frac,
        audit_bootstrap=s2_bs,
        seed_trials=s2_seed,
        noise_trials=s2_noise,
        label="medium",
    )

    # Promote finalists
    k3 = max(3, int(np.ceil(len(df2) * KEEP_FRAC)))
    params3 = df2.head(k3)[[k for k in SPACE.keys()]].to_dict(orient="records")

    # Stage 3 run (full data)
    s3_frac, s3_bs, s3_seed, s3_noise = STAGES[2]
    df3 = stage_run(
        stage_idx=3,
        params_list=params3,
        row_frac=s3_frac,
        audit_bootstrap=s3_bs,
        seed_trials=s3_seed,
        noise_trials=s3_noise,
        label="deep",
    )

    # Consolidate
    final_csv = RUNS_DIR / "asha_summary.csv"
    all_df = pd.concat(
        [
            df1.assign(stage_name="S1"),
            df2.assign(stage_name="S2"),
            df3.assign(stage_name="S3"),
        ],
        ignore_index=True,
    )
    all_df.to_csv(final_csv, index=False)

    # Print winner (best in Stage 3 if present, else best overall)
    if not df3.empty:
        best_row = df3.iloc[0].to_dict()
    else:
        best_row = all_df.sort_values("score", ascending=False).iloc[0].to_dict()

    best_params = {k: best_row[k] for k in SPACE.keys()}
    print("\n[OK] Best configuration:")
    print(best_params)
    print(
        f"Score: {best_row['score']:.4f} | Sil={best_row['silhouette']:.3f} | "
        f"Dunn={best_row['dunn']:.3f} | DBI={best_row['dbi']:.3f}"
    )
    print(f"Results written to: {final_csv}")
    print(f"Artifacts under: {RUNS_DIR.resolve()}")


if __name__ == "__main__":
    main()
