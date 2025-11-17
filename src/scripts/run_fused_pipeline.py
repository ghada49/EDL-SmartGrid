# src/scripts/run_fused_pipeline.py
"""
End-to-end fused anomaly pipeline orchestrator.

Steps:
1. Preprocess raw data -> data/processed/processed_data.csv
   (reuses tests/feature_engineering_test.main)
2. Hyperparameter tuning (mode-dependent: fast/moderate/slow/very_slow)
   (calls one of the src/scripts/tune_* modules as a separate process)
3. Final fused run with best configuration
   (reuses models.train_models.run_pipeline)
"""

from __future__ import annotations

import sys
import subprocess
import argparse
from pathlib import Path

import pandas as pd

# ---------- PATH SETUP ----------
HERE = Path(__file__).resolve().parent          # .../src/scripts
REPO_ROOT = HERE.parent.parent                  # repo root
SRC_DIR = REPO_ROOT / "src"

for p in [REPO_ROOT, SRC_DIR]:
    if str(p) not in sys.path:
        sys.path.append(str(p))

# 1) preprocessing
from tests.feature_engineering_test import main as fe_main

# 3) fused model
from models.train_models import run_pipeline

# ---------- DEFAULT PATHS ----------
PROCESSED_CSV_DEFAULT = REPO_ROOT / "data" / "processed" / "processed_data.csv"
FINAL_FUSED_OUT_DEFAULT = REPO_ROOT / "data" / "processed" / "anomaly_scores.csv"


# ---------- STEP 1: preprocessing ----------

def step_preprocess(processed_csv: Path, skip_if_exists: bool) -> None:
    processed_csv.parent.mkdir(parents=True, exist_ok=True)

    if skip_if_exists and processed_csv.exists():
        print(f"[Step 1] Skipping preprocessing (found {processed_csv})")
        return

    print("[Step 1] Running preprocessing via tests.feature_engineering_test.main()")
    fe_main()  # this already writes processed_data.csv

    if not processed_csv.exists():
        raise FileNotFoundError(
            f"Expected processed CSV not found at {processed_csv} after preprocessing."
        )

    print(f"[Step 1] Preprocessing complete -> {processed_csv}")


# ---------- STEP 2: tuning via separate process ----------

def step_tune_fused(
    processed_csv: Path,
    mode: str,
    summary_override: Path | None,
    skip_if_exists: bool,
    python_exe: str = sys.executable,
) -> pd.Series:
    """
    Run the appropriate tuner as a *separate* Python process based on `mode`,
    then read its summary CSV and return the best row (highest score).
    """

    # Choose tuner module and its default summary path
    if mode == "fast":
        tuner_module = "src.scripts.tune_anomaly_pipeline_fast"
        default_summary = REPO_ROOT / "data" / "tuning_runs_fast" / "tuning_results_fast.csv"
    elif mode == "slow":
        tuner_module = "src.scripts.tune_fused_slow"
        default_summary = REPO_ROOT / "data" / "tuning_runs" / "tuning_results.csv"
    elif mode == "very_slow":
        tuner_module = "src.scripts.tune_full_grid"
        default_summary = REPO_ROOT / "data" / "tuning_runs" / "tuning_results.csv"
    else:  # "moderate" (ASHA)
        tuner_module = "src.scripts.tune_hyperparameters"
        default_summary = REPO_ROOT / "data" / "tuning_runs_asha" / "asha_summary.csv"

    summary_csv = summary_override or default_summary

    if skip_if_exists and summary_csv.exists():
        print(f"[OK] [Step 2] Skipping tuning (found {summary_csv})")
    else:
        print(f"[>>>] [Step 2] Launching tuner '{tuner_module}' in mode={mode}")
        cmd = [
            python_exe,
            "-m",
            tuner_module,
        ]
        # This will run main() inside the tuner module
        completed = subprocess.run(cmd, cwd=str(REPO_ROOT))
        if completed.returncode != 0:
            raise RuntimeError(f"{tuner_module} failed; see console output for details.")

        if not summary_csv.exists():
            raise FileNotFoundError(
                f"Expected tuning summary not found at {summary_csv} "
                f"after running {tuner_module}"
            )

    print(f"[OK] [Step 2] Reading best config from {summary_csv}")
    df = pd.read_csv(summary_csv)
    if df.empty:
        raise ValueError(f"{summary_csv} is empty.")

    df_sorted = df.sort_values("score", ascending=False)
    best = df_sorted.iloc[0]
    print("\n[OK] Best fused configuration (from tuner summary):")
    # Only print hyperparam columns + key metrics
    cols_show = [c for c in df.columns if c in (
        "score", "silhouette", "dunn", "dbi",
        "contamination", "use_pca", "use_fa",
        "lof_neighbors", "if_estimators", "if_max_features",
        "use_ae", "use_ocsvm", "use_copula",
        "use_hdbscan", "hdb_min_cluster"
    )]
    print(best[cols_show].to_string())

    return best


