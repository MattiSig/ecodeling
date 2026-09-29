"""Replay-v0 schema, selection, and accounting provenance tests."""

import json

import pytest

from ecodeling.config.schema import MicroSimulationConfig, ModelConfig, SimulationConfig
from ecodeling.identifiers import ScenarioId
from ecodeling.micro import constant_external_paths, run_micro_simulation
from ecodeling.micro.entities import MortgageRegime
from ecodeling.micro.outputs import MicroSimulationResult
from ecodeling.reporting.replay import ReplayBundle, export_replay_v0


def _result() -> MicroSimulationResult:
    config = ModelConfig(
        scenario_id=ScenarioId("replay-test"),
        simulation=SimulationConfig(months=4, seed=27),
        micro=MicroSimulationConfig(households=20, banks=2, mortgage_term_months=24),
    )
    return run_micro_simulation(
        config,
        constant_external_paths(config, annual_inflation_bps=800),
        MortgageRegime.INDEXED,
    )


def test_export_is_canonical_validated_and_deterministic() -> None:
    result = _result()

    first = export_replay_v0(result, git_commit="0123456789abcdef")
    second = export_replay_v0(result, git_commit="0123456789abcdef")

    assert first.canonical_json() == second.canonical_json()
    assert ReplayBundle.model_validate_json(first.canonical_json()) == first
    assert json.loads(first.canonical_json())["manifest"]["schema_version"] == 0
    assert first.manifest.months == tuple(str(row.month) for row in result.aggregate_months)


def test_replay_reconciles_visible_stocks_flows_and_revaluation_sides() -> None:
    result = _result()
    replay = export_replay_v0(result, git_commit="0123456789abcdef")

    for aggregate in result.aggregate_months:
        household = next(
            item
            for item in replay.snapshots
            if item.month == str(aggregate.month) and item.sector == "households"
        )
        banks = next(
            item
            for item in replay.snapshots
            if item.month == str(aggregate.month) and item.sector == "banks"
        )
        assert household.mortgage_principal == aggregate.total_mortgage_principal
        assert household.deposits == aggregate.household_deposits
        assert household.net_worth == aggregate.household_net_worth
        assert banks.mortgage_principal == aggregate.total_mortgage_principal
        assert (
            sum(
                flow.amount
                for flow in replay.flows
                if flow.month == str(aggregate.month) and flow.flow_type == "principal_and_interest"
            )
            == aggregate.debt_service
        )

    events = [event for event in replay.events if event.event_type == "CPI_REVALUATION"]
    assert events
    for event in events:
        assert event.amount > 0
        assert {side.role for side in event.ledger_sides} == {
            "borrower_liability",
            "lender_asset",
        }
        assert {side.amount for side in event.ledger_sides} == {event.amount}
        assert event.ledger_entry_id == f"micro:{event.month}:cpi-revaluation"


def test_representatives_are_stable_real_households_with_complete_tracks() -> None:
    result = _result()
    replay = export_replay_v0(result, git_commit="0123456789abcdef")
    household_ids = {str(item.id) for item in result.households}

    assert replay.manifest.representative_selection.startswith("deterministic")
    assert {item.household_id for item in replay.representative_agents} <= household_ids
    assert len({item.household_id for item in replay.representative_agents}) == len(
        replay.representative_agents
    )
    assert all(
        len(item.track) == len(result.aggregate_months) for item in replay.representative_agents
    )


def test_schema_rejects_unknown_or_incompatible_fields() -> None:
    replay = export_replay_v0(_result(), git_commit="0123456789abcdef")
    payload = json.loads(replay.canonical_json())
    payload["manifest"]["schema_version"] = 1

    with pytest.raises(ValueError):
        ReplayBundle.model_validate(payload)
