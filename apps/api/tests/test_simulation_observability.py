"""PRISM V2 — Phase A.5: Simulation Observability & Operational Control Test Suite
================================================================================
Test suite validating:
1. Current-state endpoint (GET /api/v1/simulation-runs/{run_id}/state)
2. Metrics endpoint (GET /api/v1/simulation-runs/{run_id}/metrics)
3. Timeline endpoint (GET /api/v1/simulation-runs/{run_id}/timeline)
4. Missing run returns 404
5. Deterministic state response
6. Deterministic metrics
7. Chronological event ordering
8. Event summary generation
9. RUNNING -> PAUSED lifecycle transition
10. PAUSED -> RUNNING lifecycle transition
11. PAUSED -> single STEP
12. STEP advances exactly one tick
13. Completed simulation cannot step (no mutation)
14. Cancelled simulation cannot step (no mutation)
15. Read-only APIs do not mutate state
16. Baseline remains unchanged (SNAP_BASE_001 immutability)
17. Evacuation-state metrics match actual state
18. Resource metrics match A.4 state
19. Route/infrastructure metrics match existing simulation state
20. No duplicate simulation loop
21. Zero-duration simulation observability
22. Completed simulation observability
23. Event counts are deterministic
24. Status guardrails and invalid control transitions
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.entities import (
    StateSnapshot, RelocationAllocation, RelocationGroup, Destination,
    RoadSegment, SimulationRun, SimulationEvent, SimulationAllocationProgress,
    SimulationResourceState, CapacityState
)
from app.models.enums import (
    AllocationStatusEnum, EvacuationStateEnum, SimulationStatusEnum,
    SimulationEventTypeEnum, ResourceCategoryEnum, ResourceStatusEnum
)
from app.engines.e5_simulation.observability_service import SimulationObservabilityService

client = TestClient(app)


@pytest.fixture(scope="module")
def base_scenario():
    """Initializes a scenario snapshot for simulation testing."""
    res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    assert res.status_code == 200
    scen_data = res.json()["data"]
    return {
        "baseline_snapshot_id": "SNAP_BASE_001",
        "scenario_snapshot_id": scen_data["scenario_snapshot_id"],
        "scenario_code": "MONSOON_SURGE_01"
    }


def test_1_current_state_endpoint(base_scenario):
    """TEST 1: Current-state endpoint returns consolidated state DTO."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    assert res.status_code == 200
    run_id = res.json()["data"]["id"]

    # Step once
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    # Fetch consolidated state
    state_res = client.get(f"/api/v1/simulation-runs/{run_id}/state")
    assert state_res.status_code == 200
    payload = state_res.json()["data"]

    assert payload["run_id"] == run_id
    assert payload["snapshot_id"] == base_scenario["scenario_snapshot_id"]
    assert payload["status"] in [SimulationStatusEnum.RUNNING.value, SimulationStatusEnum.CREATED.value]
    assert payload["current_tick"] == 1
    assert payload["current_simulation_time"] == 10.0
    assert payload["total_ticks"] == 3
    assert payload["progress_percentage"] > 0.0

    # Subsections exist
    assert "population" in payload
    assert "infrastructure" in payload
    assert "resources" in payload
    assert "planning" in payload
    assert "recent_events" in payload
    assert "event_counts_by_type" in payload


def test_2_metrics_endpoint(base_scenario):
    """TEST 2: Metrics endpoint returns derived numerical operational metrics."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    metrics_res = client.get(f"/api/v1/simulation-runs/{run_id}/metrics")
    assert metrics_res.status_code == 200
    m = metrics_res.json()["data"]

    assert m["run_id"] == run_id
    assert m["ticks_completed"] == 1
    assert m["total_population"] > 0
    assert isinstance(m["population_by_state"], dict)
    assert isinstance(m["blocked_roads_count"], int)
    assert m["total_physical_capacity"] > 0
    assert m["total_effective_capacity"] > 0
    assert m["total_events_recorded"] > 0
    assert isinstance(m["counts_by_event_type"], dict)


def test_3_timeline_endpoint(base_scenario):
    """TEST 3: Timeline endpoint returns paginated chronological events with summaries."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    tl_res = client.get(f"/api/v1/simulation-runs/{run_id}/timeline?limit=10&offset=0")
    assert tl_res.status_code == 200
    tl = tl_res.json()["data"]

    assert tl["run_id"] == run_id
    assert tl["total_events"] >= 2
    assert tl["limit"] == 10
    assert tl["offset"] == 0
    assert len(tl["events"]) <= 10

    for ev in tl["events"]:
        assert "summary" in ev
        assert len(ev["summary"]) > 0
        assert "tick_index" in ev
        assert "simulation_time_min" in ev


