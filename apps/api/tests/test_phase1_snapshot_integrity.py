import pytest
from shapely.geometry import Point

from app.db.session import SessionLocal
from app.engines.e3_destination_capacity.service import DestinationCapacityEngineE3
from app.engines.e4_route_relocation.service import RouteAndRelocationEngineE4
from app.engines.e5_simulation.service import SimulationEngineE5
from app.engines.e6_integration.integrity import SnapshotIntegrityError
from app.engines.e1_hazard.observation.service import HazardObservationService
from app.models.entities import (
    CapacityState,
    Destination,
    DestinationResource,
    DestinationSnapshotState,
    RelocationGroup,
    RoutePlan,
    StateSnapshot,
    HazardPredictionRecord,
)
from app.models.enums import OperationalStatusEnum, ResourceCategoryEnum
from app.gis.spatial import to_geojson_str
from app.engines.e1_hazard.prediction.pipeline import HazardPredictionPipeline


def test_e3_returns_detached_operational_view_without_mutating_canonical_destination():
    db = SessionLocal()
    try:
        destination = db.query(Destination).first()
        original_status = destination.operational_status
        original_score = destination.suitability_score
        resource = DestinationResource(
            destination_id=destination.id,
            snapshot_id="SNAP_BASE_001",
            resource_type=ResourceCategoryEnum.WATER,
            quantity=1,
            unit="L",
            supportable_population=100,
            is_critical=True,
        )

        view, capacity = DestinationCapacityEngineE3().evaluate_destination_safety_and_capacity(
            destination,
            [resource],
            Point(0, 0).buffer(100),
            Point(0, 0).buffer(100),
            "SCENARIO_TEST",
        )

        assert view is not destination
        assert view.operational_status == OperationalStatusEnum.CLOSED
        assert capacity.is_safe is False
        db.refresh(destination)
        assert destination.operational_status == original_status
        assert destination.suitability_score == original_score
    finally:
        db.close()


def test_scenario_outputs_are_branch_scoped_and_baseline_destination_is_unchanged():
    db = SessionLocal()
    try:
        destination = db.query(Destination).first()
        original = (destination.operational_status, destination.suitability_score)
        result = SimulationEngineE5(db).execute_scenario("MONSOON_SURGE_01", "SNAP_BASE_001")
        scenario_id = result["scenario_snapshot_id"]
        snapshot = db.query(StateSnapshot).filter_by(id=scenario_id).one()
        state = db.query(DestinationSnapshotState).filter_by(
            destination_id=destination.id, snapshot_id=scenario_id
        ).one()
        db.refresh(destination)
        assert snapshot.parent_snapshot_id == "SNAP_BASE_001"
        assert (destination.operational_status, destination.suitability_score) == original
        assert state.snapshot_id == scenario_id
    finally:
        db.close()


def test_optimizer_rejects_cross_snapshot_inputs():
    db = SessionLocal()
    try:
        group = db.query(RelocationGroup).first()
        capacity = db.query(CapacityState).first()
        route = db.query(RoutePlan).first()
        with pytest.raises(SnapshotIntegrityError, match="SNAPSHOT_MISMATCH"):
            RouteAndRelocationEngineE4().optimize_relocation(
                groups=[group],
                destinations=[db.query(Destination).first()],
                capacity_states={capacity.destination_id: capacity},
                candidate_routes={(group.habitation_id, route.destination_id): route},
                snapshot_id="SCENARIO_NOT_BASELINE",
            )
    finally:
        db.close()


def test_failed_scenario_rolls_back_partial_snapshot():
    db = SessionLocal()
    try:
        before = db.query(StateSnapshot).count()
        with pytest.raises(Exception):
            SimulationEngineE5(db).execute_scenario("MONSOON_SURGE_01", "MISSING_BASELINE")
        assert db.query(StateSnapshot).count() == before
    finally:
        db.close()


def test_observation_e1_cannot_write_to_immutable_baseline():
    db = SessionLocal()
    try:
        with pytest.raises(SnapshotIntegrityError, match="SNAPSHOT_IMMUTABLE"):
            HazardObservationService.evaluate_from_observation(
                observation_id="missing-observation",
                snapshot_id="SNAP_BASE_001",
                db=db,
            )
    finally:
        db.close()


def test_prediction_e1_cannot_write_to_immutable_baseline():
    db = SessionLocal()
    try:
        prediction = HazardPredictionRecord(
            id="prediction-integrity-test",
            snapshot_id="SCENARIO_A",
            predicted_value=10.0,
            raw_model_value=10.0,
            lower_bound=9.0,
            upper_bound=11.0,
            uncertainty_metric=0.1,
            source_time_min=0.0,
            target_time_min=10.0,
            horizon_minutes=10.0,
            model_name="TEST",
            validation_status="VALID",
            feature_provenance={},
            domain_alerts=[],
        )
        with pytest.raises(SnapshotIntegrityError, match="SNAPSHOT_IMMUTABLE"):
            HazardPredictionPipeline.feed_prediction_to_e1(prediction, db, "SNAP_BASE_001")
    finally:
        db.close()
