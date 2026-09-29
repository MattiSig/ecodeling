"""End-to-end tests for scenario and comparison CLI commands."""

import json
from pathlib import Path

from typer.testing import CliRunner

from ecodeling.cli import app
from ecodeling.reporting import BatchConfig, load_config

runner = CliRunner()
CONFIG = Path(__file__).parents[1] / "fixtures" / "phase10_report_config.json"


def test_run_shock_pair_and_comparison_commands(tmp_path: Path) -> None:
    commands = (("run", 1), ("shock-pair", 2), ("compare", 4))
    for command, expected_runs in commands:
        output = tmp_path / command
        result = runner.invoke(app, [command, str(CONFIG), "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert len(tuple((output / "runs").iterdir())) == expected_runs
        assert (output / "manifest.json").is_file()


def test_batch_command_executes_reduced_monte_carlo(tmp_path: Path) -> None:
    batch_config = BatchConfig(
        model=load_config(CONFIG),
        seeds=(1010,),
        alpha_values=(0.0,),
    )
    config_path = tmp_path / "batch.json"
    config_path.write_text(json.dumps(batch_config.model_dump(mode="json")))
    output = tmp_path / "batch-output"

    result = runner.invoke(app, ["batch", str(config_path), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert "1 runs, 0 resumed" in result.output
    assert (output / "summary.json").is_file()
