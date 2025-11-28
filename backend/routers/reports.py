from __future__ import annotations

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..deps import require_roles
from ..models import Appointment, Building, Case, FeedbackLabel, Inspector

router = APIRouter(prefix="/reports", tags=["reports"])


def _build_analytics(db: Session) -> Dict:
    now = datetime.utcnow()
    total_cases = db.query(func.count(Case.id)).scalar() or 0
    closed_cases = db.query(func.count(Case.id)).filter(Case.status == "closed").scalar() or 0
    open_cases = total_cases - closed_cases

    case_ages = (
        db.query(Case.opened_at)
        .filter(Case.opened_at.isnot(None))
        .all()
    )
    avg_case_age = 0.0
    if case_ages:
        avg_case_age = sum((now - row[0]).days for row in case_ages) / len(case_ages)

    # Normalize labels in SQL to avoid case/whitespace issues
    normalized_label = func.lower(func.trim(FeedbackLabel.label))
    total_feedback = db.query(func.count(FeedbackLabel.id)).scalar() or 0
    fraud_feedback = (
        db.query(func.count(FeedbackLabel.id))
        .filter(normalized_label == "fraud")
        .scalar()
        or 0
    )
    nonfraud_feedback = (
        db.query(func.count(FeedbackLabel.id))
        .filter(normalized_label == "non_fraud")
        .scalar()
        or 0
    )
    fraud_rate = fraud_feedback / total_feedback if total_feedback else 0.0

    district_rows = (
        db.query(Building.district, func.count(Case.id))
        .join(Building, Case.building_id == Building.id)
        .group_by(Building.district)
        .all()
    )
    district_alerts = [
        {
            "district": district or "Unknown",
            "total_alerts": count,
            "alert_rate": count / total_cases if total_cases else 0.0,
        }
        for district, count in district_rows
    ]

    productivity_rows = (
        db.query(
            Inspector.name.label("name"),
            func.count(Appointment.id).label("visits"),
            func.sum(
                case((Appointment.status == "closed", 1), else_=0)
            ).label("closed"),
        )
        .outerjoin(Appointment, Appointment.inspector_id == Inspector.id)
        .group_by(Inspector.id)
        .order_by(Inspector.name.asc())
        .all()
    )
    inspector_productivity = [
        {
            "inspector": row.name,
            "visits": int(row.visits or 0),
            "closed": int(row.closed or 0),
        }
        for row in productivity_rows
    ]

    labels = (
        db.query(FeedbackLabel)
        .options(joinedload(FeedbackLabel.case).joinedload(Case.building))
        .order_by(FeedbackLabel.created_at.asc())
        .all()
    )
    month_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"fraud": 0, "total": 0})
    bias_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"fraud": 0, "non_fraud": 0})
    for label in labels:
        label_val = (label.label or "").strip().lower()
        created = label.created_at or now
        month_key = created.strftime("%Y-%m")
        month_stats[month_key]["total"] += 1
        if label_val == "fraud":
            month_stats[month_key]["fraud"] += 1

        district = "Unknown"
        if label.case and label.case.building and label.case.building.district:
            district = label.case.building.district
        if label_val == "fraud":
            bias_stats[district]["fraud"] += 1
        elif label_val == "non_fraud":
            bias_stats[district]["non_fraud"] += 1

    fraud_trend = [
        {
            "period": month,
            "fraud_rate": (
                stats["fraud"] / stats["total"] if stats["total"] else 0.0
            ),
            "total": stats["total"],
            "fraud": stats["fraud"],
        }
        for month, stats in sorted(month_stats.items())
    ]

    bias_trend = [
        {
            "district": district,
            "bias_score": (
                (stats["fraud"] - stats["non_fraud"])
                / max(stats["fraud"] + stats["non_fraud"], 1)
            ),
            "fraud": stats["fraud"],
            "non_fraud": stats["non_fraud"],
        }
        for district, stats in sorted(bias_stats.items())
    ]

    analytics = {
        "kpis": {
            "total_cases": total_cases,
            "open_cases": open_cases,
            "closed_cases": closed_cases,
            "avg_case_age_days": round(avg_case_age, 1),
            "fraud_confirmation_rate": round(fraud_rate, 4),
            "feedback_total": total_feedback,
            "fraud_feedback": fraud_feedback,
            "non_fraud_feedback": nonfraud_feedback,
        },
        "fraud_trend": fraud_trend,
        "district_alerts": district_alerts,
        "inspector_productivity": inspector_productivity,
        "bias_trend": bias_trend,
    }
    return analytics


@router.get("/kpi", dependencies=[Depends(require_roles("Manager", "Admin"))])
def get_kpis(db: Session = Depends(get_db)):
    analytics = _build_analytics(db)
    return analytics["kpis"]


@router.get("/analytics", dependencies=[Depends(require_roles("Manager", "Admin"))])
def get_analytics(db: Session = Depends(get_db)):
    return _build_analytics(db)


@router.get("/export", dependencies=[Depends(require_roles("Manager", "Admin"))])
def export_reports(
    kind: Literal["kpis", "cases", "appointments", "feedback"] = "kpis",
    fmt: Literal["csv"] = "csv",
    frm: Optional[date] = Query(default=None, alias="from"),
    to: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    if fmt != "csv":
        raise HTTPException(status_code=400, detail="Only CSV export is available in this build.")

    output = io.StringIO()
    writer = csv.writer(output)

    if kind == "kpis":
        analytics = _build_analytics(db)
        writer.writerow(["metric", "value"])
        for key, value in analytics["kpis"].items():
            writer.writerow([key, value])
    elif kind == "cases":
        query = db.query(Case).options(joinedload(Case.building))
        if frm:
            query = query.filter(Case.opened_at >= datetime.combine(frm, datetime.min.time()))
        if to:
            query = query.filter(Case.opened_at <= datetime.combine(to, datetime.max.time()))
        writer.writerow(["case_id", "status", "opened_at", "district", "final_outcome"])
        for case_row in query.all():
            district = case_row.building.district if case_row.building else ""
            writer.writerow([
                case_row.id,
                case_row.status,
                case_row.opened_at.isoformat() if case_row.opened_at else "",
                district or "",
                case_row.final_outcome or "",
            ])
    elif kind == "appointments":
        query = db.query(Appointment).options(joinedload(Appointment.inspector))
        if frm:
            query = query.filter(Appointment.start_time >= datetime.combine(frm, datetime.min.time()))
        if to:
            query = query.filter(Appointment.start_time <= datetime.combine(to, datetime.max.time()))
        writer.writerow(["appointment_id", "inspector", "case_id", "status", "start_time", "end_time"])
        for appt in query.all():
            writer.writerow([
                appt.id,
                appt.inspector.name if appt.inspector else "",
                appt.case_id,
                appt.status,
                appt.start_time.isoformat(),
                appt.end_time.isoformat(),
            ])
    elif kind == "feedback":
        query = db.query(FeedbackLabel)
        if frm:
            query = query.filter(FeedbackLabel.created_at >= datetime.combine(frm, datetime.min.time()))
        if to:
            query = query.filter(FeedbackLabel.created_at <= datetime.combine(to, datetime.max.time()))
        writer.writerow(["id", "case_id", "label", "source", "notes", "created_at"])
        for label in query.order_by(FeedbackLabel.created_at.asc()).all():
            writer.writerow([
                label.id,
                label.case_id,
                label.label,
                label.source or "",
                label.notes or "",
                label.created_at.isoformat() if label.created_at else "",
            ])
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported export kind '{kind}'")

    output.seek(0)
    filename = f"{kind}_report.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
