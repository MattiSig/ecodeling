"""Deterministic household-bank simulation driven by external income and CPI paths.

The phase-04 boundary deliberately treats wages and consumption as flows across an
external settlement boundary. Firms and endogenous prices arrive in later phases.
Mortgages, deposits, revaluations, arrears capitalization, and defaults are fully
posted to the authoritative ledger in each month.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal, localcontext

import numpy as np

from ecodeling.accounting import (
    ISK,
    Account,
    AccountKind,
    JournalEntry,
    Ledger,
    Posting,
    RevaluationEntry,
    Sector,
    TransactionEntry,
)
from ecodeling.config.schema import ModelConfig
from ecodeling.contracts import (
    IndexObservation,
    MortgageContract,
    MortgagePricing,
    MortgageState,
    MortgageStatus,
    ReferenceIndex,
    calculate_period,
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
from ecodeling.micro.entities import (
    Bank,
    BankRegistry,
    HomeownerStatus,
    Household,
    HouseholdRegistry,
    LiquidityGroup,
    MortgageRegime,
)
from ecodeling.micro.outputs import (
    AggregateMonthlyOutput,
    BankMonthlyOutput,
    CohortMonthlyOutput,
    HouseholdMonthlyOutput,
    MicroSimulationResult,
    PairedMicroResult,
)
from ecodeling.model.clock import YearMonth
from ecodeling.randomness import NamedRandomStreams, RandomStream

_BPS = 10_000
_EXTERNAL_SECTOR_ID = AgentId("external-sector")


@dataclass(frozen=True, slots=True)
class IncomeObservation:
    """Exact income multiplier where 10,000 is the opening price base."""

    month: YearMonth
    level: int

    def __post_init__(self) -> None:
        """Require an exact non-negative multiplier."""
        if type(self.level) is not int or self.level < 0:
            raise ValueError("income path levels must be non-negative integers")


@dataclass(frozen=True, slots=True)
class ExternalPaths:
    """Immutable external CPI and household-income paths."""

    cpi: ReferenceIndex
    income: tuple[IncomeObservation, ...]

    def __post_init__(self) -> None:
        """Require immutable, unique observations in chronological order."""
        if not isinstance(self.income, tuple):
            raise TypeError("income observations must be an immutable tuple")
        months = tuple(item.month for item in self.income)
        if months != tuple(sorted(months)) or len(months) != len(set(months)):
            raise ValueError("income observations must have unique increasing months")

    def income_level(self, month: YearMonth) -> int:
        """Return one external income multiplier without interpolation."""
        for observation in self.income:
            if observation.month == month:
                return observation.level
        raise ValueError(f"missing income observation for {month}")


@dataclass(slots=True)
class _HouseholdState:
    deposits: ISK
    principal: ISK
    mortgage_state: MortgageState | None
    arrears_months: int = 0
    defaulted: bool = False


@dataclass(slots=True)
class _BankState:
    reserves: ISK
    equity: ISK


def _scaled(value: int, level: int) -> int:
    """Round an exact base amount times a basis-point level half away from zero."""
    numerator = value * level
    quotient, remainder = divmod(abs(numerator), _BPS)
    if remainder * 2 >= _BPS:
        quotient += 1
    return quotient if numerator >= 0 else -quotient


def _rounded_ratio(numerator: int, denominator: int) -> int:
    """Round a non-negative exact ratio to the nearest integer."""
    if denominator <= 0:
        raise ValueError("ratio denominator must be positive")
    quotient, remainder = divmod(numerator, denominator)
    return quotient + (remainder * 2 >= denominator)


def _growth_levels(base: int, annual_growth_bps: int, count: int) -> tuple[int, ...]:
    with localcontext() as context:
        context.prec = 50
        annual = Decimal(1) + Decimal(annual_growth_bps) / Decimal(_BPS)
        monthly = annual ** (Decimal(1) / Decimal(12))
        return tuple(
            int((Decimal(base) * monthly**offset).to_integral_value(rounding=ROUND_HALF_UP))
            for offset in range(count)
        )


def constant_external_paths(
    config: ModelConfig,
    *,
    annual_inflation_bps: int = 250,
    annual_income_growth_bps: int = 250,
) -> ExternalPaths:
    """Build deterministic smooth paths long enough for lags and annual inflation."""
    if annual_inflation_bps < -9_999:
        raise ValueError("annual inflation cannot reduce the price level to zero")
    if annual_income_growth_bps < -9_999:
        raise ValueError("annual income growth cannot reduce income to zero")
    history = max(12, config.indexation.lag_months + 1)
    first = config.simulation.start_month.add_months(-history)
    count = config.simulation.months + history
    cpi_levels = _growth_levels(100_000, annual_inflation_bps, count)
    income_levels = _growth_levels(_BPS, annual_income_growth_bps, config.simulation.months)
    return ExternalPaths(
        cpi=ReferenceIndex(
            ReferenceIndexId("external-cpi"),
            tuple(
                IndexObservation(first.add_months(offset), level)
                for offset, level in enumerate(cpi_levels)
            ),
        ),
        income=tuple(
            IncomeObservation(config.simulation.start_month.add_months(offset), level)
            for offset, level in enumerate(income_levels)
        ),
    )


def _validate_paths(config: ModelConfig, paths: ExternalPaths) -> None:
    start = config.simulation.start_month
    for offset in range(-12, config.simulation.months):
        paths.cpi.level(start.add_months(offset))
    for offset in range(config.simulation.months):
        paths.income_level(start.add_months(offset))


def _generate_registries(
    config: ModelConfig,
    regime: MortgageRegime,
) -> tuple[HouseholdRegistry, BankRegistry]:
    micro = config.micro
    rng = NamedRandomStreams(config.simulation.seed).generator(RandomStream.INITIALIZATION)
    count = micro.households
    bank_registry = BankRegistry(
        tuple(Bank(AgentId(f"bank-{i + 1:02d}")) for i in range(micro.banks))
    )
    incomes = rng.integers(300_000, 900_001, size=count)
    house_values = rng.integers(30_000_000, 60_000_001, size=count)
    liquidity_codes = rng.integers(0, 3, size=count)
    ltv_bps = rng.integers(5_000, 9_001, size=count)
    order = rng.permutation(count)
    mortgage_count = int(Decimal(str(micro.mortgage_share)) * count)
    owner_count = int(Decimal(str(micro.homeowner_share)) * count)
    statuses = [HomeownerStatus.RENTER] * count
    for index in order[:mortgage_count]:
        statuses[int(index)] = HomeownerStatus.MORTGAGED
    for index in order[mortgage_count : mortgage_count + owner_count]:
        statuses[int(index)] = HomeownerStatus.DEBT_FREE

    income_quintiles = [0] * count
    for rank, index in enumerate(np.argsort(incomes, kind="stable")):
        income_quintiles[int(index)] = min(5, rank * 5 // count + 1)
    mortgaged = [
        index for index, status in enumerate(statuses) if status is HomeownerStatus.MORTGAGED
    ]
    ltv_quintiles: dict[int, int] = {}
    for rank, index in enumerate(sorted(mortgaged, key=lambda item: (int(ltv_bps[item]), item))):
        ltv_quintiles[index] = min(5, rank * 5 // len(mortgaged) + 1)

    liquidity_groups = (LiquidityGroup.LOW, LiquidityGroup.MIDDLE, LiquidityGroup.HIGH)
    deposit_months_bps = (2_500, 20_000, 80_000)
    propensity_bps = (9_000, 8_000, 6_500)
    households: list[Household] = []
    banks = bank_registry.banks
    for index in range(count):
        household_id = AgentId(f"household-{index + 1:05d}")
        status = statuses[index]
        income = int(incomes[index])
        liquidity_code = int(liquidity_codes[index])
        house = int(house_values[index]) if status is not HomeownerStatus.RENTER else 0
        principal = (
            _scaled(house, int(ltv_bps[index])) if status is HomeownerStatus.MORTGAGED else 0
        )
        household_regime = regime if principal else MortgageRegime.NONE
        households.append(
            Household(
                id=household_id,
                bank_id=banks[index % len(banks)].id,
                gross_monthly_income=income,
                opening_deposits=_scaled(income, deposit_months_bps[liquidity_code]),
                house_value=house,
                opening_mortgage=principal,
                mortgage_id=ContractId(f"mortgage-{index + 1:05d}") if principal else None,
                homeowner_status=status,
                mortgage_regime=household_regime,
                income_quintile=income_quintiles[index],
                initial_ltv_quintile=ltv_quintiles.get(index),
                liquidity_group=liquidity_groups[liquidity_code],
                consumption_propensity_bps=propensity_bps[liquidity_code],
            )
        )
    return HouseholdRegistry(tuple(households)), bank_registry


def _deposit_asset(household: Household) -> AccountId:
    return AccountId(f"{household.id}:deposit")


def _deposit_liability(household: Household) -> AccountId:
    return AccountId(f"{household.bank_id}:{household.id}:deposit")


def _mortgage_liability(household: Household) -> AccountId:
    return AccountId(f"{household.id}:mortgage")


def _mortgage_asset(household: Household) -> AccountId:
    return AccountId(f"{household.bank_id}:{household.mortgage_id}:mortgage")


def _equity(agent_id: AgentId) -> AccountId:
    return AccountId(f"{agent_id}:equity")


def _reserve(bank: Bank) -> AccountId:
    return AccountId(f"{bank.id}:external-settlement")


def _external_settlement_liability(bank: Bank) -> AccountId:
    return AccountId(f"external-sector:{bank.id}:settlement-liability")


def _register_accounts(
    ledger: Ledger,
    households: tuple[Household, ...],
    banks: tuple[Bank, ...],
) -> None:
    ledger.register_account(
        Account(
            _equity(_EXTERNAL_SECTOR_ID),
            _EXTERNAL_SECTOR_ID,
            Sector.FOREIGN,
            "External sector net worth",
            AccountKind.EQUITY,
            allow_negative=True,
        )
    )
    for bank in banks:
        settlement_claim = ContractId(f"external-settlement:{bank.id}")
        ledger.register_account(
            Account(
                _reserve(bank),
                bank.id,
                Sector.BANKS,
                "External settlement asset",
                AccountKind.FINANCIAL_ASSET,
                settlement_claim,
            )
        )
        ledger.register_account(
            Account(
                _external_settlement_liability(bank),
                _EXTERNAL_SECTOR_ID,
                Sector.FOREIGN,
                "External settlement liability",
                AccountKind.LIABILITY,
                settlement_claim,
            )
        )
        ledger.register_account(
            Account(
                _equity(bank.id),
                bank.id,
                Sector.BANKS,
                "Bank equity",
                AccountKind.EQUITY,
                allow_negative=True,
            )
        )
    for household in households:
        deposit_claim = ContractId(f"deposit:{household.id}")
        ledger.register_account(
            Account(
                _deposit_asset(household),
                household.id,
                Sector.HOUSEHOLDS,
                "Bank deposit",
                AccountKind.FINANCIAL_ASSET,
                deposit_claim,
            )
        )
        ledger.register_account(
            Account(
                _deposit_liability(household),
                household.bank_id,
                Sector.BANKS,
                "Household deposit liability",
                AccountKind.LIABILITY,
                deposit_claim,
            )
        )
        ledger.register_account(
            Account(
                _equity(household.id),
                household.id,
                Sector.HOUSEHOLDS,
                "Household net worth",
                AccountKind.EQUITY,
                allow_negative=True,
            )
        )
        if household.house_value:
            ledger.register_account(
                Account(
                    AccountId(f"{household.id}:house"),
                    household.id,
                    Sector.HOUSEHOLDS,
                    "House",
                    AccountKind.REAL_ASSET,
                )
            )
        if household.mortgage_id is not None:
            ledger.register_account(
                Account(
                    _mortgage_liability(household),
                    household.id,
                    Sector.HOUSEHOLDS,
                    "Mortgage liability",
                    AccountKind.LIABILITY,
                    household.mortgage_id,
                )
            )
            ledger.register_account(
                Account(
                    _mortgage_asset(household),
                    household.bank_id,
                    Sector.BANKS,
                    "Mortgage asset",
                    AccountKind.FINANCIAL_ASSET,
                    household.mortgage_id,
                )
            )


def _opening_entry(
    households: tuple[Household, ...],
    banks: tuple[Bank, ...],
    month: YearMonth,
) -> tuple[TransactionEntry, dict[AgentId, _BankState]]:
    postings: list[Posting] = []
    bank_deposits: dict[AgentId, int] = defaultdict(int)
    bank_mortgages: dict[AgentId, int] = defaultdict(int)
    for household in households:
        postings.extend(
            (
                Posting(_deposit_asset(household), household.opening_deposits),
                Posting(_deposit_liability(household), household.opening_deposits),
                Posting(
                    _equity(household.id),
                    household.opening_deposits + household.house_value - household.opening_mortgage,
                ),
            )
        )
        bank_deposits[household.bank_id] += household.opening_deposits
        if household.house_value:
            postings.append(Posting(AccountId(f"{household.id}:house"), household.house_value))
        if household.opening_mortgage:
            postings.extend(
                (
                    Posting(_mortgage_liability(household), household.opening_mortgage),
                    Posting(_mortgage_asset(household), household.opening_mortgage),
                )
            )
            bank_mortgages[household.bank_id] += household.opening_mortgage
    bank_states: dict[AgentId, _BankState] = {}
    total_reserves = 0
    for bank in banks:
        reserves = max(1, bank_deposits[bank.id] // 10)
        equity = bank_mortgages[bank.id] + reserves - bank_deposits[bank.id]
        postings.extend(
            (
                Posting(_reserve(bank), reserves),
                Posting(_external_settlement_liability(bank), reserves),
                Posting(_equity(bank.id), equity),
            )
        )
        total_reserves += reserves
        bank_states[bank.id] = _BankState(reserves=reserves, equity=equity)
    postings.append(Posting(_equity(_EXTERNAL_SECTOR_ID), -total_reserves))
    return (
        TransactionEntry(
            LedgerEntryId("micro:opening"), month, "Opening micro balance sheets", tuple(postings)
        ),
        bank_states,
    )


def _mortgage_contract(
    household: Household,
    config: ModelConfig,
    regime: MortgageRegime,
    pricing: MortgagePricing,
) -> MortgageContract:
    if household.mortgage_id is None:
        raise ValueError("cannot create a mortgage for a debt-free household")
    alpha_bps = (
        0
        if regime is MortgageRegime.NOMINAL
        else int(Decimal(str(config.indexation.mortgage_alpha)) * _BPS)
    )
    coupon = (
        pricing.nominal_coupon_bps
        if regime is MortgageRegime.NOMINAL
        else pricing.indexed_coupon_bps
    )
    return MortgageContract(
        id=household.mortgage_id,
        borrower_id=household.id,
        lender_id=household.bank_id,
        principal=household.opening_mortgage,
        annual_rate_bps=coupon,
        alpha_bps=alpha_bps,
        indexation_lag_months=config.indexation.lag_months,
        reference_index_id=ReferenceIndexId("external-cpi"),
        start_month=config.simulation.start_month.add_months(-1),
        term_months=config.micro.mortgage_term_months,
        borrower_deposit_account_id=_deposit_asset(household),
        lender_deposit_account_id=_deposit_liability(household),
        borrower_mortgage_account_id=_mortgage_liability(household),
        lender_mortgage_account_id=_mortgage_asset(household),
        borrower_equity_account_id=_equity(household.id),
        lender_equity_account_id=_equity(household.bank_id),
    )


def _post_if_any(ledger: Ledger, entry: JournalEntry | None) -> None:
    if entry is not None:
        ledger.post(entry)


def _income_entry(
    month: YearMonth,
    households: tuple[Household, ...],
    incomes: dict[AgentId, ISK],
    banks: dict[AgentId, Bank],
) -> TransactionEntry | None:
    postings: list[Posting] = []
    totals: dict[AgentId, int] = defaultdict(int)
    for household in households:
        income = incomes[household.id]
        if income:
            postings.extend(
                (
                    Posting(_deposit_asset(household), income),
                    Posting(_equity(household.id), income),
                    Posting(_deposit_liability(household), income),
                )
            )
            totals[household.bank_id] += income
    for bank_id, amount in totals.items():
        bank = banks[bank_id]
        postings.extend(
            (
                Posting(_reserve(bank), amount),
                Posting(_external_settlement_liability(bank), amount),
            )
        )
    if totals:
        postings.append(Posting(_equity(_EXTERNAL_SECTOR_ID), -sum(totals.values())))
    if not postings:
        return None
    return TransactionEntry(
        LedgerEntryId(f"micro:{month}:income"),
        month,
        "External household income settlement",
        tuple(postings),
    )


def _cohort_rows(
    month: YearMonth, rows: list[HouseholdMonthlyOutput]
) -> tuple[CohortMonthlyOutput, ...]:
    dimensions: dict[str, Callable[[HouseholdMonthlyOutput], str]] = {
        "income_quintile": lambda row: str(row.income_quintile),
        "homeowner_status": lambda row: row.homeowner_status.value,
        "mortgage_regime": lambda row: row.mortgage_regime.value,
        "initial_ltv_quintile": lambda row: (
            "unavailable" if row.initial_ltv_quintile is None else str(row.initial_ltv_quintile)
        ),
        "liquidity_group": lambda row: row.liquidity_group.value,
    }
    output: list[CohortMonthlyOutput] = []
    for dimension, selector in dimensions.items():
        grouped: dict[str, list[HouseholdMonthlyOutput]] = defaultdict(list)
        for row in rows:
            grouped[selector(row)].append(row)
        for value in sorted(grouped):
            members = grouped[value]
            output.append(
                CohortMonthlyOutput(
                    month,
                    dimension,
                    value,
                    len(members),
                    sum(item.income for item in members),
                    sum(item.consumption for item in members),
                    sum(item.closing_principal for item in members),
                    sum(item.actual_payment for item in members),
                    sum(item.net_worth for item in members),
                    sum(item.defaulted for item in members),
                )
            )
    return tuple(output)


def run_micro_simulation(
    config: ModelConfig,
    paths: ExternalPaths,
    regime: MortgageRegime,
) -> MicroSimulationResult:
    """Run one exact, deterministic household-bank path for a declared regime."""
    if regime not in {MortgageRegime.NOMINAL, MortgageRegime.INDEXED}:
        raise ValueError("a run regime must be nominal or indexed")
    _validate_paths(config, paths)
    household_registry, bank_registry = _generate_registries(config, regime)
    households = household_registry.households
    banks = bank_registry.banks
    bank_lookup = {bank.id: bank for bank in banks}
    ledger = Ledger()
    _register_accounts(ledger, households, banks)
    opening, bank_states = _opening_entry(
        households, banks, config.simulation.start_month.add_months(-1)
    )
    ledger.post(opening)
    pricing = MortgagePricing(
        real_rate_bps=config.micro.real_rate_bps,
        expected_inflation_bps=config.micro.expected_inflation_bps,
        inflation_risk_premium_bps=config.micro.inflation_risk_premium_bps,
        credit_spread_bps=config.micro.credit_spread_bps,
        term_spread_bps=0,
        bank_margin_bps=0,
    )
    contracts = {
        household.id: _mortgage_contract(household, config, regime, pricing)
        for household in households
        if household.mortgage_id is not None
    }
    states = {
        household.id: _HouseholdState(
            deposits=household.opening_deposits,
            principal=household.opening_mortgage,
            mortgage_state=(
                MortgageState(
                    household.mortgage_id,
                    config.simulation.start_month.add_months(-1),
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
    household_outputs: list[HouseholdMonthlyOutput] = []
    cohort_outputs: list[CohortMonthlyOutput] = []
    bank_outputs: list[BankMonthlyOutput] = []
    aggregate_outputs: list[AggregateMonthlyOutput] = []
    base_cpi = paths.cpi.level(config.simulation.start_month)

    for offset in range(config.simulation.months):
        month = config.simulation.start_month.add_months(offset)
        income_level = paths.income_level(month)
        incomes = {
            household.id: _scaled(household.gross_monthly_income, income_level)
            for household in households
        }
        _post_if_any(ledger, _income_entry(month, households, incomes, bank_lookup))
        for household in households:
            income = incomes[household.id]
            states[household.id].deposits += income
            bank_states[household.bank_id].reserves += income

        revaluation_postings: list[Posting] = []
        mortgage_postings: list[Posting] = []
        default_postings: list[Posting] = []
        bank_revaluation: dict[AgentId, int] = defaultdict(int)
        bank_interest: dict[AgentId, int] = defaultdict(int)
        bank_losses: dict[AgentId, int] = defaultdict(int)
        period_values: dict[AgentId, tuple[int, int, int, int, int, int, bool]] = {}
        for household in households:
            state = states[household.id]
            if state.mortgage_state is None or state.defaulted or state.principal == 0:
                period_values[household.id] = (0, 0, 0, 0, 0, 0, False)
                continue
            calculated = calculate_period(
                contracts[household.id], state.mortgage_state, month, paths.cpi
            )
            revaluation = calculated.indexation_revaluation
            if revaluation:
                revaluation_postings.extend(
                    (
                        Posting(_mortgage_liability(household), revaluation),
                        Posting(_equity(household.id), -revaluation),
                        Posting(_mortgage_asset(household), revaluation),
                    )
                )
                bank_revaluation[household.bank_id] += revaluation
            available = state.deposits
            actual_payment = min(available, calculated.scheduled_payment)
            interest_paid = min(actual_payment, calculated.interest)
            principal_paid = max(0, actual_payment - calculated.interest)
            unpaid_interest = calculated.interest - interest_paid
            mortgage_change = -principal_paid + unpaid_interest
            if actual_payment:
                mortgage_postings.extend(
                    (
                        Posting(_deposit_asset(household), -actual_payment),
                        Posting(_deposit_liability(household), -actual_payment),
                    )
                )
            if mortgage_change:
                mortgage_postings.extend(
                    (
                        Posting(_mortgage_liability(household), mortgage_change),
                        Posting(_mortgage_asset(household), mortgage_change),
                    )
                )
            if calculated.interest:
                mortgage_postings.append(Posting(_equity(household.id), -calculated.interest))
                bank_interest[household.bank_id] += calculated.interest
            state.deposits -= actual_payment
            state.principal = calculated.preflow_principal + unpaid_interest - principal_paid
            arrears = calculated.scheduled_payment - actual_payment
            state.arrears_months = state.arrears_months + 1 if arrears else 0
            defaulted_now = state.arrears_months >= config.micro.default_after_arrears_months
            if defaulted_now:
                loss = state.principal
                default_postings.extend(
                    (
                        Posting(_mortgage_liability(household), -loss),
                        Posting(_equity(household.id), loss),
                        Posting(_mortgage_asset(household), -loss),
                    )
                )
                bank_losses[household.bank_id] += loss
                state.principal = 0
                state.defaulted = True
                state.mortgage_state = None
            elif state.principal == 0:
                state.mortgage_state = None
            else:
                state.mortgage_state = MortgageState(
                    contracts[household.id].id,
                    month,
                    state.principal,
                    max(1, calculated.opening_remaining_payments - 1),
                    MortgageStatus.ACTIVE,
                )
            period_values[household.id] = (
                calculated.scheduled_payment,
                actual_payment,
                calculated.interest,
                principal_paid,
                revaluation,
                arrears,
                defaulted_now,
            )
        for bank_id, amount in bank_revaluation.items():
            revaluation_postings.append(Posting(_equity(bank_id), amount))
            bank_states[bank_id].equity += amount
        for bank_id, amount in bank_interest.items():
            mortgage_postings.append(Posting(_equity(bank_id), amount))
            bank_states[bank_id].equity += amount
        for bank_id, amount in bank_losses.items():
            default_postings.append(Posting(_equity(bank_id), -amount))
            bank_states[bank_id].equity -= amount
        _post_if_any(
            ledger,
            RevaluationEntry(
                LedgerEntryId(f"micro:{month}:cpi-revaluation"),
                month,
                "Lagged CPI mortgage revaluation",
                tuple(revaluation_postings),
            )
            if revaluation_postings
            else None,
        )
        _post_if_any(
            ledger,
            TransactionEntry(
                LedgerEntryId(f"micro:{month}:mortgage-settlement"),
                month,
                "Mortgage payment and arrears capitalization",
                tuple(mortgage_postings),
            )
            if mortgage_postings
            else None,
        )
        _post_if_any(
            ledger,
            RevaluationEntry(
                LedgerEntryId(f"micro:{month}:defaults"),
                month,
                "Zero-recovery mortgage default write-down",
                tuple(default_postings),
            )
            if default_postings
            else None,
        )

        consumption_postings: list[Posting] = []
        bank_consumption: dict[AgentId, int] = defaultdict(int)
        consumption_values: dict[AgentId, int] = {}
        for household in households:
            state = states[household.id]
            desired = _scaled(incomes[household.id], household.consumption_propensity_bps)
            consumption = min(desired, state.deposits)
            consumption_values[household.id] = consumption
            if consumption:
                consumption_postings.extend(
                    (
                        Posting(_deposit_asset(household), -consumption),
                        Posting(_equity(household.id), -consumption),
                        Posting(_deposit_liability(household), -consumption),
                    )
                )
                bank_consumption[household.bank_id] += consumption
                state.deposits -= consumption
        for bank_id, amount in bank_consumption.items():
            bank = bank_lookup[bank_id]
            consumption_postings.extend(
                (
                    Posting(_reserve(bank), -amount),
                    Posting(_external_settlement_liability(bank), -amount),
                )
            )
            bank_states[bank_id].reserves -= amount
        if bank_consumption:
            consumption_postings.append(
                Posting(_equity(_EXTERNAL_SECTOR_ID), sum(bank_consumption.values()))
            )
        _post_if_any(
            ledger,
            TransactionEntry(
                LedgerEntryId(f"micro:{month}:consumption"),
                month,
                "Consumption paid across external settlement boundary",
                tuple(consumption_postings),
            )
            if consumption_postings
            else None,
        )

        month_rows: list[HouseholdMonthlyOutput] = []
        for household in households:
            state = states[household.id]
            scheduled, paid, interest, amortization, revaluation, arrears, defaulted_now = (
                period_values[household.id]
            )
            income = incomes[household.id]
            row = HouseholdMonthlyOutput(
                month,
                household.id,
                household.bank_id,
                household.homeowner_status,
                household.mortgage_regime,
                household.income_quintile,
                household.initial_ltv_quintile,
                household.liquidity_group,
                income,
                consumption_values[household.id],
                scheduled,
                paid,
                interest,
                amortization,
                revaluation,
                arrears,
                state.arrears_months,
                defaulted_now,
                state.principal,
                state.deposits,
                state.deposits + household.house_value - state.principal,
                paid * _BPS // income if income else None,
                state.principal * _BPS // (income * 12) if income else None,
                state.principal * _BPS // household.house_value if household.house_value else None,
            )
            month_rows.append(row)
        household_outputs.extend(month_rows)
        cohort_outputs.extend(_cohort_rows(month, month_rows))

        for bank in banks:
            members = [row for row in month_rows if row.bank_id == bank.id]
            loans = sum(row.closing_principal for row in members)
            indexed = loans if regime is MortgageRegime.INDEXED else 0
            nominal = loans if regime is MortgageRegime.NOMINAL else 0
            deposits = sum(row.deposits for row in members)
            bank_state = bank_states[bank.id]
            assert bank_state.equity == loans + bank_state.reserves - deposits
            bank_outputs.append(
                BankMonthlyOutput(
                    month,
                    bank.id,
                    loans,
                    indexed,
                    nominal,
                    indexed,
                    deposits,
                    bank_state.reserves,
                    bank_state.equity,
                    bank_state.equity * _BPS // loans if loans else None,
                    bank_interest[bank.id],
                    bank_losses[bank.id],
                )
            )
        cpi = paths.cpi.level(month)
        previous_cpi = paths.cpi.level(month.add_months(-1))
        annual_base = paths.cpi.level(month.add_months(-12))
        borrower_principals = sorted(
            row.closing_principal
            for row in month_rows
            if row.homeowner_status is HomeownerStatus.MORTGAGED
        )
        borrower_count = len(borrower_principals)
        total_principal = sum(borrower_principals)
        middle = borrower_count // 2
        if not borrower_principals:
            median_principal = 0
        elif borrower_count % 2:
            median_principal = borrower_principals[middle]
        else:
            median_principal = _rounded_ratio(
                borrower_principals[middle - 1] + borrower_principals[middle], 2
            )
        total_income = sum(row.income for row in month_rows)
        total_debt_service = sum(row.actual_payment for row in month_rows)
        mortgaged_house_value = sum(
            household.house_value
            for household in households
            if household.homeowner_status is HomeownerStatus.MORTGAGED
        )
        arrears_households = sum(row.arrears > 0 for row in month_rows)
        defaults = sum(row.defaulted for row in month_rows)
        aggregate_outputs.append(
            AggregateMonthlyOutput(
                month,
                cpi,
                (cpi - previous_cpi) * _BPS // previous_cpi,
                (cpi - annual_base) * _BPS // annual_base,
                len(households),
                sum(row.closing_principal > 0 for row in month_rows),
                total_income,
                sum(row.consumption for row in month_rows),
                sum(row.consumption for row in month_rows) * base_cpi // cpi,
                _rounded_ratio(total_principal, borrower_count) if borrower_count else 0,
                median_principal,
                total_principal,
                sum(row.indexation_revaluation for row in month_rows),
                total_debt_service,
                total_debt_service * _BPS // total_income if total_income else None,
                total_principal * _BPS // (total_income * 12) if total_income else None,
                total_principal * _BPS // mortgaged_house_value if mortgaged_house_value else None,
                sum(row.deposits for row in month_rows),
                sum(row.net_worth for row in month_rows),
                arrears_households,
                defaults,
                arrears_households * _BPS // len(households),
                defaults * _BPS // len(households),
            )
        )
        ledger.assert_accounting_invariants()

    identity = hashlib.sha256(
        f"{config.configuration_hash()}:{regime.value}:{paths.cpi.observations}:{paths.income}".encode()
    ).hexdigest()[:24]
    return MicroSimulationResult(
        RunId(identity),
        config.scenario_id,
        config.simulation.seed,
        config.configuration_hash(),
        regime,
        households,
        banks,
        tuple(household_outputs),
        tuple(cohort_outputs),
        tuple(bank_outputs),
        tuple(aggregate_outputs),
        ledger,
    )


def run_nominal_indexed_comparison(
    config: ModelConfig,
    paths: ExternalPaths,
) -> PairedMicroResult:
    """Run a common-seed, common-path comparison differing only in loan regime."""
    nominal_config = config.model_copy(
        update={
            "scenario_id": ScenarioId(f"{config.scenario_id}-nominal"),
            "indexation": config.indexation.model_copy(update={"mortgage_alpha": 0.0}),
        }
    )
    indexed_config = config.model_copy(
        update={"scenario_id": ScenarioId(f"{config.scenario_id}-indexed")}
    )
    nominal = run_micro_simulation(nominal_config, paths, MortgageRegime.NOMINAL)
    indexed = run_micro_simulation(indexed_config, paths, MortgageRegime.INDEXED)
    common_nominal = tuple(
        replace(item, mortgage_regime=MortgageRegime.NONE) for item in nominal.households
    )
    common_indexed = tuple(
        replace(item, mortgage_regime=MortgageRegime.NONE) for item in indexed.households
    )
    if common_nominal != common_indexed:
        raise AssertionError("paired regimes did not share identical initialization")
    return PairedMicroResult(nominal=nominal, indexed=indexed)
