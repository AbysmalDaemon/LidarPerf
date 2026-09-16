"""Verified, self-contained HTML reporting for LidarPerf result bundles."""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from lidarperf.bundle import (
    DatasetRecord,
    EnvironmentRecord,
    MethodRecord,
    ResultManifest,
    TrialRecord,
    TrialStatus,
    VerificationStatus,
    verify_bundle,
)
from lidarperf.comparison import ComparisonReport
from lidarperf.regression import RegressionReport
from lidarperf.trajectory import parse_tum


class ReportError(ValueError):
    """Raised when a trustworthy report cannot be built."""


class NumericSummary(BaseModel):
    """Portable scalar summary used by the report schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = Field(ge=1)
    mean: float
    median: float
    std: float
    minimum: float
    maximum: float
    p90: float
    p95: float
    p99: float


class BundleReport(BaseModel):
    """Versioned machine-readable summary behind a rendered report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["lidarperf.report.v1"] = "lidarperf.report.v1"
    result_id: str
    created_at: str
    verification_status: str
    verification_issues: tuple[str, ...] = ()
    protocol_id: str
    protocol_version: int
    protocol_sha256: str
    track: str
    method_name: str
    method_version: str | None = None
    method_commit: str | None = None
    dataset_id: str
    dataset_fingerprint_class: str
    dataset_content_sha256: str | None = None
    measurement_class: str
    conformance_status: str
    performance_authoritative: bool
    performance_authority_reason: str | None = None
    timing_scope: str | None = None
    host_control_mode: str | None = None
    host_sha256: str | None = None
    cpu_model: str | None = None
    trial_count: int = Field(ge=1)
    successful_trials: int = Field(ge=0)
    failed_trials: int = Field(ge=0)
    warmup_trials: int = Field(ge=0)
    metrics: dict[str, NumericSummary] = Field(default_factory=dict)
    resources: dict[str, NumericSummary] = Field(default_factory=dict)
    repeatability: dict[str, JsonValue] = Field(default_factory=dict)
    trajectory_pose_count: int = Field(ge=0)
    trajectory_xy_bounds_m: tuple[float, float, float, float] | None = None
    warnings: tuple[str, ...] = ()
    comparison: ComparisonReport | None = None
    regression: RegressionReport | None = None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot read report input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReportError(f"expected JSON object in {path}")
    return value


def _summary(value: Any) -> NumericSummary | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        scalar = float(value)
        if not math.isfinite(scalar):
            return None
        return NumericSummary(
            count=1,
            mean=scalar,
            median=scalar,
            std=0.0,
            minimum=scalar,
            maximum=scalar,
            p90=scalar,
            p95=scalar,
            p99=scalar,
        )
    if not isinstance(value, dict):
        return None
    keys = ("count", "mean", "median", "std", "minimum", "maximum", "p90", "p95", "p99")
    if not all(key in value for key in keys):
        return None
    try:
        return NumericSummary(
            count=int(value["count"]),
            mean=float(value["mean"]),
            median=float(value["median"]),
            std=float(value["std"]),
            minimum=float(value["minimum"]),
            maximum=float(value["maximum"]),
            p90=float(value["p90"]),
            p95=float(value["p95"]),
            p99=float(value["p99"]),
        )
    except (TypeError, ValueError) as exc:
        raise ReportError(f"invalid numeric summary: {value!r}") from exc


def _summaries(values: dict[str, Any]) -> dict[str, NumericSummary]:
    summaries: dict[str, NumericSummary] = {}
    for name, value in values.items():
        if (summary := _summary(value)) is not None:
            summaries[name] = summary
    return summaries


def _aggregate_views(root: Path) -> tuple[
    int,
    int,
    dict[str, NumericSummary],
    dict[str, NumericSummary],
    dict[str, JsonValue],
]:
    aggregate = _read_json(root / "aggregate.json")
    successful = int(aggregate.get("successful_trials", 0))
    failed = int(aggregate.get("failed_trials", 0))
    raw_metrics = aggregate.get("metrics", {})
    if not isinstance(raw_metrics, dict):
        raise ReportError("aggregate metrics must be an object")

    trial_metrics = raw_metrics.get("trial_metrics", raw_metrics)
    metrics = _summaries(trial_metrics if isinstance(trial_metrics, dict) else {})
    resources = _summaries(
        raw_metrics.get("resources", {}) if isinstance(raw_metrics.get("resources"), dict) else {}
    )
    repeatability = raw_metrics.get("trajectory_repeatability", {})
    if not isinstance(repeatability, dict):
        repeatability = {}
    return successful, failed, metrics, resources, repeatability


