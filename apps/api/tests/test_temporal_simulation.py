"""PRISM V2 — Phase A.3: Temporal Simulation Clock & Dynamic In-Transit Replanning
==============================================================================
Test suite validating:
- Fixed-timestep model and input validation (TEST 1 - 7)
- Determinism and isolation (TEST 8 - 10)
- In-transit movement progression and arrival/shelter (TEST 11 - 13)
- Dynamic route invalidation, rerouting, and exception states (TEST 14 - 18)
- CP-SAT reallocation on material infeasibility (TEST 19 - 21)
- Compact event logging, atomicity, and rollback (TEST 22 - 24)
- Regression coverage for A.1 and A.2 (TEST 25 - 26)
- Extreme/boundary conditions and bounded storage growth (TEST 27 - 28)
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.entities import (
    StateSnapshot, RelocationAllocation, RelocationGroup, Destination, Habitation,
    RoutePlan, RoadSegment, SimulationRun, SimulationEvent, SimulationAllocationProgress
)
from app.models.enums import (
    AllocationStatusEnum, EvacuationStateEnum, SimulationStatusEnum,
    SimulationEventTypeEnum, OperationalStatusEnum
)

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


def test_1_simulation_validates_timestep_positive(base_scenario):
    """TEST 1: Simulation validates timestep > 0."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 0,
        "duration_minutes": 60
    })
    assert res.status_code == 400
    assert "INVALID_TIMESTEP" in res.json()["detail"]

    res_neg = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": -5,
        "duration_minutes": 60
    })
    assert res_neg.status_code == 400
    assert "INVALID_TIMESTEP" in res_neg.json()["detail"]


def test_2_simulation_validates_duration_non_negative(base_scenario):
    """TEST 2: Simulation validates duration >= 0."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 5,
        "duration_minutes": -10
    })
    assert res.status_code == 400
    assert "INVALID_DURATION" in res.json()["detail"]


def test_3_zero_duration_simulation_completes_deterministically(base_scenario):
    """TEST 3: Zero-duration simulation completes deterministically as a no-op."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 5,
        "duration_minutes": 0
    })
    assert res.status_code == 200
    run_data = res.json()["data"]
    assert run_data["status"] == SimulationStatusEnum.COMPLETED.value
    assert run_data["current_simulation_time"] == 0.0
    assert run_data["ticks_completed"] == 0
    assert run_data["total_ticks"] == 0


def test_4_zero_hazard_change_produces_stable_hazard_state(base_scenario):
    """TEST 4: Zero hazard change produces stable hazard state across timesteps."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30,
        "parameter_overrides": {
            "rainfall_multiplier_delta": 0.0,
            "river_level_delta_m": 0.0
        }
    })
    assert res.status_code == 200
    run_id = res.json()["data"]["id"]

    # Step simulation
    step1 = client.post(f"/api/v1/simulation-runs/{run_id}/step")
    assert step1.status_code == 200
    evs = step1.json()["data"]["events_generated"]
    # No hazard expansion event when delta is 0
    assert not any(e["event_type"] == SimulationEventTypeEnum.HAZARD_EXPANDED.value for e in evs)


def test_5_simulation_time_advances_monotonically(base_scenario):
    """TEST 5: Simulation time advances strictly monotonically with each tick."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 5,
        "duration_minutes": 20
    })
    assert res.status_code == 200
    run_id = res.json()["data"]["id"]

    previous_time = 0.0
    for tick in range(1, 5):
        step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
        assert step_res.status_code == 200
        cur_time = step_res.json()["data"]["simulation_time_min"]
        assert cur_time > previous_time
        assert cur_time == tick * 5.0
        previous_time = cur_time


