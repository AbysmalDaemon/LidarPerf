"""Semantic comparison of verified LidarPerf result bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lidarperf.bundle import (
    ConformanceStatus,
    DatasetFingerprintClass,
    DatasetRecord,
    EnvironmentRecord,
    MethodRecord,
    ResultManifest,
    VerificationStatus,
    verify_bundle,
)
from lidarperf.spec import load_protocol

_ALLOWED_DECLARED_DIFFERENCES = {"config", "build_environment", "dependencies"}
_CONTROLLED_HOST_MODES = {"self_hosted", "dedicated_vm", "bare_metal", "other_controlled"}


class ComparisonError(ValueError):
    """Raised when a comparison cannot be formed from trustworthy bundle evidence."""


class ComparisonCheck(BaseModel):
    """One explicit semantic comparability check."""

    model_config = ConfigDict(frozen=True)

    scope: Literal["accuracy", "performance", "regression"]
    code: str
    comparable: bool
    reason: str
    baseline: Any = None
    candidate: Any = None


class ScalarChange(BaseModel):
    """Candidate minus baseline change for one numeric scalar."""

    model_config = ConfigDict(frozen=True)

    baseline: float
    candidate: float
    absolute: float
    relative_percent: float | None


class ComparisonReport(BaseModel):
    """Dimension-aware comparison result for two verified bundles."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["lidarperf.comparison.v1"] = "lidarperf.comparison.v1"
    baseline_result_id: str
    candidate_result_id: str
    accuracy_comparable: bool
    performance_comparable: bool
    regression_comparable: bool
    performance_authoritative: bool
    declared_differences: tuple[str, ...] = ()
    checks: tuple[ComparisonCheck, ...]
    observed_differences: tuple[str, ...]
    metric_changes: dict[str, ScalarChange] = Field(default_factory=dict)
    resource_changes: dict[str, ScalarChange] = Field(default_factory=dict)


class _BundleView:
    def __init__(self, root: Path) -> None:
        verification = verify_bundle(root)
        if verification.status == VerificationStatus.INVALID:
            issues = "; ".join(f"{issue.code}: {issue.message}" for issue in verification.issues)
            raise ComparisonError(f"bundle {root} is invalid: {issues}")

        self.root = root
        self.manifest = ResultManifest.model_validate_json((root / "manifest.json").read_text())
        self.dataset = DatasetRecord.model_validate_json((root / "dataset.json").read_text())
        self.environment = EnvironmentRecord.model_validate_json(
            (root / "environment.json").read_text()
        )
        self.method = MethodRecord.model_validate_json((root / "method.json").read_text())
        self.protocol = load_protocol(root / "protocol.yaml").document
        self.metrics = _numeric_metrics(root)
        self.resources = _numeric_resources(root)


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("median", "mean"):
            scalar = value.get(key)
            if isinstance(scalar, (int, float)) and not isinstance(scalar, bool):
                return float(scalar)
    return None


def _numeric_metrics(root: Path) -> dict[str, float]:
    aggregate_path = root / "aggregate.json"
    if aggregate_path.is_file():
        aggregate = _read_json(aggregate_path)
        metrics = aggregate.get("metrics", {})
        metric_values = metrics.get("trial_metrics", metrics)
        return {
            key: scalar
            for key, value in metric_values.items()
            if (scalar := _summary_value(value)) is not None
        }

    metrics = _read_json(root / "trials" / "0001" / "metrics.json").get("values", {})
    return {
        key: scalar
        for key, value in metrics.items()
        if (scalar := _summary_value(value)) is not None
    }


def _numeric_resources(root: Path) -> dict[str, float]:
    aggregate_path = root / "aggregate.json"
    if aggregate_path.is_file():
        aggregate = _read_json(aggregate_path)
        resources = aggregate.get("metrics", {}).get("resources")
        if isinstance(resources, dict):
            return {
                key: scalar
                for key, value in resources.items()
                if (scalar := _summary_value(value)) is not None
            }

    resources = _read_json(root / "trials" / "0001" / "resources.json").get("values", {})
    return {
        key: scalar
        for key, value in resources.items()
        if (scalar := _summary_value(value)) is not None
    }


