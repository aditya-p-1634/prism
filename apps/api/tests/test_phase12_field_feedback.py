from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.api.v1.field_observations import create_field_observation, reconcile_field_observation
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import RoadSegment, User
from app.models.enums import RoleEnum
from app.schemas.field_observation import FieldObservationCreateDTO


def _authority(db):
    user = db.query(User).filter(User.email == "phase12-test@example.invalid").first()
    if not user:
        user = User(email="phase12-test@example.invalid", hashed_password=hash_password("test"), full_name="Phase 12 Test", role=RoleEnum.AUTHORITY, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def test_field_observation_reconciliation_preserves_plan_state():
    db = SessionLocal()
    try:
        user = _authority(db)
        segment = db.query(RoadSegment).first()
        payload = FieldObservationCreateDTO(
            snapshot_id="SNAP_BASE_001",
            observation_type="ROAD_STATUS",
            target_type="ROAD_SEGMENT",
            target_id=segment.id,
            observed_state="CLOSED",
            observed_at=datetime.now(timezone.utc),
            source_reference="field-report:test",
            confidence=0.9,
        )
        created = create_field_observation(payload, user, db)
        result = reconcile_field_observation(created.data.id, user, db)
        assert result.data.reconciliation_status == "CONFLICT"
        assert result.data.requires_human_review is True
        assert result.data.plan_mutated is False
        assert db.query(RoadSegment).filter(RoadSegment.id == segment.id).one().operational_status.value == "OPEN"
    finally:
        db.close()


def test_field_observation_requires_timezone():
    with pytest.raises(ValueError, match="timezone"):
        FieldObservationCreateDTO(
            snapshot_id="SNAP_BASE_001",
            observation_type="ROAD_STATUS",
            target_type="ROAD_SEGMENT",
            target_id="segment",
            observed_state="OPEN",
            observed_at=datetime(2026, 1, 1),
            source_reference="field-report:test",
            confidence=0.5,
        )