def _fallback_resources(root: Path, trial_count: int) -> dict[str, NumericSummary]:
    records: dict[str, list[float]] = {}
    for index in range(1, trial_count + 1):
        trial_dir = root / "trials" / f"{index:04d}"
        trial = TrialRecord.model_validate_json((trial_dir / "trial.json").read_text())
        if trial.status != TrialStatus.SUCCESS:
            continue
        values = _read_json(trial_dir / "resources.json").get("values", {})
        if not isinstance(values, dict):
            continue
        for name, value in values.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                scalar = float(value)
                if math.isfinite(scalar):
                    records.setdefault(name, []).append(scalar)

    result: dict[str, NumericSummary] = {}
    for name, values in records.items():
        ordered = sorted(values)
        count = len(ordered)
        mean = sum(ordered) / count
        variance = sum((item - mean) ** 2 for item in ordered) / count

        def percentile(fraction: float) -> float:
            if count == 1:
                return ordered[0]
            position = fraction * (count - 1)
            lower = int(math.floor(position))
            upper = int(math.ceil(position))
            weight = position - lower
            return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

        result[name] = NumericSummary(
            count=count,
            mean=mean,
            median=percentile(0.5),
            std=math.sqrt(variance),
            minimum=ordered[0],
            maximum=ordered[-1],
            p90=percentile(0.9),
            p95=percentile(0.95),
            p99=percentile(0.99),
        )
    return result


def _first_successful_trajectory(root: Path, trial_count: int) -> tuple[tuple[float, float], ...]:
    for index in range(1, trial_count + 1):
        trial_dir = root / "trials" / f"{index:04d}"
        trial = TrialRecord.model_validate_json((trial_dir / "trial.json").read_text())
        trajectory_path = trial_dir / "trajectory.tum"
        if trial.status == TrialStatus.SUCCESS and trajectory_path.is_file():
            trajectory = parse_tum(trajectory_path.read_text(encoding="utf-8"))
            return tuple((float(row[0]), float(row[1])) for row in trajectory.positions_m)
    return ()


def _external_report(path: Path | None, model: type[BaseModel]) -> BaseModel | None:
    if path is None:
        return None
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReportError(f"cannot load {path}: {exc}") from exc