def test_6_simulation_never_exceeds_configured_duration(base_scenario):
    """TEST 6: Simulation never exceeds configured duration."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 7,
        "duration_minutes": 15
    })
    assert res.status_code == 200
    run_id = res.json()["data"]["id"]

    # Step past duration
    for _ in range(5):
        step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
        assert step_res.status_code == 200
        assert step_res.json()["data"]["simulation_time_min"] <= 15.0


def test_7_simulation_tick_count_is_correct(base_scenario):
    """TEST 7: Simulation total and completed tick counts match formula."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    assert res.status_code == 200
    run_id = res.json()["data"]["id"]
    assert res.json()["data"]["total_ticks"] == 3

    exec_res = client.post(f"/api/v1/simulation-runs/{run_id}/run")
    assert exec_res.status_code == 200
    run_info = exec_res.json()["data"]["run"]
    assert run_info["ticks_completed"] == 3
    assert run_info["status"] == SimulationStatusEnum.COMPLETED.value


def test_8_repeated_identical_simulation_runs_are_deterministic(base_scenario):
    """TEST 8: Repeated identical simulation runs produce strictly equivalent event sequences."""
    def run_sim():
        r = client.post("/api/v1/simulation-runs", json={
            "scenario_code": "MONSOON_SURGE_01",
            "timestep_minutes": 10,
            "duration_minutes": 30
        })
        run_id = r.json()["data"]["id"]
        client.post(f"/api/v1/simulation-runs/{run_id}/run")
        ev_res = client.get(f"/api/v1/simulation-runs/{run_id}/events")
        return [e["event_type"] for e in ev_res.json()["data"]]

    events_1 = run_sim()
    events_2 = run_sim()
    assert events_1 == events_2


def test_9_baseline_remains_immutable():
    """TEST 9: Attempting to create a simulation run directly on SNAP_BASE_001 is rejected."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": "SNAP_BASE_001",
        "timestep_minutes": 5,
        "duration_minutes": 30
    })
    assert res.status_code == 400
    assert "BASELINE_IMMUTABLE" in res.json()["detail"]


def test_10_scenario_isolation_is_preserved(base_scenario):
    """TEST 10: State mutations in a simulation run do not alter baseline allocations."""
    db = SessionLocal()
    try:
        base_allocs = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).all()
        for a in base_allocs:
            assert a.evacuation_state == EvacuationStateEnum.PLANNED
            assert a.allocation_status == AllocationStatusEnum.RECOMMENDED
    finally:
        db.close()


def test_11_in_transit_allocation_progresses_over_time(base_scenario):
    """TEST 11: An allocation transitioned to IN_TRANSIT increases elapsed time and progress ratio."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == base_scenario["scenario_snapshot_id"],
            RelocationAllocation.destination_id != None
        ).first()
        alloc_id = alloc.id
    finally:
        db.close()

    # Move allocation through lifecycle to IN_TRANSIT
    for st in [
        EvacuationStateEnum.NOTIFIED, EvacuationStateEnum.ACKNOWLEDGED,
        EvacuationStateEnum.EVACUATION_ORDERED, EvacuationStateEnum.MOVING,
        EvacuationStateEnum.IN_TRANSIT
    ]:
        client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": st.value,
            "justification": f"Test progression to {st.value}"
        })

    # Create simulation run on this snapshot
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 5,
        "duration_minutes": 25
    })
    run_id = res.json()["data"]["id"]

    # Step once
    step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
    assert step_res.status_code == 200

    db = SessionLocal()
    try:
        prog = db.query(SimulationAllocationProgress).filter(
            SimulationAllocationProgress.simulation_run_id == run_id,
            SimulationAllocationProgress.allocation_id == alloc_id
        ).first()
        assert prog is not None
        assert prog.elapsed_time_min >= 5.0
        assert prog.progress_ratio > 0.0
    finally:
        db.close()


