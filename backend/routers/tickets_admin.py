from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models.ops import Ticket
from backend.deps import require_roles

router = APIRouter(prefix="/tickets", tags=["Admin"])


@router.get("")
def list_tickets(
    db: Session = Depends(get_db),
    _=Depends(require_roles("Admin", "Manager", "Inspector")),
):
    rows = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    return [
        {
            "id": t.id,
            "subject": t.subject,
            "description": t.description,
            "status": t.status,
            "photo_path": t.photo_path,
            "created_at": t.created_at,
            "user_id": t.user_id,
        }
        for t in rows
    ]

