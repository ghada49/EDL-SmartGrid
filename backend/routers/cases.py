from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
)
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import ops as models
from ..models.user import User

router = APIRouter(prefix="/cases", tags=["Cases"])


# 1) Create new case (from anomaly / building)
@router.post("/", dependencies=[Depends(require_roles("Manager", "Admin"))])
def create_case(
    building_id: Optional[int] = Form(None),
    anomaly_id: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
    created_by: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    case = models.Case(
        building_id=building_id,
        anomaly_id=anomaly_id,
        notes=notes,
        created_by=created_by,
        status="New",
    )
    db.add(case)
    db.add(
        models.CaseActivity(
            case=case,
            actor=created_by or "system",
            action="CREATE",
            note=notes or "Case created",
        )
    )
    db.commit()
    db.refresh(case)
    return {"id": case.id, "status": case.status}


# 2) List cases with filters (status, district, inspector)
@router.get("/", dependencies=[Depends(require_roles("Manager", "Admin", "Inspector"))])
def list_cases(
    status: Optional[str] = None,
    district: Optional[str] = None,
    inspector_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Case).join(models.Building, isouter=True)

    if status:
        q = q.filter(models.Case.status == status)

    if inspector_id:
        q = q.filter(models.Case.assigned_inspector_id == inspector_id)

    if district:
        q = q.filter(models.Building.district == district)

    cases = q.order_by(models.Case.created_at.desc()).all()

    # simple serialized view (frontend can refine)
    # Attach inspector display name if available
    def inspector_name(uid: Optional[str]) -> Optional[str]:
        if not uid:
            return None
        u = db.query(User).filter(User.id == uid).first()
        return (u.full_name or u.email) if u else None

    return [
        {
            "id": c.id,
            "status": c.status,
            "outcome": c.outcome,
            "building_id": c.building_id,
            "district": c.building.district if c.building else None,
            "assigned_inspector_id": c.assigned_inspector_id,
            "inspector_name": inspector_name(c.assigned_inspector_id),
            "created_at": c.created_at,
        }
        for c in cases
    ]


# 3) Assign / reassign inspector
@router.post(
    "/{case_id}/assign",
    dependencies=[Depends(require_roles("Manager", "Admin"))],
)
def assign_case(
    case_id: int,
    inspector_id: str = Form(...),
    actor: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    case = db.query(models.Case).get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.assigned_inspector_id = inspector_id

    db.add(
        models.CaseActivity(
            case_id=case.id,
            actor=actor or "manager",
            action="ASSIGN",
            note=f"Assigned to inspector {inspector_id}",
        )
    )
    db.commit()
    return {"id": case.id, "assigned_inspector_id": inspector_id}


# 4) Update status (tracker)
@router.patch(
    "/{case_id}/status",
    dependencies=[Depends(require_roles("Manager", "Admin", "Inspector"))],
)
def update_case_status(
    case_id: int,
    status: str = Form(...),
    actor: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if status not in ["New", "Scheduled", "Visited", "Reported", "Closed"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    case = db.query(models.Case).get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = status
    db.add(
        models.CaseActivity(
            case_id=case.id,
            actor=actor or "system",
            action="STATUS_UPDATE",
            note=f"Status changed to {status}",
        )
    )
    db.commit()
    return {"id": case.id, "status": case.status}


# 5) Case detail (building, activity log, comments, reports, attachments)
@router.get(
    "/{case_id}",
    dependencies=[Depends(require_roles("Manager", "Admin", "Inspector"))],
)
def get_case_detail(case_id: int, db: Session = Depends(get_db)):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return {
        "id": case.id,
        "status": case.status,
        "outcome": case.outcome,
        "building": {
            "id": case.building.id if case.building else None,
            "name": case.building.building_name if case.building else None,
            "district": case.building.district if case.building else None,
        }
        if case.building
        else None,
        "activities": [
            {
                "id": a.id,
                "actor": a.actor,
                "action": a.action,
                "note": a.note,
                "created_at": a.created_at,
            }
            for a in case.activities
        ],
        "reports": [
            {
                "id": r.id,
                "inspector_id": r.inspector_id,
                "findings": r.findings,
                "recommendation": r.recommendation,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in case.reports
        ],
        "attachments": [
            {
                "id": at.id,
                "filename": at.filename,
                "path": at.path,
                "uploaded_by": at.uploaded_by,
                "uploaded_at": at.uploaded_at,
            }
            for at in case.attachments
        ],
    }


# 6) Add comment (activity log)
@router.post(
    "/{case_id}/comment",
    dependencies=[Depends(require_roles("Manager", "Admin", "Inspector"))],
)
def add_case_comment(
    case_id: int,
    note: str = Form(...),
    actor: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    case = db.query(models.Case).get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    act = models.CaseActivity(
        case_id=case.id,
        actor=actor or "user",
        action="COMMENT",
        note=note,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return {"id": act.id, "case_id": case.id}


# 7) Upload attachment (optional, for evidence)
@router.post(
    "/{case_id}/attachments",
    dependencies=[Depends(require_roles("Manager", "Admin", "Inspector"))],
)
async def upload_case_attachment(
    case_id: int,
    file: UploadFile = File(...),
    uploaded_by: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    case = db.query(models.Case).get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    import os, time
    os.makedirs("data/case_attachments", exist_ok=True)
    filename = f"case_{case_id}_{int(time.time())}_{file.filename}"
    path = os.path.join("data/case_attachments", filename)

    with open(path, "wb") as f:
        f.write(await file.read())

    att = models.CaseAttachment(
        case_id=case.id,
        filename=file.filename,
        path=path,
        uploaded_by=uploaded_by,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"id": att.id, "filename": att.filename}


# 7.5) Record meter reading (Inspector)
@router.post(
    "/{case_id}/reading",
    dependencies=[Depends(require_roles("Manager", "Admin", "Inspector"))],
)
def record_meter_reading(
    case_id: int,
    reading: float = Form(...),
    unit: str = Form("kWh"),
    actor: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    case = db.query(models.Case).get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    note = f"Meter reading: {reading} {unit}"
    act = models.CaseActivity(
        case_id=case.id,
        actor=actor or "inspector",
        action="METER_READING",
        note=note,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return {"id": act.id, "case_id": case.id, "note": note}

# 8) Approve / Reject inspection report + mark case outcome
@router.post(
    "/{case_id}/review",
    dependencies=[Depends(require_roles("Manager", "Admin"))],
)
def review_inspection_report(
    case_id: int,
    report_id: int = Form(...),
    decision: str = Form(...),  # "Approve_Fraud", "Approve_NoIssue", "Reject", "Recheck"
    actor: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    case = db.query(models.Case).get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    report = (
        db.query(models.InspectionReport)
        .filter(
            models.InspectionReport.id == report_id,
            models.InspectionReport.case_id == case_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found for this case")

    if decision == "Approve_Fraud":
        report.status = "Approved"
        case.outcome = "Fraud"
        case.status = "Closed"
        note = "Report approved. Outcome: Fraud."
    elif decision == "Approve_NoIssue":
        report.status = "Approved"
        case.outcome = "No Issue"
        case.status = "Closed"
        note = "Report approved. Outcome: No Issue."
    elif decision == "Recheck":
        report.status = "Recheck"
        case.outcome = "Recheck"
        case.status = "Reported"
        note = "Recheck requested."
    elif decision == "Reject":
        report.status = "Rejected"
        note = "Report rejected."
    else:
        raise HTTPException(status_code=400, detail="Invalid decision")

    db.add(
        models.CaseActivity(
            case_id=case.id,
            actor=actor or "manager",
            action="REVIEW",
            note=note,
        )
    )
    db.commit()

    return {
        "case_id": case.id,
        "case_status": case.status,
        "case_outcome": case.outcome,
        "report_id": report.id,
        "report_status": report.status,
    }