def _scalar_changes(
    baseline: dict[str, float], candidate: dict[str, float]
) -> dict[str, ScalarChange]:
    changes: dict[str, ScalarChange] = {}
    for key in sorted(baseline.keys() & candidate.keys()):
        before = baseline[key]
        after = candidate[key]
        absolute = after - before
        relative = None if before == 0 else 100.0 * absolute / before
        changes[key] = ScalarChange(
            baseline=before,
            candidate=after,
            absolute=absolute,
            relative_percent=relative,
        )
    return changes


def _preprocessing_signature(protocol: Any) -> dict[str, Any]:
    signature: dict[str, Any] = {}
    preprocessing = protocol.preprocessing
    for name in (
        "coordinate_transform",
        "voxel_downsample",
        "crop",
        "range_filter",
        "outlier_filter",
        "ground_removal",
        "intensity_filter",
        "timestamp_reconstruction",
        "point_reordering",
        "duplicate_removal",
    ):
        operation = getattr(preprocessing, name)
        record: dict[str, Any] = {"owner": operation.owner.value}
        if operation.owner.value in {"dataset", "benchmark"}:
            record["parameters"] = operation.parameters
        signature[name] = record

    motion = preprocessing.motion_compensation
    motion_record: dict[str, Any] = {
        "input_state": motion.input_state.value,
        "performed_by": motion.performed_by.value,
    }
    if motion.performed_by.value in {"dataset", "benchmark"}:
        motion_record["motion_source"] = motion.motion_source.value
        motion_record["parameters"] = motion.parameters
    signature["motion_compensation"] = motion_record
    return signature


def _trajectory_metric_signature(protocol: Any) -> dict[str, Any]:
    trajectory = protocol.trajectory
    return {
        "pose": trajectory.pose.model_dump(mode="json"),
        "alignment": trajectory.alignment.value,
        "scale_correction": trajectory.scale_correction,
        "ape_translation": trajectory.ape_translation,
        "ape_rotation": trajectory.ape_rotation,
        "relative_error_windows": [
            window.model_dump(mode="json") for window in trajectory.relative_error_windows
        ],
    }


def _host_fingerprint(view: _BundleView) -> Any:
    return view.environment.host.get("host_sha256")


def _execution(view: _BundleView, key: str) -> Any:
    return view.environment.execution.get(key)


def _method_family(view: _BundleView) -> tuple[Any, Any]:
    return (view.method.name, view.method.source.repository)


def _check(
    checks: list[ComparisonCheck],
    *,
    scope: Literal["accuracy", "performance", "regression"],
    code: str,
    baseline: Any,
    candidate: Any,
    reason: str,
    predicate: bool | None = None,
) -> bool:
    comparable = baseline == candidate if predicate is None else predicate
    checks.append(
        ComparisonCheck(
            scope=scope,
            code=code,
            comparable=comparable,
            reason=reason,
            baseline=_json_value(baseline),
            candidate=_json_value(candidate),
        )
    )
    return comparable


def _paired_execution(baseline: _BundleView, candidate: _BundleView) -> bool:
    baseline_id = _execution(baseline, "pairing_id")
    candidate_id = _execution(candidate, "pairing_id")
    return (
        bool(baseline_id)
        and baseline_id == candidate_id
        and _execution(baseline, "paired_execution") is True
        and _execution(candidate, "paired_execution") is True
        and baseline.manifest.trial_count >= 2
        and candidate.manifest.trial_count >= 2
    )


