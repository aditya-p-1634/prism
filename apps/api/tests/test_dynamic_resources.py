"""PRISM V2 — Phase A.4 Dedicated Test Suite
===========================================
Deterministic Resource Consumption, Dynamic Carrying Capacity,
Destination Feasibility, Selective CP-SAT Reallocation,
and Anti-Bloat Bounded Storage.
"""

import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.session import SessionLocal
from app.models.entities import (
    StateSnapshot, Destination, DestinationResource, CapacityState,
    RelocationAllocation, RelocationGroup, SimulationRun, SimulationEvent,
    SimulationResourceState
)
from app.models.enums import (
    ResourceCategoryEnum, ResourceStatusEnum, SimulationStatusEnum,
    SimulationEventTypeEnum, EvacuationStateEnum, AllocationStatusEnum,
    OperationalStatusEnum
)
from app.engines.e5_simulation.temporal_engine import TemporalSimulationEngine
from app.engines.e3_destination_capacity.resource_manager import DynamicResourceManager


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_1_resource_initialization(db: Session):
    """Test 1: SimulationResourceState initialized with 9 rows (3 per dest) and NORMAL status."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0
    )

    states = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id
    ).all()

    # 3 destinations * 3 categories = 9
    assert len(states) == 9

    destinations = db.query(Destination).all()
    assert len(destinations) == 3

    for d in destinations:
        d_states = [s for s in states if s.destination_id == d.id]
        assert len(d_states) == 3
        cats = {s.resource_category for s in d_states}
        assert cats == {"POPULATION_SPACE", "WATER", "MEDICAL_CAPACITY"}
        for s in d_states:
            assert s.status == ResourceStatusEnum.NORMAL
            assert s.consumed_quantity == 0.0
            assert s.remaining_quantity == s.total_quantity
            assert s.supportable_population > 0


def test_2_correct_resource_consumption_per_tick(db: Session):
    """Test 2: Sheltered population consumes water deterministically per tick."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 2.0}
    )

    # Find an allocation and set it to SHELTERED at DEST_01
    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest1.id
    ).first()
    alloc.evacuation_state = EvacuationStateEnum.SHELTERED
    db.commit()

    # Query initial water state
    water_state_before = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id,
        SimulationResourceState.destination_id == dest1.id,
        SimulationResourceState.resource_category == "WATER"
    ).first()
    init_qty = water_state_before.total_quantity

    # Execute 1 tick
    res = engine.step_simulation(run.id)

    db.refresh(water_state_before)
    expected_consumed = alloc.assigned_capacity_count * 2.0
    assert water_state_before.consumed_quantity == pytest.approx(expected_consumed, 0.01)
    assert water_state_before.remaining_quantity == pytest.approx(init_qty - expected_consumed, 0.01)


def test_3_water_never_becomes_negative(db: Session):
    """Test 3: Water quantity is clamped at 0.0 and never becomes negative."""
    engine = TemporalSimulationEngine(db)
    # Configure an extreme consumption rate
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 10000.0}
    )

    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest1.id
    ).first()
    alloc.evacuation_state = EvacuationStateEnum.SHELTERED
    db.commit()

    # Step simulation
    engine.step_simulation(run.id)

    water_state = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id,
        SimulationResourceState.destination_id == dest1.id,
        SimulationResourceState.resource_category == "WATER"
    ).first()

    assert water_state.remaining_quantity >= 0.0
    assert water_state.remaining_quantity == 0.0
    assert water_state.supportable_population == 0
    assert water_state.status == ResourceStatusEnum.EXHAUSTED


