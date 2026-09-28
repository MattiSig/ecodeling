"""Shared accounting fixtures."""

import pytest

from ecodeling.accounting import (
    Account,
    AccountKind,
    Ledger,
    Posting,
    Sector,
    TransactionEntry,
)
from ecodeling.identifiers import AccountId, AgentId, ContractId, LedgerEntryId
from ecodeling.model.clock import YearMonth


def _register_deposit_pair(
    ledger: Ledger,
    *,
    household_number: int,
) -> None:
    household = f"household-{household_number}"
    claim = ContractId(f"{household}-deposit-claim")
    ledger.register_account(
        Account(
            id=AccountId(f"{household}-deposit"),
            owner_id=AgentId(household),
            sector=Sector.HOUSEHOLDS,
            name="Bank deposit",
            kind=AccountKind.FINANCIAL_ASSET,
            claim_id=claim,
        )
    )
    ledger.register_account(
        Account(
            id=AccountId(f"bank-1-{household}-deposit"),
            owner_id=AgentId("bank-1"),
            sector=Sector.BANKS,
            name="Deposit liability",
            kind=AccountKind.LIABILITY,
            claim_id=claim,
        )
    )
    ledger.register_account(
        Account(
            id=AccountId(f"{household}-equity"),
            owner_id=AgentId(household),
            sector=Sector.HOUSEHOLDS,
            name="Net worth",
            kind=AccountKind.EQUITY,
        )
    )


def build_funded_ledger(opening_balance: int = 1) -> Ledger:
    """Build one household deposit mirrored by a bank liability."""
    ledger = Ledger()
    _register_deposit_pair(ledger, household_number=1)
    ledger.register_account(
        Account(
            id=AccountId("bank-1-operating-asset"),
            owner_id=AgentId("bank-1"),
            sector=Sector.BANKS,
            name="Opening operating asset",
            kind=AccountKind.REAL_ASSET,
        )
    )
    ledger.post(
        TransactionEntry(
            id=LedgerEntryId("opening-deposit"),
            month=YearMonth(2025, 1),
            description="Opening household deposit and bank position",
            postings=(
                Posting(AccountId("household-1-deposit"), opening_balance),
                Posting(AccountId("household-1-equity"), opening_balance),
                Posting(AccountId("bank-1-operating-asset"), opening_balance),
                Posting(AccountId("bank-1-household-1-deposit"), opening_balance),
            ),
        )
    )
    return ledger


@pytest.fixture
def funded_ledger() -> Ledger:
    """Provide one household deposit mirrored by a bank liability."""
    return build_funded_ledger()


def build_transfer_ledger() -> Ledger:
    """Build two households holding deposits at the same bank."""
    ledger = build_funded_ledger(100_00)
    _register_deposit_pair(ledger, household_number=2)
    return ledger


@pytest.fixture
def transfer_ledger() -> Ledger:
    """Two households holding deposits at the same bank."""
    return build_transfer_ledger()


@pytest.fixture
def mortgage_ledger() -> Ledger:
    """A household mortgage mirrored as a bank asset."""
    ledger = Ledger()
    mortgage_claim = ContractId("mortgage-1")
    for account in (
        Account(
            AccountId("household-1-house"),
            AgentId("household-1"),
            Sector.HOUSEHOLDS,
            "House",
            AccountKind.REAL_ASSET,
        ),
        Account(
            AccountId("household-1-mortgage"),
            AgentId("household-1"),
            Sector.HOUSEHOLDS,
            "Mortgage liability",
            AccountKind.LIABILITY,
            mortgage_claim,
        ),
        Account(
            AccountId("household-1-equity"),
            AgentId("household-1"),
            Sector.HOUSEHOLDS,
            "Net worth",
            AccountKind.EQUITY,
            allow_negative=True,
        ),
        Account(
            AccountId("bank-1-mortgage"),
            AgentId("bank-1"),
            Sector.BANKS,
            "Mortgage asset",
            AccountKind.FINANCIAL_ASSET,
            mortgage_claim,
        ),
        Account(
            AccountId("bank-1-equity"),
            AgentId("bank-1"),
            Sector.BANKS,
            "Bank equity",
            AccountKind.EQUITY,
        ),
    ):
        ledger.register_account(account)
    ledger.post(
        TransactionEntry(
            id=LedgerEntryId("opening-mortgage"),
            month=YearMonth(2025, 1),
            description="Opening mortgage and house",
            postings=(
                Posting(AccountId("household-1-house"), 100_00),
                Posting(AccountId("household-1-mortgage"), 80_00),
                Posting(AccountId("household-1-equity"), 20_00),
                Posting(AccountId("bank-1-mortgage"), 80_00),
                Posting(AccountId("bank-1-equity"), 80_00),
            ),
        )
    )
    return ledger
