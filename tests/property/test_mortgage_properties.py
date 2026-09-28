"""Generated mortgage continuity, accounting, and payoff invariants."""

from hypothesis import given
from hypothesis import strategies as st
from tests.mortgage_support import build_mortgage_environment, reference_index

from ecodeling.contracts import MortgageStatus
from ecodeling.identifiers import AccountId, ContractId
from ecodeling.model.clock import YearMonth


@given(
    principal=st.integers(min_value=1, max_value=1_000_000),
    annual_rate_bps=st.integers(min_value=0, max_value=5_000),
    alpha_bps=st.integers(min_value=0, max_value=10_000),
    previous_level=st.integers(min_value=5_000, max_value=20_000),
    referenced_level=st.integers(min_value=5_000, max_value=20_000),
    term_months=st.integers(min_value=1, max_value=120),
)
def test_generated_period_preserves_principal_and_payment_identities(
    principal: int,
    annual_rate_bps: int,
    alpha_bps: int,
    previous_level: int,
    referenced_level: int,
    term_months: int,
) -> None:
    index = reference_index(
        YearMonth(2024, 11),
        (previous_level, referenced_level),
    )
    environment = build_mortgage_environment(
        principal=principal,
        annual_rate_bps=annual_rate_bps,
        alpha_bps=alpha_bps,
        lag_months=2,
        term_months=term_months,
        index=index,
        extra_cash=10_000_000,
    )

    period = environment.registry.advance(ContractId("mortgage-1"), YearMonth(2025, 2))

    assert period.opening_principal + period.indexation_revaluation == (period.preflow_principal)
    assert period.preflow_principal - period.principal_payment == period.closing_principal
    assert period.interest + period.principal_payment == period.scheduled_payment
    assert 0 <= period.principal_payment <= period.preflow_principal
    assert environment.ledger.balance(AccountId("household-1-mortgage")) == (
        period.closing_principal
    )
    assert environment.ledger.balance(AccountId("bank-1-mortgage")) == (period.closing_principal)
    environment.ledger.assert_accounting_invariants()


@given(
    principal=st.integers(min_value=1, max_value=100_000),
    annual_rate_bps=st.integers(min_value=0, max_value=3_000),
    alpha_bps=st.integers(min_value=0, max_value=10_000),
    term_months=st.integers(min_value=1, max_value=24),
)
def test_generated_mortgage_pays_off_within_declared_maturity(
    principal: int,
    annual_rate_bps: int,
    alpha_bps: int,
    term_months: int,
) -> None:
    levels = tuple(100_000 + offset * 100 for offset in range(term_months + 2))
    index = reference_index(YearMonth(2024, 12), levels)
    environment = build_mortgage_environment(
        principal=principal,
        annual_rate_bps=annual_rate_bps,
        alpha_bps=alpha_bps,
        lag_months=1,
        term_months=term_months,
        index=index,
        extra_cash=1_000_000,
    )

    periods = []
    for offset in range(1, term_months + 1):
        periods.append(
            environment.registry.advance(
                ContractId("mortgage-1"),
                YearMonth(2025, 1).add_months(offset),
            )
        )
        if periods[-1].status is MortgageStatus.PAID_OFF:
            break

    assert periods[-1].closing_principal == 0
    assert all(period.closing_principal >= 0 for period in periods)
    assert len(periods) <= term_months
    assert environment.ledger.balance(AccountId("household-1-mortgage")) == 0
    assert environment.ledger.balance(AccountId("bank-1-mortgage")) == 0
    environment.ledger.assert_accounting_invariants()
