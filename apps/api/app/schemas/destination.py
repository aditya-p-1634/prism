from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.models.enums import OperationalStatusEnum, ResourceCategoryEnum

class DestinationResourceDTO(BaseModel):
    id: str
    destination_id: str
    resource_type: ResourceCategoryEnum
    quantity: float
    unit: str
    supportable_population: int
    is_critical: bool

class CapacityStateDTO(BaseModel):
    id: str
    destination_id: str
    snapshot_id: str
    effective_capacity: int
    occupied_capacity: int
    remaining_capacity: int
    bottleneck_resource: str
    is_safe: bool
    rejection_reason: Optional[str] = None

class DestinationDTO(BaseModel):
    id: str
    study_area_id: str
    code: str
    name: str
    facility_type: str
    location_geojson: Dict[str, Any]
    operational_status: OperationalStatusEnum
    suitability_score: float
    capacity_state: Optional[CapacityStateDTO] = None
    resources: List[DestinationResourceDTO] = []
