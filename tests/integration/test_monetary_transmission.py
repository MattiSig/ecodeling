"""Policy timing, deterministic transmission, and mechanism-separation tests."""

import json
from pathlib import Path

from ecodeling.config.schema import (
    ForeignSectorConfig,
    IndexationConfig,
    MicroSimulationConfig,
    ModelConfig,
    MonetaryPolicyConfig,
    RealEconomyConfig,
    ShockConfig,
    ShockKind,
    SimulationConfig,
)
from ecodeling.economy import run_economy_simulation, run_endogenous_indexation_comparison
from ecodeling.identifiers import ScenarioId


def _policy_config(*, months: int = 30, alpha: float = 0.0) -> ModelConfig:
    return ModelConfig(
        scenario_id=ScenarioId("phase-09-policy"),
        simulation=SimulationConfig(months=months, seed=909),
        indexation=IndexationConfig(mortgage_alpha=alpha, lag_months=1),
        micro=MicroSimulationConfig(households=40, banks=2, mortgage_term_months=600),
        real_economy=RealEconomyConfig(firms=4, firm_cash_buffer_months=72),
        foreign_sector=ForeignSectorConfig(import_share_bps=2_500),
        monetary_policy=MonetaryPolicyConfig(
            inflation_target_annual=0.0,
            initial_policy_rate_annual=0.02,
            smoothing=0.0,
            nominal_mortgage_reset_months=1,
            indexed_mortgage_reset_months=1,
        ),
        shock=ShockConfig(kind=ShockKind.FX_DEPRECIATION, month=3, magnitude=0.10),
    )


def test_policy_observes_completed_cpi_and_transmits_only_next_month() -> None:
    result = run_economy_simulation(_policy_config())

    first = result.policy_events[0]
    assert first.month == result.aggregate_months[12].month
    assert first.observed_annual_inflation_bps == result.aggregate_months[12].annual_inflation_bps
    assert first.effective_month == result.aggregate_months[13].month
    assert result.aggregate_months[12].nominal_mortgage_rate_bps == 650

    nominal_reset = next(
        event
        for event in result.rate_reset_events
        if event.month == first.effective_month and event.channel == "nominal_mortgage"
    )
    assert nominal_reset.source_policy_event_id == first.event_id
    assert result.aggregate_months[13].nominal_mortgage_rate_bps == nominal_reset.new_rate_bps
    assert (
        result.aggregate_months[13].mortgage_interest
        != result.aggregate_months[12].mortgage_interest
    )


def test_policy_bounds_and_transmission_are_deterministic() -> None:
    config = _policy_config().model_copy(
        update={
            "monetary_policy": _policy_config().monetary_policy.model_copy(
                update={"maximum_rate_annual": 0.05}
            )
        }
    )
    first = run_economy_simulation(config)
    second = run_economy_simulation(config)

    assert first.policy_events == second.policy_events
    assert first.rate_reset_events == second.rate_reset_events
    assert all(event.policy_rate_bps <= 500 for event in first.policy_events)


def test_tightening_and_cpi_principal_revaluation_remain_distinct() -> None:
    pair = run_endogenous_indexation_comparison(_policy_config(months=18))
    fixture = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "phase09_policy_impulse.json").read_text()
    )

    assert all(row.indexation_revaluation == 0 for row in pair.nominal.aggregate_months)
    assert any(row.indexation_revaluation > 0 for row in pair.indexed.aggregate_months)
    assert pair.nominal.aggregate_months[13].nominal_mortgage_rate_bps > 650
    assert pair.indexed.aggregate_months[13].indexed_mortgage_rate_bps > 350
    assert (
        pair.nominal.aggregate_months[13].nominal_mortgage_rate_bps - 650
        > pair.indexed.aggregate_months[13].indexed_mortgage_rate_bps - 350
    )
    assert pair.nominal.aggregate_months[13].mortgage_interest > 0
    assert pair.indexed.aggregate_months[5].indexation_revaluation > 0
    first = pair.nominal.policy_events[0]
    nominal = pair.nominal.aggregate_months[13]
    indexed = pair.indexed.aggregate_months[13]
    indexed_impact = pair.indexed.aggregate_months[5]
    assert {
        "seed": pair.nominal.seed,
        "shock_month": 3,
        "shock_magnitude": 0.1,
        "first_policy_decision_month": str(first.month),
        "first_policy_effective_month": str(first.effective_month),
        "nominal": {
            "policy_rate_bps": nominal.policy_rate_bps,
            "mortgage_rate_bps": nominal.nominal_mortgage_rate_bps,
            "mortgage_interest": nominal.mortgage_interest,
            "principal_revaluation": nominal.indexation_revaluation,
        },
        "indexed": {
            "policy_rate_bps": indexed.policy_rate_bps,
            "mortgage_rate_bps": indexed.indexed_mortgage_rate_bps,
            "mortgage_interest": indexed.mortgage_interest,
            "impact_month": str(indexed_impact.month),
            "impact_principal_revaluation": indexed_impact.indexation_revaluation,
        },
    } == fixture
