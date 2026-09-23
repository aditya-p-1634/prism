import json
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import HazardState, HazardPrediction, RedZone, HazardEvidence
from app.schemas.hazard import HazardStateDTO, HazardPredictionDTO, RedZoneDTO, HazardEvidenceDTO
from app.schemas.envelope import ResponseEnvelope

router = APIRouter(prefix="/hazards", tags=["Hazard Intelligence (E1)"])

@router.get("/current", response_model=ResponseEnvelope[List[HazardStateDTO]])
def get_current_hazards(
    snapshot_id: str = Query("SNAP_BASE_001", description="Target state snapshot"),
    db: Session = Depends(get_db)
):
    states = db.query(HazardState).filter(HazardState.snapshot_id == snapshot_id).all()
    dtos = [
        HazardStateDTO(
            id=s.id,
            study_area_id=s.study_area_id,
            snapshot_id=s.snapshot_id,
            hazard_type=s.hazard_type,
            severity=s.severity,
            geom_geojson=json.loads(s.geom),
            state_type=s.state_type,
            confidence=s.confidence
        )
        for s in states
    ]
    return ResponseEnvelope[List[HazardStateDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        confidence=0.95,
        data=dtos
    )

@router.get("/red-zones", response_model=ResponseEnvelope[List[RedZoneDTO]])
def get_red_zones(
    snapshot_id: str = Query("SNAP_BASE_001"),
    db: Session = Depends(get_db)
):
    rzs = db.query(RedZone).filter(RedZone.snapshot_id == snapshot_id).all()
    dtos = []
    for rz in rzs:
        evidences = [
            HazardEvidenceDTO(
                id=ev.id,
                metric_name=ev.metric_name,
                measured_value=ev.measured_value,
                threshold_value=ev.threshold_value,
                source_reference=ev.source_reference
            )
            for ev in rz.evidences
        ]
        dtos.append(RedZoneDTO(
            id=rz.id,
            study_area_id=rz.study_area_id,
            snapshot_id=rz.snapshot_id,
            designation_code=rz.designation_code,
            hazard_type=rz.hazard_type,
            geom_geojson=json.loads(rz.geom),
            operational_status=rz.operational_status,
            reason_code=rz.reason_code,
            evidences=evidences
        ))
    return ResponseEnvelope[List[RedZoneDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=dtos
    )
