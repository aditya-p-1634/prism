"""PRISM V2 — Phase A.2: Evacuation State Machine Test Suite
==========================================================
Verifies Plan vs State separation, canonical lifecycle transitions,
exception state handling, recovery, baseline immutability,
atomicity, and audit logging.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.entities import (
    StateSnapshot, RelocationAllocation, RelocationGroup, Destination, AuditEvent
)
from app.models.enums import AllocationStatusEnum, EvacuationStateEnum

client = TestClient(app)


@pytest.fixture(scope="module")
def scenario_context():
    """Ensure baseline exists and create a scenario snapshot for state machine testing."""
    res = client.post("/api/v1/scenarios/run", json={
        "scenario_code": "MONSOON_SURGE_01"
    })
    assert res.status_code == 200, f"Failed to run scenario: {res.text}"
    scen_data = res.json()["data"]
    scen_snap_id = scen_data["scenario_snapshot_id"]
    return {
        "baseline_snapshot_id": "SNAP_BASE_001",
        "scenario_snapshot_id": scen_snap_id
    }


def test_1_initial_state(scenario_context):
    """TEST 1: Relocation allocations start in PLANNED state and are not falsely marked as evacuated."""
    db = SessionLocal()
    try:
        # Check baseline snapshot allocations
        base_allocs = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["baseline_snapshot_id"]
        ).all()
        assert len(base_allocs) == 28
        for a in base_allocs:
            assert a.evacuation_state == EvacuationStateEnum.PLANNED, (
                f"Baseline allocation {a.id} must be PLANNED, but found {a.evacuation_state}"
            )
            assert a.allocation_status == AllocationStatusEnum.RECOMMENDED

        # Check scenario snapshot allocations
        scen_allocs = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"]
        ).all()
        assert len(scen_allocs) > 0
        for a in scen_allocs:
            assert a.evacuation_state == EvacuationStateEnum.PLANNED, (
                f"Scenario allocation {a.id} must initialize to PLANNED, but found {a.evacuation_state}"
            )
    finally:
        db.close()


def test_2_valid_normal_transitions(scenario_context):
    """
    TEST 2: Verify full canonical lifecycle:
    PLANNED -> NOTIFIED -> ACKNOWLEDGED -> EVACUATION_ORDERED -> MOVING -> IN_TRANSIT -> ARRIVED -> SHELTERED
    """
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
        ).first()
        assert alloc is not None, "Scenario allocation in PLANNED state not found"
        alloc_id = alloc.id
    finally:
        db.close()

    lifecycle_steps = [
        (EvacuationStateEnum.NOTIFIED, "Notified household head via emergency alert SMS"),
        (EvacuationStateEnum.ACKNOWLEDGED, "Household acknowledged alert and confirmed readiness"),
        (EvacuationStateEnum.EVACUATION_ORDERED, "Incident commander issued formal mandatory evacuation order"),
        (EvacuationStateEnum.MOVING, "Household departed dwelling towards muster point"),
        (EvacuationStateEnum.IN_TRANSIT, "Household boarded transit vehicle on designated safe route"),
        (EvacuationStateEnum.ARRIVED, "Transit vehicle arrived at destination facility perimeter"),
        (EvacuationStateEnum.SHELTERED, "Household registered and admitted to designated shelter hall"),
    ]

    for next_state, justification in lifecycle_steps:
        res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": next_state.value,
            "justification": justification
        })
        assert res.status_code == 200, f"Transition to {next_state.value} failed: {res.text}"
        data = res.json()["data"]
        assert data["evacuation_state"] == next_state.value, f"Expected {next_state.value}, got {data['evacuation_state']}"

    # Verify final state in database
    db = SessionLocal()
    try:
        updated_alloc = db.query(RelocationAllocation).filter(RelocationAllocation.id == alloc_id).first()
        assert updated_alloc.evacuation_state == EvacuationStateEnum.SHELTERED
    finally:
        db.close()


def test_3_invalid_transitions_rejected(scenario_context):
    """
    TEST 3: Verify illegal skipping of states:
    PLANNED -> SHELTERED (rejected)
    PLANNED -> ARRIVED (rejected)
    NOTIFIED -> SHELTERED (rejected)
    """
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
        ).first()
        assert alloc is not None
        alloc_id = alloc.id
    finally:
        db.close()

    # 1. PLANNED -> SHELTERED (Illegal jump)
    res1 = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.SHELTERED.value,
        "justification": "Attempting illegal direct jump to SHELTERED"
    })
    assert res1.status_code == 400
    assert "INVALID_STATE_TRANSITION" in res1.json()["detail"]

    # 2. PLANNED -> ARRIVED (Illegal jump)
    res2 = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.ARRIVED.value,
        "justification": "Attempting illegal direct jump to ARRIVED"
    })
    assert res2.status_code == 400
    assert "INVALID_STATE_TRANSITION" in res2.json()["detail"]

    # Transition to NOTIFIED first
    res_notified = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.NOTIFIED.value,
        "justification": "Valid notification for test"
    })
    assert res_notified.status_code == 200

    # 3. NOTIFIED -> SHELTERED (Illegal jump)
    res3 = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.SHELTERED.value,
        "justification": "Attempting illegal jump from NOTIFIED to SHELTERED"
    })
    assert res3.status_code == 400
    assert "INVALID_STATE_TRANSITION" in res3.json()["detail"]


def test_4_no_response_transition(scenario_context):
    """TEST 4: Test valid transition into NO_RESPONSE from NOTIFIED."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
        ).first()
        assert alloc is not None
        alloc_id = alloc.id
    finally:
        db.close()

    # Move to NOTIFIED
    res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.NOTIFIED.value,
        "justification": "Cellular broadcast alert sent"
    })
    assert res.status_code == 200

    # Transition to NO_RESPONSE
    res_nr = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.NO_RESPONSE.value,
        "justification": "No acknowledgement received after timeout threshold"
    })
    assert res_nr.status_code == 200
    assert res_nr.json()["data"]["evacuation_state"] == EvacuationStateEnum.NO_RESPONSE.value


