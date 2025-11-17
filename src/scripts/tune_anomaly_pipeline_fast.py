# scripts/tune_anomaly_pipeline_fast.py
# Fast / web-friendly tuning for run_pipeline:
# - Randomly samples a subset of configs from a grid (no 960-run brute force)
# - Uses lighter training settings (fewer CV folds)
# - Disables heavy stability audit during tuning (bootstrap/seed/noise)
# - Still uses composite_score (Silhouette, Dunn, DBI + stability when present)
# - Early-stopping logic:
#     * patience-based: when no improvement within a contamination level,
#       move to the next contamination value instead of stopping the whole search.
#     * optional time budget (--max_time_sec)

import os
import sys
import json
import hashlib
import itertools
import time
from argparse import Namespace, ArgumentParser
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure we can import your pipeline
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from models.train_models import run_pipeline  # your enhanced run_pipeline


# ---------------- Configuration ----------------

# Default input (can be overridden by CLI)
DEFAULT_INPUT_PATH = "data/processed/processed_data.csv"

# Directory to store per-trial outputs (meta + stability JSON)
OUT_DIR = Path("data/tuning_runs_fast")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Primary parameter grid.
# NOTE:
# - This grid is reasonably rich for academic scrutiny.
# - For a *very fast web mode*, you can narrow some lists (e.g., use_ae=[0], use_hdbscan=[0]).
param_grid = {
    "contamination":   [0.02, 0.04, 0.06],   # main anomaly rate knob
    "use_pca":         [1, 0],               # PCA vs raw/FA
    "use_fa":          [0, 1],               # FA only meaningful if use_pca=0
    "lof_neighbors":   [20, 40],             # LOF k
    "if_estimators":   [100, 200],           # IF trees
    "if_max_features": [0.6, 0.8, 1.0],
    "use_ae":          [1, 0],               # AE on/off (heavier; for pure speed set [0])
    "use_ocsvm":       [1, 0],
    "use_copula":      [1, 0],
    "use_hdbscan":     [0, 1],               # can toggle HDBSCAN in fast tuner too
    "hdb_min_cluster": [20],                 # only used if use_hdbscan=1
}

# Lighter defaults for *tuning* (web/interactive friendly)
DEFAULTS = dict(
    cv_folds=3,            # lighter than 5, still sane
    ae_epochs=30,          # if AE is enabled in tuning, keep it modest
    ae_batch=64,
    seed=42,
    sweep_thresholds=0,
    if_bootstrap=0,
    use_vae=0,
    vae_latent=8,
    use_gmm=0,
    gmm_components=2,
    fuse_weights="",

    # Very light stability audit DURING tuning
    audit_bootstrap=0,     # 0 → no bootstrap refits
    audit_subsample=0.8,
    audit_seed_trials=0,   # 0 → skip seed sensitivity
    audit_noise_sigma=0.01,
    audit_noise_trials=0,  # 0 → skip noise robustness
)

# Composite score weights (same spirit as your heavy tuner)
W_SIL, W_DUNN, W_DBI = 0.50, 0.40, 0.10
W_RHO, W_JAC, W_SEED, W_NOISE = 0.20, 0.15, 0.10, 0.10
P_SIL_STD, P_DUNN_STD, P_DBI_STD = 0.10, 0.10, 0.05


# ---------------- Utilities ----------------

def combo_hash(params: dict) -> str:
    """Deterministic short hash for a parameter combo (for unique output paths)."""
    key = json.dumps(params, sort_keys=True)
    return hashlib.md5(key.encode()).hexdigest()[:10]


def build_args(params: dict, input_path: str, output_base: Path) -> Namespace:
    """
    Build the argparse Namespace that run_pipeline expects.
    Each trial writes to a unique base so meta/stability JSON don't collide.
    """
    out_csv = output_base / "anomaly_scores.csv"
    a = dict(
        input=input_path,
        output=str(out_csv),
        contamination=params["contamination"],
        cv_folds=DEFAULTS["cv_folds"],
        use_pca=bool(params["use_pca"]),
        use_fa=bool(params.get("use_fa", 0)),
        if_estimators=params["if_estimators"],
        if_max_features=params["if_max_features"],
        if_bootstrap=bool(DEFAULTS["if_bootstrap"]),
        lof_neighbors=params["lof_neighbors"],

        # AE: controllable via grid; modest epochs for tuning.
        use_ae=bool(params.get("use_ae", 0)),
        ae_epochs=DEFAULTS["ae_epochs"],
        ae_batch=DEFAULTS["ae_batch"],

        seed=DEFAULTS["seed"],
        sweep_thresholds=bool(DEFAULTS["sweep_thresholds"]),
        quiet=True,
        skip_save=False,   # must save to read stability JSON

        use_ocsvm=bool(params.get("use_ocsvm", 1)),
        use_hdbscan=bool(params.get("use_hdbscan", 0)),
        hdb_min_cluster=int(params.get("hdb_min_cluster", 20)),
        hdb_min_samples=0,

        use_gmm=bool(DEFAULTS["use_gmm"]),
        gmm_components=int(DEFAULTS["gmm_components"]),
        use_copula=bool(params.get("use_copula", 0)),
        use_vae=bool(DEFAULTS["use_vae"]),
        vae_latent=int(DEFAULTS["vae_latent"]),
        fuse_weights=str(DEFAULTS["fuse_weights"]),
        audit_bootstrap=int(DEFAULTS["audit_bootstrap"]),
        audit_subsample=float(DEFAULTS["audit_subsample"]),
        audit_seed_trials=int(DEFAULTS["audit_seed_trials"]),
        audit_noise_sigma=float(DEFAULTS["audit_noise_sigma"]),
        audit_noise_trials=int(DEFAULTS["audit_noise_trials"]),
    )
    return Namespace(**a)


