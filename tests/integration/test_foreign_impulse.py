import json
from pathlib import Path

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


def test_fx_depreciation_impulse_has_traceable_import_cost_and_cpi_response() -> None:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "phase07_fx_impulse.json"
    fixture = json.loads(fixture_path.read_text())
    baseline_config = ModelConfig(
        scenario_id=ScenarioId("phase-07-fx-impulse"),
        simulation=SimulationConfig(months=fixture["months"], seed=fixture["seed"]),
        micro=MicroSimulationConfig(households=fixture["households"], banks=2),
        real_economy=RealEconomyConfig(
            firms=fixture["firms"],
            firm_cash_buffer_months=fixture["firm_cash_buffer_months"],
        ),
        foreign_sector=ForeignSectorConfig(import_share_bps=fixture["import_share_bps"]),
    )
    baseline = run_economy_simulation(baseline_config)
    shocked = run_economy_simulation(
        baseline_config.model_copy(
            update={
                "shock": ShockConfig(
                    kind=ShockKind.FX_DEPRECIATION,
                    month=fixture["shock_month"],
                    magnitude=fixture["shock_magnitude"],
                )
            }
        )
    )

    assert [row.import_price_index for row in shocked.aggregate_months] == fixture[
        "expected_import_price_path"
    ]
    assert [
        round((shock.cpi_level - base.cpi_level) * 10_000 / base.cpi_level)
        for base, shock in zip(baseline.aggregate_months, shocked.aggregate_months, strict=True)
    ] == fixture["expected_cpi_response_bps"]
    shock_month = fixture["shock_month"]
    assert shocked.aggregate_months[:shock_month] == baseline.aggregate_months[:shock_month]
    assert (
        shocked.aggregate_months[shock_month].imported_input_expenditure
        > baseline.aggregate_months[shock_month].imported_input_expenditure
    )
    assert shocked.shock_events[0].event_id == "foreign-shock:2025-07"
    impact = shocked.aggregate_months[shock_month]
    assert str(impact.import_ledger_entry_id) == "economy:2025-07:imports"
    assert any(entry.id == impact.import_ledger_entry_id for entry in shocked.ledger.transactions)
    shocked.ledger.assert_accounting_invariants()
