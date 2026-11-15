import uuid
from datetime import timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_role, require_existing_snapshot
from app.db.session import get_db
from app.models.entities import (
    AuditEvent, DestinationSnapshotState, FieldObservation, RelocationAllocation,
    RoadSegment, StateSnapshot, User,
)
from app.models.enums import RoleEnum
from app.schemas.envelope import ResponseEnvelope
from app.schemas.field_observation import (
    FieldObservationCreateDTO, FieldObservationResponseDTO, FieldReconciliationDTO,
)

router = APIRouter(prefix="/field-observations", tags=["Field Feedback & Reconciliation (E6)"])


def _to_dto(record: FieldObservation) -> FieldObservationResponseDTO:
    return FieldObservationResponseDTO(
        id=record.id,
        snapshot_id=record.snapshot_id,
        observation_type=record.observation_type,
        target_type=record.target_type,
        target_id=record.target_id,
        observed_state=record.observed_state,
        observed_value=record.observed_value,
        unit=record.unit,
        observed_at=record.observed_at,
        source_reference=record.source_reference,
        confidence=record.confidence,
        quality_status=record.quality_status,
        reconciliation_status=record.reconciliation_status,
        reconciliation_result=record.reconciliation_result or {},
    )


@router.post("", response_model=ResponseEnvelope[FieldObservationResponseDTO])
def create_field_observation(
    payload: FieldObservationCreateDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db),
):
    snapshot = db.query(StateSnapshot).filter(StateSnapshot.id == payload.snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"SNAPSHOT_NOT_FOUND: {payload.snapshot_id}")
    target_type = payload.target_type.upper().strip()
    if target_type not in {"ROAD_SEGMENT", "DESTINATION", "ALLOCATION"}:
        raise HTTPException(status_code=422, detail="UNSUPPORTED_TARGET_TYPE: use ROAD_SEGMENT, DESTINATION, or ALLOCATION")
    record = FieldObservation(
        snapshot_id=payload.snapshot_id,
        observation_type=payload.observation_type.upper().strip(),
        target_type=target_type,
        target_id=payload.target_id,
        observed_state=payload.observed_state.upper().strip(),
        observed_value=payload.observed_value,
        unit=payload.unit,
        observed_at=payload.observed_at.astimezone(timezone.utc).replace(tzinfo=None),
        source_reference=payload.source_reference.strip(),
        confidence=payload.confidence,
        created_by=current_user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ResponseEnvelope[FieldObservationResponseDTO](
        request_id=str(uuid.uuid4()), correlation_id=str(uuid.uuid4()), snapshot_id=payload.snapshot_id, data=_to_dto(record)
    )


@router.get("", response_model=ResponseEnvelope[List[FieldObservationResponseDTO]])
def list_field_observations(
    snapshot_id: str = Query("SNAP_BASE_001"),
    reconciliation_status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    require_existing_snapshot(db, snapshot_id)
    query = db.query(FieldObservation).filter(FieldObservation.snapshot_id == snapshot_id)
    if reconciliation_status:
        query = query.filter(FieldObservation.reconciliation_status == reconciliation_status.upper())
    records = query.order_by(FieldObservation.observed_at.desc()).limit(limit).all()
    return ResponseEnvelope[List[FieldObservationResponseDTO]](
        request_id=str(uuid.uuid4()), correlation_id=str(uuid.uuid4()), snapshot_id=snapshot_id, data=[_to_dto(r) for r in records]
    )


@router.post("/{observation_id}/reconcile", response_model=ResponseEnvelope[FieldReconciliationDTO])
def reconcile_field_observation(
    observation_id: str,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db),
):
    record = db.query(FieldObservation).filter(FieldObservation.id == observation_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"FIELD_OBSERVATION_NOT_FOUND: {observation_id}")

    expected_state = None
    if record.target_type == "ROAD_SEGMENT":
        target = db.query(RoadSegment).filter(RoadSegment.id == record.target_id).first()
        expected_state = target.operational_status.value if target else None
    elif record.target_type == "DESTINATION":
        target = db.query(DestinationSnapshotState).filter(
            DestinationSnapshotState.destination_id == record.target_id,
            DestinationSnapshotState.snapshot_id == record.snapshot_id,
        ).first()
        expected_state = target.operational_status.value if target else None
    elif record.target_type == "ALLOCATION":
        target = db.query(RelocationAllocation).filter(
            RelocationAllocation.id == record.target_id,
            RelocationAllocation.snapshot_id == record.snapshot_id,
        ).first()
        expected_state = target.evacuation_state.value if target else None

    if expected_state is None:
        status_value = "UNRESOLVED"
        conflict_reason = "Target does not exist in the selected snapshot or has no comparable state."
    elif expected_state.upper() == record.observed_state.upper():
        status_value = "MATCH"
        conflict_reason = None
    else:
        status_value = "CONFLICT"
        conflict_reason = f"Observed {record.observed_state} differs from snapshot state {expected_state}."

    result = {
        "expected_state": expected_state,
        "observed_state": record.observed_state,
        "status": status_value,
        "requires_human_review": True,
        "plan_mutated": False,
    }
    before = {"reconciliation_status": record.reconciliation_status, "reconciliation_result": record.reconciliation_result or {}}
    record.reconciliation_status = status_value
    record.reconciliation_result = result
    db.add(AuditEvent(
        user_id=current_user.id,
        action_type="FIELD_OBSERVATION_RECONCILIATION",
        entity_type="FieldObservation",
        entity_id=record.id,
        before_state=before,
        after_state=result,
        justification="Reconciled field evidence against snapshot state; operational plan was not mutated.",
    ))
    db.commit()
    response = FieldReconciliationDTO(
        observation_id=record.id,
        snapshot_id=record.snapshot_id,
        reconciliation_status=status_value,
        requires_human_review=True,
        expected_state=expected_state,
        observed_state=record.observed_state,
        conflict_reason=conflict_reason,
        plan_mutated=False,
    )
    return ResponseEnvelope[FieldReconciliationDTO](
        request_id=str(uuid.uuid4()), correlation_id=str(uuid.uuid4()), snapshot_id=record.snapshot_id, data=response
    )