def test_5_route_blocked_transition(scenario_context):
    """TEST 5: Test transition into ROUTE_BLOCKED from IN_TRANSIT."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
        ).first()
        assert alloc is not None
        alloc_id = alloc.id
    finally:
        db.close()

    # Fast-forward to IN_TRANSIT through valid steps
    steps = [
        EvacuationStateEnum.NOTIFIED,
        EvacuationStateEnum.ACKNOWLEDGED,
        EvacuationStateEnum.EVACUATION_ORDERED,
        EvacuationStateEnum.MOVING,
        EvacuationStateEnum.IN_TRANSIT
    ]
    for st in steps:
        res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": st.value,
            "justification": f"Valid progression to {st.value}"
        })
        assert res.status_code == 200

    # Now report ROUTE_BLOCKED
    res_block = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.ROUTE_BLOCKED.value,
        "justification": "Road segment inundated by sudden flash runoff, convoy halted"
    })
    assert res_block.status_code == 200
    assert res_block.json()["data"]["evacuation_state"] == EvacuationStateEnum.ROUTE_BLOCKED.value


def test_6_stuck_transition(scenario_context):
    """TEST 6: Test transition into STUCK from MOVING or IN_TRANSIT."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
        ).first()
        assert alloc is not None
        alloc_id = alloc.id
    finally:
        db.close()

    # Move to MOVING
    for st in [EvacuationStateEnum.NOTIFIED, EvacuationStateEnum.ACKNOWLEDGED, EvacuationStateEnum.EVACUATION_ORDERED, EvacuationStateEnum.MOVING]:
        res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": st.value,
            "justification": f"Progressing to {st.value}"
        })
        assert res.status_code == 200

    # Transition to STUCK
    res_stuck = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.STUCK.value,
        "justification": "Vehicle transmission failure in mud lane"
    })
    assert res_stuck.status_code == 200
    assert res_stuck.json()["data"]["evacuation_state"] == EvacuationStateEnum.STUCK.value