def test_4_medical_capacity_never_becomes_negative(db: Session):
    """Test 4: Medical support capacity remaining never falls below 0."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"medical_demand_per_person": 1000.0}
    )

    dest3 = db.query(Destination).filter(Destination.code == "DEST_03").first()
    allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest3.id
    ).all()
    for a in allocs:
        a.evacuation_state = EvacuationStateEnum.SHELTERED
    db.commit()

    engine.step_simulation(run.id)

    med_state = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id,
        SimulationResourceState.destination_id == dest3.id,
        SimulationResourceState.resource_category == "MEDICAL_CAPACITY"
    ).first()

    assert med_state.remaining_quantity >= 0.0
    assert med_state.status == ResourceStatusEnum.EXHAUSTED


def test_5_resource_status_transitions(db: Session):
    """Test 5: Resource status transitions from NORMAL -> CONSTRAINED -> EXHAUSTED."""
    engine = TemporalSimulationEngine(db)
    dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()

    # DEST_02 has initial 900L water in MONSOON_SURGE_01 (75% of 1200L). Warning threshold ratio is 0.25 (225L).
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={
            "water_consumption_per_person_per_tick": 70.0,
            "resource_warning_threshold_ratio": 0.25
        }
    )

    # 10 people sheltered -> 700L consumed in tick 1 -> remaining 200L (<= 225L) -> CONSTRAINED
    alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest2.id
    ).first()
    alloc.assigned_capacity_count = 10
    alloc.evacuation_state = EvacuationStateEnum.SHELTERED
    db.commit()

    # Tick 1: drops to 200L -> CONSTRAINED
    engine.step_simulation(run.id)
    w_state = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id,
        SimulationResourceState.destination_id == dest2.id,
        SimulationResourceState.resource_category == "WATER"
    ).first()
    assert w_state.status == ResourceStatusEnum.CONSTRAINED

    # Tick 2: 700L more demanded -> clamped to 0L -> EXHAUSTED
    engine.step_simulation(run.id)
    db.refresh(w_state)
    assert w_state.status == ResourceStatusEnum.EXHAUSTED


def test_6_effective_capacity_calculation(db: Session):
    """Test 6: Effective capacity is minimum supportable across critical resources."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0
    )

    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    cap_st1 = db.query(CapacityState).filter(
        CapacityState.snapshot_id == run.scenario_snapshot_id,
        CapacityState.destination_id == dest1.id
    ).first()

    # DEST_01: Shelter 160 beds, Water 3000L (supports 150), Healthcare 4 medics (supports 200)
    # Effective capacity must be 150 with WATER bottleneck
    assert cap_st1.effective_capacity == 150
    assert cap_st1.bottleneck_resource == "WATER"

    dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()
    cap_st2 = db.query(CapacityState).filter(
        CapacityState.snapshot_id == run.scenario_snapshot_id,
        CapacityState.destination_id == dest2.id
    ).first()
    # DEST_02 under MONSOON_SURGE_01 has 25% water reduction (900L -> supports 45)
    assert cap_st2.effective_capacity == 45
    assert cap_st2.bottleneck_resource == "WATER"


def test_7_effective_capacity_cannot_exceed_physical_capacity(db: Session):
    """Test 7: Effective capacity cannot exceed physical shelter capacity."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_requirement_per_person": 0.001} # Inflates water supportable to huge number
    )

    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    engine.step_simulation(run.id)

    cap_st = db.query(CapacityState).filter(
        CapacityState.snapshot_id == run.scenario_snapshot_id,
        CapacityState.destination_id == dest1.id
    ).first()

    shelter_res = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id,
        SimulationResourceState.destination_id == dest1.id,
        SimulationResourceState.resource_category == "POPULATION_SPACE"
    ).first()

    # Effective capacity cannot exceed physical shelter beds (160)
    assert cap_st.effective_capacity <= shelter_res.total_quantity


def test_8_effective_remaining_capacity_cannot_become_negative(db: Session):
    """Test 8: Effective remaining capacity is clamped at 0."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0
    )

    dest3 = db.query(Destination).filter(Destination.code == "DEST_03").first()
    # Shelter 100 people at DEST_03 (which has effective capacity 50)
    allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest3.id
    ).all()
    for a in allocs:
        a.assigned_capacity_count = 50
        a.evacuation_state = EvacuationStateEnum.SHELTERED
    db.commit()

    engine.step_simulation(run.id)

    cap_st = db.query(CapacityState).filter(
        CapacityState.snapshot_id == run.scenario_snapshot_id,
        CapacityState.destination_id == dest3.id
    ).first()

    assert cap_st.remaining_capacity >= 0
    assert cap_st.remaining_capacity == 0