# ---------- STEP 3: final fused run ----------

def step_run_final_fused(processed_csv: Path, out_csv: Path, best_row: pd.Series) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    # Extract hyperparameters from best_row; fall back to defaults if missing
    def get(name, default=None, cast_fn=None):
        if name in best_row and pd.notna(best_row[name]):
            val = best_row[name]
        else:
            val = default
        if cast_fn is not None and val is not None:
            return cast_fn(val)
        return val

    args_ns = argparse.Namespace(
        input=str(processed_csv),
        output=str(out_csv),
        contamination=get("contamination", 0.05, float),
        cv_folds=5,
        use_pca=bool(get("use_pca", 1)),
        use_fa=bool(get("use_fa", 0)),
        if_estimators=get("if_estimators", 100, int),
        if_max_features=get("if_max_features", 0.8, float),
        if_bootstrap=False,
        lof_neighbors=get("lof_neighbors", 30, int),
        use_ae=bool(get("use_ae", 1)),
        ae_epochs=60,
        ae_batch=64,
        seed=42,
        sweep_thresholds=False,
        quiet=False,
        skip_save=False,
        use_ocsvm=bool(get("use_ocsvm", 1)),
        use_hdbscan=bool(get("use_hdbscan", 0)),
        hdb_min_cluster=get("hdb_min_cluster", 20, int),
        hdb_min_samples=0,
        use_gmm=False,
        gmm_components=2,
        use_copula=bool(get("use_copula", 1)),
        use_vae=False,
        vae_latent=8,
        fuse_weights="",          # you can hard-code IF/LOF/OCSVM/AE/COPULA weights if you want
        audit_bootstrap=12,
        audit_subsample=0.8,
        audit_seed_trials=3,
        audit_noise_sigma=0.01,
        audit_noise_trials=3,
    )

    print("\n[>>>] [Step 3] Running final fused model with best configuration")
    sil, dunn, dbi = run_pipeline(args_ns)

    print(f"\n[OK] [Step 3] Final fused metrics on full data:")
    print(f"   Silhouette = {sil:.3f}")
    print(f"   Dunn       = {dunn:.3f}")
    print(f"   DBI        = {dbi:.3f}")
    print(f"[OK] Saved fused anomaly scores -> {out_csv}")


# ---------- MAIN ----------

def main():
    ap = argparse.ArgumentParser(
        description=(
            "End-to-end fused pipeline: preprocess → tuning "
            "(fast/moderate/slow/very_slow) → final fused run."
        )
    )
    ap.add_argument(
        "--processed",
        type=str,
        default=str(PROCESSED_CSV_DEFAULT),
        help="Path to processed_data.csv.",
    )
    ap.add_argument(
        "--tuning_summary",
        type=str,
        default="",
        help="Optional override for tuner summary CSV path (otherwise derived from mode).",
    )
    ap.add_argument(
        "--output",
        type=str,
        default=str(FINAL_FUSED_OUT_DEFAULT),
        help="Final fused anomaly scores CSV path.",
    )
    ap.add_argument(
        "--skip_preprocess",
        action="store_true",
        help="Skip preprocessing if processed_data.csv already exists.",
    )
    ap.add_argument(
        "--skip_tune",
        action="store_true",
        help="Skip calling the tuner if summary CSV already exists.",
    )
    ap.add_argument(
        "--mode",
        type=str,
        choices=["fast", "moderate", "slow", "very_slow"],
        default="moderate",
        help="Tuning mode: fast | moderate (ASHA) | slow | very_slow (full grid).",
    )

    args = ap.parse_args()

    processed_csv = Path(args.processed).resolve()
    summary_override = Path(args.tuning_summary).resolve() if args.tuning_summary else None
    out_csv = Path(args.output).resolve()

    print("========== FUSED PIPELINE START ==========")
    print(f"Processed CSV : {processed_csv}")
    print(f"Mode          : {args.mode}")
    print(f"Tuning summary override: {summary_override if summary_override else '(auto-derived)'}")
    print(f"Final output  : {out_csv}")

    # 1) preprocessing
    step_preprocess(processed_csv=processed_csv, skip_if_exists=args.skip_preprocess)

    # 2) tuning (separate process)
    best_row = step_tune_fused(
        processed_csv=processed_csv,
        mode=args.mode,
        summary_override=summary_override,
        skip_if_exists=args.skip_tune,
    )

    # 3) final fused run
    step_run_final_fused(processed_csv=processed_csv, out_csv=out_csv, best_row=best_row)

    print("========== FUSED PIPELINE DONE ==========")


if __name__ == "__main__":
    main()