def test_7_recovery_from_exception_state(scenario_context):
    """TEST 7: Verify exception state ROUTE_BLOCKED can recover to IN_TRANSIT (Non-terminal)."""
    db = SessionLocal()
    try:
        # Find an allocation in ROUTE_BLOCKED from test_5
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.ROUTE_BLOCKED
        ).first()
        assert alloc is not None, "Allocation in ROUTE_BLOCKED not found"
        alloc_id = alloc.id
    finally:
        db.close()

    # Recover: ROUTE_BLOCKED -> IN_TRANSIT
    res_rec = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.IN_TRANSIT.value,
        "justification": "Bypass route established, convoy resumed transit safely"
    })
    assert res_rec.status_code == 200
    assert res_rec.json()["data"]["evacuation_state"] == EvacuationStateEnum.IN_TRANSIT.value


def test_8_requires_assistance_lifecycle(scenario_context):
    """TEST 8: Test that REQUIRES_ASSISTANCE can be entered and exited via defined transition."""
    db = SessionLocal()
    try:
        # Find allocation in STUCK from test_6
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.STUCK
        ).first()
        assert alloc is not None
        alloc_id = alloc.id
    finally:
        db.close()

    # STUCK -> REQUIRES_ASSISTANCE
    res_ast = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.REQUIRES_ASSISTANCE.value,
        "justification": "Emergency heavy towing and medical transit requested"
    })
    assert res_ast.status_code == 200
    assert res_ast.json()["data"]["evacuation_state"] == EvacuationStateEnum.REQUIRES_ASSISTANCE.value

    # Recovery: REQUIRES_ASSISTANCE -> MOVING
    res_mov = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.MOVING.value,
        "justification": "Assistance team arrived, towing underway"
    })
    assert res_mov.status_code == 200
    assert res_mov.json()["data"]["evacuation_state"] == EvacuationStateEnum.MOVING.value


def test_9_authority_override_does_not_fake_evacuation(scenario_context):
    """
    TEST 9: Perform an authority override (Phase A.1).
    Verify destination changes, allocation_status is OVERRIDDEN,
    but evacuation_state remains PLANNED (does NOT become SHELTERED/ARRIVED).
    """
    db = SessionLocal()
    try:
        # Find a planned allocation
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED,
            RelocationAllocation.destination_id != None
        ).first()
        assert alloc is not None
        alloc_id = alloc.id

        current_dest = db.query(Destination).filter(Destination.id == alloc.destination_id).first()
        target_code = "DEST_02" if current_dest.code == "DEST_03" else "DEST_03"
        target_dest = db.query(Destination).filter(Destination.code == target_code).first()
        target_dest_id = target_dest.id
    finally:
        db.close()

    # Execute authority override
    res = client.post("/api/v1/relocation/override", json={
        "allocation_id": alloc_id,
        "new_destination_id": target_dest_id,
        "justification": "Operational rebalance of shelter allocation"
    })
    assert res.status_code == 200
    data = res.json()["data"]

    # Plan changed
    assert data["destination_id"] == target_dest_id
    assert data["allocation_status"] == AllocationStatusEnum.OVERRIDDEN.value

    # Operational execution state did NOT change to evacuated
    assert data["evacuation_state"] == EvacuationStateEnum.PLANNED.value
    assert data["evacuation_state"] != EvacuationStateEnum.SHELTERED.value
    assert data["evacuation_state"] != EvacuationStateEnum.ARRIVED.value


def test_10_baseline_immutability(scenario_context):
    """TEST 10: Attempting state mutation on SNAP_BASE_001 is rejected."""
    db = SessionLocal()
    try:
        base_alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["baseline_snapshot_id"]
        ).first()
        assert base_alloc is not None
        alloc_id = base_alloc.id
        orig_state = base_alloc.evacuation_state
    finally:
        db.close()

    res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.NOTIFIED.value,
        "justification": "Attempting illegal state transition on canonical baseline"
    })
    assert res.status_code == 400
    assert "BASELINE_IMMUTABLE" in res.json()["detail"]

    # Verify baseline state is 100% untouched
    db = SessionLocal()
    try:
        check_alloc = db.query(RelocationAllocation).filter(RelocationAllocation.id == alloc_id).first()
        assert check_alloc.evacuation_state == orig_state
    finally:
        db.close()


