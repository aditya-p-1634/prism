import pytest

from app.db.session import SessionLocal
from app.engines.e4_route_relocation.service import RouteAndRelocationEngineE4
from app.engines.e6_integration.integrity import SnapshotIntegrityError
from app.models.entities import CapacityState, Destination, RelocationGroup, RoutePlan


def test_optimizer_rejects_route_identity_mismatch():
    db = SessionLocal()
    try:
        group = db.query(RelocationGroup).filter_by(snapshot_id="SNAP_BASE_001").first()
        route = db.query(RoutePlan).filter_by(snapshot_id="SNAP_BASE_001").first()
        destination = db.query(Destination).filter_by(id=route.destination_id).one()
        capacity = db.query(CapacityState).filter_by(
            snapshot_id="SNAP_BASE_001", destination_id=destination.id
        ).one()

        with pytest.raises(SnapshotIntegrityError, match="ROUTE_KEY_MISMATCH"):
            RouteAndRelocationEngineE4().optimize_relocation(
                groups=[group],
                destinations=[destination],
                capacity_states={destination.id: capacity},
                candidate_routes={("wrong-habitation", destination.id): route},
                snapshot_id="SNAP_BASE_001",
            )
    finally:
        db.close()
