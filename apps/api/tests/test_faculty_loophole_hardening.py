import math

import pytest
from pydantic import ValidationError

from app.engines.e5_simulation.validation import ScenarioParameterError, ScenarioParameterValidator
from app.schemas.simulation import SimulationRunCreateDTO


def test_simulation_zero_and_declared_maximum_parameters_are_valid():
    params = ScenarioParameterValidator.validate({
        "rainfall_multiplier_delta": 0.0,
        "river_level_delta_m": 0.0,
        "resource_warning_threshold_ratio": 0.0,
        "resource_capacity_reductions": {"DEST_01": {"WATER": 0.0}},
    })
    assert params["rainfall_multiplier_delta"] == 0.0
    assert params["river_level_delta_m"] == 0.0

    ScenarioParameterValidator.validate({
        "rainfall_multiplier_delta": ScenarioParameterValidator.MAX_RAINFALL_MULTIPLIER_DELTA,
        "river_level_delta_m": ScenarioParameterValidator.MAX_RIVER_LEVEL_DELTA_M,
        "water_requirement_per_person": ScenarioParameterValidator.MAX_RESOURCE_RATE,
    })


@pytest.mark.parametrize(
    "params",
    [
        {"rainfall_multiplier_delta": -0.01},
        {"rainfall_multiplier_delta": float("nan")},
        {"river_level_delta_m": ScenarioParameterValidator.MAX_RIVER_LEVEL_DELTA_M + 0.01},
        {"resource_warning_threshold_ratio": 1.01},
        {"resource_capacity_reductions": {"DEST_01": {"WATER": 1.1}}},
        {"closed_road_segments": [""]},
    ],
)
def test_impossible_simulation_parameters_fail_explicitly(params):
    with pytest.raises(ScenarioParameterError):
        ScenarioParameterValidator.validate(params)


def test_api_schema_rejects_negative_or_excessive_simulation_bounds():
    with pytest.raises(ValidationError):
        SimulationRunCreateDTO(timestep_minutes=0)
    with pytest.raises(ValidationError):
        SimulationRunCreateDTO(duration_minutes=10080.1)
