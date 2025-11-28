from __future__ import annotations

from typing import Optional, Dict, Tuple, List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
)
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from ..db import get_db
from ..deps import require_roles, get_current_user
from ..models import ops as models, Inspector, Appointment, FeedbackLabel
from ..models.user import User

router = APIRouter(prefix="/cases", tags=["Cases"])


class CaseMapPoint(BaseModel):
    case_id: int
    building_id: Optional[int]
    lat: float
    lng: float
    status: str
    outcome: Optional[str] = None
    feedback_label: Optional[str] = None
    assigned_inspector_id: Optional[str] = None
    inspector_name: Optional[str] = None
    district: Optional[str] = None


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
        status="new",
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

    case_ids = [c.id for c in cases]
    latest_assignees: Dict[int, Tuple[Optional[int], Optional[str]]] = {}
    if case_ids:
        appts = (
            db.query(Appointment.case_id, Appointment.inspector_id, Inspector.name)
            .outerjoin(Inspector, Appointment.inspector_id == Inspector.id)
            .filter(Appointment.case_id.in_(case_ids))
            .order_by(Appointment.start_time.desc())
            .all()
        )
        for cid, iid, iname in appts:
            if cid in latest_assignees:
                continue
            if iid is None:
                continue
            latest_assignees[cid] = (iid, iname or f"Inspector #{iid}")

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
            "lat": float(c.building.latitude) if c.building and c.building.latitude is not None else None,
            "lng": float(c.building.longitude) if c.building and c.building.longitude is not None else None,
            "district": c.building.district if c.building else None,
            "assigned_inspector_id": c.assigned_inspector_id,
            "scheduled_inspector_id": latest_assignees.get(c.id, (None, None))[0],
            "scheduled_inspector_name": latest_assignees.get(c.id, (None, None))[1],
            "inspector_name": inspector_name(c.assigned_inspector_id)
            or latest_assignees.get(c.id, (None, None))[1],
            "created_at": c.created_at,
        }
        for c in cases
    ]


@router.get(
    "/map",
    response_model=List[CaseMapPoint],
    dependencies=[Depends(require_roles("Manager", "Admin"))],
)
def cases_map(db: Session = Depends(get_db)):
    """
    Lightweight map feed for managers: all cases that have building coordinates.
    No filtering by status; includes latest assignment info if present.
    """
    rows = (
        db.query(
            models.Case.id.label("case_id"),
            models.Case.building_id.label("building_id"),
            models.Building.latitude.label("lat"),
            models.Building.longitude.label("lng"),
            models.Case.status.label("status"),
            models.Case.outcome.label("outcome"),
            models.Case.assigned_inspector_id.label("assigned_inspector_id"),
            models.Building.district.label("district"),
            FeedbackLabel.label.label("feedback_label"),
        )
        .join(models.Building, models.Case.building_id == models.Building.id)
        .outerjoin(FeedbackLabel, FeedbackLabel.case_id == models.Case.id)
        .filter(
            models.Building.latitude.isnot(None),
            models.Building.longitude.isnot(None),
        )
        .all()
    )

    # Prefetch inspector display names
    uid_set = {r.assigned_inspector_id for r in rows if r.assigned_inspector_id}
    inspector_names = {
        u.id: (u.full_name or u.email)
        for u in db.query(User).filter(User.id.in_(uid_set)).all()
    } if uid_set else {}

    # Deduplicate by case_id; prefer first feedback label if multiple
    out_map: Dict[int, CaseMapPoint] = {}
    for r in rows:
        if r.lat is None or r.lng is None:
            continue
        if r.case_id in out_map:
            # Keep existing, but fill feedback_label if missing
            if out_map[r.case_id].feedback_label is None and r.feedback_label:
                out_map[r.case_id].feedback_label = r.feedback_label
            continue
        out_map[r.case_id] = CaseMapPoint(
            case_id=r.case_id,
            building_id=r.building_id,
            lat=float(r.lat),
            lng=float(r.lng),
            status=(r.status or "new"),
            outcome=r.outcome,
            feedback_label=r.feedback_label,
            assigned_inspector_id=r.assigned_inspector_id,
            inspector_name=inspector_names.get(r.assigned_inspector_id),
            district=r.district,
        )

    return list(out_map.values())


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

    previous_status = case.status or ""
    case.assigned_inspector_id = inspector_id

    status_changed = False
    if (previous_status or "").lower() != "pending":
        case.status = "pending"
        status_changed = True
    db.add(case)

    inspector = db.query(User).filter(User.id == inspector_id).first()
    inspector_label = (inspector.full_name or inspector.email) if inspector else inspector_id

    db.add(
        models.CaseActivity(
            case_id=case.id,
            actor=actor or "manager",
            action="ASSIGN",
            note=f"Assigned to inspector {inspector_label}",
        )
    )

    if status_changed:
        db.add(
            models.CaseActivity(
                case_id=case.id,
                actor=actor or "system",
                action="STATUS_UPDATE",
                note="Status changed to Scheduled",
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
    if status not in ["new", "pending", "scheduled", "reported", "rejected", "closed"]:
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

    latest_appt = (
        db.query(Appointment)
        .options(joinedload(Appointment.inspector))
        .filter(Appointment.case_id == case_id)
        .order_by(Appointment.start_time.desc())
        .first()
    )

    def inspector_name(uid: Optional[str]) -> Optional[str]:
        if not uid:
            return None
        u = db.query(User).filter(User.id == uid).first()
        return (u.full_name or u.email) if u else None

    assigned_name = inspector_name(case.assigned_inspector_id)
    scheduled_id = latest_appt.inspector_id if latest_appt else None
    scheduled_name = (
        latest_appt.inspector.name if latest_appt and latest_appt.inspector else None
    )

    return {
        "id": case.id,
        "status": case.status,
        "outcome": case.outcome,
        "assigned_inspector_id": case.assigned_inspector_id,
        "inspector_name": assigned_name or scheduled_name,
        "scheduled_inspector_id": scheduled_id,
        "scheduled_inspector_name": scheduled_name,
        "building": {
            "id": case.building.id if case.building else None,
            "name": case.building.building_name if case.building else None,
            "district": case.building.district if case.building else None,
            "lat": float(case.building.latitude) if case.building and case.building.latitude is not None else None,
            "lng": float(case.building.longitude) if case.building and case.building.longitude is not None else None,
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


@router.post("/{case_id}/confirm", dependencies=[Depends(require_roles("Inspector"))])
def confirm_case(case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    case = db.query(models.Case).get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    # inspector can only confirm own assignment
    if case.assigned_inspector_id and str(case.assigned_inspector_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your case")
    case.status = "scheduled"
    db.add(case)
    db.add(
        models.CaseActivity(
            case_id=case.id,
            actor=current_user.full_name or current_user.email or "inspector",
            action="CONFIRM",
            note="Inspector confirmed case",
        )
    )
    db.commit()
    db.refresh(case)
    return {"id": case.id, "status": case.status}


@router.post("/{case_id}/reject", dependencies=[Depends(require_roles("Inspector"))])
def reject_case(case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    case = db.query(models.Case).get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.assigned_inspector_id and str(case.assigned_inspector_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your case")
    case.status = "rejected"
    db.add(case)
    db.add(
        models.CaseActivity(
            case_id=case.id,
            actor=current_user.full_name or current_user.email or "inspector",
            action="REJECT",
            note="Inspector rejected case",
        )
    )
    db.commit()
    db.refresh(case)
    return {"id": case.id, "status": case.status}