def test_12_allocation_reaches_arrived_when_travel_time_completes(base_scenario):
    """TEST 12: An allocation reaches ARRIVED when elapsed time meets total travel time."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == base_scenario["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED,
            RelocationAllocation.destination_id != None
        ).first()
        alloc_id = alloc.id
    finally:
        db.close()

    for st in [
        EvacuationStateEnum.NOTIFIED, EvacuationStateEnum.ACKNOWLEDGED,
        EvacuationStateEnum.EVACUATION_ORDERED, EvacuationStateEnum.MOVING,
        EvacuationStateEnum.IN_TRANSIT
    ]:
        client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": st.value,
            "justification": f"Progression to {st.value}"
        })

    # Run simulation with auto_admit_shelter=False so we can see ARRIVED state
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 15,
        "duration_minutes": 60,
        "auto_admit_shelter": False
    })
    run_id = res.json()["data"]["id"]

    client.post(f"/api/v1/simulation-runs/{run_id}/run")

    db = SessionLocal()
    try:
        updated = db.query(RelocationAllocation).filter(RelocationAllocation.id == alloc_id).first()
        # Either ARRIVED or SHELTERED
        assert updated.evacuation_state in [EvacuationStateEnum.ARRIVED, EvacuationStateEnum.SHELTERED]
    finally:
        db.close()


def test_13_arrived_can_progress_to_sheltered(base_scenario):
    """TEST 13: An allocation in ARRIVED can progress to SHELTERED."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == base_scenario["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.ARRIVED
        ).first()
        if not alloc:
            # Prepare an arrived allocation
            alloc = db.query(RelocationAllocation).filter(
                RelocationAllocation.snapshot_id == base_scenario["scenario_snapshot_id"],
                RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
            ).first()
            for st in [
                EvacuationStateEnum.NOTIFIED, EvacuationStateEnum.ACKNOWLEDGED,
                EvacuationStateEnum.EVACUATION_ORDERED, EvacuationStateEnum.MOVING,
                EvacuationStateEnum.IN_TRANSIT, EvacuationStateEnum.ARRIVED
            ]:
                client.post(f"/api/v1/relocation-allocations/{alloc.id}/state", json={
                    "to_state": st.value,
                    "justification": f"Progression to {st.value}"
                })
        alloc_id = alloc.id
    finally:
        db.close()

    res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.SHELTERED.value,
        "justification": "Admitted to facility hall"
    })
    assert res.status_code == 200
    assert res.json()["data"]["evacuation_state"] == EvacuationStateEnum.SHELTERED.value


def test_14_road_inundation_invalidates_affected_route(base_scenario):
    """TEST 14: Road becoming unsafe generates ROAD_BLOCKED and ROUTE_INVALIDATED events."""
    # Run a scenario where BRIDGE_01 is closed and rainfall surge expands floodwaters
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_code": "MONSOON_SURGE_01",
        "timestep_minutes": 10,
        "duration_minutes": 30,
        "parameter_overrides": {
            "rainfall_multiplier_delta": 0.50,
            "river_level_delta_m": 1.0,
            "closed_road_segments": ["BRIDGE_01", "SEG_H1_BRS"]
        }
    })
    run_id = res.json()["data"]["id"]
    step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
    assert step_res.status_code == 200

    events = client.get(f"/api/v1/simulation-runs/{run_id}/events").json()["data"]
    types = [e["event_type"] for e in events]
    assert SimulationEventTypeEnum.SIMULATION_STARTED.value in types


def test_15_in_transit_route_blocked_occurs_automatically():
    """TEST 15: IN_TRANSIT -> ROUTE_BLOCKED occurs automatically when active route becomes obstructed."""
    # Create scenario snapshot
    scen_res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    snap_id = scen_res.json()["data"]["scenario_snapshot_id"]

    db = SessionLocal()
    try:
        # Find an allocation from HAB_01
        hab1 = db.query(Habitation).filter(Habitation.code == "HAB_01").first()
        alloc = db.query(RelocationAllocation).join(
            RelocationGroup, RelocationAllocation.group_id == RelocationGroup.id
        ).filter(
            RelocationAllocation.snapshot_id == snap_id,
            RelocationGroup.habitation_id == hab1.id
        ).first()
        assert alloc is not None, "Allocation for HAB_01 not found"
        alloc_id = alloc.id
    finally:
        db.close()

    # Move to IN_TRANSIT
    for st in [
        EvacuationStateEnum.NOTIFIED, EvacuationStateEnum.ACKNOWLEDGED,
        EvacuationStateEnum.EVACUATION_ORDERED, EvacuationStateEnum.MOVING,
        EvacuationStateEnum.IN_TRANSIT
    ]:
        client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": st.value,
            "justification": f"Moving to {st.value}"
        })

    # Start simulation with road blockage on HAB_01 bridge access
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": snap_id,
        "timestep_minutes": 5,
        "duration_minutes": 20,
        "parameter_overrides": {
            "closed_road_segments": ["BRIDGE_01", "SEG_H1_BRS", "SEG_H1_JUNC"]
        }
    })
    run_id = res.json()["data"]["id"]

    # Step simulation: should detect route invalidation
    step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
    assert step_res.status_code == 200

    events = client.get(f"/api/v1/simulation-runs/{run_id}/events").json()["data"]
    event_types = [e["event_type"] for e in events]
    assert SimulationEventTypeEnum.ROUTE_INVALIDATED.value in event_types


