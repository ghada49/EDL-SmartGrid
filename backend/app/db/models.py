from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True)
    role = Column(String, nullable=False)  # admin, inspector, citizen

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

    cases = relationship("Case", back_populates="building")

class Case(Base):
    __tablename__ = "cases"
    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"))
    status = Column(String, default="open")  # open, investigating, closed
    notes = Column(String, nullable=True)

    building = relationship("Building", back_populates="cases")

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subject = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="open")

class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)