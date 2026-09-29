from ecodeling.config.schema import (
    ForeignSectorConfig,
    MicroSimulationConfig,
    ModelConfig,
    RealEconomyConfig,
    ShockConfig,
    ShockKind,
    ShockPersistence,
    SimulationConfig,
)
from ecodeling.economy import run_economy_simulation
from ecodeling.identifiers import ScenarioId


def _config(
    *,
    kind: ShockKind = ShockKind.NONE,
    magnitude: float = 0.0,
    persistence: ShockPersistence = ShockPersistence.PERMANENT,
    import_share_bps: int = 2_500,
) -> ModelConfig:
    shock = (
        ShockConfig()
        if kind is ShockKind.NONE
        else ShockConfig(
            kind=kind,
            month=3,
            magnitude=magnitude,
            persistence=persistence,
        )
    )
    return ModelConfig(
        scenario_id=ScenarioId("foreign-sector-test"),
        simulation=SimulationConfig(months=8, seed=8642),
        micro=MicroSimulationConfig(households=40, banks=2),
        real_economy=RealEconomyConfig(firms=4, firm_cash_buffer_months=36),
        foreign_sector=ForeignSectorConfig(import_share_bps=import_share_bps),
        shock=shock,
    )


def test_ten_percent_depreciation_raises_import_price_exactly_ten_percent() -> None:
    result = run_economy_simulation(_config(kind=ShockKind.FX_DEPRECIATION, magnitude=0.10))

    before = result.aggregate_months[2]
    impact = result.aggregate_months[3]
    assert before.exchange_rate_index == 100_000
    assert before.import_price_index == 100_000
    assert impact.exchange_rate_index == 110_000
    assert impact.foreign_price_index == 100_000
    assert impact.import_price_index == 110_000
    assert result.shock_events[0].month == impact.month
    assert result.shock_events[0].import_price_before == 100_000
    assert result.shock_events[0].import_price_after == 110_000


def test_zero_import_share_has_no_direct_cost_or_price_response() -> None:
    baseline = run_economy_simulation(_config(import_share_bps=0))
    shocked = run_economy_simulation(
        _config(
            kind=ShockKind.FX_DEPRECIATION,
            magnitude=0.10,
            import_share_bps=0,
        )
    )

    assert [row.price_isk for row in baseline.firm_months] == [
        row.price_isk for row in shocked.firm_months
    ]
    assert all(row.imported_input_cost_per_unit == 0 for row in shocked.firm_months)
    assert all(row.imported_input_expenditure == 0 for row in shocked.firm_months)
    assert [row.cpi_level for row in baseline.aggregate_months] == [
        row.cpi_level for row in shocked.aggregate_months
    ]


def test_shock_timing_persistence_and_foreign_price_channel() -> None:
    permanent = run_economy_simulation(_config(kind=ShockKind.FX_DEPRECIATION, magnitude=0.10))
    one_off = run_economy_simulation(
        _config(
            kind=ShockKind.FOREIGN_PRICE_INCREASE,
            magnitude=0.10,
            persistence=ShockPersistence.ONE_OFF,
        )
    )

    assert [row.import_price_index for row in permanent.aggregate_months] == [
        100_000,
        100_000,
        100_000,
        110_000,
        110_000,
        110_000,
        110_000,
        110_000,
    ]
    assert [row.import_price_index for row in one_off.aggregate_months] == [
        100_000,
        100_000,
        100_000,
        110_000,
        100_000,
        100_000,
        100_000,
        100_000,
    ]
    assert one_off.aggregate_months[3].foreign_price_index == 110_000
    assert one_off.aggregate_months[4].foreign_price_index == 100_000


def test_import_flows_settle_to_foreign_sector_and_are_reproducible() -> None:
    config = _config(kind=ShockKind.FX_DEPRECIATION, magnitude=0.10)
    first = run_economy_simulation(config)
    second = run_economy_simulation(config)

    assert first.firm_months == second.firm_months
    assert first.aggregate_months == second.aggregate_months
    assert first.shock_events == second.shock_events
    assert first.ledger.entries == second.ledger.entries
    assert all(
        row.imported_input_expenditure
        == sum(
            firm.imported_input_expenditure for firm in first.firm_months if firm.month == row.month
        )
        for row in first.aggregate_months
    )
    import_entries = [
        entry for entry in first.ledger.transactions if str(entry.id).endswith(":imports")
    ]
    assert len(import_entries) == config.simulation.months
    assert [row.import_ledger_entry_id for row in first.aggregate_months] == [
        entry.id for entry in import_entries
    ]
    first.ledger.assert_accounting_invariants()


def test_larger_depreciation_has_larger_cost_and_cpi_response() -> None:
    ten_percent = run_economy_simulation(_config(kind=ShockKind.FX_DEPRECIATION, magnitude=0.10))
    twenty_percent = run_economy_simulation(_config(kind=ShockKind.FX_DEPRECIATION, magnitude=0.20))

    assert (
        twenty_percent.aggregate_months[3].imported_input_expenditure
        > ten_percent.aggregate_months[3].imported_input_expenditure
    )
    assert (
        twenty_percent.aggregate_months[3].cpi_level
        > ten_percent.aggregate_months[3].cpi_level
        > ten_percent.aggregate_months[2].cpi_level
    )


def test_zero_magnitude_shock_is_economically_equivalent_to_no_shock() -> None:
    baseline = run_economy_simulation(_config())
    zero_shock = run_economy_simulation(_config(kind=ShockKind.FX_DEPRECIATION, magnitude=0.0))

    assert baseline.household_months == zero_shock.household_months
    assert baseline.firm_months == zero_shock.firm_months
    assert baseline.aggregate_months == zero_shock.aggregate_months
    assert baseline.ledger.entries == zero_shock.ledger.entries
