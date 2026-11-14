from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class FieldObservationCreateDTO(BaseModel):
    snapshot_id: str = Field(..., min_length=1)
    observation_type: str = Field(..., min_length=3, max_length=50)
    target_type: str = Field(..., min_length=3, max_length=50)
    target_id: str = Field(..., min_length=1)
    observed_state: str = Field(..., min_length=1, max_length=100)
    observed_value: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=50)
    observed_at: datetime
    source_reference: str = Field(..., min_length=2, max_length=255)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(timezone.utc)


class FieldObservationResponseDTO(BaseModel):
    id: str
    snapshot_id: str
    observation_type: str
    target_type: str
    target_id: str
    observed_state: str
    observed_value: Optional[float] = None
    unit: Optional[str] = None
    observed_at: datetime
    source_reference: str
    confidence: float
    quality_status: str
    reconciliation_status: str
    reconciliation_result: Dict[str, Any] = Field(default_factory=dict)


class FieldReconciliationDTO(BaseModel):
    observation_id: str
    snapshot_id: str
    reconciliation_status: str
    requires_human_review: bool
    expected_state: Optional[str] = None
    observed_state: str
    conflict_reason: Optional[str] = None
    plan_mutated: bool = False
