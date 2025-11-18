# backend/ml/pipeline.py
import sys
import time
import subprocess
from pathlib import Path

from .registry import save_new_model_version
from .diagnostics import generate_all_diagnostics

HERE = Path(__file__).resolve().parent          # backend/ml
REPO_ROOT = HERE.parent.parent                  # repo root (EECE-490-Project-4)
RUN_FUSED = REPO_ROOT / "src" / "scripts" / "run_fused_pipeline.py"


def run_full_training_pipeline(mode: str):
    start = time.time()
    print(f"[TRAIN] Starting training with mode={mode}", flush=True)
    print(f"[TRAIN] Repo root resolved to: {REPO_ROOT}", flush=True)
    print(f"[TRAIN] Using script: {RUN_FUSED}", flush=True)

    try:
        cmd = [
            sys.executable,
            str(RUN_FUSED),   # direct script path
            "--mode",
            mode,
        ]
        print(f"[TRAIN] Running: {' '.join(cmd)}", flush=True)

        completed = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )

        # Always show stdout/stderr in worker logs
        if completed.stdout:
            print("[TRAIN] stdout:", flush=True)
            print(completed.stdout, flush=True)
        if completed.stderr:
            print("[TRAIN] stderr:", flush=True)
            print(completed.stderr, flush=True)

        if completed.returncode != 0:
            raise RuntimeError(
                f"run_fused_pipeline failed with code {completed.returncode}"
            )

        duration = time.time() - start
        print(f"[TRAIN] Training finished in {duration:.2f} seconds (mode={mode})", flush=True)

        # Path to fused scores (what run_fused_pipeline writes)
        scores_csv = REPO_ROOT / "data" / "processed" / "anomaly_scores.csv"

        # 1) Register model (creates model card + history)
        card = save_new_model_version(
            scores_csv=scores_csv,
            mode=mode,
            duration_sec=duration,
            source_path="data/latest_ingested.csv",
        )

        # 2) Generate static diagnostics
        generate_all_diagnostics(scores_csv, card)

        return {
            "status": "completed",
            "mode": mode,
            "duration_sec": round(duration, 2),
            "model_card": card,
        }

    except Exception as e:
        print(f"[TRAIN] ERROR: {e}", flush=True)
        return {
            "status": "failed",
            "mode": mode,
            "error": str(e),
        }
