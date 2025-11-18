# src/scripts/tune_ocsvm.py
"""
Randomized hyperparameter tuning for the One-Class SVM baseline.

Usage (from repo root):

  python -m src.scripts.tune_ocsvm \
      --input data/processed/processed_data.csv \
      --n_iter 80 \
      --seeds 13 21 42 \
      --results_csv data/processed/tuning_ocsvm.csv
"""

from __future__ import annotations

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd
from argparse import Namespace

# Ensure src/ is importable
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from models.ocsvm_baseline import run_ocsvm_baseline


def composite_score(sil: float, dunn: float, dbi: float) -> float:
    """
    Combine unsupervised metrics into a single scalar.
    Higher is better.
    """
    def nz(x):
        return x if (x is not None and np.isfinite(x)) else 0.0

    sil = nz(sil)
    dunn = nz(dunn)
    dbi = nz(dbi)

    # You can tune these weights, but this is consistent with your earlier idea:
    return 0.7 * sil + 0.25 * dunn - 0.15 * dbi


def sample_config(rng: np.random.RandomState) -> dict:
    """
    Sample one hyperparameter configuration for OCSVM.
    Tuned ranges are small but meaningful.
    """
    cfg = dict(
        contamination=float(rng.choice([0.02, 0.03, 0.04, 0.05])),
        nu=float(rng.uniform(0.01, 0.10)),
        kernel=str(rng.choice(["rbf", "sigmoid", "poly"])),
        gamma=str(rng.choice(["scale", "auto"])),
        degree=int(rng.choice([2, 3, 4])),
        coef0=float(rng.choice([0.0, 0.5, 1.0])),
        use_pca=bool(rng.choice([1, 0])),
        pca_var=float(rng.choice([0.95, 0.98])),
        scaler=str(rng.choice(["robust", "standard"])),
    )

    # If kernel is not poly or sigmoid, coef0 is irrelevant; keep it anyway for consistency.
    if cfg["kernel"] == "rbf":
        # degree and coef0 not used; we keep them but they won't harm.
        pass

    return cfg


def tune(
    input_csv: str,
    n_iter: int = 80,
    seeds: tuple[int, ...] = (13, 21, 42),
    random_seed: int = 2025,
    results_csv: str = "data/processed/tuning_ocsvm.csv",
    quiet: bool = False,
) -> dict:
    rng = np.random.RandomState(random_seed)
    rows = []
    t0 = time.time()

    for i in range(1, n_iter + 1):
        cfg = sample_config(rng)

        sils, duns, dbis = [], [], []
        for s in seeds:
            sil, dunn, dbi = run_ocsvm_baseline(
                input_csv=input_csv,
                output_csv="data/processed/_ocsvm_tuning_tmp.csv",
                contamination=cfg["contamination"],
                nu=cfg["nu"],
                kernel=cfg["kernel"],
                gamma=cfg["gamma"],
                degree=cfg["degree"],
                coef0=cfg["coef0"],
                use_pca=cfg["use_pca"],
                pca_var=cfg["pca_var"],
                scaler_type=cfg["scaler"],
                seed=int(s),
                quiet=True,
                skip_save=True,  # don't write CSV for each trial
            )
            sils.append(sil)
            duns.append(dunn)
            dbis.append(dbi)

        m = dict(
            sil_mu=float(np.nanmean(sils)),
            sil_sd=float(np.nanstd(sils)),
            dunn_mu=float(np.nanmean(duns)),
            dunn_sd=float(np.nanstd(duns)),
            dbi_mu=float(np.nanmean(dbis)),
            dbi_sd=float(np.nanstd(dbis)),
        )
        score = composite_score(m["sil_mu"], m["dunn_mu"], m["dbi_mu"])

        row = {
            "iter": i,
            "score": score,
            **m,
            **cfg,
        }
        rows.append(row)

        if not quiet:
            print(
                f"[{i:02d}/{n_iter}] score={score:.3f} | "
                f"Sil μ={m['sil_mu']:.3f}±{m['sil_sd']:.3f}, "
                f"Dunn μ={m['dunn_mu']:.3f}±{m['dunn_sd']:.3f}, "
                f"DBI μ={m['dbi_mu']:.3f}±{m['dbi_sd']:.3f} | "
                f"cfg={json.dumps(cfg)}"
            )

    df = pd.DataFrame(rows).sort_values("score", ascending=False)
    os.makedirs(os.path.dirname(results_csv), exist_ok=True)
    df.to_csv(results_csv, index=False)

    if not quiet:
        print("\n=== Top 10 OCSVM configs by composite score ===")
        print(
            df.head(10)[
                [
                    "score", "sil_mu", "dunn_mu", "dbi_mu",
                    "contamination", "nu", "kernel", "gamma",
                    "degree", "coef0", "use_pca", "pca_var", "scaler",
                ]
            ].to_string(index=False, float_format=lambda x: f"{x:.3f}")
        )
        print(f"\nSaved all OCSVM trials → {results_csv}")
        print(f"Total tuning time: {time.time() - t0:.1f}s")

    best = df.iloc[0].to_dict()
    return best


def main():
    p = argparse.ArgumentParser(description="Randomized OCSVM baseline tuning")
    p.add_argument("--input", type=str, default="data/processed/processed_data.csv")
    p.add_argument("--n_iter", type=int, default=80)
    p.add_argument("--seeds", type=int, nargs="+", default=[13, 21, 42])
    p.add_argument("--random_seed", type=int, default=2025)
    p.add_argument("--results_csv", type=str, default="data/processed/tuning_ocsvm.csv")
    p.add_argument("--quiet", type=int, default=0)
    args = p.parse_args()

    best = tune(
        input_csv=args.input,
        n_iter=args.n_iter,
        seeds=tuple(args.seeds),
        random_seed=args.random_seed,
        results_csv=args.results_csv,
        quiet=bool(args.quiet),
    )
    print("\nBest OCSVM configuration:")
    for k, v in best.items():
        print(f"{k:>15}: {v}")


if __name__ == "__main__":
    main()
