"""Immutable outputs from labor, production, goods, and price stages."""

from dataclasses import dataclass

from ecodeling.accounting import ISK, Ledger
from ecodeling.config.schema import ShockKind, ShockPersistence
from ecodeling.economy.entities import Firm, WorkerHousehold
from ecodeling.identifiers import AgentId, LedgerEntryId, RunId, ScenarioId
from ecodeling.model.clock import YearMonth


@dataclass(frozen=True, slots=True)
class HouseholdEconomyMonthlyOutput:
    """One household's labor income and goods-market settlement."""

    month: YearMonth
    household_id: AgentId
    employer_id: AgentId | None
    wage_income: ISK
    consumption_budget: ISK
    consumption_units: int
    consumption_expenditure: ISK
    closing_deposits: ISK
    scheduled_mortgage_payment: ISK
    actual_mortgage_payment: ISK
    mortgage_interest: ISK
    mortgage_revaluation: ISK
    closing_mortgage_principal: ISK
    arrears: ISK
    arrears_months: int
    defaulted: bool
    mortgage_rate_bps: int


@dataclass(frozen=True, slots=True)
class FirmMonthlyOutput:
    """One firm's staged employment, physical, price, and cash results."""

    month: YearMonth
    firm_id: AgentId
    employees: int
    desired_employees: int
    vacancies_unfilled: int
    wage: ISK
    wage_bill: ISK
    desired_production: int
    production: int
    capacity: int
    opening_inventory: int
    sales: int
    closing_inventory: int
    price_isk: ISK
    import_share_bps: int
    import_price_index: int
    imported_input_cost_per_unit: ISK
    imported_input_expenditure: ISK
    total_unit_cost: ISK
    revenue: ISK
    cash_profit: ISK
    closing_deposits: ISK
    expected_demand_next: int


@dataclass(frozen=True, slots=True)
class EconomyMonthlyOutput:
    """Conserved market totals and the endogenous consumer price series."""

    month: YearMonth
    employed_households: int
    unemployed_households: int
    vacancies_unfilled: int
    production_units: int
    sales_units: int
    closing_inventory_units: int
    wage_income: ISK
    household_consumption: ISK
    firm_revenue: ISK
    exchange_rate_index: int
    foreign_price_index: int
    import_price_index: int
    imported_input_expenditure: ISK
    import_ledger_entry_id: LedgerEntryId | None
    cpi_level: int
    monthly_inflation_bps: int
    annual_inflation_bps: int | None
    total_mortgage_principal: ISK
    indexation_revaluation: ISK
    debt_service: ISK
    arrears_households: int
    defaults: int
    bank_mortgage_assets: ISK
    bank_equity: ISK
    revaluation_ledger_entry_id: LedgerEntryId | None
    policy_rate_bps: int
    nominal_mortgage_rate_bps: int
    indexed_mortgage_rate_bps: int
    deposit_rate_bps: int
    bank_funding_rate_bps: int
    mortgage_interest: ISK


@dataclass(frozen=True, slots=True)
class MortgageFeedbackEvent:
    """Recorded causal step from an observed CPI movement to financial responses."""

    event_id: str
    month: YearMonth
    source_shock_event_id: str | None
    cpi_observation_month: YearMonth
    previous_cpi_observation_month: YearMonth
    cpi_level: int
    previous_cpi_level: int
    alpha_bps: int
    mortgage_revaluation: ISK
    scheduled_debt_service: ISK
    actual_debt_service: ISK
    arrears_households: int
    defaults: int
    consumption_expenditure: ISK
    bank_equity: ISK
    revaluation_ledger_entry_id: LedgerEntryId


@dataclass(frozen=True, slots=True)
class ForeignShockEvent:
    """Traceable activation of an exogenous FX or foreign-price shock."""

    event_id: str
    month: YearMonth
    kind: ShockKind
    persistence: ShockPersistence
    magnitude_bps: int
    exchange_rate_before: int
    exchange_rate_after: int
    foreign_price_before: int
    foreign_price_after: int
    import_price_before: int
    import_price_after: int


@dataclass(frozen=True, slots=True)
class PolicyDecisionEvent:
    """A bounded month-end policy decision and its information set."""

    event_id: str
    month: YearMonth
    effective_month: YearMonth
    inflation_observation_month: YearMonth
    observed_annual_inflation_bps: int
    prior_policy_rate_bps: int
    unconstrained_policy_rate_bps: int
    policy_rate_bps: int
    lower_bound_bps: int
    upper_bound_bps: int


@dataclass(frozen=True, slots=True)
class InterestRateResetEvent:
    """A policy-linked channel reset using a previously recorded decision."""

    event_id: str
    month: YearMonth
    channel: str
    source_policy_event_id: str
    prior_rate_bps: int
    new_rate_bps: int
    pass_through_bps: int


@dataclass(frozen=True, slots=True)
class EconomySimulationResult:
    """Authoritative endogenous-economy outputs and accounting journal."""

    run_id: RunId
    scenario_id: ScenarioId
    seed: int
    configuration_hash: str
    households: tuple[WorkerHousehold, ...]
    firms: tuple[Firm, ...]
    household_months: tuple[HouseholdEconomyMonthlyOutput, ...]
    firm_months: tuple[FirmMonthlyOutput, ...]
    aggregate_months: tuple[EconomyMonthlyOutput, ...]
    shock_events: tuple[ForeignShockEvent, ...]
    feedback_events: tuple[MortgageFeedbackEvent, ...]
    policy_events: tuple[PolicyDecisionEvent, ...]
    rate_reset_events: tuple[InterestRateResetEvent, ...]
    ledger: Ledger


@dataclass(frozen=True, slots=True)
class PairedEconomyResult:
    """Nominal and fully indexed endogenous runs with common random numbers."""

    nominal: EconomySimulationResult
    indexed: EconomySimulationResult
