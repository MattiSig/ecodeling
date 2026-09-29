"""Canonical compact replay regression fixture."""

from pathlib import Path

from ecodeling.config.schema import MicroSimulationConfig, ModelConfig, SimulationConfig
from ecodeling.identifiers import ScenarioId
from ecodeling.micro import constant_external_paths, run_micro_simulation
from ecodeling.micro.entities import MortgageRegime
from ecodeling.reporting.replay import export_replay_v0


def test_canonical_replay_fixture_matches_export() -> None:
    config = ModelConfig(
        scenario_id=ScenarioId("canonical-replay-v0"),
        simulation=SimulationConfig(months=6, seed=5),
        micro=MicroSimulationConfig(households=20, banks=2, mortgage_term_months=36),
    )
    result = run_micro_simulation(
        config,
        constant_external_paths(config, annual_inflation_bps=600),
        MortgageRegime.INDEXED,
    )
    replay = export_replay_v0(result, git_commit="4e423f9a753d05da917e09414df2fab8a5824a91")

    fixture = Path("web/internal-audit/replay-v0.json")
    assert fixture.read_text(encoding="utf-8") == replay.canonical_json() + "\n"
