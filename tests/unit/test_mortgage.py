"""Unit tests for mortgage contract calculations and lifecycle rules."""

import pytest
from tests.mortgage_support import build_mortgage_environment, reference_index

from ecodeling.accounting import AccountingError, Posting, TransactionEntry
from ecodeling.contracts import (
    ContractError,
    MortgagePricing,
    MortgageStatus,
    calculate_indexation,
)
from ecodeling.identifiers import AccountId, ContractId, LedgerEntryId
from ecodeling.model.clock import YearMonth


def test_indexation_acceptance_examples() -> None:
    assert calculate_indexation(10_000_000, 0, 10_100, 10_000) == 0
    assert calculate_indexation(10_000_000, 10_000, 10_100, 10_000) == 100_000
    assert calculate_indexation(10_000_000, 5_000, 10_100, 10_000) == 50_000


def test_indexation_rounds_half_isk_away_from_zero() -> None:
    assert calculate_indexation(1, 5_000, 20_000, 10_000) == 1
    assert calculate_indexation(1, 10_000, 5_000, 10_000) == -1


def test_nominal_pricing_includes_expected_inflation_and_risk_premium() -> None:
    pricing = MortgagePricing(
        real_rate_bps=300,
        expected_inflation_bps=250,
        inflation_risk_premium_bps=50,
        credit_spread_bps=100,
        term_spread_bps=25,
        bank_margin_bps=75,
    )

    assert pricing.indexed_coupon_bps == 500
    assert pricing.nominal_coupon_bps == 800


def test_lagged_revaluation_and_settlement_are_mirrored_ledger_events() -> None:
    index = reference_index(
        YearMonth(2024, 11),
        (10_000, 10_100, 50_000),
    )
    environment = build_mortgage_environment(
        principal=1_200,
        annual_rate_bps=1_200,
        alpha_bps=10_000,
        lag_months=2,
        term_months=2,
        index=index,
    )

    period = environment.registry.advance(ContractId("mortgage-1"), YearMonth(2025, 2))

    assert environment.ledger.transactions[1].id == LedgerEntryId("mortgage:mortgage-1:opening")
    assert period.opening_principal == 1_200
    assert period.indexation_revaluation == 12
    assert period.preflow_principal == 1_212
    assert period.scheduled_payment == period.interest + period.principal_payment
    assert period.closing_principal == 1_212 - period.principal_payment
    assert period.revaluation_entry_id is not None
    assert period.settlement_entry_id is not None
    assert environment.ledger.balance(AccountId("household-1-mortgage")) == (
        period.closing_principal
    )
    assert environment.ledger.balance(AccountId("bank-1-mortgage")) == (period.closing_principal)
    environment.ledger.assert_accounting_invariants()


def test_nominal_mortgage_needs_no_index_observations_and_pays_off_exactly() -> None:
    environment = build_mortgage_environment(
        principal=1_200,
        annual_rate_bps=0,
        alpha_bps=0,
        term_months=3,
    )

    periods = tuple(
        environment.registry.advance(
            ContractId("mortgage-1"), YearMonth(2025, 1).add_months(offset)
        )
        for offset in range(1, 4)
    )

    assert [period.scheduled_payment for period in periods] == [400, 400, 400]
    assert all(period.indexation_revaluation == 0 for period in periods)
    assert all(period.revaluation_entry_id is None for period in periods)
    assert periods[-1].closing_principal == 0
    assert periods[-1].status is MortgageStatus.PAID_OFF
    assert environment.registry.state(ContractId("mortgage-1")).remaining_payments == 0
    environment.ledger.assert_accounting_invariants()


def test_negative_inflation_reduces_principal_without_an_implicit_floor() -> None:
    index = reference_index(YearMonth(2024, 11), (10_000, 9_900))
    environment = build_mortgage_environment(
        principal=1_200,
        annual_rate_bps=0,
        alpha_bps=10_000,
        lag_months=2,
        term_months=2,
        index=index,
    )

    period = environment.registry.advance(ContractId("mortgage-1"), YearMonth(2025, 2))

    assert period.indexation_revaluation == -12
    assert period.preflow_principal == 1_188
    assert environment.ledger.revaluations[-1].postings[0].amount == -12
    environment.ledger.assert_accounting_invariants()


def test_mortgage_months_must_advance_sequentially() -> None:
    environment = build_mortgage_environment(alpha_bps=0)

    with pytest.raises(ContractError, match="expected mortgage month"):
        environment.registry.advance(ContractId("mortgage-1"), YearMonth(2025, 3))


def test_failed_settlement_leaves_period_state_and_all_events_unchanged() -> None:
    index = reference_index(YearMonth(2024, 11), (10_000, 10_100))
    environment = build_mortgage_environment(
        principal=1_200,
        annual_rate_bps=1_200,
        alpha_bps=10_000,
        lag_months=2,
        term_months=2,
        index=index,
        extra_cash=0,
    )
    environment.ledger.post(
        TransactionEntry(
            LedgerEntryId("withdraw-origination-proceeds"),
            YearMonth(2025, 1),
            "Withdraw all mortgage proceeds before payment",
            (
                Posting(AccountId("household-1-deposit"), -1_200),
                Posting(AccountId("household-1-equity"), -1_200),
                Posting(AccountId("bank-1-household-1-deposit"), -1_200),
                Posting(AccountId("bank-1-operating-asset"), -1_200),
            ),
        )
    )
    state_before = environment.registry.state(ContractId("mortgage-1"))
    entries_before = environment.ledger.entries

    with pytest.raises(AccountingError, match="would make account negative"):
        environment.registry.advance(ContractId("mortgage-1"), YearMonth(2025, 2))

    assert environment.registry.state(ContractId("mortgage-1")) == state_before
    assert environment.ledger.entries == entries_before


def test_contract_registry_rejects_duplicate_contract_ids() -> None:
    environment = build_mortgage_environment(alpha_bps=0)

    with pytest.raises(ContractError, match="contract ID already exists"):
        environment.registry.register_mortgage(environment.contract)
