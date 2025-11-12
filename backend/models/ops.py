from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from ..db import Base
from sqlalchemy.sql import func


# ---------- Buildings ----------

class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True, index=True)
    building_name = Column(String, nullable=True)
    construction_year = Column(Integer, nullable=True)
    num_floors = Column(Integer, nullable=True)
    num_apartments = Column(Integer, nullable=True)
    longitude = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    total_kwh = Column(Float, nullable=True)
    district = Column(String, nullable=True)  # optional: for filtering

    cases = relationship("Case", back_populates="building")


# ---------- Citizen Tickets ----------

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subject = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="New")
    photo_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------- Model Versions ----------

class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)


# ---------- Case Management ----------

class Case(Base):
    """
    Manager-facing investigation case.
    """

    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)

    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    anomaly_id = Column(Integer, nullable=True)  # optional link to anomaly/table row

    created_by = Column(String, nullable=True)  # username or id of creator (Manager/Admin)
    # Match users.id which is a String (UUID)
    assigned_inspector_id = Column(String, ForeignKey("users.id"), nullable=True)

    # New → Scheduled → Visited → Reported → Closed
    status = Column(String, default="New")

    # Fraud / No Issue / Recheck / None
    outcome = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    building = relationship("Building", back_populates="cases")
    activities = relationship(
        "CaseActivity",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseActivity.created_at",
    )
    reports = relationship(
        "InspectionReport",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="InspectionReport.created_at",
    )
    attachments = relationship(
        "CaseAttachment",
        back_populates="case",
        cascade="all, delete-orphan",
    )


class CaseActivity(Base):
    """
    Timeline / activity log entries (status changes, assignments, comments, etc.).
    """

    __tablename__ = "case_activities"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)

    actor = Column(String, nullable=True)   # e.g., "manager_1", "inspector_5"
    action = Column(String, nullable=False) # e.g., STATUS_UPDATE / ASSIGN / COMMENT
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="activities")


class InspectionReport(Base):
    """
    Inspector's report attached to a case; Manager can approve/reject.
    """

    __tablename__ = "inspection_reports"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    findings = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)

    # Pending / Approved / Rejected / Recheck
    status = Column(String, default="Pending")

    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="reports")


class CaseAttachment(Base):
    """
    Files/photos attached to a case.
    """

    __tablename__ = "case_attachments"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    filename = Column(String, nullable=False)
    path = Column(String, nullable=False)
    uploaded_by = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="attachments")
