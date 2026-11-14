"""Shared test isolation for the PRISM backend.

The application reads configuration during module import, so the disposable
database environment must be installed before any test imports ``app.main``.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest


_test_root = Path(tempfile.mkdtemp(prefix="prism-test-"))
_test_database = (_test_root / "prism-test.db").as_posix()

os.environ["PRISM_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_database}"
os.environ["JWT_SECRET"] = "prism-test-only-secret"


@pytest.fixture(scope="session", autouse=True)
def seeded_test_database():
    """Seed one clean session database and remove it after the test run."""
    from app.db.session import engine
    from app.seed.seed_service import seed_demo_database

    seed_demo_database()
    try:
        yield
    finally:
        engine.dispose()
        shutil.rmtree(_test_root, ignore_errors=True)


def pytest_report_header(config):
    return f"PRISM test database: {_test_database}"
