# backend/routers/inspector.py
# backend/routers/inspector.py
from ..models import Appointment, Building, Case, Inspector, FeedbackLabel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional, Literal
from datetime import date, datetime, timedelta
from pydantic import BaseModel, Field
from math import radians, sin, cos, sqrt, atan2
import io
import pandas as pd
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..deps import get_current_user
from ..models import Appointment, Case, Inspector, FeedbackLabel  # Case for joins
from ..models.user import User
from ..models.ops import Building

router = APIRouter()  # prefix is added in main/app when mounting

# ---------- Schemas ----------
class FraudMapPoint(BaseModel):
    case_id: int
    building_id: Optional[int]
    lat: float
    lng: float
    status: str
    outcome: Optional[str] = None
    feedback_label: Optional[str] = None

    class Config:
        from_attributes = True

class ApptOut(BaseModel):
    id: int
    case_id: int
    start: datetime
    end: datetime
    status: str
    lat: Optional[float] = None
    lng: Optional[float] = None

    class Config:
        from_attributes = True


class RespondIn(BaseModel):
    action: str  # "accept" | "reject"


class RoutePoint(BaseModel):
    id: int
    lat: float
    lng: float
    case_id: int
    start: Optional[datetime] = None


class RouteOut(BaseModel):
    clusters: List[List[RoutePoint]]
    ordered: List[RoutePoint]


class InspectorSelfOut(BaseModel):
    id: int
    name: str
    active: bool
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None
    user_id: Optional[str] = None

    class Config:
        from_attributes = True

class InspectorProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    home_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    home_lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0)


class ConfirmRequest(BaseModel):
    action: Literal["confirm", "reschedule", "visited"]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class InspectorSummary(BaseModel):
    inspector_id: int
    pending: int
    accepted: int
    visited: int
    closed_cases: int
    fraud_detected: int
    visits_today: int


# ---------- Helpers ----------
def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def _get_linked_inspector(db: Session, user: User) -> Inspector:
    inspector = db.query(Inspector).filter(Inspector.user_id == user.id).first()
    if not inspector:
        raise HTTPException(status_code=404, detail="Inspector profile not linked")
    return inspector


def _resolve_inspector_id(
    db: Session,
    user: User,
    inspector_id: Optional[int],
) -> int:
    if inspector_id is not None:
        if user.role == "Inspector":
            linked = _get_linked_inspector(db, user)
            if linked.id != inspector_id:
                raise HTTPException(status_code=403, detail="Cannot access other inspectors")
        return inspector_id
    if user.role != "Inspector":
        raise HTTPException(status_code=400, detail="inspector_id is required")
    return _get_linked_inspector(db, user).id


@router.get("/me", response_model=InspectorSelfOut, tags=["Inspector"])
def inspector_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "Inspector":
        raise HTTPException(status_code=403, detail="Only inspectors can access this resource")
    return _get_linked_inspector(db, current_user)


@router.patch("/me", response_model=InspectorSelfOut, tags=["Inspector"])
def update_inspector_me(
    payload: InspectorProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "Inspector":
        raise HTTPException(status_code=403, detail="Only inspectors can update this profile")

    inspector = _get_linked_inspector(db, current_user)

    fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))

    if payload.name is not None:
        inspector.name = payload.name
    if "home_lat" in fields_set:
        inspector.home_lat = payload.home_lat
    if "home_lng" in fields_set:
        inspector.home_lng = payload.home_lng

    db.add(inspector)
    db.commit()
    db.refresh(inspector)
    return inspector


# ---------- Endpoints ----------
@router.get("/schedule", response_model=List[ApptOut], tags=["Inspector"])
def my_schedule(
    db: Session = Depends(get_db),
    day: Optional[date] = Query(None),
    inspector_id: Optional[int] = Query(
        None, description="Inspector ID (optional when authenticated as an inspector)"
    ),
    current_user: User = Depends(get_current_user),
):
    target_id = _resolve_inspector_id(db, current_user, inspector_id)
    q = (
        db.query(Appointment)
        .options(joinedload(Appointment.case).joinedload(Case.building))
        .filter(Appointment.inspector_id == target_id)
    )

    if day:
        start_dt = datetime.combine(day, datetime.min.time())
        end_dt = datetime.combine(day, datetime.max.time())
        q = q.filter(Appointment.start_time >= start_dt, Appointment.start_time <= end_dt)

    rows = q.order_by(Appointment.start_time.asc()).all()

    out: List[ApptOut] = []
    for a in rows:
        lat = lng = None
        if a.case and a.case.building:
            lat = a.case.building.latitude
            lng = a.case.building.longitude
        out.append(
            ApptOut(
                id=a.id,
                case_id=a.case_id,
                start=a.start_time,
                end=a.end_time,
                status=a.status,
                lat=lat,
                lng=lng,
            )
        )
    return out


