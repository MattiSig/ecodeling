"""Production replay-v1 contract, reconciliation, and serialization tests."""

import gzip
import json

import pytest

from ecodeling.config.schema import (
    ForeignSectorConfig,
    IndexationConfig,
    MicroSimulationConfig,
    ModelConfig,
    RealEconomyConfig,
    ShockConfig,
    ShockKind,
    SimulationConfig,
)
from ecodeling.economy import run_endogenous_indexation_comparison
from ecodeling.identifiers import ScenarioId
from ecodeling.reporting import (
    ReplayBundleV1,
    ReplayCompatibilityError,
    ReplaySizeError,
    export_replay_v1,
    load_replay_v1,
    serialize_replay_v1,
)


def _bundle() -> ReplayBundleV1:
    config = ModelConfig(
        scenario_id=ScenarioId("replay-v1-test"),
        simulation=SimulationConfig(months=15, seed=1212),
        indexation=IndexationConfig(mortgage_alpha=1.0, lag_months=1),
        micro=MicroSimulationConfig(households=20, banks=1, mortgage_term_months=120),
        real_economy=RealEconomyConfig(firms=4, firm_cash_buffer_months=36),
        foreign_sector=ForeignSectorConfig(import_share_bps=2_500),
        shock=ShockConfig(kind=ShockKind.FX_DEPRECIATION, month=3, magnitude=0.1),
    )
    return export_replay_v1(
        run_endogenous_indexation_comparison(config),
        git_commit="0123456789abcdef",
    )


def test_v1_is_aligned_reconciled_and_deterministic() -> None:
    first = _bundle()
    second = _bundle()

    assert first.canonical_json() == second.canonical_json()
    assert ReplayBundleV1.model_validate_json(first.canonical_json()) == first
    assert [run.regime for run in first.runs] == ["nominal", "indexed"]
    assert first.scenario_pairing.shared_initialization
    assert first.scenario_pairing.shared_shock_path
    assert {row.sector for row in first.sector_snapshots} == {
        "households",
        "firms",
        "banks",
        "government",
        "central_bank",
        "foreign",
    }
    assert all(
        row.financial_assets_isk is None
        for row in first.sector_snapshots
        if row.sector in {"government", "central_bank"}
    )
    assert {row.dimension for row in first.distribution_series} == {
        "income_quintile",
        "homeowner_status",
        "mortgage_regime",
        "initial_ltv_group",
        "opening_liquidity_group",
    }
    assert {row.household_id for row in first.representative_agents if row.regime == "nominal"} == {
        row.household_id for row in first.representative_agents if row.regime == "indexed"
    }


def test_v1_serialization_is_bounded_compressed_and_hash_stable() -> None:
    bundle = _bundle()
    first = serialize_replay_v1(bundle)
    second = serialize_replay_v1(bundle)

    assert first == second
    assert gzip.decompress(first.gzip_bytes) == first.canonical_bytes
    assert len(first.gzip_bytes) < len(first.canonical_bytes)
    assert load_replay_v1(first.canonical_bytes) == bundle
    assert len(first.sha256) == 64

    with pytest.raises(ReplaySizeError, match="exceeds"):
        export_replay_v1(
            run_endogenous_indexation_comparison(
                ModelConfig(
                    scenario_id=ScenarioId("too-small"),
                    simulation=SimulationConfig(months=2, seed=1),
                    micro=MicroSimulationConfig(households=10, banks=1),
                    real_economy=RealEconomyConfig(firms=2),
                )
            ),
            git_commit="0123456",
            maximum_uncompressed_bytes=1,
        )


def test_v1_loader_has_explicit_compatibility_errors() -> None:
    with pytest.raises(ReplayCompatibilityError, match="cannot be losslessly migrated"):
        load_replay_v1(json.dumps({"manifest": {"schema_version": 0}}))
    with pytest.raises(ReplayCompatibilityError, match="unsupported"):
        load_replay_v1(json.dumps({"manifest": {"schema_version": 2}}))
    with pytest.raises(ReplayCompatibilityError, match="not valid JSON"):
        load_replay_v1("not json")
