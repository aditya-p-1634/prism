from app.db.session import engine, Base
import app.models # register all models

def init_db():
    Base.metadata.create_all(bind=engine)
    print("All PRISM canonical database tables created successfully.")

if __name__ == "__main__":
    init_db()
