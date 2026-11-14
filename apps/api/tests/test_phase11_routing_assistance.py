from types import SimpleNamespace

from app.api.v1.routing import get_assistance_queue
from app.db.session import SessionLocal
from app.engines.e4_route_relocation.service import RouteAndRelocationEngineE4


def test_route_validity_window_requires_departure_and_arrival_to_fit():
    route = SimpleNamespace(is_viable=True, total_time_min=30.0, valid_from_min=10.0, valid_until_min=60.0)
    assert not RouteAndRelocationEngineE4.is_route_time_feasible(route, 0.0)
    assert RouteAndRelocationEngineE4.is_route_time_feasible(route, 10.0)
    assert not RouteAndRelocationEngineE4.is_route_time_feasible(route, 31.0)


def test_assistance_queue_is_explicit_and_non_dispatching():
    db = SessionLocal()
    try:
        response = get_assistance_queue("SNAP_BASE_001", db)
        data = response.data
        assert data["dispatch_capability"] == "NOT_IMPLEMENTED"
        assert data["field_confirmation_available"] is False
        assert isinstance(data["queue"], list)
    finally:
        db.close()
