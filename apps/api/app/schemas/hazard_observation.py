"""
PRISM Phase A.7 — Hazard Observation Schemas
============================================
Pydantic DTO models for real-world telemetry stations, observations,
quality validation, CSV ingestion reports, and observation-driven E1 evaluations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class HazardStationCreateDTO(BaseModel):
    station_code: str = Field(..., description="Unique alphanumeric station code, e.g. NANDAMBAKKAM_CHECKDAM")
    station_name: str = Field(..., description="Human-readable station name")
    river: str = Field(..., description="River name, e.g. Adyar")
    district: str = Field(..., description="District, e.g. Chennai")
    state: str = Field("Tamil Nadu", description="State name")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Station latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Station longitude in decimal degrees")
    hazard_type: str = Field("RIVER_WATER_LEVEL", description="Hazard measurement type")
    unit: str = Field("metres", description="Engineering measurement unit (e.g. metres)")
    source: str = Field("Tamil Nadu River Water Level Telemetry Hourly", description="Source agency / network")
    source_dataset: str = Field("tn_water_resources_telemetry_hourly", description="Source dataset identifier")
    warning_threshold_m: Optional[float] = Field(None, description="Documented warning threshold if known, else None")
    danger_threshold_m: Optional[float] = Field(None, description="Documented critical danger threshold if known, else None")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Additional station metadata")


class HazardStationResponseDTO(BaseModel):
    id: str
    station_code: str
    station_name: str
    river: str
    district: str
    state: str
    latitude: float
    longitude: float
    hazard_type: str
    unit: str
    source: str
    source_dataset: str
    is_active: bool
    warning_threshold_m: Optional[float] = None
    danger_threshold_m: Optional[float] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HazardObservationCreateDTO(BaseModel):
    station_code: str = Field(..., description="Station code matching registered HazardStation")
    observed_at: datetime = Field(..., description="Physical measurement timestamp (UTC or timezone-aware)")
    value: float = Field(..., description="Observed numeric water level measurement")
    unit: str = Field("metres", description="Measurement unit (e.g. metres)")
    source: Optional[str] = Field(None, description="Telemetry source override if different from station")
    source_dataset: Optional[str] = Field(None, description="Source dataset override if different from station")
    raw_reference: Dict[str, Any] = Field(default_factory=dict, description="Raw input record snippet for provenance")


class HazardObservationResponseDTO(BaseModel):
    id: str
    station_id: str
    station_code: str
    station_name: str
    river: str
    district: str
    hazard_type: str
    source: str
    source_dataset: str
    observed_at: datetime
    ingested_at: datetime
    value: float
    unit: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    quality_status: str
    quality_flags: List[str] = Field(default_factory=list)
    freshness: str
    raw_reference: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class CurrentHazardStateResponseDTO(BaseModel):
    station_code: str
    station_name: str
    river: str
    district: str
    observed_at: Optional[datetime] = None
    value: Optional[float] = None
    unit: str
    quality_status: Optional[str] = None
    freshness: str
    is_stale: bool
    source: str
    source_dataset: str
    severity_classification: str
    warning_threshold_m: Optional[float] = None
    danger_threshold_m: Optional[float] = None
    disclaimer: str


class CsvIngestionReportDTO(BaseModel):
    rows_received: int
    rows_accepted: int
    rows_suspect: int
    rows_rejected: int
    duplicates: int
    invalid_timestamps: int
    invalid_values: int
    unknown_stations: int
    rejection_reasons: List[Dict[str, Any]] = Field(default_factory=list)
    ingested_observation_ids: List[str] = Field(default_factory=list)


class CsvImportRequestDTO(BaseModel):
    csv_content: str = Field(..., description="Raw CSV string content containing telemetry observations")
    filename: Optional[str] = Field("telemetry_upload.csv", description="Originating filename for audit logging")


class ObservationEvaluateRequestDTO(BaseModel):
    snapshot_id: str = Field(..., description="Target scenario snapshot ID to project hazard state into")
    study_area_id: Optional[str] = Field(None, description="Optional target study area ID (defaults to baseline study area)")
    allow_stale: bool = Field(False, description="Explicit override flag allowing a STALE observation to drive E1 for audit purposes")


class ObservationEvaluateResponseDTO(BaseModel):
    observation_id: str
    station_code: str
    observed_at: datetime
    value: float
    unit: str
    hazard_state_id: str
    red_zone_id: str
    severity: str
    expansion_factor: float
    spatial_disclaimer: str
    is_audit_replay: bool = Field(False, description="True if evaluation was performed in audit/replay mode on historical/stale telemetry")
    evaluation_mode: str = Field("OPERATIONAL", description="OPERATIONAL or HISTORICAL_AUDIT_REPLAY")
    audit_event_id: Optional[str] = None
    evidence_reference: str
