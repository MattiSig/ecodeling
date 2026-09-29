from ecodeling.config.schema import (
    ForeignSectorConfig,
    MicroSimulationConfig,
    ModelConfig,
    RealEconomyConfig,
    ShockConfig,
    ShockKind,
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
        assert aggregate.household_consumption + aggregate.export_revenue == aggregate.firm_revenue
        assert aggregate.firm_revenue == sum(row.revenue for row in firms)
        assert all(row.consumption_expenditure <= row.consumption_budget for row in households)
        assert aggregate.sales_units == (
            sum(row.consumption_units for row in households) + aggregate.export_units
        )
    result.ledger.assert_accounting_invariants()


def test_export_goods_cash_and_bank_dividends_reconcile_to_the_journal() -> None:
    config = _config(months=18).model_copy(
        update={
            "foreign_sector": ForeignSectorConfig(import_share_bps=2_500),
        }
    )
    result = run_economy_simulation(config)
    entries = {str(entry.id): entry for entry in result.ledger.entries}
    for aggregate in result.aggregate_months:
        households = [row for row in result.household_months if row.month == aggregate.month]
        assert aggregate.household_consumption + aggregate.export_revenue == aggregate.firm_revenue
        assert aggregate.sales_units == (
            sum(row.consumption_units for row in households) + aggregate.export_units
        )
        assert aggregate.bank_dividends == sum(row.bank_dividend for row in households)
        assert aggregate.bank_dividends == sum(
            min(row.actual_mortgage_payment, row.mortgage_interest) for row in households
        )
        assert 0 < aggregate.export_revenue <= 6_000_000
        entry = entries[f"economy:{aggregate.month}:exports"]
        assert (
            sum(
                p.amount
                for p in entry.postings
                if str(p.account_id).startswith("firm-") and str(p.account_id).endswith(":deposit")
            )
            == aggregate.export_revenue
        )
        assert (
            sum(
                p.amount
                for p in entry.postings
                if str(p.account_id) == "economy-external-sector:deposit"
            )
            == -aggregate.export_revenue
        )
    result.ledger.assert_accounting_invariants()


def test_export_budget_does_not_automatically_offset_an_import_price_shock() -> None:
    base = _config(months=8).model_copy(
        update={
            "foreign_sector": ForeignSectorConfig(import_share_bps=2_500),
        }
    )
    shocked = run_economy_simulation(
        base.model_copy(
            update={
                "shock": ShockConfig(kind=ShockKind.FX_DEPRECIATION, month=2, magnitude=0.5),
            }
        )
    )
    baseline = run_economy_simulation(base)
    assert {
        row.export_demand for row in (*baseline.aggregate_months, *shocked.aggregate_months)
    } == {6_000_000}
    assert shocked.aggregate_months[-1].cpi_level > baseline.aggregate_months[-1].cpi_level
    assert sum(row.consumption_units for row in shocked.household_months) < sum(
        row.consumption_units for row in baseline.household_months
    )


def test_export_settlement_financing_has_exact_mirrored_claims() -> None:
    base = _config(months=2)
    result = run_economy_simulation(
        base.model_copy(
            update={
                "real_economy": base.real_economy.model_copy(
                    update={"consumption_propensity_bps": 0}
                ),
                "foreign_sector": ForeignSectorConfig(
                    import_share_bps=2_500, monthly_export_demand_isk=12_000_000
                ),
            }
        )
    )
    assert sum(row.external_financing for row in result.aggregate_months) > 0
    entries = {str(entry.id): entry for entry in result.ledger.entries}
    for row in result.aggregate_months:
        if row.external_financing:
            funding = entries[f"economy:{row.month}:export-funding"]
            assert {str(p.account_id): p.amount for p in funding.postings} == {
                "economy-clearing-bank:external-settlement": row.external_financing,
                "economy-external-sector:settlement-liability": row.external_financing,
                "economy-external-sector:deposit": row.external_financing,
                "economy-clearing-bank:economy-external-sector:deposit": row.external_financing,
            }
    result.ledger.assert_accounting_invariants()


def test_uncollected_interest_is_not_paid_out_as_dividends() -> None:
    base = _config(months=24)
    result = run_economy_simulation(
        base.model_copy(
            update={
                "micro": base.micro.model_copy(update={"mortgage_term_months": 12}),
                "foreign_sector": ForeignSectorConfig(
                    import_share_bps=2_500, monthly_export_demand_isk=0
                ),
            }
        )
    )
    assert any(row.bank_dividends < row.mortgage_interest for row in result.aggregate_months)
    for aggregate in result.aggregate_months:
        assert aggregate.bank_dividends == sum(
            min(row.actual_mortgage_payment, row.mortgage_interest)
            for row in result.household_months
            if row.month == aggregate.month
        )


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