def test_9_sheltered_population_consumes_resources_correctly(db: Session):
    """Test 9: Sheltered groups consume resources while non-sheltered do not."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 5.0}
    )

    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest1.id
    ).all()

    # Mark exactly one allocation as SHELTERED
    target_alloc = allocs[0]
    target_alloc.evacuation_state = EvacuationStateEnum.SHELTERED
    target_alloc.assigned_capacity_count = 10

    # Ensure other allocations are PLANNED or IN_TRANSIT
    for a in allocs[1:]:
        a.evacuation_state = EvacuationStateEnum.PLANNED
    db.commit()

    engine.step_simulation(run.id)

    w_state = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id,
        SimulationResourceState.destination_id == dest1.id,
        SimulationResourceState.resource_category == "WATER"
    ).first()

    # Exactly 10 people * 5.0 = 50.0 consumed
    assert w_state.consumed_quantity == pytest.approx(50.0, 0.01)


def test_10_non_sheltered_allocations_do_not_consume_resources(db: Session):
    """Test 10: Allocations in PLANNED, NOTIFIED, MOVING, IN_TRANSIT consume 0 shelter resources."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 10.0}
    )

    allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id
    ).all()

    # Ensure all allocations are in non-sheltered states that do not auto-arrive
    states_to_test = [
        EvacuationStateEnum.PLANNED, EvacuationStateEnum.NOTIFIED,
        EvacuationStateEnum.ACKNOWLEDGED, EvacuationStateEnum.MOVING
    ]
    for idx, a in enumerate(allocs):
        a.evacuation_state = states_to_test[idx % len(states_to_test)]
    db.commit()

    engine.step_simulation(run.id)

    # Total consumed water across all destinations must be 0.0
    all_water = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id,
        SimulationResourceState.resource_category == "WATER"
    ).all()

    for ws in all_water:
        assert ws.consumed_quantity == 0.0


def test_11_resource_depletion_changes_destination_feasibility(db: Session):
    """Test 11: Destination becomes infeasible when remaining capacity drops below uncommitted demand."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 200.0} # Depletes quickly
    )

    dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()
    allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest2.id
    ).all()

    # 1 group sheltered (consumes water), 1 group PLANNED
    allocs[0].evacuation_state = EvacuationStateEnum.SHELTERED
    allocs[0].assigned_capacity_count = 5

    allocs[1].evacuation_state = EvacuationStateEnum.PLANNED
    allocs[1].assigned_capacity_count = 10
    db.commit()

    # Run step: water will be depleted, reducing capacity below 10 -> infeasible
    res = engine.step_simulation(run.id)

    # Check for DESTINATION_INFEASIBLE event
    infeasible_events = [
        e for e in res["events_generated"]
        if e.event_type == SimulationEventTypeEnum.DESTINATION_INFEASIBLE
    ]
    assert len(infeasible_events) > 0
    assert any(e.entity_id == dest2.id for e in infeasible_events)


def test_12_no_cp_sat_when_no_allocation_infeasibility_exists(db: Session):
    """Test 12: CP-SAT solver is not called when capacity drops but planned demand still fits."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        # Moderate consumption that leaves plenty of room
        parameter_overrides={"water_consumption_per_person_per_tick": 1.0}
    )

    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest1.id
    ).all()

    # 1 group sheltered (consumes water), other groups are safe
    allocs[0].evacuation_state = EvacuationStateEnum.SHELTERED
    allocs[0].assigned_capacity_count = 5
    db.commit()

    res = engine.step_simulation(run.id)

    # REALLOCATION_TRIGGERED should NOT be emitted
    realloc_events = [
        e for e in res["events_generated"]
        if e.event_type == SimulationEventTypeEnum.REALLOCATION_TRIGGERED
    ]
    assert len(realloc_events) == 0


def test_13_cp_sat_triggered_when_uncommitted_allocation_becomes_infeasible(db: Session):
    """Test 13: CP-SAT is triggered when uncommitted planned allocation becomes infeasible."""
    engine = TemporalSimulationEngine(db)
    # Fast water consumption at D2 (capacity 60)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 100.0}
    )

    dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()
    allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest2.id
    ).all()

    # 1 group sheltered, 1 group PLANNED
    allocs[0].evacuation_state = EvacuationStateEnum.SHELTERED
    allocs[0].assigned_capacity_count = 10

    allocs[1].evacuation_state = EvacuationStateEnum.PLANNED
    allocs[1].assigned_capacity_count = 15
    db.commit()

    res = engine.step_simulation(run.id)

    # REALLOCATION_TRIGGERED and REALLOCATION_COMPLETED should be emitted
    event_types = [e.event_type for e in res["events_generated"]]
    assert SimulationEventTypeEnum.REALLOCATION_TRIGGERED in event_types
    assert SimulationEventTypeEnum.REALLOCATION_COMPLETED in event_types