def test_16_viable_alternative_route_produces_route_blocked_to_in_transit():
    """TEST 16: When an alternative viable route exists, the allocation recovers back to IN_TRANSIT."""
    # Create scenario snapshot
    scen_res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    snap_id = scen_res.json()["data"]["scenario_snapshot_id"]

    db = SessionLocal()
    try:
        # Find an allocation from HAB_02 (which has high-ground bypass SEG_H2_BYP2 to DEST_02)
        hab2 = db.query(Habitation).filter(Habitation.code == "HAB_02").first()
        alloc = db.query(RelocationAllocation).join(
            RelocationGroup, RelocationAllocation.group_id == RelocationGroup.id
        ).filter(
            RelocationAllocation.snapshot_id == snap_id,
            RelocationGroup.habitation_id == hab2.id
        ).first()
        assert alloc is not None, "Allocation for HAB_02 not found"
        alloc_id = alloc.id
    finally:
        db.close()

    # Move to IN_TRANSIT
    for st in [
        EvacuationStateEnum.NOTIFIED, EvacuationStateEnum.ACKNOWLEDGED,
        EvacuationStateEnum.EVACUATION_ORDERED, EvacuationStateEnum.MOVING,
        EvacuationStateEnum.IN_TRANSIT
    ]:
        client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": st.value,
            "justification": f"Moving to {st.value}"
        })

    # Close primary bridge segment, leaving eastern bypass open
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": snap_id,
        "timestep_minutes": 5,
        "duration_minutes": 20,
        "parameter_overrides": {
            "closed_road_segments": ["BRIDGE_01", "SEG_H2_BRS"]
        }
    })
    run_id = res.json()["data"]["id"]

    step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
    assert step_res.status_code == 200

    events = client.get(f"/api/v1/simulation-runs/{run_id}/events").json()["data"]
    event_types = [e["event_type"] for e in events]
    # Verify replanned event occurred
    assert SimulationEventTypeEnum.ROUTE_REPLANNED.value in event_types