def compare_bundles(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    declared_differences: set[str] | frozenset[str] = frozenset(),
) -> ComparisonReport:
    """Compare two verified bundles without inventing missing benchmark semantics."""

    unknown = set(declared_differences) - _ALLOWED_DECLARED_DIFFERENCES
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ComparisonError(f"unknown declared difference(s): {names}")

    baseline = _BundleView(Path(baseline_path))
    candidate = _BundleView(Path(candidate_path))
    checks: list[ComparisonCheck] = []

    accuracy_results = [
        _check(
            checks,
            scope="accuracy",
            code="CONFORMANCE",
            baseline=baseline.manifest.conformance_status.value,
            candidate=candidate.manifest.conformance_status.value,
            reason="both bundles must remain conformant",
            predicate=(
                baseline.manifest.conformance_status != ConformanceStatus.NON_CONFORMANT
                and candidate.manifest.conformance_status != ConformanceStatus.NON_CONFORMANT
            ),
        ),
        _check(
            checks,
            scope="accuracy",
            code="TRACK",
            baseline=baseline.manifest.track.value,
            candidate=candidate.manifest.track.value,
            reason="strict accuracy comparison requires a compatible track",
        ),
        _check(
            checks,
            scope="accuracy",
            code="TEMPORAL_SEMANTICS",
            baseline=baseline.protocol.estimator_semantics,
            candidate=candidate.protocol.estimator_semantics,
            reason="strict comparison requires compatible estimator temporal semantics",
        ),
        _check(
            checks,
            scope="accuracy",
            code="SENSOR_POLICY",
            baseline=baseline.protocol.sensors,
            candidate=candidate.protocol.sensors,
            reason="runtime sensor policies must match",
        ),
        _check(
            checks,
            scope="accuracy",
            code="DATASET_FINGERPRINT",
            baseline=(baseline.dataset.id, baseline.dataset.content_sha256),
            candidate=(candidate.dataset.id, candidate.dataset.content_sha256),
            reason="dataset sequence and exact content fingerprint must match",
            predicate=(
                baseline.dataset.fingerprint_class == DatasetFingerprintClass.EXACT
                and candidate.dataset.fingerprint_class == DatasetFingerprintClass.EXACT
                and baseline.dataset.id == candidate.dataset.id
                and baseline.dataset.content_sha256 is not None
                and baseline.dataset.content_sha256 == candidate.dataset.content_sha256
            ),
        ),
        _check(
            checks,
            scope="accuracy",
            code="GROUND_TRUTH_FINGERPRINT",
            baseline=baseline.dataset.ground_truth_sha256,
            candidate=candidate.dataset.ground_truth_sha256,
            reason="ground-truth identity must be known and identical",
            predicate=(
                baseline.dataset.ground_truth_sha256 is not None
                and baseline.dataset.ground_truth_sha256 == candidate.dataset.ground_truth_sha256
            ),
        ),
        _check(
            checks,
            scope="accuracy",
            code="EVALUATION_FRAME",
            baseline=baseline.protocol.trajectory.evaluation_frame,
            candidate=candidate.protocol.trajectory.evaluation_frame,
            reason="evaluation-frame semantics must match",
        ),
        _check(
            checks,
            scope="accuracy",
            code="TIMESTAMP_ASSOCIATION",
            baseline=baseline.protocol.trajectory.association,
            candidate=candidate.protocol.trajectory.association,
            reason="timestamp-association semantics must match",
        ),
        _check(
            checks,
            scope="accuracy",
            code="PREPROCESSING_INPUT_SEMANTICS",
            baseline=_preprocessing_signature(baseline.protocol),
            candidate=_preprocessing_signature(candidate.protocol),
            reason="benchmark/dataset-owned input preprocessing semantics must match",
        ),
        _check(
            checks,
            scope="accuracy",
            code="TRAJECTORY_METRIC_PROTOCOL",
            baseline=_trajectory_metric_signature(baseline.protocol),
            candidate=_trajectory_metric_signature(candidate.protocol),
            reason="trajectory metric semantics must match",
        ),
    ]
    accuracy_comparable = all(accuracy_results)

    baseline_cpu = _execution(baseline, "cpu_allocation")
    candidate_cpu = _execution(candidate, "cpu_allocation")
    baseline_thread = _execution(baseline, "thread_policy")
    candidate_thread = _execution(candidate, "thread_policy")
    baseline_host_id = _execution(baseline, "benchmark_host_id")
    candidate_host_id = _execution(candidate, "benchmark_host_id")
    baseline_host_mode = _execution(baseline, "host_control_mode")
    candidate_host_mode = _execution(candidate, "host_control_mode")

    performance_results = [
        accuracy_comparable,
        _check(
            checks,
            scope="performance",
            code="TIMING_SCOPE",
            baseline=baseline.protocol.timing.scope.value,
            candidate=candidate.protocol.timing.scope.value,
            reason="timing scopes must match",
        ),
        _check(
            checks,
            scope="performance",
            code="MEASUREMENT_CLASS",
            baseline=baseline.manifest.measurement_class.value,
            candidate=candidate.manifest.measurement_class.value,
            reason="measurement classes must match for strict v0.1 comparison",
        ),
        _check(
            checks,
            scope="performance",
            code="HARDWARE_FINGERPRINT",
            baseline=_host_fingerprint(baseline),
            candidate=_host_fingerprint(candidate),
            reason="recorded host hardware/environment fingerprints must match",
            predicate=(
                _host_fingerprint(baseline) is not None
                and _host_fingerprint(baseline) == _host_fingerprint(candidate)
            ),
        ),
        _check(
            checks,
            scope="performance",
            code="PHYSICAL_HOST_IDENTITY",
            baseline=baseline_host_id,
            candidate=candidate_host_id,
            reason="the same physical benchmark host must be explicitly identifiable",
            predicate=(
                bool(baseline_host_id)
                and baseline_host_id == candidate_host_id
                and baseline_host_mode in _CONTROLLED_HOST_MODES
                and candidate_host_mode in _CONTROLLED_HOST_MODES
            ),
        ),
        _check(
            checks,
            scope="performance",
            code="CPU_ALLOCATION",
            baseline=baseline_cpu,
            candidate=candidate_cpu,
            reason="explicit CPU allocations must be non-empty and identical",
            predicate=bool(baseline_cpu) and baseline_cpu == candidate_cpu,
        ),
        _check(
            checks,
            scope="performance",
            code="THREAD_POLICY",
            baseline=baseline_thread,
            candidate=candidate_thread,
            reason="explicit thread policies must be known and identical",
            predicate=bool(baseline_thread) and baseline_thread == candidate_thread,
        ),
        _check(
            checks,
            scope="performance",
            code="CACHE_POLICY",
            baseline=baseline.protocol.measurement.cache_policy.value,
            candidate=candidate.protocol.measurement.cache_policy.value,
            reason="cache policies must match",
        ),
        _check(
            checks,
            scope="performance",
            code="BENCHMARK_BACKEND",
            baseline=(_execution(baseline, "backend"), _execution(baseline, "backend_version")),
            candidate=(_execution(candidate, "backend"), _execution(candidate, "backend_version")),
            reason="benchmark backend semantics and version must match",
        ),
        _check(
            checks,
            scope="performance",
            code="SOFTWARE_ENVIRONMENT",
            baseline=baseline.environment.software,
            candidate=candidate.environment.software,
            reason=(
                "software environments must match unless dependencies are the declared subject"
            ),
            predicate=(
                baseline.environment.software == candidate.environment.software
                or "dependencies" in declared_differences
            ),
        ),
        _check(
            checks,
            scope="performance",
            code="PERFORMANCE_AUTHORITY",
            baseline=_execution(baseline, "performance_authoritative"),
            candidate=_execution(candidate, "performance_authoritative"),
            reason="both bundles must explicitly permit authoritative performance claims",
            predicate=(
                _execution(baseline, "performance_authoritative") is True
                and _execution(candidate, "performance_authoritative") is True
            ),
        ),
    ]
    performance_comparable = all(performance_results)
    performance_authoritative = performance_comparable

    protocol_equal = (
        baseline.manifest.protocol.resolved_sha256 == candidate.manifest.protocol.resolved_sha256
    )
    config_equal = baseline.method.config_sha256 == candidate.method.config_sha256
    build_equal = baseline.method.build == candidate.method.build
    dependencies_equal = baseline.environment.software == candidate.environment.software

    regression_results = [
        performance_comparable,
        _check(
            checks,
            scope="regression",
            code="METHOD_IDENTITY",
            baseline=_method_family(baseline),
            candidate=_method_family(candidate),
            reason="source-code regression requires the same method family/repository",
            predicate=(
                baseline.method.name == candidate.method.name
                and baseline.method.source.repository is not None
                and baseline.method.source.repository == candidate.method.source.repository
            ),
        ),
        _check(
            checks,
            scope="regression",
            code="EXACT_PROTOCOL",
            baseline=baseline.manifest.protocol.resolved_sha256,
            candidate=candidate.manifest.protocol.resolved_sha256,
            reason="strict regression requires the exact same resolved protocol",
            predicate=protocol_equal,
        ),
        _check(
            checks,
            scope="regression",
            code="ALGORITHM_CONFIG",
            baseline=baseline.method.config_sha256,
            candidate=candidate.method.config_sha256,
            reason="configuration must match unless config is the declared subject",
            predicate=config_equal or "config" in declared_differences,
        ),
        _check(
            checks,
            scope="regression",
            code="BUILD_ENVIRONMENT",
            baseline=baseline.method.build,
            candidate=candidate.method.build,
            reason="build environment must match unless explicitly declared",
            predicate=build_equal or "build_environment" in declared_differences,
        ),
        _check(
            checks,
            scope="regression",
            code="DEPENDENCY_SET",
            baseline=baseline.environment.software,
            candidate=candidate.environment.software,
            reason="dependency set must match unless explicitly declared",
            predicate=dependencies_equal or "dependencies" in declared_differences,
        ),
        _check(
            checks,
            scope="regression",
            code="PAIRED_REPETITION",
            baseline={
                "pairing_id": _execution(baseline, "pairing_id"),
                "paired_execution": _execution(baseline, "paired_execution"),
                "trial_count": baseline.manifest.trial_count,
            },
            candidate={
                "pairing_id": _execution(candidate, "pairing_id"),
                "paired_execution": _execution(candidate, "paired_execution"),
                "trial_count": candidate.manifest.trial_count,
            },
            reason="strict regression requires repeated paired execution",
            predicate=_paired_execution(baseline, candidate),
        ),
    ]
    regression_comparable = all(regression_results)

    differences: list[str] = []
    if baseline.manifest.protocol.resolved_sha256 != candidate.manifest.protocol.resolved_sha256:
        differences.append("protocol.resolved_sha256")
    if baseline.method.version != candidate.method.version:
        differences.append("method.version")
    if baseline.method.source.commit != candidate.method.source.commit:
        differences.append("method.source.commit")
    if baseline.method.config_sha256 != candidate.method.config_sha256:
        differences.append("method.config_sha256")
    if baseline.manifest.trial_count != candidate.manifest.trial_count:
        differences.append("manifest.trial_count")
    if baseline.environment.measurement_class != candidate.environment.measurement_class:
        differences.append("environment.measurement_class")
    if baseline.environment.host != candidate.environment.host:
        differences.append("environment.host")
    if baseline.environment.execution != candidate.environment.execution:
        differences.append("environment.execution")
    if baseline.environment.software != candidate.environment.software:
        differences.append("environment.software")

    return ComparisonReport(
        baseline_result_id=str(baseline.manifest.result_id),
        candidate_result_id=str(candidate.manifest.result_id),
        accuracy_comparable=accuracy_comparable,
        performance_comparable=performance_comparable,
        regression_comparable=regression_comparable,
        performance_authoritative=performance_authoritative,
        declared_differences=tuple(sorted(declared_differences)),
        checks=tuple(checks),
        observed_differences=tuple(differences),
        metric_changes=_scalar_changes(baseline.metrics, candidate.metrics),
        resource_changes=_scalar_changes(baseline.resources, candidate.resources),
    )
