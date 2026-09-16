"""CLI handler for portable LidarPerf reports."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .report import ReportError, write_report


def report_results(
    bundle: Path,
    html_path: Annotated[
        Path | None,
        typer.Option("--html", help="Write a self-contained HTML/SVG report."),
    ] = None,
    json_path: Annotated[
        Path | None,
        typer.Option("--json", help="Write the versioned machine-readable report JSON."),
    ] = None,
    comparison_path: Annotated[
        Path | None,
        typer.Option("--comparison", help="Attach a lidarperf.comparison.v1 JSON report."),
    ] = None,
    regression_path: Annotated[
        Path | None,
        typer.Option("--regression", help="Attach a lidarperf.regression.v1 JSON report."),
    ] = None,
) -> None:
    """Summarize a verified result bundle and optionally render a portable HTML report."""

    try:
        report = write_report(
            bundle,
            html_path=html_path,
            json_path=json_path,
            comparison_path=comparison_path,
            regression_path=regression_path,
        )
    except (ReportError, OSError, ValueError) as exc:
        typer.echo(f"INVALID REPORT: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo("LidarPerf report")
    typer.echo(f"result: {report.result_id}")
    typer.echo(f"verification: {report.verification_status}")
    typer.echo(f"measurement class: {report.measurement_class}")
    typer.echo(
        "performance authority: "
        + ("AUTHORITATIVE" if report.performance_authoritative else "NON-AUTHORITATIVE")
    )
    typer.echo(
        f"trials: {report.successful_trials}/{report.trial_count} successful; "
        f"warmups={report.warmup_trials}"
    )
    if html_path is not None:
        typer.echo(f"html: {html_path}")
    if json_path is not None:
        typer.echo(f"json: {json_path}")
