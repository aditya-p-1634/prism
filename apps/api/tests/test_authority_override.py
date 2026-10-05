"""
PRISM V2 — PHASE A.1 REGRESSION TEST SUITE
Authority Override Safety & Baseline Immutability Invariant Suite

Tests:
1. TEST 1: Valid authority override on a mutable scenario snapshot succeeds.
2. TEST 2: Attempted override directly against SNAP_BASE_001 cannot mutate baseline.
3. TEST 3: Attempt to override to a flooded/unsafe destination is rejected.
4. TEST 4: Attempt to override across a blocked/collapsed bridge is rejected.
5. TEST 5: Attempt to override when destination capacity is insufficient is rejected.
6. TEST 6: Successful override updates old/new capacity consistently.
7. TEST 7: Failed override leaves database state completely unchanged.
8. TEST 8: Successful override creates the expected audit event.
9. TEST 9: Disconnected graph/no viable route is rejected.
10. TEST 10: Repeated execution of the same invalid override does not partially corrupt state.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.entities import (
    StateSnapshot, RelocationAllocation, RelocationGroup, CapacityState,
    Destination, AuditEvent, Habitation, RoutePlan
)
from app.models.enums import AllocationStatusEnum, OperationalStatusEnum

client = TestClient(app)

@pytest.fixture(scope="module")
def scenario_context():
    """Ensure baseline exists and create a scenario snapshot for override testing."""
    # Run MONSOON_SURGE_01 scenario to get an active scenario snapshot
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


def test_1_valid_authority_override_succeeds(scenario_context):
    """TEST 1: Valid authority override on a mutable scenario snapshot succeeds."""
    scen_snap_id = scenario_context["scenario_snapshot_id"]
    db = SessionLocal()
    try:
        # Find an allocation currently at DEST_03 from HAB_01 or HAB_02 where DEST_02 has headroom
        # In MONSOON_SURGE_01, DEST_02 has remaining capacity 18
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scen_snap_id,
            RelocationAllocation.destination_id != None
        ).first()
        assert alloc is not None, "Scenario allocation not found"

        group = db.query(RelocationGroup).filter(RelocationGroup.id == alloc.group_id).first()
        group_size = group.group_size

        # Find another destination with sufficient capacity and viable route
        # For HAB_01 or HAB_02, DEST_02 and DEST_03 both have bypass routes
        current_dest_id = alloc.destination_id
        current_dest = db.query(Destination).filter(Destination.id == current_dest_id).first()
        
        target_code = "DEST_02" if current_dest.code == "DEST_03" else "DEST_03"
        target_dest = db.query(Destination).filter(Destination.code == target_code).first()

        res = client.post("/api/v1/relocation/override", json={
            "allocation_id": alloc.id,
            "new_destination_id": target_dest.id,
            "justification": "Valid operational rebalance to secondary facility"
        })
        assert res.status_code == 200, f"Override failed: {res.text}"
        data = res.json()["data"]
        assert data["destination_id"] == target_dest.id
        assert data["allocation_status"] == AllocationStatusEnum.OVERRIDDEN.value
        assert "AUTHORITY_OVERRIDE" in data["reason_code"]
    finally:
        db.close()


def test_2_baseline_immutability_enforced():
    """TEST 2: Attempted override directly against SNAP_BASE_001 cannot mutate baseline."""
    db = SessionLocal()
    try:
        # Capture baseline allocation and capacity state before test
        base_alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).first()
        assert base_alloc is not None, "Baseline allocation not found"

        orig_dest_id = base_alloc.destination_id
        orig_status = base_alloc.allocation_status
        orig_reason = base_alloc.reason_code
        orig_route = base_alloc.route_plan_id

        dest_02 = db.query(Destination).filter(Destination.code == "DEST_02").first()

        # Attempt to override directly against SNAP_BASE_001
        res = client.post("/api/v1/relocation/override", json={
            "allocation_id": base_alloc.id,
            "new_destination_id": dest_02.id,
            "justification": "ILLEGAL_ATTEMPT_TO_MUTATE_CANONICAL_BASELINE"
        })

        # MUST be rejected with HTTP 400 Bad Request
        assert res.status_code == 400
        detail = res.json().get("detail", "")
        assert "BASELINE_IMMUTABLE" in detail

        # Verify database record is 100% untouched
        db.refresh(base_alloc)
        assert base_alloc.destination_id == orig_dest_id
        assert base_alloc.allocation_status == orig_status
        assert base_alloc.reason_code == orig_reason
        assert base_alloc.route_plan_id == orig_route
    finally:
        db.close()


def test_3_override_to_unsafe_destination_rejected(scenario_context):
    """TEST 3: Attempt to override to a flooded/unsafe destination is rejected."""
    scen_snap_id = scenario_context["scenario_snapshot_id"]
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scen_snap_id
        ).first()
        assert alloc is not None

        orig_dest_id = alloc.destination_id

        # Temporarily create a mock unsafe destination state or mark one closed
        unsafe_dest = db.query(Destination).filter(Destination.code == "DEST_02").first()
        unsafe_cap = db.query(CapacityState).filter(
            CapacityState.destination_id == unsafe_dest.id,
            CapacityState.snapshot_id == scen_snap_id
        ).first()

        # Mark as unsafe in capacity state
        prev_safety = unsafe_cap.is_safe
        prev_reason = unsafe_cap.rejection_reason
        unsafe_cap.is_safe = False
        unsafe_cap.rejection_reason = "HAZARD_INUNDATION_COLLAPSE"
        db.commit()

        try:
            res = client.post("/api/v1/relocation/override", json={
                "allocation_id": alloc.id,
                "new_destination_id": unsafe_dest.id,
                "justification": "Attempted override to known unsafe destination"
            })
            assert res.status_code == 400
            assert "DESTINATION_UNSAFE" in res.json().get("detail", "")
        finally:
            # Restore state
            unsafe_cap.is_safe = prev_safety
            unsafe_cap.rejection_reason = prev_reason
            db.commit()

        # Verify allocation was not modified
        db.refresh(alloc)
        assert alloc.destination_id == orig_dest_id
    finally:
        db.close()


def test_4_override_across_collapsed_bridge_rejected(scenario_context):
    """TEST 4: Attempt to override across a blocked/collapsed bridge is rejected."""
    scen_snap_id = scenario_context["scenario_snapshot_id"]
    db = SessionLocal()
    try:
        # In MONSOON_SURGE_01, BRIDGE_01 is collapsed.
        # HAB_01 (Riverside Lowlands) has no viable route to DEST_01!
        hab_01 = db.query(Habitation).filter(Habitation.code == "HAB_01").first()
        dest_01 = db.query(Destination).filter(Destination.code == "DEST_01").first()

        group_hab1 = db.query(RelocationGroup).filter(
            RelocationGroup.habitation_id == hab_01.id,
            RelocationGroup.snapshot_id == scen_snap_id
        ).first()

        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.group_id == group_hab1.id,
            RelocationAllocation.snapshot_id == scen_snap_id
        ).first()
        assert alloc is not None

        orig_dest_id = alloc.destination_id

        # Attempt to override to DEST_01 which requires crossing the collapsed BRIDGE_01
        res = client.post("/api/v1/relocation/override", json={
            "allocation_id": alloc.id,
            "new_destination_id": dest_01.id,
            "justification": "Attempt to route across collapsed bridge"
        })

        assert res.status_code == 400
        detail = res.json().get("detail", "")
        assert "NO_VIABLE_ROUTE" in detail

        # Verify allocation was not modified
        db.refresh(alloc)
        assert alloc.destination_id == orig_dest_id
    finally:
        db.close()


def test_5_insufficient_capacity_rejected(scenario_context):
    """TEST 5: Attempt to override when destination capacity is insufficient is rejected."""
    scen_snap_id = scenario_context["scenario_snapshot_id"]
    db = SessionLocal()
    try:
        # In scenario, DEST_03 capacity is tight
        dest_03 = db.query(Destination).filter(Destination.code == "DEST_03").first()
        cap_03 = db.query(CapacityState).filter(
            CapacityState.destination_id == dest_03.id,
            CapacityState.snapshot_id == scen_snap_id
        ).first()

        # Artificially set remaining capacity to 0
        orig_remaining = cap_03.remaining_capacity
        orig_occupied = cap_03.occupied_capacity
        cap_03.remaining_capacity = 0
        cap_03.occupied_capacity = cap_03.effective_capacity
        db.commit()

        # Find an allocation currently at DEST_02
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scen_snap_id,
            RelocationAllocation.destination_id != dest_03.id
        ).first()

        try:
            res = client.post("/api/v1/relocation/override", json={
                "allocation_id": alloc.id,
                "new_destination_id": dest_03.id,
                "justification": "Attempt to overload zero-headroom shelter"
            })
            assert res.status_code == 400
            assert "DESTINATION_CAPACITY_EXCEEDED" in res.json().get("detail", "")
        finally:
            cap_03.remaining_capacity = orig_remaining
            cap_03.occupied_capacity = orig_occupied
            db.commit()
    finally:
        db.close()


def test_6_capacity_accounting_consistency(scenario_context):
    """TEST 6: Successful override updates old/new capacity consistently."""
    scen_snap_id = scenario_context["scenario_snapshot_id"]
    db = SessionLocal()
    try:
        # Find an allocation at DEST_02 with a valid bypass to DEST_03
        dest_02 = db.query(Destination).filter(Destination.code == "DEST_02").first()
        dest_03 = db.query(Destination).filter(Destination.code == "DEST_03").first()

        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scen_snap_id,
            RelocationAllocation.destination_id == dest_02.id
        ).first()

        group = db.query(RelocationGroup).filter(RelocationGroup.id == alloc.group_id).first()
        g_size = group.group_size

        cap_old = db.query(CapacityState).filter(
            CapacityState.destination_id == dest_02.id,
            CapacityState.snapshot_id == scen_snap_id
        ).first()
        cap_new = db.query(CapacityState).filter(
            CapacityState.destination_id == dest_03.id,
            CapacityState.snapshot_id == scen_snap_id
        ).first()

        # Ensure DEST_03 has enough headroom for test
        if cap_new.remaining_capacity < g_size:
            cap_new.remaining_capacity += g_size + 5
            db.commit()

        old_occ_before = cap_old.occupied_capacity
        old_rem_before = cap_old.remaining_capacity
        new_occ_before = cap_new.occupied_capacity
        new_rem_before = cap_new.remaining_capacity

        res = client.post("/api/v1/relocation/override", json={
            "allocation_id": alloc.id,
            "new_destination_id": dest_03.id,
            "justification": "Consistent capacity accounting test"
        })
        assert res.status_code == 200

        db.refresh(cap_old)
        db.refresh(cap_new)

        # Invariant 4 checks
        assert cap_old.occupied_capacity == old_occ_before - g_size
        assert cap_old.remaining_capacity == old_rem_before + g_size
        assert cap_new.occupied_capacity == new_occ_before + g_size
        assert cap_new.remaining_capacity == new_rem_before - g_size
        assert cap_old.remaining_capacity == cap_old.effective_capacity - cap_old.occupied_capacity
        assert cap_new.remaining_capacity == cap_new.effective_capacity - cap_new.occupied_capacity
        assert cap_old.remaining_capacity >= 0
        assert cap_new.remaining_capacity >= 0
    finally:
        db.close()


def test_7_failed_override_leaves_database_state_unchanged(scenario_context):
    """TEST 7: Failed override leaves database state unchanged (transactional safety)."""
    scen_snap_id = scenario_context["scenario_snapshot_id"]
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scen_snap_id
        ).first()

        dest_before = alloc.destination_id
        status_before = alloc.allocation_status
        audit_count_before = db.query(AuditEvent).count()

        # Deliberately submit invalid override (nonexistent destination)
        res = client.post("/api/v1/relocation/override", json={
            "allocation_id": alloc.id,
            "new_destination_id": "DEST_DOES_NOT_EXIST",
            "justification": "Invalid test"
        })
        assert res.status_code == 404
        assert "DESTINATION_NOT_FOUND" in res.json().get("detail", "")

        # Verify zero database mutation
        db.refresh(alloc)
        assert alloc.destination_id == dest_before
        assert alloc.allocation_status == status_before
        assert db.query(AuditEvent).count() == audit_count_before
    finally:
        db.close()


def test_8_successful_override_creates_audit_event(scenario_context):
    """TEST 8: Successful override creates the expected audit event with before/after state."""
    scen_snap_id = scenario_context["scenario_snapshot_id"]
    db = SessionLocal()
    try:
        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == scen_snap_id
        ).first()

        dest_02 = db.query(Destination).filter(Destination.code == "DEST_02").first()
        dest_03 = db.query(Destination).filter(Destination.code == "DEST_03").first()
        target = dest_03 if alloc.destination_id == dest_02.id else dest_02

        unique_justification = f"LEGAL_COMMAND_ORDER_TEST_8_{scen_snap_id[:8]}"

        res = client.post("/api/v1/relocation/override", json={
            "allocation_id": alloc.id,
            "new_destination_id": target.id,
            "justification": unique_justification
        })
        assert res.status_code == 200

        # Query audit event table
        audit = db.query(AuditEvent).filter(
            AuditEvent.entity_id == alloc.id,
            AuditEvent.justification == unique_justification
        ).first()

        assert audit is not None
        assert audit.action_type == "AUTHORITY_ALLOCATION_OVERRIDE"
        assert audit.entity_type == "RELOCATION_ALLOCATION"
        assert "destination_id" in audit.before_state
        assert "destination_id" in audit.after_state
        assert audit.after_state["destination_id"] == target.id
        assert audit.created_at is not None
    finally:
        db.close()


def test_9_disconnected_graph_route_rejected(scenario_context):
    """TEST 9: Disconnected graph/no viable route is rejected."""
    scen_snap_id = scenario_context["scenario_snapshot_id"]
    db = SessionLocal()
    try:
        # HAB_03 to DEST_02 has no viable route under MONSOON_SURGE_01
        hab_03 = db.query(Habitation).filter(Habitation.code == "HAB_03").first()
        dest_02 = db.query(Destination).filter(Destination.code == "DEST_02").first()

        group = db.query(RelocationGroup).filter(
            RelocationGroup.habitation_id == hab_03.id,
            RelocationGroup.snapshot_id == scen_snap_id
        ).first()

        alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.group_id == group.id,
            RelocationAllocation.snapshot_id == scen_snap_id
        ).first()

        res = client.post("/api/v1/relocation/override", json={
            "allocation_id": alloc.id,
            "new_destination_id": dest_02.id,
            "justification": "Attempt to cross disconnected network"
        })
        assert res.status_code == 400
        assert "NO_VIABLE_ROUTE" in res.json().get("detail", "")
    finally:
        db.close()


def test_10_repeated_invalid_override_idempotence():
    """TEST 10: Repeated execution of the same invalid override does not partially corrupt state."""
    db = SessionLocal()
    try:
        base_alloc = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).first()
        dest_02 = db.query(Destination).filter(Destination.code == "DEST_02").first()

        # Execute 5 consecutive invalid overrides against SNAP_BASE_001
        for _ in range(5):
            res = client.post("/api/v1/relocation/override", json={
                "allocation_id": base_alloc.id,
                "new_destination_id": dest_02.id,
                "justification": "REPEATED_ATTEMPT_BASELINE_MUTATION"
            })
            assert res.status_code == 400
            assert "BASELINE_IMMUTABLE" in res.json().get("detail", "")

        # Verify state is completely uncorrupted
        db.refresh(base_alloc)
        assert base_alloc.allocation_status != AllocationStatusEnum.OVERRIDDEN
        assert base_alloc.destination_id != dest_02.id
    finally:
        db.close()
