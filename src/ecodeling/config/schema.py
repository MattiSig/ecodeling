"""Frozen, validated configuration and canonical run identity."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from ecodeling.identifiers import ScenarioId
from ecodeling.model.clock import YearMonth

Probability = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
NonNegativeFinite = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class FrozenConfigModel(BaseModel):
    """Base configuration that rejects unknown or post-validation changes."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class SimulationConfig(FrozenConfigModel):
    """Calendar, duration, and master randomness parameters."""

    months: Annotated[int, Field(ge=1, le=1_200)] = 600
    seed: Annotated[int, Field(ge=0, le=2**64 - 1)] = 123
    start_month: YearMonth = YearMonth(2025, 1)


class IndexationConfig(FrozenConfigModel):
    """Mortgage CPI indexation parameters for the v0.1 mechanism."""

    mortgage_alpha: Probability = 1.0
    lag_months: Annotated[int, Field(ge=0, le=120)] = 2


class MonetaryPolicyConfig(FrozenConfigModel):
    """Parameters for the later inflation-response policy rule."""

    inflation_target_annual: NonNegativeFinite = 0.025
    phi_pi: NonNegativeFinite = 1.5
    smoothing: Probability = 0.8
    minimum_rate_annual: Annotated[float, Field(allow_inf_nan=False)] = 0.0
    maximum_rate_annual: Annotated[float, Field(allow_inf_nan=False)] = 1.0

    @model_validator(mode="after")
    def validate_rate_bounds(self) -> Self:
        """Require an ordered interval for future policy-rate decisions."""
        if self.minimum_rate_annual > self.maximum_rate_annual:
            raise ValueError("minimum policy rate must not exceed maximum policy rate")
        return self


class ShockKind(StrEnum):
    """Shock processes supported by the v0.1 configuration contract."""

    NONE = "none"
    FX_DEPRECIATION = "fx_depreciation"


class ShockConfig(FrozenConfigModel):
    """Timing and magnitude of the configured external shock."""

    kind: ShockKind = ShockKind.NONE
    month: Annotated[int, Field(ge=0)] | None = None
    magnitude: Annotated[float, Field(allow_inf_nan=False)] = 0.0

    @field_validator("month")
    @classmethod
    def require_month_for_active_shock(
        cls,
        month: int | None,
        info: ValidationInfo,
    ) -> int | None:
        """Require an explicit zero-based month for an active shock."""
        if info.data.get("kind") is not ShockKind.NONE and month is None:
            raise ValueError("active shock requires a month")
        return month

    @model_validator(mode="after")
    def validate_inactive_shock(self) -> Self:
        """Keep the no-shock configuration semantically unambiguous."""
        if self.kind is ShockKind.NONE and (self.month is not None or self.magnitude != 0.0):
            raise ValueError("no-shock configuration cannot set month or magnitude")
        return self


class ModelConfig(FrozenConfigModel):
    """Complete result-affecting configuration for a reproducible model run."""

    scenario_id: Annotated[ScenarioId, Field(min_length=1)]
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    indexation: IndexationConfig = Field(default_factory=IndexationConfig)
    monetary_policy: MonetaryPolicyConfig = Field(default_factory=MonetaryPolicyConfig)
    shock: ShockConfig = Field(default_factory=ShockConfig)

    @model_validator(mode="after")
    def validate_shock_horizon(self) -> Self:
        """Prevent configured shocks from falling outside the simulation horizon."""
        if self.shock.month is not None and self.shock.month >= self.simulation.months:
            raise ValueError("shock month must fall within the simulation horizon")
        return self

    def canonical_json(self) -> str:
        """Serialize all explicit and default parameters in canonical JSON form."""
        payload = self.model_dump(mode="json")
        return json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def configuration_hash(self) -> str:
        """Return the SHA-256 identity of the canonical configuration."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
