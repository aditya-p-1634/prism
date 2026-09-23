from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.models.enums import PriorityClassEnum

class HouseholdDTO(BaseModel):
    id: str
    habitation_id: str
    anonymized_code: str
    member_count: int
    vulnerable_elderly: int
    vulnerable_children: int
    mobility_impaired: int
    assistance_required: bool
    has_partial_data: bool

class HabitationDTO(BaseModel):
    id: str
    study_area_id: str
    code: str
    name: str
    settlement_type: str
    population_estimate: int
    geom_geojson: Dict[str, Any]
    centroid_geojson: Dict[str, Any]
    elevation_m: float
    total_households: int = 0
    priority_breakdown: Dict[str, int] = {}

class ExposureAssessmentDTO(BaseModel):
    id: str
    habitation_id: str
    snapshot_id: str
    exposure_score: float
    is_in_red_zone: bool
    flood_depth_m: float
    time_to_impact_hours: float

class VulnerabilityProfileDTO(BaseModel):
    id: str
    household_id: str
    snapshot_id: str
    vulnerability_score: float
    demographic_factor: float
    assistance_factor: float
    accessibility_risk_factor: float

class PriorityRecordDTO(BaseModel):
    id: str
    habitation_id: str
    household_id: str
    snapshot_id: str
    habitation_name: Optional[str] = None
    household_code: Optional[str] = None
    priority_score: float
    priority_class: PriorityClassEnum
    reason_codes: List[str]
    component_scores: Dict[str, float]
