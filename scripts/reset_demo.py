import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.join(os.path.dirname(current_dir), "apps", "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.db.session import engine, Base
import app.models

def reset_demo():
    if "--confirm" not in sys.argv:
        print("WARNING: This will drop all PRISM database tables and purge all snapshots.")
        print("To proceed, run: python scripts/reset_demo.py --confirm")
        sys.exit(1)

    print("Dropping all existing database tables...")
    Base.metadata.drop_all(bind=engine)
    print("Re-creating clean database tables...")
    Base.metadata.create_all(bind=engine)
    print("SUCCESS: Database schema reset cleanly.")

if __name__ == "__main__":
    reset_demo()
