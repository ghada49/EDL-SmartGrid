from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class Building(BaseModel):
    building_code: Optional[str] = None
    electricity_kwh: float = Field(ge=0)
    area_m2: float = Field(gt=0)
    year_construction: int = Field(ge=1900, le=2025)
    num_floors: int = Field(ge=1)
    num_apartments: int = Field(ge=1)
    function: str
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)

    @field_validator("function")
    @classmethod
    def check_function(cls, v: str) -> str:
        allowed = {"Residentiel", "Mixte"}
        if v not in allowed:
            raise ValueError(f"function must be one of {allowed}")
        return v


class ScoreOut(BaseModel):
    building_code: Optional[str] = None
    score: float
    is_fraud: bool
    components: Dict[str, float]
    peer_group: Dict[str, Any] = {}


class BatchIn(BaseModel):
    items: List[Building]

