import pytest
from shapely.geometry import Point

from app.db.session import SessionLocal
from app.engines.e3_destination_capacity.service import DestinationCapacityEngineE3
from app.engines.e4_route_relocation.service import RouteAndRelocationEngineE4
from app.engines.e5_simulation.service import SimulationEngineE5
from app.engines.e6_integration.integrity import SnapshotIntegrityError
from app.models.entities import (
    CapacityState,
    Destination,
    DestinationResource,
    DestinationSnapshotState,
    RelocationGroup,
    RoutePlan,
    StateSnapshot,
)
from app.models.enums import OperationalStatusEnum, ResourceCategoryEnum
from app.gis.spatial import to_geojson_str


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
