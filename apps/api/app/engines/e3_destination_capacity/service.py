from typing import List, Dict, Any, Optional
import shapely
from app.gis.spatial import to_shapely, intersects
from app.models.entities import Destination, DestinationResource, CapacityState
from app.models.enums import OperationalStatusEnum, ResourceCategoryEnum

def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))

class DestinationCapacityEngineE3:
    """Engine 3: Safe Destination & Dynamic Carrying Capacity."""

    def evaluate_destination_safety_and_capacity(
        self,
        destination: Destination,
        resources: List[DestinationResource],
        current_hazard_geom: shapely.Geometry,
        predicted_hazard_geom: shapely.Geometry,
        snapshot_id: str,
        occupied_capacity: int = 0
    ) -> Tuple[Destination, CapacityState]:
        """
        Evaluate candidate site:
        1. Hard safety filtering against flood hazards.
        2. Dynamic multi-resource bottleneck calculation.
        3. Suitability scoring.
        """
        dest_point = to_shapely(destination.location_geom)

        # 1. Hard safety check: cannot be in flood extent
        is_flooded = intersects(dest_point, current_hazard_geom) or intersects(dest_point, predicted_hazard_geom)

        if is_flooded:
            destination.operational_status = OperationalStatusEnum.CLOSED
            destination.suitability_score = 0.0

            capacity_state = CapacityState(
                destination_id=destination.id,
                snapshot_id=snapshot_id,
                effective_capacity=0,
                occupied_capacity=occupied_capacity,
                remaining_capacity=0,
                bottleneck_resource="FLOOD_HAZARD_INUNDATION",
                is_safe=False,
                rejection_reason="DESTINATION_INUNDATED_BY_HAZARD"
            )
            return destination, capacity_state

        # 2. Dynamic Resource Bottleneck Calculation
        # Capacity is the minimum supportable population among active critical resources
        critical_resources = [r for r in resources if r.is_critical]
        if not critical_resources:
            # Fallback if no specific resources defined
            bottleneck_resource = "GENERAL_SHELTER"
            effective_cap = 50
        else:
            # Find the resource with the minimum supportable population
            min_res = min(critical_resources, key=lambda r: r.supportable_population)
            effective_cap = max(0, min_res.supportable_population)
            bottleneck_resource = min_res.resource_type.value

        remaining_cap = max(0, effective_cap - occupied_capacity)

        # 3. Suitability Scoring (0 to 100)
        safe_score = 100.0
        cap_score = clamp((effective_cap / 150.0) * 100.0, 10.0, 100.0)
        access_score = 85.0 if destination.operational_status == OperationalStatusEnum.OPEN else 40.0
        service_score = 90.0 if len(resources) >= 4 else 60.0
        travel_score = 80.0
        risk_score = 95.0

        suitability = (
            0.35 * safe_score +
            0.20 * cap_score +
            0.15 * access_score +
            0.15 * service_score +
            0.10 * travel_score +
            0.05 * risk_score
        )
        destination.suitability_score = round(suitability, 1)

        capacity_state = CapacityState(
            destination_id=destination.id,
            snapshot_id=snapshot_id,
            effective_capacity=effective_cap,
            occupied_capacity=occupied_capacity,
            remaining_capacity=remaining_cap,
            bottleneck_resource=bottleneck_resource,
            is_safe=True,
            rejection_reason=None
        )

        return destination, capacity_state
