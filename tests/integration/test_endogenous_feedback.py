import json
from itertools import pairwise
from pathlib import Path

from ecodeling.config.schema import (
    ForeignSectorConfig,
    IndexationConfig,
    MicroSimulationConfig,
    ModelConfig,
    RealEconomyConfig,
    ShockConfig,
    ShockKind,
    SimulationConfig,
)
from ecodeling.economy import run_economy_simulation, run_endogenous_indexation_comparison
from ecodeling.identifiers import ScenarioId


def _feedback_config(*, months: int, alpha: float = 1.0) -> ModelConfig:
    return ModelConfig(
        scenario_id=ScenarioId("phase-08-feedback"),
        simulation=SimulationConfig(months=months, seed=808),
        indexation=IndexationConfig(mortgage_alpha=alpha, lag_months=1),
        micro=MicroSimulationConfig(households=40, banks=2, mortgage_term_months=600),
        real_economy=RealEconomyConfig(firms=4, firm_cash_buffer_months=max(36, months + 12)),
        foreign_sector=ForeignSectorConfig(import_share_bps=2_500),
        shock=ShockConfig(kind=ShockKind.FX_DEPRECIATION, month=3, magnitude=0.10),
    )


def test_endogenous_cpi_is_lagged_and_traceable_through_households_and_bank() -> None:
    fixture = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "phase08_feedback_trace.json").read_text()
    )
    config = _feedback_config(months=12)
    baseline = run_economy_simulation(
        config.model_copy(update={"shock": ShockConfig(), "scenario_id": "phase-08-baseline"})
    )
    shocked = run_economy_simulation(config)

    # CPI produced in shock month 3 is first eligible at month 5: one information
    # month plus the configured one-month contractual lag.
    assert [row.indexation_revaluation for row in shocked.aggregate_months[:5]] == [
        row.indexation_revaluation for row in baseline.aggregate_months[:5]
    ]
    impact = shocked.aggregate_months[5]
    baseline_impact = baseline.aggregate_months[5]
    assert impact.indexation_revaluation > baseline_impact.indexation_revaluation
    assert impact.total_mortgage_principal > baseline_impact.total_mortgage_principal
    assert impact.household_consumption < baseline_impact.household_consumption
    assert impact.bank_equity > baseline_impact.bank_equity

    trace = next(event for event in shocked.feedback_events if event.month == impact.month)
    assert trace.source_shock_event_id == shocked.shock_events[0].event_id
    assert trace.cpi_observation_month == shocked.aggregate_months[3].month
    assert trace.cpi_level == shocked.aggregate_months[3].cpi_level
    assert trace.revaluation_ledger_entry_id == impact.revaluation_ledger_entry_id
    assert trace.consumption_expenditure == impact.household_consumption
    assert trace.bank_equity == impact.bank_equity
    assert any(entry.id == trace.revaluation_ledger_entry_id for entry in shocked.ledger.entries)
    assert {
        "impact_month": str(trace.month),
        "source_cpi_month": str(trace.cpi_observation_month),
        "previous_cpi_month": str(trace.previous_cpi_observation_month),
        "source_cpi_level": trace.cpi_level,
        "previous_cpi_level": trace.previous_cpi_level,
        "mortgage_revaluation": trace.mortgage_revaluation,
        "scheduled_debt_service": trace.scheduled_debt_service,
        "actual_debt_service": trace.actual_debt_service,
        "consumption_expenditure": trace.consumption_expenditure,
        "bank_equity": trace.bank_equity,
        "arrears_households": trace.arrears_households,
        "defaults": trace.defaults,
        "revaluation_ledger_entry_id": str(trace.revaluation_ledger_entry_id),
    } == {
        key: value
        for key, value in fixture.items()
        if key
        not in {
            "seed",
            "households",
            "firms",
            "shock_month",
            "shock_magnitude",
            "lag_months",
        }
    }
    shocked.ledger.assert_accounting_invariants()


def test_alpha_is_continuous_without_scenario_specific_branches() -> None:
    alphas = tuple(step / 10 for step in range(11))
    results = [run_economy_simulation(_feedback_config(months=8, alpha=alpha)) for alpha in alphas]
    revaluations = [result.aggregate_months[5].indexation_revaluation for result in results]

    assert revaluations[0] == 0
    assert all(lower < upper for lower, upper in pairwise(revaluations))


def test_paired_600_month_runs_share_initialization_and_exogenous_shocks() -> None:
    pair = run_endogenous_indexation_comparison(_feedback_config(months=600))

    assert pair.nominal.households == pair.indexed.households
    assert pair.nominal.firms == pair.indexed.firms
    assert pair.nominal.shock_events == pair.indexed.shock_events
    assert pair.nominal.aggregate_months[0].indexation_revaluation == 0
    assert all(row.indexation_revaluation == 0 for row in pair.nominal.aggregate_months)
    assert any(row.indexation_revaluation != 0 for row in pair.indexed.aggregate_months)
    pair.nominal.ledger.assert_accounting_invariants()
    pair.indexed.ledger.assert_accounting_invariants()