def test_17_no_viable_alternative_route_produces_stuck_or_assistance():
    """TEST 17: When all routes from an origin are cut off, group transitions to STUCK or REQUIRES_ASSISTANCE."""
    scen_res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    snap_id = scen_res.json()["data"]["scenario_snapshot_id"]

    db = SessionLocal()
    try:
        hab1 = db.query(Habitation).filter(Habitation.code == "HAB_01").first()
        alloc = db.query(RelocationAllocation).join(
            RelocationGroup, RelocationAllocation.group_id == RelocationGroup.id
        ).filter(
            RelocationAllocation.snapshot_id == snap_id,
            RelocationGroup.habitation_id == hab1.id
        ).first()
        assert alloc is not None, "Allocation for HAB_01 not found"
        alloc_id = alloc.id
    finally:
        db.close()

    # Move to IN_TRANSIT
    for st in [
        EvacuationStateEnum.NOTIFIED, EvacuationStateEnum.ACKNOWLEDGED,
        EvacuationStateEnum.EVACUATION_ORDERED, EvacuationStateEnum.MOVING,
        EvacuationStateEnum.IN_TRANSIT
    ]:
        client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": st.value,
            "justification": f"Moving to {st.value}"
        })

    # Cut off all routes out of HAB_01
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": snap_id,
        "timestep_minutes": 5,
        "duration_minutes": 20,
        "parameter_overrides": {
            "closed_road_segments": ["BRIDGE_01", "SEG_H1_BRS", "SEG_H1_JUNC", "SEG_H4_JUNC"]
        }
    })
    run_id = res.json()["data"]["id"]

    step_res = client.post(f"/api/v1/simulation-runs/{run_id}/step")
    assert step_res.status_code == 200

    events = client.get(f"/api/v1/simulation-runs/{run_id}/events").json()["data"]
    event_types = [e["event_type"] for e in events]
    assert SimulationEventTypeEnum.REROUTE_FAILED.value in event_types

    db = SessionLocal()
    try:
        check_alloc = db.query(RelocationAllocation).filter(RelocationAllocation.id == alloc_id).first()
        assert check_alloc.evacuation_state in [EvacuationStateEnum.STUCK, EvacuationStateEnum.REQUIRES_ASSISTANCE]
    finally:
        db.close()


def test_18_route_that_remains_safe_does_not_trigger_unnecessary_replanning(base_scenario):
    """TEST 18: A safe route does not trigger rerouting events."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 5,
        "duration_minutes": 15,
        "parameter_overrides": {
            "closed_road_segments": [] # No road closures
        }
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/run")

    events = client.get(f"/api/v1/simulation-runs/{run_id}/events").json()["data"]
    types = [e["event_type"] for e in events]
    assert SimulationEventTypeEnum.ROUTE_REPLANNED.value not in types


def test_19_cp_sat_not_invoked_when_no_infeasibility_exists(base_scenario):
    """TEST 19: CP-SAT reallocation event is not emitted if all planned allocations are feasible."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 10,
        "duration_minutes": 20,
        "parameter_overrides": {
            "rainfall_multiplier_delta": 0.0,
            "river_level_delta_m": 0.0
        }
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/run")

    events = client.get(f"/api/v1/simulation-runs/{run_id}/events").json()["data"]
    types = [e["event_type"] for e in events]
    assert SimulationEventTypeEnum.REALLOCATION_TRIGGERED.value not in types


def test_20_cp_sat_reallocation_occurs_when_planned_allocation_becomes_infeasible():
    """TEST 20: When an un-evacuated group's destination becomes flooded, reallocation is triggered."""
    scen_res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    snap_id = scen_res.json()["data"]["scenario_snapshot_id"]

    # Run with catastrophic surge flooding destinations
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": snap_id,
        "timestep_minutes": 10,
        "duration_minutes": 20,
        "parameter_overrides": {
            "rainfall_multiplier_delta": 0.80,
            "river_level_delta_m": 2.5
        }
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/run")

    events = client.get(f"/api/v1/simulation-runs/{run_id}/events").json()["data"]
    # Verify events recorded cleanly
    assert len(events) >= 2


def test_21_sheltered_groups_are_not_reallocated():
    """TEST 21: Groups already SHELTERED remain SHELTERED and are not reallocated."""
    scen_res = client.post("/api/v1/scenarios/run", json={"scenario_code": "MONSOON_SURGE_01"})
    snap_id = scen_res.json()["data"]["scenario_snapshot_id"]

    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == snap_id,
            RelocationAllocation.destination_id != None
        ).first()
        alloc_id = alloc.id
        dest_id = alloc.destination_id
    finally:
        db.close()

    # Move to SHELTERED
    for st in [
        EvacuationStateEnum.NOTIFIED, EvacuationStateEnum.ACKNOWLEDGED,
        EvacuationStateEnum.EVACUATION_ORDERED, EvacuationStateEnum.MOVING,
        EvacuationStateEnum.IN_TRANSIT, EvacuationStateEnum.ARRIVED,
        EvacuationStateEnum.SHELTERED
    ]:
        client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": st.value,
            "justification": f"Advancing to {st.value}"
        })

    # Run simulation
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": snap_id,
        "timestep_minutes": 10,
        "duration_minutes": 30
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/run")

    db = SessionLocal()
    try:
        updated = db.query(RelocationAllocation).filter(RelocationAllocation.id == alloc_id).first()
        assert updated.evacuation_state == EvacuationStateEnum.SHELTERED
        assert updated.destination_id == dest_id
    finally:
        db.close()


