# backend/models/__init__.py

from .user import User
from .dataset_version import DatasetVersion  # if this exists
# from .data_upload import DataUpload  # noqa: F401  # uncomment if you use it

from .ops import (
    Building,
    Case,
    Ticket,
    ModelVersion,
    CaseActivity,
    InspectionReport,
    CaseAttachment,
)

from .scheduling import Inspector, Appointment, FeedbackLabel

__all__ = [
    "User",
    "DatasetVersion",
    # "DataUpload",  # add here if you uncomment it above
    "Building",
    "Case",
    "Ticket",
    "ModelVersion",
    "CaseActivity",
    "InspectionReport",
    "CaseAttachment",
    "Inspector",
    "Appointment",
    "FeedbackLabel",
]
