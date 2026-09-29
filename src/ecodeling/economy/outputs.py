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
    ledger: Ledger
