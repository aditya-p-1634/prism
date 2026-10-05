import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import (
    RoutePlan, RelocationAllocation, RelocationGroup, Habitation, Destination, User, AuditEvent, RoadSegment,
    StateSnapshot, CapacityState, HazardState, RedZone, RoadNode, Scenario
)
from app.models.enums import RoleEnum, AllocationStatusEnum, OperationalStatusEnum, EvacuationStateEnum
from app.schemas.routing import (
    RoutePlanDTO, RelocationAllocationDTO, RelocationOverrideDTO, RoadSegmentDTO,
    EvacuationStateTransitionDTO, EvacuationStateResponseDTO
)
from app.schemas.envelope import ResponseEnvelope
from app.api.deps import require_role, get_current_user
from app.engines.e4_route_relocation.service import RouteAndRelocationEngineE4
from app.engines.e5_simulation.state_machine import EvacuationStateMachine
from app.gis.spatial import to_shapely, intersects

router = APIRouter(prefix="", tags=["Safe Routes & Relocation Optimization (E4)"])

@router.get("/road-segments", response_model=ResponseEnvelope[List[RoadSegmentDTO]])
def get_road_segments(db: Session = Depends(get_db)):
    segments = db.query(RoadSegment).all()
    dtos = [
        RoadSegmentDTO(
            id=s.id,
            segment_code=s.segment_code,
            u_node_id=s.u_node_id,
            v_node_id=s.v_node_id,
            road_class=s.road_class,
            length_meters=s.length_meters,
            max_speed_kmh=s.max_speed_kmh,
            geom_geojson=json.loads(s.geom),
            operational_status=s.operational_status,
            hazard_risk_score=s.hazard_risk_score,
            is_bridge=s.is_bridge
        )
        for s in segments
    ]
    return ResponseEnvelope[List[RoadSegmentDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        data=dtos
    )

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
            evacuation_state=a.evacuation_state,
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
    # 0. Validate Payload Input
    if not payload.justification or not payload.justification.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_OVERRIDE: Mandatory operational justification is required for authority overrides."
        )

    # 1. Lookup Allocation
    alloc = db.query(RelocationAllocation).filter(
        (RelocationAllocation.id == payload.allocation_id) | (RelocationAllocation.group_id == payload.allocation_id)
    ).first()
    if not alloc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ALLOCATION_NOT_FOUND: Allocation record '{payload.allocation_id}' not found."
        )

    # 2. Invariant 1: Snapshot Lookup & Baseline Immutability
    snapshot = db.query(StateSnapshot).filter(StateSnapshot.id == alloc.snapshot_id).first()
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SNAPSHOT_NOT_FOUND: Snapshot '{alloc.snapshot_id}' associated with allocation not found."
        )

    if snapshot.id == "SNAP_BASE_001" or snapshot.snapshot_type == "BASELINE" or snapshot.is_immutable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"BASELINE_IMMUTABLE: Canonical baseline snapshot '{snapshot.id}' is strictly immutable. "
                   f"Authority overrides cannot directly mutate baseline state. "
                   f"Please run or select an active scenario branch before applying overrides."
        )

    # 3. Lookup New Destination
    new_dest = db.query(Destination).filter(
        (Destination.id == payload.new_destination_id) | (Destination.code == payload.new_destination_id)
    ).first()
    if not new_dest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DESTINATION_NOT_FOUND: Target destination '{payload.new_destination_id}' not found."
        )

    # 4. Invariant 2: Destination Safety Validation
    # 4a. Check Operational Status
    if new_dest.operational_status == OperationalStatusEnum.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DESTINATION_UNSAFE: Target destination '{new_dest.code}' ({new_dest.name}) is operationally CLOSED in snapshot '{alloc.snapshot_id}'."
        )

    # 4b. Check CapacityState Safety in Current Snapshot
    dest_cap = db.query(CapacityState).filter(
        CapacityState.destination_id == new_dest.id,
        CapacityState.snapshot_id == alloc.snapshot_id
    ).first()

    if dest_cap and (not dest_cap.is_safe or dest_cap.rejection_reason):
        reason = dest_cap.rejection_reason or "UNSAFE_DESTINATION"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DESTINATION_UNSAFE: Target destination '{new_dest.code}' ({new_dest.name}) is marked unsafe in snapshot '{alloc.snapshot_id}'. Reason: {reason}."
        )

    # 4c. Check Spatial Hazard / Inundation
    dest_pt = to_shapely(new_dest.location_geom)
    hazard_state = db.query(HazardState).filter(HazardState.snapshot_id == alloc.snapshot_id).first()
    if hazard_state:
        flood_geom = to_shapely(hazard_state.geom)
        if intersects(dest_pt, flood_geom):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DESTINATION_UNSAFE: Target destination '{new_dest.code}' ({new_dest.name}) is submerged under floodwaters in snapshot '{alloc.snapshot_id}'."
            )

    red_zones = db.query(RedZone).filter(RedZone.snapshot_id == alloc.snapshot_id).all()
    for rz in red_zones:
        rz_geom = to_shapely(rz.geom)
        if intersects(dest_pt, rz_geom):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DESTINATION_UNSAFE: Target destination '{new_dest.code}' ({new_dest.name}) intersects active Red Zone '{rz.designation_code}' ({rz.reason_code}) in snapshot '{alloc.snapshot_id}'."
            )

    # 5. Lookup Group & Habitation
    group = db.query(RelocationGroup).filter(RelocationGroup.id == alloc.group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RELOCATION_GROUP_NOT_FOUND: Relocation group '{alloc.group_id}' not found."
        )

    hab = db.query(Habitation).filter(Habitation.id == group.habitation_id).first()
    if not hab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HABITATION_NOT_FOUND: Origin habitation '{group.habitation_id}' not found."
        )

    # 6. Invariant 3: Route Feasibility Validation
    viable_route = db.query(RoutePlan).filter(
        RoutePlan.origin_habitation_id == hab.id,
        RoutePlan.destination_id == new_dest.id,
        RoutePlan.snapshot_id == alloc.snapshot_id,
        RoutePlan.is_viable == True
    ).first()

    if not viable_route:
        # Check scenario closed segments if snapshot is tied to a scenario
        closed_segments = []
        if snapshot.scenario_id:
            scenario = db.query(Scenario).filter(Scenario.id == snapshot.scenario_id).first()
            if scenario and scenario.parameters:
                closed_segments = scenario.parameters.get("closed_road_segments", [])

        # Dynamically verify with E4 routing engine across current snapshot road network
        e4 = RouteAndRelocationEngineE4()
        road_nodes = db.query(RoadNode).all()
        road_segments = db.query(RoadSegment).filter(RoadSegment.study_area_id == hab.study_area_id).all()

        eval_segments = []
        for s in road_segments:
            is_closed = (s.segment_code in closed_segments) or (s.operational_status == OperationalStatusEnum.CLOSED)
            cloned_s = RoadSegment(
                id=s.id,
                study_area_id=s.study_area_id,
                segment_code=s.segment_code,
                u_node_id=s.u_node_id,
                v_node_id=s.v_node_id,
                road_class=s.road_class,
                length_meters=s.length_meters,
                max_speed_kmh=s.max_speed_kmh,
                geom=s.geom,
                operational_status=OperationalStatusEnum.CLOSED if is_closed else s.operational_status,
                hazard_risk_score=s.hazard_risk_score,
                is_bridge=s.is_bridge
            )
            eval_segments.append(cloned_s)

        current_flood = to_shapely(hazard_state.geom) if hazard_state else to_shapely(hab.geom)
        G, _ = e4.build_network_graph(road_nodes, eval_segments, current_flood, current_flood)
        computed_route = e4.find_safe_route(G, hab, new_dest, road_nodes, alloc.snapshot_id)

        if not computed_route or not computed_route.is_viable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"NO_VIABLE_ROUTE: No safe, viable evacuation route exists from '{hab.name}' ({hab.code}) to destination '{new_dest.name}' ({new_dest.code}) in snapshot '{alloc.snapshot_id}'. Route cannot traverse closed bridge (BRIDGE_01) or inundated road segments."
            )
        else:
            db.add(computed_route)
            db.flush()
            viable_route = computed_route

    # 7. Invariant 4: Destination Capacity Consistency
    if not dest_cap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DESTINATION_CAPACITY_EXCEEDED: No capacity record found for destination '{new_dest.code}' in snapshot '{alloc.snapshot_id}'."
        )

    group_size = group.group_size if group.group_size > 0 else (alloc.assigned_capacity_count if alloc.assigned_capacity_count > 0 else 1)
    old_dest_id = alloc.destination_id

    # If reallocating to a different destination, check capacity headroom
    if new_dest.id != old_dest_id:
        if group_size > dest_cap.remaining_capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DESTINATION_CAPACITY_EXCEEDED: Destination '{new_dest.code}' ({new_dest.name}) has insufficient capacity. "
                       f"Required: {group_size}, Remaining: {dest_cap.remaining_capacity}, Effective: {dest_cap.effective_capacity}, Occupied: {dest_cap.occupied_capacity}."
            )

        # Release capacity from old destination if one was assigned
        if old_dest_id:
            old_cap = db.query(CapacityState).filter(
                CapacityState.destination_id == old_dest_id,
                CapacityState.snapshot_id == alloc.snapshot_id
            ).first()
            if old_cap:
                old_cap.occupied_capacity = max(0, old_cap.occupied_capacity - group_size)
                old_cap.remaining_capacity = max(0, old_cap.effective_capacity - old_cap.occupied_capacity)

        # Consume capacity at new destination
        dest_cap.occupied_capacity = dest_cap.occupied_capacity + group_size
        dest_cap.remaining_capacity = max(0, dest_cap.effective_capacity - dest_cap.occupied_capacity)

    # 8. Invariant 5 & 6: Transactional Mutation & Audit Logging
    old_dest = db.query(Destination).filter(Destination.id == old_dest_id).first() if old_dest_id else None

    before_state = {
        "snapshot_id": alloc.snapshot_id,
        "allocation_id": alloc.id,
        "group_id": alloc.group_id,
        "origin_habitation": hab.code,
        "destination_id": old_dest_id,
        "destination_code": old_dest.code if old_dest else None,
        "route_plan_id": alloc.route_plan_id,
        "status": alloc.allocation_status.value if hasattr(alloc.allocation_status, 'value') else str(alloc.allocation_status),
        "evacuation_state": alloc.evacuation_state.value if hasattr(alloc.evacuation_state, 'value') else str(alloc.evacuation_state),
        "assigned_capacity_count": alloc.assigned_capacity_count,
        "reason_code": alloc.reason_code,
        "new_dest_capacity_before": {
            "effective": dest_cap.effective_capacity,
            "occupied": dest_cap.occupied_capacity - (group_size if new_dest.id != old_dest_id else 0),
            "remaining": dest_cap.remaining_capacity + (group_size if new_dest.id != old_dest_id else 0)
        }
    }

    # Apply mutation to allocation record
    alloc.destination_id = new_dest.id
    alloc.route_plan_id = viable_route.id
    alloc.assigned_capacity_count = group_size
    alloc.allocation_status = AllocationStatusEnum.OVERRIDDEN
    alloc.reason_code = f"AUTHORITY_OVERRIDE: {payload.justification.strip()}"

    after_state = {
        "snapshot_id": alloc.snapshot_id,
        "allocation_id": alloc.id,
        "group_id": alloc.group_id,
        "origin_habitation": hab.code,
        "destination_id": new_dest.id,
        "destination_code": new_dest.code,
        "route_plan_id": viable_route.id,
        "status": alloc.allocation_status.value if hasattr(alloc.allocation_status, 'value') else str(alloc.allocation_status),
        "evacuation_state": alloc.evacuation_state.value if hasattr(alloc.evacuation_state, 'value') else str(alloc.evacuation_state),
        "assigned_capacity_count": alloc.assigned_capacity_count,
        "reason_code": alloc.reason_code,
        "new_dest_capacity_after": {
            "effective": dest_cap.effective_capacity,
            "occupied": dest_cap.occupied_capacity,
            "remaining": dest_cap.remaining_capacity
        }
    }

    audit = AuditEvent(
        user_id=current_user.id if current_user else None,
        action_type="AUTHORITY_ALLOCATION_OVERRIDE",
        entity_type="RELOCATION_ALLOCATION",
        entity_id=alloc.id,
        before_state=before_state,
        after_state=after_state,
        justification=payload.justification.strip()
    )
    db.add(audit)

    try:
        db.commit()
        db.refresh(alloc)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TRANSACTION_FAILED: Failed to atomically commit authority override: {str(e)}"
        )

    # 9. Format and return Response DTO
    hab_map = {h.id: h.name for h in db.query(Habitation).all()}
    dest_map = {d.id: d.name for d in db.query(Destination).all()}

    dto = RelocationAllocationDTO(
        id=alloc.id,
        group_id=alloc.group_id,
        destination_id=alloc.destination_id,
        route_plan_id=alloc.route_plan_id,
        snapshot_id=alloc.snapshot_id,
        habitation_name=hab_map.get(hab.id),
        destination_name=dest_map.get(alloc.destination_id),
        allocation_status=alloc.allocation_status,
        evacuation_state=alloc.evacuation_state,
        assigned_capacity_count=alloc.assigned_capacity_count,
        reason_code=alloc.reason_code
    )

    return ResponseEnvelope[RelocationAllocationDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=alloc.snapshot_id,
        data=dto
    )

