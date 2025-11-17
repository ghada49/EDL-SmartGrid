# backend/routers/ops_train.py

from fastapi import APIRouter, Depends, Query, HTTPException
from redis import Redis
from rq.job import Job

from ..rq_connection import train_queue
from ..deps import require_roles
from ..ml.pipeline import run_full_training_pipeline

router = APIRouter(
    prefix="/ops/train",
    tags=["Training Jobs"],
)

@router.post("")  # 🔹 NOT "/" → this matches /ops/train (no extra slash)
def start_training(
    mode: str = Query(
        "moderate",
        pattern="^(fast|moderate|slow|very_slow)$"
    ),
    _=Depends(require_roles("Admin")),
):
    """
    Enqueue a training job with the selected tuner mode.
    mode is taken from the query string: /ops/train?mode=fast|moderate|slow|very_slow
    """
    job = train_queue.enqueue(run_full_training_pipeline, mode)
    return {"job_id": job.id, "status": "queued", "mode": mode}


@router.get("/{job_id}")
def get_job_status(
    job_id: str,
    _=Depends(require_roles("Admin")),
):
    """
    Poll an existing RQ job by ID.
    """
    conn = Redis()
    try:
        job = Job.fetch(job_id, connection=conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.is_finished:
        return {"status": "completed", "result": job.result}
    if job.is_failed:
        return {"status": "failed", "error": str(job.exc_info)}
    if job.is_started:
        return {"status": "running"}
    return {"status": "queued"}
