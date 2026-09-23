import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import Scenario, StateSnapshot
from app.schemas.scenario import ScenarioDTO, ScenarioRunRequestDTO, DeltaReportDTO
from app.schemas.envelope import ResponseEnvelope
from app.engines.e5_simulation.service import SimulationEngineE5

router = APIRouter(prefix="/scenarios", tags=["Predictive Simulation & Adaptation (E5)"])

@router.get("", response_model=ResponseEnvelope[List[ScenarioDTO]])
def list_scenarios(db: Session = Depends(get_db)):
    scenarios = db.query(Scenario).all()
    dtos = [
        ScenarioDTO(
            id=s.id,
            code=s.code,
            name=s.name,
            description=s.description,
            parameters=s.parameters
        )
        for s in scenarios
    ]
    return ResponseEnvelope[List[ScenarioDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        data=dtos
    )

@router.post("/run", response_model=ResponseEnvelope[DeltaReportDTO])
def run_scenario(
    payload: ScenarioRunRequestDTO,
    db: Session = Depends(get_db)
):
    baseline_snapshot = db.query(StateSnapshot).filter(StateSnapshot.id == "SNAP_BASE_001").first()
    if not baseline_snapshot:
        raise HTTPException(status_code=400, detail="Baseline snapshot SNAP_BASE_001 not found.")

    e5 = SimulationEngineE5(db)
    try:
        delta = e5.execute_scenario(
            scenario_code=payload.scenario_code,
            baseline_snapshot_id=baseline_snapshot.id,
            overrides=payload.parameter_overrides
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {str(ve)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scenario execution failed: {str(e)}")

    delta_dto = DeltaReportDTO(
        scenario_code=delta["scenario_code"],
        baseline_snapshot_id=delta["baseline_snapshot_id"],
        scenario_snapshot_id=delta["scenario_snapshot_id"],
        hazard_delta=delta["hazard_delta"],
        priority_shifts=delta["priority_shifts"],
        capacity_changes=delta["capacity_changes"],
        route_invalidations=delta["route_invalidations"],
        reallocated_groups_count=delta["reallocated_groups_count"],
        unmet_demand_delta=delta["unmet_demand_delta"],
        summary_explanation=delta["summary_explanation"]
    )

    return ResponseEnvelope[DeltaReportDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=delta["scenario_snapshot_id"],
        scenario_id=payload.scenario_code,
        data=delta_dto
    )
