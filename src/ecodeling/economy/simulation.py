"""Staged labor, production, goods-market, and endogenous-CPI simulation.

All decisions for a stage are computed from the completed prior stage. Labor and
goods requests are matched before any resulting state is mutated, so registry
iteration cannot grant an agent early access to capacity or inventory.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from ecodeling.accounting import (
    ISK,
    Account,
    AccountKind,
    Ledger,
    Posting,
    RevaluationEntry,
    Sector,
    TransactionEntry,
)
from ecodeling.config.schema import ModelConfig, ShockKind, ShockPersistence
from ecodeling.contracts import (
    IndexObservation,
    MortgageContract,
    MortgagePricing,
    MortgageState,
    MortgageStatus,
    ReferenceIndex,
    calculate_period,
)
from ecodeling.economy.entities import Firm, WorkerHousehold
from ecodeling.economy.outputs import (
    EconomyMonthlyOutput,
    EconomySimulationResult,
    FirmMonthlyOutput,
    ForeignShockEvent,
    HouseholdEconomyMonthlyOutput,
    InterestRateResetEvent,
    MortgageFeedbackEvent,
    PairedEconomyResult,
    PolicyDecisionEvent,
)
from ecodeling.economy.policy import (
    annual_rate_bps,
    coefficient_bps,
    decide_policy_rate,
    passed_through_rate,
)
from ecodeling.identifiers import (
    AccountId,
    AgentId,
    ContractId,
    LedgerEntryId,
    ReferenceIndexId,
    RunId,
    ScenarioId,
)
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
    principal: ISK
    mortgage_state: MortgageState | None
    arrears_months: int = 0
    defaulted: bool = False


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


def _house(household_id: AgentId) -> AccountId:
    return AccountId(f"{household_id}:house")


def _mortgage_liability(household_id: AgentId) -> AccountId:
    return AccountId(f"{household_id}:mortgage")


def _mortgage_asset(mortgage_id: ContractId) -> AccountId:
    return AccountId(f"{_BANK_ID}:{mortgage_id}:mortgage")


def _reserve() -> AccountId:
    return AccountId(f"{_BANK_ID}:external-settlement")


def _external_liability() -> AccountId:
    return AccountId(f"{_EXTERNAL_ID}:settlement-liability")


def _create_agents(config: ModelConfig) -> tuple[tuple[WorkerHousehold, ...], tuple[Firm, ...]]:
    economy = config.real_economy
    initialization_rng = NamedRandomStreams(config.simulation.seed).generator(
        RandomStream.INITIALIZATION
    )
    household_count = config.micro.households
    mortgage_count = int(Decimal(str(config.micro.mortgage_share)) * household_count)
    mortgaged_indexes = set(
        int(index) for index in initialization_rng.permutation(household_count)[:mortgage_count]
    )
    house_values = initialization_rng.integers(30_000_000, 60_000_001, size=household_count)
    ltv_bps = initialization_rng.integers(5_000, 9_001, size=household_count)
    household_rows: list[WorkerHousehold] = []
    for index in range(household_count):
        household_id = AgentId(f"worker-household-{index + 1:05d}")
        if index in mortgaged_indexes:
            house_value = int(house_values[index])
            principal = _round_ratio(house_value * int(ltv_bps[index]), _BPS)
            mortgage_id = ContractId(f"economy-mortgage-{index + 1:05d}")
        else:
            house_value = 0
            principal = 0
            mortgage_id = None
        household_rows.append(
            WorkerHousehold(
                household_id,
                economy.opening_household_deposits_isk,
                house_value,
                principal,
                mortgage_id,
            )
        )
    households = tuple(household_rows)
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
    total_mortgages = 0
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
        if isinstance(agent, WorkerHousehold) and agent.house_value:
            ledger.register_account(
                Account(
                    _house(agent.id),
                    agent.id,
                    Sector.HOUSEHOLDS,
                    "House",
                    AccountKind.REAL_ASSET,
                )
            )
        if isinstance(agent, WorkerHousehold) and agent.mortgage_id is not None:
            ledger.register_account(
                Account(
                    _mortgage_liability(agent.id),
                    agent.id,
                    Sector.HOUSEHOLDS,
                    "Mortgage liability",
                    AccountKind.LIABILITY,
                    agent.mortgage_id,
                )
            )
            ledger.register_account(
                Account(
                    _mortgage_asset(agent.mortgage_id),
                    _BANK_ID,
                    Sector.BANKS,
                    "Mortgage asset",
                    AccountKind.FINANCIAL_ASSET,
                    agent.mortgage_id,
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
        if isinstance(agent, WorkerHousehold) and agent.house_value:
            postings.append(Posting(_house(agent.id), agent.house_value))
            postings.append(Posting(_equity(agent.id), agent.house_value))
        if isinstance(agent, WorkerHousehold) and agent.mortgage_id is not None:
            postings.extend(
                (
                    Posting(_mortgage_liability(agent.id), agent.opening_mortgage),
                    Posting(_mortgage_asset(agent.mortgage_id), agent.opening_mortgage),
                    Posting(_equity(agent.id), -agent.opening_mortgage),
                )
            )
            total_mortgages += agent.opening_mortgage
    postings.extend(
        (
            Posting(_reserve(), total_deposits),
            Posting(_external_liability(), total_deposits),
            Posting(_equity(_EXTERNAL_ID), -total_deposits),
        )
    )
    if total_mortgages:
        postings.append(Posting(_equity(_BANK_ID), total_mortgages))
    opening_changes: dict[AccountId, int] = defaultdict(int)
    for posting in postings:
        opening_changes[posting.account_id] += posting.amount
    ledger.post(
        TransactionEntry(
            LedgerEntryId("economy:opening"),
            month,
            "Opening household, firm, and clearing balance sheets",
            tuple(
                Posting(account_id, amount)
                for account_id, amount in opening_changes.items()
                if amount
            ),
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


def _alpha_bps(config: ModelConfig) -> int:
    return int(
        (Decimal(str(config.indexation.mortgage_alpha)) * Decimal(_BPS)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def _mortgage_contracts(
    config: ModelConfig,
    households: tuple[WorkerHousehold, ...],
) -> dict[AgentId, MortgageContract]:
    alpha_bps = _alpha_bps(config)
    pricing = MortgagePricing(
        real_rate_bps=config.micro.real_rate_bps,
        expected_inflation_bps=config.micro.expected_inflation_bps,
        inflation_risk_premium_bps=config.micro.inflation_risk_premium_bps,
        credit_spread_bps=config.micro.credit_spread_bps,
        term_spread_bps=0,
        bank_margin_bps=0,
    )
    inflation_compensation = (
        config.micro.expected_inflation_bps + config.micro.inflation_risk_premium_bps
    )
    annual_rate_bps = pricing.indexed_coupon_bps + _round_ratio(
        inflation_compensation * (_BPS - alpha_bps), _BPS
    )
    start_month = config.simulation.start_month.add_months(-1)
    reference_id = ReferenceIndexId("endogenous-cpi")
    return {
        household.id: MortgageContract(
            id=household.mortgage_id,
            borrower_id=household.id,
            lender_id=_BANK_ID,
            principal=household.opening_mortgage,
            annual_rate_bps=annual_rate_bps,
            alpha_bps=alpha_bps,
            # CPI is generated at period end, so availability contributes one
            # month in addition to the explicit contractual lag.
            indexation_lag_months=config.indexation.lag_months + 1,
            reference_index_id=reference_id,
            start_month=start_month,
            term_months=config.micro.mortgage_term_months,
            borrower_deposit_account_id=_deposit_asset(household.id),
            lender_deposit_account_id=_deposit_liability(household.id),
            borrower_mortgage_account_id=_mortgage_liability(household.id),
            lender_mortgage_account_id=_mortgage_asset(household.mortgage_id),
            borrower_equity_account_id=_equity(household.id),
            lender_equity_account_id=_equity(_BANK_ID),
        )
        for household in households
        if household.mortgage_id is not None
    }


def run_economy_simulation(config: ModelConfig) -> EconomySimulationResult:
    """Run staged domestic markets with exogenous foreign prices and FX."""
    households, firms = _create_agents(config)
    economy = config.real_economy
    ledger = Ledger()
    _register_and_open(ledger, households, firms, config.simulation.start_month.add_months(-1))
    contracts = _mortgage_contracts(config, households)
    mortgage_start = config.simulation.start_month.add_months(-1)
    household_states = {
        household.id: _HouseholdState(
            None,
            household.opening_deposits,
            household.opening_mortgage,
            (
                MortgageState(
                    household.mortgage_id,
                    mortgage_start,
                    household.opening_mortgage,
                    config.micro.mortgage_term_months,
                    MortgageStatus.ACTIVE,
                )
                if household.mortgage_id is not None
                else None
            ),
        )
        for household in households
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
    feedback_events: list[MortgageFeedbackEvent] = []
    policy_events: list[PolicyDecisionEvent] = []
    rate_reset_events: list[InterestRateResetEvent] = []
    base_price_sum = sum(firm.opening_price for firm in firms)
    baseline_import_price = _round_ratio(
        config.foreign_sector.baseline_exchange_rate_index
        * config.foreign_sector.baseline_foreign_price_index,
        _PRICE_BASE,
    )
    cpi_history = [
        IndexObservation(
            config.simulation.start_month.add_months(-offset),
            _PRICE_BASE,
        )
        for offset in range(config.indexation.lag_months + 2, 0, -1)
    ]
    policy_config = config.monetary_policy
    policy_rate_bps = annual_rate_bps(policy_config.initial_policy_rate_annual)
    reference_policy_rate_bps = policy_rate_bps
    pricing = MortgagePricing(
        real_rate_bps=config.micro.real_rate_bps,
        expected_inflation_bps=config.micro.expected_inflation_bps,
        inflation_risk_premium_bps=config.micro.inflation_risk_premium_bps,
        credit_spread_bps=config.micro.credit_spread_bps,
        term_spread_bps=0,
        bank_margin_bps=0,
    )
    nominal_mortgage_rate_bps = pricing.nominal_coupon_bps
    indexed_mortgage_rate_bps = pricing.indexed_coupon_bps
    deposit_rate_bps = passed_through_rate(
        0,
        policy_rate_bps=policy_rate_bps,
        reference_policy_rate_bps=0,
        pass_through_bps=coefficient_bps(policy_config.deposit_rate_pass_through),
    )
    bank_funding_rate_bps = passed_through_rate(
        0,
        policy_rate_bps=policy_rate_bps,
        reference_policy_rate_bps=0,
        pass_through_bps=coefficient_bps(policy_config.bank_funding_rate_pass_through),
    )

    for offset in range(config.simulation.months):
        month = config.simulation.start_month.add_months(offset)

        # Decisions are made after CPI is known and become available one month
        # later. Each transmission channel then follows its own reset schedule.
        if policy_events:
            source_policy_event = policy_events[-1]
            effective_policy_rate = source_policy_event.policy_rate_bps
            channel_specs = (
                (
                    "nominal_mortgage",
                    offset % policy_config.nominal_mortgage_reset_months == 0,
                    nominal_mortgage_rate_bps,
                    pricing.nominal_coupon_bps,
                    coefficient_bps(policy_config.nominal_mortgage_pass_through),
                ),
                (
                    "indexed_mortgage",
                    offset % policy_config.indexed_mortgage_reset_months == 0,
                    indexed_mortgage_rate_bps,
                    pricing.indexed_coupon_bps,
                    coefficient_bps(policy_config.indexed_mortgage_pass_through),
                ),
                (
                    "deposit",
                    True,
                    deposit_rate_bps,
                    0,
                    coefficient_bps(policy_config.deposit_rate_pass_through),
                ),
                (
                    "bank_funding",
                    True,
                    bank_funding_rate_bps,
                    0,
                    coefficient_bps(policy_config.bank_funding_rate_pass_through),
                ),
            )
            reset_rates: dict[str, int] = {}
            for channel, resets_now, prior_rate, baseline_rate, pass_through in channel_specs:
                if not resets_now:
                    continue
                new_rate = passed_through_rate(
                    baseline_rate,
                    policy_rate_bps=effective_policy_rate,
                    reference_policy_rate_bps=(
                        0 if channel in {"deposit", "bank_funding"} else reference_policy_rate_bps
                    ),
                    pass_through_bps=pass_through,
                )
                reset_rates[channel] = new_rate
                rate_reset_events.append(
                    InterestRateResetEvent(
                        event_id=f"rate-reset:{channel}:{month}",
                        month=month,
                        channel=channel,
                        source_policy_event_id=source_policy_event.event_id,
                        prior_rate_bps=prior_rate,
                        new_rate_bps=new_rate,
                        pass_through_bps=pass_through,
                    )
                )
            nominal_mortgage_rate_bps = reset_rates.get(
                "nominal_mortgage", nominal_mortgage_rate_bps
            )
            indexed_mortgage_rate_bps = reset_rates.get(
                "indexed_mortgage", indexed_mortgage_rate_bps
            )
            deposit_rate_bps = reset_rates.get("deposit", deposit_rate_bps)
            bank_funding_rate_bps = reset_rates.get("bank_funding", bank_funding_rate_bps)

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

        # 7. Mortgage revaluation and settlement use only CPI observations that
        # existed before this period. Payment and balance-sheet effects therefore
        # become available before households form consumption budgets.
        reference_index = ReferenceIndex(ReferenceIndexId("endogenous-cpi"), tuple(cpi_history))
        revaluation_postings: list[Posting] = []
        settlement_postings: list[Posting] = []
        default_postings: list[Posting] = []
        mortgage_values: dict[AgentId, tuple[int, int, int, int, int, bool]] = {}
        total_bank_revaluation = 0
        total_bank_interest = 0
        total_bank_losses = 0
        mortgage_rates: dict[AgentId, int] = {}
        for household in households:
            household_state = household_states[household.id]
            if (
                household_state.mortgage_state is None
                or household_state.defaulted
                or household_state.principal == 0
            ):
                mortgage_values[household.id] = (0, 0, 0, 0, 0, False)
                mortgage_rates[household.id] = 0
                continue
            contract = contracts[household.id]
            mortgage_rate = _round_ratio(
                nominal_mortgage_rate_bps * (_BPS - contract.alpha_bps)
                + indexed_mortgage_rate_bps * contract.alpha_bps,
                _BPS,
            )
            mortgage_rates[household.id] = mortgage_rate
            calculated = calculate_period(
                replace(contract, annual_rate_bps=mortgage_rate),
                household_state.mortgage_state,
                month,
                reference_index,
            )
            revaluation = calculated.indexation_revaluation
            if revaluation:
                revaluation_postings.extend(
                    (
                        Posting(_mortgage_liability(household.id), revaluation),
                        Posting(_equity(household.id), -revaluation),
                        Posting(_mortgage_asset(contracts[household.id].id), revaluation),
                    )
                )
                total_bank_revaluation += revaluation
            actual_payment = min(household_state.deposits, calculated.scheduled_payment)
            interest_paid = min(actual_payment, calculated.interest)
            principal_paid = max(0, actual_payment - calculated.interest)
            unpaid_interest = calculated.interest - interest_paid
            mortgage_change = -principal_paid + unpaid_interest
            if actual_payment:
                settlement_postings.extend(
                    (
                        Posting(_deposit_asset(household.id), -actual_payment),
                        Posting(_deposit_liability(household.id), -actual_payment),
                    )
                )
            if mortgage_change:
                settlement_postings.extend(
                    (
                        Posting(_mortgage_liability(household.id), mortgage_change),
                        Posting(_mortgage_asset(contracts[household.id].id), mortgage_change),
                    )
                )
            if calculated.interest:
                settlement_postings.append(Posting(_equity(household.id), -calculated.interest))
                total_bank_interest += calculated.interest
            household_state.deposits -= actual_payment
            household_state.principal = (
                calculated.preflow_principal + unpaid_interest - principal_paid
            )
            arrears = calculated.scheduled_payment - actual_payment
            household_state.arrears_months = household_state.arrears_months + 1 if arrears else 0
            defaulted_now = (
                household_state.arrears_months >= config.micro.default_after_arrears_months
            )
            if defaulted_now:
                loss = household_state.principal
                default_postings.extend(
                    (
                        Posting(_mortgage_liability(household.id), -loss),
                        Posting(_equity(household.id), loss),
                        Posting(_mortgage_asset(contracts[household.id].id), -loss),
                    )
                )
                total_bank_losses += loss
                household_state.principal = 0
                household_state.defaulted = True
                household_state.mortgage_state = None
            elif household_state.principal == 0:
                household_state.mortgage_state = None
            else:
                household_state.mortgage_state = MortgageState(
                    contracts[household.id].id,
                    month,
                    household_state.principal,
                    max(1, calculated.opening_remaining_payments - 1),
                    MortgageStatus.ACTIVE,
                )
            mortgage_values[household.id] = (
                calculated.scheduled_payment,
                actual_payment,
                calculated.interest,
                revaluation,
                arrears,
                defaulted_now,
            )
        if total_bank_revaluation:
            revaluation_postings.append(Posting(_equity(_BANK_ID), total_bank_revaluation))
        if total_bank_interest:
            settlement_postings.append(Posting(_equity(_BANK_ID), total_bank_interest))
        if total_bank_losses:
            default_postings.append(Posting(_equity(_BANK_ID), -total_bank_losses))
        revaluation_entry = (
            RevaluationEntry(
                LedgerEntryId(f"economy:{month}:cpi-revaluation"),
                month,
                "Lagged endogenous-CPI mortgage revaluation",
                tuple(revaluation_postings),
            )
            if revaluation_postings
            else None
        )
        if revaluation_entry is not None:
            ledger.post(revaluation_entry)
        if settlement_postings:
            ledger.post(
                TransactionEntry(
                    LedgerEntryId(f"economy:{month}:mortgage-settlement"),
                    month,
                    "Mortgage payment and arrears capitalization",
                    tuple(settlement_postings),
                )
            )
        if default_postings:
            ledger.post(
                RevaluationEntry(
                    LedgerEntryId(f"economy:{month}:defaults"),
                    month,
                    "Zero-recovery mortgage default write-down",
                    tuple(default_postings),
                )
            )

        # The stylized bank distributes current mortgage interest as household
        # dividends. This closes the otherwise omitted bank-income circuit while
        # retaining principal repayment, revaluation, arrears, and losses on its
        # balance sheet. Distribution is deterministic and independent of regime.
        if total_bank_interest:
            dividend, remainder = divmod(total_bank_interest, len(households))
            dividend_postings: list[Posting] = [Posting(_equity(_BANK_ID), -total_bank_interest)]
            for index, household in enumerate(households):
                amount = dividend + (index < remainder)
                if amount:
                    household_states[household.id].deposits += amount
                    dividend_postings.extend(
                        (
                            Posting(_deposit_asset(household.id), amount),
                            Posting(_deposit_liability(household.id), amount),
                            Posting(_equity(household.id), amount),
                        )
                    )
            ledger.post(
                TransactionEntry(
                    LedgerEntryId(f"economy:{month}:bank-dividends"),
                    month,
                    "Distribution of current mortgage interest income",
                    tuple(dividend_postings),
                )
            )

        # 8. Randomized search plans purchases against a provisional inventory snapshot.
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

        # 9. Complete expectations and derive CPI only from transacted firm prices.
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
        cpi_history.append(IndexObservation(month, cpi))

        # The current CPI is complete only here. The resulting policy decision
        # cannot affect this month's already-settled mortgages.
        if annual_inflation is not None:
            decision = decide_policy_rate(
                policy_config,
                decision_month=month,
                observed_inflation_bps=annual_inflation,
                prior_policy_rate_bps=policy_rate_bps,
            )
            policy_rate_bps = decision.policy_rate_bps
            policy_events.append(
                PolicyDecisionEvent(
                    event_id=f"policy-decision:{month}",
                    month=month,
                    effective_month=decision.effective_month,
                    inflation_observation_month=month,
                    observed_annual_inflation_bps=decision.observed_inflation_bps,
                    prior_policy_rate_bps=decision.prior_policy_rate_bps,
                    unconstrained_policy_rate_bps=decision.unconstrained_rate_bps,
                    policy_rate_bps=decision.policy_rate_bps,
                    lower_bound_bps=decision.lower_bound_bps,
                    upper_bound_bps=decision.upper_bound_bps,
                )
            )

        for household in households:
            household_state = household_states[household.id]
            scheduled, paid, interest, revaluation, arrears, defaulted_now = mortgage_values[
                household.id
            ]
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
                    scheduled,
                    paid,
                    interest,
                    revaluation,
                    household_state.principal,
                    arrears,
                    household_state.arrears_months,
                    defaulted_now,
                    mortgage_rates[household.id],
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
        total_principal = sum(state.principal for state in household_states.values())
        total_revaluation = sum(value[3] for value in mortgage_values.values())
        total_scheduled = sum(value[0] for value in mortgage_values.values())
        total_paid = sum(value[1] for value in mortgage_values.values())
        arrears_households = sum(value[4] > 0 for value in mortgage_values.values())
        defaults = sum(value[5] for value in mortgage_values.values())
        bank_mortgage_assets = sum(
            ledger.balance(_mortgage_asset(contract.id)) for contract in contracts.values()
        )
        bank_equity = ledger.balance(_equity(_BANK_ID))
        aggregate = EconomyMonthlyOutput(
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
            total_principal,
            total_revaluation,
            total_paid,
            arrears_households,
            defaults,
            bank_mortgage_assets,
            bank_equity,
            revaluation_entry.id if revaluation_entry is not None else None,
            policy_rate_bps,
            nominal_mortgage_rate_bps,
            indexed_mortgage_rate_bps,
            deposit_rate_bps,
            bank_funding_rate_bps,
            total_bank_interest,
        )
        aggregate_outputs.append(aggregate)
        if revaluation_entry is not None:
            referenced_month = month.add_months(-(config.indexation.lag_months + 1))
            previous_month = referenced_month.add_months(-1)
            source_shock = (
                shock_events[0].event_id
                if shock_events and shock_events[0].month <= referenced_month
                else None
            )
            feedback_events.append(
                MortgageFeedbackEvent(
                    event_id=f"mortgage-feedback:{month}",
                    month=month,
                    source_shock_event_id=source_shock,
                    cpi_observation_month=referenced_month,
                    previous_cpi_observation_month=previous_month,
                    cpi_level=reference_index.level(referenced_month),
                    previous_cpi_level=reference_index.level(previous_month),
                    alpha_bps=_alpha_bps(config),
                    mortgage_revaluation=total_revaluation,
                    scheduled_debt_service=total_scheduled,
                    actual_debt_service=total_paid,
                    arrears_households=arrears_households,
                    defaults=defaults,
                    consumption_expenditure=aggregate.household_consumption,
                    bank_equity=bank_equity,
                    revaluation_ledger_entry_id=revaluation_entry.id,
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
        tuple(feedback_events),
        tuple(policy_events),
        tuple(rate_reset_events),
        ledger,
    )


def run_endogenous_indexation_comparison(config: ModelConfig) -> PairedEconomyResult:
    """Run common-seed nominal and fully indexed endogenous economies."""
    nominal_config = config.model_copy(
        update={
            "scenario_id": ScenarioId(f"{config.scenario_id}-nominal"),
            "indexation": config.indexation.model_copy(update={"mortgage_alpha": 0.0}),
        }
    )
    indexed_config = config.model_copy(
        update={
            "scenario_id": ScenarioId(f"{config.scenario_id}-indexed"),
            "indexation": config.indexation.model_copy(update={"mortgage_alpha": 1.0}),
        }
    )
    nominal = run_economy_simulation(nominal_config)
    indexed = run_economy_simulation(indexed_config)
    if nominal.households != indexed.households or nominal.firms != indexed.firms:
        raise AssertionError("paired regimes did not share identical initialization")
    if nominal.shock_events != indexed.shock_events:
        raise AssertionError("paired regimes did not share the configured shock path")
    return PairedEconomyResult(nominal, indexed)
