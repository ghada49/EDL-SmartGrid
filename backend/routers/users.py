# backend/routers/users.py
from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models.user import User
from ..models import Inspector
from ..schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])

# ---------- Schemas ----------
class RoleUpdateIn(BaseModel):
    role: Literal["Citizen", "Inspector", "Manager", "Admin"]

class SuspendIn(BaseModel):
    is_active: bool = Field(..., description="false = suspend, true = re-activate")

class ProfileUpdateIn(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=120)


# ---------- Helpers ----------
def _count_admins(db: Session) -> int:
    return db.query(User).filter(User.role == "Admin", User.is_active == True).count()

def ensure_inspector_profile(db: Session, user: User, active: bool = True) -> None:
    """
    Create or update the Inspector profile that backs scheduling.
    Ensures managers immediately see the inspector in dropdowns.
    """
    profile = db.query(Inspector).filter(Inspector.user_id == user.id).first()
    display_name = user.full_name or user.email or f"Inspector {user.id[:8]}"

    if active:
        if profile:
            profile.active = True
            profile.name = display_name
        else:
            profile = Inspector(name=display_name, active=True, user_id=user.id)
            db.add(profile)
    else:
        if profile:
            profile.active = False

    if profile:
        db.add(profile)

# ---------- Routes ----------
@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me")
def update_me(
    payload: ProfileUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
        db.commit()
        db.refresh(current_user)
    return {"status": "ok", "id": current_user.id, "full_name": current_user.full_name}


@router.get(
    "/",
    response_model=List[UserOut],
    dependencies=[Depends(require_roles("Admin", "Manager"))],
)
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch(
    "/{user_id}/role",
    response_model=UserOut,
    dependencies=[Depends(require_roles("Admin", "Manager"))],
)
def update_role(
    user_id: str,
    payload: RoleUpdateIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    new_role = payload.role
    old_role = target.role

    # no self-role change
    if actor.id == target.id:
        raise HTTPException(status_code=403, detail="You cannot change your own role")

    # Policy:
    # - Admin: can set any role, but cannot demote the last Admin
    # - Manager: only Citizen <-> Inspector, and not touching Admin/Manager
    if actor.role == "Admin":
        if target.role == "Admin" and new_role != "Admin":
            if _count_admins(db) <= 1:
                raise HTTPException(status_code=400, detail="Cannot demote the last Admin")
    elif actor.role == "Manager":
        if target.role not in {"Citizen", "Inspector"} or new_role not in {"Citizen", "Inspector"}:
            raise HTTPException(status_code=403, detail="Managers can only change Citizen/Inspector roles")
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    target.role = new_role
    db.add(target)

    if new_role == "Inspector":
        ensure_inspector_profile(db, target, active=True)
    elif old_role == "Inspector" and new_role != "Inspector":
        ensure_inspector_profile(db, target, active=False)

    db.commit()
    db.refresh(target)
    return target


@router.patch(
    "/{user_id}/suspend",
    dependencies=[Depends(require_roles("Admin"))],
)
def suspend_user(
    user_id: str,
    payload: SuspendIn,
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Don’t allow suspending the last active Admin
    if target.role == "Admin" and payload.is_active is False and _count_admins(db) <= 1:
        raise HTTPException(status_code=400, detail="Cannot suspend the last active Admin")

    target.is_active = payload.is_active
    db.commit()
    db.refresh(target)
    return {"status": "ok", "id": target.id, "is_active": target.is_active}
