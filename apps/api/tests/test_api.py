from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["system"] == "PRISM"

def test_auth_login():
    response = client.post("/api/v1/auth/login", json={
        "email": "authority@prism.gov.in",
        "password": "authority123"
    })
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert payload["data"]["token_type"] == "bearer"
    assert payload["data"]["role"] == "AUTHORITY"

def test_dashboard_overview():
    response = client.get("/api/v1/dashboard/overview?snapshot_id=SNAP_BASE_001")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    data = payload["data"]
    assert "kpis" in data
    assert "layers" in data
    assert data["kpis"]["total_habitations"] == 4
    assert data["kpis"]["total_households"] == 28
    assert "flood_polygons" in data["layers"]
    assert "destinations" in data["layers"]

def test_destinations_api():
    response = client.get("/api/v1/destinations?snapshot_id=SNAP_BASE_001")
    assert response.status_code == 200
    payload = response.json()
    destinations = payload["data"]
    assert len(destinations) == 3
    d2 = next(d for d in destinations if d["code"] == "DEST_02")
    assert d2["capacity_state"]["bottleneck_resource"] == "WATER"

def test_relocation_allocations():
    response = client.get("/api/v1/relocation/allocations?snapshot_id=SNAP_BASE_001")
    assert response.status_code == 200
    payload = response.json()
    allocations = payload["data"]
    assert len(allocations) == 28
