"""Deterministic amortizing mortgages backed by typed ledger events.

Mortgage periods are processed in a fixed order: opening state, lagged CPI
revaluation, cash-flow calculation, settlement, and closing state. Monetary
amounts are whole ISK and every rounding operation uses half away from zero.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal, localcontext
from enum import StrEnum

from ecodeling.accounting import (
    ISK,
    AccountKind,
    JournalEntry,
    Ledger,
    Posting,
    RevaluationEntry,
    TransactionEntry,
)
from ecodeling.identifiers import (
    AccountId,
    AgentId,
    ContractId,
    LedgerEntryId,
    ReferenceIndexId,
)
from ecodeling.model.clock import YearMonth

_BASIS_POINTS_PER_UNIT = 10_000
_MONTHLY_RATE_DENOMINATOR = 12 * _BASIS_POINTS_PER_UNIT


class ContractError(ValueError):
    """Raised when contract terms or lifecycle transitions are invalid."""


class MortgageStatus(StrEnum):
    """Lifecycle status of an isolated mortgage contract."""

    ACTIVE = "active"
    PAID_OFF = "paid_off"


@dataclass(frozen=True, slots=True)
class IndexObservation:
    """A strictly positive integer reference-index level for one month."""

    month: YearMonth
    level: int

    def __post_init__(self) -> None:
        """Reject non-integer and non-positive index levels."""
        if type(self.level) is not int or self.level <= 0:
            raise ValueError("reference-index level must be a positive integer")


@dataclass(frozen=True, slots=True)
class ReferenceIndex:
    """Immutable monthly reference-index history used by lagged contracts."""

    id: ReferenceIndexId
    observations: tuple[IndexObservation, ...]

    def __post_init__(self) -> None:
        """Require immutable, unique observations in chronological order."""
        if not self.id:
            raise ValueError("reference-index ID must be non-empty")
        if not isinstance(self.observations, tuple):
            raise TypeError("index observations must be an immutable tuple")
        months = tuple(observation.month for observation in self.observations)
        if months != tuple(sorted(months)) or len(months) != len(set(months)):
            raise ValueError("index observations must have unique increasing months")

    def level(self, month: YearMonth) -> int:
        """Return one observed level or fail instead of interpolating data."""
        for observation in self.observations:
            if observation.month == month:
                return observation.level
        raise ContractError(f"missing reference-index observation for {month}")

    def lagged_levels(self, payment_month: YearMonth, lag_months: int) -> tuple[int, int]:
        """Return ``(current, previous)`` levels for the declared lag."""
        referenced_month = payment_month.add_months(-lag_months)
        previous_month = referenced_month.add_months(-1)
        return self.level(referenced_month), self.level(previous_month)


@dataclass(frozen=True, slots=True)
class MortgagePricing:
    """Documented stylized decomposition for indexed and nominal coupons."""

    real_rate_bps: int
    expected_inflation_bps: int
    inflation_risk_premium_bps: int
    credit_spread_bps: int
    term_spread_bps: int
    bank_margin_bps: int

    def __post_init__(self) -> None:
        """Require exact non-negative basis-point components."""
        for name in (
            "real_rate_bps",
            "expected_inflation_bps",
            "inflation_risk_premium_bps",
            "credit_spread_bps",
            "term_spread_bps",
            "bank_margin_bps",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    @property
    def indexed_coupon_bps(self) -> int:
        """Return real rate plus credit, term, and bank spreads."""
        return (
            self.real_rate_bps
            + self.credit_spread_bps
            + self.term_spread_bps
            + self.bank_margin_bps
        )

    @property
    def nominal_coupon_bps(self) -> int:
        """Add expected inflation and inflation risk to the indexed coupon."""
        return (
            self.indexed_coupon_bps + self.expected_inflation_bps + self.inflation_risk_premium_bps
        )


@dataclass(frozen=True, slots=True)
class MortgageContract:
    """Immutable mortgage terms and the ledger accounts used for settlement."""

    id: ContractId
    borrower_id: AgentId
    lender_id: AgentId
    principal: ISK
    annual_rate_bps: int
    alpha_bps: int
    indexation_lag_months: int
    reference_index_id: ReferenceIndexId
    start_month: YearMonth
    term_months: int
    borrower_deposit_account_id: AccountId
    lender_deposit_account_id: AccountId
    borrower_mortgage_account_id: AccountId
    lender_mortgage_account_id: AccountId
    borrower_equity_account_id: AccountId
    lender_equity_account_id: AccountId

    def __post_init__(self) -> None:
        """Validate exact monetary, rate, indexation, and account terms."""
        if not self.id or not self.borrower_id or not self.lender_id or not self.reference_index_id:
            raise ValueError("contract, parties, and reference-index IDs must be non-empty")
        if self.borrower_id == self.lender_id:
            raise ValueError("mortgage borrower and lender must differ")
        if type(self.principal) is not int or self.principal <= 0:
            raise ValueError("mortgage principal must be a positive integer ISK amount")
        if type(self.annual_rate_bps) is not int or self.annual_rate_bps < 0:
            raise ValueError("annual rate must be non-negative integer basis points")
        if type(self.alpha_bps) is not int or not 0 <= self.alpha_bps <= 10_000:
            raise ValueError("indexation alpha must be integer basis points from 0 to 10000")
        if type(self.indexation_lag_months) is not int or self.indexation_lag_months < 0:
            raise ValueError("indexation lag must be a non-negative integer month count")
        if type(self.term_months) is not int or self.term_months < 1:
            raise ValueError("mortgage term must be a positive integer month count")
        account_ids = (
            self.borrower_deposit_account_id,
            self.lender_deposit_account_id,
            self.borrower_mortgage_account_id,
            self.lender_mortgage_account_id,
            self.borrower_equity_account_id,
            self.lender_equity_account_id,
        )
        if any(not account_id for account_id in account_ids):
            raise ValueError("all mortgage ledger account IDs must be non-empty")
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("mortgage ledger account IDs must be distinct")

    @property
    def maturity_month(self) -> YearMonth:
        """Return the final payment month after ``term_months`` installments."""
        return self.start_month.add_months(self.term_months)


@dataclass(frozen=True, slots=True)
class MortgageState:
    """Authoritative opening or closing state for one mortgage period."""

    contract_id: ContractId
    month: YearMonth
    principal: ISK
    remaining_payments: int
    status: MortgageStatus

    def __post_init__(self) -> None:
        """Keep active and paid-off state combinations unambiguous."""
        if type(self.principal) is not int or self.principal < 0:
            raise ValueError("mortgage state principal must be non-negative integer ISK")
        if type(self.remaining_payments) is not int or self.remaining_payments < 0:
            raise ValueError("remaining payments must be a non-negative integer")
        if self.status is MortgageStatus.ACTIVE and (
            self.principal == 0 or self.remaining_payments == 0
        ):
            raise ValueError("an active mortgage requires principal and remaining payments")
        if self.status is MortgageStatus.PAID_OFF and (
            self.principal != 0 or self.remaining_payments != 0
        ):
            raise ValueError("a paid-off mortgage must have zero principal and payments")


@dataclass(frozen=True, slots=True)
class MortgagePeriodResult:
    """Complete opening-to-closing trace for one monthly mortgage period."""

    contract_id: ContractId
    month: YearMonth
    opening_principal: ISK
    indexation_revaluation: ISK
    preflow_principal: ISK
    interest: ISK
    scheduled_payment: ISK
    principal_payment: ISK
    closing_principal: ISK
    opening_remaining_payments: int
    closing_remaining_payments: int
    status: MortgageStatus
    revaluation_entry_id: LedgerEntryId | None = None
    settlement_entry_id: LedgerEntryId | None = None

    def __post_init__(self) -> None:
        """Assert the period's stock-flow and payment decomposition identities."""
        if self.opening_principal + self.indexation_revaluation != self.preflow_principal:
            raise ValueError("preflow principal does not reconcile")
        if self.preflow_principal - self.principal_payment != self.closing_principal:
            raise ValueError("closing principal does not reconcile")
        if self.interest + self.principal_payment != self.scheduled_payment:
            raise ValueError("payment decomposition does not reconcile")
        if not 0 <= self.principal_payment <= self.preflow_principal:
            raise ValueError("principal payment lies outside payoff bounds")
        if self.status is MortgageStatus.PAID_OFF:
            if self.closing_principal != 0 or self.closing_remaining_payments != 0:
                raise ValueError("paid-off period must close with zero principal and payments")
        elif self.closing_principal == 0 or self.closing_remaining_payments == 0:
            raise ValueError("active period must retain principal and remaining payments")


