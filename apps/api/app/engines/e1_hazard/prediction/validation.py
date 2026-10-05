"""
PRISM Phase A.6 — Physical Plausibility, Input Quality & Domain Validation
==========================================================================
Enforces:
1. Input Quality / Sensor Failure Checks (finite, bounds, non-negative, missing).
2. Domain-of-Validity / Out-of-Distribution Gating (training distribution envelope).
3. Physical Plausibility: Strict hydrological reality bounds (riverbed floor, floodwall crest, max rise/fall rate).
4. Domain Constraints: Prototype operational alert stages and rapid surge detection rules.

Never silently modifies predictions: returns explicit VALID, DEGRADED, or REJECTED statuses.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import math


@dataclass
class ValidationResult:
    status: str  # "VALID", "CORRECTED", "DEGRADED", "REJECTED"
    validated_value: float
    raw_value: float
    reason: Optional[str] = None
    domain_violations: List[str] = field(default_factory=list)


class InputQualityValidator:
    """
    Validates sensor inputs and feature values before pipeline execution.
    Fails safely on corrupted, NaN, Inf, negative rainfall, or extreme out-of-range sensor readings.
    """

    MIN_SENSOR_STAGE = 7.0   # Absolute physical dry floor for gauge sensor
    MAX_SENSOR_STAGE = 18.0  # Absolute catastrophic overtop height for gauge tower

    @classmethod
    def validate_inputs(
        cls,
        current_stage: float,
        lag1_stage: Optional[float],
        rainfall_rate: float,
        rolling_rain_30m: Optional[float],
        horizon_minutes: float
    ) -> ValidationResult:
        """Validates all raw sensor and feature inputs."""
        # Check current_stage
        if current_stage is None or not math.isfinite(current_stage):
            return ValidationResult(
                status="REJECTED",
                validated_value=0.0,
                raw_value=current_stage if current_stage is not None else -999.0,
                reason="INPUT_QUALITY_FAILURE: current_stage_m is missing, null, or non-finite (NaN/Inf)."
            )

        if current_stage < cls.MIN_SENSOR_STAGE or current_stage > cls.MAX_SENSOR_STAGE:
            return ValidationResult(
                status="REJECTED",
                validated_value=current_stage,
                raw_value=current_stage,
                reason=f"INPUT_QUALITY_FAILURE: current_stage_m ({current_stage:.2f}m) exceeds physical sensor bounds [{cls.MIN_SENSOR_STAGE}m, {cls.MAX_SENSOR_STAGE}m]."
            )

        # Check lag1_stage
        if lag1_stage is not None:
            if not math.isfinite(lag1_stage):
                return ValidationResult(
                    status="REJECTED",
                    validated_value=current_stage,
                    raw_value=lag1_stage,
                    reason="INPUT_QUALITY_FAILURE: lag1_stage_m is non-finite (NaN/Inf)."
                )
            if lag1_stage < cls.MIN_SENSOR_STAGE or lag1_stage > cls.MAX_SENSOR_STAGE:
                return ValidationResult(
                    status="REJECTED",
                    validated_value=current_stage,
                    raw_value=lag1_stage,
                    reason=f"INPUT_QUALITY_FAILURE: lag1_stage_m ({lag1_stage:.2f}m) exceeds physical sensor bounds."
                )

        # Check rainfall_rate
        if rainfall_rate is None or not math.isfinite(rainfall_rate):
            return ValidationResult(
                status="REJECTED",
                validated_value=current_stage,
                raw_value=rainfall_rate if rainfall_rate is not None else -999.0,
                reason="INPUT_QUALITY_FAILURE: rainfall_rate_mmh is missing, null, or non-finite (NaN/Inf)."
            )

        if rainfall_rate < 0.0:
            return ValidationResult(
                status="REJECTED",
                validated_value=current_stage,
                raw_value=rainfall_rate,
                reason=f"INPUT_QUALITY_FAILURE: rainfall_rate_mmh ({rainfall_rate:.2f}mm/h) cannot be negative."
            )

        # Check rolling_rain_30m
        if rolling_rain_30m is not None:
            if not math.isfinite(rolling_rain_30m):
                return ValidationResult(
                    status="REJECTED",
                    validated_value=current_stage,
                    raw_value=rolling_rain_30m,
                    reason="INPUT_QUALITY_FAILURE: rolling_rain_30m is non-finite (NaN/Inf)."
                )
            if rolling_rain_30m < 0.0:
                return ValidationResult(
                    status="REJECTED",
                    validated_value=current_stage,
                    raw_value=rolling_rain_30m,
                    reason=f"INPUT_QUALITY_FAILURE: rolling_rain_30m ({rolling_rain_30m:.2f}mm/h) cannot be negative."
                )

        # Check horizon_minutes
        if horizon_minutes is None or not math.isfinite(horizon_minutes) or horizon_minutes <= 0.0:
            return ValidationResult(
                status="REJECTED",
                validated_value=current_stage,
                raw_value=horizon_minutes if horizon_minutes is not None else -999.0,
                reason=f"INPUT_QUALITY_FAILURE: horizon_minutes must be positive finite number, got {horizon_minutes}."
            )

        return ValidationResult(
            status="VALID",
            validated_value=float(current_stage),
            raw_value=float(current_stage),
            reason="All raw input sensor values passed quality screening."
        )


class DomainOfValidityChecker:
    """
    Detects whether current observation inputs fall materially outside the training/validation
    distribution of the synthetic prototype hydrograph.
    Inputs outside domain are marked DEGRADED / OUT_OF_DOMAIN to prevent unsafe overconfidence.
    """

    # Domain envelope based on Vayu River Basin synthetic calibration distribution:
    STAGE_DOMAIN_MIN = 8.50    # Minimum observed stage in calibration
    STAGE_DOMAIN_MAX = 12.50   # Maximum observed stage in calibration
    MAX_STAGE_DELTA_10M = 0.40 # Maximum 10-min rate of change in calibration
    MAX_RAINFALL_MMH = 80.0    # Peak convective rainfall in calibration
    MAX_ROLLING_RAIN_MMH = 70.0
    MAX_SUPPORTED_HORIZON_MIN = 120.0 # Upper bound of calibrated horizons

    @classmethod
    def check_domain(
        cls,
        current_stage: float,
        lag1_stage: float,
        rainfall_rate: float,
        rolling_rain_30m: float,
        horizon_minutes: float
    ) -> Tuple[bool, List[str]]:
        """
        Checks if inputs are within the calibration domain.
        Returns (is_in_domain, list_of_violations).
        """
        violations = []

        if current_stage < cls.STAGE_DOMAIN_MIN or current_stage > cls.STAGE_DOMAIN_MAX:
            violations.append(
                f"current_stage_m ({current_stage:.2f}m) outside calibration domain [{cls.STAGE_DOMAIN_MIN}m, {cls.STAGE_DOMAIN_MAX}m]"
            )

        delta = abs(current_stage - lag1_stage)
        if delta > cls.MAX_STAGE_DELTA_10M:
            violations.append(
                f"10-min stage delta ({delta:.2f}m) exceeds calibration domain max ({cls.MAX_STAGE_DELTA_10M:.2f}m)"
            )

        if rainfall_rate > cls.MAX_RAINFALL_MMH:
            violations.append(
                f"rainfall_rate_mmh ({rainfall_rate:.1f}mm/h) exceeds calibration domain max ({cls.MAX_RAINFALL_MMH:.1f}mm/h)"
            )

        if rolling_rain_30m > cls.MAX_ROLLING_RAIN_MMH:
            violations.append(
                f"rolling_rain_30m ({rolling_rain_30m:.1f}mm/h) exceeds calibration domain max ({cls.MAX_ROLLING_RAIN_MMH:.1f}mm/h)"
            )

        if horizon_minutes > cls.MAX_SUPPORTED_HORIZON_MIN:
            violations.append(
                f"horizon_minutes ({horizon_minutes:.0f}m) exceeds maximum supported lead time ({cls.MAX_SUPPORTED_HORIZON_MIN:.0f}m)"
            )

        is_in_domain = len(violations) == 0
        return is_in_domain, violations


class PhysicalPlausibilityValidator:
    """
    Validates physical feasibility of hydrometric stage predictions.
    Grounded in Vayu River Basin channel hydraulics:
    - Riverbed floor: 8.0m (stage cannot drop below channel dry bottom).
    - Top of flood dyke: 15.0m (maximum possible crest elevation).
    - Maximum plausible rate of rise or fall: 1.5m / 10 minutes (catchment hydrodynamics upper bound).

    Defaults to allow_correction=False: unphysical predictions are REJECTED with an auditable reason
    rather than silently clamped.
    """

    def __init__(
        self,
        min_stage_m: float = 8.0,
        max_stage_m: float = 15.0,
        max_rate_change_per_10m: float = 1.5,
        allow_correction: bool = False
    ):
        self.min_stage_m = float(min_stage_m)
        self.max_stage_m = float(max_stage_m)
        self.max_rate_change_per_10m = float(max_rate_change_per_10m)
        self.allow_correction = allow_correction

    def validate(
        self,
        predicted_stage: float,
        current_stage: float,
        horizon_minutes: float
    ) -> ValidationResult:
        """Validates predicted stage against physical hydraulic bounds."""
        # 1. Finite float check
        if not math.isfinite(predicted_stage):
            return ValidationResult(
                status="REJECTED",
                validated_value=current_stage,
                raw_value=predicted_stage,
                reason="Prediction value is non-finite (NaN or Inf)."
            )

        # 2. Rate of change check (both rise and fall)
        time_steps = max(1.0, horizon_minutes / 10.0)
        max_allowed_change = round(self.max_rate_change_per_10m * time_steps, 4)
        actual_change = round(abs(predicted_stage - current_stage), 4)

        if actual_change > max_allowed_change:
            direction = "rise" if predicted_stage > current_stage else "fall"
            return ValidationResult(
                status="REJECTED",
                validated_value=current_stage,
                raw_value=predicted_stage,
                reason=f"Predicted rate of {direction} ({actual_change:.3f}m in {horizon_minutes:.0f}min) "
                       f"exceeds maximum physical surge/drawdown limit ({max_allowed_change:.3f}m)."
            )

        # 3. Absolute bounds check
        if predicted_stage < self.min_stage_m:
            if self.allow_correction:
                return ValidationResult(
                    status="CORRECTED",
                    validated_value=self.min_stage_m,
                    raw_value=predicted_stage,
                    reason=f"Predicted stage {predicted_stage:.3f}m fell below riverbed floor ({self.min_stage_m}m); clamped to physical minimum."
                )
            return ValidationResult(
                status="REJECTED",
                validated_value=current_stage,
                raw_value=predicted_stage,
                reason=f"PHYSICAL_FLOOR_VIOLATION: Predicted stage {predicted_stage:.3f}m is below physical riverbed floor ({self.min_stage_m}m)."
            )

        if predicted_stage > self.max_stage_m:
            if self.allow_correction:
                return ValidationResult(
                    status="CORRECTED",
                    validated_value=self.max_stage_m,
                    raw_value=predicted_stage,
                    reason=f"Predicted stage {predicted_stage:.3f}m exceeded dyke crest ({self.max_stage_m}m); clamped to physical maximum."
                )
            return ValidationResult(
                status="REJECTED",
                validated_value=current_stage,
                raw_value=predicted_stage,
                reason=f"PHYSICAL_CREST_VIOLATION: Predicted stage {predicted_stage:.3f}m exceeds physical dyke crest ({self.max_stage_m}m)."
            )

        return ValidationResult(
            status="VALID",
            validated_value=round(predicted_stage, 3),
            raw_value=round(predicted_stage, 3),
            reason="Prediction passed all physical hydraulic plausibility criteria."
        )


class DomainConstraintValidator:
    """
    Evaluates expert domain rules and operational warning thresholds
    established by Central Water Commission (CWC) and district protocols.
    Annotated explicitly as PROTOTYPE_DOMAIN_RULES for prototype demonstration.
    """

    def __init__(
        self,
        alert_stage_m: float = 10.30,
        danger_stage_m: float = 11.00,
        rapid_surge_rate_per_10m: float = 0.50
    ):
        self.alert_stage_m = alert_stage_m
        self.danger_stage_m = danger_stage_m
        self.rapid_surge_rate_per_10m = rapid_surge_rate_per_10m

    def evaluate_rules(
        self,
        validated_stage: float,
        current_stage: float,
        horizon_minutes: float
    ) -> List[Dict[str, Any]]:
        """Evaluates operational alert rules against the validated prediction."""
        alerts = []

        # Rule 1: Danger stage
        if validated_stage >= self.danger_stage_m:
            alerts.append({
                "rule_id": "CRITICAL_DANGER_STAGE_EXCEEDED",
                "severity": "CRITICAL",
                "threshold_m": self.danger_stage_m,
                "message": f"Predicted river stage ({validated_stage:.2f}m) meets or exceeds critical danger level ({self.danger_stage_m:.2f}m).",
                "provenance": "PROTOTYPE_CWC_DISTRICT_CRITICAL"
            })
        # Rule 2: Alert stage
        elif validated_stage >= self.alert_stage_m:
            alerts.append({
                "rule_id": "OPERATIONAL_ALERT_STAGE_EXCEEDED",
                "severity": "WARNING",
                "threshold_m": self.alert_stage_m,
                "message": f"Predicted river stage ({validated_stage:.2f}m) meets or exceeds warning alert level ({self.alert_stage_m:.2f}m).",
                "provenance": "PROTOTYPE_CWC_DISTRICT_ALERT"
            })

        # Rule 3: Rapid flash surge
        steps = max(1.0, horizon_minutes / 10.0)
        rate = round((validated_stage - current_stage) / steps, 4)
        if rate >= self.rapid_surge_rate_per_10m:
            alerts.append({
                "rule_id": "RAPID_FLASH_SURGE_DETECTED",
                "severity": "HIGH",
                "rate_m_per_10m": rate,
                "message": f"Predicted rate of river rise ({rate:.2f}m/10min) indicates rapid flash flood onset.",
                "provenance": "PROTOTYPE_FLASH_SURGE_RULE"
            })

        return alerts
