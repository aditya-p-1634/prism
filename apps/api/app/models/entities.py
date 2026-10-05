import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, ForeignKey, DateTime, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import (
    DataQualityEnum, FreshnessEnum, OperationalStatusEnum, StateTypeEnum,
    PriorityClassEnum, ResourceCategoryEnum, AllocationStatusEnum, RoleEnum, JobStatusEnum,
    EvacuationStateEnum, ResourceStatusEnum, SimulationStatusEnum, SimulationEventTypeEnum,
    ObservationQualityEnum, HazardMeasurementTypeEnum
)

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# -------------------------------------------------------------
# 1. System, Users, Provenance & Snapshots
# -------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(SAEnum(RoleEnum), default=RoleEnum.VIEWER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class StateSnapshot(Base):
    __tablename__ = "state_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="RESTRICT"), nullable=True)
    snapshot_type = Column(String(50), default="BASELINE", nullable=False) # BASELINE or SCENARIO
    label = Column(String(255), nullable=False)
    is_immutable = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    scenario = relationship("Scenario", back_populates="snapshots")

class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    parameters = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    snapshots = relationship("StateSnapshot", back_populates="scenario")

class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    organization = Column(String(255), nullable=True)
    authority_level = Column(String(100), nullable=True)
    quality_rating = Column(SAEnum(DataQualityEnum), default=DataQualityEnum.HIGH, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class Observation(Base):
    __tablename__ = "observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_id = Column(String(36), ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=True)
    subject_type = Column(String(100), nullable=False) # RIVER_GAUGE, RAIN_STATION, ROAD_CAMERA
    location_geom = Column(Text, nullable=True) # GeoJSON Point
    observed_at = Column(DateTime, nullable=False)
    raw_value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    quality = Column(SAEnum(DataQualityEnum), default=DataQualityEnum.HIGH, nullable=False)
    freshness = Column(SAEnum(FreshnessEnum), default=FreshnessEnum.FRESH, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

# -------------------------------------------------------------
# 2. Study Area & Hazard Intelligence (E1)
# -------------------------------------------------------------

class StudyArea(Base):
    __tablename__ = "study_areas"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    boundary_geom = Column(Text, nullable=False) # GeoJSON Polygon
    crs_code = Column(String(50), default="EPSG:4326", nullable=False)
    computational_crs = Column(String(50), default="EPSG:32643", nullable=False)
    timezone = Column(String(100), default="Asia/Kolkata", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class HazardState(Base):
    __tablename__ = "hazard_states"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    study_area_id = Column(String(36), ForeignKey("study_areas.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    hazard_type = Column(String(50), default="FLOOD", nullable=False)
    severity = Column(String(50), default="HIGH", nullable=False)
    geom = Column(Text, nullable=False) # GeoJSON MultiPolygon
    state_type = Column(SAEnum(StateTypeEnum), default=StateTypeEnum.OBSERVED, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class HazardPrediction(Base):
    __tablename__ = "hazard_predictions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    hazard_state_id = Column(String(36), ForeignKey("hazard_states.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    horizon_hours = Column(Float, default=6.0, nullable=False)
    predicted_extent_geom = Column(Text, nullable=False) # GeoJSON MultiPolygon
    expansion_factor = Column(Float, default=1.0, nullable=False)
    confidence = Column(Float, default=0.85, nullable=False)
    method_identifier = Column(String(100), default="PLANAR_PROJECTED_BUFFER_v1", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class RedZone(Base):
    __tablename__ = "red_zones"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    study_area_id = Column(String(36), ForeignKey("study_areas.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    designation_code = Column(String(100), nullable=False)
    hazard_type = Column(String(50), default="FLOOD", nullable=False)
    geom = Column(Text, nullable=False) # GeoJSON MultiPolygon
    operational_status = Column(SAEnum(OperationalStatusEnum), default=OperationalStatusEnum.ACTIVE, nullable=False)
    reason_code = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    evidences = relationship("HazardEvidence", back_populates="red_zone", cascade="all, delete-orphan")

class HazardEvidence(Base):
    __tablename__ = "hazard_evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    red_zone_id = Column(String(36), ForeignKey("red_zones.id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    measured_value = Column(Float, nullable=False)
    threshold_value = Column(Float, nullable=False)
    source_reference = Column(String(255), nullable=True)

    red_zone = relationship("RedZone", back_populates="evidences")

# -------------------------------------------------------------
# 3. People, Habitations & Priority (E2)
# -------------------------------------------------------------

class Habitation(Base):
    __tablename__ = "habitations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    study_area_id = Column(String(36), ForeignKey("study_areas.id", ondelete="RESTRICT"), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    settlement_type = Column(String(100), default="RURAL_VILLAGE", nullable=False)
    population_estimate = Column(Integer, default=0, nullable=False)
    geom = Column(Text, nullable=False) # GeoJSON Polygon
    centroid_geom = Column(Text, nullable=False) # GeoJSON Point
    elevation_m = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    households = relationship("Household", back_populates="habitation")

class Household(Base):
    __tablename__ = "households"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    habitation_id = Column(String(36), ForeignKey("habitations.id", ondelete="RESTRICT"), nullable=False)
    anonymized_code = Column(String(100), unique=True, nullable=False, index=True)
    member_count = Column(Integer, default=1, nullable=False)
    vulnerable_elderly = Column(Integer, default=0, nullable=False)
    vulnerable_children = Column(Integer, default=0, nullable=False)
    mobility_impaired = Column(Integer, default=0, nullable=False)
    assistance_required = Column(Boolean, default=False, nullable=False)
    has_partial_data = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    habitation = relationship("Habitation", back_populates="households")

class ExposureAssessment(Base):
    __tablename__ = "exposure_assessments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    habitation_id = Column(String(36), ForeignKey("habitations.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    exposure_score = Column(Float, default=0.0, nullable=False) # 0 to 100
    is_in_red_zone = Column(Boolean, default=False, nullable=False)
    flood_depth_m = Column(Float, default=0.0, nullable=False)
    time_to_impact_hours = Column(Float, default=999.0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class VulnerabilityProfile(Base):
    __tablename__ = "vulnerability_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    household_id = Column(String(36), ForeignKey("households.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    vulnerability_score = Column(Float, default=0.0, nullable=False) # 0 to 100
    demographic_factor = Column(Float, default=0.0, nullable=False)
    assistance_factor = Column(Float, default=0.0, nullable=False)
    accessibility_risk_factor = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class PriorityRecord(Base):
    __tablename__ = "priority_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    habitation_id = Column(String(36), ForeignKey("habitations.id", ondelete="RESTRICT"), nullable=False)
    household_id = Column(String(36), ForeignKey("households.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    priority_score = Column(Float, default=0.0, nullable=False) # 0 to 100
    priority_class = Column(SAEnum(PriorityClassEnum), default=PriorityClassEnum.MEDIUM_TERM, nullable=False)
    reason_codes = Column(JSON, default=list, nullable=False) # list of reason strings
    component_scores = Column(JSON, default=dict, nullable=False) # {exposure, vulnerability, urgency, access, assistance}
    created_at = Column(DateTime, default=utc_now, nullable=False)

# -------------------------------------------------------------
# 4. Destinations & Carrying Capacity (E3)
# -------------------------------------------------------------

class Destination(Base):
    __tablename__ = "destinations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    study_area_id = Column(String(36), ForeignKey("study_areas.id", ondelete="RESTRICT"), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    facility_type = Column(String(100), default="COMMUNITY_CENTER", nullable=False)
    location_geom = Column(Text, nullable=False) # GeoJSON Point
    boundary_geom = Column(Text, nullable=True) # GeoJSON Polygon
    operational_status = Column(SAEnum(OperationalStatusEnum), default=OperationalStatusEnum.OPEN, nullable=False)
    suitability_score = Column(Float, default=100.0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    resources = relationship("DestinationResource", back_populates="destination", cascade="all, delete-orphan")

class DestinationResource(Base):
    __tablename__ = "destination_resources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    destination_id = Column(String(36), ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    resource_type = Column(SAEnum(ResourceCategoryEnum), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    supportable_population = Column(Integer, nullable=False)
    is_critical = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    destination = relationship("Destination", back_populates="resources")

class CapacityState(Base):
    __tablename__ = "capacity_states"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    destination_id = Column(String(36), ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    effective_capacity = Column(Integer, default=0, nullable=False)
    occupied_capacity = Column(Integer, default=0, nullable=False)
    remaining_capacity = Column(Integer, default=0, nullable=False)
    bottleneck_resource = Column(String(100), nullable=False) # e.g. "WATER", "SHELTER"
    is_safe = Column(Boolean, default=True, nullable=False)
    rejection_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

# -------------------------------------------------------------
# 5. Road Network, Routing & Relocation Optimization (E4)
# -------------------------------------------------------------

class RoadNode(Base):
    __tablename__ = "road_nodes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    study_area_id = Column(String(36), ForeignKey("study_areas.id", ondelete="RESTRICT"), nullable=False)
    node_code = Column(String(100), unique=True, nullable=False, index=True)
    location_geom = Column(Text, nullable=False) # GeoJSON Point
    elevation_m = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class RoadSegment(Base):
    __tablename__ = "road_segments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    study_area_id = Column(String(36), ForeignKey("study_areas.id", ondelete="RESTRICT"), nullable=False)
    segment_code = Column(String(100), unique=True, nullable=False, index=True)
    u_node_id = Column(String(36), ForeignKey("road_nodes.id", ondelete="RESTRICT"), nullable=False)
    v_node_id = Column(String(36), ForeignKey("road_nodes.id", ondelete="RESTRICT"), nullable=False)
    road_class = Column(String(100), default="PRIMARY", nullable=False) # PRIMARY, SECONDARY, BRIDGE
    length_meters = Column(Float, nullable=False)
    max_speed_kmh = Column(Float, default=40.0, nullable=False)
    geom = Column(Text, nullable=False) # GeoJSON LineString
    operational_status = Column(SAEnum(OperationalStatusEnum), default=OperationalStatusEnum.OPEN, nullable=False)
    hazard_risk_score = Column(Float, default=0.0, nullable=False) # 0 to 1
    is_bridge = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class RoutePlan(Base):
    __tablename__ = "route_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    origin_habitation_id = Column(String(36), ForeignKey("habitations.id", ondelete="RESTRICT"), nullable=False)
    destination_id = Column(String(36), ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    total_distance_m = Column(Float, nullable=False)
    total_time_min = Column(Float, nullable=False)
    route_cost = Column(Float, nullable=False)
    geom = Column(Text, nullable=False) # GeoJSON LineString
    path_nodes = Column(JSON, default=list, nullable=False) # list of node codes
    is_viable = Column(Boolean, default=True, nullable=False)
    invalidated_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class RelocationGroup(Base):
    __tablename__ = "relocation_groups"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    habitation_id = Column(String(36), ForeignKey("habitations.id", ondelete="RESTRICT"), nullable=False)
    household_id = Column(String(36), ForeignKey("households.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    group_size = Column(Integer, default=1, nullable=False)
    priority_score = Column(Float, default=0.0, nullable=False)
    priority_class = Column(SAEnum(PriorityClassEnum), default=PriorityClassEnum.MEDIUM_TERM, nullable=False)
    requires_special_transit = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class RelocationAllocation(Base):
    __tablename__ = "relocation_allocations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    group_id = Column(String(36), ForeignKey("relocation_groups.id", ondelete="RESTRICT"), nullable=False)
    destination_id = Column(String(36), ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=True)
    route_plan_id = Column(String(36), ForeignKey("route_plans.id", ondelete="RESTRICT"), nullable=True)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="RESTRICT"), nullable=False)
    allocation_status = Column(SAEnum(AllocationStatusEnum), default=AllocationStatusEnum.RECOMMENDED, nullable=False)
    evacuation_state = Column(SAEnum(EvacuationStateEnum), default=EvacuationStateEnum.PLANNED, nullable=False)
    assigned_capacity_count = Column(Integer, default=0, nullable=False)
    reason_code = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

# -------------------------------------------------------------
# 6. Jobs, Events & Audit (E6)
# -------------------------------------------------------------

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_type = Column(String(100), nullable=False) # OPTIMIZE_RELOCATION, RUN_SCENARIO
    status = Column(SAEnum(JobStatusEnum), default=JobStatusEnum.PENDING, nullable=False)
    progress_pct = Column(Integer, default=0, nullable=False)
    input_payload = Column(JSON, default=dict, nullable=False)
    result_payload = Column(JSON, default=dict, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

class Event(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class EventDelivery(Base):
    __tablename__ = "event_deliveries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    consumer_engine = Column(String(50), nullable=False) # E1, E2, E3, E4, E5, E6
    is_delivered = Column(Boolean, default=False, nullable=False)
    delivered_at = Column(DateTime, nullable=True)

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(String(100), nullable=False) # AUTHORITY_OVERRIDE, SCENARIO_RUN
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(36), nullable=False)
    before_state = Column(JSON, default=dict, nullable=True)
    after_state = Column(JSON, default=dict, nullable=True)
    justification = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

# -------------------------------------------------------------
# 7. Temporal Simulation Clock & Dynamic Execution (E5 - A.3)
# -------------------------------------------------------------

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True)
    scenario_snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="CASCADE"), nullable=False)
    status = Column(SAEnum(SimulationStatusEnum), default=SimulationStatusEnum.CREATED, nullable=False)
    timestep_minutes = Column(Float, default=5.0, nullable=False)
    duration_minutes = Column(Float, default=60.0, nullable=False)
    current_simulation_time = Column(Float, default=0.0, nullable=False)
    ticks_completed = Column(Integer, default=0, nullable=False)
    total_ticks = Column(Integer, default=12, nullable=False)
    parameters = Column(JSON, default=dict, nullable=False)
    summary_metrics = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    events = relationship("SimulationEvent", back_populates="simulation_run", cascade="all, delete-orphan")
    progress_records = relationship("SimulationAllocationProgress", back_populates="simulation_run", cascade="all, delete-orphan")
    resource_states = relationship("SimulationResourceState", back_populates="simulation_run", cascade="all, delete-orphan")

class SimulationEvent(Base):
    __tablename__ = "simulation_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    simulation_run_id = Column(String(36), ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False)
    simulation_time_min = Column(Float, nullable=False)
    tick_index = Column(Integer, nullable=False)
    event_type = Column(SAEnum(SimulationEventTypeEnum), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(String(36), nullable=True)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    simulation_run = relationship("SimulationRun", back_populates="events")

class SimulationAllocationProgress(Base):
    __tablename__ = "simulation_allocation_progress"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    simulation_run_id = Column(String(36), ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False)
    allocation_id = Column(String(36), ForeignKey("relocation_allocations.id", ondelete="CASCADE"), nullable=False)
    route_plan_id = Column(String(36), ForeignKey("route_plans.id", ondelete="SET NULL"), nullable=True)
    original_route_plan_id = Column(String(36), nullable=True)
    elapsed_time_min = Column(Float, default=0.0, nullable=False)
    total_travel_time_min = Column(Float, default=0.0, nullable=False)
    progress_ratio = Column(Float, default=0.0, nullable=False) # 0.0 to 1.0
    is_blocked = Column(Boolean, default=False, nullable=False)
    reroute_count = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    simulation_run = relationship("SimulationRun", back_populates="progress_records")

class SimulationResourceState(Base):
    __tablename__ = "simulation_resource_states"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    simulation_run_id = Column(String(36), ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False)
    destination_id = Column(String(36), ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False)
    resource_category = Column(String(50), nullable=False) # POPULATION_SPACE, WATER, MEDICAL_CAPACITY
    resource_type = Column(SAEnum(ResourceCategoryEnum), nullable=False)
    total_quantity = Column(Float, nullable=False)
    consumed_quantity = Column(Float, default=0.0, nullable=False)
    remaining_quantity = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    supportable_population = Column(Integer, nullable=False)
    status = Column(SAEnum(ResourceStatusEnum), default=ResourceStatusEnum.NORMAL, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    simulation_run = relationship("SimulationRun", back_populates="resource_states")
    destination = relationship("Destination")

# -------------------------------------------------------------
# 8. Hybrid Hazard Prediction Layer (A.6)
# -------------------------------------------------------------

class HazardPredictionRecord(Base):
    __tablename__ = "hazard_prediction_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    simulation_run_id = Column(String(36), ForeignKey("simulation_runs.id", ondelete="SET NULL"), nullable=True)
    snapshot_id = Column(String(36), ForeignKey("state_snapshots.id", ondelete="SET NULL"), nullable=True)
    hazard_type = Column(String(50), default="RIVER_FLOOD", nullable=False)
    target_metric = Column(String(50), default="RIVER_STAGE_M", nullable=False)
    source_time_min = Column(Float, nullable=False)
    target_time_min = Column(Float, nullable=False)
    horizon_minutes = Column(Float, nullable=False)
    predicted_value = Column(Float, nullable=False)
    raw_model_value = Column(Float, nullable=False)
    lower_bound = Column(Float, nullable=False)
    upper_bound = Column(Float, nullable=False)
    uncertainty_metric = Column(Float, nullable=False)
    confidence = Column(Float, nullable=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), default="1.0.0", nullable=False)
    method = Column(String(100), default="AUTOREGRESSIVE_RIDGE", nullable=False)
    validation_status = Column(String(50), default="VALID", nullable=False) # VALID, CORRECTED, REJECTED, DEGRADED
    validation_reason = Column(Text, nullable=True)
    lifecycle_state = Column(String(50), default="VALIDATED", nullable=True) # PREDICTED, VALIDATED, DEGRADED, OUT_OF_DOMAIN, REJECTED, EVALUATED_BY_E1
    feature_provenance = Column(JSON, default=dict, nullable=False)
    domain_alerts = Column(JSON, default=list, nullable=False)
    actual_value = Column(Float, nullable=True)
    evaluation_error = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

# -------------------------------------------------------------
# 9. Real-World Hazard Data & Telemetry Observations (A.7)
# -------------------------------------------------------------

class HazardStation(Base):
    __tablename__ = "hazard_stations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    station_code = Column(String(100), unique=True, nullable=False, index=True)
    station_name = Column(String(255), nullable=False)
    river = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    state = Column(String(100), default="Tamil Nadu", nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    hazard_type = Column(SAEnum(HazardMeasurementTypeEnum), default=HazardMeasurementTypeEnum.RIVER_WATER_LEVEL, nullable=False)
    unit = Column(String(50), default="metres", nullable=False)
    source = Column(String(255), default="Tamil Nadu River Water Level Telemetry Hourly", nullable=False)
    source_dataset = Column(String(255), default="tn_water_resources_telemetry_hourly", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    warning_threshold_m = Column(Float, nullable=True)  # Authoritative threshold if known, else None
    danger_threshold_m = Column(Float, nullable=True)   # Authoritative threshold if known, else None
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    observations = relationship("HazardObservation", back_populates="station", cascade="all, delete-orphan")


class HazardObservation(Base):
    __tablename__ = "hazard_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    station_id = Column(String(36), ForeignKey("hazard_stations.id", ondelete="RESTRICT"), nullable=False, index=True)
    station_code = Column(String(100), nullable=False, index=True)
    station_name = Column(String(255), nullable=False)
    river = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    hazard_type = Column(SAEnum(HazardMeasurementTypeEnum), default=HazardMeasurementTypeEnum.RIVER_WATER_LEVEL, nullable=False)
    source = Column(String(255), nullable=False)
    source_dataset = Column(String(255), nullable=False)
    observed_at = Column(DateTime, nullable=False, index=True)
    ingested_at = Column(DateTime, default=utc_now, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), default="metres", nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    quality_status = Column(SAEnum(ObservationQualityEnum), default=ObservationQualityEnum.VALID, nullable=False, index=True)
    quality_flags = Column(JSON, default=list, nullable=False)
    freshness = Column(SAEnum(FreshnessEnum), default=FreshnessEnum.FRESH, nullable=False)
    raw_reference = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    station = relationship("HazardStation", back_populates="observations")


