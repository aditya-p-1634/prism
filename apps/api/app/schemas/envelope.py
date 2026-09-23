from pydantic import BaseModel, Field
from typing import TypeVar, Generic, Optional, List, Dict, Any
from app.models.enums import DataQualityEnum

T = TypeVar("T")

class ResponseEnvelope(BaseModel, Generic[T]):
    request_id: str
    correlation_id: str
    snapshot_id: Optional[str] = None
    scenario_id: Optional[str] = None
    contract_version: str = "1.0"
    data_quality: DataQualityEnum = DataQualityEnum.HIGH
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    data: T
    warnings: List[str] = Field(default_factory=list)

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False

class ErrorEnvelope(BaseModel):
    error: ErrorDetail
    request_id: str
    correlation_id: str
