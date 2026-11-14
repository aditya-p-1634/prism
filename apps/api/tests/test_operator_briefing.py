import pytest
from fastapi import HTTPException

from app.api.v1.dashboard import get_operator_briefing
from app.db.session import SessionLocal


def test_operator_briefing_is_read_only_and_actionable():
    db = SessionLocal()
    try:
        response = get_operator_briefing("SNAP_BASE_001", db)
        data = response.data
        assert data["snapshot"]["is_immutable"] is True
        assert data["snapshot"]["requires_human_review"] is True
        assert data["integrity"]["allocation_is_not_evacuation"] is True
        assert data["integrity"]["field_confirmation_available"] is False
        assert data["decision_summary"]["total_priority_groups"] == 28
        assert data["decision_summary"]["unmet_groups"] == 0
        assert data["next_actions"]
        assert data["top_priority_groups"]
    finally:
        db.close()


def test_operator_briefing_rejects_unknown_snapshot():
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            get_operator_briefing("UNKNOWN", db)
        assert exc_info.value.status_code == 404
    finally:
        db.close()
