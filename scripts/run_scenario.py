import sys
import os
import json

# Add apps/api to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.join(os.path.dirname(current_dir), "apps", "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.db.session import SessionLocal
from app.engines.e5_simulation.service import SimulationEngineE5
from app.models.entities import StateSnapshot, Scenario

def run_scenario(scenario_code: str = "MONSOON_SURGE_01"):
    print("=" * 60)
    print(f"PRISM: EXECUTING SCENARIO [{scenario_code}]")
    print("=" * 60)

    db = SessionLocal()
    try:
        baseline_snapshot = db.query(StateSnapshot).filter(StateSnapshot.id == "SNAP_BASE_001").first()
        if not baseline_snapshot:
            print("ERROR: Baseline snapshot SNAP_BASE_001 not found. Please run scripts/seed_demo.py first.")
            sys.exit(1)

        scenario = db.query(Scenario).filter(Scenario.code == scenario_code).first()
        if not scenario:
            print(f"ERROR: Scenario {scenario_code} not found in database registry.")
            sys.exit(1)

        print(f"\nScenario Description: {scenario.description}")
        print(f"Scenario Parameters: {json.dumps(scenario.parameters, indent=2)}")

        print("\nTriggering Engine 5 Adaptive Replanning Cascade...")
        print("  -> E1: Recalculating hazard flood expansion and Red Zone...")
        print("  -> E2: Re-evaluating exposure and re-ranking household priorities...")
        print("  -> E3: Recalculating destination carrying capacities and bottlenecks...")
        print("  -> E4: Pruning submerged routes and solving CP-SAT reallocation...")

        e5 = SimulationEngineE5(db)
        delta = e5.execute_scenario(scenario_code, baseline_snapshot.id)

        print("\n" + "=" * 60)
        print("SCENARIO EXECUTION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nCAUSAL DELTA REPORT:")
        print(f"• Baseline Snapshot: {delta['baseline_snapshot_id']}")
        print(f"• Scenario Snapshot: {delta['scenario_snapshot_id']}")
        print(f"• Priority Shifts: {delta['priority_shifts']['upgraded_to_immediate']} households upgraded to IMMEDIATE priority!")
        print(f"• Households with higher vulnerability: {delta['priority_shifts']['households_with_increased_priority']}")
        print(f"• Invalidated Routes: {', '.join(delta['route_invalidations'])}")
        print(f"• Unmet Relocation Demand: {delta['unmet_demand_delta']} groups")
        print("\nEXECUTIVE SUMMARY NARRATIVE:")
        print(delta["summary_explanation"])
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR DURING SCENARIO EXECUTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    scen = sys.argv[1] if len(sys.argv) > 1 else "MONSOON_SURGE_01"
    run_scenario(scen)
