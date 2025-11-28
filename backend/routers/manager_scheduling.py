from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from datetime import datetime, date, timedelta
from typing import List, Optional

from ..db import get_db
from ..models import Inspector, Appointment, Case, Building
from ..schemas.manager_scheduling import (
    InspectorOut, AppointmentOut, WorkloadItem,
    SuggestAssignmentsRequest, SuggestionOut,
    AssignRequest, RescheduleRequest, ReassignRequest,
    AutoAssignRequest, AssignmentResult, OverviewOut, OverviewInspector,
)
from ..utils.assign import haversine_km, week_bounds

router = APIRouter(prefix="/manager/scheduling", tags=["Manager Scheduling"])


# -----------------------------------------------------
# Unified Load Function
# -----------------------------------------------------
def _current_load_by_inspector(db: Session) -> dict[int, int]:
    """
    Count appointments whose linked case is NOT closed (any appointment status).
    Used consistently across suggest, workload, overview, and auto-assign.
    """
    rows = (
        db.query(Appointment.inspector_id, func.count(Appointment.id))
        .join(Case, Appointment.case_id == Case.id, isouter=True)
        .filter(or_(Case.id.is_(None), func.lower(Case.status) != "closed"))
        .group_by(Appointment.inspector_id)
        .all()
    )
    return {ins_id: int(count or 0) for ins_id, count in rows}


@router.get("/ping")
def ping():
    return {"ok": True}


# -----------------------------------------------------
# Inspectors
# -----------------------------------------------------
@router.get("/inspectors", response_model=List[InspectorOut])
def list_inspectors(active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(Inspector)
    if active_only:
        q = q.filter(Inspector.active == True)
    return q.order_by(Inspector.name.asc()).all()


# -----------------------------------------------------
# All appointments
# -----------------------------------------------------
@router.get("/appointments", response_model=List[AppointmentOut])
def all_appointments(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    inspector_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Appointment)
        .options(joinedload(Appointment.case).joinedload(Case.building))
        .order_by(Appointment.start_time.asc())
    )

    if inspector_id:
        q = q.filter(Appointment.inspector_id == inspector_id)

    if start:
        q = q.filter(Appointment.start_time >= datetime.combine(start, datetime.min.time()))
    if end:
        q = q.filter(Appointment.start_time <= datetime.combine(end, datetime.max.time()))

    rows = q.all()
    out: List[AppointmentOut] = []
    for a in rows:
        lat = lng = None
        title = getattr(a.case, "title", None) or f"Case #{a.case_id}"
        # Use case status if present so scheduling view mirrors Case Management
        effective_status = a.case.status if a.case and a.case.status else a.status
        if a.case and a.case.building:
            lat = a.case.building.latitude
            lng = a.case.building.longitude

        out.append(
            AppointmentOut(
                id=a.id,
                case_id=a.case_id,
                inspector_id=a.inspector_id,
                start_time=a.start_time,
                end_time=a.end_time,
                status=effective_status,
                title=title,
                lat=lat,
                lng=lng,
            )
        )
    return out


