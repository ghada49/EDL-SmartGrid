from __future__ import annotations

import os

from sqlalchemy.orm import Session

# Use absolute imports so this script works with `python backend/seed_admin.py`
from backend.config import settings
from backend.db import Base, engine, SessionLocal
from backend.models.user import User
from backend.security import get_password_hash


def seed_admin() -> None:
    Base.metadata.create_all(bind=engine)
    admin_email = os.getenv("ADMIN_EMAIL", "admin@municipality.gov.lb")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin123!")

    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            print("Admin already exists:", admin_email)
            return
        admin = User(
            email=admin_email,
            hashed_password=get_password_hash(admin_password),
            role="Admin",
            full_name="System Administrator",
        )
        db.add(admin)
        db.commit()
        print("Admin user created:", admin_email)
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
