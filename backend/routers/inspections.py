from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models.ops import Case, CaseActivity, InspectionReport

router = APIRouter(prefix="/inspections", tags=["Inspections"])


# Inspector submits a report for a case
@router.post("/{case_id}/report", dependencies=[Depends(require_roles("Inspector"))])
def submit_report(
    case_id: int,
    inspector_id: str = Form(...),
    findings: str = Form(...),
    recommendation: str = Form(...),
    db: Session = Depends(get_db),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    report = InspectionReport(
        case_id=case.id,
        inspector_id=inspector_id,
        findings=findings,
        recommendation=recommendation,
        status="Pending",
    )
    db.add(report)

    case.status = "Reported"
    db.add(
        CaseActivity(
            case_id=case.id,
            actor=f"Inspector {inspector_id}",
            action="REPORT_SUBMITTED",
            note="Inspector submitted report",
        )
    )

    db.commit()
    db.refresh(report)
    return {"message": "Report submitted", "report_id": report.id}


# Manager/Admin approves / rejects / recheck report
@router.post("/{case_id}/review", dependencies=[Depends(require_roles("Manager", "Admin"))])
def review_report(
    case_id: int,
    decision: str,  # "Fraud", "No Issue", "Recheck"
    db: Session = Depends(get_db),
):
    allowed = ["Fraud", "No Issue", "Recheck"]
    if decision not in allowed:
        raise HTTPException(status_code=400, detail=f"Decision must be one of {allowed}")

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get latest report
    report = (
        db.query(InspectionReport)
        .filter(InspectionReport.case_id == case.id)
        .order_by(InspectionReport.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=400, detail="No inspection report to review")

    if decision == "Fraud":
        report.status = "Approved"
        case.outcome = "Fraud"
        case.status = "Reported"
    elif decision == "No Issue":
        report.status = "Approved"
        case.outcome = "No Issue"
        case.status = "Reported"
    elif decision == "Recheck":
        report.status = "Recheck"
        case.outcome = "Recheck"
        case.status = "Scheduled"

    db.add(report)
    db.add(case)

    db.add(
        CaseActivity(
            case_id=case.id,
            actor="Manager",
            action="DECISION",
            note=f"Case marked as {decision}",
        )
    )

    db.commit()
    return {
        "case_id": case.id,
        "status": case.status,
        "outcome": case.outcome,
        "report_status": report.status,
    }
