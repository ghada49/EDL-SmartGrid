from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import require_roles


router = APIRouter(prefix="/inspections", tags=["inspections"])


@router.post("/assign", dependencies=[Depends(require_roles("Inspector", "Manager", "Admin"))])
def assign_inspection():
    return {"ok": True, "message": "Inspection assigned"}

