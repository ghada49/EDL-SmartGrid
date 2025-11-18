# src/scripts/run_ocsvm_baseline_pipeline.py
from __future__ import annotations

import sys
import argparse
from pathlib import Path

# ---------- PATH SETUP ----------
HERE = Path(__file__).resolve().parent          # .../src/scripts
REPO_ROOT = HERE.parent.parent                  # repo root
SRC_DIR = REPO_ROOT / "src"

for p in [REPO_ROOT, SRC_DIR]:
    if str(p) not in sys.path:
        sys.path.append(str(p))

# 1) preprocessing entry point (this should write data/processed/processed_data.csv)
from tests.feature_engineering_test import main as fe_main

# 2) OCSVM baseline
from models.ocsvm_baseline import run_ocsvm_baseline

# 3) OCSVM tuner
from scripts.tune_ocsvm import tune as tune_ocsvm


# ---------- DEFAULT PATHS ----------
PROCESSED_CSV_DEFAULT = REPO_ROOT / "data" / "processed" / "processed_data.csv"
OCSVM_OUT_DEFAULT = REPO_ROOT / "data" / "processed" / "ocsvm_baseline_scores.csv"
OCSVM_TUNING_CSV_DEFAULT = REPO_ROOT / "data" / "processed" / "tuning_ocsvm.csv"


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


# ---------- STEP 2: hyperparameter tuning ----------
def step_tune_ocsvm(
    processed_csv: Path,
    *,
    n_iter: int,
    seeds: list[int],
    random_seed: int,
    results_csv: Path,
    quiet: bool,
) -> dict:
    print("[Step 2] Running OCSVM hyperparameter tuning...")
    best = tune_ocsvm(
        input_csv=str(processed_csv),
        n_iter=n_iter,
        seeds=tuple(seeds),
        random_seed=random_seed,
        results_csv=str(results_csv),
        quiet=quiet,
    )

    # 'best' is a dict from the top row of tuning df
    print("\n[Step 2] Best OCSVM configuration from tuning:")
    for k, v in best.items():
        print(f"  {k:>15}: {v}")

    return best


# ---------- STEP 3: OCSVM baseline with chosen config ----------
def step_ocsvm_baseline(
    processed_csv: Path,
    output_csv: Path,
    *,
    contamination: float,
    nu: float,
    kernel: str,
    gamma: str | float,
    degree: int,
    coef0: float,
    use_pca: bool,
    pca_var: float,
    scaler_type: str,
    seed: int,
    quiet: bool,
    skip_save: bool,
) -> None:
    print("\n[Step 3] Running One-Class SVM baseline with selected hyperparameters")
    sil, dunn, dbi = run_ocsvm_baseline(
        input_csv=str(processed_csv),
        output_csv=str(output_csv),
        contamination=contamination,
        nu=nu,
        kernel=kernel,
        gamma=gamma,
        degree=degree,
        coef0=coef0,
        use_pca=use_pca,
        pca_var=pca_var,
        scaler_type=scaler_type,
        seed=seed,
        quiet=quiet,
        skip_save=skip_save,
    )

    if not quiet:
        print(f"[Pipeline] OCSVM metrics -> Sil={sil:.3f}, Dunn={dunn:.3f}, DBI={dbi:.3f}")
        print(f"[Pipeline] Scores saved to: {output_csv}")


# ---------- CLI ENTRYPOINT ----------
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run preprocessing + OCSVM tuning + OCSVM baseline pipeline"
    )

    # Paths
    ap.add_argument(
        "--processed_csv",
        type=str,
        default=str(PROCESSED_CSV_DEFAULT),
        help="Path to processed_data.csv (output of preprocessing).",
    )
    ap.add_argument(
        "--output_csv",
        type=str,
        default=str(OCSVM_OUT_DEFAULT),
        help="Where to save OCSVM baseline scores.",
    )
    ap.add_argument(
        "--skip_preprocess_if_exists",
        type=int,
        default=1,
        help="1 = skip preprocessing if processed_csv exists, 0 = always rerun.",
    )

    # ---- TUNING CONTROL ----
    ap.add_argument(
        "--do_tuning",
        type=int,
        default=1,
        help="1 = run OCSVM tuning and use best config, 0 = skip tuning and use CLI OCSVM params.",
    )
    ap.add_argument(
        "--tune_n_iter",
        type=int,
        default=80,
        help="Number of random configs to try in OCSVM tuning.",
    )
    ap.add_argument(
        "--tune_seeds",
        type=int,
        nargs="+",
        default=[13, 21, 42],
        help="List of seeds for stability evaluation in tuning.",
    )
    ap.add_argument(
        "--tune_random_seed",
        type=int,
        default=2025,
        help="Random seed controlling the hyperparameter sampling itself.",
    )
    ap.add_argument(
        "--tune_results_csv",
        type=str,
        default=str(OCSVM_TUNING_CSV_DEFAULT),
        help="Where to save the tuning results CSV.",
    )

    # ---- OCSVM PARAMS (used if do_tuning = 0, or as defaults) ----
    ap.add_argument("--contamination", type=float, default=0.03)
    ap.add_argument("--nu", type=float, default=0.045)
    ap.add_argument("--kernel", type=str, default="sigmoid")
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

    processed_csv = Path(args.processed_csv)
    output_csv = Path(args.output_csv)
    tuning_csv = Path(args.tune_results_csv)

    # Step 1: preprocessing
    step_preprocess(
        processed_csv=processed_csv,
        skip_if_exists=bool(args.skip_preprocess_if_exists),
    )

    # Step 2: tuning (optional)
    best_cfg: dict | None = None
    if bool(args.do_tuning):
        best_cfg = step_tune_ocsvm(
            processed_csv=processed_csv,
            n_iter=args.tune_n_iter,
            seeds=args.tune_seeds,
            random_seed=args.tune_random_seed,
            results_csv=tuning_csv,
            quiet=bool(args.quiet),
        )

    # Decide which hyperparameters to use for the final baseline run
    if best_cfg is not None:
        contamination = float(best_cfg["contamination"])
        nu = float(best_cfg["nu"])
        kernel = str(best_cfg["kernel"])
        gamma = str(best_cfg["gamma"])
        degree = int(best_cfg["degree"])
        coef0 = float(best_cfg["coef0"])
        use_pca = bool(best_cfg["use_pca"])
        pca_var = float(best_cfg["pca_var"])
        scaler_type = str(best_cfg["scaler"])
        print("\n[Pipeline] Using tuned OCSVM hyperparameters for final baseline run.")
    else:
        # Use CLI defaults / user-provided values
        contamination = args.contamination
        nu = args.nu
        kernel = args.kernel
        gamma = args.gamma
        degree = args.degree
        coef0 = args.coef0
        use_pca = bool(args.use_pca)
        pca_var = args.pca_var
        scaler_type = args.scaler
        print("\n[Pipeline] Using CLI OCSVM hyperparameters (no tuning).")

    # Step 3: final OCSVM baseline
    step_ocsvm_baseline(
        processed_csv=processed_csv,
        output_csv=output_csv,
        contamination=contamination,
        nu=nu,
        kernel=kernel,
        gamma=gamma,
        degree=degree,
        coef0=coef0,
        use_pca=use_pca,
        pca_var=pca_var,
        scaler_type=scaler_type,
        seed=args.seed,
        quiet=bool(args.quiet),
        skip_save=bool(args.skip_save),
    )


if __name__ == "__main__":
    main()
