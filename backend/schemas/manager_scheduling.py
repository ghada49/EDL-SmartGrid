# backend/schemas/manager_scheduling.py
from datetime import datetime, date
from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, Field

class InspectorOut(BaseModel):
    id: int
    name: str
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None
    active: bool = True
    user_id: Optional[str] = None
    model_config = {"from_attributes": True}

class AppointmentOut(BaseModel):
    id: int
    case_id: int
    inspector_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    status: str
    title: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    model_config = {"from_attributes": True}

class WorkloadItem(BaseModel):
    inspector_id: int
    inspector_name: str
    active_cases: int
    appointments_this_week: int

class SuggestAssignmentsRequest(BaseModel):
    strategy: str = Field(pattern=r"^(proximity|workload)$", default="proximity")
    # either send case_id OR raw coordinates
    case_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    top_k: int = 5

class SuggestionOut(BaseModel):
    inspector_id: int
    inspector_name: str
    score: float    # lower distance or lower load → better (explain in UI)
    reason: str

class AssignRequest(BaseModel):
    case_id: int
    inspector_id: int
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None
    target_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    target_lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0)

class RescheduleRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    inspector_id: Optional[int] = None  # if provided → reassign

class ReassignRequest(BaseModel):
    inspector_id: int





# Already have: InspectorOut, AppointmentOut, WorkloadItem, SuggestAssignmentsRequest, SuggestionOut,
# AssignRequest, RescheduleRequest, ReassignRequest

class OverviewInspector(BaseModel):
    inspector_id: int
    inspector_name: str
    capacity: int | None = None
    active_cases: int = 0
    appointments: List["AppointmentOut"] = []

class OverviewOut(BaseModel):
    day: date
    inspectors: List[OverviewInspector]

class AutoAssignRequest(BaseModel):
    case_ids: List[int]
    strategy: Literal["proximity", "balanced"] = "proximity"
    start_time: Optional[datetime] = None
    duration_minutes: int = 45          # default slot length
    max_radius_km: float = 15.0

class AssignmentResult(BaseModel):
    case_id: int
    inspector_id: int
    reason: str
    score: float

class KPIResponse(BaseModel):
    frm: date
    to: date
    area: Optional[str] = None
    fraud_rate: float
    closure_stats: Dict[str, int]
    bias_by_district: List[Dict] = []

class ExportQuery(BaseModel):
    frm: date
    to: date
    kind: Literal["kpis","appointments","cases"] = "kpis"
    fmt: Literal["xlsx","pdf"] = "xlsx"

# Align label literals with the frontend options so validation succeeds.
LabelStr = Literal["fraud", "non_fraud", "uncertain"]
SourceStr = Literal["field_verification","billing_audit","manual_review","manager_ui","other"]

class FeedbackLabelIn(BaseModel):
    case_id: int
    label: LabelStr
    source: SourceStr = "field_verification"
    notes: Optional[str] = None

class FeedbackLabelOut(BaseModel):
    id: int
    case_id: int
    label: LabelStr
    source: SourceStr
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2; use orm_mode=True for v1

class FeedbackLogItem(FeedbackLabelOut):
    meter_id: Optional[str] = None
