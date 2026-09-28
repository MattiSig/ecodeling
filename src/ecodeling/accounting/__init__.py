"""Exact, append-only stock-flow accounting primitives.

Amounts are integer Icelandic krónur (ISK). A posting amount is a signed change in
an account's natural balance: positive increases an asset, liability, or equity
account and negative decreases it. The ledger never stores a mutable balance;
reports are reconstructed from immutable journal entries.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from ecodeling.identifiers import (
    AccountId,
    AgentId,
    ContractId,
    LedgerEntryId,
)
from ecodeling.model.clock import YearMonth

type ISK = int
"""Exact monetary amount in whole Icelandic krónur, never a floating-point value."""


class AccountingError(ValueError):
    """Raised before an invalid operation can change the ledger."""


class Sector(StrEnum):
    """Institutional sectors supported by the model's balance sheets."""

    HOUSEHOLDS = "households"
    FIRMS = "firms"
    BANKS = "banks"
    GOVERNMENT = "government"
    CENTRAL_BANK = "central_bank"
    FOREIGN = "foreign"


class AccountKind(StrEnum):
    """Balance-sheet account classification and its accounting sign."""

    FINANCIAL_ASSET = "financial_asset"
    REAL_ASSET = "real_asset"
    LIABILITY = "liability"
    EQUITY = "equity"

    @property
    def accounting_sign(self) -> int:
        """Return the sign in ``assets - liabilities - equity``."""
        if self in {AccountKind.FINANCIAL_ASSET, AccountKind.REAL_ASSET}:
            return 1
        return -1


@dataclass(frozen=True, slots=True)
class Account:
    """A registered balance-sheet account whose position comes only from postings."""

    id: AccountId
    owner_id: AgentId
    sector: Sector
    name: str
    kind: AccountKind
    claim_id: ContractId | None = None
    allow_negative: bool = False

    def __post_init__(self) -> None:
        """Validate account identity and financial-claim metadata."""
        if not self.id or not self.owner_id or not self.name.strip():
            raise ValueError("account ID, owner ID, and name must be non-empty")
        requires_claim = self.kind in {
            AccountKind.FINANCIAL_ASSET,
            AccountKind.LIABILITY,
        }
        if requires_claim and self.claim_id is None:
            raise ValueError("financial assets and liabilities require a claim ID")
        if not requires_claim and self.claim_id is not None:
            raise ValueError("real asset and equity accounts must not have a claim ID")


@dataclass(frozen=True, slots=True)
class Posting:
    """A signed change in one account's natural balance."""

    account_id: AccountId
    amount: ISK

    def __post_init__(self) -> None:
        """Reject ambiguous zero or non-integer monetary changes."""
        if not self.account_id:
            raise ValueError("posting account ID must be non-empty")
        if type(self.amount) is not int:
            raise TypeError("posting amount must be an integer number of ISK")
        if self.amount == 0:
            raise ValueError("zero-value postings are not permitted")


@dataclass(frozen=True, slots=True)
class TransactionEntry:
    """A balanced cash or contractual transaction journal entry."""

    id: LedgerEntryId
    month: YearMonth
    description: str
    postings: tuple[Posting, ...]

    def __post_init__(self) -> None:
        """Validate structural journal requirements independent of a ledger."""
        _validate_entry_structure(self.id, self.description, self.postings)


@dataclass(frozen=True, slots=True)
class RevaluationEntry:
    """A balanced non-cash change in the value of existing positions."""

    id: LedgerEntryId
    month: YearMonth
    description: str
    postings: tuple[Posting, ...]

    def __post_init__(self) -> None:
        """Validate structural journal requirements independent of a ledger."""
        _validate_entry_structure(self.id, self.description, self.postings)


type JournalEntry = TransactionEntry | RevaluationEntry


