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

@router.get("/households", response_model=ResponseEnvelope[List[HouseholdDTO]])
def get_households(
    habitation_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Household)
    if habitation_id:
        query = query.filter(Household.habitation_id == habitation_id)
    households = query.all()
    dtos = [
        HouseholdDTO(
            id=h.id,
            habitation_id=h.habitation_id,
            anonymized_code=h.anonymized_code,
            member_count=h.member_count,
            vulnerable_elderly=h.vulnerable_elderly,
            vulnerable_children=h.vulnerable_children,
            mobility_impaired=h.mobility_impaired,
            assistance_required=h.assistance_required,
            has_partial_data=h.has_partial_data
        )
        for h in households
    ]
    return ResponseEnvelope[List[HouseholdDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        data=dtos
    )

@router.get("/priorities", response_model=ResponseEnvelope[List[PriorityRecordDTO]])
def get_priorities(
    snapshot_id: str = Query("SNAP_BASE_001"),
    db: Session = Depends(get_db)
):
    prios = db.query(PriorityRecord).filter(PriorityRecord.snapshot_id == snapshot_id).order_by(PriorityRecord.priority_score.desc()).all()
    hab_map = {h.id: h.name for h in db.query(Habitation).all()}
    hh_map = {hh.id: hh for hh in db.query(Household).all()}

    dtos = []
    for p in prios:
        hh = hh_map.get(p.household_id)
        dtos.append(
            PriorityRecordDTO(
                id=p.id,
                habitation_id=p.habitation_id,
                household_id=p.household_id,
                snapshot_id=p.snapshot_id,
                habitation_name=hab_map.get(p.habitation_id),
                household_code=hh.anonymized_code if hh else p.household_id,
                priority_score=p.priority_score,
                priority_class=p.priority_class,
                reason_codes=p.reason_codes,
                component_scores=p.component_scores,
                member_count=hh.member_count if hh else 1,
                vulnerable_elderly=hh.vulnerable_elderly if hh else 0,
                vulnerable_children=hh.vulnerable_children if hh else 0,
                mobility_impaired=hh.mobility_impaired if hh else 0,
                assistance_required=hh.assistance_required if hh else False,
                has_partial_data=hh.has_partial_data if hh else False
            )
        )

    return ResponseEnvelope[List[PriorityRecordDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=dtos
    )

