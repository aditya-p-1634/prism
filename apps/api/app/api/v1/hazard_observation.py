"""
PRISM Phase A.7 — Hazard Observation & Real Telemetry API Router
================================================================
Endpoints:
- Stations:
  - POST /api/v1/hazard-stations: Register a new telemetry monitoring station.
  - GET  /api/v1/hazard-stations: List registered stations.
  - GET  /api/v1/hazard-stations/{station_id_or_code}: Retrieve station metadata.
  - GET  /api/v1/hazard-stations/{station_id_or_code}/current-state: Latest observation & freshness.
  - GET  /api/v1/hazard-stations/{station_id_or_code}/observations: Query station observation history.
- Observations:
  - POST /api/v1/hazard-observations: Ingest a single telemetry observation.
  - GET  /api/v1/hazard-observations: Query telemetry observations with filtering.
  - GET  /api/v1/hazard-observations/latest: Retrieve latest observation.
  - GET  /api/v1/hazard-observations/{observation_id}: Retrieve single observation by ID.
  - POST /api/v1/hazard-observations/{observation_id}/evaluate: Drive E1 using validated observation.
  - POST /api/v1/hazard-observations/import: Batch CSV ingestion with structured audit report.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import HazardStation, HazardObservation, User
from app.models.enums import RoleEnum, ObservationQualityEnum, FreshnessEnum
from app.api.deps import require_role
from app.schemas.envelope import ResponseEnvelope
from app.schemas.hazard_observation import (
    HazardStationCreateDTO,
    HazardStationResponseDTO,
    HazardObservationCreateDTO,
    HazardObservationResponseDTO,
    CurrentHazardStateResponseDTO,
    CsvIngestionReportDTO,
    CsvImportRequestDTO,
    ObservationEvaluateRequestDTO,
    ObservationEvaluateResponseDTO
)
from app.engines.e1_hazard.observation.station_registry import StationRegistry
from app.engines.e1_hazard.observation.ingestion import ObservationIngestionService
from app.engines.e1_hazard.observation.service import HazardObservationService, _obs_to_dto
from app.engines.e1_hazard.observation.validation import ObservationSafetyException

router = APIRouter(prefix="", tags=["Real-World Telemetry & Observations (E1 - A.7)"])


def _station_to_dto(s: HazardStation) -> HazardStationResponseDTO:
    return HazardStationResponseDTO(
        id=s.id,
        station_code=s.station_code,
        station_name=s.station_name,
        river=s.river,
        district=s.district,
        state=s.state,
        latitude=s.latitude,
        longitude=s.longitude,
        hazard_type=s.hazard_type.value if hasattr(s.hazard_type, "value") else str(s.hazard_type),
        unit=s.unit,
        source=s.source,
        source_dataset=s.source_dataset,
        is_active=s.is_active,
        warning_threshold_m=s.warning_threshold_m,
        danger_threshold_m=s.danger_threshold_m,
        metadata_json=s.metadata_json or {},
        created_at=s.created_at,
        updated_at=s.updated_at
    )


# -------------------------------------------------------------
# Hazard Stations Endpoints
# -------------------------------------------------------------

@router.post("/hazard-stations", response_model=ResponseEnvelope[HazardStationResponseDTO])
def register_hazard_station(
    payload: HazardStationCreateDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN])),
    db: Session = Depends(get_db)
):
    """Registers a new telemetry monitoring station in the station registry."""
    try:
        station = StationRegistry.register_station(payload, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ResponseEnvelope[HazardStationResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=_station_to_dto(station)
    )


@router.get("/hazard-stations", response_model=ResponseEnvelope[List[HazardStationResponseDTO]])
def list_hazard_stations(
    hazard_type: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """Lists registered telemetry stations with optional filtering."""
    # Ensure pilot station is seeded
    StationRegistry.ensure_pilot_station(db)
    stations = StationRegistry.list_stations(hazard_type=hazard_type, district=district, is_active=is_active, db=db)
    return ResponseEnvelope[List[HazardStationResponseDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=[_station_to_dto(s) for s in stations]
    )


@router.get("/hazard-stations/{station_id_or_code}", response_model=ResponseEnvelope[HazardStationResponseDTO])
def get_hazard_station(
    station_id_or_code: str,
    db: Session = Depends(get_db)
):
    """Retrieves metadata for a station by station_code or primary key ID."""
    StationRegistry.ensure_pilot_station(db)
    stn = StationRegistry.get_by_code(station_id_or_code, db) or StationRegistry.get_by_id(station_id_or_code, db)
    if not stn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STATION_NOT_FOUND: Telemetry station '{station_id_or_code}' not found in registry."
        )
    return ResponseEnvelope[HazardStationResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=_station_to_dto(stn)
    )


@router.get("/hazard-stations/{station_id_or_code}/current-state", response_model=ResponseEnvelope[CurrentHazardStateResponseDTO])
def get_station_current_state(
    station_id_or_code: str,
    db: Session = Depends(get_db)
):
    """
    Returns the latest valid observation, value, unit, quality status, and freshness
    for the specified telemetry station. Stale observations are explicitly marked.
    """
    StationRegistry.ensure_pilot_station(db)
    stn = StationRegistry.get_by_code(station_id_or_code, db) or StationRegistry.get_by_id(station_id_or_code, db)
    if not stn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STATION_NOT_FOUND: Telemetry station '{station_id_or_code}' not found in registry."
        )
    current_state = HazardObservationService.get_current_hazard_state(stn.station_code, db)
    return ResponseEnvelope[CurrentHazardStateResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=current_state
    )


@router.get("/hazard-stations/{station_id_or_code}/observations", response_model=ResponseEnvelope[List[HazardObservationResponseDTO]])
def list_station_observations(
    station_id_or_code: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Queries telemetry observation history for a specific station."""
    stn = StationRegistry.get_by_code(station_id_or_code, db) or StationRegistry.get_by_id(station_id_or_code, db)
    if not stn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STATION_NOT_FOUND: Station '{station_id_or_code}' not found."
        )
    records = db.query(HazardObservation).filter(
        HazardObservation.station_id == stn.id
    ).order_by(HazardObservation.observed_at.desc()).limit(limit).all()

    return ResponseEnvelope[List[HazardObservationResponseDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=[_obs_to_dto(r) for r in records]
    )


# -------------------------------------------------------------
# Hazard Observations Endpoints
# -------------------------------------------------------------

@router.post("/hazard-observations", response_model=ResponseEnvelope[HazardObservationResponseDTO])
def create_hazard_observation(
    payload: HazardObservationCreateDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    """
    Ingests and validates a single real-world telemetry observation.
    Differentiates physical observed_at from system ingested_at.
    """
    StationRegistry.ensure_pilot_station(db)
    obs = ObservationIngestionService.ingest_single(payload, db)
    return ResponseEnvelope[HazardObservationResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=_obs_to_dto(obs)
    )


@router.get("/hazard-observations", response_model=ResponseEnvelope[List[HazardObservationResponseDTO]])
def list_hazard_observations(
    station_code: Optional[str] = Query(None),
    quality_status: Optional[str] = Query(None),
    freshness: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Lists observations with optional quality, station, and freshness filters."""
    query = db.query(HazardObservation)
    if station_code:
        query = query.filter(HazardObservation.station_code == station_code.strip().upper())
    if quality_status:
        query = query.filter(HazardObservation.quality_status == quality_status)
    if freshness:
        query = query.filter(HazardObservation.freshness == freshness)

    records = query.order_by(HazardObservation.observed_at.desc()).limit(limit).all()
    return ResponseEnvelope[List[HazardObservationResponseDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=[_obs_to_dto(r) for r in records]
    )


@router.get("/hazard-observations/latest", response_model=ResponseEnvelope[HazardObservationResponseDTO])
def get_latest_hazard_observation(
    station_code: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Retrieves the most recent valid observation (optionally filtered by station)."""
    StationRegistry.ensure_pilot_station(db)
    query = db.query(HazardObservation).filter(
        HazardObservation.quality_status.in_([ObservationQualityEnum.VALID, ObservationQualityEnum.STALE])
    )
    if station_code:
        query = query.filter(HazardObservation.station_code == station_code.strip().upper())
    latest = query.order_by(HazardObservation.observed_at.desc()).first()

    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO_OBSERVATIONS_FOUND: No valid telemetry observations found."
        )
    return ResponseEnvelope[HazardObservationResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=_obs_to_dto(latest)
    )


@router.get("/hazard-observations/{observation_id}", response_model=ResponseEnvelope[HazardObservationResponseDTO])
def get_hazard_observation(
    observation_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves a single observation by primary key ID with full provenance."""
    obs = db.query(HazardObservation).filter(HazardObservation.id == observation_id).first()
    if not obs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OBSERVATION_NOT_FOUND: Hazard observation '{observation_id}' not found."
        )
    return ResponseEnvelope[HazardObservationResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=_obs_to_dto(obs)
    )


@router.post("/hazard-observations/{observation_id}/evaluate", response_model=ResponseEnvelope[ObservationEvaluateResponseDTO])
def evaluate_hazard_observation(
    observation_id: str,
    payload: ObservationEvaluateRequestDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    """
    Evaluates a validated real telemetry observation through E1 Hazard Engine.
    Emits an E6 AuditEvent establishing the full provenance chain.
    Strictly gates rejected or stale observations unless explicit allow_stale is granted.
    """
    try:
        result_dto = HazardObservationService.evaluate_from_observation(
            observation_id=observation_id,
            snapshot_id=payload.snapshot_id,
            study_area_id=payload.study_area_id,
            allow_stale=payload.allow_stale,
            db=db,
            user_id=current_user.id
        )
    except ObservationSafetyException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return ResponseEnvelope[ObservationEvaluateResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=payload.snapshot_id,
        data=result_dto
    )


@router.post("/hazard-observations/import", response_model=ResponseEnvelope[CsvIngestionReportDTO])
def import_hazard_observations_csv(
    payload: CsvImportRequestDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    """
    Ingests batch telemetry observations from CSV content with full schema, station,
    timestamp, unit, and duplicate validation. Returns an auditable ingestion report.
    """
    StationRegistry.ensure_pilot_station(db)
    report = ObservationIngestionService.ingest_csv(
        csv_content=payload.csv_content,
        filename=payload.filename or "upload.csv",
        db=db
    )
    return ResponseEnvelope[CsvIngestionReportDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id="NONE",
        data=report
    )
