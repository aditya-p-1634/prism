from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.models.enums import OperationalStatusEnum, AllocationStatusEnum, PriorityClassEnum

class RoadSegmentDTO(BaseModel):
    id: str
    segment_code: str
    u_node_id: str
    v_node_id: str
    road_class: str
    length_meters: float
    max_speed_kmh: float
    geom_geojson: Dict[str, Any]
    operational_status: OperationalStatusEnum
    hazard_risk_score: float
    is_bridge: bool

class RoutePlanDTO(BaseModel):
    id: str
    origin_habitation_id: str
    destination_id: str
    snapshot_id: str
    origin_name: Optional[str] = None
    destination_name: Optional[str] = None
    total_distance_m: float
    total_time_min: float
    route_cost: float
    geom_geojson: Dict[str, Any]
    path_nodes: List[str]
    is_viable: bool
    invalidated_reason: Optional[str] = None

class RelocationGroupDTO(BaseModel):
    id: str
    habitation_id: str
    household_id: str
    snapshot_id: str
    group_size: int
    priority_score: float
    priority_class: PriorityClassEnum
    requires_special_transit: bool

class RelocationAllocationDTO(BaseModel):
    id: str
    group_id: str
    destination_id: Optional[str]
    route_plan_id: Optional[str]
    snapshot_id: str
    habitation_name: Optional[str] = None
    destination_name: Optional[str] = None
    allocation_status: AllocationStatusEnum
    assigned_capacity_count: int
    reason_code: str

class RelocationOverrideDTO(BaseModel):
    allocation_id: str
    new_destination_id: str
    justification: str
