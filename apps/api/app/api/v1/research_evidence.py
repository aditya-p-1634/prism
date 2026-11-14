"""Read-only research evidence endpoints kept separate from E1-E6 state."""

import json
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.schemas.envelope import ResponseEnvelope

router = APIRouter(prefix="/research-evidence", tags=["Research Evidence (Non-operational)"])
ARTIFACT = Path(__file__).resolve().parents[5] / "docs/research/artifacts/phase17_spatial_event_evidence.json"


@router.get("/spatial-event", response_model=ResponseEnvelope[Dict[str, Any]])
def get_spatial_event_evidence() -> ResponseEnvelope[Dict[str, Any]]:
    """Return the immutable Phase 17 evidence artifact without mutating operational state."""
    if not ARTIFACT.exists():
        raise HTTPException(status_code=503, detail="Research evidence artifact is unavailable")
    try:
        data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Research evidence artifact is unreadable") from exc
    return ResponseEnvelope(
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        confidence=0.0,
        data=data,
        warnings=["Historical research evidence is non-operational and not a supervised flood label."],
    )
