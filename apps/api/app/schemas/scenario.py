from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ScenarioDTO(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any]

class ScenarioRunRequestDTO(BaseModel):
    scenario_code: str = "MONSOON_SURGE_01"
    parameter_overrides: Dict[str, Any] = {}

class DeltaReportDTO(BaseModel):
    scenario_code: str
    baseline_snapshot_id: str
    scenario_snapshot_id: str
    hazard_delta: Dict[str, Any]
    priority_shifts: Dict[str, Any]
    capacity_changes: Dict[str, Any]
    route_invalidations: List[str]
    reallocated_groups_count: int
    unmet_demand_delta: int
    summary_explanation: str