def test_11_invalid_transition_atomicity(scenario_context):
    """TEST 11: Invalid transition leaves database state completely unchanged."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
        ).first()
        assert alloc is not None
        alloc_id = alloc.id
        orig_state = alloc.evacuation_state
    finally:
        db.close()

    # Attempt illegal transition
    res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.ARRIVED.value,
        "justification": "Invalid transition attempt"
    })
    assert res.status_code == 400

    # Verify allocation is unchanged in database
    db = SessionLocal()
    try:
        fresh_alloc = db.query(RelocationAllocation).filter(RelocationAllocation.id == alloc_id).first()
        assert fresh_alloc.evacuation_state == orig_state
    finally:
        db.close()


def test_12_audit_event_generation(scenario_context):
    """TEST 12: Successful state transition generates an AuditEvent with full before/after diffs."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
        ).first()
        assert alloc is not None
        alloc_id = alloc.id
    finally:
        db.close()

    res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.NOTIFIED.value,
        "justification": "Automated IVR alert delivery confirmed"
    })
    assert res.status_code == 200

    # Query audit event
    db = SessionLocal()
    try:
        audit = db.query(AuditEvent).filter(
            AuditEvent.action_type == "EVACUATION_STATE_TRANSITION",
            AuditEvent.entity_id == alloc_id
        ).order_by(AuditEvent.created_at.desc()).first()

        assert audit is not None, "AuditEvent not generated"
        assert audit.entity_type == "RelocationAllocation"
        assert audit.justification == "Automated IVR alert delivery confirmed"
        assert audit.before_state["evacuation_state"] == EvacuationStateEnum.PLANNED.value
        assert audit.after_state["evacuation_state"] == EvacuationStateEnum.NOTIFIED.value
    finally:
        db.close()


def test_13_repeated_invalid_transition(scenario_context):
    """TEST 13: Repeated execution of the same invalid transition does not corrupt state."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
        ).first()
        assert alloc is not None
        alloc_id = alloc.id
    finally:
        db.close()

    for _ in range(3):
        res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
            "to_state": EvacuationStateEnum.SHELTERED.value,
            "justification": "Repeated invalid transition"
        })
        assert res.status_code == 400
        assert "INVALID_STATE_TRANSITION" in res.json()["detail"]

    # Verify state remains PLANNED
    db = SessionLocal()
    try:
        fresh_alloc = db.query(RelocationAllocation).filter(RelocationAllocation.id == alloc_id).first()
        assert fresh_alloc.evacuation_state == EvacuationStateEnum.PLANNED
    finally:
        db.close()


def test_14_snapshot_isolation(scenario_context):
    """TEST 14: State updates in a mutable scenario snapshot do not modify baseline or other snapshots."""
    db = SessionLocal()
    try:
        base_allocs = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["baseline_snapshot_id"]
        ).all()
        # Verify all baseline allocations remain in PLANNED
        for a in base_allocs:
            assert a.evacuation_state == EvacuationStateEnum.PLANNED
    finally:
        db.close()


def test_15_stale_state_concurrency_protection(scenario_context):
    """TEST 15: Concurrency check: If expected_current_state does not match, transition is rejected."""
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scenario_context["scenario_snapshot_id"],
            RelocationAllocation.evacuation_state == EvacuationStateEnum.NOTIFIED
        ).first()
        assert alloc is not None
        alloc_id = alloc.id
    finally:
        db.close()

    # Pass expected_current_state = PLANNED (but current is NOTIFIED)
    res = client.post(f"/api/v1/relocation-allocations/{alloc_id}/state", json={
        "to_state": EvacuationStateEnum.ACKNOWLEDGED.value,
        "justification": "Stale update attempt",
        "expected_current_state": EvacuationStateEnum.PLANNED.value
    })
    assert res.status_code == 409
    assert "STALE_STATE_CONFLICT" in res.json()["detail"]