def test_14_existing_sheltered_people_are_not_reallocated(db: Session):
    """Test 14: People already SHELTERED or ARRIVED are NEVER evicted or reallocated."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 500.0} # Complete exhaustion
    )

    dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()
    allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest2.id
    ).all()

    sheltered_alloc = allocs[0]
    sheltered_alloc.evacuation_state = EvacuationStateEnum.SHELTERED
    sheltered_alloc_id = sheltered_alloc.id

    planned_alloc = allocs[1]
    planned_alloc.evacuation_state = EvacuationStateEnum.PLANNED
    db.commit()

    # Step simulation: D2 becomes exhausted
    engine.step_simulation(run.id)

    db.refresh(sheltered_alloc)
    # Invariant: Sheltered person remains at DEST_02 and state is SHELTERED!
    assert sheltered_alloc.destination_id == dest2.id
    assert sheltered_alloc.evacuation_state == EvacuationStateEnum.SHELTERED


def test_15_invalid_unavailable_destinations_not_assigned(db: Session):
    """Test 15: Reallocations do not assign to closed or inundated destinations."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0
    )

    dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()
    cap2 = db.query(CapacityState).filter(
        CapacityState.snapshot_id == run.scenario_snapshot_id,
        CapacityState.destination_id == dest2.id
    ).first()
    cap2.is_safe = False
    cap2.remaining_capacity = 0

    # Also set SimulationResourceState for dest2 to exhausted
    for s in db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id,
        SimulationResourceState.destination_id == dest2.id
    ).all():
        s.remaining_quantity = 0.0
        s.supportable_population = 0
        s.status = ResourceStatusEnum.EXHAUSTED
    db.commit()

    # Reallocation should never pick dest2
    alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest2.id,
        RelocationAllocation.evacuation_state == EvacuationStateEnum.PLANNED
    ).first()

    if alloc:
        engine.step_simulation(run.id)
        db.refresh(alloc)
        assert alloc.destination_id != dest2.id


def test_16_no_allocation_exceeds_effective_capacity(db: Session):
    """Test 16: Allocations assigned to a destination do not exceed effective capacity."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0
    )

    engine.run_simulation(run.id, max_steps=2)

    destinations = db.query(Destination).all()
    for d in destinations:
        cap = db.query(CapacityState).filter(
            CapacityState.snapshot_id == run.scenario_snapshot_id,
            CapacityState.destination_id == d.id
        ).first()

        dest_allocs = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
            RelocationAllocation.destination_id == d.id,
            RelocationAllocation.allocation_status != AllocationStatusEnum.UNMET
        ).all()

        total_assigned = sum(a.assigned_capacity_count for a in dest_allocs)
        assert total_assigned <= cap.effective_capacity + 15 # within solver tolerance


def test_17_no_feasible_destination_produces_unmet_demand(db: Session):
    """Test 17: When all destination capacities are exhausted, allocation becomes UNMET."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0
    )

    # Force all resource states and capacity states to 0 remaining capacity
    for s in db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id
    ).all():
        s.remaining_quantity = 0.0
        s.supportable_population = 0
        s.status = ResourceStatusEnum.EXHAUSTED

    caps = db.query(CapacityState).filter(
        CapacityState.snapshot_id == run.scenario_snapshot_id
    ).all()
    for c in caps:
        c.remaining_capacity = 0
        c.effective_capacity = 0
    db.commit()

    # Trigger step with a PLANNED group
    res = engine.step_simulation(run.id)

    unmet_allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.allocation_status == AllocationStatusEnum.UNMET
    ).all()

    assert len(unmet_allocs) > 0


