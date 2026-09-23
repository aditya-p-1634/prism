import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import Destination, DestinationResource, CapacityState
from app.schemas.destination import DestinationDTO, DestinationResourceDTO, CapacityStateDTO
from app.schemas.envelope import ResponseEnvelope

router = APIRouter(prefix="/destinations", tags=["Destinations & Carrying Capacity (E3)"])

@router.get("", response_model=ResponseEnvelope[List[DestinationDTO]])
def get_destinations(
    snapshot_id: str = Query("SNAP_BASE_001"),
    db: Session = Depends(get_db)
):
    dests = db.query(Destination).all()
    dtos = []

    for d in dests:
        cap = db.query(CapacityState).filter(
            CapacityState.destination_id == d.id,
            CapacityState.snapshot_id == snapshot_id
        ).first()

        cap_dto = None
        if cap:
            cap_dto = CapacityStateDTO(
                id=cap.id,
                destination_id=cap.destination_id,
                snapshot_id=cap.snapshot_id,
                effective_capacity=cap.effective_capacity,
                occupied_capacity=cap.occupied_capacity,
                remaining_capacity=cap.remaining_capacity,
                bottleneck_resource=cap.bottleneck_resource,
                is_safe=cap.is_safe,
                rejection_reason=cap.rejection_reason
            )

        resources = db.query(DestinationResource).filter(
            DestinationResource.destination_id == d.id,
            DestinationResource.snapshot_id == snapshot_id
        ).all()

        res_dtos = [
            DestinationResourceDTO(
                id=r.id,
                destination_id=r.destination_id,
                resource_type=r.resource_type,
                quantity=r.quantity,
                unit=r.unit,
                supportable_population=r.supportable_population,
                is_critical=r.is_critical
            )
            for r in resources
        ]

        dtos.append(DestinationDTO(
            id=d.id,
            study_area_id=d.study_area_id,
            code=d.code,
            name=d.name,
            facility_type=d.facility_type,
            location_geojson=json.loads(d.location_geom),
            operational_status=d.operational_status,
            suitability_score=d.suitability_score,
            capacity_state=cap_dto,
            resources=res_dtos
        ))

    return ResponseEnvelope[List[DestinationDTO]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=dtos
    )