def build_report(
    bundle: str | Path,
    *,
    comparison_path: str | Path | None = None,
    regression_path: str | Path | None = None,
) -> BundleReport:
    """Build a trustworthy report summary from a verified immutable bundle."""

    root = Path(bundle)
    verification = verify_bundle(root)
    if verification.status == VerificationStatus.INVALID:
        detail = "; ".join(f"{issue.code}: {issue.message}" for issue in verification.issues)
        raise ReportError(f"bundle {root} is invalid: {detail}")

    manifest = ResultManifest.model_validate_json((root / "manifest.json").read_text())
    method = MethodRecord.model_validate_json((root / "method.json").read_text())
    dataset = DatasetRecord.model_validate_json((root / "dataset.json").read_text())
    environment = EnvironmentRecord.model_validate_json((root / "environment.json").read_text())
    successful, failed, metrics, resources, repeatability = _aggregate_views(root)
    if not resources:
        resources = _fallback_resources(root, manifest.trial_count)

    execution = environment.execution
    host = environment.host
    cpu = host.get("cpu", {}) if isinstance(host.get("cpu"), dict) else {}
    trajectory_xy = _first_successful_trajectory(root, manifest.trial_count)
    bounds = None
    if trajectory_xy:
        xs = [point[0] for point in trajectory_xy]
        ys = [point[1] for point in trajectory_xy]
        bounds = (min(xs), max(xs), min(ys), max(ys))

    comparison = _external_report(
        Path(comparison_path) if comparison_path is not None else None,
        ComparisonReport,
    )
    regression = _external_report(
        Path(regression_path) if regression_path is not None else None,
        RegressionReport,
    )
    result_id = str(manifest.result_id)
    for attached in (comparison, regression):
        if attached is None:
            continue
        baseline = getattr(attached, "baseline_result_id", None)
        candidate = getattr(attached, "candidate_result_id", None)
        if result_id not in {baseline, candidate}:
            raise ReportError("attached comparison/regression does not reference this result bundle")

    warnings = [
        f"{issue.severity.value.upper()} [{issue.code}] {issue.message}"
        for issue in verification.issues
    ]
    authoritative = execution.get("performance_authoritative") is True
    authority_reason = execution.get("performance_authority_reason")
    if not authoritative:
        reason = authority_reason if isinstance(authority_reason, str) else "not declared authoritative"
        warnings.append(f"Performance evidence is non-authoritative: {reason}")
    if failed:
        warnings.append(f"{failed} measured trial(s) failed; inspect retained trial evidence.")
    if dataset.fingerprint_class.value != "exact":
        warnings.append("Dataset fingerprint is weaker than exact content identity.")

    return BundleReport(
        result_id=result_id,
        created_at=manifest.created_at.isoformat(),
        verification_status=verification.status.value,
        verification_issues=tuple(warnings[: len(verification.issues)]),
        protocol_id=manifest.protocol.id,
        protocol_version=manifest.protocol.version,
        protocol_sha256=manifest.protocol.resolved_sha256,
        track=manifest.track.value,
        method_name=method.name,
        method_version=method.version,
        method_commit=method.source.commit,
        dataset_id=dataset.id,
        dataset_fingerprint_class=dataset.fingerprint_class.value,
        dataset_content_sha256=dataset.content_sha256,
        measurement_class=manifest.measurement_class.value,
        conformance_status=manifest.conformance_status.value,
        performance_authoritative=authoritative,
        performance_authority_reason=(
            authority_reason if isinstance(authority_reason, str) else None
        ),
        timing_scope=(execution.get("timing_scope") if isinstance(execution.get("timing_scope"), str) else None),
        host_control_mode=(
            execution.get("host_control_mode")
            if isinstance(execution.get("host_control_mode"), str)
            else None
        ),
        host_sha256=host.get("host_sha256") if isinstance(host.get("host_sha256"), str) else None,
        cpu_model=cpu.get("model") if isinstance(cpu.get("model"), str) else None,
        trial_count=manifest.trial_count,
        successful_trials=successful,
        failed_trials=failed,
        warmup_trials=int(execution.get("warmup_trials", 0) or 0),
        metrics=metrics,
        resources=resources,
        repeatability=repeatability,
        trajectory_pose_count=len(trajectory_xy),
        trajectory_xy_bounds_m=bounds,
        warnings=tuple(warnings),
        comparison=comparison,
        regression=regression,
    )


def _fmt(value: float, name: str = "") -> str:
    if "bytes" in name:
        if abs(value) >= 1024**3:
            return f"{value / 1024**3:.3f} GiB"
        if abs(value) >= 1024**2:
            return f"{value / 1024**2:.2f} MiB"
        if abs(value) >= 1024:
            return f"{value / 1024:.2f} KiB"
        return f"{value:.0f} B"
    if name.endswith("_s") or "time_s" in name:
        return f"{value:.4f} s"
    if "fraction" in name:
        return f"{100.0 * value:.2f}%"
    if "deg" in name:
        return f"{value:.4f}°"
    if name.endswith("_m") or ".rmse_m" in name:
        return f"{value:.4f} m"
    return f"{value:.6g}"


def _distribution_svg(summary: NumericSummary, name: str) -> str:
    width = 300.0
    lo = summary.minimum
    hi = summary.maximum
    if hi == lo:
        median_x = mean_x = width / 2
        p90_x = p95_x = width / 2
    else:
        scale = width / (hi - lo)
        median_x = (summary.median - lo) * scale
        mean_x = (summary.mean - lo) * scale
        p90_x = (summary.p90 - lo) * scale
        p95_x = (summary.p95 - lo) * scale
    title = escape(
        f"min {_fmt(lo, name)}; median {_fmt(summary.median, name)}; "
        f"mean {_fmt(summary.mean, name)}; p95 {_fmt(summary.p95, name)}; "
        f"max {_fmt(hi, name)}"
    )
    return (
        f'<svg class="dist" viewBox="0 0 320 36" role="img" aria-label="{title}">'
        '<line x1="10" y1="18" x2="310" y2="18" class="range"/>'
        f'<line x1="{10 + p90_x:.2f}" y1="9" x2="{10 + p90_x:.2f}" y2="27" '
        'class="p90"/>'
        f'<line x1="{10 + p95_x:.2f}" y1="7" x2="{10 + p95_x:.2f}" y2="29" '
        'class="p95"/>'
        f'<line x1="{10 + median_x:.2f}" y1="5" x2="{10 + median_x:.2f}" y2="31" '
        'class="median"/>'
        f'<circle cx="{10 + mean_x:.2f}" cy="18" r="4" class="mean"/>'
        "</svg>"
    )


