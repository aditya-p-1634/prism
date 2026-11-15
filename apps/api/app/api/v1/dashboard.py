import json
import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import (
    StateSnapshot, StudyArea, HazardState, HazardPrediction, RedZone, Habitation, Household,
    PriorityRecord, Destination, CapacityState, RoadSegment, RoutePlan, RelocationAllocation
)
from app.models.enums import PriorityClassEnum, AllocationStatusEnum
from app.schemas.envelope import ResponseEnvelope
from app.api.deps import require_existing_snapshot

router = APIRouter(prefix="/dashboard", tags=["Command Dashboard & Read Models (B10)"])

@router.get("/overview", response_model=ResponseEnvelope[Dict[str, Any]])
def get_dashboard_overview(
    snapshot_id: str = Query("SNAP_BASE_001", description="Target state snapshot ID"),
    db: Session = Depends(get_db)
):
    snapshot = require_existing_snapshot(db, snapshot_id)
    study_area = db.query(StudyArea).first()

    # 1. Hazard Layers
    hazard = db.query(HazardState).filter(HazardState.snapshot_id == snapshot_id).first()
    prediction = db.query(HazardPrediction).filter(HazardPrediction.snapshot_id == snapshot_id).first()
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

    study_area_feature = None
    if study_area and study_area.boundary_geom:
        study_area_feature = {
            "type": "Feature",
            "geometry": json.loads(study_area.boundary_geom),
            "properties": {
                "id": study_area.id,
                "code": study_area.code,
                "name": study_area.name,
                "source_crs": study_area.crs_code,
            },
        }

    predicted_flood_features = []
    if prediction and prediction.predicted_extent_geom:
        predicted_flood_features.append({
            "type": "Feature",
            "geometry": json.loads(prediction.predicted_extent_geom),
            "properties": {
                "id": prediction.id,
                "type": "PREDICTED_FLOOD_EXTENT",
                "horizon_hours": prediction.horizon_hours,
                "confidence": prediction.confidence,
                "method_identifier": prediction.method_identifier,
            },
        })

    # 2. Habitations Layer
    habs = db.query(Habitation).all()
    hab_features = []
    hab_point_features = []
    for h in habs:
        prios = db.query(PriorityRecord).filter(
            PriorityRecord.habitation_id == h.id,
            PriorityRecord.snapshot_id == snapshot_id
        ).all()
        imm_count = sum(1 for p in prios if p.priority_class == PriorityClassEnum.IMMEDIATE)
        short_count = sum(1 for p in prios if p.priority_class == PriorityClassEnum.SHORT_TERM)
        med_count = sum(1 for p in prios if p.priority_class == PriorityClassEnum.MEDIUM_TERM)

        properties = {
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
        hab_features.append({
            "type": "Feature",
            "geometry": json.loads(h.geom),
            "properties": properties
        })
        hab_point_features.append({
            "type": "Feature",
            "geometry": json.loads(h.centroid_geom),
            "properties": properties,
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
            "study_area_boundary": {
                "type": "FeatureCollection",
                "features": [study_area_feature] if study_area_feature else [],
            },
            "flood_polygons": {"type": "FeatureCollection", "features": flood_features},
            "predicted_flood_polygons": {"type": "FeatureCollection", "features": predicted_flood_features},
            "red_zones": {"type": "FeatureCollection", "features": red_zone_features},
            "habitations": {"type": "FeatureCollection", "features": hab_features},
            "habitation_points": {"type": "FeatureCollection", "features": hab_point_features},
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


@router.get("/operator-briefing", response_model=ResponseEnvelope[Dict[str, Any]])
def get_operator_briefing(
    snapshot_id: str = Query("SNAP_BASE_001", description="Target decision snapshot ID"),
    db: Session = Depends(get_db)
):
    """Return a read-only, operator-oriented decision brief for one snapshot.

    This read model intentionally does not approve, allocate, or mutate any
    operational state. It translates E1-E4 outputs into a small set of
    reviewable facts and next actions for the incident commander.
    """
    snapshot = require_existing_snapshot(db, snapshot_id)

    hazard = db.query(HazardState).filter(HazardState.snapshot_id == snapshot_id).first()
    red_zones = db.query(RedZone).filter(RedZone.snapshot_id == snapshot_id).all()
    priorities = db.query(PriorityRecord).filter(
        PriorityRecord.snapshot_id == snapshot_id
    ).order_by(PriorityRecord.priority_score.desc()).all()
    households = {h.id: h for h in db.query(Household).all()}
    habitations = {h.id: h for h in db.query(Habitation).all()}
    capacities = db.query(CapacityState).filter(CapacityState.snapshot_id == snapshot_id).all()
    routes = db.query(RoutePlan).filter(RoutePlan.snapshot_id == snapshot_id).all()
    allocations = db.query(RelocationAllocation).filter(
        RelocationAllocation.snapshot_id == snapshot_id
    ).all()

    immediate = [p for p in priorities if p.priority_class == PriorityClassEnum.IMMEDIATE]
    short_term = [p for p in priorities if p.priority_class == PriorityClassEnum.SHORT_TERM]
    unmet = [a for a in allocations if a.allocation_status == AllocationStatusEnum.UNMET]
    unsafe_destinations = [c for c in capacities if not c.is_safe]
    invalid_routes = [r for r in routes if not r.is_viable]
    partial_data = sum(1 for h in households.values() if h.has_partial_data)

    warnings: List[Dict[str, Any]] = []
    next_actions: List[Dict[str, Any]] = []
    if hazard and (hazard.confidence is None or hazard.confidence < 0.7):
        warnings.append({"code": "LOW_HAZARD_CONFIDENCE", "severity": "HIGH", "message": "Hazard evidence confidence is below the review threshold."})
    if partial_data:
        warnings.append({"code": "PARTIAL_HOUSEHOLD_DATA", "severity": "MEDIUM", "message": f"{partial_data} household records contain partial data."})
    if unmet:
        warnings.append({"code": "UNMET_DEMAND", "severity": "HIGH", "message": f"{len(unmet)} relocation groups have no feasible allocation."})
        next_actions.append({"code": "RESOLVE_UNMET_DEMAND", "priority": "IMMEDIATE", "label": "Resolve unmet relocation demand", "reason": "Capacity or route constraints prevent a complete plan."})
    if unsafe_destinations:
        next_actions.append({"code": "REVIEW_DESTINATIONS", "priority": "IMMEDIATE", "label": "Review unsafe destinations", "reason": f"{len(unsafe_destinations)} destination capacity states are unsafe."})
    if invalid_routes:
        next_actions.append({"code": "REVIEW_ROUTES", "priority": "IMMEDIATE", "label": "Review invalid routes", "reason": f"{len(invalid_routes)} route plans are not currently viable."})
    if immediate:
        next_actions.append({"code": "REVIEW_IMMEDIATE_GROUPS", "priority": "IMMEDIATE", "label": "Review immediate-priority groups", "reason": f"{len(immediate)} groups require immediate attention."})
    if not next_actions:
        next_actions.append({"code": "AUTHORIZE_PLAN_REVIEW", "priority": "NORMAL", "label": "Review plan for authorization", "reason": "No blocking constraint was detected in this snapshot."})

    top_groups = []
    for p in priorities[:8]:
        household = households.get(p.household_id)
        habitation = habitations.get(p.habitation_id)
        top_groups.append({
            "household_id": p.household_id,
            "household_code": household.anonymized_code if household else p.household_id,
            "habitation": habitation.name if habitation else p.habitation_id,
            "priority_class": p.priority_class.value,
            "priority_score": p.priority_score,
            "member_count": household.member_count if household else None,
            "assistance_required": bool(household.assistance_required) if household else False,
            "reason_codes": p.reason_codes or [],
            "has_partial_data": bool(household.has_partial_data) if household else True,
        })

    briefing = {
        "snapshot": {
            "id": snapshot.id,
            "label": snapshot.label,
            "snapshot_type": snapshot.snapshot_type,
            "is_immutable": bool(snapshot.is_immutable),
            "requires_human_review": True,
        },
        "situation": {
            "hazard_present": hazard is not None,
            "hazard_type": hazard.hazard_type if hazard else None,
            "hazard_severity": hazard.severity if hazard else None,
            "hazard_confidence": hazard.confidence if hazard else None,
            "red_zone_count": len(red_zones),
            "status": "REVIEW_REQUIRED" if (red_zones or immediate or warnings) else "NO_ACTIVE_ALERT",
        },
        "decision_summary": {
            "total_priority_groups": len(priorities),
            "immediate_groups": len(immediate),
            "short_term_groups": len(short_term),
            "assigned_groups": len(allocations) - len(unmet),
            "unmet_groups": len(unmet),
            "unsafe_destinations": len(unsafe_destinations),
            "invalid_routes": len(invalid_routes),
            "partial_household_records": partial_data,
        },
        "top_priority_groups": top_groups,
        "warnings": warnings,
        "next_actions": next_actions,
        "integrity": {
            "allocation_is_not_evacuation": True,
            "field_confirmation_available": False,
            "approval_required": True,
        },
    }

    return ResponseEnvelope[Dict[str, Any]](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        data=briefing
    )