def calculate_indexation(
    opening_principal: ISK,
    alpha_bps: int,
    referenced_level: int,
    previous_level: int,
) -> ISK:
    """Calculate symmetric CPI principal revaluation, rounded to whole ISK."""
    if type(opening_principal) is not int or opening_principal < 0:
        raise ValueError("opening principal must be a non-negative integer ISK amount")
    if type(alpha_bps) is not int or not 0 <= alpha_bps <= _BASIS_POINTS_PER_UNIT:
        raise ValueError("indexation alpha must be integer basis points from 0 to 10000")
    if type(referenced_level) is not int or referenced_level <= 0:
        raise ValueError("referenced index level must be a positive integer")
    if type(previous_level) is not int or previous_level <= 0:
        raise ValueError("previous index level must be a positive integer")
    numerator = opening_principal * alpha_bps * (referenced_level - previous_level)
    denominator = _BASIS_POINTS_PER_UNIT * previous_level
    revaluation = _round_ratio_half_away_from_zero(numerator, denominator)
    return max(-opening_principal, revaluation)


def _round_ratio_half_away_from_zero(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("rounding denominator must be positive")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


def _round_decimal_isk(value: Decimal) -> ISK:
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


def _interest(principal: ISK, annual_rate_bps: int) -> ISK:
    return _round_ratio_half_away_from_zero(
        principal * annual_rate_bps,
        _MONTHLY_RATE_DENOMINATOR,
    )


def _annuity_payment(principal: ISK, annual_rate_bps: int, payments: int) -> ISK:
    if principal == 0:
        return 0
    if payments == 1:
        return principal + _interest(principal, annual_rate_bps)
    interest = _interest(principal, annual_rate_bps)
    if annual_rate_bps == 0:
        rounded = _round_ratio_half_away_from_zero(principal, payments)
    else:
        with localcontext() as context:
            context.prec = 50
            monthly_rate = Decimal(annual_rate_bps) / Decimal(_MONTHLY_RATE_DENOMINATOR)
            factor = (Decimal(1) + monthly_rate) ** (-payments)
            rounded = _round_decimal_isk(Decimal(principal) * monthly_rate / (Decimal(1) - factor))
    total_due = principal + interest
    return min(total_due, max(interest + 1, rounded))


def calculate_period(
    contract: MortgageContract,
    opening: MortgageState,
    month: YearMonth,
    reference_index: ReferenceIndex,
) -> MortgagePeriodResult:
    """Purely calculate one ordered mortgage lifecycle without ledger mutation."""
    if opening.contract_id != contract.id:
        raise ContractError("opening state belongs to a different contract")
    if opening.status is not MortgageStatus.ACTIVE or opening.remaining_payments < 1:
        raise ContractError("cannot advance a paid-off mortgage")
    expected_month = opening.month.add_months(1)
    if month != expected_month:
        raise ContractError(f"expected mortgage month {expected_month}, received {month}")

    revaluation = 0
    if contract.alpha_bps != 0:
        referenced, previous = reference_index.lagged_levels(month, contract.indexation_lag_months)
        revaluation = calculate_indexation(
            opening.principal,
            contract.alpha_bps,
            referenced,
            previous,
        )
    preflow = opening.principal + revaluation
    interest = _interest(preflow, contract.annual_rate_bps)
    payment = _annuity_payment(
        preflow,
        contract.annual_rate_bps,
        opening.remaining_payments,
    )
    principal_payment = payment - interest
    closing = preflow - principal_payment
    closing_remaining = 0 if closing == 0 else opening.remaining_payments - 1
    status = MortgageStatus.PAID_OFF if closing == 0 else MortgageStatus.ACTIVE
    return MortgagePeriodResult(
        contract_id=contract.id,
        month=month,
        opening_principal=opening.principal,
        indexation_revaluation=revaluation,
        preflow_principal=preflow,
        interest=interest,
        scheduled_payment=payment,
        principal_payment=principal_payment,
        closing_principal=closing,
        opening_remaining_payments=opening.remaining_payments,
        closing_remaining_payments=closing_remaining,
        status=status,
    )


class ContractRegistry:
    """Mortgage registry coordinating lifecycle state and atomic ledger events."""

    def __init__(self, ledger: Ledger, reference_indexes: tuple[ReferenceIndex, ...]) -> None:
        """Bind the registry to authoritative accounting and reference data."""
        if not isinstance(reference_indexes, tuple):
            raise TypeError("reference indexes must be an immutable tuple")
        index_ids = tuple(index.id for index in reference_indexes)
        if len(index_ids) != len(set(index_ids)):
            raise ValueError("reference-index IDs must be unique")
        self._ledger = ledger
        self._reference_indexes = {index.id: index for index in reference_indexes}
        self._contracts: dict[ContractId, MortgageContract] = {}
        self._states: dict[ContractId, MortgageState] = {}
        self._history: dict[ContractId, list[MortgagePeriodResult]] = {}

    @property
    def contracts(self) -> tuple[MortgageContract, ...]:
        """Return registered contracts in stable registration order."""
        return tuple(self._contracts.values())

    def state(self, contract_id: ContractId) -> MortgageState:
        """Return the current immutable state of a registered contract."""
        try:
            return self._states[contract_id]
        except KeyError as error:
            raise ContractError(f"unknown contract: {contract_id}") from error

    def history(self, contract_id: ContractId) -> tuple[MortgagePeriodResult, ...]:
        """Return completed period traces for a registered contract."""
        if contract_id not in self._history:
            raise ContractError(f"unknown contract: {contract_id}")
        return tuple(self._history[contract_id])

    def register_mortgage(self, contract: MortgageContract) -> MortgageState:
        """Register and originate a mortgage through a balanced ledger event."""
        if contract.id in self._contracts:
            raise ContractError(f"contract ID already exists: {contract.id}")
        if contract.reference_index_id not in self._reference_indexes:
            raise ContractError(f"unknown contract reference index: {contract.reference_index_id}")
        self._validate_accounts(contract)
        opening_entry = self._opening_entry(contract)
        self._ledger.post(opening_entry)
        opening = MortgageState(
            contract_id=contract.id,
            month=contract.start_month,
            principal=contract.principal,
            remaining_payments=contract.term_months,
            status=MortgageStatus.ACTIVE,
        )
        self._contracts[contract.id] = contract
        self._states[contract.id] = opening
        self._history[contract.id] = []
        return opening

    def advance(self, contract_id: ContractId, month: YearMonth) -> MortgagePeriodResult:
        """Calculate, settle, and close exactly one due mortgage period."""
        try:
            contract = self._contracts[contract_id]
        except KeyError as error:
            raise ContractError(f"unknown contract: {contract_id}") from error
        opening = self._states[contract_id]
        calculated = calculate_period(
            contract,
            opening,
            month,
            self._reference_indexes[contract.reference_index_id],
        )
        entries, revaluation_id, settlement_id = self._period_entries(contract, calculated)
        self._ledger.post_all(entries)
        completed = replace(
            calculated,
            revaluation_entry_id=revaluation_id,
            settlement_entry_id=settlement_id,
        )
        self._states[contract_id] = MortgageState(
            contract_id=contract.id,
            month=month,
            principal=completed.closing_principal,
            remaining_payments=completed.closing_remaining_payments,
            status=completed.status,
        )
        self._history[contract_id].append(completed)
        return completed

    def _validate_accounts(self, contract: MortgageContract) -> None:
        accounts = {account.id: account for account in self._ledger.accounts}
        expected = (
            (
                contract.borrower_deposit_account_id,
                contract.borrower_id,
                AccountKind.FINANCIAL_ASSET,
            ),
            (
                contract.lender_deposit_account_id,
                contract.lender_id,
                AccountKind.LIABILITY,
            ),
            (
                contract.borrower_mortgage_account_id,
                contract.borrower_id,
                AccountKind.LIABILITY,
            ),
            (
                contract.lender_mortgage_account_id,
                contract.lender_id,
                AccountKind.FINANCIAL_ASSET,
            ),
            (
                contract.borrower_equity_account_id,
                contract.borrower_id,
                AccountKind.EQUITY,
            ),
            (
                contract.lender_equity_account_id,
                contract.lender_id,
                AccountKind.EQUITY,
            ),
        )
        for account_id, owner_id, kind in expected:
            account = accounts.get(account_id)
            if account is None:
                raise ContractError(f"mortgage account is not registered: {account_id}")
            if account.owner_id != owner_id or account.kind is not kind:
                raise ContractError(
                    f"mortgage account has incompatible ownership/type: {account_id}"
                )
        borrower_deposit = accounts[contract.borrower_deposit_account_id]
        lender_deposit = accounts[contract.lender_deposit_account_id]
        if borrower_deposit.claim_id != lender_deposit.claim_id:
            raise ContractError("borrower and lender deposit accounts must mirror one claim")
        borrower_mortgage = accounts[contract.borrower_mortgage_account_id]
        lender_mortgage = accounts[contract.lender_mortgage_account_id]
        if borrower_mortgage.claim_id != contract.id or lender_mortgage.claim_id != contract.id:
            raise ContractError("mortgage asset and liability claim IDs must equal contract ID")
        for equity_id in (
            contract.borrower_equity_account_id,
            contract.lender_equity_account_id,
        ):
            if not accounts[equity_id].allow_negative:
                raise ContractError(
                    "mortgage equity accounts must explicitly allow negative balances"
                )

    @staticmethod
    def _opening_entry(contract: MortgageContract) -> TransactionEntry:
        return TransactionEntry(
            id=LedgerEntryId(f"mortgage:{contract.id}:opening"),
            month=contract.start_month,
            description=f"Originate mortgage {contract.id}",
            postings=(
                Posting(contract.borrower_deposit_account_id, contract.principal),
                Posting(contract.borrower_mortgage_account_id, contract.principal),
                Posting(contract.lender_mortgage_account_id, contract.principal),
                Posting(contract.lender_deposit_account_id, contract.principal),
            ),
        )

    @staticmethod
    def _period_entries(
        contract: MortgageContract,
        period: MortgagePeriodResult,
    ) -> tuple[tuple[JournalEntry, ...], LedgerEntryId | None, LedgerEntryId | None]:
        entries: list[JournalEntry] = []
        revaluation_id: LedgerEntryId | None = None
        settlement_id: LedgerEntryId | None = None
        month_key = str(period.month)
        if period.indexation_revaluation != 0:
            revaluation_id = LedgerEntryId(f"mortgage:{contract.id}:{month_key}:revaluation")
            change = period.indexation_revaluation
            entries.append(
                RevaluationEntry(
                    id=revaluation_id,
                    month=period.month,
                    description=f"Revalue mortgage {contract.id} from lagged CPI",
                    postings=(
                        Posting(contract.borrower_mortgage_account_id, change),
                        Posting(contract.borrower_equity_account_id, -change),
                        Posting(contract.lender_mortgage_account_id, change),
                        Posting(contract.lender_equity_account_id, change),
                    ),
                )
            )
        if period.scheduled_payment != 0:
            settlement_id = LedgerEntryId(f"mortgage:{contract.id}:{month_key}:settlement")
            postings = [
                Posting(contract.borrower_deposit_account_id, -period.scheduled_payment),
                Posting(contract.lender_deposit_account_id, -period.scheduled_payment),
                Posting(contract.borrower_mortgage_account_id, -period.principal_payment),
                Posting(contract.lender_mortgage_account_id, -period.principal_payment),
            ]
            if period.interest != 0:
                postings.extend(
                    (
                        Posting(contract.borrower_equity_account_id, -period.interest),
                        Posting(contract.lender_equity_account_id, period.interest),
                    )
                )
            entries.append(
                TransactionEntry(
                    id=settlement_id,
                    month=period.month,
                    description=f"Settle mortgage {contract.id} payment",
                    postings=tuple(postings),
                )
            )
        if not entries:
            raise ContractError("mortgage period produced no ledger events")
        return tuple(entries), revaluation_id, settlement_id