def _trajectory_svg(points: tuple[tuple[float, float], ...]) -> str:
    if len(points) < 2:
        return '<div class="empty">No successful trajectory payload available.</div>'
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-12)
    span_y = max(max_y - min_y, 1e-12)
    width, height, pad = 660.0, 300.0, 18.0
    usable_w, usable_h = width - 2 * pad, height - 2 * pad
    scale = min(usable_w / span_x, usable_h / span_y)
    offset_x = (width - span_x * scale) / 2
    offset_y = (height - span_y * scale) / 2
    mapped = [
        (
            offset_x + (x - min_x) * scale,
            height - (offset_y + (y - min_y) * scale),
        )
        for x, y in points
    ]
    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in mapped)
    start_x, start_y = mapped[0]
    end_x, end_y = mapped[-1]
    return (
        '<svg class="trajectory" viewBox="0 0 660 300" role="img" '
        'aria-label="XY trajectory preview">'
        '<rect x="0" y="0" width="660" height="300" rx="10" class="plot-bg"/>'
        f'<polyline points="{polyline}" class="path"/>'
        f'<circle cx="{start_x:.2f}" cy="{start_y:.2f}" r="5" class="start"/>'
        f'<circle cx="{end_x:.2f}" cy="{end_y:.2f}" r="5" class="end"/>'
        "</svg>"
    )


def _metric_table(title: str, values: dict[str, NumericSummary]) -> str:
    if not values:
        return f'<section><h2>{escape(title)}</h2><div class="empty">No numeric values.</div></section>'
    rows = []
    for name, summary in sorted(values.items()):
        rows.append(
            "<tr>"
            f"<td><code>{escape(name)}</code></td>"
            f"<td>{_fmt(summary.median, name)}</td>"
            f"<td>{_fmt(summary.mean, name)}</td>"
            f"<td>{_fmt(summary.std, name)}</td>"
            f"<td>{_fmt(summary.p95, name)}</td>"
            f"<td>{_distribution_svg(summary, name)}</td>"
            "</tr>"
        )
    return (
        f"<section><h2>{escape(title)}</h2><div class=\"table-wrap\"><table>"
        "<thead><tr><th>Metric</th><th>Median</th><th>Mean</th><th>Std</th>"
        "<th>P95</th><th>Distribution</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div></section>"
    )


def _comparison_html(report: ComparisonReport | None) -> str:
    if report is None:
        return ""
    statuses = (
        ("Accuracy comparable", report.accuracy_comparable),
        ("Performance comparable", report.performance_comparable),
        ("Performance authoritative", report.performance_authoritative),
        ("Regression comparable", report.regression_comparable),
    )
    badges = "".join(
        f'<div class="status {"good" if value else "bad"}"><span>{escape(label)}</span>'
        f"<strong>{'YES' if value else 'NO'}</strong></div>"
        for label, value in statuses
    )
    failures = [check for check in report.checks if not check.comparable]
    reasons = "".join(
        f"<li><code>{escape(check.scope)}:{escape(check.code)}</code> "
        f"{escape(check.reason)}</li>"
        for check in failures
    )
    return (
        "<section><h2>Comparison context</h2>"
        f'<div class="status-grid">{badges}</div>'
        + (f'<ul class="issues">{reasons}</ul>' if reasons else "")
        + "</section>"
    )


def _regression_html(report: RegressionReport | None) -> str:
    if report is None:
        return ""
    verdict_class = "good" if report.verdict.value == "PASS" else "warn"
    body = (
        "<section><h2>Regression context</h2>"
        f'<div class="verdict {verdict_class}">{escape(report.verdict.value)}</div>'
    )
    if report.performance is not None:
        perf = report.performance
        body += (
            '<div class="kpi-grid">'
            f'<div class="kpi"><span>Median regression</span><strong>'
            f"{perf.median_regression_percent:+.3f}%</strong></div>"
            f'<div class="kpi"><span>Practical threshold</span><strong>'
            f"+{perf.practical_threshold_percent:.3f}%</strong></div>"
            f'<div class="kpi"><span>Valid pairs</span><strong>{perf.valid_pairs}</strong></div>'
            "</div>"
        )
    if report.comparability_issues:
        items = "".join(f"<li>{escape(item)}</li>" for item in report.comparability_issues)
        body += f'<ul class="issues">{items}</ul>'
    return body + "</section>"


