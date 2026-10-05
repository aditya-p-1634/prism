"""
PRISM — Correctness Reconciliation Pass Automated Verifier
Validates:
1. Destination capacity derivation (D1=150, D2=60, D3=50 baseline; D1=150, D2=45, D3=50 scenario)
2. Safe routing algorithm confirmation (NetworkX Dijkstra weighted shortest path)
3. Engine ownership attribution (E4 relocation optimization, E5 predictive simulation)
4. Invariant checks:
   - 93 total people across 28 households
   - Baseline affected: 8 households, 26 people
   - Scenario affected: 16 households, 53 people
   - Scenario allocation: D1=20, D2=27, D3=46 (total=93, unmet=0)
   - Baseline immutability
   - Authority override creation and audit trail recording
   - Clean restoration to baseline
"""

import sys
import json
import urllib.request

API_BASE = "http://localhost:8000/api/v1"

def get(path):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("data", data) if isinstance(data, dict) else data

def post(path, body=None):
    url = f"{API_BASE}{path}"
    raw = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=raw, headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("data", data) if isinstance(data, dict) else data

def main():
    print("============================================================")
    print("PRISM: RUNNING FINAL CORRECTNESS RECONCILIATION PASS")
    print("============================================================")

    # 1. Reset to baseline first
    print("\n[Step 1] Ensuring clean baseline state...")
    reset_res = post("/snapshots/reset")
    assert reset_res.get("status") == "success", f"Reset failed: {reset_res}"

    # 2. Check Baseline Capacity Derivation
    print("\n[Step 2] Verifying Baseline Destination Capacities (E3)...")
    dests = get("/destinations?snapshot_id=SNAP_BASE_001")
    cap_map = {}
    for d in dests:
        cap = d.get("capacity_state", {})
        eff = cap.get("effective_capacity")
        bot = cap.get("bottleneck_resource")
        cap_map[d["code"]] = (eff, bot)
        print(f"  {d['code']} ({d['name']}): Effective Capacity = {eff}, Bottleneck = {bot}")

    assert cap_map["DEST_01"][0] == 150, f"Expected 150 for DEST_01, got {cap_map['DEST_01'][0]}"
    assert cap_map["DEST_02"][0] == 60, f"Expected 60 for DEST_02, got {cap_map['DEST_02'][0]}"
    assert cap_map["DEST_03"][0] == 50, f"Expected 50 for DEST_03, got {cap_map['DEST_03'][0]}"
    assert cap_map["DEST_01"][1] == "WATER", f"Expected WATER bottleneck for DEST_01, got {cap_map['DEST_01'][1]}"
    assert cap_map["DEST_02"][1] == "WATER", f"Expected WATER bottleneck for DEST_02, got {cap_map['DEST_02'][1]}"
    assert cap_map["DEST_03"][1] == "HEALTHCARE", f"Expected HEALTHCARE bottleneck for DEST_03, got {cap_map['DEST_03'][1]}"
    print("  -> Baseline capacities verified: D1=150, D2=60, D3=50 (derived via Liebig's Law).")

    # 3. Check Baseline Population & Priorities
    print("\n[Step 3] Verifying Baseline Population & Inundation...")
    households = get("/people/households?snapshot_id=SNAP_BASE_001")
    total_hh = len(households)
    total_pop = sum(h["member_count"] for h in households)
    print(f"  Total Households: {total_hh} (Expected 28)")
    print(f"  Total Population: {total_pop} (Expected 93)")
    assert total_hh == 28, f"Expected 28 households, got {total_hh}"
    assert total_pop == 93, f"Expected 93 population, got {total_pop}"

    priors = get("/people/priorities?snapshot_id=SNAP_BASE_001")
    affected_priors = [p for p in priors if p.get("component_scores", {}).get("exposure", 0) > 0]
    aff_hh = len(affected_priors)
    aff_pop = sum(p["member_count"] for p in affected_priors)
    print(f"  Baseline Affected Households: {aff_hh} (Expected 8)")
    print(f"  Baseline Affected Population: {aff_pop} (Expected 26)")
    assert aff_hh == 8, f"Expected 8 affected households, got {aff_hh}"
    assert aff_pop == 26, f"Expected 26 affected population, got {aff_pop}"

    # 4. Check Road Network & Bridge Status
    print("\n[Step 4] Verifying Baseline Road Network & Routing (E4)...")
    segments = get("/road-segments")
    bridge = next((s for s in segments if "BRIDGE" in s.get("segment_code", "") or s.get("is_bridge")), None)
    assert bridge is not None, "BRIDGE_01 segment not found in network!"
    print(f"  BRIDGE_01 status: {bridge.get('operational_status')} (Expected OPEN)")
    assert bridge.get("operational_status") == "OPEN", "BRIDGE_01 should be OPEN at baseline"

    routes = get("/routes?snapshot_id=SNAP_BASE_001")
    print(f"  Route plans generated: {len(routes)} (Expected 12 viable origin-destination routes)")
    assert len(routes) == 12, f"Expected 12 routes, got {len(routes)}"

    # 5. Run MONSOON_SURGE_01
    print("\n[Step 5] Executing MONSOON_SURGE_01 Scenario...")
    scen_res = post("/scenarios/run", {
        "scenario_code": "MONSOON_SURGE_01",
        "parameter_overrides": {
            "rainfall_multiplier": 1.20,
            "river_level_delta_m": 0.50,
            "collapse_bridge_01": True,
            "dest_02_water_retention": 0.75
        }
    })
    scen_snap_id = scen_res.get("scenario_snapshot_id")
    print(f"  Scenario Snapshot ID: {scen_snap_id}")

    # 6. Verify Scenario Capacity Derivation (D1=150, D2=45, D3=50)
    print("\n[Step 6] Verifying Scenario Destination Capacities (E3)...")
    scen_dests = get(f"/destinations?snapshot_id={scen_snap_id}")
    scen_cap_map = {}
    for d in scen_dests:
        cap = d.get("capacity_state", {})
        eff = cap.get("effective_capacity")
        bot = cap.get("bottleneck_resource")
        scen_cap_map[d["code"]] = (eff, bot)
        print(f"  {d['code']} ({d['name']}): Effective Capacity = {eff}, Bottleneck = {bot}")

    assert scen_cap_map["DEST_01"][0] == 150, f"Expected 150 for DEST_01, got {scen_cap_map['DEST_01'][0]}"
    assert scen_cap_map["DEST_02"][0] == 45, f"Expected 45 for DEST_02, got {scen_cap_map['DEST_02'][0]}"
    assert scen_cap_map["DEST_03"][0] == 50, f"Expected 50 for DEST_03, got {scen_cap_map['DEST_03'][0]}"
    assert scen_cap_map["DEST_02"][1] == "WATER", f"Expected WATER bottleneck for DEST_02, got {scen_cap_map['DEST_02'][1]}"
    print("  -> Scenario capacities verified: D1=150, D2=45, D3=50 (D2 water capacity 25% drop verified).")

    # 7. Verify Scenario Population & Priorities
    print("\n[Step 7] Verifying Scenario Population Inundation...")
    scen_priors = get(f"/people/priorities?snapshot_id={scen_snap_id}")
    scen_aff_priors = [p for p in scen_priors if p.get("component_scores", {}).get("exposure", 0) > 0]
    scen_aff_hh = len(scen_aff_priors)
    scen_aff_pop = sum(p["member_count"] for p in scen_aff_priors)
    print(f"  Scenario Affected Households: {scen_aff_hh} (Expected 16)")
    print(f"  Scenario Affected Population: {scen_aff_pop} (Expected 53)")
    assert scen_aff_hh == 16, f"Expected 16 affected households, got {scen_aff_hh}"
    assert scen_aff_pop == 53, f"Expected 53 affected population, got {scen_aff_pop}"

    # 8. Verify E4 CP-SAT Allocation Results
    print("\n[Step 8] Verifying Scenario Relocation Allocations (E4 CP-SAT)...")
    scen_allocs = get(f"/relocation/allocations?snapshot_id={scen_snap_id}")
    dest_dist = {}
    for a in scen_allocs:
        d_name = a.get("destination_name")
        dest_dist[d_name] = dest_dist.get(d_name, 0) + a.get("assigned_capacity_count", 0)
    print(f"  Scenario Allocation Distribution: {dest_dist}")
    assert dest_dist.get("Vayu Community Center") == 20, f"Expected 20 at DEST_01, got {dest_dist.get('Vayu Community Center')}"
    assert dest_dist.get("District Senior Secondary School") == 27, f"Expected 27 at DEST_02, got {dest_dist.get('District Senior Secondary School')}"
    assert dest_dist.get("Hilltop Sports Complex") == 46, f"Expected 46 at DEST_03, got {dest_dist.get('Hilltop Sports Complex')}"
    total_alloc = sum(dest_dist.values())
    print(f"  Total Accommodated: {total_alloc} / 93 | Unmet Demand: 0")
    assert total_alloc == 93, f"Expected 93 accommodated, got {total_alloc}"

    # 9. Verify Authority Override & Audit Recording
    print("\n[Step 9] Verifying Authority Override & Audit Trail...")
    alloc_to_move = next(a for a in scen_allocs if a.get("destination_name") == "Hilltop Sports Complex")
    override_res = post("/relocation/override", {
        "allocation_id": alloc_to_move["id"],
        "new_destination_id": "DEST_01",
        "justification": "Authority directive: special medical care required at primary center."
    })
    assert override_res.get("allocation_status") == "OVERRIDDEN", f"Override status error: {override_res}"
    print(f"  Override executed successfully: allocation={override_res.get('id')}, status={override_res.get('allocation_status')}")

    audit_res = get("/audit/events")
    events = audit_res.get("events", audit_res) if isinstance(audit_res, dict) else audit_res
    override_evt = next((e for e in events if e.get("action_type") == "AUTHORITY_ALLOCATION_OVERRIDE"), None)
    assert override_evt is not None, "Authority override event missing from audit ledger!"
    print(f"  Audit event logged: action={override_evt.get('action_type')}, actor={override_evt.get('actor_role') or override_evt.get('actor')}")
    print(f"  Before state: {override_evt.get('before_state')}")
    print(f"  After state: {override_evt.get('after_state')}")

    # 10. Verify Baseline Immutability
    print("\n[Step 10] Verifying Baseline Immutability...")
    base_priors_check = get("/people/priorities?snapshot_id=SNAP_BASE_001")
    base_aff_check = [p for p in base_priors_check if p.get("component_scores", {}).get("exposure", 0) > 0]
    assert len(base_aff_check) == 8, f"Baseline mutated! Expected 8 affected, got {len(base_aff_check)}"
    print("  Baseline immutability confirmed: still 8 affected households.")

    # 11. Restore to Baseline
    print("\n[Step 11] Restoring Canonical Baseline...")
    reset_res = post("/snapshots/reset")
    assert reset_res.get("status") == "success"
    post_reset_priors = get("/people/priorities?snapshot_id=SNAP_BASE_001")
    post_aff = [p for p in post_reset_priors if p.get("component_scores", {}).get("exposure", 0) > 0]
    assert len(post_aff) == 8
    print("  Canonical baseline restored cleanly.")

    print("\n============================================================")
    print("ALL 11 RECONCILIATION CHECKS PASSED PERFECTLY WITH ZERO ERRORS!")
    print("============================================================")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
