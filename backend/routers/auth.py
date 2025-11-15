# backend/routers/auth.py
from __future__ import annotations
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db, Base, engine
from ..models.user import User
from ..schemas.auth import UserCreate, UserLogin, UserOut, Token
from ..security import verify_password, get_password_hash, create_access_token
from ..deps import require_roles, get_current_user
from .users import ensure_inspector_profile
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# One place creates tables (OK for MVP; prefer Alembic later)
Base.metadata.create_all(bind=engine)

@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    # Always create as Citizen on public signup
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role="Citizen",
        is_active=True,   # set False if you add email verification later
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user: Optional[User] = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    token = create_access_token(
        {"sub": user.id, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=token)

@router.post("/signup/admin", response_model=UserOut, dependencies=[Depends(require_roles("Admin"))])
def admin_create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_user),
):
    if payload.role not in {"Citizen", "Inspector", "Manager", "Admin"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role or "Citizen",
        is_active=True,
    )
    db.add(user)
    db.flush()
    if user.role == "Inspector":
        ensure_inspector_profile(db, user, active=True)
    db.commit()
    db.refresh(user)
    return user
