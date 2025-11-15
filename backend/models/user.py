# backend/models/user.py
from __future__ import annotations

import uuid

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import validates

from ..db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        String,
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)

    # Roles: "Admin", "Manager", "Inspector", "Citizen"
    role = Column(String, nullable=False, default="Citizen")

    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    @validates("role")
    def normalize_role(self, key, value: str | None) -> str:
        """
        Normalize role strings so they always have the expected capitalization.
        This keeps the DB consistent with what the frontend expects.
        """
        if not value:
            return "Citizen"

        value = value.lower()
        mapping = {
            "admin": "Admin",
            "manager": "Manager",
            "inspector": "Inspector",
            "citizen": "Citizen",
        }
        # fallback: if it's some other role, just return as-is
        return mapping.get(value, value)
