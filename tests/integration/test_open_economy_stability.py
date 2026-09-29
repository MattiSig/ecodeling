"""Stability gates for the actual published open-economy calibration."""

from pathlib import Path

import pytest

from ecodeling.config.schema import ShockConfig
from ecodeling.economy import run_endogenous_indexation_comparison
from ecodeling.reporting import load_config


@pytest.mark.parametrize(
    "seed, households, firms", [(1010, 20, 4), (42, 20, 4), (808, 20, 4), (1010, 200, 10)]
)
def test_published_no_shock_pair_does_not_collapse(seed: int, households: int, firms: int) -> None:
    source = load_config(Path("tests/fixtures/phase10_report_config.json"))
    config = source.model_copy(
        update={
            "simulation": source.simulation.model_copy(update={"months": 120, "seed": seed}),
            "micro": source.micro.model_copy(update={"households": households}),
            "real_economy": source.real_economy.model_copy(update={"firms": firms}),
            "shock": ShockConfig(),
        }
    )
    pair = run_endogenous_indexation_comparison(config)
    for result in (pair.nominal, pair.indexed):
        rows = result.aggregate_months
        assert all(row.employed_households == config.micro.households for row in rows)
        assert sum(row.defaults for row in rows) == 0
        assert all(row.cpi_level == 100_000 for row in rows)
        # Activity must survive beyond the short publication window, not merely
        # postpone the collapse with an opening cash injection.
        assert sum(row.production_units for row in rows[-12:]) >= (
            0.9 * sum(row.production_units for row in rows[:12])
        )
        result.ledger.assert_accounting_invariants()


def test_exports_are_explicit_and_can_be_disabled() -> None:
    source = load_config(Path("tests/fixtures/phase10_report_config.json"))
    config = source.model_copy(
        update={
            "shock": ShockConfig(),
            "foreign_sector": source.foreign_sector.model_copy(
                update={"monthly_export_demand_isk": 0}
            ),
        }
    )
    pair = run_endogenous_indexation_comparison(config)
    for result in (pair.nominal, pair.indexed):
        assert all(row.export_revenue == row.export_units == 0 for row in result.aggregate_months)
        assert result.aggregate_months[-1].employed_households < config.micro.households