def test_4_missing_run_returns_404():
    """TEST 4: Non-existent simulation run ID returns 404 for all endpoints."""
    fake_id = "NON_EXISTENT_RUN_99999"

    assert client.get(f"/api/v1/simulation-runs/{fake_id}/state").status_code == 404
    assert client.get(f"/api/v1/simulation-runs/{fake_id}/metrics").status_code == 404
    assert client.get(f"/api/v1/simulation-runs/{fake_id}/timeline").status_code == 404
    assert client.post(f"/api/v1/simulation-runs/{fake_id}/pause").status_code == 404
    assert client.post(f"/api/v1/simulation-runs/{fake_id}/resume").status_code == 404
    assert client.post(f"/api/v1/simulation-runs/{fake_id}/cancel").status_code == 404


def test_5_deterministic_state_response(base_scenario):
    """TEST 5: Calling state endpoint multiple times yields strictly identical response."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 20
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    state_1 = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
    state_2 = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
    state_3 = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]

    assert state_1 == state_2 == state_3


def test_6_deterministic_metrics(base_scenario):
    """TEST 6: Calling metrics endpoint multiple times yields strictly identical response."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 20
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    m1 = client.get(f"/api/v1/simulation-runs/{run_id}/metrics").json()["data"]
    m2 = client.get(f"/api/v1/simulation-runs/{run_id}/metrics").json()["data"]
    m3 = client.get(f"/api/v1/simulation-runs/{run_id}/metrics").json()["data"]

    assert m1 == m2 == m3


