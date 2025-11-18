# backend/routers/tickets.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
from pathlib import Path
import os, shutil

from backend.db import get_db
from backend.models.ops import Ticket
from backend.models import ops as models
from backend.deps import get_current_user, require_roles
from backend.models.user import User

router = APIRouter(prefix="/tickets", tags=["Tickets"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _public_photo_path(filename: str) -> str:
    """Ensure we expose a consistent web path irrespective of OS path separators."""
    filename = filename.replace("\\", "/")
    if filename.startswith("data/"):
        return filename
    # try to locate the uploads folder in absolute paths
    idx = filename.find("data/uploads")
    if idx != -1:
        return filename[idx:]
    return f"data/uploads/{Path(filename).name}"


def _serialize_ticket(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status,
        "photo_path": _public_photo_path(ticket.photo_path)
        if ticket.photo_path
        else None,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "user_id": ticket.user_id,
    }


# -------------------------------------------------------------
# 1️⃣ Citizen submits a ticket — must be logged in
# -------------------------------------------------------------
@router.post("/")
async def submit_ticket(
    subject: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),   # ⬅ logged in user
):
    photo_path = None

    # Validate file type (security)
    if file:
        if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            raise HTTPException(status_code=400, detail="Only PNG/JPG allowed.")

        file_name = f"ticket_{int(datetime.now().timestamp())}_{file.filename}"
        photo_path = os.path.join(UPLOAD_DIR, file_name)

        with open(photo_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # Save ticket with owner
    ticket = Ticket(
        user_id=current_user.id,
        subject=subject,
        description=description,
        photo_path=photo_path,
        status="New",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {
        "ticket_id": ticket.id,
        "status": ticket.status,
        "created_at": ticket.created_at,
    }


# -------------------------------------------------------------
# 2️⃣ Citizen fetches ONLY their own tickets
# -------------------------------------------------------------
@router.get("/mine")
def get_my_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tickets = (
        db.query(Ticket)
        .filter(Ticket.user_id == current_user.id)
        .order_by(Ticket.created_at.desc())
        .all()
    )
    return tickets


# -------------------------------------------------------------
# 3️⃣ Ticket detail — restricted:
#    ✔ Citizen → only own tickets
#    ✔ Manager/Admin → all
# -------------------------------------------------------------
@router.get("/{ticket_id}")
def track_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Citizen can ONLY see their own ticket
    if current_user.role == "Citizen" and ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return ticket


# -------------------------------------------------------------
# 4️⃣ Add follow-up — only owner or admin/manager
# -------------------------------------------------------------
@router.post("/{ticket_id}/followup")
async def add_followup(
    ticket_id: int,
    note: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Authorization
    if current_user.role == "Citizen" and ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    followup_path = None
    if file:
        if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            raise HTTPException(status_code=400, detail="Only PNG/JPG allowed.")

        fname = f"followup_{ticket_id}_{int(datetime.now().timestamp())}_{file.filename}"
        followup_path = os.path.join(UPLOAD_DIR, fname)

        with open(followup_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # Append note to description (simple version)
    ticket.description += f"\n\n[Follow-up {datetime.now().strftime('%Y-%m-%d %H:%M')} - {current_user.email}]: {note}"

    db.commit()
    return {"message": "Follow-up added", "ticket_id": ticket.id}
