from sqlalchemy import text
from app.db.session import engine, Base
import app.models # register all models

def init_db():
    Base.metadata.create_all(bind=engine)
    # Ensure migration columns for SQLite if table previously existed
    with engine.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(relocation_allocations)"))
            cols = [r[1] for r in res.fetchall()]
            if cols and "evacuation_state" not in cols:
                conn.execute(text("ALTER TABLE relocation_allocations ADD COLUMN evacuation_state VARCHAR(50) DEFAULT 'PLANNED' NOT NULL"))
                conn.commit()

            res2 = conn.execute(text("PRAGMA table_info(hazard_prediction_records)"))
            cols2 = [r[1] for r in res2.fetchall()]
            if cols2 and "lifecycle_state" not in cols2:
                conn.execute(text("ALTER TABLE hazard_prediction_records ADD COLUMN lifecycle_state VARCHAR(50) DEFAULT 'VALIDATED'"))
                conn.commit()
        except Exception:
            pass

    # Ensure canonical pilot station is registered
    try:
        from app.db.session import SessionLocal
        from app.engines.e1_hazard.observation.station_registry import StationRegistry
        with SessionLocal() as db:
            StationRegistry.ensure_pilot_station(db)
    except Exception as e:
        print(f"Notice: Pilot station registration during init_db: {e}")

    print("All PRISM canonical database tables created successfully.")

if __name__ == "__main__":
    init_db()