def test_7_chronological_event_ordering(base_scenario):
    """TEST 7: Timeline events are strictly ordered chronologically by simulation time and tick."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 5,
        "duration_minutes": 20
    })
    run_id = res.json()["data"]["id"]
    for _ in range(4):
        client.post(f"/api/v1/simulation-runs/{run_id}/step")

    tl_res = client.get(f"/api/v1/simulation-runs/{run_id}/timeline?limit=100")
    events = tl_res.json()["data"]["events"]
    assert len(events) > 0

    for i in range(len(events) - 1):
        e_curr = events[i]
        e_next = events[i + 1]
        assert e_curr["simulation_time_min"] <= e_next["simulation_time_min"]
        if e_curr["simulation_time_min"] == e_next["simulation_time_min"]:
            assert e_curr["tick_index"] <= e_next["tick_index"]


def test_8_event_summary_generation():
    """TEST 8: Factual human-readable summaries generated deterministically from event payload."""
    # Test Road Blocked
    ev1 = SimulationEvent(
        simulation_run_id="run-1",
        simulation_time_min=10.0,
        tick_index=1,
        event_type=SimulationEventTypeEnum.ROAD_BLOCKED,
        entity_type="RoadSegment",
        entity_id="seg-123",
        details={"segment_code": "BRIDGE_01"}
    )
    assert SimulationObservabilityService.generate_event_summary(ev1) == "Road BRIDGE_01 became blocked."

    # Test Route Invalidated
    ev2 = SimulationEvent(
        simulation_run_id="run-1",
        simulation_time_min=10.0,
        tick_index=1,
        event_type=SimulationEventTypeEnum.ROUTE_INVALIDATED,
        entity_type="RelocationAllocation",
        entity_id="alloc-99",
        details={}
    )
    assert SimulationObservabilityService.generate_event_summary(ev2) == "Route for allocation alloc-99 became invalid."

    # Test Route Replanned
    ev3 = SimulationEvent(
        simulation_run_id="run-1",
        simulation_time_min=10.0,
        tick_index=1,
        event_type=SimulationEventTypeEnum.ROUTE_REPLANNED,
        entity_type="RelocationAllocation",
        entity_id="alloc-99",
        details={"new_travel_time_min": 14.5}
    )
    assert SimulationObservabilityService.generate_event_summary(ev3) == "Allocation alloc-99 was assigned a new feasible route (travel time 14.5min)."

    # Test Resource Warning
    ev4 = SimulationEvent(
        simulation_run_id="run-1",
        simulation_time_min=20.0,
        tick_index=2,
        event_type=SimulationEventTypeEnum.RESOURCE_WARNING,
        entity_type="SimulationResourceState",
        entity_id="DEST_02",
        details={"destination_code": "DEST_02", "resource_type": "WATER"}
    )
    assert SimulationObservabilityService.generate_event_summary(ev4) == "Destination DEST_02 became resource-constrained (WATER)."

    # Test Destination Infeasible
    ev5 = SimulationEvent(
        simulation_run_id="run-1",
        simulation_time_min=20.0,
        tick_index=2,
        event_type=SimulationEventTypeEnum.DESTINATION_INFEASIBLE,
        entity_type="Destination",
        entity_id="DEST_02",
        details={"destination_code": "DEST_02"}
    )
    assert SimulationObservabilityService.generate_event_summary(ev5) == "Destination DEST_02 can no longer accommodate the affected uncommitted demand."

    # Test Arrival
    ev6 = SimulationEvent(
        simulation_run_id="run-1",
        simulation_time_min=30.0,
        tick_index=3,
        event_type=SimulationEventTypeEnum.ARRIVAL,
        entity_type="RelocationAllocation",
        entity_id="alloc-12",
        details={}
    )
    assert SimulationObservabilityService.generate_event_summary(ev6) == "Allocation alloc-12 reached its destination."

    # Test Evacuation State Changed
    ev7 = SimulationEvent(
        simulation_run_id="run-1",
        simulation_time_min=10.0,
        tick_index=1,
        event_type=SimulationEventTypeEnum.EVACUATION_STATE_CHANGED,
        entity_type="RelocationAllocation",
        entity_id="alloc-12",
        details={"from_state": "MOVING", "to_state": "IN_TRANSIT"}
    )
    assert SimulationObservabilityService.generate_event_summary(ev7) == "Allocation alloc-12 changed evacuation state from MOVING to IN_TRANSIT."


def test_9_running_to_paused(base_scenario):
    """TEST 9: Running simulation transitions to PAUSED on pause control."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    # Pause simulation
    pause_res = client.post(f"/api/v1/simulation-runs/{run_id}/pause")
    assert pause_res.status_code == 200
    assert pause_res.json()["data"]["status"] == SimulationStatusEnum.PAUSED.value

    # Verify PAUSED event was logged
    events_res = client.get(f"/api/v1/simulation-runs/{run_id}/timeline?event_type={SimulationEventTypeEnum.SIMULATION_PAUSED.value}")
    assert events_res.status_code == 200
    assert events_res.json()["data"]["total_events"] >= 1


def test_10_paused_to_running(base_scenario):
    """TEST 10: Paused simulation resumes back to RUNNING on resume control."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")
    client.post(f"/api/v1/simulation-runs/{run_id}/pause")

    # Resume
    resume_res = client.post(f"/api/v1/simulation-runs/{run_id}/resume")
    assert resume_res.status_code == 200
    assert resume_res.json()["data"]["status"] == SimulationStatusEnum.RUNNING.value

    # Verify RESUMED event
    events_res = client.get(f"/api/v1/simulation-runs/{run_id}/timeline?event_type={SimulationEventTypeEnum.SIMULATION_RESUMED.value}")
    assert events_res.status_code == 200
    assert events_res.json()["data"]["total_events"] >= 1


def test_11_paused_to_single_step(base_scenario):
    """TEST 11: Single STEP executes while in PAUSED state."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 40
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")
    client.post(f"/api/v1/simulation-runs/{run_id}/pause")

    step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
    assert step_res.status_code == 200
    assert step_res.json()["data"]["tick_index"] == 2
    assert step_res.json()["data"]["simulation_time_min"] == 20.0


