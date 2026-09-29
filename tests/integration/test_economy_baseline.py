import json
from pathlib import Path

from ecodeling.config.schema import (
    MicroSimulationConfig,
    ModelConfig,
    MonetaryPolicyConfig,
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
        # Preserve the Phase 06 calibration boundary while later policy
        # mechanics are tested in their own impulse fixture.
        monetary_policy=MonetaryPolicyConfig(
            initial_policy_rate_annual=0.045,
            minimum_rate_annual=0.045,
            maximum_rate_annual=0.045,
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
    opening_inventory = 0
    for row in aggregates:
        assert (
            opening_inventory + row.production_units
            == row.sales_units + row.closing_inventory_units
        )
        opening_inventory = row.closing_inventory_units
    assert all(row.household_consumption == row.firm_revenue for row in aggregates)
    result.ledger.assert_accounting_invariants()