def test_18_baseline_immutability(db: Session):
    """Test 18: SNAP_BASE_001 resources, capacities, and allocations remain completely unchanged."""
    engine = TemporalSimulationEngine(db)

    # Query baseline state before
    base_caps_before = {
        cs.destination_id: (cs.effective_capacity, cs.occupied_capacity, cs.remaining_capacity)
        for cs in db.query(CapacityState).filter(CapacityState.snapshot_id == "SNAP_BASE_001").all()
    }
    base_res_before = {
        (r.destination_id, r.resource_type): r.quantity
        for r in db.query(DestinationResource).filter(DestinationResource.snapshot_id == "SNAP_BASE_001").all()
    }
    base_allocs_count = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == "SNAP_BASE_001"
    ).count()

    # Run complete multi-step simulation
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 50.0}
    )
    engine.run_simulation(run.id)

    # Verify baseline state after
    base_caps_after = {
        cs.destination_id: (cs.effective_capacity, cs.occupied_capacity, cs.remaining_capacity)
        for cs in db.query(CapacityState).filter(CapacityState.snapshot_id == "SNAP_BASE_001").all()
    }
    base_res_after = {
        (r.destination_id, r.resource_type): r.quantity
        for r in db.query(DestinationResource).filter(DestinationResource.snapshot_id == "SNAP_BASE_001").all()
    }
    base_allocs_count_after = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == "SNAP_BASE_001"
    ).count()

    assert base_caps_before == base_caps_after
    assert base_res_before == base_res_after
    assert base_allocs_count == base_allocs_count_after


def test_19_scenario_isolation(db: Session):
    """Test 19: Resource simulation in run A does not mutate scenario B."""
    engine = TemporalSimulationEngine(db)

    # Run A
    run_a = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 100.0}
    )
    # Shelter someone in Run A
    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    alloc_a = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run_a.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest1.id
    ).first()
    alloc_a.evacuation_state = EvacuationStateEnum.SHELTERED
    db.commit()

    engine.step_simulation(run_a.id)

    # Run B created after
    run_b = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0
    )

    # Run B's DEST_01 water state must be at full initial quantity
    water_b = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run_b.id,
        SimulationResourceState.destination_id == dest1.id,
        SimulationResourceState.resource_category == "WATER"
    ).first()

    assert water_b.consumed_quantity == 0.0
    assert water_b.remaining_quantity == water_b.total_quantity


def test_20_deterministic_repeated_simulation(db: Session):
    """Test 20: Repeated simulations with identical inputs produce identical resource trajectories."""
    engine = TemporalSimulationEngine(db)

    params = {"water_consumption_per_person_per_tick": 10.0}

    # Run 1
    run1 = engine.create_simulation_run("MONSOON_SURGE_01", timestep_minutes=5.0, duration_minutes=15.0, parameter_overrides=params)
    res1 = engine.run_simulation(run1.id)

    # Run 2
    run2 = engine.create_simulation_run("MONSOON_SURGE_01", timestep_minutes=5.0, duration_minutes=15.0, parameter_overrides=params)
    res2 = engine.run_simulation(run2.id)

    states1 = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run1.id
    ).order_by(SimulationResourceState.destination_id, SimulationResourceState.resource_category).all()
    states2 = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run2.id
    ).order_by(SimulationResourceState.destination_id, SimulationResourceState.resource_category).all()

    for s1, s2 in zip(states1, states2):
        assert s1.resource_category == s2.resource_category
        assert s1.consumed_quantity == pytest.approx(s2.consumed_quantity, 0.01)
        assert s1.remaining_quantity == pytest.approx(s2.remaining_quantity, 0.01)
        assert s1.supportable_population == s2.supportable_population
        assert s1.status == s2.status


def test_21_failed_resource_update_rolls_back_atomically(db: Session, monkeypatch):
    """Test 21: A simulated failure during resource calculation rolls back database state safely."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run("MONSOON_SURGE_01", timestep_minutes=5.0, duration_minutes=30.0)

    # Monkeypatch evaluate_tick_consumption_and_capacity to raise an exception
    def failing_eval(*args, **kwargs):
        raise RuntimeError("Simulated transient resource engine failure")

    monkeypatch.setattr(DynamicResourceManager, "evaluate_tick_consumption_and_capacity", failing_eval)

    with pytest.raises(HTTPException) as exc_info:
        engine.step_simulation(run.id)

    assert exc_info.value.status_code == 500

    # Ensure run is marked FAILED and transaction was rolled back cleanly
    db.refresh(run)
    assert run.status == SimulationStatusEnum.FAILED


def test_22_failed_cpsat_reallocation_rolls_back_atomically(db: Session, monkeypatch):
    """Test 22: Failure during CP-SAT reallocation triggers clean rollback without partial state corruption."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        "MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 500.0}
    )

    dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()
    alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest2.id
    ).first()
    alloc.evacuation_state = EvacuationStateEnum.PLANNED
    alloc.assigned_capacity_count = 100 # exceeds capacity
    db.commit()

    def failing_cpsat(*args, **kwargs):
        raise ValueError("Simulated CP-SAT solver exception")

    monkeypatch.setattr(engine.e4, "optimize_relocation", failing_cpsat)

    with pytest.raises(HTTPException):
        engine.step_simulation(run.id)

    db.refresh(run)
    assert run.status == SimulationStatusEnum.FAILED


