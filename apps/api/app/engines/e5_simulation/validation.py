"""Hard boundary validation for scenario and simulation parameters."""

import math
from typing import Any, Dict


class ScenarioParameterError(ValueError):
    """Raised when a scenario would create an undefined or impossible state."""


class ScenarioParameterValidator:
    # Explicit prototype envelope. These are engineering safety limits, not
    # claims about real-world hydrology.
    MAX_RAINFALL_MULTIPLIER_DELTA = 5.0
    MAX_RIVER_LEVEL_DELTA_M = 20.0
    MAX_RESOURCE_RATE = 10000.0

    @staticmethod
    def _finite_non_negative(params: Dict[str, Any], key: str, maximum: float) -> None:
        if key not in params:
            return
        value = params[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ScenarioParameterError(f"INVALID_PARAMETER: {key} must be a finite numeric value")
        if value < 0 or value > maximum:
            raise ScenarioParameterError(f"PARAMETER_OUT_OF_RANGE: {key} must be within [0, {maximum}]")

    @classmethod
    def validate(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            raise ScenarioParameterError("INVALID_PARAMETER_SET: scenario parameters must be an object")

        cls._finite_non_negative(params, "rainfall_multiplier_delta", cls.MAX_RAINFALL_MULTIPLIER_DELTA)
        cls._finite_non_negative(params, "river_level_delta_m", cls.MAX_RIVER_LEVEL_DELTA_M)
        for key in (
            "water_consumption_per_person_per_tick",
            "water_consumption_per_person_per_min",
            "water_requirement_per_person",
            "medical_demand_per_person",
            "medical_demand_special_transit",
        ):
            cls._finite_non_negative(params, key, cls.MAX_RESOURCE_RATE)

        if "resource_warning_threshold_ratio" in params:
            value = params["resource_warning_threshold_ratio"]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0 <= value <= 1:
                raise ScenarioParameterError("PARAMETER_OUT_OF_RANGE: resource_warning_threshold_ratio must be within [0, 1]")

        closed = params.get("closed_road_segments", [])
        if not isinstance(closed, list) or any(not isinstance(code, str) or not code.strip() for code in closed):
            raise ScenarioParameterError("INVALID_PARAMETER: closed_road_segments must be a list of non-empty strings")

        reductions = params.get("resource_capacity_reductions", {})
        if not isinstance(reductions, dict):
            raise ScenarioParameterError("INVALID_PARAMETER: resource_capacity_reductions must be an object")
        for destination_code, resource_values in reductions.items():
            if not isinstance(destination_code, str) or not isinstance(resource_values, dict):
                raise ScenarioParameterError("INVALID_PARAMETER: resource reductions must map destination codes to objects")
            for resource_code, multiplier in resource_values.items():
                if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or not math.isfinite(float(multiplier)) or not 0 <= multiplier <= 1:
                    raise ScenarioParameterError(
                        f"PARAMETER_OUT_OF_RANGE: resource reduction {destination_code}/{resource_code} must be within [0, 1]"
                    )

        return params