def render_html(report: BundleReport, trajectory_xy: tuple[tuple[float, float], ...]) -> str:
    """Render a portable report with no external CSS, JavaScript, fonts, or network calls."""

    authority = "AUTHORITATIVE" if report.performance_authoritative else "NON-AUTHORITATIVE"
    authority_class = "good" if report.performance_authoritative else "warn"
    warnings = "".join(f"<li>{escape(item)}</li>" for item in report.warnings)
    key_metrics = (
        "ape.translation.rmse_m",
        "ape.rotation.rmse_deg",
        "coverage.temporal_fraction",
        "coverage.distance_fraction",
    )
    cards = []
    for name in key_metrics:
        summary = report.metrics.get(name)
        if summary is not None:
            cards.append(
                f'<div class="kpi"><span>{escape(name)}</span>'
                f"<strong>{_fmt(summary.median, name)}</strong></div>"
            )
    wall = report.resources.get("wall_time_s")
    if wall is not None:
        cards.append(
            '<div class="kpi"><span>wall_time_s median</span>'
            f"<strong>{_fmt(wall.median, 'wall_time_s')}</strong></div>"
        )

    repeatability = ""
    if report.repeatability:
        translation = report.repeatability.get("translation_pairwise_rmse_m")
        rotation = report.repeatability.get("rotation_pairwise_rmse_deg")
        timestamp_sets = report.repeatability.get("timestamp_sets_identical")
        repeatability = "<section><h2>Estimator-output repeatability</h2><div class=\"kpi-grid\">"
        for label, value, name in (
            ("Pairwise translation RMSE", translation, "translation_pairwise_rmse_m"),
            ("Pairwise rotation RMSE", rotation, "rotation_pairwise_rmse_deg"),
        ):
            summary = _summary(value)
            if summary is not None:
                repeatability += (
                    f'<div class="kpi"><span>{escape(label)}</span>'
                    f"<strong>{_fmt(summary.median, name)}</strong></div>"
                )
        if isinstance(timestamp_sets, bool):
            repeatability += (
                '<div class="kpi"><span>Identical timestamp sets</span>'
                f"<strong>{'YES' if timestamp_sets else 'NO'}</strong></div>"
            )
        repeatability += "</div></section>"

    title = f"LidarPerf report · {report.method_name} · {report.dataset_id}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{ color-scheme: light dark; --bg:#f5f7fa; --card:#fff; --text:#102a43;
