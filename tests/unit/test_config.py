"""Tests for validated and canonical simulation configuration."""

import json

import pytest
from pydantic import ValidationError

from ecodeling.config.schema import ModelConfig, ShockKind
from ecodeling.identifiers import ScenarioId


def test_default_configuration_is_frozen_and_complete() -> None:
    """Defaults produce the documented 600-month reproducible experiment shape."""
    config = ModelConfig(scenario_id=ScenarioId("baseline"))

    assert config.simulation.months == 600
    assert config.simulation.seed == 123
    assert config.indexation.mortgage_alpha == 1.0
    assert config.indexation.lag_months == 2
    assert config.monetary_policy.inflation_target_annual == 0.025
    assert config.shock.kind is ShockKind.NONE

    with pytest.raises(ValidationError):
        config.simulation.months = 12


@pytest.mark.parametrize(
    ("payload", "location"),
    [
        ({"simulation": {"months": 0}}, "simulation.months"),
        ({"simulation": {"seed": -1}}, "simulation.seed"),
        ({"indexation": {"mortgage_alpha": 1.01}}, "indexation.mortgage_alpha"),
        ({"indexation": {"lag_months": -1}}, "indexation.lag_months"),
        ({"micro": {"mortgage_share": 0.9, "homeowner_share": 0.2}}, "micro"),
        ({"monetary_policy": {"smoothing": 1.01}}, "monetary_policy.smoothing"),
        ({"shock": {"kind": "fx_depreciation", "magnitude": 0.1}}, "shock.month"),
        ({"unknown": True}, "unknown"),
    ],
)
def test_configuration_rejects_invalid_values(
    payload: dict[str, object],
    location: str,
) -> None:
    """Invalid bounds, incomplete shocks, and unknown parameters fail validation."""
    with pytest.raises(ValidationError) as error:
        ModelConfig.model_validate({"scenario_id": "invalid", **payload})

    rendered_locations = {
        ".".join(str(part) for part in item["loc"]) for item in error.value.errors()
    }
    assert location in rendered_locations


def test_canonical_serialization_is_stable_and_hash_covers_parameters() -> None:
    """Equivalent inputs have one JSON encoding and result-affecting changes alter its hash."""
    first = ModelConfig.model_validate(
        {
            "scenario_id": "indexed",
            "simulation": {"seed": 42, "months": 24},
            "shock": {"kind": "fx_depreciation", "month": 12, "magnitude": 0.1},
        }
    )
    second = ModelConfig.model_validate_json(
        json.dumps(
            {
                "shock": {"magnitude": 0.1, "month": 12, "kind": "fx_depreciation"},
                "simulation": {"months": 24, "seed": 42},
                "scenario_id": "indexed",
            }
        )
    )

    assert first.canonical_json() == second.canonical_json()
    assert first.configuration_hash() == second.configuration_hash()
    assert (
        first.configuration_hash()
        != first.model_copy(
            update={"simulation": first.simulation.model_copy(update={"seed": 43})}
        ).configuration_hash()
    )


def test_default_configuration_has_stable_canonical_identity() -> None:
    """The default parameter set has a regression-safe canonical hash."""
    config = ModelConfig(scenario_id=ScenarioId("baseline"))

    assert config.configuration_hash() == (
        "8bfeb048371c6fd8474549d97f70ff8a3e1e113f2e0db9dfe60297ede4bd92e1"
    )
