import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    SimulationRun, SimulationEvent, User, Destination,
    CapacityState, RelocationAllocation, SimulationResourceState
)
from app.models.enums import RoleEnum, EvacuationStateEnum, SimulationEventTypeEnum
from app.schemas.simulation import (
    SimulationRunCreateDTO, SimulationRunResponseDTO,
    SimulationStepResponseDTO, SimulationEventDTO, SimulationRunExecuteDTO,
    ResourceStateDTO, DestinationResourceSummaryDTO, SimulationResourcesResponseDTO,
    ConsolidatedSimulationStateDTO, SimulationOperationalMetricsDTO,
    SimulationTimelineResponseDTO, SimulationTimelineEventDTO
)
from app.schemas.envelope import ResponseEnvelope
from app.api.deps import require_role, get_current_user
from app.engines.e5_simulation.temporal_engine import TemporalSimulationEngine
from app.engines.e5_simulation.observability_service import SimulationObservabilityService


router = APIRouter(prefix="/simulation-runs", tags=["Predictive Simulation & Adaptation (E5)"])


def _to_run_dto(run: SimulationRun) -> SimulationRunResponseDTO:
    return SimulationRunResponseDTO(
        id=run.id,
        scenario_id=run.scenario_id,
        scenario_snapshot_id=run.scenario_snapshot_id,
        status=run.status,
        timestep_minutes=run.timestep_minutes,
        duration_minutes=run.duration_minutes,
        current_simulation_time=run.current_simulation_time,
        ticks_completed=run.ticks_completed,
        total_ticks=run.total_ticks,
        parameters=run.parameters,
        summary_metrics=run.summary_metrics,
        created_at=run.created_at,
        updated_at=run.updated_at
    )


def _to_event_dto(e: SimulationEvent) -> SimulationEventDTO:
    return SimulationEventDTO(
        id=e.id,
        simulation_run_id=e.simulation_run_id,
        simulation_time_min=e.simulation_time_min,
        tick_index=e.tick_index,
        event_type=e.event_type,
        entity_type=e.entity_type,
        entity_id=e.entity_id,
        details=e.details,
        created_at=e.created_at
    )


@router.post("", response_model=ResponseEnvelope[SimulationRunResponseDTO])
def create_simulation_run(
    payload: SimulationRunCreateDTO,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    engine = TemporalSimulationEngine(db)
    run = engine.create_simulation_run(
        scenario_code=payload.scenario_code,
        scenario_snapshot_id=payload.scenario_snapshot_id,
        timestep_minutes=payload.timestep_minutes,
        duration_minutes=payload.duration_minutes,
        parameter_overrides=payload.parameter_overrides,
        auto_admit_shelter=payload.auto_admit_shelter
    )

    dto = _to_run_dto(run)
    return ResponseEnvelope[SimulationRunResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=run.scenario_snapshot_id,
        data=dto
    )


@router.get("/{run_id}", response_model=ResponseEnvelope[SimulationRunResponseDTO])
def get_simulation_run(
    run_id: str,
    db: Session = Depends(get_db)
):
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found."
        )

    dto = _to_run_dto(run)
    return ResponseEnvelope[SimulationRunResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=run.scenario_snapshot_id,
        data=dto
    )


