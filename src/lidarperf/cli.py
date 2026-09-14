"""Command-line entry point for LidarPerf."""

from __future__ import annotations

from pathlib import Path

import typer

from ._version import __version__
from .spec import ProtocolLoadError, load_protocol

app = typer.Typer(
    name="lidarperf",
    help="Conformance-aware performance regression testing for LiDAR odometry.",
    no_args_is_help=False,
    add_completion=False,
)
protocol_app = typer.Typer(help="Validate and inspect benchmark protocol documents.")
app.add_typer(protocol_app, name="protocol")


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


@protocol_app.command("validate")
def protocol_validate(path: Path) -> None:
    """Validate a protocol YAML/JSON document and print its canonical identity."""

    try:
        resolved = load_protocol(path)
    except ProtocolLoadError as exc:
        typer.echo(f"INVALID: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    identity = resolved.document.protocol
    typer.echo("VALID")
    typer.echo(f"protocol: {identity.id}@{identity.version}")
    typer.echo(f"track: {resolved.document.track.value}")
    typer.echo(f"sha256: {resolved.resolved_sha256}")
