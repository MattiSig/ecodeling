from ecodeling.config.schema import (
    MicroSimulationConfig,
    ModelConfig,
    RealEconomyConfig,
    SimulationConfig,
)
from ecodeling.economy import run_economy_simulation
from ecodeling.identifiers import ScenarioId


def _config(*, months: int = 18) -> ModelConfig:
    return ModelConfig(
        scenario_id=ScenarioId("endogenous-economy-test"),
        simulation=SimulationConfig(months=months, seed=2468),
        micro=MicroSimulationConfig(households=40, banks=2),
        real_economy=RealEconomyConfig(firms=4, firm_cash_buffer_months=36),
    )


def test_staged_markets_conserve_goods_and_money() -> None:
    result = run_economy_simulation(_config())

    for aggregate in result.aggregate_months:
        firms = [row for row in result.firm_months if row.month == aggregate.month]
        households = [row for row in result.household_months if row.month == aggregate.month]
        assert all(
            row.opening_inventory + row.production == row.sales + row.closing_inventory
            for row in firms
        )
        assert all(row.production <= row.capacity for row in firms)
        assert aggregate.production_units == sum(row.production for row in firms)
        assert aggregate.sales_units == sum(row.sales for row in firms)
        assert aggregate.closing_inventory_units == sum(row.closing_inventory for row in firms)
        assert aggregate.wage_income == sum(row.wage_bill for row in firms)
        assert aggregate.wage_income == sum(row.wage_income for row in households)
        assert aggregate.household_consumption == sum(
            row.consumption_expenditure for row in households
        )
        assert aggregate.household_consumption == aggregate.firm_revenue
        assert aggregate.firm_revenue == sum(row.revenue for row in firms)
        assert all(row.consumption_expenditure <= row.consumption_budget for row in households)
    result.ledger.assert_accounting_invariants()


def test_named_matching_streams_make_complete_run_reproducible() -> None:
    config = _config()

    first = run_economy_simulation(config)
    second = run_economy_simulation(config)

    assert first.households == second.households
    assert first.firms == second.firms
    assert first.household_months == second.household_months
    assert first.firm_months == second.firm_months
    assert first.aggregate_months == second.aggregate_months
    assert first.ledger.entries == second.ledger.entries
    assert first.run_id == second.run_id


def test_cpi_and_inflation_are_derived_from_transacted_firm_prices() -> None:
    result = run_economy_simulation(_config(months=18))

    for offset, aggregate in enumerate(result.aggregate_months):
        firms = [row for row in result.firm_months if row.month == aggregate.month]
        transacted = sum(row.price_isk * row.sales for row in firms)
        total_sales = sum(row.sales for row in firms)
        assert total_sales > 0
        base_price_sum = sum(firm.opening_price for firm in result.firms)
        expected_cpi = round(transacted * len(firms) * 100_000 / (total_sales * base_price_sum))
        assert aggregate.cpi_level == expected_cpi
        if offset >= 12:
            annual_base = result.aggregate_months[offset - 12].cpi_level
            expected_annual = round((aggregate.cpi_level - annual_base) * 10_000 / annual_base)
            assert aggregate.annual_inflation_bps == expected_annual
        else:
            assert aggregate.annual_inflation_bps is None


def test_price_target_uses_cost_markup_and_partial_adjustment() -> None:
    config = _config(months=1).model_copy(
        update={
            "real_economy": RealEconomyConfig(
                firms=4,
                monthly_wage_isk=400_000,
                productivity_units_per_worker=400,
                opening_price_isk=1_000,
                markup_bps=2_000,
                price_adjustment_bps=2_500,
                firm_cash_buffer_months=36,
            )
        }
    )

    result = run_economy_simulation(config)

    # Unit cost is 1,000 and the 20% markup target is 1,200; one 25% step reaches 1,050.
    assert {firm.opening_price for firm in result.firms} == {1_000}
    assert {row.price_isk for row in result.firm_months} == {1_050}
    assert result.aggregate_months[0].cpi_level == 105_000
    assert result.aggregate_months[0].monthly_inflation_bps == 500
