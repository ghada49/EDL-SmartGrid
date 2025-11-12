from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from ..db import Base

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    upload_time = Column(DateTime, default=datetime.utcnow)
    row_count = Column(Integer)
    status = Column(String, default="active")  # optional: active/archived
    uploaded_by = Column(String, nullable=True)  # optional, if auth connected