# -----------------------------------------------------
# Workload Summary
# -----------------------------------------------------
@router.get("/workload", response_model=List[WorkloadItem])
def workload(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    wstart, wend = week_bounds(now)

    active_counts = _current_load_by_inspector(db)

    week_counts = dict(
        db.query(Appointment.inspector_id, func.count(Appointment.id))
        .join(Case, Appointment.case_id == Case.id, isouter=True)
        .filter(or_(Case.id.is_(None), func.lower(Case.status) != "closed"))
        .filter(Appointment.start_time >= wstart)
        .filter(Appointment.start_time <= wend)
        .group_by(Appointment.inspector_id)
        .all()
    )

    inspectors = (
        db.query(Inspector)
        .filter(Inspector.active == True)
        .order_by(Inspector.name.asc())
        .all()
    )

    return [
        WorkloadItem(
            inspector_id=ins.id,
            inspector_name=ins.name,
            active_cases=int(active_counts.get(ins.id, 0)),
            appointments_this_week=int(week_counts.get(ins.id, 0)),
        )
        for ins in inspectors
    ]


# -----------------------------------------------------
# Suggest (uses unified load logic)
# -----------------------------------------------------
@router.post("/suggest", response_model=List[SuggestionOut])
def suggest(req: SuggestAssignmentsRequest, db: Session = Depends(get_db)):
    lat = req.lat
    lng = req.lng

    # Only require coordinates when proximity strategy is used.
    if req.strategy == "proximity":
        if req.case_id and (lat is None or lng is None):
            c = db.query(Case).options(joinedload(Case.building)).get(req.case_id)
            if not c or not c.building:
                raise HTTPException(404, "Case or building not found")
            lat = c.building.latitude
            lng = c.building.longitude
        if lat is None or lng is None:
            raise HTTPException(400, "Provide case_id or lat/lng for proximity scoring")

    inspectors = db.query(Inspector).filter(Inspector.active == True).all()
    load = _current_load_by_inspector(db)

    scores: List[SuggestionOut] = []
    for ins in inspectors:
        if req.strategy == "proximity" and ins.home_lat is not None:
            d = haversine_km(lat, lng, ins.home_lat, ins.home_lng)
            scores.append(
                SuggestionOut(
                    inspector_id=ins.id,
                    inspector_name=ins.name,
                    score=round(d, 3),
                    reason="distance_km",
                )
            )
        else:
            l = float(load.get(ins.id, 0))
            scores.append(
                SuggestionOut(
                    inspector_id=ins.id,
                    inspector_name=ins.name,
                    score=l,
                    reason="current_load",
                )
            )

    scores.sort(key=lambda s: s.score)
    return scores[: req.top_k]


# -----------------------------------------------------
# Assign
# -----------------------------------------------------
@router.post("/assign", response_model=AppointmentOut)
def assign_visit(req: AssignRequest, db: Session = Depends(get_db)):
    ins = db.query(Inspector).get(req.inspector_id)
    if not ins:
        raise HTTPException(404, "Inspector not found")
    if not ins.user_id:
        raise HTTPException(400, "Inspector is not linked to a user account; cannot assign")
    c = db.query(Case).get(req.case_id)
    if not c:
        raise HTTPException(404, "Case not found")

    # Always sync the case assignment to the inspector's linked user for inspector consoles
    c.assigned_inspector_id = ins.user_id

    if (c.status or "").lower() != "pending":
        c.status = "pending"

    if req.target_lat is not None:
        if c.building_id:
            b = db.query(Building).get(c.building_id)
            if b:
                b.latitude = req.target_lat
                b.longitude = req.target_lng
        else:
            b = Building(
                building_name=getattr(c, "title", None) or f"Case #{c.id}",
                latitude=req.target_lat,
                longitude=req.target_lng,
                district=getattr(c, "district", None),
            )
            db.add(b)
            db.flush()
            c.building_id = b.id

    ap = Appointment(
        case_id=req.case_id,
        inspector_id=req.inspector_id,
        start_time=req.start_time,
        end_time=req.end_time,
        status="pending",
        notes=req.notes or None,
    )
    db.add(ap)
    db.commit()
    db.refresh(ap)

    lat = lng = None
    if c.building:
        lat = c.building.latitude
        lng = c.building.longitude

    return AppointmentOut(
        id=ap.id,
        case_id=ap.case_id,
        inspector_id=ap.inspector_id,
        start_time=ap.start_time,
        end_time=ap.end_time,
        status=ap.status,
        title=getattr(c, "title", None),
        lat=lat,
        lng=lng,
    )


# -----------------------------------------------------
# Reschedule
# -----------------------------------------------------
@router.patch("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule(appointment_id: int, req: RescheduleRequest, db: Session = Depends(get_db)):
    ap = (
        db.query(Appointment)
        .options(joinedload(Appointment.case).joinedload(Case.building))
        .get(appointment_id)
    )
    if not ap:
        raise HTTPException(404, "Appointment not found")

    ap.start_time = req.start_time
    ap.end_time = req.end_time

    if req.inspector_id is not None:
        ins = db.query(Inspector).get(req.inspector_id)
        if not ins:
            raise HTTPException(404, "Inspector not found")
        if not ins.user_id:
            raise HTTPException(400, "Inspector is not linked to a user account; cannot assign")
        ap.inspector_id = req.inspector_id
        if ap.case:
            ap.case.assigned_inspector_id = ins.user_id
            ap.case.status = "pending"
    # keep appointment status aligned with case status for the scheduling view
    ap.status = "pending"

    db.commit()
    db.refresh(ap)

    lat = lng = None
    if ap.case and ap.case.building:
        lat = ap.case.building.latitude
        lng = ap.case.building.longitude

    return AppointmentOut(
        id=ap.id,
        case_id=ap.case_id,
        inspector_id=ap.inspector_id,
        start_time=ap.start_time,
        end_time=ap.end_time,
        status=ap.status,
        title=getattr(ap.case, "title", None),
        lat=lat,
        lng=lng,
    )


# -----------------------------------------------------
# Reassign
# -----------------------------------------------------
@router.patch("/appointments/{appointment_id}/reassign", response_model=AppointmentOut)
def reassign(appointment_id: int, req: ReassignRequest, db: Session = Depends(get_db)):
    ap = (
        db.query(Appointment)
        .options(joinedload(Appointment.case).joinedload(Case.building))
        .get(appointment_id)
    )
    if not ap:
        raise HTTPException(404, "Appointment not found")
    ins = db.query(Inspector).get(req.inspector_id)
    if not ins:
        raise HTTPException(404, "Inspector not found")
    if not ins.user_id:
        raise HTTPException(400, "Inspector is not linked to a user account; cannot assign")

    ap.inspector_id = req.inspector_id
    # Keep case assignment in sync so Case Management and inspector console reflect the reassignment.
    # Reset case status to pending so the new inspector can confirm/reject.
    if ap.case:
        ap.case.assigned_inspector_id = ins.user_id
        ap.case.status = "pending"
    ap.status = "pending"
    db.commit()
    db.refresh(ap)

    lat = lng = None
    if ap.case and ap.case.building:
        lat = ap.case.building.latitude
        lng = ap.case.building.longitude

    return AppointmentOut(
        id=ap.id,
        case_id=ap.case_id,
        inspector_id=ap.inspector_id,
        start_time=ap.start_time,
        end_time=ap.end_time,
        status=ap.status,
        title=getattr(ap.case, "title", None),
        lat=lat,
        lng=lng,
    )


# -----------------------------------------------------
# Overview (uses unified load logic)
# -----------------------------------------------------
@router.get("/schedule/overview", response_model=OverviewOut)
def schedule_overview(
    day: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    d = day or datetime.utcnow().date()

    inspectors = (
        db.query(Inspector)
        .filter(Inspector.active == True)
        .order_by(Inspector.name.asc())
        .all()
    )

    active_counts = _current_load_by_inspector(db)

    start_dt = datetime.combine(d, datetime.min.time())
    end_dt = datetime.combine(d, datetime.max.time())

    appts = (
        db.query(Appointment)
        .options(joinedload(Appointment.case).joinedload(Case.building))
        .filter(Appointment.start_time >= start_dt)
        .filter(Appointment.start_time <= end_dt)
        .order_by(Appointment.start_time.asc())
        .all()
    )

    appts_by_ins: dict[int | None, list[AppointmentOut]] = {}
    for a in appts:
        lat = lng = None
        if a.case and a.case.building:
            lat = a.case.building.latitude
            lng = a.case.building.longitude
        effective_status = a.case.status if a.case and a.case.status else a.status

        item = AppointmentOut(
            id=a.id,
            case_id=a.case_id,
            inspector_id=a.inspector_id,
            start_time=a.start_time,
            end_time=a.end_time,
            status=effective_status,
            title=getattr(a.case, "title", None),
            lat=lat,
            lng=lng,
        )
        appts_by_ins.setdefault(a.inspector_id, []).append(item)

    out_list: List[OverviewInspector] = []
    for ins in inspectors:
        out_list.append(
            OverviewInspector(
                inspector_id=ins.id,
                inspector_name=ins.name,
                capacity=None,
                active_cases=int(active_counts.get(ins.id, 0)),
                appointments=appts_by_ins.get(ins.id, []),
            )
        )

    return OverviewOut(day=d, inspectors=out_list)


# -----------------------------------------------------
# Auto-assign
# -----------------------------------------------------
@router.post("/schedule/auto-assign", response_model=List[AssignmentResult])
def auto_assign(req: AutoAssignRequest, db: Session = Depends(get_db)):
    cases = (
        db.query(Case)
        .options(joinedload(Case.building))
        .filter(Case.id.in_(req.case_ids))
        .all()
    )
    if not cases:
        raise HTTPException(404, "No cases found")

    inspectors = db.query(Inspector).filter(Inspector.active == True).all()
    if not inspectors:
        raise HTTPException(400, "No inspectors available")

    loads = _current_load_by_inspector(db)

    results: List[AssignmentResult] = []
    start_base = req.start_time or datetime.utcnow()

    for idx, c in enumerate(cases):
        if not c.building:
            continue
        lat, lng = c.building.latitude, c.building.longitude

        scored = []
        for ins in inspectors:
            if req.strategy == "proximity" and ins.home_lat is not None:
                d = haversine_km(lat, lng, ins.home_lat, ins.home_lng)
                s = d + 0.5 * float(loads.get(ins.id, 0))
                scored.append((ins, s, d))
            else:
                s = float(loads.get(ins.id, 0))
                scored.append((ins, s, None))
        scored.sort(key=lambda t: t[1])
        best, score, dist = scored[0]

        slot_start = start_base + (idx * timedelta(minutes=req.duration_minutes))
        slot_end = slot_start + timedelta(minutes=req.duration_minutes)

        ap = Appointment(
            case_id=c.id,
            inspector_id=best.id,
            start_time=slot_start,
            end_time=slot_end,
            status="pending",
            notes=f"auto-assign:{req.strategy}",
        )
        db.add(ap)
        loads[best.id] = loads.get(best.id, 0) + 1

        results.append(
            AssignmentResult(
                case_id=c.id,
                inspector_id=best.id,
                reason=("distance_km" if dist is not None else "balanced_load"),
                score=float(score),
            )
        )

    db.commit()
    return results