@router.post("/relocation-allocations/{allocation_id}/state", response_model=ResponseEnvelope[RelocationAllocationDTO])
@router.post("/evacuation/{allocation_id}/transition", response_model=ResponseEnvelope[RelocationAllocationDTO])
def transition_allocation_state(
    allocation_id: str,
    payload: EvacuationStateTransitionDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    alloc = EvacuationStateMachine.transition_state(
        db=db,
        allocation_id=allocation_id,
        to_state=payload.to_state,
        justification=payload.justification,
        current_user=current_user,
        expected_current_state=payload.expected_current_state
    )

    hab_map = {h.id: h.name for h in db.query(Habitation).all()}
    dest_map = {d.id: d.name for d in db.query(Destination).all()}
    group = db.query(RelocationGroup).filter(RelocationGroup.id == alloc.group_id).first()

    dto = RelocationAllocationDTO(
        id=alloc.id,
        group_id=alloc.group_id,
        destination_id=alloc.destination_id,
        route_plan_id=alloc.route_plan_id,
        snapshot_id=alloc.snapshot_id,
        habitation_name=hab_map.get(group.habitation_id) if group else None,
        destination_name=dest_map.get(alloc.destination_id) if alloc.destination_id else "UNMET DEMAND",
        allocation_status=alloc.allocation_status,
        evacuation_state=alloc.evacuation_state,
        assigned_capacity_count=alloc.assigned_capacity_count,
        reason_code=alloc.reason_code
    )

    return ResponseEnvelope[RelocationAllocationDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=alloc.snapshot_id,
        data=dto
    )

@router.get("/relocation-allocations/{allocation_id}/state", response_model=ResponseEnvelope[EvacuationStateResponseDTO])
def get_allocation_state(
    allocation_id: str,
    db: Session = Depends(get_db)
):
    alloc = db.query(RelocationAllocation).filter(RelocationAllocation.id == allocation_id).first()
    if not alloc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ALLOCATION_NOT_FOUND: Relocation allocation '{allocation_id}' not found."
        )

    dto = EvacuationStateResponseDTO(
        allocation_id=alloc.id,
        snapshot_id=alloc.snapshot_id,
        group_id=alloc.group_id,
        allocation_status=alloc.allocation_status,
        evacuation_state=alloc.evacuation_state,
        allowed_transitions=EvacuationStateMachine.get_allowed_transitions(alloc.evacuation_state)
    )

    return ResponseEnvelope[EvacuationStateResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=alloc.snapshot_id,
        data=dto
    )
