"""Command-line entry points for Ecodeling."""

from pathlib import Path
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


ConfigArgument = Annotated[
    Path,
    typer.Argument(exists=True, dir_okay=False, readable=True, resolve_path=True),
]
OutputOption = Annotated[
    Path,
    typer.Option("--output", "-o", help="New or empty output directory."),
]


@app.command("run")
def run_command(config: ConfigArgument, output: OutputOption) -> None:
    """Run one JSON configuration and persist authoritative analytical outputs."""
    from ecodeling.reporting import current_git_commit, generate_single_run, load_config

    result = generate_single_run(load_config(config), output, git_commit=current_git_commit())
    typer.echo(f"Wrote {result.experiment_id} to {result.path}")


@app.command("shock-pair")
def shock_pair_command(config: ConfigArgument, output: OutputOption) -> None:
    """Run a configured shock against the same regime's no-shock baseline."""
    from ecodeling.reporting import current_git_commit, generate_shock_pair, load_config

    result = generate_shock_pair(load_config(config), output, git_commit=current_git_commit())
    typer.echo(f"Wrote {result.experiment_id} to {result.path}")


@app.command("compare")
def compare_command(config: ConfigArgument, output: OutputOption) -> None:
    """Generate the complete nominal/indexed counterfactual experiment and figures."""
    from ecodeling.reporting import current_git_commit, generate_regime_comparison, load_config

    result = generate_regime_comparison(
        load_config(config), output, git_commit=current_git_commit()
    )
    typer.echo(f"Wrote {result.experiment_id} to {result.path}")


@app.command("batch")
def batch_command(config: ConfigArgument, output: OutputOption) -> None:
    """Run or resume a bounded Monte Carlo and sensitivity batch."""
    from ecodeling.reporting import (
        current_git_commit,
        generate_batch,
        load_batch_config,
    )

    result = generate_batch(load_batch_config(config), output, git_commit=current_git_commit())
    typer.echo(
        f"Wrote {result.batch_id} ({result.run_count} runs, "
        f"{result.resumed_runs} resumed) to {result.path}"
    )


@app.command("serve")
def serve_command(
    host: Annotated[str, typer.Option(help="Service bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65_535, help="Service TCP port.")] = 8000,
) -> None:
    """Serve the bounded public simulation API."""
    import uvicorn

    uvicorn.run("ecodeling.service.api:app", host=host, port=port)
