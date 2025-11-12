from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
import os, shutil
from backend.models import ops as models

from backend.db import get_db        # ✅ from backend/db.py
from backend.models.ops import Ticket   # ✅ reuse existing Ticket table

router = APIRouter(prefix="/tickets", tags=["Citizen"])

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# 1️⃣ Submit a complaint
@router.post("/")
async def submit_ticket(
    subject: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    photo_path = None
    if file:
        file_name = f"ticket_{int(datetime.now().timestamp())}_{file.filename}"
        photo_path = os.path.join(UPLOAD_DIR, file_name)
        with open(photo_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    ticket = Ticket(
        subject=subject,
        description=description,
        photo_path=photo_path,
        status="New",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # Create a Case for case management
    case = models.Case(status="New")
    db.add(case)
    db.add(
        models.CaseActivity(
            case=case,
            actor="citizen",
            action="FROM_TICKET",
            note=f"Created from ticket #{ticket.id}: {subject}",
        )
    )
    db.commit()
    db.refresh(case)
    return {
        "ticket_id": ticket.id,
        "status": ticket.status,
        "created_at": ticket.created_at,
        "case_id": case.id,
    }


# 2️⃣ Track ticket status by ID
@router.get("/{ticket_id}")
def track_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {
        "ticket_id": ticket.id,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status,
        "photo_path": ticket.photo_path,
        "created_at": ticket.created_at,
    }


# 3️⃣ Add follow-up note or evidence
@router.post("/{ticket_id}/followup")
async def add_followup(
    ticket_id: int,
    note: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    followup_path = None
    if file:
        fname = f"followup_{ticket_id}_{int(datetime.now().timestamp())}_{file.filename}"
        followup_path = os.path.join(UPLOAD_DIR, fname)
        with open(followup_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # Append note inline for now
    ticket.description += f"\n\n[Follow-up {datetime.now().strftime('%Y-%m-%d %H:%M')}]: {note}"
    db.commit()
    return {"message": "Follow-up added", "ticket_id": ticket.id}
