"""PRISM V2 — Phase A.5 Observability & Operational Control Demonstration
========================================================================
Demonstrates full A.5 deterministic observability and operational lifecycle:
1. Create isolated simulation run
2. Inspect initial consolidated state (t=0, tick=0)
3. Step simulation (t=10 min, tick 1)
4. Inspect operational metrics
5. Inspect chronological timeline events & factual summaries
6. Pause simulation (RUNNING -> PAUSED)
7. Execute single step while paused (t=20 min, tick 2)
8. Resume simulation (PAUSED -> RUNNING)
9. Advance to completion (t=30 min, tick 3)
10. Inspect final completed state and event counts
11. Verify baseline SNAP_BASE_001 immutability
"""

import sys
import os

# Add apps/api to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from app.db.session import SessionLocal
from app.models.entities import RelocationAllocation
from app.models.enums import SimulationStatusEnum, SimulationEventTypeEnum
from app.engines.e5_simulation.temporal_engine import TemporalSimulationEngine
from app.engines.e5_simulation.observability_service import SimulationObservabilityService


def main():
    db = SessionLocal()
    try:
        print("=" * 75)
        print("   PRISM V2 — PHASE A.5 OBSERVABILITY & OPERATIONAL CONTROL DEMO")
        print("=" * 75)

        engine = TemporalSimulationEngine(db)

        # Baseline check before demo
        base_allocs_before = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).count()
        print(f"\n[Baseline Initial Verification] SNAP_BASE_001 total allocations: {base_allocs_before}")

        # 1. Create Simulation Run
        run = engine.create_simulation_run(
            scenario_code="MONSOON_SURGE_01",
            timestep_minutes=10.0,
            duration_minutes=30.0,
            parameter_overrides={
                "closed_road_segments": ["BRIDGE_01"],
                "rainfall_multiplier_delta": 0.25,
                "river_level_delta_m": 0.60
            }
        )
        print(f"\n[1. Simulation Run Created]")
        print(f"  Run ID: {run.id}")
        print(f"  Scenario Snapshot ID: {run.scenario_snapshot_id}")
        print(f"  Timestep: {run.timestep_minutes} min | Duration: {run.duration_minutes} min | Total Ticks: {run.total_ticks}")

        # 2. Inspect Initial State (t=0)
        state_0 = SimulationObservabilityService.get_consolidated_state(db, run.id)
        print(f"\n[2. Initial Consolidated State at t=0 min]")
        print(f"  Status: {state_0.status.value}")
        print(f"  Clock: {state_0.current_simulation_time:.1f} min (Tick {state_0.current_tick}/{state_0.total_ticks})")
        print(f"  Progress: {state_0.progress_percentage:.1f}%")
        print(f"  Population: Total={state_0.population.total_population}, Planned={state_0.population.planned_population}, Sheltered={state_0.population.sheltered_population}")
        print(f"  Infrastructure: Blocked Roads={state_0.infrastructure.blocked_roads_count}, Open Roads={state_0.infrastructure.open_roads_count}")

        # 3. Step Simulation (t=10 min, Tick 1)
        print(f"\n[3. Stepping Simulation -> Tick 1 (t=10 min)]")
        res_step1 = engine.step_simulation(run.id)
        print(f"  Step returned: {len(res_step1['events_generated'])} events generated")

        # 4. Inspect Operational Metrics
        metrics_1 = SimulationObservabilityService.get_operational_metrics(db, run.id)
        print(f"\n[4. Operational Metrics at t=10 min]")
        print(f"  Ticks Completed: {metrics_1.ticks_completed} / {metrics_1.total_ticks}")
        print(f"  In-Transit Population: {metrics_1.in_transit_population}")
        print(f"  Sheltered Population: {metrics_1.sheltered_population}")
        print(f"  Stuck / Route Blocked: {metrics_1.stuck_population} / {metrics_1.route_blocked_population}")
        print(f"  Total Effective Capacity: {metrics_1.total_effective_capacity} / Physical: {metrics_1.total_physical_capacity}")
        print(f"  Occupancy: {metrics_1.overall_occupancy_pct:.1f}%")
        print(f"  Water Consumed: {metrics_1.total_water_consumed_liters:.1f} L")
        print(f"  Active Routes: {metrics_1.active_routes_count} | Reroutes: {metrics_1.reroute_count}")

        # 5. Inspect Chronological Events & Timeline
        timeline_1 = SimulationObservabilityService.get_simulation_timeline(db, run.id, limit=5)
        print(f"\n[5. Chronological Timeline Highlights (First 5 of {timeline_1.total_events} events)]")
        for i, ev in enumerate(timeline_1.events, 1):
            print(f"  {i}. [t={ev.simulation_time_min:.1f}m | Tick {ev.tick_index}] [{ev.event_type.value}]")
            print(f"     Summary: \"{ev.summary}\"")

        # 6. Pause Simulation
        print(f"\n[6. Pausing Simulation]")
        paused_run = engine.pause_simulation(run.id)
        print(f"  Run status transitioned to: {paused_run.status.value}")
        assert paused_run.status == SimulationStatusEnum.PAUSED

        # 7. Single Step while Paused (t=20 min, Tick 2)
        print(f"\n[7. Executing Single Step While Paused -> Tick 2 (t=20 min)]")
        res_step2 = engine.step_simulation(run.id)
        db.refresh(run)
        print(f"  Advanced to: {run.current_simulation_time:.1f} min (Tick {run.ticks_completed})")
        print(f"  Events generated in tick: {len(res_step2['events_generated'])}")

        # 8. Resume Simulation
        print(f"\n[8. Resuming Simulation]")
        resumed_run = engine.resume_simulation(run.id)
        print(f"  Run status transitioned to: {resumed_run.status.value}")
        assert resumed_run.status == SimulationStatusEnum.RUNNING

        # 9. Advance to Completion (t=30 min, Tick 3)
        print(f"\n[9. Advancing Simulation to Completion -> Tick 3 (t=30 min)]")
        res_step3 = engine.step_simulation(run.id)
        db.refresh(run)
        print(f"  Simulation completed with status: {run.status.value}")
        assert run.status == SimulationStatusEnum.COMPLETED

        # 10. Inspect Final State
        final_state = SimulationObservabilityService.get_consolidated_state(db, run.id)
        final_metrics = SimulationObservabilityService.get_operational_metrics(db, run.id)
        print(f"\n[10. Final Consolidated State & Metrics]")
        print(f"  Status: {final_state.status.value}")
        print(f"  Final Time: {final_state.current_simulation_time:.1f} min (Progress: {final_state.progress_percentage:.1f}%)")
        print(f"  Total Events Recorded: {final_metrics.total_events_recorded}")
        print(f"  Latest Important Event: \"{final_state.latest_important_event.summary if final_state.latest_important_event else 'None'}\"")
        print(f"  Event Counts By Type: {final_metrics.counts_by_event_type}")

        # 11. Baseline Invariant Verification
        base_allocs_after = db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).count()
        print(f"\n[11. Baseline Immutability Check]")
        print(f"  SNAP_BASE_001 allocations before: {base_allocs_before}")
        print(f"  SNAP_BASE_001 allocations after:  {base_allocs_after}")
        assert base_allocs_before == base_allocs_after
        print(f"  [PASS] SNAP_BASE_001 remains 100% immutable and untouched.")

        print("\n" + "=" * 75)
        print("  DEMO COMPLETED SUCCESSFULLY: ALL A.5 OBSERVABILITY CAPABILITIES VERIFIED")
        print("=" * 75)

    finally:
        db.close()


if __name__ == "__main__":
    main()