def composite_score(sil, dunn, dbi, stab: dict) -> float:
    """
    Combine unsupervised partition quality with stability audit into a single score.
    Higher is better. For this *fast* tuner, most stability terms will be NaN/absent,
    so they default to 0 via nz().
    """
    bs = stab.get("bootstrap", {})
    seed = stab.get("seed_sensitivity", {})
    noise = stab.get("noise_robustness", {})

    rho = bs.get("spearman_rho_mean", np.nan)
    jac = bs.get("jaccard_at_k_mean", np.nan)
    ari = bs.get("ari_mean", np.nan)  # not used directly but kept for symmetry
    sil_std = bs.get("silhouette_std", np.nan)
    dunn_std = bs.get("dunn_std", np.nan)
    dbi_std = bs.get("dbi_std", np.nan)

    rho_seed = seed.get("spearman_rho_mean", np.nan)
    rho_noise = noise.get("spearman_rho_mean", np.nan)

    def nz(x, neutral=0.0):
        return x if (x is not None and np.isfinite(x)) else neutral

    sil, dunn, dbi = nz(sil), nz(dunn), nz(dbi)
    rho, jac = nz(rho), nz(jac)
    rho_seed, rho_noise = nz(rho_seed), nz(rho_noise)
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


def run_trial(params: dict, input_path: str) -> dict:
    """Run a single configuration and return a result row (dict)."""
    t0 = time.time()
    out_base = OUT_DIR / combo_hash(params)
    out_base.mkdir(parents=True, exist_ok=True)

    args = build_args(params, input_path, out_base)
    sil, dunn, dbi = run_pipeline(args)

    # Read stability JSON (may be minimal/empty in fast mode)
    stab_path = out_base / "anomaly_scores_stability.json"
    if not stab_path.exists():
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


# ---------------- Main (random subset of grid + contamination-wise patience) ----------------

