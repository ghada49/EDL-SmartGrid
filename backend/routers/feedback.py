from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from typing import Any  # ⬅️ add this

from ..db import get_db
from ..models import FeedbackLabel, Case
from ..schemas.manager_scheduling import FeedbackLabelIn, FeedbackLabelOut, FeedbackLogItem

router = APIRouter(prefix="/manager/feedback", tags=["Feedback"])

@router.post("/labels", response_model=FeedbackLabelOut)
def add_label(payload: FeedbackLabelIn, db: Session = Depends(get_db), user:Any =None):
    # TODO: wire your auth dependency
    c = db.query(Case).get(payload.case_id)
    if not c:
        raise HTTPException(404, "Case not found")

    fb = FeedbackLabel(
        case_id=payload.case_id,
        meter_id=getattr(c, "meter_id", None),
        label=payload.label,
        source=payload.source,
        notes=payload.notes,
        actor_id=getattr(user, "id", None),
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return FeedbackLabelOut(
        id=fb.id, case_id=fb.case_id, label=fb.label, source=fb.source,
        notes=fb.notes, created_at=fb.created_at
    )

@router.get("/logs", response_model=List[FeedbackLogItem])
def logs(
    frm: Optional[date] = Query(None, alias="from"),
    to: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    q = db.query(FeedbackLabel).order_by(FeedbackLabel.created_at.desc())
    if frm:
        q = q.filter(FeedbackLabel.created_at >= datetime.combine(frm, datetime.min.time()))
    if to:
        q = q.filter(FeedbackLabel.created_at <= datetime.combine(to, datetime.max.time()))

    rows = q.all()
    return [
        FeedbackLogItem(
            id=r.id, case_id=r.case_id, meter_id=r.meter_id,
            label=r.label, source=r.source, notes=r.notes,
            created_at=r.created_at
        ) for r in rows
    ]
