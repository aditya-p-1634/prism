"""
PRISM Phase A.7 — Hazard Observation Operational Service & E1 Adapter
=====================================================================
Orchestrates:
1. Current Hazard State determination for telemetry stations.
2. Freshness evaluation (FRESH, AGING, STALE).
3. Safety boundary enforcement: Rejects invalid or stale observations from driving E1.
4. E1 Evaluation invocation with explicit prototype spatial transformation tags.
5. Full E6 audit event emission establishing complete observation-to-hazard traceability.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import shapely

from app.models.entities import (
    HazardStation,
    HazardObservation,
    HazardState,
    AuditEvent,
    User
)
from app.models.enums import (
    ObservationQualityEnum,
    FreshnessEnum,
    StateTypeEnum,
    RoleEnum
)
from app.schemas.hazard_observation import (
    CurrentHazardStateResponseDTO,
    HazardObservationResponseDTO,
    ObservationEvaluateResponseDTO
)
from app.engines.e1_hazard.observation.station_registry import StationRegistry
from app.engines.e1_hazard.observation.validation import ObservationValidator, ObservationSafetyException
from app.engines.e1_hazard.service import HazardEngineE1
from app.engines.e6_integration.service import IntegrationBackboneE6
from app.gis.spatial import to_shapely


def _obs_to_dto(obs: HazardObservation) -> HazardObservationResponseDTO:
    return HazardObservationResponseDTO(
        id=obs.id,
        station_id=obs.station_id,
        station_code=obs.station_code,
        station_name=obs.station_name,
        river=obs.river,
        district=obs.district,
        hazard_type=obs.hazard_type.value if hasattr(obs.hazard_type, "value") else str(obs.hazard_type),
        source=obs.source,
        source_dataset=obs.source_dataset,
        observed_at=obs.observed_at,
        ingested_at=obs.ingested_at,
        value=obs.value,
        unit=obs.unit,
        latitude=obs.latitude,
        longitude=obs.longitude,
        quality_status=obs.quality_status.value if hasattr(obs.quality_status, "value") else str(obs.quality_status),
        quality_flags=obs.quality_flags or [],
        freshness=obs.freshness.value if hasattr(obs.freshness, "value") else str(obs.freshness),
        raw_reference=obs.raw_reference or {},
        created_at=obs.created_at
    )


class HazardObservationService:
    """Service coordinator for real-world hazard telemetry and observation-driven E1 evaluation."""

    @classmethod
    def get_current_hazard_state(
        cls,
        station_code: str,
        db: Session,
        reference_time: Optional[datetime] = None
    ) -> CurrentHazardStateResponseDTO:
        """
        Determines the current hazard state for a telemetry monitoring station.
        Exposes value, unit, quality status, freshness, and explicit staleness indicators.
        """
        station = StationRegistry.get_by_code(station_code, db)
        if not station:
            raise ValueError(f"Station with code '{station_code}' not found in registry.")

        # Find latest valid observation
        latest_obs = db.query(HazardObservation).filter(
            HazardObservation.station_id == station.id,
            HazardObservation.quality_status.in_([ObservationQualityEnum.VALID, ObservationQualityEnum.STALE])
        ).order_by(HazardObservation.observed_at.desc()).first()

        if not latest_obs:
            return CurrentHazardStateResponseDTO(
                station_code=station.station_code,
                station_name=station.station_name,
                river=station.river,
                district=station.district,
                observed_at=None,
                value=None,
                unit=station.unit,
                quality_status=None,
                freshness=FreshnessEnum.EXPIRED.value,
                is_stale=True,
                source=station.source,
                source_dataset=station.source_dataset,
                severity_classification="SEVERITY_UNCLASSIFIED",
                warning_threshold_m=station.warning_threshold_m,
                danger_threshold_m=station.danger_threshold_m,
                disclaimer="No valid telemetry observations recorded for this station."
            )

        # Re-evaluate freshness against current reference time
        current_freshness, elapsed_hours = ObservationValidator.compute_freshness(
            latest_obs.observed_at, reference_time=reference_time
        )
        is_stale = (current_freshness == FreshnessEnum.STALE)

        # Classification without inventing arbitrary safety thresholds (Section 8)
        if station.danger_threshold_m is not None and latest_obs.value >= station.danger_threshold_m:
            severity = "CRITICAL_DANGER"
        elif station.warning_threshold_m is not None and latest_obs.value >= station.warning_threshold_m:
            severity = "WARNING"
        elif station.warning_threshold_m is not None:
            severity = "NORMAL"
        else:
            severity = "SEVERITY_UNCLASSIFIED"

        disclaimer = (
            "STALE TELEMETRY: Last known value retained for audit; prohibited from driving real-time E1 without explicit override."
            if is_stale else
            "FRESH TELEMETRY: Validated real-world observation."
        )

        return CurrentHazardStateResponseDTO(
            station_code=station.station_code,
            station_name=station.station_name,
            river=station.river,
            district=station.district,
            latest_observation=_obs_to_dto(latest_obs),
            observed_at=latest_obs.observed_at,
            value=latest_obs.value,
            unit=latest_obs.unit,
            quality_status=latest_obs.quality_status.value if hasattr(latest_obs.quality_status, "value") else str(latest_obs.quality_status),
            freshness=current_freshness.value,
            is_stale=is_stale,
            source=latest_obs.source,
            source_dataset=latest_obs.source_dataset,
            severity_classification=severity,
            warning_threshold_m=station.warning_threshold_m,
            danger_threshold_m=station.danger_threshold_m,
            disclaimer=disclaimer
        )

    @classmethod
    def evaluate_from_observation(
        cls,
        observation_id: str,
        snapshot_id: str,
        study_area_id: Optional[str] = None,
        allow_stale: bool = False,
        db: Optional[Session] = None,
        user_id: Optional[str] = None
    ) -> ObservationEvaluateResponseDTO:
        """
        Drives E1 Hazard Engine using a validated real-world telemetry observation.

        Strict Safety Boundaries:
        1. REJECTED or SUSPECT observations are strictly prohibited from driving E1.
        2. STALE observations cannot silently masquerade as current telemetry unless
           allow_stale=True is explicitly supplied for historical audit simulations.
        3. Emits a full E6 AuditEvent preserving the provenance chain:
           E1 hazard state -> Observation ID -> Station ID -> Source -> Observed Time.
        """
        if db is None:
            raise ValueError("Database session is required.")

        obs = db.query(HazardObservation).filter(HazardObservation.id == observation_id).first()
        if not obs:
            raise ValueError(f"Hazard observation '{observation_id}' not found.")

        # Hard Safety Gate 1: Quality Check
        if obs.quality_status not in [ObservationQualityEnum.VALID, ObservationQualityEnum.STALE]:
            raise ObservationSafetyException(
                f"OBSERVATION_SAFETY_GATE_REJECTED: Observation '{obs.id}' has status '{obs.quality_status}'. "
                f"Rejected observations (Flags: {obs.quality_flags}) are strictly prohibited from driving E1 hazard evaluations."
            )

        # Hard Safety Gate 2: Freshness Check
        current_freshness, elapsed_h = ObservationValidator.compute_freshness(obs.observed_at)
        if current_freshness == FreshnessEnum.STALE and not allow_stale:
            raise ObservationSafetyException(
                f"OBSERVATION_SAFETY_GATE_REJECTED: Observation '{obs.id}' is STALE ({elapsed_h:.1f} hours old). "
                "Stale telemetry cannot silently masquerade as current hazard state without explicit allow_stale=True."
            )

        # Baseline Study Area Geometry Resolution
        baseline_hazard = db.query(HazardState).filter(HazardState.snapshot_id == "SNAP_BASE_001").first()
        if not baseline_hazard:
            raise RuntimeError("Baseline hazard state not found in database.")

        sa_id = study_area_id or baseline_hazard.study_area_id
        base_flood_geom = to_shapely(baseline_hazard.geom)

        e1 = HazardEngineE1()
        e1_result = e1.evaluate_from_observation(
            observation=obs,
            study_area_id=sa_id,
            snapshot_id=snapshot_id,
            base_flood_geom=base_flood_geom
        )

        # Determine evaluation mode and whether this is historical audit/replay
        is_stale_data = (current_freshness == FreshnessEnum.STALE)
        is_audit_replay = is_stale_data and allow_stale
        evaluation_mode = "HISTORICAL_AUDIT_REPLAY" if is_audit_replay else "OPERATIONAL"

        # Record E6 Audit Event for full forensic provenance
        e6 = IntegrationBackboneE6(db)
        audit_event = e6.record_audit_event(
            action_type="E1_EVALUATE_FROM_OBSERVATION",
            entity_type="HazardObservation",
            entity_id=obs.id,
            user_id=user_id,
            before_state={
                "station_code": obs.station_code,
                "source": obs.source,
                "source_dataset": obs.source_dataset,
                "observed_at": obs.observed_at.isoformat(),
                "ingested_at": obs.ingested_at.isoformat(),
                "water_level_m": obs.value,
                "is_stale": is_stale_data,
                "allow_stale": allow_stale
            },
            after_state={
                "snapshot_id": snapshot_id,
                "hazard_state_id": e1_result["hazard_state"].id,
                "red_zone_id": e1_result["red_zone"].id,
                "expansion_factor": e1_result["hazard_prediction"].expansion_factor,
                "severity": e1_result["hazard_state"].severity,
                "evidence_source": e1_result["evidence"].source_reference,
                "evaluation_mode": evaluation_mode,
                "is_audit_replay": is_audit_replay
            },
            justification=(
                f"[{evaluation_mode}] Evaluated real telemetry water level {obs.value:.2f}m from station {obs.station_code} "
                f"into E1 hazard state for snapshot {snapshot_id}."
            )
        )

        return ObservationEvaluateResponseDTO(
            observation_id=obs.id,
            station_code=obs.station_code,
            observed_at=obs.observed_at,
            value=obs.value,
            unit=obs.unit,
            hazard_state_id=e1_result["hazard_state"].id,
            red_zone_id=e1_result["red_zone"].id,
            severity=e1_result["hazard_state"].severity,
            expansion_factor=e1_result["hazard_prediction"].expansion_factor,
            spatial_disclaimer="Prototype spatial transformation — not a validated hydrodynamic inundation model.",
            is_audit_replay=is_audit_replay,
            evaluation_mode=evaluation_mode,
            audit_event_id=audit_event.id if audit_event else None,
            evidence_reference=e1_result["evidence"].source_reference
        )
