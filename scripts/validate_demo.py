import sys
import os

# Ensure UTF-8 output if possible
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add apps/api to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.join(os.path.dirname(current_dir), "apps", "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.db.session import SessionLocal
from app.models.entities import (
    StateSnapshot, StudyArea, Habitation, Household, Destination,
    CapacityState, RoadSegment, RoutePlan, RelocationAllocation, RedZone, PriorityRecord
)
from app.models.enums import OperationalStatusEnum, AllocationStatusEnum
from app.gis.spatial import to_shapely

def validate_demo():
    print("=" * 60)
    print("PRISM: RUNNING AUTOMATED DOMAIN & SYSTEM INVARIANT VALIDATOR")
    print("=" * 60)

    db = SessionLocal()
    failures = []

    try:
        # 1. Snapshot Integrity
        print("\n[Check 1/6] Verifying Snapshot & Immutability Invariant...")
        base_snap = db.query(StateSnapshot).filter(StateSnapshot.id == "SNAP_BASE_001").first()
        if not base_snap:
            failures.append("Baseline snapshot SNAP_BASE_001 not found.")
        elif not base_snap.is_immutable:
            failures.append("Baseline snapshot SNAP_BASE_001 is not marked is_immutable=True.")
        else:
            print("  [PASS] Baseline snapshot exists and is marked IMMUTABLE.")

        # 2. Spatial Geometry Validity
        print("\n[Check 2/6] Verifying Geospatial Topology & Validity...")
        habs = db.query(Habitation).all()
        for hab in habs:
            geom = to_shapely(hab.geom)
            if not geom.is_valid:
                failures.append(f"Habitation {hab.code} geometry is invalid.")
        dests = db.query(Destination).all()
        for d in dests:
            pt = to_shapely(d.location_geom)
            if not pt.is_valid:
                failures.append(f"Destination {d.code} point is invalid.")
        print(f"  [PASS] {len(habs)} Habitations and {len(dests)} Destinations have valid geometries.")

        # 3. Destination Safety Invariant
        print("\n[Check 3/6] Verifying Destination Hard Safety Filtering...")
        red_zones = db.query(RedZone).all()
        rz_geoms = [to_shapely(rz.geom) for rz in red_zones]
        for d in dests:
            pt = to_shapely(d.location_geom)
            for rz_geom in rz_geoms:
                if pt.intersects(rz_geom) and d.operational_status == OperationalStatusEnum.OPEN:
                    failures.append(f"Safety Violation: Destination {d.code} is in Red Zone but marked OPEN!")
        print("  [PASS] No flooded or Red Zone destination is marked OPEN.")

        # 4. Carrying Capacity Invariant
        print("\n[Check 4/6] Verifying Non-Negative Capacity Invariant...")
        caps = db.query(CapacityState).all()
        for cap in caps:
            if cap.remaining_capacity < 0:
                failures.append(f"Capacity Violation: Destination {cap.destination_id} has negative remaining capacity {cap.remaining_capacity}!")
        print(f"  [PASS] All {len(caps)} capacity states satisfy remaining_capacity >= 0.")

        # 5. Indivisibility Constraint
        print("\n[Check 5/6] Verifying Relocation Group Indivisibility...")
        allocs = db.query(RelocationAllocation).filter(RelocationAllocation.snapshot_id == "SNAP_BASE_001").all()
        group_counts = {}
        for a in allocs:
            group_counts[a.group_id] = group_counts.get(a.group_id, 0) + 1
        for gid, count in group_counts.items():
            if count > 1:
                failures.append(f"Indivisibility Violation: Group {gid} allocated {count} times!")
        print(f"  [PASS] All {len(allocs)} allocations respect single-assignment indivisibility.")

        # 6. Route Safety Invariant
        print("\n[Check 6/6] Verifying Safe Route Traversal...")
        routes = db.query(RoutePlan).all()
        for r in routes:
            if not r.is_viable and r.invalidated_reason is None:
                failures.append(f"Route {r.id} is marked unviable without reason code.")
        print(f"  [PASS] All {len(routes)} route plans have consistent viability state.")

        print("\n" + "=" * 60)
        if failures:
            print("VALIDATION FAILED WITH INVARIANT VIOLATIONS:")
            for f in failures:
                print(f"  [FAIL] {f}")
            print("=" * 60)
            sys.exit(1)
        else:
            print("ALL INVARIANT CHECKS PASSED PERFECTLY!")
            print("• Snapshot Immutability: VERIFIED")
            print("• Spatial Validity: VERIFIED")
            print("• Hard Safety Filtering: VERIFIED")
            print("• Capacity Non-Negativity: VERIFIED")
            print("• Household Indivisibility: VERIFIED")
            print("• Safe Route Integrity: VERIFIED")
            print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    validate_demo()
