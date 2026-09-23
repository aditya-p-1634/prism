import sys
import os

# Add apps/api to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.join(os.path.dirname(current_dir), "apps", "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.seed.seed_service import seed_demo_database

def seed_demo():
    print("=" * 60)
    print("PRISM: SEEDING CANONICAL VAYU RIVER BASIN DEMO WORLD")
    print("=" * 60)
    res = seed_demo_database()
    print("\n" + "=" * 60)
    print("SUCCESS! BASELINE WORLD INITIALIZED CLEANLY.")
    print(f"Snapshot ID: {res['snapshot_id']}")
    print(f"Households: {res['households_count']}")
    print(f"Allocations: {res['allocations_count']}")
    print("Baseline Snapshot: SNAP_BASE_001 (IMMUTABLE)")
    print("=" * 60)

if __name__ == "__main__":
    seed_demo()