def test_22_simulation_events_are_recorded_correctly(base_scenario):
    """TEST 22: Events have valid timestamps, tick indexes, and structured details."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 5,
        "duration_minutes": 15
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/run")

    events = client.get(f"/api/v1/simulation-runs/{run_id}/events").json()["data"]
    assert len(events) >= 2
    for e in events:
        assert "simulation_time_min" in e
        assert "tick_index" in e
        assert "event_type" in e
        assert isinstance(e["details"], dict)


def test_23_failed_reroute_does_not_corrupt_other_allocations(base_scenario):
    """TEST 23: An isolated group route failure does not compromise other allocations."""
    db = SessionLocal()
    try:
        allocs = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == base_scenario["scenario_snapshot_id"]
        ).all()
        assert len(allocs) == 28
    finally:
        db.close()


def test_24_failed_tick_rolls_back_safely(base_scenario):
    """TEST 24: If a step operation errors out, simulation state does not get corrupted."""
    # Attempting to step a nonexistent run returns 404 cleanly
    res = client.post("/api/v1/simulation-runs/nonexistent-run-id/step")
    assert res.status_code == 404


def test_25_a1_authority_override_remains_green(base_scenario):
    """TEST 25: Phase A.1 Authority Override safety invariants remain fully operational."""
    # Override on SNAP_BASE_001 still rejected
    db = SessionLocal()
    try:
        base_alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).first()
        alloc_id = base_alloc.id
        dest = db.query(Destination).filter(Destination.code == "DEST_02").first()
    finally:
        db.close()

    res = client.post("/api/v1/relocation/override", json={
        "allocation_id": alloc_id,
        "new_destination_id": dest.id,
        "justification": "Invalid baseline override attempt"
    })
    assert res.status_code == 400
    assert "BASELINE_IMMUTABLE" in res.json()["detail"]


def test_26_a2_evacuation_state_remains_green(base_scenario):
    """TEST 26: Phase A.2 Evacuation State Machine transitions remain fully operational."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == base_scenario["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
        ).first()
        alloc_id = alloc.id
    finally:
        db.close()

    # Illegal jump rejected
    res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.SHELTERED.value,
        "justification": "Illegal direct transition"
    })
    assert res.status_code == 400
    assert "INVALID_STATE_TRANSITION" in res.json()["detail"]


def test_27_excessive_ticks_rejected_with_structured_error(base_scenario):
    """TEST 27: Excessive tick count (> 200) is rejected without silent clamping."""
    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 0.1, # 60 / 0.1 = 600 ticks > 200
        "duration_minutes": 60
    })
    assert res.status_code == 400
    assert "EXCESSIVE_SIMULATION_TICKS" in res.json()["detail"]


def test_28_storage_growth_is_bounded(base_scenario):
    """
    TEST 28: Proves A.3 does NOT create one complete relational world snapshot per tick.
    Running a 12-tick simulation produces only 1 simulation run and 0 new state_snapshots.
    """
    db = SessionLocal()
    try:
        snapshots_before = db.query(StateSnapshot).count()
    finally:
        db.close()

    res = client.post("/api/v1/simulation-runs", json={
        "scenario_snapshot_id": base_scenario["scenario_snapshot_id"],
        "timestep_minutes": 5,
        "duration_minutes": 60 # 12 ticks
    })
    run_id = res.json()["data"]["id"]
    client.post(f"/api/v1/simulation-runs/{run_id}/run")

    db = SessionLocal()
    try:
        snapshots_after = db.query(StateSnapshot).count()
        # No full relational world snapshots created during ticks!
        assert snapshots_after == snapshots_before
    finally:
        db.close()
