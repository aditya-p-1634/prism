"""
PRISM End-to-End Product Verification & Invariant Check Script
Tests the full runtime chain against the live running FastAPI backend on http://localhost:8000.
"""

import sys
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000/api/v1"

def api_get(endpoint):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("data", res) if isinstance(res, dict) else res

def api_post(endpoint, payload=None):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("data", res) if isinstance(res, dict) else res

def main():
    print("=== PRISM END-TO-END INVARIANT & FLOW VERIFICATION ===")
    
    # 1. Telemetry & Baseline check
    print("\n[1] Checking System Telemetry & DB Status...")
    telemetry = api_get("/health/telemetry")
    assert telemetry["database"]["connected"] is True, "Database is not connected!"
    assert telemetry["database"]["file_size_kb"] > 0, "Database size is 0 KB!"
    print(f"  DB Connected: {telemetry['database']['connected']}")
    print(f"  DB Size: {telemetry['database']['file_size_kb']} KB")
    print(f"  DB Latency: {telemetry['measured_telemetry']['query_latency_ms']} ms")
    print(f"  Study Area: {telemetry['study_area']['name']} ({telemetry['study_area']['code']})")
    print(f"  Entities: {telemetry['study_area']['entities']}")
    
    # 2. Canonical Baseline Check
    print("\n[2] Checking Canonical Baseline (SNAP_BASE_001)...")
    snaps = api_get("/snapshots")
    snap_ids = [s["id"] for s in snaps]
    assert "SNAP_BASE_001" in snap_ids, "SNAP_BASE_001 not found in snapshots!"
    print(f"  Snapshots present: {snap_ids}")
    
    hh_data = api_get("/people/households?snapshot_id=SNAP_BASE_001")
    total_hh = len(hh_data)
    total_pop = sum(h["member_count"] for h in hh_data)
    print(f"  Households: {total_hh} (Expected 28)")
    print(f"  Total Pop: {total_pop} (Expected 93)")
    assert total_hh == 28, f"Expected 28 households, got {total_hh}"
    assert total_pop == 93, f"Expected 93 population, got {total_pop}"

    priors = api_get("/people/priorities?snapshot_id=SNAP_BASE_001")
    affected_priors = [p for p in priors if p.get("component_scores", {}).get("exposure", 0) > 0]
    affected_hh_count = len(affected_priors)
    affected_pop = sum(p["member_count"] for p in affected_priors)
    print(f"  Baseline Affected HH: {affected_hh_count} (Expected 8)")
    print(f"  Baseline Affected Pop: {affected_pop} (Expected 26)")
    assert affected_hh_count == 8, f"Expected 8 affected households, got {affected_hh_count}"
    assert affected_pop == 26, f"Expected 26 affected population, got {affected_pop}"
    
    facs = api_get("/destinations?snapshot_id=SNAP_BASE_001")
    print(f"  Facilities count: {len(facs)} (Expected 3)")
    assert len(facs) == 3, f"Expected 3 facilities, got {len(facs)}"
    for f in facs:
        cap = f.get("capacity_state") or {}
        print(f"    {f['code']} ({f['name']}): Effective={cap.get('effective_capacity')}, Bottleneck={cap.get('bottleneck_resource')}")
    
    segments = api_get("/road-segments")
    print(f"  Road segments: {len(segments)}")
    bridge = next((s for s in segments if "BRIDGE" in s.get("segment_code", "") or s.get("is_bridge")), None)
    if bridge:
        print(f"  Bridge Status at Baseline: {bridge.get('operational_status')}")
    
    allocs = api_get("/relocation/allocations?snapshot_id=SNAP_BASE_001")
    print(f"  Baseline Allocations count: {len(allocs)} (Expected 28)")
    assert len(allocs) == 28, f"Expected 28 allocations, got {len(allocs)}"
    
    # 3. Execute MONSOON_SURGE_01 Scenario
    print("\n[3] Executing Scenario MONSOON_SURGE_01...")
    res = api_post("/scenarios/run", {
        "scenario_code": "MONSOON_SURGE_01",
        "parameter_overrides": {
            "rainfall_multiplier": 1.20,
            "river_level_delta_m": 0.50,
            "collapse_bridge_01": True,
            "dest_02_water_retention": 0.75
        }
    })
    
    scenario_snap_id = res.get("scenario_snapshot_id")
    print(f"  Scenario executed successfully! Snapshot ID: {scenario_snap_id}")
    print(f"  Summary: {res.get('summary_explanation')}")
    print(f"  Hazard Delta: {res.get('hazard_delta')}")
    print(f"  Route Invalidations: {res.get('route_invalidations')}")
    print(f"  Capacity Changes: {res.get('capacity_changes')}")
    print(f"  Reallocated Groups: {res.get('reallocated_groups_count')}")
    print(f"  Unmet Demand Delta: {res.get('unmet_demand_delta')}")
    
    # 4. Verify Scenario State Isolation
    print("\n[4] Verifying Scenario State Isolation...")
    scen_priors = api_get(f"/people/priorities?snapshot_id={scenario_snap_id}")
    scen_affected_priors = [p for p in scen_priors if p.get("component_scores", {}).get("exposure", 0) > 0]
    print(f"  Scenario Affected HH count: {len(scen_affected_priors)} (Expected 16)")
    assert len(scen_affected_priors) == 16, f"Expected 16 scenario affected HH, got {len(scen_affected_priors)}"
    scen_affected_pop = sum(p["member_count"] for p in scen_affected_priors)
    print(f"  Scenario Affected Pop: {scen_affected_pop} (Expected 53)")
    assert scen_affected_pop == 53, f"Expected 53 scenario affected population, got {scen_affected_pop}"
    
    # Check baseline is still immutable
    base_priors_check = api_get("/people/priorities?snapshot_id=SNAP_BASE_001")
    base_aff_check = [p for p in base_priors_check if p.get("component_scores", {}).get("exposure", 0) > 0]
    assert len(base_aff_check) == 8, f"Baseline mutated! Expected 8 affected, got {len(base_aff_check)}"
    print("  Baseline immutability verified: still 8 affected households.")
    
    # Check allocations distribution under scenario
    scen_allocs = api_get(f"/relocation/allocations?snapshot_id={scenario_snap_id}")
    dest_name_counts = {}
    for a in scen_allocs:
        d_name = a.get("destination_name")
        dest_name_counts[d_name] = dest_name_counts.get(d_name, 0) + a.get("assigned_capacity_count", 0)
    print(f"  Scenario Destination Distribution: {dest_name_counts}")
    assert dest_name_counts.get("Vayu Community Center") == 20, f"Expected 20 at Vayu Community Center, got {dest_name_counts.get('Vayu Community Center')}"
    assert dest_name_counts.get("District Senior Secondary School") == 27, f"Expected 27 at District Senior Secondary School, got {dest_name_counts.get('District Senior Secondary School')}"
    assert dest_name_counts.get("Hilltop Sports Complex") == 46, f"Expected 46 at Hilltop Sports Complex, got {dest_name_counts.get('Hilltop Sports Complex')}"
    
    # 5. Authority Override Verification
    print("\n[5] Testing Authority Override...")
    # Find an allocation assigned to Hilltop Sports Complex (DEST_03)
    alloc_to_override = next((a for a in scen_allocs if a.get("destination_name") == "Hilltop Sports Complex"), scen_allocs[0])
    alloc_id = alloc_to_override.get("id")
    print(f"  Attempting override for allocation: {alloc_id} ({alloc_to_override.get('habitation_name')})")
    
    override_res = api_post("/relocation/override", {
        "allocation_id": alloc_id,
        "new_destination_id": "DEST_01",
        "justification": "Authorized district relocation exception for critical medical requirement."
    })
    print(f"  Override Response: id={override_res.get('id')}, status={override_res.get('allocation_status')}, reason={override_res.get('reason_code')}")
    assert override_res.get("allocation_status") == "OVERRIDDEN", "Allocation status should be OVERRIDDEN"
    
    # 6. Check Audit Log contains the override
    print("\n[6] Checking Audit Trail for Event...")
    audit_data = api_get("/audit/events")
    events = audit_data.get("events", audit_data) if isinstance(audit_data, dict) else audit_data
    print(f"  Total Audit Events: {len(events)}")
    override_events = [e for e in events if "OVERRIDE" in str(e.get("action_type", "")).upper()]
    print(f"  Override Events found: {len(override_events)}")
    assert len(override_events) > 0, "Authority override did not produce an audit event!"
    latest_evt = override_events[0]
    print(f"  Audit Event Verified: action={latest_evt.get('action_type')}, entity={latest_evt.get('entity_id')}, just={latest_evt.get('justification')}")
    
    # 7. Operational Reports Check
    print("\n[7] Checking Operational Reports...")
    rep = api_get(f"/reports/summary?snapshot_id={scenario_snap_id}")
    summary_kpis = rep.get("summary", {})
    print(f"  Report summary KPIs: {summary_kpis}")
    assert summary_kpis.get("total_relocated_headcount") == 93, f"Expected 93 accommodated, got {summary_kpis.get('total_relocated_headcount')}"
    assert summary_kpis.get("unmet_headcount") == 0, f"Expected 0 unmet, got {summary_kpis.get('unmet_headcount')}"
    
    # 8. Restore Canonical Baseline
    print("\n[8] Testing Restore Canonical Baseline...")
    reset_res = api_post("/snapshots/reset")
    print(f"  Reset response status: {reset_res.get('status', 'OK')}")
    
    # Verify baseline is active and clean
    post_reset_hh = api_get("/people/households?snapshot_id=SNAP_BASE_001")
    assert len(post_reset_hh) == 28
    post_reset_priors = api_get("/people/priorities?snapshot_id=SNAP_BASE_001")
    post_reset_aff = [p for p in post_reset_priors if p.get("component_scores", {}).get("exposure", 0) > 0]
    assert len(post_reset_aff) == 8
    print("  Baseline restored cleanly: 28 households, 8 affected.")
    
    print("\nALL 8 END-TO-END INVARIANT & INTEGRATION CHECKS PASSED WITH ZERO ERRORS!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
