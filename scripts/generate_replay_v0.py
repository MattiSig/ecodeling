"""Regenerate the compact canonical replay-v0 browser fixture."""

from pathlib import Path

from ecodeling.config.schema import MicroSimulationConfig, ModelConfig, SimulationConfig
from ecodeling.identifiers import ScenarioId
from ecodeling.micro import constant_external_paths, run_micro_simulation
from ecodeling.micro.entities import MortgageRegime
from ecodeling.reporting.replay import export_replay_v0

BASELINE_COMMIT = "4e423f9a753d05da917e09414df2fab8a5824a91"
OUTPUT = Path("web/internal-audit/replay-v0.json")


def main() -> None:
    """Run the declared small model and write canonical validated JSON."""
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
    replay = export_replay_v0(result, git_commit=BASELINE_COMMIT)
    OUTPUT.write_text(replay.canonical_json() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
