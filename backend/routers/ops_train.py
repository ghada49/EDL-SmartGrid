# backend/routers/ops_train.py

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from redis import Redis
from rq.job import Job

from ..rq_connection import train_queue
from ..deps import require_roles
from ..ml.pipeline import run_full_training_pipeline
from ..ml.registry import (
    get_current_model_card,
    get_model_history,
    set_active_model_version,
)
from pydantic import BaseModel
from uuid import uuid4
router = APIRouter(
    prefix="/ops/train",
    tags=["Training Jobs"],
)
from backend.ml.training_status import (
    init_training_job,
    get_training_status,
)
@router.post("")
def start_train(
    mode: str = Query("moderate"),
    background_tasks: BackgroundTasks = None,
):
    job_id = str(uuid4())
    init_training_job(job_id, mode)

    # run in background so request returns immediately
    background_tasks.add_task(run_full_training_pipeline, job_id, mode)

    return {
        "job_id": job_id,
        "status": "queued",
        "mode": mode,
    }


@router.get("/{job_id}")
def read_train_status(job_id: str):
    return get_training_status(job_id)
def get_job_status(
    job_id: str,
    _=Depends(require_roles("Admin")),
):
    """
    Poll an existing RQ job by ID.

    If finished, the 'result' field contains whatever
    run_full_training_pipeline(...) returned, e.g.:

      {
        "status": "completed",
        "mode": "fast",
        "duration_sec": 166.5,
        "model_card": { ... }
      }
    """
    # Use the same Redis connection as the queue
    conn: Redis = train_queue.connection  # type: ignore
    try:
        job = Job.fetch(job_id, connection=conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.is_finished:
        return {
            "status": "completed",
            "result": job.result,  # dict from run_full_training_pipeline
        }
    if job.is_failed:
        return {"status": "failed", "error": str(job.exc_info)}
    if job.is_started:
        return {"status": "running"}
    return {"status": "queued"}


@router.get("/model/current")
def get_current_model(
    _=Depends(require_roles("Admin")),
):
    """
    Return the current model card (latest successful training run).

    Data comes from:
      data/model_registry/current_model_card.json
    """
    card = get_current_model_card()
    if card is None:
        raise HTTPException(status_code=404, detail="No trained model found")
    return card


@router.get("/model/history")
def get_model_history_route(
    _=Depends(require_roles("Admin")),
):
    """
    Return the full model history (all past model cards).

    Data comes from:
      data/model_registry/history.json
    """
    return get_model_history()


class ActivateModelRequest(BaseModel):
    version: int


@router.post("/model/activate")
def activate_model_version(
    payload: ActivateModelRequest,
    _=Depends(require_roles("Admin")),
):
    try:
        card = set_active_model_version(payload.version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return card
