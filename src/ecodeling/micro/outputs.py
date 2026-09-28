"""Immutable analytical outputs from household-bank simulations."""

from dataclasses import dataclass

from ecodeling.accounting import ISK, Ledger
from ecodeling.identifiers import AgentId, RunId, ScenarioId
from ecodeling.micro.entities import (
    Bank,
    HomeownerStatus,
    Household,
    LiquidityGroup,
    MortgageRegime,
)
from ecodeling.model.clock import YearMonth


@dataclass(frozen=True, slots=True)
class HouseholdMonthlyOutput:
    """Auditable monthly cash-flow and balance-sheet record for one household."""

    month: YearMonth
    household_id: AgentId
    bank_id: AgentId
    homeowner_status: HomeownerStatus
    mortgage_regime: MortgageRegime
    income_quintile: int
    initial_ltv_quintile: int | None
    liquidity_group: LiquidityGroup
    income: ISK
    consumption: ISK
    scheduled_payment: ISK
    actual_payment: ISK
    interest: ISK
    principal_amortization: ISK
    indexation_revaluation: ISK
    arrears: ISK
    arrears_months: int
    defaulted: bool
    closing_principal: ISK
    deposits: ISK
    net_worth: ISK
    debt_service_to_income_bps: int | None
    debt_to_income_bps: int | None
    ltv_bps: int | None


@dataclass(frozen=True, slots=True)
class CohortMonthlyOutput:
    """Monthly totals for one declared distributional reporting group."""

    month: YearMonth
    dimension: str
    value: str
    households: int
    income: ISK
    consumption: ISK
    mortgage_principal: ISK
    debt_service: ISK
    net_worth: ISK
    defaults: int


@dataclass(frozen=True, slots=True)
class BankMonthlyOutput:
    """Monthly bank balance-sheet and mortgage-income record."""

    month: YearMonth
    bank_id: AgentId
    total_loans: ISK
    indexed_assets: ISK
    nominal_assets: ISK
    net_indexed_position: ISK
    deposits: ISK
    reserves: ISK
    equity: ISK
    capital_ratio_bps: int | None
    interest_income: ISK
    credit_losses: ISK


@dataclass(frozen=True, slots=True)
class AggregateMonthlyOutput:
    """Monthly model-wide prices and household-finance aggregates."""

    month: YearMonth
    cpi_level: int
    monthly_inflation_bps: int
    annual_inflation_bps: int
    households: int
    mortgaged_households: int
    total_income: ISK
    total_consumption: ISK
    real_consumption: ISK
    average_mortgage_principal: ISK
    median_mortgage_principal: ISK
    total_mortgage_principal: ISK
    indexed_revaluation: ISK
    debt_service: ISK
    debt_service_to_income_bps: int | None
    debt_to_income_bps: int | None
    mortgage_ltv_bps: int | None
    household_deposits: ISK
    household_net_worth: ISK
    arrears_households: int
    defaults: int
    arrears_rate_bps: int
    default_rate_bps: int


@dataclass(frozen=True, slots=True)
class MicroSimulationResult:
    """Complete authoritative output and provenance for one micro run."""

    run_id: RunId
    scenario_id: ScenarioId
    seed: int
    configuration_hash: str
    regime: MortgageRegime
    households: tuple[Household, ...]
    banks: tuple[Bank, ...]
    household_months: tuple[HouseholdMonthlyOutput, ...]
    cohort_months: tuple[CohortMonthlyOutput, ...]
    bank_months: tuple[BankMonthlyOutput, ...]
    aggregate_months: tuple[AggregateMonthlyOutput, ...]
    ledger: Ledger


@dataclass(frozen=True, slots=True)
class PairedMicroResult:
    """Nominal/indexed runs sharing population and external paths."""

    nominal: MicroSimulationResult
    indexed: MicroSimulationResult
