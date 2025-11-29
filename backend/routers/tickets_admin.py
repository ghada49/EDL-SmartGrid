from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.db import get_db
from backend.models.ops import Ticket
from backend.deps import require_roles

router = APIRouter(prefix="/tickets", tags=["Admin"])


@router.get("")
def list_tickets(
    db: Session = Depends(get_db),
    _=Depends(require_roles("Admin", "Manager", "Inspector")),
):
    rows = (
        db.query(Ticket)
        .options(joinedload(Ticket.user))
        .order_by(Ticket.created_at.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "subject": t.subject,
            "description": t.description,
            "status": t.status,
            "photo_path": t.photo_path,
            "created_at": t.created_at,
            "user_id": t.user_id,
            "user_name": t.user.full_name if t.user else None,
            "user_email": t.user.email if t.user else None,
        }
        for t in rows
    ]


@router.patch("/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    _=Depends(require_roles("Admin", "Manager", "Inspector")),
):
    allowed_statuses = {"New", "In Review", "Closed"}
    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400, detail=f"Status must be one of {sorted(allowed_statuses)}"
        )

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status == "Closed":
        raise HTTPException(
            status_code=400, detail="Closed tickets cannot be updated"
        )

    ticket.status = status
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"id": ticket.id, "status": ticket.status}
