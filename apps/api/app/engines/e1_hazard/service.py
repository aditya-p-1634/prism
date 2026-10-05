import uuid
from typing import Dict, Any, List, Optional
import shapely
from shapely.geometry import MultiPolygon, Polygon
from app.gis.spatial import to_shapely, to_geojson_str, buffer_meters
from app.models.entities import HazardState, HazardPrediction, RedZone, HazardEvidence
from app.models.enums import StateTypeEnum, OperationalStatusEnum

def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))

class HazardEngineE1:
    """Engine 1: Multi-Hazard Intelligence & Prediction."""

    def __init__(
        self,
        reference_change_m: float = 2.0,
        persistence_window_count: int = 5,
        max_expansion_factor: float = 2.5,
        base_buffer_meters: float = 300.0
    ):
        self.reference_change_m = reference_change_m
        self.persistence_window_count = persistence_window_count
        self.max_expansion_factor = max_expansion_factor
        self.base_buffer_meters = base_buffer_meters

    def compute_expansion_factor(
        self,
        rainfall_multiplier_delta: float,
        river_level_current: float,
        river_level_baseline: float,
        valid_persistent_obs_count: int = 5
    ) -> float:
        """Frozen formula for E1 expansion factor."""
        normalized_river_delta = clamp(
            (river_level_current - river_level_baseline) / self.reference_change_m,
            0.0, 1.0
        )
        persistence_factor = clamp(
            valid_persistent_obs_count / self.persistence_window_count,
            0.0, 1.0
        )
        expansion = 1.00 + (0.60 * rainfall_multiplier_delta) + (0.30 * normalized_river_delta) + (0.10 * persistence_factor)
        return clamp(expansion, 1.00, self.max_expansion_factor)

    def evaluate_hazard_state(
        self,
        study_area_id: str,
        snapshot_id: str,
        base_flood_geom: shapely.Geometry,
        rainfall_multiplier_delta: float = 0.0,
        river_level_current: float = 10.0,
        river_level_baseline: float = 10.0,
        horizon_hours: float = 6.0,
        base_confidence: float = 0.95,
        data_quality_factor: float = 1.0
    ) -> Dict[str, Any]:
        """
        Evaluate current hazard extent, compute predicted extent, and generate Red Zone.
        """
        expansion_factor = self.compute_expansion_factor(
            rainfall_multiplier_delta=rainfall_multiplier_delta,
            river_level_current=river_level_current,
            river_level_baseline=river_level_baseline
        )

        current_geom = base_flood_geom
        if not current_geom.is_valid:
            current_geom = shapely.make_valid(current_geom)

        # Predict future extent using planar metric expansion
        added_buffer_m = (expansion_factor - 1.0) * self.base_buffer_meters
        if added_buffer_m > 0:
            predicted_geom = buffer_meters(current_geom, added_buffer_m)
        else:
            predicted_geom = current_geom

        confidence = clamp(base_confidence * data_quality_factor, 0.0, 1.0)

        # Red Zone: areas directly inundated by current or severe predicted surge
        red_zone_geom = current_geom

        hazard_state_id = str(uuid.uuid4())
        red_zone_id = str(uuid.uuid4())

        # Create HazardState
        hazard_state = HazardState(
            id=hazard_state_id,
            study_area_id=study_area_id,
            snapshot_id=snapshot_id,
            hazard_type="FLOOD",
            severity="HIGH" if expansion_factor > 1.2 else "MEDIUM",
            geom=to_geojson_str(current_geom),
            state_type=StateTypeEnum.OBSERVED if expansion_factor == 1.0 else StateTypeEnum.SIMULATION,
            confidence=confidence
        )

        # Create HazardPrediction
        hazard_prediction = HazardPrediction(
            id=str(uuid.uuid4()),
            hazard_state_id=hazard_state_id,
            snapshot_id=snapshot_id,
            horizon_hours=horizon_hours,
            predicted_extent_geom=to_geojson_str(predicted_geom),
            expansion_factor=expansion_factor,
            confidence=round(confidence * 0.90, 2),
            method_identifier="PLANAR_PROJECTED_BUFFER_v1"
        )

        # Create Red Zone
        red_zone = RedZone(
            id=red_zone_id,
            study_area_id=study_area_id,
            snapshot_id=snapshot_id,
            designation_code=f"RZ-FL-{study_area_id[:4].upper()}",
            hazard_type="FLOOD",
            geom=to_geojson_str(red_zone_geom),
            operational_status=OperationalStatusEnum.ACTIVE,
            reason_code="SEVERE_RIVERINE_INUNDATION"
        )

        evidence = HazardEvidence(
            id=str(uuid.uuid4()),
            red_zone_id=red_zone_id,
            metric_name="RIVER_STAGE_M",
            measured_value=river_level_current,
            threshold_value=river_level_baseline + 0.30,
            source_reference="CWC_GAUGE_01"
        )

        return {
            "hazard_state": hazard_state,
            "hazard_prediction": hazard_prediction,
            "red_zone": red_zone,
            "evidence": evidence,
            "current_geom": current_geom,
            "predicted_geom": predicted_geom
        }

    def evaluate_from_prediction(
        self,
        predicted_river_level: float,
        study_area_id: str,
        snapshot_id: str,
        base_flood_geom: shapely.Geometry,
        rainfall_multiplier_delta: float = 0.0,
        horizon_hours: float = 6.0,
        confidence: float = 0.85
    ) -> Dict[str, Any]:
        """
        Consumes an A.6 validated predicted hazard state to evaluate projected
        flood geometry and red-zone extents without modifying baseline scenario logic.
        """
        return self.evaluate_hazard_state(
            study_area_id=study_area_id,
            snapshot_id=snapshot_id,
            base_flood_geom=base_flood_geom,
            rainfall_multiplier_delta=rainfall_multiplier_delta,
            river_level_current=predicted_river_level,
            river_level_baseline=10.0,
            horizon_hours=horizon_hours,
            base_confidence=confidence
        )

    def evaluate_from_observation(
        self,
        observation: Any,
        study_area_id: str,
        snapshot_id: str,
        base_flood_geom: shapely.Geometry,
        rainfall_multiplier_delta: float = 0.0,
        horizon_hours: float = 6.0
    ) -> Dict[str, Any]:
        """
        Consumes an A.7 validated real-world telemetry observation to drive E1.

        CRITICAL NOTICE (Section 12):
        Prototype spatial transformation — not a validated hydrodynamic inundation model.
        A single river gauge measurement does not produce an authoritative flood map.
        This provides a controlled spatial projection for PRISM prototype relocation planning.
        """
        gauge_baseline = 2.0 if getattr(observation, "station_code", "") == "NANDAMBAKKAM_CHECKDAM" else 10.0

        eval_res = self.evaluate_hazard_state(
            study_area_id=study_area_id,
            snapshot_id=snapshot_id,
            base_flood_geom=base_flood_geom,
            rainfall_multiplier_delta=rainfall_multiplier_delta,
            river_level_current=observation.value,
            river_level_baseline=gauge_baseline,
            horizon_hours=horizon_hours,
            base_confidence=1.0  # Real verified observation
        )

        # Explicitly tag observation-driven provenance on hazard prediction and evidence
        eval_res["hazard_state"].state_type = StateTypeEnum.OBSERVED
        eval_res["hazard_prediction"].method_identifier = "PROTOTYPE_OBSERVATION_SPATIAL_TRANSFORMATION_v1"

        # Update evidence to point to real telemetry observation
        evidence = eval_res["evidence"]
        evidence.metric_name = "RIVER_WATER_LEVEL"
        evidence.measured_value = observation.value
        evidence.threshold_value = None  # Severity unclassified unless documented
        evidence.source_reference = f"STATION:{observation.station_code}:OBS:{observation.id}"

        return eval_res


