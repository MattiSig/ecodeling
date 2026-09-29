"""End-to-end tests for scenario and comparison CLI commands."""

from pathlib import Path

from typer.testing import CliRunner

from ecodeling.cli import app

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
