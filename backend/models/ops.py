# backend/models/ops.py
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
from sqlalchemy.sql import func

from ..db import Base


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

    # Add this:
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    subject = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="New")
    photo_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")



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

    # Who created the case (manager/admin username or id)
    created_by = Column(String, nullable=True)

    # Match users.id which is a String (UUID)
    assigned_inspector_id = Column(String, ForeignKey("users.id"), nullable=True)

    # New → Scheduled → Visited → Reported → Closed
    # (also works fine if some old code uses "open"/"investigating"/"closed")
    status = Column(String, default="New")

    # For simple outcomes / new KPI logic
    outcome = Column(String, nullable=True)        # e.g. "Fraud", "No Issue", "Recheck"
    final_outcome = Column(String, nullable=True)  # e.g. "fraud" | "non_fraud" | None

    # For reports / KPIs
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    notes = Column(String, nullable=True)

    # Relationships
    building = relationship("Building", back_populates="cases")

    # from “old” ops.py (scheduling / feedback)
    appointments = relationship(
        "Appointment",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    feedback_labels = relationship(
        "FeedbackLabel",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    # from “new” case-management branch
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

    # Match users.id type (String UUID)
    inspector_id = Column(String, ForeignKey("users.id"), nullable=True)

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
