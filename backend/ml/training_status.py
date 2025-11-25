# backend/ml/training_status.py
import json
from datetime import datetime
from typing import Optional

from backend.rq_connection import redis_conn  # same Redis used by RQ

KEY_PREFIX = "training_job:"


def _key(job_id: str) -> str:
    return f"{KEY_PREFIX}{job_id}"


def init_training_job(job_id: str, mode: str):
    job = {
        "job_id": job_id,
        "status": "queued",      # queued | running | completed | failed
        "stage": "queued",       # queued, initializing, core_pipeline, registry, diagnostics, completed
        "progress": 0.0,         # 0..1
        "mode": mode,
        "started_at": None,
        "finished_at": None,
        "error": None,
        "result": None,
    }
    redis_conn.set(_key(job_id), json.dumps(job))


def update_training_status(
    job_id: str,
    *,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    progress: Optional[float] = None,
    result: Optional[dict] = None,
    error: Optional[str] = None,
):
    raw = redis_conn.get(_key(job_id))
    if not raw:
        return

    job = json.loads(raw)

    if status is not None:
        job["status"] = status
        if status == "running" and job.get("started_at") is None:
            job["started_at"] = datetime.utcnow().isoformat()
        if status in ("completed", "failed"):
            job["finished_at"] = datetime.utcnow().isoformat()

    if stage is not None:
        job["stage"] = stage

    if progress is not None:
        job["progress"] = max(0.0, min(1.0, float(progress)))  # clamp 0..1

    if result is not None:
        job["result"] = result

    if error is not None:
        job["error"] = error

    redis_conn.set(_key(job_id), json.dumps(job))


def get_training_status(job_id: str) -> dict:
    raw = redis_conn.get(_key(job_id))
    if not raw:
        return {
            "job_id": job_id,
            "status": "unknown",
            "stage": "unknown",
            "progress": 0.0,
        }
    return json.loads(raw)
