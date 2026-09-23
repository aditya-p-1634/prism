from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.entities import AuditEvent, User

router = APIRouter(prefix="/audit", tags=["Audit & Governance"])

@router.get("/events")
def list_audit_events(
    action_type: Optional[str] = Query(None, description="Filter by action type (e.g. AUTHORITY_OVERRIDE, SCENARIO_RUN)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    List audit records with actor information and before/after state diffs.
    Provides immutable traceability for all decision changes and overrides.
    """
    query = db.query(AuditEvent)
    if action_type:
        query = query.filter(AuditEvent.action_type == action_type)
    
    events = query.order_by(AuditEvent.created_at.desc()).limit(limit).all()
    
    results = []
    for evt in events:
        user_name = "DEMO AUTHORITY"
        user_role = "DISTRICT AUTHORITY"
        if evt.user_id:
            user = db.query(User).filter(User.id == evt.user_id).first()
            if user:
                user_name = user.full_name or user.email
                user_role = user.role.value if hasattr(user.role, 'value') else str(user.role)

        results.append({
            "id": evt.id,
            "action_type": evt.action_type,
            "entity_type": evt.entity_type,
            "entity_id": evt.entity_id,
            "user_name": user_name,
            "user_role": user_role,
            "justification": evt.justification,
            "before_state": evt.before_state,
            "after_state": evt.after_state,
            "created_at": evt.created_at.isoformat() if evt.created_at else None
        })
        
    return {
        "status": "success",
        "count": len(results),
        "events": results
    }
