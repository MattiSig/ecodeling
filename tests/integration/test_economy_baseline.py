import json
from pathlib import Path

from ecodeling.config.schema import (
    MicroSimulationConfig,
    ModelConfig,
    RealEconomyConfig,
    SimulationConfig,
)
from ecodeling.economy import run_economy_simulation
from ecodeling.identifiers import ScenarioId


def test_seeded_no_shock_baseline_stays_within_calibrated_bounds() -> None:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "phase06_no_shock_baseline.json"
    fixture = json.loads(fixture_path.read_text())
    config = ModelConfig(
        scenario_id=ScenarioId("phase-06-no-shock"),
        simulation=SimulationConfig(months=fixture["months"], seed=fixture["seed"]),
        micro=MicroSimulationConfig(households=fixture["households"], banks=2),
        real_economy=RealEconomyConfig(
            firms=fixture["firms"],
            firm_cash_buffer_months=fixture["firm_cash_buffer_months"],
        ),
    )

    result = run_economy_simulation(config)
    aggregates = result.aggregate_months

    assert min(row.cpi_level for row in aggregates) >= fixture["cpi_min"]
    assert max(row.cpi_level for row in aggregates) <= fixture["cpi_max"]
    assert min(row.employed_households for row in aggregates) >= fixture["employment_min"]
    assert max(row.employed_households for row in aggregates) <= fixture["employment_max"]
    assert (
        max(abs(row.monthly_inflation_bps) for row in aggregates)
        <= fixture["monthly_inflation_abs_max_bps"]
    )
    assert all(row.production_units >= row.sales_units for row in aggregates)
    assert all(row.household_consumption == row.firm_revenue for row in aggregates)
    result.ledger.assert_accounting_invariants()
