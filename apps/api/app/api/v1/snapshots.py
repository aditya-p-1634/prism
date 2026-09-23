import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import StateSnapshot
from app.schemas.envelope import ResponseEnvelope

router = APIRouter(prefix="/snapshots", tags=["Snapshots & Lineage (E6)"])

@router.get("", response_model=ResponseEnvelope[List[Dict[str, Any]]])
def list_snapshots(db: Session = Depends(get_db)):
    snaps = db.query(StateSnapshot).order_by(StateSnapshot.created_at.desc()).all()
    data = [
        {
            "id": s.id,
            "label": s.label,
            "snapshot_type": s.snapshot_type,
            "is_immutable": s.is_immutable,
            "scenario_id": s.scenario_id,
            "created_at": s.created_at.isoformat()
        }
        for s in snaps
    ]
    return ResponseEnvelope[List[Dict[str, Any]]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        data=data
    )

@router.post("/reset", response_model=ResponseEnvelope[Dict[str, Any]])
def reset_to_baseline():
    """
    Restore canonical baseline reality (SNAP_BASE_001).
    Purges ephemeral test/scenario executions and reinitializes deterministic state.
    """
    from app.seed.seed_service import seed_demo_database
    res = seed_demo_database()
    return ResponseEnvelope[Dict[str, Any]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        data=res
    )

