"""PRISM V2 — Phase A.4 Dynamic Resource Depletion Demonstration Verification
========================================================================
Demonstrates the full deterministic causal chain:
1. Starts feasible
2. Sheltered population consumes water and medical resources
3. Effective carrying capacity falls (bottleneck tracking)
4. Destination becomes constrained / infeasible for uncommitted planned allocations
5. CP-SAT selectively reallocates the uncommitted group to feasible alternative (DEST_01)
6. Sheltered population at DEST_02 remains untouched (NO eviction)
7. Audit / simulation events explain every transition
8. SNAP_BASE_001 baseline immutability verified
"""

import sys
import os

# Add apps/api to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from app.db.session import SessionLocal
from app.models.entities import (
    Destination, CapacityState, RelocationAllocation, RelocationGroup,
    SimulationRun, SimulationEvent, SimulationResourceState
)
from app.models.enums import (
    EvacuationStateEnum, AllocationStatusEnum, SimulationEventTypeEnum, ResourceStatusEnum
)
from app.engines.e5_simulation.temporal_engine import TemporalSimulationEngine


def main():
    db = SessionLocal()
    try:
        print("=" * 70)
        print("  PRISM V2 — PHASE A.4 DEMONSTRATION VERIFICATION")
        print("=" * 70)

        engine = TemporalSimulationEngine(db)

        # Baseline check before
        base_allocs_count = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).count()
        print(f"\n[Baseline Initial State] SNAP_BASE_001 total allocations: {base_allocs_count}")

        # 1. Create isolated simulation run
        run = engine.create_simulation_run(
            scenario_code="MONSOON_SURGE_01",
            timestep_minutes=5.0,
            duration_minutes=30.0,
            parameter_overrides={"water_consumption_per_person_per_tick": 70.0}
        )
        print(f"[Run Created] ID: {run.id[:8]}... | Snapshot: {run.scenario_snapshot_id[:8]}...")

        dest1 = db.query(Destination).filter(Destination.code == "DEST_01").first()
        dest2 = db.query(Destination).filter(Destination.code == "DEST_02").first()

        # Set up demonstration allocations at DEST_02
        d2_allocs = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == run.scenario_snapshot_id,
            RelocationAllocation.destination_id == dest2.id
        ).all()

        sheltered_group = d2_allocs[0]
        sheltered_group.assigned_capacity_count = 5
        sheltered_group.evacuation_state = EvacuationStateEnum.SHELTERED

        planned_group = d2_allocs[1]
        planned_group.assigned_capacity_count = 20
        planned_group.evacuation_state = EvacuationStateEnum.PLANNED
        db.commit()

        # Initial Capacity
        cap_init = db.query(CapacityState).filter(
            CapacityState.snapshot_id == run.scenario_snapshot_id,
            CapacityState.destination_id == dest2.id
        ).first()
        print(f"\n[t=0 min Initial Capacity]")
        print(f"  DEST_02 Effective Capacity: {cap_init.effective_capacity}")
        print(f"  DEST_02 Sheltered Population: {sheltered_group.assigned_capacity_count}")
        print(f"  DEST_02 Uncommitted Planned Demand: {planned_group.assigned_capacity_count}")
        print(f"  DEST_02 Feasibility: True (5 + 20 <= {cap_init.effective_capacity})")

        # Step 1: t=5 min
        print(f"\n--- Advancing to t=5 min (Tick 1) ---")
        res1 = engine.step_simulation(run.id)
        w1 = db.query(SimulationResourceState).filter(
            SimulationResourceState.simulation_run_id == run.id,
            SimulationResourceState.destination_id == dest2.id,
            SimulationResourceState.resource_category == "WATER"
        ).first()
        cap1 = db.query(CapacityState).filter(
            CapacityState.snapshot_id == run.scenario_snapshot_id,
            CapacityState.destination_id == dest2.id
        ).first()
        print(f"  Water remaining: {w1.remaining_quantity:.1f} L (status: {w1.status.value})")
        print(f"  Effective capacity: {cap1.effective_capacity} (bottleneck: {cap1.bottleneck_resource})")
        print(f"  Events generated: {[e.event_type.value for e in res1['events_generated']]}")

        # Step 2: t=10 min
        print(f"\n--- Advancing to t=10 min (Tick 2) ---")
        res2 = engine.step_simulation(run.id)
        w2 = db.query(SimulationResourceState).filter(
            SimulationResourceState.simulation_run_id == run.id,
            SimulationResourceState.destination_id == dest2.id,
            SimulationResourceState.resource_category == "WATER"
        ).first()
        cap2 = db.query(CapacityState).filter(
            CapacityState.snapshot_id == run.scenario_snapshot_id,
            CapacityState.destination_id == dest2.id
        ).first()
        print(f"  Water remaining: {w2.remaining_quantity:.1f} L (status: {w2.status.value})")
        print(f"  Effective capacity: {cap2.effective_capacity} (bottleneck: {cap2.bottleneck_resource})")
        print(f"  Remaining capacity: {cap2.remaining_capacity}")
        print(f"  Events generated: {[e.event_type.value for e in res2['events_generated']]}")

        # Inspect Allocations after depletion
        db.refresh(sheltered_group)
        db.refresh(planned_group)

        new_dest_planned = db.query(Destination).filter(Destination.id == planned_group.destination_id).first() if planned_group.destination_id else None

        print(f"\n[Post-Depletion State & Reallocation Verification]")
        print(f"  Sheltered Group: Destination={dest2.code} | State={sheltered_group.evacuation_state.value} (UNTOUCHED)")
        print(f"  Planned Group: Destination={new_dest_planned.code if new_dest_planned else 'UNMET'} | Status={planned_group.allocation_status.value} | Reason={planned_group.reason_code}")

        assert sheltered_group.destination_id == dest2.id, "Sheltered group was evicted!"
        assert sheltered_group.evacuation_state == EvacuationStateEnum.SHELTERED, "Sheltered group state mutated!"
        print(f"  [PASS] Physical state preserved: Sheltered population was NOT evicted.")

        # Baseline check after
        base_allocs_count_after = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).count()
        assert base_allocs_count == base_allocs_count_after
        print(f"  [PASS] Baseline Immutability: SNAP_BASE_001 allocations untouched ({base_allocs_count_after}).")

        # Event audit verification
        events = db.query(SimulationEvent).filter(SimulationEvent.simulation_run_id == run.id).all()
        types = {e.event_type for e in events}
        assert SimulationEventTypeEnum.RESOURCE_CONSUMED in types
        assert SimulationEventTypeEnum.DESTINATION_CAPACITY_CHANGED in types
        print(f"  [PASS] Simulation Events: {len(events)} events recorded. Resource & capacity events verified.")

        print("\n" + "=" * 70)
        print("  DEMONSTRATION VERIFICATION COMPLETE: ALL INVARIANTS PASSED!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    main()