def main():
    parser = ArgumentParser(
        description=(
            "Fast tuner for run_pipeline (random subset of grid, light audit). "
            "Patience triggers a switch to the next contamination value."
        )
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT_PATH,
        help="Processed CSV path for tuning (default: %(default)s).",
    )
    parser.add_argument(
        "--max_trials",
        type=int,
        default=40,
        help="Maximum number of configurations to evaluate (default: %(default)s).",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=10,
        help=(
            "Number of consecutive non-improving trials within a given "
            "contamination level before moving to the next one (default: %(default)s). "
            "Set 0 to disable this behavior."
        ),
    )
    parser.add_argument(
        "--max_time_sec",
        type=float,
        default=0.0,
        help="Optional global time budget in seconds (0 = no time limit).",
    )
    args = parser.parse_args()

    contamination_values = param_grid["contamination"]
    other_keys = [k for k in param_grid.keys() if k != "contamination"]

    # Total number of theoretical combos (for info only)
    total_combos = 0
    for _c in contamination_values:
        n = 1
        for k in other_keys:
            n *= len(param_grid[k])
        total_combos += n

    rng = np.random.default_rng(DEFAULTS["seed"])

    results = []
    best = None
    best_score = None
    trial_count = 0
    start_time = time.time()

    print(f"Input file: {args.input}")
    print(f"Max trials: {args.max_trials}")
    print(f"Global time budget (seconds): {'none' if args.max_time_sec <= 0.0 else args.max_time_sec}")
    print(f"Hyperspace theoretical size (all contaminations): {total_combos}")

    # Outer loop over contamination values (the "constant" we change when plateau)
    for ci, cont in enumerate(contamination_values, start=1):
        if trial_count >= args.max_trials:
            break

        # Build all combos for this contamination
        grids_for_cont = []
        for combo in itertools.product(*[param_grid[k] for k in other_keys]):
            p = {k: v for k, v in zip(other_keys, combo)}
            p["contamination"] = cont
            grids_for_cont.append(p)

        rng.shuffle(grids_for_cont)

        print(f"\n=== Exploring contamination = {cont} "
              f"({ci}/{len(contamination_values)}), "
              f"{len(grids_for_cont)} configs before budget cuts ===")

        no_improve = 0  # reset for each contamination level

        for params in grids_for_cont:
            if trial_count >= args.max_trials:
                print("Reached max_trials budget, stopping search.")
                break

            # Time-based early stopping
            if args.max_time_sec > 0.0:
                elapsed = time.time() - start_time
                if elapsed > args.max_time_sec:
                    print(f"\n⏱ Early stopping: exceeded time budget of {args.max_time_sec} seconds.")
                    print("Stopping search across all contaminations.")
                    trial_count = args.max_trials  # force outer break
                    break

            trial_count += 1
            print(f"\n[Trial {trial_count}] {params}")

            # Safety: ensure use_fa present when use_pca=0
            if not params["use_pca"] and ("use_fa" not in params):
                params["use_fa"] = 0

            try:
                row = run_trial(params, args.input)
                results.append(row)

                score = row["score"]
                print(
                    f"  → score={score:.4f}  "
                    f"sil={row['silhouette']:.3f}  "
                    f"dunn={row['dunn']:.3f}  "
                    f"dbi={row['dbi']:.3f}"
                )

                if (best is None) or (best_score is None) or (score > best_score):
                    best = row
                    best_score = score
                    no_improve = 0
                    print("  ✓ New global best configuration.")
                else:
                    no_improve += 1
                    if args.patience > 0:
                        print(f"  (no improvement at this contamination, no_improve={no_improve})")

                # If patience is enabled and plateau reached for this contamination,
                # move to the next contamination instead of stopping the whole search.
                if args.patience > 0 and no_improve >= args.patience:
                    print(
                        f"\n🔁 No improvement for {args.patience} trials at "
                        f"contamination={cont}. Moving to next contamination level."
                    )
                    break

            except Exception as e:
                print(f"  !! Failed: {e}")
                results.append(
                    {
                        **params,
                        "silhouette": np.nan,
                        "dunn": np.nan,
                        "dbi": np.nan,
                        "score": -1e9,
                        "error": str(e),
                    }
                )

        # Check global budgets after finishing this contamination block
        if trial_count >= args.max_trials:
            break
        if args.max_time_sec > 0.0 and (time.time() - start_time) > args.max_time_sec:
            break

        # Save results CSV (including partial runs if early-stopped / budgeted)
    df = pd.DataFrame(results)
    if not df.empty:
        # Sort by score descending
        df.sort_values("score", ascending=False, inplace=True)

    out_csv = OUT_DIR / "tuning_results_fast.csv"
    df.to_csv(out_csv, index=False)

    # Some diagnostics to understand what happened
    if not df.empty:
        # Heuristic: treat score <= -1e8 as "hard failure"
        num_trials = len(df)
        num_failed = int((df["score"] <= -1e8).sum())
        num_success = num_trials - num_failed
        print(f"\nTrials summary: total={num_trials}, success={num_success}, failed={num_failed}")
    else:
        print("\nTrials summary: no trials executed.")

    print("\n[OK] Best configuration:")
    if not df.empty:
        # Even if all runs failed, this will still pick the highest score row
        best_row = df.iloc[0]

        # Extract only hyperparameter keys from param_grid (plus use_fa safety)
        best_params = {
            k: best_row[k]
            for k in param_grid.keys()
            if k in best_row.index
        }
        # Also ensure use_fa is shown if present
        if "use_fa" in best_row.index and "use_fa" not in best_params:
            best_params["use_fa"] = best_row["use_fa"]

        print(best_params)
        print(
            f"Score: {best_row['score']:.4f} | "
            f"Sil={best_row['silhouette']:.3f} | "
            f"Dunn={best_row['dunn']:.3f} | "
            f"DBI={best_row['dbi']:.3f}"
        )

        # If this best row actually had an error, say it explicitly
        if "error" in best_row and isinstance(best_row["error"], str) and best_row["error"]:
            print(f"\n[WARN] Note: even the best row has error='{best_row['error']}'. "
                  "Check tuning_results_fast.csv for details.")
    else:
        print("No successful runs (all trials failed and no results were recorded).")

    print(f"\nTotal trials executed: {trial_count}")
    print(f"All trials saved to: {out_csv}")
    print(f"Per-trial artifacts under: {OUT_DIR.resolve()}")



if __name__ == "__main__":
    main()
