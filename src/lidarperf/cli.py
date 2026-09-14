"""Command-line entry point for LidarPerf."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from ._version import __version__
from .bundle import VerificationStatus, verify_bundle
from .host import DoctorSeverity, assess_host, probe_host
from .spec import ProtocolLoadError, load_protocol
from .synthetic import SyntheticFixtureConfig, write_fixture

app = typer.Typer(
    name="lidarperf",
    help="Conformance-aware performance regression testing for LiDAR odometry.",
    no_args_is_help=False,
    add_completion=False,
)
protocol_app = typer.Typer(help="Validate and inspect benchmark protocol documents.")
synthetic_app = typer.Typer(help="Generate deterministic synthetic conformance fixtures.")
app.add_typer(protocol_app, name="protocol")
app.add_typer(synthetic_app, name="synthetic")


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


@app.command("doctor")
def doctor(
    data_path: Path | None = typer.Option(
        None,
        "--data-path",
        help="Optional benchmark dataset path whose filesystem should be inspected.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit the complete machine-readable doctor report as JSON.",
    ),
) -> None:
    """Inspect host provenance and benchmark readiness without changing machine state."""

    report = assess_host(probe_host(data_path))
    if json_output:
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        snapshot = report.snapshot
        distro = snapshot.os.distribution or snapshot.os.system
        version = snapshot.os.distribution_version or snapshot.os.kernel_release
        typer.echo("LidarPerf host doctor")
        typer.echo(f"host_sha256: {snapshot.host_sha256}")
        typer.echo(f"platform: {distro} {version} ({snapshot.os.architecture})")
        typer.echo(
            "cpu: "
            f"{snapshot.cpu.model or 'unknown'}; "
            f"logical={snapshot.cpu.logical_cpus}; "
            f"affinity={snapshot.cpu.affinity_count or 'unknown'}"
        )
        typer.echo(f"cgroups: {snapshot.cgroups.version}")
        benchexec = snapshot.runtime.benchexec_available or snapshot.runtime.runexec_available
        typer.echo(f"benchexec: {'available' if benchexec else 'unavailable'}")
        typer.echo("eligible: " + ", ".join(report.eligible_measurement_classes))
        if report.issues:
            typer.echo("issues:")
            for issue in report.issues:
                typer.echo(f"  {issue.severity.value.upper()} [{issue.code}] {issue.message}")
        else:
            typer.echo("issues: none")

    if any(issue.severity == DoctorSeverity.ERROR for issue in report.issues):
        raise typer.Exit(code=2)


@app.command("verify")
def verify_result(path: Path) -> None:
    """Verify a LidarPerf result bundle's schema, provenance links, and checksums."""

    report = verify_bundle(path)
    typer.echo(report.status.value)
    for issue in report.issues:
        stream = sys.stderr if issue.severity.value == "error" else sys.stdout
        typer.echo(f"{issue.severity.value.upper()} [{issue.code}] {issue.message}", file=stream)
    if report.status == VerificationStatus.INVALID:
        raise typer.Exit(code=2)


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


@synthetic_app.command("generate")
def synthetic_generate(
    output: Path,
    pose_count: int = typer.Option(240, "--poses", min=2, help="Number of LiDAR scans/poses."),
    scan_rate_hz: float = typer.Option(10.0, "--scan-rate", min=0.001, help="Scan rate in Hz."),
    max_points_per_scan: int = typer.Option(
        384,
        "--max-points",
        min=1,
        help="Maximum points retained in each synthetic scan.",
    ),
    seed: int = typer.Option(20260914, "--seed", help="Deterministic noise seed."),
    noise_std_m: float = typer.Option(
        0.0,
        "--noise-std",
        min=0.0,
        help="Per-axis synthetic point-noise standard deviation in metres.",
    ),
    motion_distortion: bool = typer.Option(
        False,
        "--motion-distortion/--no-motion-distortion",
        help="Generate rolling-scan motion distortion using exact acquisition-time poses.",
    ),
) -> None:
    """Write a deterministic synthetic LiDAR sequence and exact ground truth."""

    try:
        config = SyntheticFixtureConfig(
            pose_count=pose_count,
            scan_rate_hz=scan_rate_hz,
            max_points_per_scan=max_points_per_scan,
            seed=seed,
            noise_std_m=noise_std_m,
            motion_distortion=motion_distortion,
        )
        manifest = write_fixture(output, config)
    except (FileExistsError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo("GENERATED")
    typer.echo(f"output: {output}")
    typer.echo(f"fixture_sha256: {manifest.fixture_id_sha256}")
    typer.echo(f"scans: {manifest.scan_count}")
    typer.echo(f"points: {manifest.total_point_count}")
