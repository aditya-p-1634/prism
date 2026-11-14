from app.core.config import settings
from app.db.session import engine, SessionLocal
from app.models.entities import (
    Household,
    RelocationAllocation,
    StateSnapshot,
)


def test_tests_use_a_disposable_database():
    """The repository's canonical prism.db must never be used by pytest."""
    assert settings.PRISM_ENV == "test"
    assert "prism-test-" in str(engine.url)
    assert not str(engine.url).endswith("/prism.db")


def test_clean_seed_has_canonical_baseline_counts():
    """The shared test fixture starts from the documented demo baseline."""
    with SessionLocal() as db:
        baseline = db.query(StateSnapshot).filter(StateSnapshot.id == "SNAP_BASE_001").one()
        assert baseline.is_immutable is True
        assert db.query(Household).count() == 28
        assert db.query(RelocationAllocation).filter(
            RelocationAllocation.snapshot_id == "SNAP_BASE_001"
        ).count() == 28
