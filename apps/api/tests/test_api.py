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
    assert data["kpis"]["total_relocations_assigned"] == 28
    assert data["kpis"]["unmet_relocation_demand"] == 0
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

def test_households_and_priorities():
    hh_res = client.get("/api/v1/people/households")
    assert hh_res.status_code == 200
    hhs = hh_res.json()["data"]
    assert len(hhs) == 28
    assert any(h["has_partial_data"] for h in hhs)

    prio_res = client.get("/api/v1/people/priorities?snapshot_id=SNAP_BASE_001")
    assert prio_res.status_code == 200
    prios = prio_res.json()["data"]
    assert len(prios) == 28
    assert prios[0]["member_count"] >= 1

def test_road_segments():
    res = client.get("/api/v1/road-segments")
    assert res.status_code == 200
    segs = res.json()["data"]
    assert len(segs) >= 15
    assert any(s["is_bridge"] for s in segs)

def test_reports_and_csv_export():
    rep_res = client.get("/api/v1/reports/summary?snapshot_id=SNAP_BASE_001")
    assert rep_res.status_code == 200
    rep = rep_res.json()
    assert rep["summary"]["total_groups"] == 28
    assert rep["summary"]["allocated_groups"] == 28
    assert rep["summary"]["unmet_groups"] == 0

    csv_res = client.get("/api/v1/reports/export?report_type=manifest&snapshot_id=SNAP_BASE_001")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "household_code" in csv_res.text

