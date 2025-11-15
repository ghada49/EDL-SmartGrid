# backend/routers/manager_scheduling.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import datetime, date, timedelta
from typing import List, Optional


from ..db import get_db
from ..models import Inspector, Appointment, Case, Building
from ..schemas.manager_scheduling import (
    InspectorOut, AppointmentOut, WorkloadItem,
    SuggestAssignmentsRequest, SuggestionOut,
    AssignRequest, RescheduleRequest, ReassignRequest,
     AutoAssignRequest, AssignmentResult,OverviewOut, OverviewInspector
)
from ..utils.assign import haversine_km, week_bounds


router = APIRouter(prefix="/manager/scheduling", tags=["Manager Scheduling"])
# … (rest of the code you already have)
@router.get("/ping")
def ping():
    return {"ok": True}

# -----------------------
# Inspectors & calendar
# -----------------------

@router.get("/inspectors", response_model=List[InspectorOut])
def list_inspectors(active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(Inspector)
    if active_only:
        q = q.filter(Inspector.active == True)  # noqa: E712
    return q.order_by(Inspector.name.asc()).all()

@router.get("/appointments", response_model=List[AppointmentOut])
def all_appointments(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    inspector_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = (db.query(Appointment)
           .options(joinedload(Appointment.case).joinedload(Case.building))
           .order_by(Appointment.start_time.asc()))

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
        if a.case and a.case.building:
            lat = a.case.building.latitude
            lng = a.case.building.longitude
        out.append(AppointmentOut(
            id=a.id, case_id=a.case_id, inspector_id=a.inspector_id,
            start_time=a.start_time, end_time=a.end_time,
            status=a.status, title=title, lat=lat, lng=lng
        ))
    return out

# -----------------------
# Workload summary
# -----------------------

@router.get("/workload", response_model=List[WorkloadItem])
def workload(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    wstart, wend = week_bounds(now)

    # active cases per inspector (cases with at least one open appointment)
    active_q = (
        db.query(Inspector.id.label("iid"), Inspector.name.label("name"),
                 func.count(Appointment.id).label("active_cases"))
          .join(Appointment, Appointment.inspector_id == Inspector.id, isouter=True)
          .filter((Appointment.status != "closed") | (Appointment.id.is_(None)))
          .group_by(Inspector.id)
    ).subquery()

    # appointments this week
    week_q = (
        db.query(Appointment.inspector_id.label("iid"),
                 func.count(Appointment.id).label("week_appts"))
          .filter(Appointment.start_time >= wstart)
          .filter(Appointment.start_time <= wend)
          .group_by(Appointment.inspector_id)
    ).subquery()

    res = (
        db.query(
            active_q.c.iid, active_q.c.name,
            func.coalesce(active_q.c.active_cases, 0),
            func.coalesce(week_q.c.week_appts, 0),
        )
        .outerjoin(week_q, week_q.c.iid == active_q.c.iid)
        .order_by(active_q.c.name.asc())
        .all()
    )

    out = [
        WorkloadItem(
            inspector_id=r[0],
            inspector_name=r[1],
            active_cases=int(r[2] or 0),
            appointments_this_week=int(r[3] or 0),
        ) for r in res
    ]
    return out

# -----------------------
# Auto-assignment suggestions
# -----------------------

@router.post("/suggest", response_model=List[SuggestionOut])
def suggest(req: SuggestAssignmentsRequest, db: Session = Depends(get_db)):
    # 1) get target lat/lng
    lat = req.lat
    lng = req.lng
    if req.case_id and (lat is None or lng is None):
        c = db.query(Case).options(joinedload(Case.building)).get(req.case_id)
        if not c or not c.building:
            raise HTTPException(404, "Case or building not found")
        lat = c.building.latitude
        lng = c.building.longitude
    if lat is None or lng is None:
        raise HTTPException(400, "Provide case_id or lat/lng")

    inspectors = db.query(Inspector).filter(Inspector.active == True).all()  # noqa: E712

    # current load per inspector
    load = dict(
        db.query(Appointment.inspector_id, func.count(Appointment.id))
          .filter(Appointment.status.in_(["pending", "accepted"]))
          .group_by(Appointment.inspector_id)
          .all()
    )

    scores: List[SuggestionOut] = []
    for ins in inspectors:
        if req.strategy == "proximity" and ins.home_lat is not None and ins.home_lng is not None:
            d = haversine_km(lat, lng, ins.home_lat, ins.home_lng)
            scores.append(SuggestionOut(
                inspector_id=ins.id, inspector_name=ins.name,
                score=round(d, 3), reason="distance_km"
            ))
        else:
            l = float(load.get(ins.id, 0))
            scores.append(SuggestionOut(
                inspector_id=ins.id, inspector_name=ins.name,
                score=l, reason="current_load"
            ))

    # lower score is better
    scores.sort(key=lambda s: s.score)
    return scores[: req.top_k]

# -----------------------
# Create/assign & reschedule
# -----------------------

@router.post("/assign", response_model=AppointmentOut)
def assign_visit(req: AssignRequest, db: Session = Depends(get_db)):
    ins = db.query(Inspector).get(req.inspector_id)
    if not ins:
        raise HTTPException(404, "Inspector not found")
    c = db.query(Case).get(req.case_id)
    if not c:
        raise HTTPException(404, "Case not found")

    # Also reflect the assignment on the case itself so the manager UI shows the inspector.
    if ins.user_id:
        c.assigned_inspector_id = ins.user_id
    

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
    title = getattr(c, "title", None) or f"Case #{c.id}"
    if c.building:
        lat = c.building.latitude
        lng = c.building.longitude

    return AppointmentOut(
        id=ap.id, case_id=ap.case_id, inspector_id=ap.inspector_id,
        start_time=ap.start_time, end_time=ap.end_time, status=ap.status,
        title=title, lat=lat, lng=lng
    )

@router.patch("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule(appointment_id: int, req: RescheduleRequest, db: Session = Depends(get_db)):
    ap = db.query(Appointment).options(joinedload(Appointment.case).joinedload(Case.building)).get(appointment_id)
    if not ap:
        raise HTTPException(404, "Appointment not found")

    ap.start_time = req.start_time
    ap.end_time = req.end_time
    if req.inspector_id is not None:
        if not db.query(Inspector).get(req.inspector_id):
            raise HTTPException(404, "Inspector not found")
        ap.inspector_id = req.inspector_id

    db.add(ap)
    db.commit()
    db.refresh(ap)

    lat = lng = None
    title = getattr(ap.case, "title", None) or f"Case #{ap.case_id}"
    if ap.case and ap.case.building:
        lat = ap.case.building.latitude
        lng = ap.case.building.longitude

    return AppointmentOut(
        id=ap.id, case_id=ap.case_id, inspector_id=ap.inspector_id,
        start_time=ap.start_time, end_time=ap.end_time, status=ap.status,
        title=title, lat=lat, lng=lng
    )

@router.patch("/appointments/{appointment_id}/reassign", response_model=AppointmentOut)
def reassign(appointment_id: int, req: ReassignRequest, db: Session = Depends(get_db)):
    ap = db.query(Appointment).options(joinedload(Appointment.case).joinedload(Case.building)).get(appointment_id)
    if not ap:
        raise HTTPException(404, "Appointment not found")
    if not db.query(Inspector).get(req.inspector_id):
        raise HTTPException(404, "Inspector not found")

    ap.inspector_id = req.inspector_id
    db.add(ap)
    db.commit()
    db.refresh(ap)

    lat = lng = None
    title = getattr(ap.case, "title", None) or f"Case #{ap.case_id}"
    if ap.case and ap.case.building:
        lat = ap.case.building.latitude
        lng = ap.case.building.longitude

    return AppointmentOut(
        id=ap.id, case_id=ap.case_id, inspector_id=ap.inspector_id,
        start_time=ap.start_time, end_time=ap.end_time, status=ap.status,
        title=title, lat=lat, lng=lng
    )





# NEW: POST /manager/scheduling/schedule/auto-assign
# NEW: GET /manager/scheduling/schedule/overview
@router.get("/schedule/overview", response_model=OverviewOut)
def schedule_overview(
    day: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    d = day or datetime.utcnow().date()

    # inspectors
    inspectors = (
        db.query(Inspector)
          .filter(Inspector.active == True)  # noqa: E712
          .order_by(Inspector.name.asc())
          .all()
    )

    # counts per inspector
    from sqlalchemy import func, and_
    active_counts = dict(
        db.query(Appointment.inspector_id, func.count(Appointment.id))
          .filter(Appointment.status.in_(["pending","accepted"]))
          .group_by(Appointment.inspector_id)
          .all()
    )

    # appointments for the chosen day
    start_dt = datetime.combine(d, datetime.min.time())
    end_dt   = datetime.combine(d, datetime.max.time())
    appts = (
        db.query(Appointment)
          .options(joinedload(Appointment.case).joinedload(Case.building))
          .filter(Appointment.start_time >= start_dt, Appointment.start_time <= end_dt)
          .order_by(Appointment.start_time.asc())
          .all()
    )

    appts_by_ins: dict[int, list[AppointmentOut]] = {}
    for a in appts:
        lat = lng = None
        title = getattr(a.case, "title", None) or f"Case #{a.case_id}"
        if a.case and a.case.building:
            lat = a.case.building.latitude
            lng = a.case.building.longitude
        item = AppointmentOut(
            id=a.id, case_id=a.case_id, inspector_id=a.inspector_id,
            start_time=a.start_time, end_time=a.end_time,
            status=a.status, title=title, lat=lat, lng=lng
        )
        appts_by_ins.setdefault(a.inspector_id or -1, []).append(item)

    out_list: List[OverviewInspector] = []
    for ins in inspectors:
        out_list.append(OverviewInspector(
            inspector_id=ins.id,
            inspector_name=ins.name,
            capacity=None,
            active_cases=int(active_counts.get(ins.id, 0)),
            appointments=appts_by_ins.get(ins.id, [])
        ))

    return OverviewOut(day=d, inspectors=out_list)

@router.post("/schedule/auto-assign", response_model=List[AssignmentResult])
def auto_assign(req: AutoAssignRequest, db: Session = Depends(get_db)):
    # reuse your proximity/balanced logic from /suggest
    # 1) resolve case coordinates
    cases = (
        db.query(Case)
          .options(joinedload(Case.building))
          .filter(Case.id.in_(req.case_ids))
          .all()
    )
    if not cases:
        raise HTTPException(404, "No cases found")

    inspectors = db.query(Inspector).filter(Inspector.active == True).all()  # noqa: E712
    if not inspectors:
        raise HTTPException(400, "No inspectors available")

    # current load
    from sqlalchemy import func
    loads = dict(
        db.query(Appointment.inspector_id, func.count(Appointment.id))
          .filter(Appointment.status.in_(["pending","accepted"]))
          .group_by(Appointment.inspector_id)
          .all()
    )

    results: List[AssignmentResult] = []
    start_base = req.start_time or datetime.utcnow()

    for idx, c in enumerate(cases):
        if not c.building:
            continue
        lat, lng = c.building.latitude, c.building.longitude

        # score each inspector
        scored = []
        for ins in inspectors:
            if req.strategy == "proximity" and ins.home_lat is not None and ins.home_lng is not None:
                d = haversine_km(lat, lng, ins.home_lat, ins.home_lng)
                # distance + current load (lower better)
                s = d + 0.5 * float(loads.get(ins.id, 0))
                scored.append((ins, s, d))
            else:
                s = float(loads.get(ins.id, 0))
                scored.append((ins, s, None))
        scored.sort(key=lambda t: t[1])
        best, score, dist = scored[0]

        # create appointment slot
        slot_start = start_base + (idx * timedelta(minutes=req.duration_minutes))
        slot_end   = slot_start + timedelta(minutes=req.duration_minutes)
        ap = Appointment(
            case_id=c.id,
            inspector_id=best.id,
            start_time=slot_start,
            end_time=slot_end,
            status="pending",
            notes=f"auto-assign:{req.strategy}"
        )
        db.add(ap)
        loads[best.id] = loads.get(best.id, 0) + 1
        results.append(AssignmentResult(
            case_id=c.id, inspector_id=best.id,
            reason=("distance_km" if dist is not None else "balanced_load"),
            score=float(score)
        ))

    db.commit()
    return results