--muted:#627d98; --line:#d9e2ec; --blue:#1769aa; --green:#137333; --red:#b3261e;
--amber:#9a6700; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111827; --card:#182235; --text:#e5edf7;
--muted:#9fb3c8; --line:#34445a; --blue:#78b9f2; --green:#7ed692; --red:#ff938a;
--amber:#ffd27d; }} }}
* {{ box-sizing:border-box; }} body {{ margin:0; font:14px/1.5 system-ui,-apple-system,sans-serif;
background:var(--bg); color:var(--text); }} main {{ max-width:1180px; margin:auto; padding:34px 22px 70px; }}
header {{ margin-bottom:24px; }} h1 {{ font-size:30px; margin:0 0 6px; }} h2 {{ font-size:19px;
margin:0 0 14px; }} p {{ color:var(--muted); }} section {{ background:var(--card); border:1px solid
var(--line); border-radius:14px; padding:20px; margin:16px 0; box-shadow:0 3px 14px #0000000d; }}
.badges,.kpi-grid,.status-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
gap:10px; }} .badge,.kpi,.status {{ border:1px solid var(--line); border-radius:10px; padding:12px; }}
.badge span,.kpi span,.status span {{ display:block; color:var(--muted); font-size:12px; margin-bottom:4px; }}
.badge strong,.kpi strong,.status strong {{ font-size:18px; }} .good strong,.verdict.good {{ color:var(--green); }}
.bad strong {{ color:var(--red); }} .warn strong,.verdict.warn {{ color:var(--amber); }}
.notice {{ border-left:5px solid var(--amber); }} .notice strong {{ color:var(--amber); }}
.verdict {{ font-size:26px; font-weight:800; margin-bottom:14px; }} .table-wrap {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ text-align:left; padding:9px; border-bottom:1px solid
var(--line); vertical-align:middle; }} th {{ color:var(--muted); font-size:12px; }} code {{ font-size:12px; }}
.dist {{ width:250px; max-width:36vw; height:36px; }} .range {{ stroke:var(--line); stroke-width:4; }}
.p90 {{ stroke:var(--blue); stroke-width:2; opacity:.55; }} .p95 {{ stroke:var(--blue); stroke-width:2; }}
.median {{ stroke:var(--text); stroke-width:3; }} .mean {{ fill:var(--amber); }} .trajectory {{ width:100%;
max-height:380px; }} .plot-bg {{ fill:var(--bg); stroke:var(--line); }} .path {{ fill:none; stroke:var(--blue);
stroke-width:2.2; }} .start {{ fill:var(--green); }} .end {{ fill:var(--red); }} .issues {{ color:var(--muted); }}
.empty {{ color:var(--muted); padding:10px 0; }} .mono {{ font-family:ui-monospace,SFMono-Regular,monospace;
word-break:break-all; }} footer {{ color:var(--muted); margin-top:26px; font-size:12px; }}
</style>
</head>
<body><main>
<header><h1>{escape(report.method_name)} · {escape(report.dataset_id)}</h1>
<p>Verified LidarPerf result report · result <span class="mono">{escape(report.result_id)}</span></p></header>
<section><h2>Evidence status</h2><div class="badges">
<div class="badge good"><span>Bundle verification</span><strong>{escape(report.verification_status)}</strong></div>
<div class="badge"><span>Measurement class</span><strong>{escape(report.measurement_class)}</strong></div>
<div class="badge"><span>Conformance</span><strong>{escape(report.conformance_status)}</strong></div>
<div class="badge {authority_class}"><span>Performance authority</span><strong>{authority}</strong></div>
</div></section>
{f'<section class="notice"><h2>Scientific caveats</h2><ul class="issues">{warnings}</ul></section>' if warnings else ''}
<section><h2>Run summary</h2><div class="kpi-grid">
<div class="kpi"><span>Measured trials</span><strong>{report.trial_count}</strong></div>
<div class="kpi good"><span>Successful</span><strong>{report.successful_trials}</strong></div>
<div class="kpi bad"><span>Failed</span><strong>{report.failed_trials}</strong></div>
<div class="kpi"><span>Warmups</span><strong>{report.warmup_trials}</strong></div>
{''.join(cards)}
</div></section>
<section><h2>Trajectory preview</h2>{_trajectory_svg(trajectory_xy)}
<p>{report.trajectory_pose_count} poses; XY preview is presentation only and does not replace protocol-scoped trajectory metrics.</p></section>
{_metric_table('Accuracy and validity metrics', report.metrics)}
{_metric_table('Runtime and resource measurements', report.resources)}
{repeatability}
{_comparison_html(report.comparison)}
{_regression_html(report.regression)}
<section><h2>Provenance</h2><div class="table-wrap"><table><tbody>
<tr><th>Protocol</th><td>{escape(report.protocol_id)}@{report.protocol_version}</td></tr>
<tr><th>Protocol SHA-256</th><td class="mono">{escape(report.protocol_sha256)}</td></tr>
<tr><th>Track / timing</th><td>{escape(report.track)} / {escape(report.timing_scope or 'unknown')}</td></tr>
<tr><th>Method version / commit</th><td>{escape(report.method_version or 'unknown')} / <span class="mono">{escape(report.method_commit or 'unknown')}</span></td></tr>
<tr><th>Dataset fingerprint</th><td>{escape(report.dataset_fingerprint_class)} / <span class="mono">{escape(report.dataset_content_sha256 or 'unknown')}</span></td></tr>
<tr><th>Host control</th><td>{escape(report.host_control_mode or 'unknown')}</td></tr>
<tr><th>Host SHA-256</th><td class="mono">{escape(report.host_sha256 or 'unknown')}</td></tr>
<tr><th>CPU</th><td>{escape(report.cpu_model or 'unknown')}</td></tr>
</tbody></table></div></section>
<footer>Generated from verified immutable LidarPerf evidence. This file is self-contained and performs no network requests.</footer>
</main></body></html>
"""


def write_report(
    bundle: str | Path,
    *,
    html_path: str | Path | None = None,
    json_path: str | Path | None = None,
    comparison_path: str | Path | None = None,
    regression_path: str | Path | None = None,
) -> BundleReport:
    """Build and optionally persist machine-readable and self-contained HTML reports."""

    root = Path(bundle)
    report = build_report(
        root,
        comparison_path=comparison_path,
        regression_path=regression_path,
    )
    trajectory_xy = _first_successful_trajectory(root, report.trial_count)
    if html_path is not None:
        target = Path(html_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_html(report, trajectory_xy), encoding="utf-8", newline="\n")
    if json_path is not None:
        target = Path(json_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report
