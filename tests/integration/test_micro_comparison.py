"""Integration tests for common-path nominal/indexed experiments."""

from dataclasses import replace

from ecodeling.config.schema import MicroSimulationConfig, ModelConfig, SimulationConfig
from ecodeling.identifiers import ScenarioId
from ecodeling.micro import (
    constant_external_paths,
    run_micro_simulation,
    run_nominal_indexed_comparison,
)
from ecodeling.micro.entities import MortgageRegime


def test_paired_regimes_share_initialization_and_diverge_as_documented() -> None:
    config = ModelConfig(
        scenario_id=ScenarioId("paired"),
        simulation=SimulationConfig(months=36, seed=1234),
        micro=MicroSimulationConfig(households=50, banks=2, mortgage_term_months=120),
    )
    paths = constant_external_paths(config, annual_inflation_bps=600)

    pair = run_nominal_indexed_comparison(config, paths)

    nominal_opening = tuple(
        replace(item, mortgage_regime=MortgageRegime.NONE) for item in pair.nominal.households
    )
    indexed_opening = tuple(
        replace(item, mortgage_regime=MortgageRegime.NONE) for item in pair.indexed.households
    )
    assert nominal_opening == indexed_opening
    assert tuple(row.cpi_level for row in pair.nominal.aggregate_months) == tuple(
        row.cpi_level for row in pair.indexed.aggregate_months
    )
    assert pair.nominal.aggregate_months[-1].total_mortgage_principal != (
        pair.indexed.aggregate_months[-1].total_mortgage_principal
    )
    assert pair.indexed.aggregate_months[-1].indexed_revaluation > 0
    assert pair.nominal.aggregate_months[-1].indexed_revaluation == 0
    pair.nominal.ledger.assert_accounting_invariants()
    pair.indexed.ledger.assert_accounting_invariants()


def test_seeded_600_month_population_run_preserves_accounting() -> None:
    config = ModelConfig(scenario_id=ScenarioId("phase-04-acceptance"))
    paths = constant_external_paths(config)

    result = run_micro_simulation(config, paths, MortgageRegime.INDEXED)

    assert len(result.households) == 1_000
    assert len(result.banks) == 2
    assert len(result.aggregate_months) == 600
    assert len(result.household_months) == 600_000
    assert all(row.total_mortgage_principal >= 0 for row in result.aggregate_months)
    result.ledger.assert_accounting_invariants()
