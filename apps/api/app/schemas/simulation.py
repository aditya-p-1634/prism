from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.enums import SimulationStatusEnum, SimulationEventTypeEnum, ResourceStatusEnum

class SimulationRunCreateDTO(BaseModel):
    scenario_code: str = "MONSOON_SURGE_01"
    scenario_snapshot_id: Optional[str] = None
    timestep_minutes: float = Field(default=5.0, description="Simulation timestep in model minutes")
    duration_minutes: float = Field(default=60.0, description="Total simulation duration in model minutes")
    auto_admit_shelter: bool = Field(default=True, description="Automatically transition ARRIVED groups to SHELTERED")
    parameter_overrides: Dict[str, Any] = Field(default_factory=dict, description="Scenario overrides (e.g. rainfall_multiplier_delta, water_consumption_per_person_per_min)")

class SimulationRunExecuteDTO(BaseModel):
    max_steps: Optional[int] = Field(default=None, description="Optional maximum number of steps to advance")

class SimulationEventDTO(BaseModel):
    id: str
    simulation_run_id: str
    simulation_time_min: float
    tick_index: int
    event_type: SimulationEventTypeEnum
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    details: Dict[str, Any]
    created_at: Optional[datetime] = None

class SimulationRunResponseDTO(BaseModel):
    id: str
    scenario_id: Optional[str] = None
    scenario_snapshot_id: str
    status: SimulationStatusEnum
    timestep_minutes: float
    duration_minutes: float
    current_simulation_time: float
    ticks_completed: int
    total_ticks: int
    parameters: Dict[str, Any]
    summary_metrics: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class SimulationStepResponseDTO(BaseModel):
    run: SimulationRunResponseDTO
    tick_index: int
    simulation_time_min: float
    events_generated: List[SimulationEventDTO]
    state_summary: Dict[str, Any]

# -------------------------------------------------------------
# Phase A.4 Dynamic Resource Schemas
# -------------------------------------------------------------

class ResourceStateDTO(BaseModel):
    id: Optional[str] = None
    destination_id: str
    resource_category: str
    resource_type: str
    total_quantity: float
    consumed_quantity: float
    remaining_quantity: float
    unit: str
    supportable_population: int
    status: ResourceStatusEnum

class DestinationResourceSummaryDTO(BaseModel):
    destination_id: str
    destination_code: str
    destination_name: str
    is_safe: bool
    is_feasible: bool
    effective_capacity: int
    occupied_population: int
    effective_remaining_capacity: int
    uncommitted_planned_demand: int
    bottleneck_resource: str
    resources: List[ResourceStateDTO]

class SimulationResourcesResponseDTO(BaseModel):
    simulation_run_id: str
    simulation_time_min: float
    tick_index: int
    destinations: List[DestinationResourceSummaryDTO]

# -------------------------------------------------------------
# Phase A.5 Observability & Operational Metrics Schemas
# -------------------------------------------------------------

class SimulationTimelineEventDTO(BaseModel):
    id: str
    simulation_run_id: str
    simulation_time_min: float
    tick_index: int
    event_type: SimulationEventTypeEnum
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

class SimulationTimelineResponseDTO(BaseModel):
    run_id: str
    total_events: int
    returned_events: int
    limit: int
    offset: int
    events: List[SimulationTimelineEventDTO]

class SimulationPopulationStateDTO(BaseModel):
    total_population: int
    affected_population: int
    counts_by_state: Dict[str, int]
    allocation_counts_by_state: Dict[str, int]
    planned_population: int
    in_transit_population: int
    arrived_population: int
    sheltered_population: int
    stuck_population: int
    route_blocked_population: int
    assistance_required_population: int
    no_response_population: int

class SimulationInfrastructureStateDTO(BaseModel):
    blocked_roads_count: int
    open_roads_count: int
    blocked_road_codes: List[str]
    invalidated_routes_count: int
    active_routes_count: int
    reroute_counts: int
    failed_reroutes: int

class SimulationPlanningStateDTO(BaseModel):
    allocation_count: int
    unmet_demand_count: int
    unmet_demand_population: int
    reallocation_count: int
    infeasible_destinations_count: int

class ConsolidatedSimulationStateDTO(BaseModel):
    run_id: str
    scenario_id: Optional[str] = None
    snapshot_id: str
    status: SimulationStatusEnum
    current_simulation_time: float
    current_tick: int
    total_ticks: int
    timestep_minutes: float
    duration_minutes: float
    progress_percentage: float
    population: SimulationPopulationStateDTO
    infrastructure: SimulationInfrastructureStateDTO
    resources: List[DestinationResourceSummaryDTO]
    planning: SimulationPlanningStateDTO
    recent_events: List[SimulationTimelineEventDTO]
    event_counts_by_type: Dict[str, int]
    latest_important_event: Optional[SimulationTimelineEventDTO] = None

class SimulationOperationalMetricsDTO(BaseModel):
    run_id: str
    snapshot_id: str
    status: SimulationStatusEnum
    current_simulation_time: float
    ticks_completed: int
    total_ticks: int
    progress_pct: float
    total_population: int
    sheltered_population: int
    in_transit_population: int
    stuck_population: int
    route_blocked_population: int
    assistance_required_population: int
    planned_population: int
    population_by_state: Dict[str, int]
    allocations_by_state: Dict[str, int]
    blocked_roads_count: int
    active_routes_count: int
    invalidated_routes_count: int
    reroute_count: int
    failed_reroute_count: int
    total_physical_capacity: int
    total_effective_capacity: int
    total_occupied_capacity: int
    total_remaining_capacity: int
    overall_occupancy_pct: float
    total_water_consumed_liters: float
    destinations_constrained_count: int
    destinations_exhausted_count: int
    destinations_infeasible_count: int
    unmet_demand_count: int
    unmet_demand_population: int
    total_events_recorded: int
    counts_by_event_type: Dict[str, int]