def test_12_step_advances_exactly_one_tick(base_scenario):
    """TEST 12: STEP advances clock by exactly one timestep and increments completed ticks by 1."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 12.5,
        "duration_minutes": 50
    })
    run_id = res.json()["data"]["id"]

    for i in range(1, 4):
        s = client.post(f"/api/v1/simulation-runs/{run_id}/step")
        assert s.status_code == 200
        data = s.json()["data"]
        assert data["tick_index"] == i
        assert data["simulation_time_min"] == i * 12.5
        assert data["run"]["ticks_completed"] == i


def test_13_completed_simulation_cannot_step(base_scenario):
    """TEST 13: Completed simulation cannot step further (no mutation, clock and ticks do not advance)."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 20
    })
    run_id = res.json()["data"]["id"]

    # Step to completion (2 ticks)
    client.post(f"/api/v1/simulation-runs/{run_id}/step")
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    state_before = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
    assert state_before["status"] == SimulationStatusEnum.COMPLETED.value
    ticks_before = state_before["current_tick"]
    time_before = state_before["current_simulation_time"]

    # Attempt to step past completion
    step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
    assert step_res.status_code == 200
    # No events generated, no advance in ticks or time
    assert len(step_res.json()["data"]["events_generated"]) == 0

    state_after = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
    assert state_after["current_tick"] == ticks_before
    assert state_after["current_simulation_time"] == time_before
    assert state_after["status"] == SimulationStatusEnum.COMPLETED.value


