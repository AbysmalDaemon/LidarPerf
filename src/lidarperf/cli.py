"""Command-line entry point for LidarPerf."""

from __future__ import annotations

import typer

from ._version import __version__

app = typer.Typer(
    name="lidarperf",
    help="Conformance-aware performance regression testing for LiDAR odometry.",
    no_args_is_help=False,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"lidarperf {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed LidarPerf version and exit.",
    ),
) -> None:
    """Run LidarPerf."""
    if ctx.invoked_subcommand is None and not version:
        typer.echo(ctx.get_help())
