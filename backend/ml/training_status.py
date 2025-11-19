# backend/ml/training_status.py
from datetime import datetime
from typing import Dict, Optional

TRAINING_JOBS: Dict[str, dict] = {}


def init_training_job(job_id: str, mode: str):
    TRAINING_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",          # queued | running | completed | failed
        "stage": "queued",           # queued, initializing, core_pipeline, registry, diagnostics, completed
        "progress": 0.0,             # 0..1
        "mode": mode,
        "started_at": None,
        "finished_at": None,
        "error": None,
        "result": None,
    }


def update_training_status(
    job_id: str,
    *,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    progress: Optional[float] = None,
    result: Optional[dict] = None,
    error: Optional[str] = None,
):
    job = TRAINING_JOBS.get(job_id)
    if not job:
        return

    if status is not None:
        job["status"] = status
        if status == "running" and job["started_at"] is None:
            job["started_at"] = datetime.utcnow().isoformat()
        if status in ("completed", "failed"):
            job["finished_at"] = datetime.utcnow().isoformat()

    if stage is not None:
        job["stage"] = stage

    if progress is not None:
        job["progress"] = max(0.0, min(1.0, float(progress)))  # clamp

    if result is not None:
        job["result"] = result

    if error is not None:
        job["error"] = error


def get_training_status(job_id: str) -> dict:
    return TRAINING_JOBS.get(
        job_id,
        {
            "job_id": job_id,
            "status": "unknown",
            "stage": "unknown",
            "progress": 0.0,
        },
    )
