from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.models.enums import StateTypeEnum, OperationalStatusEnum

class HazardEvidenceDTO(BaseModel):
    id: str
    metric_name: str
    measured_value: float
    threshold_value: float
    source_reference: Optional[str] = None

class RedZoneDTO(BaseModel):
    id: str
    study_area_id: str
    snapshot_id: str
    designation_code: str
    hazard_type: str
    geom_geojson: Dict[str, Any]
    operational_status: OperationalStatusEnum
    reason_code: str
    evidences: List[HazardEvidenceDTO] = []

class HazardStateDTO(BaseModel):
    id: str
    study_area_id: str
    snapshot_id: str
    hazard_type: str
    severity: str
    geom_geojson: Dict[str, Any]
    state_type: StateTypeEnum
    confidence: float

class HazardPredictionDTO(BaseModel):
    id: str
    hazard_state_id: str
    snapshot_id: str
    horizon_hours: float
    predicted_extent_geojson: Dict[str, Any]
    expansion_factor: float
    confidence: float
    method_identifier: str
