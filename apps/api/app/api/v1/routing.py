import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import (
    RoutePlan, RelocationAllocation, RelocationGroup, Habitation, Destination, User, AuditEvent
)
from app.models.enums import RoleEnum, AllocationStatusEnum
from app.schemas.routing import RoutePlanDTO, RelocationAllocationDTO, RelocationOverrideDTO
from app.schemas.envelope import ResponseEnvelope
from app.api.deps import require_role, get_current_user

router = APIRouter(prefix="", tags=["Safe Routes & Relocation Optimization (E4)"])

@router.get("/routes", response_model=ResponseEnvelope[List[RoutePlanDTO]])
def get_routes(
    snapshot_id: str = Query("SNAP_BASE_001"),
    db: Session = Depends(get_db)
):
    routes = db.query(RoutePlan).filter(RoutePlan.snapshot_id == snapshot_id).all()
    hab_map = {h.id: h.name for h in db.query(Habitation).all()}
    dest_map = {d.id: d.name for d in db.query(Destination).all()}

    dtos = [
        RoutePlanDTO(
            id=r.id,
            origin_habitation_id=r.origin_habitation_id,
            destination_id=r.destination_id,
            snapshot_id=r.snapshot_id,
            origin_name=hab_map.get(r.origin_habitation_id),
            destination_name=dest_map.get(r.destination_id),
            total_distance_m=r.total_distance_m,
            total_time_min=r.total_time_min,
            route_cost=r.route_cost,
            geom_geojson=json.loads(r.geom),
            path_nodes=r.path_nodes,
            is_viable=r.is_viable,
            invalidated_reason=r.invalidated_reason
        )
        for r in routes
    ]
    return ResponseEnvelope[List[RoutePlanDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=dtos
    )

@router.get("/relocation/allocations", response_model=ResponseEnvelope[List[RelocationAllocationDTO]])
def get_allocations(
    snapshot_id: str = Query("SNAP_BASE_001"),
    db: Session = Depends(get_db)
):
    allocs = db.query(RelocationAllocation).filter(RelocationAllocation.snapshot_id == snapshot_id).all()
    hab_map = {h.id: h.name for h in db.query(Habitation).all()}
    dest_map = {d.id: d.name for d in db.query(Destination).all()}
    group_map = {g.id: g for g in db.query(RelocationGroup).all()}

    dtos = []
    for a in allocs:
        g = group_map.get(a.group_id)
        hab_name = hab_map.get(g.habitation_id) if g else None
        dest_name = dest_map.get(a.destination_id) if a.destination_id else "UNMET DEMAND"

        dtos.append(RelocationAllocationDTO(
            id=a.id,
            group_id=a.group_id,
            destination_id=a.destination_id,
            route_plan_id=a.route_plan_id,
            snapshot_id=a.snapshot_id,
            habitation_name=hab_name,
            destination_name=dest_name,
            allocation_status=a.allocation_status,
            assigned_capacity_count=a.assigned_capacity_count,
            reason_code=a.reason_code
        ))

    return ResponseEnvelope[List[RelocationAllocationDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=dtos
    )

@router.post("/relocation/override", response_model=ResponseEnvelope[RelocationAllocationDTO])
def override_allocation(
    payload: RelocationOverrideDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN])),
    db: Session = Depends(get_db)
):
    alloc = db.query(RelocationAllocation).filter(RelocationAllocation.id == payload.allocation_id).first()
    if not alloc:
        raise HTTPException(status_code=404, detail="Allocation not found")

    new_dest = db.query(Destination).filter(Destination.id == payload.new_destination_id).first()
    if not new_dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    before_state = {
        "destination_id": alloc.destination_id,
        "status": alloc.allocation_status.value,
        "reason_code": alloc.reason_code
    }

    alloc.destination_id = new_dest.id
    alloc.allocation_status = AllocationStatusEnum.OVERRIDDEN
    alloc.reason_code = f"AUTHORITY_OVERRIDE: {payload.justification}"

    after_state = {
        "destination_id": alloc.destination_id,
        "status": alloc.allocation_status.value,
        "reason_code": alloc.reason_code
    }

    # Record tamper-evident audit trail
    audit = AuditEvent(
        user_id=current_user.id if current_user else None,
        action_type="AUTHORITY_ALLOCATION_OVERRIDE",
        entity_type="RELOCATION_ALLOCATION",
        entity_id=alloc.id,
        before_state=before_state,
        after_state=after_state,
        justification=payload.justification
    )
    db.add(audit)
    db.commit()
    db.refresh(alloc)

    hab_map = {h.id: h.name for h in db.query(Habitation).all()}
    dest_map = {d.id: d.name for d in db.query(Destination).all()}
    group_map = {g.id: g for g in db.query(RelocationGroup).all()}
    g = group_map.get(alloc.group_id)

    dto = RelocationAllocationDTO(
        id=alloc.id,
        group_id=alloc.group_id,
        destination_id=alloc.destination_id,
        route_plan_id=alloc.route_plan_id,
        snapshot_id=alloc.snapshot_id,
        habitation_name=hab_map.get(g.habitation_id) if g else None,
        destination_name=dest_map.get(alloc.destination_id),
        allocation_status=alloc.allocation_status,
        assigned_capacity_count=alloc.assigned_capacity_count,
        reason_code=alloc.reason_code
    )

    return ResponseEnvelope[RelocationAllocationDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=alloc.snapshot_id,
        data=dto
    )