def test_14_cancelled_simulation_cannot_step(base_scenario):
    """TEST 14: Cancelled simulation cannot step and rejects invalid state mutations."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/step")

    # Cancel simulation
    cancel_res = client.post(f"/api/v1/simulation-runs/{run_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["data"]["status"] == SimulationStatusEnum.CANCELLED.value

    # Attempt to step
    step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
    assert step_res.status_code == 200
    assert len(step_res.json()["data"]["events_generated"]) == 0
    assert step_res.json()["data"]["run"]["status"] == SimulationStatusEnum.CANCELLED.value

    # Cannot pause or resume a cancelled simulation
    assert client.post(f"/api/v1/simulation-runs/{run_id}/pause").status_code == 400
    assert client.post(f"/api/v1/simulation-runs/{run_id}/resume").status_code == 400
    assert client.post(f"/api/v1/simulation-runs/{run_id}/cancel").status_code == 400


def test_15_read_only_apis_do_not_mutate_state(base_scenario):
    """TEST 15: Observability endpoints (state, metrics, timeline) are strictly read-only."""
    db = SessionLocal()
    try:
        res = client.post("/api/v1/simulation-runs", json={
            "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
            "timestep_minutes": 10,
            "duration_minutes": 30
        })
        run_id = res.json()["data"]["id"]
        client.post(f"/api/v1/simulation-runs/{run_id}/step")

        # Snapshot DB counts before calling read-only APIs
        run_before = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        ticks_before = run_before.ticks_completed
        time_before = run_before.current_simulation_time
        events_before = db.query(SimulationEvent).filter(SimulationEvent.simulation_run_id == run_id).count()
        allocs_before = [(a.id, a.evacuation_state, a.destination_id) for a in db.query(RelocationAllocation).filter(RelocationAllocation.snapshot_id == base_scenario["scenario_snapshot_id"]).all()]

        # Call read-only endpoints 10 times
        for _ in range(10):
            client.get(f"/api/v1/simulation-runs/{run_id}/state")
            client.get(f"/api/v1/simulation-runs/{run_id}/metrics")
            client.get(f"/api/v1/simulation-runs/{run_id}/timeline")

        # Verify DB counts after
        db.expire_all()
        run_after = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        assert run_after.ticks_completed == ticks_before
        assert run_after.current_simulation_time == time_before
        events_after = db.query(SimulationEvent).filter(SimulationEvent.simulation_run_id == run_id).count()
        assert events_after == events_before
        allocs_after = [(a.id, a.evacuation_state, a.destination_id) for a in db.query(RelocationAllocation).filter(RelocationAllocation.snapshot_id == base_scenario["scenario_snapshot_id"]).all()]
        assert allocs_after == allocs_before
    finally:
        db.close()


def test_16_baseline_remains_unchanged(base_scenario):
    """TEST 16: Canonical baseline SNAP_BASE_001 is untouched by observability & control APIs."""
    db = SessionLocal()
    try:
        base_allocs_before = [
            (a.id, a.assigned_capacity_count, a.destination_id, a.evacuation_state)
            for a in db.query(RelocationAllocation).filter(RelocationAllocation.snapshot_id == "SNAP_BASE_001").order_by(RelocationAllocation.id.asc()).all()
        ]
        assert len(base_allocs_before) == 28

        # Create, step, pause, resume, step, cancel a simulation run
        res = client.post("/api/v1/simulation-runs", json={
            "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
            "timestep_minutes": 10,
            "duration_minutes": 30
        })
        run_id = res.json()["data"]["id"]
        client.post(f"/api/v1/simulation-runs/{run_id}/step")
        client.get(f"/api/v1/simulation-runs/{run_id}/state")
        client.get(f"/api/v1/simulation-runs/{run_id}/metrics")
        client.post(f"/api/v1/simulation-runs/{run_id}/pause")
        client.post(f"/api/v1/simulation-runs/{run_id}/resume")
        client.get(f"/api/v1/simulation-runs/{run_id}/timeline")
        client.post(f"/api/v1/simulation-runs/{run_id}/cancel")

        db.expire_all()
        base_allocs_after = [
            (a.id, a.assigned_capacity_count, a.destination_id, a.evacuation_state)
            for a in db.query(RelocationAllocation).filter(RelocationAllocation.snapshot_id == "SNAP_BASE_001").order_by(RelocationAllocation.id.asc()).all()
        ]
        assert base_allocs_after == base_allocs_before
    finally:
        db.close()


def test_17_evacuation_state_metrics_match_actual_state(base_scenario):
    """TEST 17: Evacuation-state counts in state/metrics match actual RelocationAllocation records."""
    db = SessionLocal()
    try:
        res = client.post("/api/v1/simulation-runs", json={
            "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
            "timestep_minutes": 10,
            "duration_minutes": 30
        })
        run_id = res.json()["data"]["id"]
        client.post(f"/api/v1/simulation-runs/{run_id}/step")

        state_data = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
        reported_pop = state_data["population"]["counts_by_state"]

        # Directly query DB
        allocs = db.query(RelocationAllocation).filter(RelocationAllocation.snapshot_id == base_scenario["scenario_snapshot_id"]).all()
        actual_pop = {s.value: 0 for s in EvacuationStateEnum}
        for a in allocs:
            st = a.evacuation_state.value if a.evacuation_state else "PLANNED"
            actual_pop[st] += a.assigned_capacity_count

        assert reported_pop == actual_pop
    finally:
        db.close()


def test_18_resource_metrics_match_a4_state(base_scenario):
    """TEST 18: Resource metrics match SimulationResourceState and CapacityState from A.4."""
    db = SessionLocal()
    try:
        res = client.post("/api/v1/simulation-runs", json={
            "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
            "timestep_minutes": 10,
            "duration_minutes": 30
        })
        run_id = res.json()["data"]["id"]
        client.post(f"/api/v1/simulation-runs/{run_id}/step")

        state_data = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
        metrics_data = client.get(f"/api/v1/simulation-runs/{run_id}/metrics").json()["data"]

        # Validate total effective capacity matches CapacityState sum
        cap_states = db.query(CapacityState).filter(CapacityState.snapshot_id == base_scenario["scenario_snapshot_id"]).all()
        expected_eff_cap = sum(cs.effective_capacity for cs in cap_states)
        expected_rem_cap = sum(cs.remaining_capacity for cs in cap_states)

        assert metrics_data["total_effective_capacity"] == expected_eff_cap
        assert metrics_data["total_remaining_capacity"] == expected_rem_cap

        # Validate water consumed matches SimulationResourceState
        res_states = db.query(SimulationResourceState).filter(SimulationResourceState.simulation_run_id == run_id).all()
        expected_water = sum(s.consumed_quantity for s in res_states if s.resource_type == ResourceCategoryEnum.WATER)
        assert abs(metrics_data["total_water_consumed_liters"] - expected_water) < 1e-2
    finally:
        db.close()


def test_19_route_infrastructure_metrics_match_existing_simulation_state(base_scenario):
    """TEST 19: Route and infrastructure metrics match active roads and progress records."""
    db = SessionLocal()
    try:
        res = client.post("/api/v1/simulation-runs", json={
            "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
            "timestep_minutes": 10,
            "duration_minutes": 30
        })
        run_id = res.json()["data"]["id"]
        client.post(f"/api/v1/simulation-runs/{run_id}/step")

        state_data = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
        infra = state_data["infrastructure"]

        # Closed roads in parameters
        run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        closed_codes = sorted(list(set(run.parameters.get("closed_road_segments", []))))
        assert infra["blocked_roads_count"] == len(closed_codes)
        assert infra["blocked_road_codes"] == closed_codes

        # Reroutes match progress sum
        progs = db.query(SimulationAllocationProgress).filter(SimulationAllocationProgress.simulation_run_id == run_id).all()
        expected_reroutes = sum(p.reroute_count for p in progs)
        assert infra["reroute_counts"] == expected_reroutes
    finally:
        db.close()


def test_20_no_duplicate_simulation_loop(base_scenario):
    """TEST 20: Observability does not execute an independent simulation loop or advance ticks."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    run_id = res.json()["data"]["id"]

    # Initial state
    s0 = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
    assert s0["current_tick"] == 0
    assert s0["current_simulation_time"] == 0.0

    # Repeated calls to state, metrics, timeline
    for _ in range(5):
        client.get(f"/api/v1/simulation-runs/{run_id}/state")
        client.get(f"/api/v1/simulation-runs/{run_id}/metrics")
        client.get(f"/api/v1/simulation-runs/{run_id}/timeline")

    s1 = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
    assert s1["current_tick"] == 0
    assert s1["current_simulation_time"] == 0.0


