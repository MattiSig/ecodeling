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


class MicroSimulationConfig(FrozenConfigModel):
    """Population and stylized household-bank behavior for the micro model."""

    households: Annotated[int, Field(ge=10, le=10_000)] = 1_000
    banks: Annotated[int, Field(ge=1, le=20)] = 2
    mortgage_share: Probability = 0.70
    homeowner_share: Probability = 0.15
    mortgage_term_months: Annotated[int, Field(ge=12, le=1_200)] = 600
    default_after_arrears_months: Annotated[int, Field(ge=2, le=24)] = 3
    real_rate_bps: Annotated[int, Field(ge=0, le=10_000)] = 300
    expected_inflation_bps: Annotated[int, Field(ge=0, le=10_000)] = 250
    inflation_risk_premium_bps: Annotated[int, Field(ge=0, le=10_000)] = 50
    credit_spread_bps: Annotated[int, Field(ge=0, le=10_000)] = 50

    @model_validator(mode="after")
    def validate_tenure_shares(self) -> Self:
        """Leave a non-negative renter share after owner groups are assigned."""
        if self.mortgage_share + self.homeowner_share > 1.0:
            raise ValueError("mortgage and debt-free homeowner shares cannot exceed one")
        return self


class RealEconomyConfig(FrozenConfigModel):
    """Firm, labor, goods-market, and price parameters for the v0.1 economy."""

    firms: Annotated[int, Field(ge=2, le=500)] = 20
    monthly_wage_isk: Annotated[int, Field(ge=1)] = 450_000
    productivity_units_per_worker: Annotated[int, Field(ge=1)] = 400
    capacity_units_per_firm: Annotated[int, Field(ge=1)] = 25_000
    opening_price_isk: Annotated[int, Field(ge=1)] | None = None
    markup_bps: Annotated[int, Field(ge=0, le=20_000)] = 0
    price_adjustment_bps: Annotated[int, Field(ge=0, le=10_000)] = 2_500
    expectations_adjustment_bps: Annotated[int, Field(ge=0, le=10_000)] = 5_000
    inventory_target_bps: Annotated[int, Field(ge=0, le=20_000)] = 1_000
    firing_adjustment_bps: Annotated[int, Field(ge=1, le=10_000)] = 2_500
    consumption_propensity_bps: Annotated[int, Field(ge=0, le=10_000)] = 10_000
    opening_household_deposits_isk: Annotated[int, Field(ge=0)] = 450_000
    firm_cash_buffer_months: Annotated[int, Field(ge=1, le=1_200)] = 120

    @model_validator(mode="after")
    def validate_capacity_supports_one_worker(self) -> Self:
        """Reject a capacity below one worker's declared technology."""
        if self.capacity_units_per_firm < self.productivity_units_per_worker:
            raise ValueError("firm capacity must support at least one worker")
        return self


class ForeignSectorConfig(FrozenConfigModel):
    """Exogenous foreign prices, exchange rates, and imported-input exposure."""

    baseline_exchange_rate_index: Annotated[int, Field(ge=1)] = 100_000
    baseline_foreign_price_index: Annotated[int, Field(ge=1)] = 100_000
    import_share_bps: Annotated[int, Field(ge=0, lt=10_000)] = 0


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
    FOREIGN_PRICE_INCREASE = "foreign_price_increase"


class ShockPersistence(StrEnum):
    """Supported transparent paths after an exogenous shock starts."""

    ONE_OFF = "one_off"
    PERMANENT = "permanent"


class ShockConfig(FrozenConfigModel):
    """Timing and magnitude of the configured external shock."""

    kind: ShockKind = ShockKind.NONE
    month: Annotated[int, Field(ge=0)] | None = None
    magnitude: Annotated[float, Field(gt=-1.0, allow_inf_nan=False)] = 0.0
    persistence: ShockPersistence = ShockPersistence.PERMANENT

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
    micro: MicroSimulationConfig = Field(default_factory=MicroSimulationConfig)
    real_economy: RealEconomyConfig = Field(default_factory=RealEconomyConfig)
    foreign_sector: ForeignSectorConfig = Field(default_factory=ForeignSectorConfig)
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
