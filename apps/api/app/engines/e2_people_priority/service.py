from typing import List, Dict, Any, Tuple
import shapely
from app.gis.spatial import to_shapely, intersects
from app.models.entities import Habitation, Household, ExposureAssessment, VulnerabilityProfile, PriorityRecord
from app.models.enums import PriorityClassEnum

def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))

class PeoplePriorityEngineE2:
    """Engine 2: Habitation & Household Vulnerability + Priority."""

    def evaluate_habitation_exposure(
        self,
        habitation: Habitation,
        current_hazard_geom: shapely.Geometry,
        predicted_hazard_geom: shapely.Geometry,
        snapshot_id: str
    ) -> ExposureAssessment:
        """Evaluate spatial exposure against current and predicted flood extents."""
        hab_geom = to_shapely(habitation.geom)

        is_current_exposed = intersects(hab_geom, current_hazard_geom)
        is_predicted_exposed = intersects(hab_geom, predicted_hazard_geom)

        current_score = 100.0 if is_current_exposed else 0.0
        predicted_score = 75.0 if is_predicted_exposed else 0.0

        # Frozen rule: max(current, future) - never average away severe exposure
        exposure_score = max(current_score, predicted_score)
        is_in_red_zone = is_current_exposed or (is_predicted_exposed and habitation.elevation_m < 15.0)

        flood_depth_m = 1.2 if is_current_exposed else (0.5 if is_predicted_exposed else 0.0)
        time_to_impact = 0.5 if is_current_exposed else (3.0 if is_predicted_exposed else 999.0)

        return ExposureAssessment(
            habitation_id=habitation.id,
            snapshot_id=snapshot_id,
            exposure_score=exposure_score,
            is_in_red_zone=is_in_red_zone,
            flood_depth_m=flood_depth_m,
            time_to_impact_hours=time_to_impact
        )

    def evaluate_household_vulnerability(
        self,
        household: Household,
        snapshot_id: str
    ) -> VulnerabilityProfile:
        """
        Evaluate household vulnerability.
        Invariant: missing or partial registration never assumes zero vulnerability.
        """
        if household.has_partial_data:
            # Conservative baseline for unregistered/partial data
            vulnerability_score = 45.0
            demographic = 40.0
            assistance = 40.0
            access_risk = 30.0
        else:
            demographic = clamp(
                (household.vulnerable_elderly * 25.0) + (household.vulnerable_children * 15.0) + (household.mobility_impaired * 35.0),
                10.0, 100.0
            )
            assistance = 85.0 if household.assistance_required else 15.0
            access_risk = 50.0 if household.mobility_impaired > 0 else 20.0
            vulnerability_score = clamp(
                0.50 * demographic + 0.35 * assistance + 0.15 * access_risk,
                10.0, 100.0
            )

        return VulnerabilityProfile(
            household_id=household.id,
            snapshot_id=snapshot_id,
            vulnerability_score=vulnerability_score,
            demographic_factor=demographic,
            assistance_factor=assistance,
            accessibility_risk_factor=access_risk
        )

    def compute_priority(
        self,
        habitation: Habitation,
        household: Household,
        exposure: ExposureAssessment,
        vulnerability: VulnerabilityProfile,
        snapshot_id: str
    ) -> PriorityRecord:
        """
        Compute explainable relocation priority.
        P = 0.35 exposure + 0.25 vulnerability + 0.20 time urgency + 0.10 accessibility risk + 0.10 assistance
        """
        exp_score = exposure.exposure_score
        vuln_score = vulnerability.vulnerability_score
        
        # Time urgency: 0 to 100 based on time to impact
        if exposure.time_to_impact_hours <= 1.0:
            urgency_score = 100.0
        elif exposure.time_to_impact_hours <= 4.0:
            urgency_score = 70.0
        elif exposure.time_to_impact_hours <= 12.0:
            urgency_score = 30.0
        else:
            urgency_score = 0.0

        access_risk = vulnerability.accessibility_risk_factor
        assistance = vulnerability.assistance_factor

        # Frozen formula
        P = (
            0.35 * exp_score +
            0.25 * vuln_score +
            0.20 * urgency_score +
            0.10 * access_risk +
            0.10 * assistance
        )
        P = round(clamp(P, 0.0, 100.0), 1)

        # Classification
        if P >= 75.0 or (exposure.flood_depth_m >= 1.0 and vuln_score >= 50.0):
            priority_class = PriorityClassEnum.IMMEDIATE
        elif P >= 50.0:
            priority_class = PriorityClassEnum.SHORT_TERM
        else:
            priority_class = PriorityClassEnum.MEDIUM_TERM

        # Explainability reason codes
        reason_codes = []
        if exposure.is_in_red_zone:
            reason_codes.append("LOCATION_IN_ACTIVE_RED_ZONE")
        if exposure.exposure_score >= 70.0:
            reason_codes.append("SEVERE_DIRECT_FLOOD_EXPOSURE")
        elif exposure.exposure_score >= 40.0:
            reason_codes.append("PROJECTED_FLOOD_EXPANSION_THREAT")
        if household.mobility_impaired > 0:
            reason_codes.append(f"MOBILITY_IMPAIRED_MEMBERS_{household.mobility_impaired}")
        if household.vulnerable_elderly > 0:
            reason_codes.append("ELDERLY_DEPENDENTS_PRESENT")
        if household.assistance_required:
            reason_codes.append("MANDATORY_EVACUATION_ASSISTANCE")
        if household.has_partial_data:
            reason_codes.append("PARTIAL_DATA_CONSERVATIVE_DEFAULT")

        component_scores = {
            "exposure": exp_score,
            "vulnerability": vuln_score,
            "time_urgency": urgency_score,
            "accessibility_risk": access_risk,
            "assistance": assistance
        }

        return PriorityRecord(
            habitation_id=habitation.id,
            household_id=household.id,
            snapshot_id=snapshot_id,
            priority_score=P,
            priority_class=priority_class,
            reason_codes=reason_codes,
            component_scores=component_scores
        )
