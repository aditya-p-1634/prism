import json
import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import (
    StateSnapshot, StudyArea, HazardState, RedZone, Habitation, Household,
    PriorityRecord, Destination, CapacityState, RoadSegment, RoutePlan, RelocationAllocation
)
from app.models.enums import PriorityClassEnum, AllocationStatusEnum
from app.schemas.envelope import ResponseEnvelope

router = APIRouter(prefix="/dashboard", tags=["Command Dashboard & Read Models (B10)"])

@router.get("/overview", response_model=ResponseEnvelope[Dict[str, Any]])
def get_dashboard_overview(
    snapshot_id: str = Query("SNAP_BASE_001", description="Target state snapshot ID"),
    db: Session = Depends(get_db)
):
    snapshot = db.query(StateSnapshot).filter(StateSnapshot.id == snapshot_id).first()
    study_area = db.query(StudyArea).first()

    # 1. Hazard Layers
    hazard = db.query(HazardState).filter(HazardState.snapshot_id == snapshot_id).first()
    red_zones = db.query(RedZone).filter(RedZone.snapshot_id == snapshot_id).all()

    flood_features = []
    if hazard:
        flood_features.append({
            "type": "Feature",
            "geometry": json.loads(hazard.geom),
            "properties": {
                "id": hazard.id,
                "type": "FLOOD_EXTENT",
                "severity": hazard.severity,
                "confidence": hazard.confidence,
                "state_type": hazard.state_type.value
            }
        })

    red_zone_features = []
    for rz in red_zones:
        red_zone_features.append({
            "type": "Feature",
            "geometry": json.loads(rz.geom),
            "properties": {
                "id": rz.id,
                "designation": rz.designation_code,
                "status": rz.operational_status.value,
                "reason": rz.reason_code
            }
        })

    # 2. Habitations Layer
    habs = db.query(Habitation).all()
    hab_features = []
    for h in habs:
        prios = db.query(PriorityRecord).filter(
            PriorityRecord.habitation_id == h.id,
            PriorityRecord.snapshot_id == snapshot_id
        ).all()
        imm_count = sum(1 for p in prios if p.priority_class == PriorityClassEnum.IMMEDIATE)
        short_count = sum(1 for p in prios if p.priority_class == PriorityClassEnum.SHORT_TERM)
        med_count = sum(1 for p in prios if p.priority_class == PriorityClassEnum.MEDIUM_TERM)

        hab_features.append({
            "type": "Feature",
            "geometry": json.loads(h.geom),
            "properties": {
                "id": h.id,
                "code": h.code,
                "name": h.name,
                "population": h.population_estimate,
                "elevation_m": h.elevation_m,
                "immediate_priority_count": imm_count,
                "short_term_priority_count": short_count,
                "medium_term_priority_count": med_count,
                "highest_priority": "IMMEDIATE" if imm_count > 0 else ("SHORT_TERM" if short_count > 0 else "MEDIUM_TERM")
            }
        })

    # 3. Destinations Layer
    dests = db.query(Destination).all()
    dest_features = []
    active_bottlenecks = []

    for d in dests:
        cap = db.query(CapacityState).filter(
            CapacityState.destination_id == d.id,
            CapacityState.snapshot_id == snapshot_id
        ).first()

        eff_cap = cap.effective_capacity if cap else 0
        rem_cap = cap.remaining_capacity if cap else 0
        bottleneck = cap.bottleneck_resource if cap else "UNKNOWN"
        is_safe = cap.is_safe if cap else False

        if bottleneck not in active_bottlenecks:
            active_bottlenecks.append(bottleneck)

        dest_features.append({
            "type": "Feature",
            "geometry": json.loads(d.location_geom),
            "properties": {
                "id": d.id,
                "code": d.code,
                "name": d.name,
                "facility_type": d.facility_type,
                "operational_status": d.operational_status.value,
                "is_safe": is_safe,
                "effective_capacity": eff_cap,
                "remaining_capacity": rem_cap,
                "bottleneck_resource": bottleneck,
                "suitability_score": d.suitability_score
            }
        })

    # 4. Road Network & Routes
    segs = db.query(RoadSegment).all()
    road_features = []
    for s in segs:
        road_features.append({
            "type": "Feature",
            "geometry": json.loads(s.geom),
            "properties": {
                "id": s.id,
                "segment_code": s.segment_code,
                "road_class": s.road_class,
                "is_bridge": s.is_bridge,
                "operational_status": s.operational_status.value,
                "length_m": s.length_meters
            }
        })

    routes = db.query(RoutePlan).filter(RoutePlan.snapshot_id == snapshot_id).all()
    route_features = []
    for r in routes:
        route_features.append({
            "type": "Feature",
            "geometry": json.loads(r.geom),
            "properties": {
                "id": r.id,
                "distance_m": r.total_distance_m,
                "time_min": r.total_time_min,
                "cost": r.route_cost,
                "is_viable": r.is_viable,
                "reason": r.invalidated_reason
            }
        })

    # 5. KPIs & Summary Stats
    all_prios = db.query(PriorityRecord).filter(PriorityRecord.snapshot_id == snapshot_id).all()
    immediate_total = sum(1 for p in all_prios if p.priority_class == PriorityClassEnum.IMMEDIATE)
    short_term_total = sum(1 for p in all_prios if p.priority_class == PriorityClassEnum.SHORT_TERM)

    allocs = db.query(RelocationAllocation).filter(RelocationAllocation.snapshot_id == snapshot_id).all()
    unmet_count = sum(1 for a in allocs if a.allocation_status == AllocationStatusEnum.UNMET)
    allocated_count = sum(1 for a in allocs if a.allocation_status in (AllocationStatusEnum.RECOMMENDED, AllocationStatusEnum.ACCEPTED, AllocationStatusEnum.OVERRIDDEN))

    kpis = {
        "study_area_name": study_area.name if study_area else "Vayu River Basin",
        "study_area_code": study_area.code if study_area else "STUDY_VAYU_01",
        "snapshot_label": snapshot.label if snapshot else "Baseline",
        "snapshot_type": snapshot.snapshot_type if snapshot else "BASELINE",
        "total_habitations": len(habs),
        "total_households": len(all_prios),
        "immediate_priority_households": immediate_total,
        "short_term_priority_households": short_term_total,
        "active_bottlenecks": active_bottlenecks,
        "total_relocations_assigned": allocated_count,
        "unmet_relocation_demand": unmet_count
    }

    overview_data = {
        "kpis": kpis,
        "layers": {
            "flood_polygons": {"type": "FeatureCollection", "features": flood_features},
            "red_zones": {"type": "FeatureCollection", "features": red_zone_features},
            "habitations": {"type": "FeatureCollection", "features": hab_features},
            "destinations": {"type": "FeatureCollection", "features": dest_features},
            "road_segments": {"type": "FeatureCollection", "features": road_features},
            "active_routes": {"type": "FeatureCollection", "features": route_features}
        }
    }

    return ResponseEnvelope[Dict[str, Any]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=overview_data
    )
