"""Focused tests for household-bank initialization and monthly mechanisms."""

from dataclasses import replace

from ecodeling.config.schema import MicroSimulationConfig, ModelConfig, SimulationConfig
from ecodeling.identifiers import ScenarioId
from ecodeling.micro import ExternalPaths, constant_external_paths, run_micro_simulation
from ecodeling.micro.entities import MortgageRegime
from ecodeling.micro.simulation import IncomeObservation


def _config(*, households: int = 20, months: int = 6) -> ModelConfig:
    return ModelConfig(
        scenario_id=ScenarioId("micro-test"),
        simulation=SimulationConfig(months=months, seed=77),
        micro=MicroSimulationConfig(households=households, banks=2, mortgage_term_months=24),
    )


def test_initialization_is_heterogeneous_reproducible_and_grouped() -> None:
    config = _config()
    paths = constant_external_paths(config)

    first = run_micro_simulation(config, paths, MortgageRegime.INDEXED)
    second = run_micro_simulation(config, paths, MortgageRegime.INDEXED)

    assert first.households == second.households
    assert first.household_months == second.household_months
    assert first.aggregate_months == second.aggregate_months
    assert len(first.households) == 20
    assert len(first.banks) == 2
    assert {household.income_quintile for household in first.households} == {1, 2, 3, 4, 5}
    assert len({household.gross_monthly_income for household in first.households}) > 1
    assert {row.dimension for row in first.cohort_months} == {
        "homeowner_status",
        "income_quintile",
        "initial_ltv_quintile",
        "liquidity_group",
        "mortgage_regime",
    }


def test_indexation_changes_principal_and_net_worth_without_spending_cash() -> None:
    config = _config(months=2)
    paths = constant_external_paths(config, annual_inflation_bps=12_000)
    result = run_micro_simulation(config, paths, MortgageRegime.INDEXED)

    revalued = [row for row in result.household_months if row.indexation_revaluation > 0]
    assert revalued
    for row in revalued:
        assert row.actual_payment <= row.scheduled_payment
        assert (
            row.net_worth
            == row.deposits
            + next(
                household.house_value
                for household in result.households
                if household.id == row.household_id
            )
            - row.closing_principal
        )
    assert sum(row.indexation_revaluation for row in revalued) == sum(
        output.indexed_revaluation for output in result.aggregate_months
    )
    result.ledger.assert_accounting_invariants()


def test_persistent_income_failure_creates_arrears_then_mirrored_defaults() -> None:
    config = _config(months=12).model_copy(
        update={
            "micro": _config(months=12).micro.model_copy(update={"default_after_arrears_months": 2})
        }
    )
    normal = constant_external_paths(config, annual_inflation_bps=0, annual_income_growth_bps=0)
    zero_income = tuple(replace(item, level=0) for item in normal.income)
    paths = ExternalPaths(normal.cpi, zero_income)

    result = run_micro_simulation(config, paths, MortgageRegime.NOMINAL)

    assert any(row.arrears > 0 for row in result.household_months)
    assert any(row.defaulted for row in result.household_months)
    assert sum(row.credit_losses for row in result.bank_months) > 0
    result.ledger.assert_accounting_invariants()


def test_external_paths_reject_missing_months() -> None:
    config = _config()
    paths = constant_external_paths(config)
    truncated = ExternalPaths(
        paths.cpi, (IncomeObservation(config.simulation.start_month, 10_000),)
    )

    try:
        run_micro_simulation(config, truncated, MortgageRegime.NOMINAL)
    except ValueError as error:
        assert "missing income observation" in str(error)
    else:
        raise AssertionError("a missing external month must fail")
