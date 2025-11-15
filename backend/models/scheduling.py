from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.db import Base
from datetime import datetime

# ... your Appointment & Inspector stay the same

class FeedbackLabel(Base):
    __tablename__ = "feedback_labels"
   
    actor = relationship("User", lazy="joined")

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    meter_id = Column(String, nullable=True)           # optional if you store it on Case
    label = Column(String, nullable=False)             # store literal label strings (fraud/non_fraud/uncertain)
    source = Column(String, default="field_verification")
    notes = Column(String, nullable=True)
    actor_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="feedback_labels", lazy="joined")

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    inspector_id = Column(Integer, ForeignKey("inspectors.id"), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, default="pending")       # pending/accepted/closed
    notes = Column(String, nullable=True)

    case = relationship("Case", back_populates="appointments")
    inspector = relationship("Inspector", back_populates="appointments")

class Inspector(Base):
    __tablename__ = "inspectors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    home_lat = Column(Float, nullable=True)
    home_lng = Column(Float, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, unique=True)

    # link to appointments
    appointments = relationship(
        "Appointment",
        back_populates="inspector",
        cascade="all, delete-orphan",
    )
    user = relationship("User", lazy="joined")