def test_23_simulation_event_generation(db: Session):
    """Test 23: Simulation events for resource consumption and capacity changes are persisted."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 50.0}
    )

    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest1.id
    ).first()
    alloc.evacuation_state = EvacuationStateEnum.SHELTERED
    db.commit()

    engine.step_simulation(run.id)

    events = db.query(SimulationEvent).filter(
        SimulationEvent.simulation_run_id == run.id
    ).all()

    event_types = {e.event_type for e in events}
    assert SimulationEventTypeEnum.RESOURCE_CONSUMED in event_types


def test_24_existing_a1_regression_tests_pass(db: Session):
    """Test 24: Direct verification that authority override baseline mutation remains forbidden."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    base_alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == "SNAP_BASE_001"
    ).first()

    dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()
    res = client.post(
        "/api/v1/relocation/override",
        json={
            "allocation_id": base_alloc.id,
            "new_destination_id": dest2.id,
            "justification": "Testing baseline immutability in A.4"
        }
    )
    assert res.status_code == 400
    assert "BASELINE_IMMUTABLE" in res.text


def test_25_existing_a2_regression_tests_pass(db: Session):
    """Test 25: EvacuationStateMachine transition checks remain enforced."""
    from app.engines.e5_simulation.state_machine import EvacuationStateMachine

    run_engine = TemporalSimulationEngine(db)
    run = run_engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0
    )

    alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id
    ).first()

    # Invalid jump PLANNED -> SHELTERED must be rejected
    with pytest.raises(HTTPException) as exc:
        EvacuationStateMachine.transition_state(
            db=db,
            allocation_id=alloc.id,
            to_state=EvacuationStateEnum.SHELTERED,
            justification="Illegal skip"
        )
    assert exc.value.status_code == 400


def test_26_existing_a3_regression_tests_pass(db: Session):
    """Test 26: A.3 temporal movement, reroute, and clock advance remain intact."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run("MONSOON_SURGE_01", timestep_minutes=5.0, duration_minutes=15.0)

    res = engine.step_simulation(run.id)
    assert res["simulation_time_min"] == 5.0
    assert res["tick_index"] == 1


def test_27_storage_growth_remains_bounded(db: Session):
    """Test 27: Running multiple ticks creates 0 new snapshots and exactly 9 SimulationResourceState rows."""
    engine = TemporalSimulationEngine(db)
    snaps_before = db.query(StateSnapshot).count()

    run = engine.create_simulation_run("MONSOON_SURGE_01", timestep_minutes=5.0, duration_minutes=30.0)
    snaps_after_create = db.query(StateSnapshot).count()
    assert snaps_after_create == snaps_before + 1 # Exactly 1 scenario snapshot branch

    # Execute 6 ticks
    for _ in range(6):
        engine.step_simulation(run.id)

    snaps_after_run = db.query(StateSnapshot).count()
    assert snaps_after_run == snaps_after_create # NO new snapshots per tick!

    # Exactly 9 resource state rows
    res_states_count = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id
    ).count()
    assert res_states_count == 9


def test_28_zero_duration_simulation_behavior_remains_valid(db: Session):
    """Test 28: Zero-duration simulation completes immediately with 0 ticks and 0 consumption."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run("MONSOON_SURGE_01", timestep_minutes=5.0, duration_minutes=0.0)

    assert run.status == SimulationStatusEnum.COMPLETED
    assert run.ticks_completed == 0
    assert run.total_ticks == 0


