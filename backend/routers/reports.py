from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import require_roles


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/kpi", dependencies=[Depends(require_roles("Manager", "Admin"))])
def get_kpis():
    # Placeholder KPI set
    return {
        "total_cases": 0,
        "resolved": 0,
        "avg_inspection_time_days": 0.0,
        "district_breakdown": {},
    }

