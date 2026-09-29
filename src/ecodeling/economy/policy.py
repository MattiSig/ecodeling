"""Exact, lag-safe monetary-policy decisions and rate pass-through."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from ecodeling.config.schema import MonetaryPolicyConfig
from ecodeling.model.clock import YearMonth

_BPS = 10_000


def annual_rate_bps(value: float) -> int:
    """Convert a configured annual decimal rate to exact integer basis points."""
    return int((Decimal(str(value)) * _BPS).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def coefficient_bps(value: float) -> int:
    """Convert a configured unit coefficient to exact integer basis points."""
    return annual_rate_bps(value)


def round_ratio(numerator: int, denominator: int) -> int:
    """Round an integer ratio half away from zero."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return quotient if numerator >= 0 else -quotient


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """One month-end decision based on information available in that month."""

    decision_month: YearMonth
    effective_month: YearMonth
    observed_inflation_bps: int
    prior_policy_rate_bps: int
    unconstrained_rate_bps: int
    policy_rate_bps: int
    lower_bound_bps: int
    upper_bound_bps: int


def decide_policy_rate(
    config: MonetaryPolicyConfig,
    *,
    decision_month: YearMonth,
    observed_inflation_bps: int,
    prior_policy_rate_bps: int,
) -> PolicyDecision:
    """Apply the smoothed Taylor-like rule in consistent annual basis points."""
    target = annual_rate_bps(config.inflation_target_annual)
    neutral = annual_rate_bps(config.neutral_real_rate_annual)
    phi = coefficient_bps(config.phi_pi)
    rho = coefficient_bps(config.smoothing)
    desired = (
        neutral
        + observed_inflation_bps
        + round_ratio(phi * (observed_inflation_bps - target), _BPS)
    )
    unconstrained = round_ratio(rho * prior_policy_rate_bps + (_BPS - rho) * desired, _BPS)
    lower = annual_rate_bps(config.minimum_rate_annual)
    upper = annual_rate_bps(config.maximum_rate_annual)
    decided = min(upper, max(lower, unconstrained))
    return PolicyDecision(
        decision_month=decision_month,
        effective_month=decision_month.add_months(1),
        observed_inflation_bps=observed_inflation_bps,
        prior_policy_rate_bps=prior_policy_rate_bps,
        unconstrained_rate_bps=unconstrained,
        policy_rate_bps=decided,
        lower_bound_bps=lower,
        upper_bound_bps=upper,
    )


def passed_through_rate(
    baseline_rate_bps: int,
    *,
    policy_rate_bps: int,
    reference_policy_rate_bps: int,
    pass_through_bps: int,
) -> int:
    """Apply a policy-rate deviation to one channel without allowing negative rates."""
    change = round_ratio(
        (policy_rate_bps - reference_policy_rate_bps) * pass_through_bps,
        _BPS,
    )
    return max(0, baseline_rate_bps + change)
