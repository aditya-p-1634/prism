import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.api.v1.health import readiness_check
from app.db.session import SessionLocal


def test_production_rejects_demo_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(PRISM_ENV="production")


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            PRISM_ENV="production",
            JWT_SECRET="x" * 40,
            CORS_ORIGINS="*",
        )


def test_cors_origins_are_parsed_explicitly():
    settings = Settings(
        PRISM_ENV="test",
        JWT_SECRET="test-secret",
        CORS_ORIGINS="http://localhost:3000, https://ops.example.org",
    )
    assert settings.cors_origins == ["http://localhost:3000", "https://ops.example.org"]


def test_readiness_accepts_seeded_immutable_baseline():
    db = SessionLocal()
    try:
        result = readiness_check(db)
        assert result["status"] == "READY"
        assert result["checks"]["baseline_snapshot"]["immutable"] is True
    finally:
        db.close()