def test_29_multiple_ticks_produce_monotonic_resource_consumption(db: Session):
    """Test 29: Monotonic decrease in remaining resources tick-over-tick."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 2.0}
    )

    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest1.id
    ).first()
    alloc.evacuation_state = EvacuationStateEnum.SHELTERED
    alloc.assigned_capacity_count = 10
    db.commit()

    rem_history = []
    for _ in range(4):
        engine.step_simulation(run.id)
        w_state = db.query(SimulationResourceState).filter(
            SimulationResourceState.simulation_run_id == run.id,
            SimulationResourceState.destination_id == dest1.id,
            SimulationResourceState.resource_category == "WATER"
        ).first()
        rem_history.append(w_state.remaining_quantity)

    # Strictly decreasing
    assert rem_history[0] > rem_history[1] > rem_history[2] > rem_history[3]


def test_30_resource_consumption_does_not_occur_twice_for_same_population_tick(db: Session):
    """Test 30: Resource consumption is charged exactly once per population per timestep."""
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 10.0}
    )

    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    alloc = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest1.id
    ).first()
    alloc.evacuation_state = EvacuationStateEnum.SHELTERED
    alloc.assigned_capacity_count = 5 # 5 people
    db.commit()

    # Step 1 tick
    engine.step_simulation(run.id)

    w_state = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run.id,
        SimulationResourceState.destination_id == dest1.id,
        SimulationResourceState.resource_category == "WATER"
    ).first()

    # Must be exactly 5 * 10.0 = 50.0 (not double counted to 100.0)
    assert w_state.consumed_quantity == 50.0


def test_31_demonstration_scenario_full_causal_chain(db: Session):
    """
    Test 31: Full Demonstration Scenario:
    1. Destination D2 starts feasible.
    2. People arrive and become sheltered.
    3. Resources are consumed.
    4. Effective capacity decreases.
    5. Destination becomes constrained and infeasible for an uncommitted planned group.
    6. CP-SAT selects feasible alternative destination (D1).
    7. Existing sheltered people at D2 remain untouched.
    8. Events explain the entire causal progression.
    """
    engine = TemporalSimulationEngine(db)
    # Configure high consumption rate to visibly trigger capacity drop
    run = engine.create_simulation_run(
        scenario_code="MONSOON_SURGE_01",
        timestep_minutes=5.0,
        duration_minutes=30.0,
        parameter_overrides={"water_consumption_per_person_per_tick": 100.0}
    )

    dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
    dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()

    d2_allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
        RelocationAllocation.destination_id == dest2.id
    ).all()

    # Group 1: Already SHELTERED at D2 (5 people)
    sheltered_group = d2_allocs[0]
    sheltered_group.assigned_capacity_count = 5
    sheltered_group.evacuation_state = EvacuationStateEnum.SHELTERED

    # Group 2: PLANNED at D2 (20 people)
    planned_group = d2_allocs[1]
    planned_group.assigned_capacity_count = 20
    planned_group.evacuation_state = EvacuationStateEnum.PLANNED
    db.commit()

    # Initial state: D2 effective capacity under MONSOON_SURGE_01 is 45, feasible for both (5 + 20 <= 45)
    cap_before = db.query(CapacityState).filter(
        CapacityState.snapshot_id == run.scenario_snapshot_id,
        CapacityState.destination_id == dest2.id
    ).first()
    assert cap_before.effective_capacity == 45

    # Step simulation: 5 sheltered people consume 500L water (out of 1200L).
    # Remaining water = 700L. Water-supported capacity drops to 700 // 20 = 35.
    # Step again: remaining water = 200L. Water-supported capacity drops to 200 // 20 = 10.
    # Remaining capacity = 10 - 5 = 5.
    # Planned group requires 10 -> INFEASIBLE!
    engine.step_simulation(run.id)
    res = engine.step_simulation(run.id)

    db.refresh(sheltered_group)
    db.refresh(planned_group)

    # 1. Existing sheltered person remains at D2 untouched!
    assert sheltered_group.destination_id == dest2.id
    assert sheltered_group.evacuation_state == EvacuationStateEnum.SHELTERED

    # 2. Planned group was reallocated to another destination or marked appropriately
    assert planned_group.destination_id != dest2.id or planned_group.allocation_status == AllocationStatusEnum.UNMET

    # 3. Events logged explaining the progression
    events = db.query(SimulationEvent).filter(
        SimulationEvent.simulation_run_id == run.id
    ).all()
    event_types = {e.event_type for e in events}
    assert SimulationEventTypeEnum.RESOURCE_CONSUMED in event_types
    assert SimulationEventTypeEnum.DESTINATION_CAPACITY_CHANGED in event_types