def _validate_entry_structure(
    entry_id: LedgerEntryId,
    description: str,
    postings: tuple[Posting, ...],
) -> None:
    if not entry_id or not description.strip():
        raise ValueError("entry ID and description must be non-empty")
    if not isinstance(postings, tuple):
        raise TypeError("entry postings must be an immutable tuple")
    if len(postings) < 2:
        raise ValueError("an entry requires at least two postings")
    account_ids = tuple(posting.account_id for posting in postings)
    if len(account_ids) != len(set(account_ids)):
        raise ValueError("an entry may post to each account only once")


@dataclass(frozen=True, slots=True)
class Position:
    """The reconstructed closing position of one account."""

    account: Account
    balance: ISK


@dataclass(frozen=True, slots=True)
class BalanceSheet:
    """A reconciled balance-sheet report for an agent or aggregate."""

    positions: tuple[Position, ...]
    financial_assets: ISK
    real_assets: ISK
    liabilities: ISK
    equity: ISK

    @property
    def assets(self) -> ISK:
        """Return total real and financial assets."""
        return self.financial_assets + self.real_assets

    @property
    def net_worth(self) -> ISK:
        """Return assets less liabilities, which equals equity when reconciled."""
        return self.assets - self.liabilities

    @property
    def accounting_gap(self) -> ISK:
        """Return ``assets - liabilities - equity``; zero means balanced."""
        return self.net_worth - self.equity


@dataclass(frozen=True, slots=True)
class SectorBalanceSheet:
    """Balance sheet for one institutional sector."""

    sector: Sector
    balance_sheet: BalanceSheet


@dataclass(frozen=True, slots=True)
class SystemBalanceSheet:
    """System totals and sector identities for all registered accounts."""

    sectors: tuple[SectorBalanceSheet, ...]
    financial_assets: ISK
    real_assets: ISK
    financial_liabilities: ISK
    equity: ISK

    @property
    def assets(self) -> ISK:
        """Return total system assets."""
        return self.financial_assets + self.real_assets

    @property
    def financial_claim_gap(self) -> ISK:
        """Return internal financial assets less their mirrored liabilities."""
        return self.financial_assets - self.financial_liabilities

    @property
    def accounting_gap(self) -> ISK:
        """Return the aggregate balance-sheet equation residual."""
        return self.assets - self.financial_liabilities - self.equity


