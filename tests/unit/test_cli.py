"""Tests for the initial command-line interface."""

from typer.testing import CliRunner

from ecodeling import __version__
from ecodeling.cli import app

runner = CliRunner()


def test_version_option_reports_package_version() -> None:
    """The eager version option should work without a subcommand."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout == f"ecodeling {__version__}\n"


def test_validate_reports_success() -> None:
    """The foundation validation command should report success."""
    result = runner.invoke(app, ["validate"])

    assert result.exit_code == 0
    assert result.stdout == "Ecodeling foundation is valid.\n"
