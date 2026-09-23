import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import Habitation, Household, PriorityRecord
from app.schemas.people import HabitationDTO, HouseholdDTO, PriorityRecordDTO
from app.schemas.envelope import ResponseEnvelope

router = APIRouter(prefix="/people", tags=["People & Vulnerability Priority (E2)"])

@router.get("/habitations", response_model=ResponseEnvelope[List[HabitationDTO]])
def get_habitations(
    snapshot_id: str = Query("SNAP_BASE_001"),
    db: Session = Depends(get_db)
):
    habs = db.query(Habitation).all()
    dtos = []
    for h in habs:
        # Get priority breakdown
        prios = db.query(PriorityRecord).filter(
            PriorityRecord.habitation_id == h.id,
            PriorityRecord.snapshot_id == snapshot_id
        ).all()

        breakdown = {"IMMEDIATE": 0, "SHORT_TERM": 0, "MEDIUM_TERM": 0}
        for p in prios:
            breakdown[p.priority_class.value] = breakdown.get(p.priority_class.value, 0) + 1

        dtos.append(HabitationDTO(
            id=h.id,
            study_area_id=h.study_area_id,
            code=h.code,
            name=h.name,
            settlement_type=h.settlement_type,
            population_estimate=h.population_estimate,
            geom_geojson=json.loads(h.geom),
            centroid_geojson=json.loads(h.centroid_geom),
            elevation_m=h.elevation_m,
            total_households=len(prios),
            priority_breakdown=breakdown
        ))

    return ResponseEnvelope[List[HabitationDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=dtos
    )

@router.get("/priorities", response_model=ResponseEnvelope[List[PriorityRecordDTO]])
def get_priorities(
    snapshot_id: str = Query("SNAP_BASE_001"),
    db: Session = Depends(get_db)
):
    prios = db.query(PriorityRecord).filter(PriorityRecord.snapshot_id == snapshot_id).order_by(PriorityRecord.priority_score.desc()).all()
    hab_map = {h.id: h.name for h in db.query(Habitation).all()}
    hh_map = {hh.id: hh.anonymized_code for hh in db.query(Household).all()}

    dtos = [
        PriorityRecordDTO(
            id=p.id,
            habitation_id=p.habitation_id,
            household_id=p.household_id,
            snapshot_id=p.snapshot_id,
            habitation_name=hab_map.get(p.habitation_id),
            household_code=hh_map.get(p.household_id),
            priority_score=p.priority_score,
            priority_class=p.priority_class,
            reason_codes=p.reason_codes,
            component_scores=p.component_scores
        )
        for p in prios
    ]
    return ResponseEnvelope[List[PriorityRecordDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=dtos
    )
