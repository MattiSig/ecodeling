"""Command-line entry points for Ecodeling."""

from typing import Annotated

import typer

from ecodeling import __version__

app = typer.Typer(
    help="Build, validate, and run Ecodeling simulations.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    """Print the installed application version and exit."""
    if value:
        typer.echo(f"ecodeling {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            help="Show the version and exit.",
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Expose common Ecodeling command-line options."""


@app.command()
def validate() -> None:
    """Validate the installed foundation and exit successfully."""
    typer.echo("Ecodeling foundation is valid.")