@router.get("/schedule/me", response_model=List[ApptOut], tags=["Inspector"])
def schedule_me(
    day: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return my_schedule(
        db=db,
        day=day,
        inspector_id=None,
        current_user=current_user,
    )


@router.patch("/appointments/{appointment_id}/respond", response_model=ApptOut, tags=["Inspector"])
def respond_appointment(
    appointment_id: int,
    payload: RespondIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = db.query(Appointment).get(appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    if payload.action not in ("accept", "reject"):
        raise HTTPException(400, "action must be 'accept' or 'reject'")

    # if inspector role, ensure they are linked to this appointment
    if current_user.role == "Inspector":
        linked = _get_linked_inspector(db, current_user)
        if appt.inspector_id != linked.id:
            raise HTTPException(status_code=403, detail="Cannot update another inspector's appointment")

    appt.status = "accepted" if payload.action == "accept" else "rejected"
    db.commit()
    db.refresh(appt)

    # pull lat/lng via join
    a = (
        db.query(Appointment)
        .options(joinedload(Appointment.case).joinedload(Case.building))
        .get(appt.id)
    )
    lat = lng = None
    if a.case and a.case.building:
        lat = a.case.building.latitude
        lng = a.case.building.longitude

    return ApptOut(
        id=a.id,
        case_id=a.case_id,
        start=a.start_time,
        end=a.end_time,
        status=a.status,
        lat=lat,
        lng=lng,
    )


@router.patch("/schedule/{appointment_id}/confirm", response_model=ApptOut, tags=["Inspector"])
def confirm_visit(
    appointment_id: int,
    payload: ConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = db.query(Appointment).get(appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    if current_user.role == "Inspector":
        linked = _get_linked_inspector(db, current_user)
        if appt.inspector_id != linked.id:
            raise HTTPException(status_code=403, detail="Cannot modify another inspector's visit")

    if payload.action == "reschedule":
        if not payload.start_time or not payload.end_time:
            raise HTTPException(400, "start_time and end_time are required when rescheduling")
        appt.start_time = payload.start_time
        appt.end_time = payload.end_time
        appt.status = "pending"
    elif payload.action == "confirm":
        appt.status = "accepted"
    elif payload.action == "visited":
        appt.status = "closed"
    else:
        raise HTTPException(400, "Unsupported action")

    db.commit()
    db.refresh(appt)

    lat = lng = None
    if appt.case and appt.case.building:
        lat = appt.case.building.latitude
        lng = appt.case.building.longitude
    return ApptOut(
        id=appt.id,
        case_id=appt.case_id,
        start=appt.start_time,
        end=appt.end_time,
        status=appt.status,
        lat=lat,
        lng=lng,
    )


@router.get("/routes", response_model=RouteOut, tags=["Inspector"])
def routes(
    day: date = Query(...),
    inspector_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_id = _resolve_inspector_id(db, current_user, inspector_id)
    start_dt = datetime.combine(day, datetime.min.time())
    end_dt = datetime.combine(day, datetime.max.time())

    rows = (
        db.query(Appointment)
        .options(joinedload(Appointment.case).joinedload(Case.building))
        .filter(
            Appointment.inspector_id == target_id,
            Appointment.start_time >= start_dt,
            Appointment.start_time <= end_dt,
            Appointment.status.in_(("pending", "accepted")),
        )
        .order_by(Appointment.start_time.asc())
        .all()
    )

    pts: List[RoutePoint] = []
    for r in rows:
        if r.case and r.case.building and r.case.building.latitude is not None and r.case.building.longitude is not None:
            pts.append(
                RoutePoint(
                    id=r.id,
                    lat=float(r.case.building.latitude),
                    lng=float(r.case.building.longitude),
                    case_id=r.case_id,
                    start=r.start_time,
                )
            )

    # cluster by 2 km
    CLUSTER_R = 2.0
    clusters: List[List[RoutePoint]] = []
    for p in pts:
        placed = False
        for c in clusters:
            if haversine(p.lat, p.lng, c[0].lat, c[0].lng) <= CLUSTER_R:
                c.append(p)
                placed = True
                break
        if not placed:
            clusters.append([p])

    # simple greedy route from earliest start
    if not pts:
        return RouteOut(clusters=clusters, ordered=[])
    cur = min(pts, key=lambda x: x.start or datetime.min)
    ordered = [cur]
    remaining = [x for x in pts if x.id != cur.id]
    while remaining:
        nxt = min(remaining, key=lambda x: haversine(cur.lat, cur.lng, x.lat, x.lng))
        ordered.append(nxt)
        remaining.remove(nxt)
        cur = nxt

    return RouteOut(clusters=clusters, ordered=ordered)


@router.get("/reports/case/{case_id}.pdf", tags=["Inspector"])
def case_report_pdf(case_id: int, db: Session = Depends(get_db)):
    appts = (
        db.query(Appointment)
        .filter(Appointment.case_id == case_id)
        .order_by(Appointment.start_time.asc())
        .all()
    )
    if not appts:
        raise HTTPException(404, "No appointments for case")

    # lightweight, text-only PDF (no extra deps except reportlab if you want fancy)
    buf = io.BytesIO()
    try:
        from reportlab.pdfgen import canvas  # optional dependency
    except Exception:
        # Fallback: return a CSV-ish text file if reportlab not installed
        buf.write(b"start_time,end_time,status,appointment_id\n")
        for a in appts:
            buf.write(f"{a.start_time},{a.end_time},{a.status},{a.id}\n".encode("utf-8"))
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=case_{case_id}.txt"},
        )

    c = canvas.Canvas(buf)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, f"Inspection Report – Case #{case_id}")
    y = 770
    c.setFont("Helvetica", 11)
    for a in appts:
        c.drawString(
            50,
            y,
            f"{a.start_time:%Y-%m-%d %H:%M} → {a.end_time:%H:%M} | status={a.status} | appt_id={a.id}",
        )
        y -= 18
        if y < 60:
            c.showPage()
            y = 800
    c.showPage()
    c.save()
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=case_{case_id}.pdf"},
    )


@router.get("/cases/{case_id}/report", tags=["Inspector"])
def case_report_alias(case_id: int, db: Session = Depends(get_db)):
    return case_report_pdf(case_id, db)


@router.get("/reports/inspector", response_model=InspectorSummary, tags=["Inspector"])
def inspector_summary(
    day: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_id = _resolve_inspector_id(db, current_user, None)
    day_val = day or datetime.utcnow().date()
    start_dt = datetime.combine(day_val, datetime.min.time())
    end_dt = datetime.combine(day_val, datetime.max.time())

    visits_today = (
        db.query(func.count(Appointment.id))
        .filter(
            Appointment.inspector_id == target_id,
            Appointment.start_time >= start_dt,
            Appointment.start_time <= end_dt,
        )
        .scalar()
        or 0
    )

    counts = dict(
        db.query(Appointment.status, func.count(Appointment.id))
        .filter(Appointment.inspector_id == target_id)
        .group_by(Appointment.status)
        .all()
    )

    closed_cases = (
        db.query(func.count(func.distinct(Case.id)))
        .join(Appointment, Appointment.case_id == Case.id)
        .filter(Appointment.inspector_id == target_id, Case.status == "closed")
        .scalar()
        or 0
    )

    fraud_detected = (
        db.query(func.count(FeedbackLabel.id))
        .join(Case, FeedbackLabel.case_id == Case.id)
        .join(Appointment, Appointment.case_id == Case.id)
        .filter(
            Appointment.inspector_id == target_id,
            FeedbackLabel.label == "fraud",
        )
        .scalar()
        or 0
    )

    return InspectorSummary(
        inspector_id=target_id,
        pending=int(counts.get("pending", 0) or 0),
        accepted=int(counts.get("accepted", 0) or 0),
        visited=int(counts.get("closed", 0) or 0),
        closed_cases=int(closed_cases),
        fraud_detected=int(fraud_detected),
        visits_today=int(visits_today),
    )

@router.get("/fraud-map", response_model=List[FraudMapPoint], tags=["Inspector"])
def fraud_map(
    inspector_id: Optional[int] = Query(
        None, description="Inspector ID (optional when authenticated as an inspector)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return ALL cases assigned to this inspector that have a building with lat/lng.
    Fraud info (outcome/feedback_label) is included only for styling on the map.
    """
    # If logged in as Inspector with no inspector_id param,
    # this resolves to the linked inspector's id
    target_id = _resolve_inspector_id(db, current_user, inspector_id)

    rows = (
        db.query(
            Case.id.label("case_id"),
            Case.building_id.label("building_id"),
            Building.latitude.label("lat"),
            Building.longitude.label("lng"),
            Case.status.label("status"),
            Case.outcome.label("outcome"),
            FeedbackLabel.label.label("feedback_label"),
        )
        # only cases that have an appointment for THIS inspector
        .join(Appointment, Appointment.case_id == Case.id)
        .join(Building, Case.building_id == Building.id)
        .outerjoin(FeedbackLabel, FeedbackLabel.case_id == Case.id)
        .filter(
            Appointment.inspector_id == target_id,
            Building.latitude.isnot(None),
            Building.longitude.isnot(None),
        )
        .all()
    )

    points: List[FraudMapPoint] = []
    for r in rows:
        if r.lat is None or r.lng is None:
            continue
        points.append(
            FraudMapPoint(
                case_id=r.case_id,
                building_id=r.building_id,
                lat=float(r.lat),
                lng=float(r.lng),
                status=r.status or "New",
                outcome=r.outcome,
                feedback_label=r.feedback_label,
            )
        )

    return points
@router.get("/fraud-map/me", response_model=List[FraudMapPoint], tags=["Inspector"])
def fraud_map_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return ALL cases that are assigned to the current inspector (via Case.assigned_inspector_id)
    and have a building with lat/lng. Does NOT depend on case status.
    Fraud info is only for styling on the map.
    """
    # Find which inspector is linked to this user
    inspector = _get_linked_inspector(db, current_user)
    if not inspector.user_id:
        raise HTTPException(status_code=400, detail="Inspector is not linked to a user account")

    rows = (
        db.query(
            Case.id.label("case_id"),
            Case.building_id.label("building_id"),
            Building.latitude.label("lat"),
            Building.longitude.label("lng"),
            Case.status.label("status"),
            Case.outcome.label("outcome"),
            FeedbackLabel.label.label("feedback_label"),
        )
        .join(Building, Case.building_id == Building.id)
        .outerjoin(FeedbackLabel, FeedbackLabel.case_id == Case.id)
        .filter(
            Case.assigned_inspector_id == inspector.user_id,
            Building.latitude.isnot(None),
            Building.longitude.isnot(None),
        )
        .all()
    )

    points: List[FraudMapPoint] = []
    for r in rows:
        if r.lat is None or r.lng is None:
            continue
        points.append(
            FraudMapPoint(
                case_id=r.case_id,
                building_id=r.building_id,
                lat=float(r.lat),
                lng=float(r.lng),
                status=r.status or "New",
                outcome=r.outcome,
                feedback_label=r.feedback_label,
            )
        )

    return points


@router.get("/reports/weekly.xlsx", tags=["Inspector"])
def weekly_export(
    week_start: date,
    inspector_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_id = _resolve_inspector_id(db, current_user, inspector_id)
    start = datetime.combine(week_start, datetime.min.time())
    end = start + timedelta(days=7)
    q = (
        db.query(Appointment)
        .options(joinedload(Appointment.case).joinedload(Case.building))
        .filter(
            Appointment.inspector_id == target_id,
            Appointment.start_time >= start,
            Appointment.start_time < end,
        )
        .order_by(Appointment.start_time.asc())
    )

    rows = []
    for a in q.all():
        lat = lng = None
        if a.case and a.case.building:
            lat = a.case.building.latitude
            lng = a.case.building.longitude
        rows.append(
            {
                "appointment_id": a.id,
                "case_id": a.case_id,
                "start": a.start_time,
                "end": a.end_time,
                "status": a.status,
                "lat": lat,
                "lng": lng,
            }
        )

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Visits")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=weekly_visits.xlsx"},
    )
