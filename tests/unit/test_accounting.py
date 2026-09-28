"""Unit tests for the stock-flow accounting kernel."""

import pytest

from ecodeling.accounting import (
    Account,
    AccountingError,
    AccountKind,
    Ledger,
    Posting,
    RevaluationEntry,
    Sector,
    TransactionEntry,
)
from ecodeling.identifiers import AccountId, AgentId, ContractId, LedgerEntryId
from ecodeling.model.clock import YearMonth


def test_opening_positions_produce_balanced_agent_and_system_reports(
    funded_ledger: Ledger,
) -> None:
    household = funded_ledger.balance_sheet(AgentId("household-1"))
    bank = funded_ledger.balance_sheet(AgentId("bank-1"))
    system = funded_ledger.system_balance_sheet()

    assert household.assets == 1
    assert household.liabilities == 0
    assert household.equity == 1
    assert household.accounting_gap == 0
    assert bank.assets == 1
    assert bank.liabilities == 1
    assert bank.equity == 0
    assert bank.accounting_gap == 0
    assert system.financial_assets == system.financial_liabilities == 1
    assert system.financial_claim_gap == 0
    assert system.accounting_gap == 0
    assert all(sector.balance_sheet.accounting_gap == 0 for sector in system.sectors)


def test_transfer_changes_both_deposit_sides_and_preserves_totals(
    transfer_ledger: Ledger,
) -> None:
    before = transfer_ledger.system_balance_sheet()
    transfer_ledger.post(
        TransactionEntry(
            id=LedgerEntryId("transfer-1"),
            month=YearMonth(2025, 1),
            description="Household transfer",
            postings=(
                Posting(AccountId("household-1-deposit"), -25_00),
                Posting(AccountId("bank-1-household-1-deposit"), -25_00),
                Posting(AccountId("household-1-equity"), -25_00),
                Posting(AccountId("household-2-deposit"), 25_00),
                Posting(AccountId("bank-1-household-2-deposit"), 25_00),
                Posting(AccountId("household-2-equity"), 25_00),
            ),
        )
    )

    assert transfer_ledger.balance(AccountId("household-1-deposit")) == 75_00
    assert transfer_ledger.balance(AccountId("household-2-deposit")) == 25_00
    after = transfer_ledger.system_balance_sheet()
    assert after.financial_assets == before.financial_assets
    assert after.financial_liabilities == before.financial_liabilities
    assert after.assets == before.assets
    assert after.equity == before.equity
    transfer_ledger.assert_accounting_invariants()


def test_mortgage_revaluation_is_mirrored_and_changes_explicit_equity(
    mortgage_ledger: Ledger,
) -> None:
    mortgage_ledger.post(
        RevaluationEntry(
            id=LedgerEntryId("mortgage-indexation-1"),
            month=YearMonth(2025, 2),
            description="One ISK CPI revaluation",
            postings=(
                Posting(AccountId("household-1-mortgage"), 1),
                Posting(AccountId("household-1-equity"), -1),
                Posting(AccountId("bank-1-mortgage"), 1),
                Posting(AccountId("bank-1-equity"), 1),
            ),
        )
    )

    assert mortgage_ledger.balance(AccountId("household-1-mortgage")) == 80_01
    assert mortgage_ledger.balance(AccountId("bank-1-mortgage")) == 80_01
    assert mortgage_ledger.balance_sheet(AgentId("household-1")).net_worth == 19_99
    assert mortgage_ledger.balance_sheet(AgentId("bank-1")).net_worth == 80_01
    assert len(mortgage_ledger.revaluations) == 1
    mortgage_ledger.assert_accounting_invariants()


def test_unbalanced_entry_fails_without_mutating_the_journal(funded_ledger: Ledger) -> None:
    entries_before = funded_ledger.entries
    balances_before = funded_ledger.system_balance_sheet()

    with pytest.raises(AccountingError, match="agent accounting effects do not balance"):
        funded_ledger.post(
            TransactionEntry(
                id=LedgerEntryId("invalid-one-sided"),
                month=YearMonth(2025, 1),
                description="Invalid one-sided asset creation",
                postings=(
                    Posting(AccountId("household-1-deposit"), 1_00),
                    Posting(AccountId("household-1-equity"), 50),
                    Posting(AccountId("bank-1-household-1-deposit"), 1_00),
                    Posting(AccountId("bank-1-operating-asset"), 1_00),
                ),
            )
        )

    assert funded_ledger.entries == entries_before
    assert funded_ledger.system_balance_sheet() == balances_before


def test_claim_mismatch_fails_atomically(funded_ledger: Ledger) -> None:
    entries_before = funded_ledger.entries

    with pytest.raises(AccountingError, match="mirrored claim effects do not match"):
        funded_ledger.post(
            TransactionEntry(
                id=LedgerEntryId("invalid-claim"),
                month=YearMonth(2025, 1),
                description="Mismatched deposit claim",
                postings=(
                    Posting(AccountId("household-1-deposit"), 1_00),
                    Posting(AccountId("household-1-equity"), 1_00),
                    Posting(AccountId("bank-1-household-1-deposit"), 99),
                    Posting(AccountId("bank-1-operating-asset"), 99),
                ),
            )
        )

    assert funded_ledger.entries == entries_before


def test_duplicate_entry_identifier_fails_atomically(funded_ledger: Ledger) -> None:
    opening = funded_ledger.entries[0]
    with pytest.raises(AccountingError, match="entry ID already exists"):
        funded_ledger.post(opening)
    assert funded_ledger.entries == (opening,)


def test_entry_batch_fails_atomically_when_later_entry_is_invalid(
    funded_ledger: Ledger,
) -> None:
    before = funded_ledger.entries
    valid = TransactionEntry(
        LedgerEntryId("valid-first"),
        YearMonth(2025, 1),
        "Balanced first batch entry",
        (
            Posting(AccountId("household-1-deposit"), 1),
            Posting(AccountId("household-1-equity"), 1),
            Posting(AccountId("bank-1-household-1-deposit"), 1),
            Posting(AccountId("bank-1-operating-asset"), 1),
        ),
    )
    invalid = TransactionEntry(
        LedgerEntryId("invalid-second"),
        YearMonth(2025, 1),
        "Unbalanced second batch entry",
        (
            Posting(AccountId("household-1-deposit"), 1),
            Posting(AccountId("household-1-equity"), 2),
        ),
    )

    with pytest.raises(AccountingError):
        funded_ledger.post_all((valid, invalid))

    assert funded_ledger.entries == before


def test_accounts_require_claim_ids_only_for_financial_claims() -> None:
    with pytest.raises(ValueError, match="claim ID"):
        Account(
            id=AccountId("orphan"),
            owner_id=AgentId("household-1"),
            sector=Sector.HOUSEHOLDS,
            name="Orphan deposit",
            kind=AccountKind.FINANCIAL_ASSET,
        )

    with pytest.raises(ValueError, match="must not have"):
        Account(
            id=AccountId("misclassified"),
            owner_id=AgentId("household-1"),
            sector=Sector.HOUSEHOLDS,
            name="House",
            kind=AccountKind.REAL_ASSET,
            claim_id=ContractId("not-a-financial-claim"),
        )


@pytest.mark.parametrize("invalid_amount", [1.5, True])
def test_postings_reject_inexact_money(invalid_amount: object) -> None:
    with pytest.raises(TypeError, match="integer number of ISK"):
        Posting(AccountId("deposit"), invalid_amount)  # type: ignore[arg-type]