@router.post("/{run_id}/step", response_model=ResponseEnvelope[SimulationStepResponseDTO])
def step_simulation_run(
    run_id: str,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    engine = TemporalSimulationEngine(db)
    res = engine.step_simulation(run_id)

    step_dto = SimulationStepResponseDTO(
        run=_to_run_dto(res["run"]),
        tick_index=res["tick_index"],
        simulation_time_min=res["simulation_time_min"],
        events_generated=[_to_event_dto(e) for e in res["events_generated"]],
        state_summary=res["state_summary"]
    )

    return ResponseEnvelope[SimulationStepResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=res["run"].scenario_snapshot_id,
        data=step_dto
    )


@router.post("/{run_id}/run", response_model=ResponseEnvelope[Dict[str, Any]])
def execute_simulation_run(
    run_id: str,
    payload: Optional[SimulationRunExecuteDTO] = None,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    max_steps = payload.max_steps if payload else None
    engine = TemporalSimulationEngine(db)
    res = engine.run_simulation(run_id, max_steps=max_steps)

    run_dto = _to_run_dto(res["run"])
    return ResponseEnvelope[Dict[str, Any]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=res["run"].scenario_snapshot_id,
        data={
            "run": run_dto.model_dump(),
            "steps_executed": res["steps_executed"],
            "total_events_generated": res["total_events_generated"],
            "final_status": res["final_status"],
            "current_simulation_time": res["current_simulation_time"],
            "metrics": res["metrics"]
        }
    )


@router.post("/{run_id}/pause", response_model=ResponseEnvelope[SimulationRunResponseDTO])
def pause_simulation_run(
    run_id: str,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    engine = TemporalSimulationEngine(db)
    run = engine.pause_simulation(run_id)

    dto = _to_run_dto(run)
    return ResponseEnvelope[SimulationRunResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=run.scenario_snapshot_id,
        data=dto
    )


@router.get("/{run_id}/events", response_model=ResponseEnvelope[List[SimulationEventDTO]])
def get_simulation_events(
    run_id: str,
    db: Session = Depends(get_db)
):
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found."
        )

    events = db.query(SimulationEvent).filter(
        SimulationEvent.simulation_run_id == run_id
    ).order_by(SimulationEvent.simulation_time_min.asc(), SimulationEvent.created_at.asc()).all()

    dtos = [_to_event_dto(e) for e in events]
    return ResponseEnvelope[List[SimulationEventDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=run.scenario_snapshot_id,
        data=dtos
    )


@router.get("/{run_id}/resources", response_model=ResponseEnvelope[SimulationResourcesResponseDTO])
def get_simulation_resources(
    run_id: str,
    db: Session = Depends(get_db)
):
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SIMULATION_RUN_NOT_FOUND: Simulation run '{run_id}' not found."
        )

    res_states = db.query(SimulationResourceState).filter(
        SimulationResourceState.simulation_run_id == run_id
    ).all()

    destinations = db.query(Destination).all()
    allocs = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == run.scenario_snapshot_id
    ).all()
    cap_states = db.query(CapacityState).filter(
        CapacityState.snapshot_id == run.scenario_snapshot_id
    ).all()
    cap_map = {cs.destination_id: cs for cs in cap_states}

    dest_summaries: List[DestinationResourceSummaryDTO] = []
    for d in destinations:
        d_states = [s for s in res_states if s.destination_id == d.id]
        d_allocs = [a for a in allocs if a.destination_id == d.id]

        sheltered_pop = sum(
            a.assigned_capacity_count for a in d_allocs
            if a.evacuation_state in [EvacuationStateEnum.ARRIVED, EvacuationStateEnum.SHELTERED]
        )
        uncommitted_demand = sum(
            a.assigned_capacity_count for a in d_allocs
            if a.evacuation_state in [
                EvacuationStateEnum.PLANNED, EvacuationStateEnum.NOTIFIED,
                EvacuationStateEnum.ACKNOWLEDGED, EvacuationStateEnum.EVACUATION_ORDERED
            ]
        )

        cap_st = cap_map.get(d.id)
        effective_cap = cap_st.effective_capacity if cap_st else 0
        rem_cap = cap_st.remaining_capacity if cap_st else 0
        bottleneck = cap_st.bottleneck_resource if cap_st else "SHELTER"
        is_safe = cap_st.is_safe if cap_st else True
        is_feasible = is_safe and (rem_cap >= uncommitted_demand)

        resource_dtos = [
            ResourceStateDTO(
                id=s.id,
                destination_id=s.destination_id,
                resource_category=s.resource_category,
                resource_type=s.resource_type.value,
                total_quantity=s.total_quantity,
                consumed_quantity=s.consumed_quantity,
                remaining_quantity=s.remaining_quantity,
                unit=s.unit,
                supportable_population=s.supportable_population,
                status=s.status
            ) for s in d_states
        ]

        dest_summaries.append(DestinationResourceSummaryDTO(
            destination_id=d.id,
            destination_code=d.code,
            destination_name=d.name,
            is_safe=is_safe,
            is_feasible=is_feasible,
            effective_capacity=effective_cap,
            occupied_population=sheltered_pop,
            effective_remaining_capacity=rem_cap,
            uncommitted_planned_demand=uncommitted_demand,
            bottleneck_resource=bottleneck,
            resources=resource_dtos
        ))

    response_data = SimulationResourcesResponseDTO(
        simulation_run_id=run.id,
        simulation_time_min=run.current_simulation_time,
        tick_index=run.ticks_completed,
        destinations=dest_summaries
    )

    return ResponseEnvelope[SimulationResourcesResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=run.scenario_snapshot_id,
        data=response_data
    )


# -------------------------------------------------------------
# Phase A.5 Observability & Control Endpoints
# -------------------------------------------------------------

@router.get("/{run_id}/state", response_model=ResponseEnvelope[ConsolidatedSimulationStateDTO])
def get_simulation_state(
    run_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns consolidated read-only operational state of the simulation.
    Performs zero mutations on database or snapshots.
    """
    state = SimulationObservabilityService.get_consolidated_state(db, run_id)
    return ResponseEnvelope[ConsolidatedSimulationStateDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=state.snapshot_id,
        data=state
    )


@router.get("/{run_id}/metrics", response_model=ResponseEnvelope[SimulationOperationalMetricsDTO])
def get_simulation_metrics(
    run_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns derived operational metrics for the simulation.
    Read-only, strictly deterministic.
    """
    metrics = SimulationObservabilityService.get_operational_metrics(db, run_id)
    return ResponseEnvelope[SimulationOperationalMetricsDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=metrics.snapshot_id,
        data=metrics
    )


@router.get("/{run_id}/timeline", response_model=ResponseEnvelope[SimulationTimelineResponseDTO])
def get_simulation_timeline(
    run_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    event_type: Optional[SimulationEventTypeEnum] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns chronological simulation event history with deterministic ordering
    and factual human-readable event summaries.
    """
    timeline = SimulationObservabilityService.get_simulation_timeline(
        db=db,
        run_id=run_id,
        limit=limit,
        offset=offset,
        event_type=event_type
    )
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    snapshot_id = run.scenario_snapshot_id if run else "UNKNOWN"

    return ResponseEnvelope[SimulationTimelineResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=timeline
    )


@router.post("/{run_id}/resume", response_model=ResponseEnvelope[SimulationRunResponseDTO])
def resume_simulation_run(
    run_id: str,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    """Resumes a paused simulation run."""
    engine = TemporalSimulationEngine(db)
    run = engine.resume_simulation(run_id)

    dto = _to_run_dto(run)
    return ResponseEnvelope[SimulationRunResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=run.scenario_snapshot_id,
        data=dto
    )


@router.post("/{run_id}/cancel", response_model=ResponseEnvelope[SimulationRunResponseDTO])
def cancel_simulation_run(
    run_id: str,
    current_user: User = Depends(require_role([RoleEnum.AUTHORITY, RoleEnum.ADMIN, RoleEnum.DATA_OPERATOR])),
    db: Session = Depends(get_db)
):
    """Cancels an active or paused simulation run."""
    engine = TemporalSimulationEngine(db)
    run = engine.cancel_simulation(run_id)

    dto = _to_run_dto(run)
    return ResponseEnvelope[SimulationRunResponseDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=run.scenario_snapshot_id,
        data=dto
    )


