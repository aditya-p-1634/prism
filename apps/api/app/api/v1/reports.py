from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.entities import (
    StateSnapshot, Habitation, Household, Destination, DestinationResource,
    CapacityState, RoadSegment, RoutePlan, RelocationGroup, RelocationAllocation
)
from app.models.enums import AllocationStatusEnum, OperationalStatusEnum

router = APIRouter(prefix="/reports", tags=["Operational Reports"])

@router.get("/summary")
def get_report_summary(
    snapshot_id: str = Query("SNAP_BASE_001", description="Target snapshot ID for report generation"),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive operational reports from verified system state.
    Outputs data for evacuation manifests, shelter logistics, and infrastructure status.
    """
    snapshot = db.query(StateSnapshot).filter(StateSnapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found.")

    # 1. Evacuation Manifest Data
    allocations = db.query(RelocationAllocation).filter(RelocationAllocation.snapshot_id == snapshot_id).all()
    manifest_rows = []
    total_assigned_headcount = 0
    unmet_headcount = 0

    for alloc in allocations:
        group = db.query(RelocationGroup).filter(RelocationGroup.id == alloc.group_id).first()
        if not group:
            continue
        
        hh = db.query(Household).filter(Household.id == group.household_id).first()
        hab = db.query(Habitation).filter(Habitation.id == group.habitation_id).first()
        dest = db.query(Destination).filter(Destination.id == alloc.destination_id).first() if alloc.destination_id else None
        route = db.query(RoutePlan).filter(RoutePlan.id == alloc.route_plan_id).first() if alloc.route_plan_id else None

        status_str = alloc.allocation_status.value if hasattr(alloc.allocation_status, 'value') else str(alloc.allocation_status)
        is_assigned = status_str in ("RECOMMENDED", "ACCEPTED", "OVERRIDDEN") and dest is not None
        
        if is_assigned:
            total_assigned_headcount += alloc.assigned_capacity_count
        else:
            unmet_headcount += group.group_size

        manifest_rows.append({
            "allocation_id": alloc.id,
            "household_code": hh.anonymized_code if hh else "N/A",
            "habitation_code": hab.code if hab else "N/A",
            "habitation_name": hab.name if hab else "N/A",
            "member_count": group.group_size,
            "priority_score": round(group.priority_score, 1),
            "priority_class": group.priority_class.value if hasattr(group.priority_class, 'value') else str(group.priority_class),
            "destination_code": dest.code if dest else "UNMET",
            "destination_name": dest.name if dest else "No Viable Shelter",
            "route_distance_km": round(route.total_distance_m / 1000.0, 2) if route else None,
            "estimated_time_min": round(route.total_time_min, 1) if route else None,
            "status": status_str,
            "reason_code": alloc.reason_code
        })

    # 2. Shelter Logistics Data
    capacities = db.query(CapacityState).filter(CapacityState.snapshot_id == snapshot_id).all()
    shelter_rows = []
    for cap in capacities:
        dest = db.query(Destination).filter(Destination.id == cap.destination_id).first()
        resources = db.query(DestinationResource).filter(
            DestinationResource.destination_id == cap.destination_id,
            DestinationResource.snapshot_id == snapshot_id
        ).all()

        res_breakdown = {}
        for r in resources:
            r_type = r.resource_type.value if hasattr(r.resource_type, 'value') else str(r.resource_type)
            res_breakdown[r_type] = {
                "quantity": r.quantity,
                "unit": r.unit,
                "supportable_population": r.supportable_population,
                "is_critical": r.is_critical
            }

        utilization_pct = round((cap.occupied_capacity / cap.effective_capacity * 100.0), 1) if cap.effective_capacity > 0 else 0.0

        shelter_rows.append({
            "destination_id": cap.destination_id,
            "destination_code": dest.code if dest else "N/A",
            "destination_name": dest.name if dest else "N/A",
            "effective_capacity": cap.effective_capacity,
            "occupied_capacity": cap.occupied_capacity,
            "remaining_capacity": cap.remaining_capacity,
            "utilization_pct": utilization_pct,
            "bottleneck_resource": cap.bottleneck_resource,
            "is_safe": cap.is_safe,
            "resources": res_breakdown
        })

    # 3. Infrastructure & Road Status
    road_segments = db.query(RoadSegment).all()
    infra_rows = []
    for seg in road_segments:
        op_status = seg.operational_status.value if hasattr(seg.operational_status, 'value') else str(seg.operational_status)
        infra_rows.append({
            "segment_code": seg.segment_code,
            "road_class": seg.road_class,
            "length_meters": round(seg.length_meters, 1),
            "is_bridge": seg.is_bridge,
            "operational_status": op_status,
            "hazard_risk_score": round(seg.hazard_risk_score, 2)
        })

    return {
        "status": "success",
        "snapshot_id": snapshot.id,
        "snapshot_label": snapshot.label,
        "is_baseline": snapshot.is_immutable and snapshot.id == "SNAP_BASE_001",
        "summary": {
            "total_groups": len(manifest_rows),
            "allocated_groups": len([r for r in manifest_rows if r["status"] in ("RECOMMENDED", "ACCEPTED", "OVERRIDDEN") and r["destination_code"] != "UNMET"]),
            "unmet_groups": len([r for r in manifest_rows if r["status"] == "UNMET" or r["destination_code"] == "UNMET"]),
            "total_relocated_headcount": total_assigned_headcount,
            "unmet_headcount": unmet_headcount,
            "active_shelters_count": len(shelter_rows),
            "closed_roads_count": len([r for r in infra_rows if r["operational_status"] == "CLOSED"])
        },
        "manifest": manifest_rows,
        "shelters": shelter_rows,
        "infrastructure": infra_rows
    }


@router.get("/export")
def export_report_csv(
    report_type: str = Query("manifest", pattern="^(manifest|shelters|infrastructure)$"),
    snapshot_id: str = Query("SNAP_BASE_001"),
    db: Session = Depends(get_db)
):
    """
    Offline-ready CSV export for operational manifests, shelter logistics, and infrastructure status.
    """
    import csv
    import io
    from fastapi.responses import Response

    rep = get_report_summary(snapshot_id=snapshot_id, db=db)
    output = io.StringIO()

    if report_type == "manifest":
        rows = rep.get("manifest", [])
        if not rows:
            output.write("No manifest records found\n")
        else:
            fieldnames = ["allocation_id", "household_code", "habitation_code", "habitation_name", "member_count", "priority_score", "priority_class", "destination_code", "destination_name", "route_distance_km", "estimated_time_min", "status", "reason_code"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        filename = f"evacuation_manifest_{snapshot_id}.csv"

    elif report_type == "shelters":
        rows = rep.get("shelters", [])
        fieldnames = ["destination_code", "destination_name", "effective_capacity", "occupied_capacity", "remaining_capacity", "utilization_pct", "bottleneck_resource", "is_safe"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
        filename = f"shelter_logistics_{snapshot_id}.csv"

    else:
        rows = rep.get("infrastructure", [])
        fieldnames = ["segment_code", "road_class", "length_meters", "is_bridge", "operational_status", "hazard_risk_score"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
        filename = f"infrastructure_damage_{snapshot_id}.csv"

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

