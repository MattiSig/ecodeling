"""Staged labor, production, goods-market, and endogenous-CPI simulation.

All decisions for a stage are computed from the completed prior stage. Labor and
goods requests are matched before any resulting state is mutated, so registry
iteration cannot grant an agent early access to capacity or inventory.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from ecodeling.accounting import (
    ISK,
    Account,
    AccountKind,
    Ledger,
    Posting,
    Sector,
    TransactionEntry,
)
from ecodeling.config.schema import ModelConfig, ShockKind, ShockPersistence
from ecodeling.economy.entities import Firm, WorkerHousehold
from ecodeling.economy.outputs import (
    EconomyMonthlyOutput,
    EconomySimulationResult,
    FirmMonthlyOutput,
    ForeignShockEvent,
    HouseholdEconomyMonthlyOutput,
)
from ecodeling.identifiers import AccountId, AgentId, ContractId, LedgerEntryId, RunId
from ecodeling.model.clock import YearMonth
from ecodeling.randomness import NamedRandomStreams, RandomStream

_BPS = 10_000
_PRICE_BASE = 100_000
_BANK_ID = AgentId("economy-clearing-bank")
_EXTERNAL_ID = AgentId("economy-external-sector")


@dataclass(slots=True)
class _FirmState:
    employees: set[AgentId]
    inventory: int
    expected_demand: int
    wage: ISK
    price: ISK
    deposits: ISK


@dataclass(slots=True)
class _HouseholdState:
    employer_id: AgentId | None
    deposits: ISK


def _round_ratio(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return quotient if numerator >= 0 else -quotient


def _ceil_ratio(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return (numerator + denominator - 1) // denominator


def _shock_magnitude_bps(config: ModelConfig) -> int:
    return int(
        (Decimal(str(config.shock.magnitude)) * Decimal(_BPS)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def _baseline_import_cost(labor_unit_cost: ISK, import_share_bps: int) -> ISK:
    if import_share_bps == 0:
        return 0
    return _round_ratio(labor_unit_cost * import_share_bps, _BPS - import_share_bps)


def _foreign_path(config: ModelConfig, offset: int) -> tuple[int, int, int]:
    foreign = config.foreign_sector
    exchange_rate = foreign.baseline_exchange_rate_index
    foreign_price = foreign.baseline_foreign_price_index
    shock = config.shock
    shock_active = shock.month is not None and (
        offset == shock.month
        or (offset > shock.month and shock.persistence is ShockPersistence.PERMANENT)
    )
    if shock_active:
        factor_bps = _BPS + _shock_magnitude_bps(config)
        if shock.kind is ShockKind.FX_DEPRECIATION:
            exchange_rate = _round_ratio(exchange_rate * factor_bps, _BPS)
        elif shock.kind is ShockKind.FOREIGN_PRICE_INCREASE:
            foreign_price = _round_ratio(foreign_price * factor_bps, _BPS)
    import_price = _round_ratio(
        exchange_rate * foreign_price,
        _PRICE_BASE,
    )
    return exchange_rate, foreign_price, import_price


def _deposit_asset(agent_id: AgentId) -> AccountId:
    return AccountId(f"{agent_id}:deposit")


def _deposit_liability(agent_id: AgentId) -> AccountId:
    return AccountId(f"{_BANK_ID}:{agent_id}:deposit")


def _equity(agent_id: AgentId) -> AccountId:
    return AccountId(f"{agent_id}:equity")


def _reserve() -> AccountId:
    return AccountId(f"{_BANK_ID}:external-settlement")


def _external_liability() -> AccountId:
    return AccountId(f"{_EXTERNAL_ID}:settlement-liability")


def _create_agents(config: ModelConfig) -> tuple[tuple[WorkerHousehold, ...], tuple[Firm, ...]]:
    economy = config.real_economy
    households = tuple(
        WorkerHousehold(
            AgentId(f"worker-household-{index + 1:05d}"),
            economy.opening_household_deposits_isk,
        )
        for index in range(config.micro.households)
    )
    labor_unit_cost = _round_ratio(
        economy.monthly_wage_isk,
        economy.productivity_units_per_worker,
    )
    import_unit_cost = _baseline_import_cost(
        labor_unit_cost,
        config.foreign_sector.import_share_bps,
    )
    cost_plus_price = max(
        1,
        _round_ratio(
            (labor_unit_cost + import_unit_cost) * (_BPS + economy.markup_bps),
            _BPS,
        ),
    )
    opening_price = economy.opening_price_isk or cost_plus_price
    monthly_payroll = _ceil_ratio(len(households), economy.firms) * economy.monthly_wage_isk
    firms = tuple(
        Firm(
            id=AgentId(f"firm-{index + 1:03d}"),
            productivity_units_per_worker=economy.productivity_units_per_worker,
            capacity_units=economy.capacity_units_per_firm,
            opening_wage=economy.monthly_wage_isk,
            opening_price=opening_price,
            markup_bps=economy.markup_bps,
            import_share_bps=config.foreign_sector.import_share_bps,
            opening_deposits=monthly_payroll * economy.firm_cash_buffer_months,
        )
        for index in range(economy.firms)
    )
    return households, firms


def _register_and_open(
    ledger: Ledger,
    households: tuple[WorkerHousehold, ...],
    firms: tuple[Firm, ...],
    month: YearMonth,
) -> None:
    reserve_claim = ContractId("economy:external-settlement")
    ledger.register_account(
        Account(
            _reserve(),
            _BANK_ID,
            Sector.BANKS,
            "Settlement reserve",
            AccountKind.FINANCIAL_ASSET,
            reserve_claim,
        )
    )
    ledger.register_account(
        Account(
            _external_liability(),
            _EXTERNAL_ID,
            Sector.FOREIGN,
            "Settlement liability",
            AccountKind.LIABILITY,
            reserve_claim,
        )
    )
    ledger.register_account(
        Account(
            _equity(_BANK_ID),
            _BANK_ID,
            Sector.BANKS,
            "Clearing-bank equity",
            AccountKind.EQUITY,
            allow_negative=True,
        )
    )
    ledger.register_account(
        Account(
            _equity(_EXTERNAL_ID),
            _EXTERNAL_ID,
            Sector.FOREIGN,
            "External-sector equity",
            AccountKind.EQUITY,
            allow_negative=True,
        )
    )
    foreign_deposit_claim = ContractId("economy:deposit:foreign-sector")
    ledger.register_account(
        Account(
            _deposit_asset(_EXTERNAL_ID),
            _EXTERNAL_ID,
            Sector.FOREIGN,
            "Foreign-sector deposit",
            AccountKind.FINANCIAL_ASSET,
            foreign_deposit_claim,
        )
    )
    ledger.register_account(
        Account(
            _deposit_liability(_EXTERNAL_ID),
            _BANK_ID,
            Sector.BANKS,
            "Foreign-sector deposit liability",
            AccountKind.LIABILITY,
            foreign_deposit_claim,
        )
    )
    postings: list[Posting] = []
    total_deposits = 0
    agents: tuple[WorkerHousehold | Firm, ...] = (*households, *firms)
    for agent in agents:
        claim = ContractId(f"economy:deposit:{agent.id}")
        ledger.register_account(
            Account(
                _deposit_asset(agent.id),
                agent.id,
                Sector.HOUSEHOLDS if isinstance(agent, WorkerHousehold) else Sector.FIRMS,
                "Deposit",
                AccountKind.FINANCIAL_ASSET,
                claim,
            )
        )
        ledger.register_account(
            Account(
                _deposit_liability(agent.id),
                _BANK_ID,
                Sector.BANKS,
                f"Deposit liability: {agent.id}",
                AccountKind.LIABILITY,
                claim,
            )
        )
        ledger.register_account(
            Account(
                _equity(agent.id),
                agent.id,
                Sector.HOUSEHOLDS if isinstance(agent, WorkerHousehold) else Sector.FIRMS,
                "Net worth",
                AccountKind.EQUITY,
                allow_negative=True,
            )
        )
        amount = agent.opening_deposits
        if amount:
            postings.extend(
                (
                    Posting(_deposit_asset(agent.id), amount),
                    Posting(_deposit_liability(agent.id), amount),
                    Posting(_equity(agent.id), amount),
                )
            )
            total_deposits += amount
    postings.extend(
        (
            Posting(_reserve(), total_deposits),
            Posting(_external_liability(), total_deposits),
            Posting(_equity(_EXTERNAL_ID), -total_deposits),
        )
    )
    ledger.post(
        TransactionEntry(
            LedgerEntryId("economy:opening"),
            month,
            "Opening household, firm, and clearing balance sheets",
            tuple(postings),
        )
    )


def _transfer_entry(
    entry_id: LedgerEntryId,
    month: YearMonth,
    description: str,
    transfers: tuple[tuple[AgentId, AgentId, ISK], ...],
) -> TransactionEntry | None:
    changes: dict[AccountId, int] = defaultdict(int)
    for payer, recipient, amount in transfers:
        if amount <= 0:
            continue
        changes[_deposit_asset(payer)] -= amount
        changes[_deposit_liability(payer)] -= amount
        changes[_equity(payer)] -= amount
        changes[_deposit_asset(recipient)] += amount
        changes[_deposit_liability(recipient)] += amount
        changes[_equity(recipient)] += amount
    postings = tuple(
        Posting(account_id, amount) for account_id, amount in changes.items() if amount
    )
    return TransactionEntry(entry_id, month, description, postings) if postings else None


def run_economy_simulation(config: ModelConfig) -> EconomySimulationResult:
    """Run staged domestic markets with exogenous foreign prices and FX."""
    households, firms = _create_agents(config)
    economy = config.real_economy
    ledger = Ledger()
    _register_and_open(ledger, households, firms, config.simulation.start_month.add_months(-1))
    household_states = {
        household.id: _HouseholdState(None, household.opening_deposits) for household in households
    }
    full_employment_units = len(households) * economy.productivity_units_per_worker
    expected_per_firm = _ceil_ratio(full_employment_units, len(firms))
    firm_states = {
        firm.id: _FirmState(
            employees=set(),
            inventory=0,
            expected_demand=expected_per_firm,
            wage=firm.opening_wage,
            price=firm.opening_price,
            deposits=firm.opening_deposits,
        )
        for firm in firms
    }
    labor_rng = NamedRandomStreams(config.simulation.seed).generator(RandomStream.LABOR_MATCHING)
    goods_rng = NamedRandomStreams(config.simulation.seed).generator(
        RandomStream.CONSUMPTION_MATCHING
    )
    household_outputs: list[HouseholdEconomyMonthlyOutput] = []
    firm_outputs: list[FirmMonthlyOutput] = []
    aggregate_outputs: list[EconomyMonthlyOutput] = []
    shock_events: list[ForeignShockEvent] = []
    base_price_sum = sum(firm.opening_price for firm in firms)
    baseline_import_price = _round_ratio(
        config.foreign_sector.baseline_exchange_rate_index
        * config.foreign_sector.baseline_foreign_price_index,
        _PRICE_BASE,
    )

    for offset in range(config.simulation.months):
        month = config.simulation.start_month.add_months(offset)

        # 0. Observe the current exogenous FX/foreign-price path before plans are made.
        exchange_rate, foreign_price, import_price = _foreign_path(config, offset)
        if config.shock.month == offset and config.shock.kind is not ShockKind.NONE:
            before_exchange, before_foreign, before_import = _foreign_path(config, offset - 1)
            shock_events.append(
                ForeignShockEvent(
                    event_id=f"foreign-shock:{month}",
                    month=month,
                    kind=config.shock.kind,
                    persistence=config.shock.persistence,
                    magnitude_bps=_shock_magnitude_bps(config),
                    exchange_rate_before=before_exchange,
                    exchange_rate_after=exchange_rate,
                    foreign_price_before=before_foreign,
                    foreign_price_after=foreign_price,
                    import_price_before=before_import,
                    import_price_after=import_price,
                )
            )

        # 1. Firms form production and labor plans from prior sales expectations/inventory.
        desired_production: dict[AgentId, int] = {}
        desired_workers: dict[AgentId, int] = {}
        for firm in firms:
            state = firm_states[firm.id]
            target_inventory = _round_ratio(
                state.expected_demand * economy.inventory_target_bps, _BPS
            )
            desired = min(
                firm.capacity_units,
                max(0, state.expected_demand + target_inventory - state.inventory),
            )
            desired_production[firm.id] = desired
            desired_workers[firm.id] = _ceil_ratio(desired, firm.productivity_units_per_worker)

        # 2. Firings complete before randomized vacancy matching; assignments mutate once.
        retained: dict[AgentId, set[AgentId]] = {}
        released: set[AgentId] = set()
        vacancies: list[AgentId] = []
        for firm in firms:
            current = sorted(firm_states[firm.id].employees, key=str)
            excess = max(0, len(current) - desired_workers[firm.id])
            dismissals = min(
                excess,
                max(1, _ceil_ratio(excess * economy.firing_adjustment_bps, _BPS)) if excess else 0,
            )
            kept = set(current[: len(current) - dismissals] if dismissals else current)
            retained[firm.id] = kept
            released.update(set(current) - kept)
            vacancies.extend([firm.id] * max(0, desired_workers[firm.id] - len(kept)))
        unemployed = [
            household.id
            for household in households
            if household_states[household.id].employer_id is None or household.id in released
        ]
        labor_rng.shuffle(unemployed)
        labor_rng.shuffle(vacancies)
        for household_id, firm_id in zip(unemployed, vacancies, strict=False):
            retained[firm_id].add(household_id)
        for household in households:
            household_states[household.id].employer_id = None
        for firm in firms:
            firm_states[firm.id].employees = retained[firm.id]
            for household_id in retained[firm.id]:
                household_states[household_id].employer_id = firm.id

        # 3. Wages settle through mirrored bank-deposit claims.
        wage_transfers: list[tuple[AgentId, AgentId, ISK]] = []
        wages: dict[AgentId, int] = {household.id: 0 for household in households}
        wage_bills: dict[AgentId, int] = {}
        for firm in firms:
            state = firm_states[firm.id]
            bill = len(state.employees) * state.wage
            if bill > state.deposits:
                raise RuntimeError(f"firm payroll exceeds deposits: {firm.id}")
            wage_bills[firm.id] = bill
            for household_id in sorted(state.employees, key=str):
                wage_transfers.append((firm.id, household_id, state.wage))
                wages[household_id] = state.wage
                household_states[household_id].deposits += state.wage
            state.deposits -= bill
        wage_entry = _transfer_entry(
            LedgerEntryId(f"economy:{month}:wages"),
            month,
            "Firm payroll settlement",
            tuple(wage_transfers),
        )
        if wage_entry is not None:
            ledger.post(wage_entry)

        # 4. Production is bounded by both technology and explicit firm capacity.
        opening_inventory: dict[AgentId, int] = {}
        production: dict[AgentId, int] = {}
        for firm in firms:
            state = firm_states[firm.id]
            opening_inventory[firm.id] = state.inventory
            produced = min(
                desired_production[firm.id],
                firm.capacity_units,
                len(state.employees) * firm.productivity_units_per_worker,
            )
            production[firm.id] = produced
            state.inventory += produced

        # 5. Imported inputs settle with the foreign sector at the observed import price.
        imported_unit_costs: dict[AgentId, int] = {}
        import_expenditures: dict[AgentId, int] = {}
        import_transfers: list[tuple[AgentId, AgentId, ISK]] = []
        for firm in firms:
            labor_unit_cost = _round_ratio(
                firm_states[firm.id].wage,
                firm.productivity_units_per_worker,
            )
            baseline_cost = _baseline_import_cost(labor_unit_cost, firm.import_share_bps)
            imported_unit_cost = _round_ratio(
                baseline_cost * import_price,
                baseline_import_price,
            )
            expenditure = production[firm.id] * imported_unit_cost
            if expenditure > firm_states[firm.id].deposits:
                raise RuntimeError(f"firm import bill exceeds deposits: {firm.id}")
            imported_unit_costs[firm.id] = imported_unit_cost
            import_expenditures[firm.id] = expenditure
            if expenditure:
                firm_states[firm.id].deposits -= expenditure
                import_transfers.append((firm.id, _EXTERNAL_ID, expenditure))
        import_entry = _transfer_entry(
            LedgerEntryId(f"economy:{month}:imports"),
            month,
            "Imported production-input settlement",
            tuple(import_transfers),
        )
        if import_entry is not None:
            ledger.post(import_entry)
        import_entry_id = import_entry.id if import_entry is not None else None

        # 6. Prices respond to labor and import costs plus markup, never directly to CPI.
        prices: dict[AgentId, int] = {}
        total_unit_costs: dict[AgentId, int] = {}
        for firm in firms:
            state = firm_states[firm.id]
            unit_cost = _round_ratio(state.wage, firm.productivity_units_per_worker)
            unit_cost += imported_unit_costs[firm.id]
            total_unit_costs[firm.id] = unit_cost
            target = max(1, _round_ratio(unit_cost * (_BPS + firm.markup_bps), _BPS))
            adjustment = _round_ratio((target - state.price) * economy.price_adjustment_bps, _BPS)
            state.price = max(1, state.price + adjustment)
            prices[firm.id] = state.price

        # 7. Randomized search plans purchases against a provisional inventory snapshot.
        # Firm state is mutated only after the complete allocation plan exists.
        budgets = {
            household.id: min(
                household_states[household.id].deposits,
                _round_ratio(wages[household.id] * economy.consumption_propensity_bps, _BPS),
            )
            for household in households
        }
        remaining_inventory = {firm.id: firm_states[firm.id].inventory for firm in firms}
        allocated_units: dict[AgentId, int] = {household.id: 0 for household in households}
        planned_purchases: list[tuple[AgentId, AgentId, int, ISK]] = []
        household_order = list(households)
        goods_rng.shuffle(household_order)
        price_weights = np.array([1.0 / prices[firm.id] for firm in firms], dtype=np.float64)
        price_weights /= price_weights.sum()
        for household in household_order:
            remaining_budget = budgets[household.id]
            search_order = goods_rng.choice(
                len(firms), size=len(firms), replace=False, p=price_weights
            )
            for firm_index in search_order:
                firm_id = firms[int(firm_index)].id
                units = min(remaining_inventory[firm_id], remaining_budget // prices[firm_id])
                if units:
                    expenditure = units * prices[firm_id]
                    planned_purchases.append((household.id, firm_id, units, expenditure))
                    remaining_inventory[firm_id] -= units
                    remaining_budget -= expenditure
                    allocated_units[household.id] += units
                if not remaining_budget:
                    break

        purchases: list[tuple[AgentId, AgentId, ISK]] = []
        expenditures: dict[AgentId, int] = defaultdict(int)
        revenues: dict[AgentId, int] = defaultdict(int)
        firm_sales: dict[AgentId, int] = defaultdict(int)
        for household_id, firm_id, units, expenditure in planned_purchases:
            purchases.append((household_id, firm_id, expenditure))
            expenditures[household_id] += expenditure
            firm_sales[firm_id] += units
            revenues[firm_id] += expenditure
        for firm in firms:
            firm_states[firm.id].inventory = remaining_inventory[firm.id]
        for household in households:
            expenditure = expenditures[household.id]
            if expenditure:
                household_states[household.id].deposits -= expenditure
        for firm in firms:
            firm_states[firm.id].deposits += revenues[firm.id]
        goods_entry = _transfer_entry(
            LedgerEntryId(f"economy:{month}:goods"),
            month,
            "Consumer-goods settlement",
            tuple(purchases),
        )
        if goods_entry is not None:
            ledger.post(goods_entry)

        # 8. Complete expectations and derive CPI only from transacted firm prices.
        for firm in firms:
            state = firm_states[firm.id]
            state.expected_demand += _round_ratio(
                (firm_sales[firm.id] - state.expected_demand) * economy.expectations_adjustment_bps,
                _BPS,
            )
        total_sales = sum(firm_sales.values())
        if total_sales:
            transaction_price_sum = sum(prices[firm.id] * firm_sales[firm.id] for firm in firms)
            cpi = _round_ratio(
                transaction_price_sum * len(firms) * _PRICE_BASE,
                total_sales * base_price_sum,
            )
        else:
            cpi = _round_ratio(sum(prices.values()) * _PRICE_BASE, base_price_sum)
        prior_cpi = aggregate_outputs[-1].cpi_level if aggregate_outputs else _PRICE_BASE
        monthly_inflation = _round_ratio((cpi - prior_cpi) * _BPS, prior_cpi)
        annual_inflation = (
            _round_ratio(
                (cpi - aggregate_outputs[-12].cpi_level) * _BPS, aggregate_outputs[-12].cpi_level
            )
            if offset >= 12
            else None
        )

        for household in households:
            household_state = household_states[household.id]
            household_outputs.append(
                HouseholdEconomyMonthlyOutput(
                    month,
                    household.id,
                    household_state.employer_id,
                    wages[household.id],
                    budgets[household.id],
                    allocated_units[household.id],
                    expenditures[household.id],
                    household_state.deposits,
                )
            )
        for firm in firms:
            firm_state = firm_states[firm.id]
            firm_outputs.append(
                FirmMonthlyOutput(
                    month,
                    firm.id,
                    len(firm_state.employees),
                    desired_workers[firm.id],
                    max(0, desired_workers[firm.id] - len(firm_state.employees)),
                    firm_state.wage,
                    wage_bills[firm.id],
                    desired_production[firm.id],
                    production[firm.id],
                    firm.capacity_units,
                    opening_inventory[firm.id],
                    firm_sales[firm.id],
                    firm_state.inventory,
                    firm_state.price,
                    firm.import_share_bps,
                    import_price,
                    imported_unit_costs[firm.id],
                    import_expenditures[firm.id],
                    total_unit_costs[firm.id],
                    revenues[firm.id],
                    revenues[firm.id] - wage_bills[firm.id] - import_expenditures[firm.id],
                    firm_state.deposits,
                    firm_state.expected_demand,
                )
            )
        employed = sum(state.employer_id is not None for state in household_states.values())
        aggregate_outputs.append(
            EconomyMonthlyOutput(
                month,
                employed,
                len(households) - employed,
                sum(
                    max(0, desired_workers[firm.id] - len(firm_states[firm.id].employees))
                    for firm in firms
                ),
                sum(production.values()),
                total_sales,
                sum(state.inventory for state in firm_states.values()),
                sum(wages.values()),
                sum(expenditures.values()),
                sum(revenues.values()),
                exchange_rate,
                foreign_price,
                import_price,
                sum(import_expenditures.values()),
                import_entry_id,
                cpi,
                monthly_inflation,
                annual_inflation,
            )
        )
        for household in households:
            assert (
                ledger.balance(_deposit_asset(household.id))
                == household_states[household.id].deposits
            )
        for firm in firms:
            assert ledger.balance(_deposit_asset(firm.id)) == firm_states[firm.id].deposits
        ledger.assert_accounting_invariants()

    identity = hashlib.sha256(f"economy:{config.configuration_hash()}".encode()).hexdigest()[:20]
    return EconomySimulationResult(
        RunId(f"economy-{identity}"),
        config.scenario_id,
        config.simulation.seed,
        config.configuration_hash(),
        households,
        firms,
        tuple(household_outputs),
        tuple(firm_outputs),
        tuple(aggregate_outputs),
        tuple(shock_events),
        ledger,
    )
