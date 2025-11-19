# backend/ml/pipeline.py
import sys
import time
import subprocess
from pathlib import Path

from .registry import save_new_model_version
from .diagnostics import generate_all_diagnostics
from .training_status import update_training_status

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
RUN_FUSED = REPO_ROOT / "src" / "scripts" / "run_fused_pipeline.py"


def run_full_training_pipeline(job_id: str, mode: str):
    start = time.time()
    print(f"[TRAIN] Starting training with mode={mode}", flush=True)
    print(f"[TRAIN] Repo root resolved to: {REPO_ROOT}", flush=True)
    print(f"[TRAIN] Using script: {RUN_FUSED}", flush=True)

    # Stage: initializing
    update_training_status(
        job_id,
        status="running",
        stage="initializing",
        progress=0.02,
    )

    try:
        cmd = [
            sys.executable,
            str(RUN_FUSED),
            "--mode",
            mode,
        ]
        print(f"[TRAIN] Running: {' '.join(cmd)}", flush=True)

        # Stage: core fused pipeline
        update_training_status(
            job_id,
            stage="core_pipeline",
            progress=0.10,
        )

        completed = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )

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

        scores_csv = REPO_ROOT / "data" / "processed" / "anomaly_scores.csv"

        # Stage: registry
        update_training_status(
            job_id,
            stage="registry",
            progress=0.70,
        )

        card = save_new_model_version(
            scores_csv=scores_csv,
            mode=mode,
            duration_sec=duration,
            source_path="data/latest_ingested.csv",
        )

        # Stage: diagnostics
        update_training_status(
            job_id,
            stage="diagnostics",
            progress=0.85,
        )

        generate_all_diagnostics(scores_csv, card)

        result = {
            "status": "completed",
            "mode": mode,
            "duration_sec": round(duration, 2),
            "model_card": card,
        }

        # Final stage
        update_training_status(
            job_id,
            status="completed",
            stage="completed",
            progress=1.0,
            result=result,
        )

        return result

    except Exception as e:
        print(f"[TRAIN] ERROR: {e}", flush=True)
        update_training_status(
            job_id,
            status="failed",
            stage="failed",
            progress=1.0,
            error=str(e),
        )
        return {
            "status": "failed",
            "mode": mode,
            "error": str(e),
        }
