"""Bencher Metric Format export for verified LidarPerf result bundles."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from lidarperf.report import BundleReport, ReportError, build_report


class BencherExportError(ValueError):
    """Raised when a trustworthy Bencher export cannot be produced."""


class BencherMetric(BaseModel):
    """One Bencher Metric Format value."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    value: float


@dataclass(frozen=True)
class BencherExport:
    """Pure BMF payload plus the LidarPerf authority decision used to name it."""

    benchmark_name: str
    alerts_suppressed: bool
    metrics: dict[str, BencherMetric]

    def bmf(self) -> dict[str, dict[str, dict[str, float]]]:
        """Return plain Bencher Metric Format JSON data."""

        return {
            self.benchmark_name: {
                name: metric.model_dump(mode="json") for name, metric in self.metrics.items()
            }
        }


_METRIC_MEASURES = (
    ("ape.translation.rmse_m", "lidarperf-ape-translation-rmse-m"),
    ("ape.rotation.rmse_deg", "lidarperf-ape-rotation-rmse-deg"),
    ("coverage.temporal_fraction", "lidarperf-coverage-temporal-ratio"),
    ("coverage.distance_fraction", "lidarperf-coverage-distance-ratio"),
)

_RESOURCE_MEASURES = (
    ("wall_time_s", "lidarperf-wall-time-s"),
    ("cpu_time_s", "lidarperf-cpu-time-s"),
    ("peak_memory_bytes", "lidarperf-peak-memory-bytes"),
    ("cpu_core_equivalents", "lidarperf-cpu-core-equivalents"),
)

_REPEATABILITY_MEASURES = (
    ("translation_pairwise_rmse_m", "lidarperf-output-translation-rmse-m"),
    ("rotation_pairwise_rmse_deg", "lidarperf-output-rotation-rmse-deg"),
)

_SUCCESS_MEASURE = "lidarperf-trial-success-ratio"
_IGNORE_SUFFIX = "-bencher-ignore"
_BENCHMARK_NAME_LIMIT = 1024


def _kebab(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if normalized:
        return normalized
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"id-{digest}"


def _bounded_name(name: str, *, reserve: int = 0) -> str:
    limit = _BENCHMARK_NAME_LIMIT - reserve
    if len(name) <= limit:
        return name
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
    prefix_length = max(1, limit - len(digest) - 1)
    return f"{name[:prefix_length].rstrip('-')}-{digest}"


def _semantic_benchmark_name(report: BundleReport) -> str:
    dataset_identity = (
        report.dataset_content_sha256[:12]
        if report.dataset_content_sha256
        else report.dataset_fingerprint_class
    )
    protocol_identity = report.protocol_sha256[:12]
    components = (
        "lidarperf",
        report.track,
        report.method_name,
        report.dataset_id,
        f"data-{dataset_identity}",
        report.protocol_id,
        f"protocol-v{report.protocol_version}",
        f"protocol-{protocol_identity}",
        report.measurement_class,
    )
    return _bounded_name("-".join(_kebab(component) for component in components))


def _alerts_suppressed(report: BundleReport) -> bool:
    return (
        not report.performance_authoritative
        or report.conformance_status != "conformant"
        or report.failed_trials > 0
    )


def _metric(value: Any) -> BencherMetric | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    scalar = float(value)
    if not math.isfinite(scalar):
        return None
    return BencherMetric(value=scalar)


def _summary_median(summary: Any) -> BencherMetric | None:
    median = getattr(summary, "median", None)
    return _metric(median)


def _repeatability_median(report: BundleReport, key: str) -> BencherMetric | None:
    value = report.repeatability.get(key)
    if not isinstance(value, dict):
        return None
    return _metric(value.get("median"))


def _collect_metrics(report: BundleReport) -> dict[str, BencherMetric]:
    metrics: dict[str, BencherMetric] = {}

    for source, measure in _METRIC_MEASURES:
        if source in report.metrics and (metric := _summary_median(report.metrics[source])):
            metrics[measure] = metric

    for source, measure in _RESOURCE_MEASURES:
        if source in report.resources and (metric := _summary_median(report.resources[source])):
            metrics[measure] = metric

    for source, measure in _REPEATABILITY_MEASURES:
        if (metric := _repeatability_median(report, source)) is not None:
            metrics[measure] = metric

    success_ratio = report.successful_trials / report.trial_count
    metrics[_SUCCESS_MEASURE] = BencherMetric(value=success_ratio)
    return metrics


def export_report_to_bencher(report: BundleReport) -> BencherExport:
    """Convert an already verified report summary to conservative Bencher BMF data."""

    metrics = _collect_metrics(report)
    if not metrics:
        raise BencherExportError("verified bundle contains no exportable numeric metrics")

    suppressed = _alerts_suppressed(report)
    name = _semantic_benchmark_name(report)
    if suppressed:
        name = _bounded_name(name, reserve=len(_IGNORE_SUFFIX)) + _IGNORE_SUFFIX

    return BencherExport(
        benchmark_name=name,
        alerts_suppressed=suppressed,
        metrics=metrics,
    )


def build_bencher_export(bundle: str | Path) -> BencherExport:
    """Convert a verified result bundle into conservative Bencher Metric Format data.

    The emitted benchmark identity intentionally excludes result IDs, host identities, local
    paths, logs, and command lines. Exact dataset/protocol fingerprints are shortened into the
    stable semantic benchmark name so incompatible inputs do not silently share one history.

    Bencher alerts are automatically suppressed for non-authoritative, non-conformant, or
    partially failed evidence by using Bencher's ``-bencher-ignore`` benchmark-name suffix.
    Metrics are still stored by Bencher, but presentation cannot upgrade LidarPerf evidence.
    """

    try:
        report = build_report(bundle)
    except (ReportError, OSError, ValueError) as exc:
        raise BencherExportError(str(exc)) from exc

    return export_report_to_bencher(report)
