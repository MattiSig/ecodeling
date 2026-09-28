"""Generated accounting invariant tests."""

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from tests.conftest import build_funded_ledger, build_transfer_ledger

from ecodeling.accounting import AccountingError, Posting, TransactionEntry
from ecodeling.identifiers import AccountId, LedgerEntryId
from ecodeling.model.clock import YearMonth


@given(amounts=st.lists(st.integers(min_value=0, max_value=100_00), min_size=1, max_size=100))
@example(amounts=[1])
def test_arbitrary_valid_transfer_sequence_conserves_deposits(
    amounts: list[int],
) -> None:
    transfer_ledger = build_transfer_ledger()
    expected_first = 100_00
    for index, proposed in enumerate(amounts):
        available = expected_first if index % 2 == 0 else 100_00 - expected_first
        amount = min(proposed, available)
        if amount == 0:
            continue
        direction = -1 if index % 2 == 0 else 1
        transfer_ledger.post(
            TransactionEntry(
                id=LedgerEntryId(f"transfer-{index}"),
                month=YearMonth(2025, 1),
                description="Generated valid transfer",
                postings=(
                    Posting(AccountId("household-1-deposit"), direction * amount),
                    Posting(AccountId("bank-1-household-1-deposit"), direction * amount),
                    Posting(AccountId("household-1-equity"), direction * amount),
                    Posting(AccountId("household-2-deposit"), -direction * amount),
                    Posting(AccountId("bank-1-household-2-deposit"), -direction * amount),
                    Posting(AccountId("household-2-equity"), -direction * amount),
                ),
            )
        )
        expected_first += direction * amount

    report = transfer_ledger.system_balance_sheet()
    assert report.financial_assets == report.financial_liabilities == 100_00
    assert transfer_ledger.balance(AccountId("household-1-deposit")) == expected_first
    transfer_ledger.assert_accounting_invariants()


@given(asset_change=st.integers(min_value=1, max_value=10_000))
def test_arbitrary_invalid_entries_fail_atomically(
    asset_change: int,
) -> None:
    funded_ledger = build_funded_ledger()
    before_entries = funded_ledger.entries
    before_report = funded_ledger.system_balance_sheet()

    with pytest.raises(AccountingError):
        funded_ledger.post(
            TransactionEntry(
                id=LedgerEntryId("generated-invalid"),
                month=YearMonth(2025, 1),
                description="Generated invalid posting",
                postings=(
                    Posting(AccountId("household-1-deposit"), asset_change),
                    Posting(AccountId("household-1-equity"), asset_change),
                ),
            )
        )

    assert funded_ledger.entries == before_entries
    assert funded_ledger.system_balance_sheet() == before_report
