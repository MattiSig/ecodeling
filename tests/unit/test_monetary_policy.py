"""Tests for the exact monetary-policy rule and channel pass-through."""

from ecodeling.config.schema import MonetaryPolicyConfig
from ecodeling.economy.policy import decide_policy_rate, passed_through_rate
from ecodeling.model.clock import YearMonth


def test_policy_rule_uses_annual_units_smoothing_and_bounds() -> None:
    config = MonetaryPolicyConfig(maximum_rate_annual=0.05)

    decision = decide_policy_rate(
        config,
        decision_month=YearMonth(2026, 1),
        observed_inflation_bps=500,
        prior_policy_rate_bps=450,
    )

    # Desired rate is 10.75%; smoothing gives 5.75%, then the 5% cap binds.
    assert decision.unconstrained_rate_bps == 575
    assert decision.policy_rate_bps == 500
    assert decision.effective_month == YearMonth(2026, 2)


def test_channel_pass_through_is_distinct_and_non_negative() -> None:
    assert (
        passed_through_rate(
            650,
            policy_rate_bps=550,
            reference_policy_rate_bps=450,
            pass_through_bps=10_000,
        )
        == 750
    )
    assert (
        passed_through_rate(
            350,
            policy_rate_bps=550,
            reference_policy_rate_bps=450,
            pass_through_bps=2_500,
        )
        == 375
    )
    assert (
        passed_through_rate(
            25,
            policy_rate_bps=0,
            reference_policy_rate_bps=450,
            pass_through_bps=10_000,
        )
        == 0
    )
