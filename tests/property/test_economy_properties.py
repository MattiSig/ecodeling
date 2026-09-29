from hypothesis import given, settings
from hypothesis import strategies as st

from ecodeling.config.schema import (
    ForeignSectorConfig,
    MicroSimulationConfig,
    ModelConfig,
    RealEconomyConfig,
    SimulationConfig,
)
from ecodeling.economy import run_economy_simulation
from ecodeling.identifiers import ScenarioId


@settings(max_examples=8, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=2**32),
    households=st.integers(10, 30),
    import_share=st.integers(0, 5_000),
)
def test_generated_market_paths_conserve_stocks_and_flows(
    seed: int, households: int, import_share: int
) -> None:
    config = ModelConfig(
        scenario_id=ScenarioId("generated-market-conservation"),
        simulation=SimulationConfig(months=4, seed=seed),
        micro=MicroSimulationConfig(households=households, banks=1),
        real_economy=RealEconomyConfig(firms=3, firm_cash_buffer_months=12),
        foreign_sector=ForeignSectorConfig(import_share_bps=import_share),
    )

    result = run_economy_simulation(config)

    for aggregate in result.aggregate_months:
        firms = [row for row in result.firm_months if row.month == aggregate.month]
        assert sum(row.opening_inventory + row.production for row in firms) == sum(
            row.sales + row.closing_inventory for row in firms
        )
        assert aggregate.household_consumption + aggregate.export_revenue == aggregate.firm_revenue
        assert aggregate.wage_income == sum(row.wage_bill for row in firms)
    result.ledger.assert_accounting_invariants()