class Ledger:
    """Account registry and append-only journal with atomic invariant checks."""

    def __init__(self) -> None:
        """Create an empty ledger with no opening balances or hidden state."""
        self._accounts: dict[AccountId, Account] = {}
        self._entries: list[JournalEntry] = []
        self._entry_ids: set[LedgerEntryId] = set()

    @property
    def accounts(self) -> tuple[Account, ...]:
        """Return registered accounts in stable registration order."""
        return tuple(self._accounts.values())

    @property
    def entries(self) -> tuple[JournalEntry, ...]:
        """Return the immutable journal view in posting order."""
        return tuple(self._entries)

    @property
    def transactions(self) -> tuple[TransactionEntry, ...]:
        """Return cash/contract transactions separately from revaluations."""
        return tuple(entry for entry in self._entries if isinstance(entry, TransactionEntry))

    @property
    def revaluations(self) -> tuple[RevaluationEntry, ...]:
        """Return non-cash revaluation entries separately from transactions."""
        return tuple(entry for entry in self._entries if isinstance(entry, RevaluationEntry))

    def register_account(self, account: Account) -> None:
        """Register an empty account; balances can only be added by journal entry."""
        if account.id in self._accounts:
            raise AccountingError(f"account ID already exists: {account.id}")
        self._accounts[account.id] = account

    def post(self, entry: JournalEntry) -> None:
        """Validate a complete entry, then append it atomically."""
        self.post_all((entry,))

    def post_all(self, entries: tuple[JournalEntry, ...]) -> None:
        """Validate and append a group of ordered entries as one atomic operation."""
        if not isinstance(entries, tuple):
            raise TypeError("entries must be an immutable tuple")
        if not entries:
            raise ValueError("at least one entry is required")
        entry_ids = tuple(entry.id for entry in entries)
        if len(entry_ids) != len(set(entry_ids)):
            raise AccountingError("batch contains duplicate entry IDs")
        existing = [entry_id for entry_id in entry_ids if entry_id in self._entry_ids]
        if existing:
            raise AccountingError(f"entry ID already exists: {existing[0]}")

        prospective = {account_id: self.balance(account_id) for account_id in self._accounts}
        for entry in entries:
            accounts = self._resolve_accounts(entry)
            self._validate_agent_effects(entry, accounts)
            self._validate_claim_effects(entry, accounts)
            self._validate_prospective_balances(entry, accounts, prospective)
            for posting in entry.postings:
                prospective[posting.account_id] += posting.amount

        self._entries.extend(entries)
        self._entry_ids.update(entry_ids)

    def balance(self, account_id: AccountId) -> ISK:
        """Reconstruct one account balance from the journal."""
        if account_id not in self._accounts:
            raise AccountingError(f"unknown account: {account_id}")
        return sum(
            posting.amount
            for entry in self._entries
            for posting in entry.postings
            if posting.account_id == account_id
        )

    def balance_sheet(self, owner_id: AgentId) -> BalanceSheet:
        """Build one agent's balance sheet from its account positions."""
        return self._report(
            tuple(account for account in self._accounts.values() if account.owner_id == owner_id)
        )

    def sector_balance_sheet(self, sector: Sector) -> SectorBalanceSheet:
        """Build an aggregate balance sheet for an institutional sector."""
        accounts = tuple(account for account in self._accounts.values() if account.sector is sector)
        return SectorBalanceSheet(sector, self._report(accounts))

    def system_balance_sheet(self) -> SystemBalanceSheet:
        """Build system and sector aggregates from all account positions."""
        report = self._report(tuple(self._accounts.values()))
        sectors = tuple(
            self.sector_balance_sheet(sector)
            for sector in Sector
            if any(account.sector is sector for account in self._accounts.values())
        )
        return SystemBalanceSheet(
            sectors=sectors,
            financial_assets=report.financial_assets,
            real_assets=report.real_assets,
            financial_liabilities=report.liabilities,
            equity=report.equity,
        )

    def assert_accounting_invariants(self) -> None:
        """Assert agent equations, mirrored claims, and aggregate identities."""
        owners = {account.owner_id for account in self._accounts.values()}
        for owner_id in owners:
            gap = self.balance_sheet(owner_id).accounting_gap
            if gap != 0:
                raise AccountingError(f"agent balance sheet does not balance: {owner_id} gap={gap}")
        self._assert_current_claims_mirrored()
        report = self.system_balance_sheet()
        if report.financial_claim_gap != 0:
            raise AccountingError(
                f"aggregate financial claims do not cancel: gap={report.financial_claim_gap}"
            )
        if report.accounting_gap != 0:
            raise AccountingError(
                f"system balance sheet does not balance: gap={report.accounting_gap}"
            )

    def _resolve_accounts(self, entry: JournalEntry) -> tuple[Account, ...]:
        missing = [
            posting.account_id
            for posting in entry.postings
            if posting.account_id not in self._accounts
        ]
        if missing:
            raise AccountingError(f"entry references unknown accounts: {missing}")
        return tuple(self._accounts[posting.account_id] for posting in entry.postings)

    def _validate_agent_effects(
        self,
        entry: JournalEntry,
        accounts: tuple[Account, ...],
    ) -> None:
        effects: dict[AgentId, int] = defaultdict(int)
        for posting, account in zip(entry.postings, accounts, strict=True):
            effects[account.owner_id] += account.kind.accounting_sign * posting.amount
        gaps = {owner: effect for owner, effect in effects.items() if effect != 0}
        if gaps:
            raise AccountingError(f"agent accounting effects do not balance: {gaps}")

    def _validate_claim_effects(
        self,
        entry: JournalEntry,
        accounts: tuple[Account, ...],
    ) -> None:
        effects: dict[ContractId, dict[AccountKind, int]] = defaultdict(lambda: defaultdict(int))
        for posting, account in zip(entry.postings, accounts, strict=True):
            if account.claim_id is not None:
                effects[account.claim_id][account.kind] += posting.amount
        claim_kinds = self._claim_kinds()
        incomplete = {
            claim_id: sorted(kind.value for kind in claim_kinds[claim_id])
            for claim_id in effects
            if claim_kinds[claim_id] != {AccountKind.FINANCIAL_ASSET, AccountKind.LIABILITY}
        }
        if incomplete:
            raise AccountingError(
                f"financial claims require asset and liability accounts: {incomplete}"
            )
        mismatches = {
            claim_id: dict(changes)
            for claim_id, changes in effects.items()
            if changes[AccountKind.FINANCIAL_ASSET] != changes[AccountKind.LIABILITY]
        }
        if mismatches:
            raise AccountingError(f"mirrored claim effects do not match: {mismatches}")

    def _validate_prospective_balances(
        self,
        entry: JournalEntry,
        accounts: tuple[Account, ...],
        balances: dict[AccountId, ISK],
    ) -> None:
        for posting, account in zip(entry.postings, accounts, strict=True):
            closing = balances[account.id] + posting.amount
            if closing < 0 and not account.allow_negative:
                raise AccountingError(
                    f"posting would make account negative: {account.id} closing={closing}"
                )

    def _assert_current_claims_mirrored(self) -> None:
        claims: dict[ContractId, dict[AccountKind, int]] = defaultdict(lambda: defaultdict(int))
        for account in self._accounts.values():
            if account.claim_id is not None:
                claims[account.claim_id][account.kind] += self.balance(account.id)
        claim_kinds = self._claim_kinds()
        for claim_id, balances in claims.items():
            if claim_kinds[claim_id] != {
                AccountKind.FINANCIAL_ASSET,
                AccountKind.LIABILITY,
            }:
                raise AccountingError(
                    f"financial claim lacks an asset or liability account: {claim_id}"
                )
            asset = balances[AccountKind.FINANCIAL_ASSET]
            liability = balances[AccountKind.LIABILITY]
            if asset != liability:
                raise AccountingError(
                    f"financial claim is not mirrored: {claim_id} asset={asset} liability={liability}"
                )

    def _claim_kinds(self) -> dict[ContractId, set[AccountKind]]:
        claim_kinds: dict[ContractId, set[AccountKind]] = defaultdict(set)
        for account in self._accounts.values():
            if account.claim_id is not None:
                claim_kinds[account.claim_id].add(account.kind)
        return claim_kinds

    def _report(self, accounts: tuple[Account, ...]) -> BalanceSheet:
        positions = tuple(Position(account, self.balance(account.id)) for account in accounts)
        return BalanceSheet(
            positions=positions,
            financial_assets=sum(
                position.balance
                for position in positions
                if position.account.kind is AccountKind.FINANCIAL_ASSET
            ),
            real_assets=sum(
                position.balance
                for position in positions
                if position.account.kind is AccountKind.REAL_ASSET
            ),
            liabilities=sum(
                position.balance
                for position in positions
                if position.account.kind is AccountKind.LIABILITY
            ),
            equity=sum(
                position.balance
                for position in positions
                if position.account.kind is AccountKind.EQUITY
            ),
        )


__all__ = [
    "ISK",
    "Account",
    "AccountKind",
    "AccountingError",
    "BalanceSheet",
    "JournalEntry",
    "Ledger",
    "Position",
    "Posting",
    "RevaluationEntry",
    "Sector",
    "SectorBalanceSheet",
    "SystemBalanceSheet",
    "TransactionEntry",
]
