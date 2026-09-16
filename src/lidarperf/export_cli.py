"""CLI handlers for external result exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .export import BencherExportError, build_bencher_export


def export_bencher_results(
    bundle: Path,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write Bencher Metric Format JSON to a file instead of stdout.",
        ),
    ] = None,
) -> None:
    """Export a verified `.lperf` bundle as Bencher Metric Format JSON."""

    try:
        export = build_bencher_export(bundle)
    except (BencherExportError, OSError, ValueError) as exc:
        typer.echo(f"INVALID BENCHER EXPORT: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    text = json.dumps(export.bmf(), indent=2, sort_keys=True)
    if output is None:
        typer.echo(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        typer.echo(f"Bencher JSON: {output}", err=True)

    if export.alerts_suppressed:
        typer.echo(
            "NOTE: Bencher alerts suppressed for this evidence; metrics remain descriptive.",
            err=True,
        )