def test_21_zero_duration_simulation_observability(base_scenario):
    """TEST 21: Zero-duration simulation is observable and correctly reports 100% progress."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 0
    })
    assert res.status_code == 200
    run_id = res.json()["data"]["id"]

    state_res = client.get(f"/api/v1/simulation-runs/{run_id}/state")
    assert state_res.status_code == 200
    st = state_res.json()["data"]
    assert st["duration_minutes"] == 0.0
    assert st["progress_percentage"] == 100.0

    metrics_res = client.get(f"/api/v1/simulation-runs/{run_id}/metrics")
    assert metrics_res.status_code == 200
    assert metrics_res.json()["data"]["progress_pct"] == 100.0


def test_22_completed_simulation_observability(base_scenario):
    """TEST 22: Completed simulation is observable with final metrics and completed events."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 20
    })
    run_id = res.json()["data"]["id"]

    exec_res = client.post(f"/api/v1/simulation-runs/{run_id}/run")
    assert exec_res.status_code == 200
    assert exec_res.json()["data"]["final_status"] == SimulationStatusEnum.COMPLETED.value

    # Observability
    st = client.get(f"/api/v1/simulation-runs/{run_id}/state").json()["data"]
    assert st["status"] == SimulationStatusEnum.COMPLETED.value
    assert st["progress_percentage"] == 100.0
    assert st["current_tick"] == 2

    tl = client.get(f"/api/v1/simulation-runs/{run_id}/timeline").json()["data"]
    assert any(e["event_type"] == SimulationEventTypeEnum.SIMULATION_COMPLETED.value for e in tl["events"])


def test_23_event_counts_are_deterministic():
    """TEST 23: Identical simulation runs produce deterministic event counts by type."""
    def run_simulation():
        r = client.post("/api/v1/simulation-runs", json={
            "scenario_code": "MONSOON_SURGE_01",
            "timestep_minutes": 10,
            "duration_minutes": 20
        })
        run_id = r.json()["data"]["id"]
        client.post(f"/api/v1/simulation-runs/{run_id}/run")
        m = client.get(f"/api/v1/simulation-runs/{run_id}/metrics").json()["data"]
        return m["counts_by_event_type"]

    counts_1 = run_simulation()
    counts_2 = run_simulation()
    assert counts_1 == counts_2


def test_24_invalid_lifecycle_operations_rejected(base_scenario):
    """TEST 24: Status transition guardrails reject invalid lifecycle operations with 400."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 20
    })
    run_id = res.json()["data"]["id"]

    # In CREATED or RUNNING state, calling resume fails (can only resume from PAUSED)
    resume_err = client.post(f"/api/v1/simulation-runs/{run_id}/resume")
    assert resume_err.status_code == 400
    assert "INVALID_SIMULATION_STATE" in resume_err.json()["detail"]

    # Step to completion
    client.post(f"/api/v1/simulation-runs/{run_id}/run")

    # In COMPLETED state, calling pause, resume, or cancel fails
    p_err = client.post(f"/api/v1/simulation-runs/{run_id}/pause")
    assert p_err.status_code == 400
    assert "INVALID_SIMULATION_STATE" in p_err.json()["detail"]

    r_err = client.post(f"/api/v1/simulation-runs/{run_id}/resume")
    assert r_err.status_code == 400
    assert "INVALID_SIMULATION_STATE" in r_err.json()["detail"]

    c_err = client.post(f"/api/v1/simulation-runs/{run_id}/cancel")
    assert c_err.status_code == 400
    assert "INVALID_SIMULATION_STATE" in c_err.json()["detail"]
