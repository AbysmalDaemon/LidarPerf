"""Accuracy-gated paired performance regression decisions for LidarPerf bundles."""

from __future__ import annotations

import json
import math
import random
import statistics
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from lidarperf.bundle import (
    ConformanceStatus,
    ResultManifest,
    TrialRecord,
    TrialStatus,
    VerificationStatus,
    verify_bundle,
)
from lidarperf.comparison import ComparisonError, ComparisonReport, compare_bundles


class RegressionError(ValueError):
    """Raised when trustworthy regression evidence cannot be loaded."""


class RegressionVerdict(StrEnum):
    """Normative Step 12 regression outcomes from SPEC.md section 61."""

    PASS = "PASS"
    FAIL_ACCURACY = "FAIL_ACCURACY"
    FAIL_PERFORMANCE = "FAIL_PERFORMANCE"
    FAIL_VALIDITY = "FAIL_VALIDITY"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class MetricDirection(StrEnum):
    """Direction that represents improvement for a scalar metric."""

    LOWER_IS_BETTER = "lower_is_better"
    HIGHER_IS_BETTER = "higher_is_better"


class AccuracyGate(BaseModel):
    """One explicit accuracy gate; no universal gate is silently invented."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["absolute_max", "relative_max_regression", "non_inferiority_margin"]
    metric: str = Field(min_length=1)
    direction: MetricDirection = MetricDirection.LOWER_IS_BETTER
    limit: float | None = None
    max_regression_percent: float | None = Field(default=None, ge=0.0)
    margin: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_gate_parameters(self) -> AccuracyGate:
        supplied = {
            "limit": self.limit is not None,
            "max_regression_percent": self.max_regression_percent is not None,
            "margin": self.margin is not None,
        }
        expected = {
            "absolute_max": "limit",
            "relative_max_regression": "max_regression_percent",
            "non_inferiority_margin": "margin",
        }[self.type]
        if not supplied[expected]:
            raise ValueError(f"accuracy gate type {self.type!r} requires {expected}")
        extras = [name for name, present in supplied.items() if present and name != expected]
        if extras:
            raise ValueError(f"accuracy gate type {self.type!r} does not use: {', '.join(extras)}")
        if self.type == "absolute_max" and self.direction != MetricDirection.LOWER_IS_BETTER:
            raise ValueError("absolute_max currently supports lower_is_better metrics only")
        return self


class PerformanceGate(BaseModel):
    """Explicit practical performance threshold plus paired uncertainty settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str = Field(default="wall_time_s", min_length=1)
    direction: MetricDirection = MetricDirection.LOWER_IS_BETTER
    max_regression_percent: float | None = Field(default=None, ge=0.0)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    bootstrap_samples: int = Field(default=10_000, ge=100, le=1_000_000)
    bootstrap_seed: int = 20260916
    min_valid_pairs: int = Field(default=5, ge=2)


class RegressionPolicy(BaseModel):
    """Versioned explicit decision policy supplied to ``lidarperf regress``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["lidarperf.regression-policy.v1"] = "lidarperf.regression-policy.v1"
    performance: PerformanceGate = Field(default_factory=PerformanceGate)
    accuracy_gates: tuple[AccuracyGate, ...] = ()
    require_all_trials_successful: bool = True


class AccuracyGateResult(BaseModel):
    """Evaluation result for one configured accuracy gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    metric: str
    direction: MetricDirection
    passed: bool | None
    baseline: float | None = None
    candidate: float | None = None
    observed_regression_percent: float | None = None
    threshold: float | None = None
    reason: str


class PairedPerformanceSummary(BaseModel):
    """Paired performance effect size and deterministic bootstrap uncertainty."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    direction: MetricDirection
    valid_pairs: int
    pair_regression_percent: tuple[float, ...]
    median_regression_percent: float
    confidence_level: float
    confidence_interval_low_percent: float
    confidence_interval_high_percent: float
    practical_threshold_percent: float
    bootstrap_samples: int
    bootstrap_seed: int


class RegressionReport(BaseModel):
    """Versioned Step 12 regression decision report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["lidarperf.regression.v1"] = "lidarperf.regression.v1"
    verdict: RegressionVerdict
    baseline_result_id: str
    candidate_result_id: str
    comparison: ComparisonReport
    policy: RegressionPolicy
    validity_issues: tuple[str, ...] = ()
    comparability_issues: tuple[str, ...] = ()
    accuracy_gates: tuple[AccuracyGateResult, ...] = ()
    performance: PairedPerformanceSummary | None = None
    warnings: tuple[str, ...] = ()


class _BundleRegressionView:
    def __init__(self, root: Path) -> None:
        verification = verify_bundle(root)
        if verification.status == VerificationStatus.INVALID:
            issues = "; ".join(f"{issue.code}: {issue.message}" for issue in verification.issues)
            raise RegressionError(f"bundle {root} is invalid: {issues}")
        self.root = root
        self.manifest = ResultManifest.model_validate_json((root / "manifest.json").read_text())
        self.environment = _read_json(root / "environment.json")
        self.trials = tuple(
            TrialRecord.model_validate_json(
                (root / "trials" / f"{index:04d}" / "trial.json").read_text()
            )
            for index in range(1, self.manifest.trial_count + 1)
        )

    @property
    def execution(self) -> dict[str, Any]:
        value = self.environment.get("execution", {})
        return value if isinstance(value, dict) else {}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_regression_policy(path: str | Path) -> RegressionPolicy:
    """Load a strict YAML/JSON Step 12 decision policy."""

    policy_path = Path(path)
    try:
        data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RegressionError(f"cannot load regression policy {policy_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RegressionError("regression policy must contain a mapping/object")
    try:
        return RegressionPolicy.model_validate(data)
    except ValueError as exc:
        raise RegressionError(f"invalid regression policy: {exc}") from exc


def _numeric_trial_value(root: Path, index: int, filename: str, metric: str) -> float | None:
    values = _read_json(root / "trials" / f"{index:04d}" / filename).get("values", {})
    value = values.get(metric) if isinstance(values, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    scalar = float(value)
    return scalar if math.isfinite(scalar) else None


def _execution_validity_issues(
    baseline: _BundleRegressionView,
    candidate: _BundleRegressionView,
    policy: RegressionPolicy,
) -> tuple[str, ...]:
    issues: list[str] = []
    for label, view in (("baseline", baseline), ("candidate", candidate)):
        if view.manifest.conformance_status == ConformanceStatus.NON_CONFORMANT:
            issues.append(f"{label} bundle is non-conformant")
        failed = [trial.trial_index for trial in view.trials if trial.status != TrialStatus.SUCCESS]
        if failed and policy.require_all_trials_successful:
            issues.append(f"{label} has failed measured trials: {failed}")
        for trial in view.trials:
            if trial.timed_out:
                issues.append(f"{label} trial {trial.trial_index} timed out")
            if trial.status == TrialStatus.SUCCESS and trial.exit_code != 0:
                issues.append(
                    f"{label} trial {trial.trial_index} is marked successful "
                    f"with exit_code={trial.exit_code}"
                )
    return tuple(issues)


def _pairing_issues(
    baseline: _BundleRegressionView,
    candidate: _BundleRegressionView,
) -> tuple[str, ...]:
    issues: list[str] = []
    baseline_exec = baseline.execution
    candidate_exec = candidate.execution

    pairing_id = baseline_exec.get("pairing_id")
    if not pairing_id or pairing_id != candidate_exec.get("pairing_id"):
        issues.append("paired regression requires the same non-empty pairing_id")
    if (
        baseline_exec.get("paired_execution") is not True
        or candidate_exec.get("paired_execution") is not True
    ):
        issues.append("both bundles must declare paired_execution=true")

    baseline_seed = baseline_exec.get("pairing_seed")
    candidate_seed = candidate_exec.get("pairing_seed")
    if not isinstance(baseline_seed, int) or baseline_seed != candidate_seed:
        issues.append(
            "paired blocked randomization requires the same recorded integer pairing_seed"
        )

    baseline_order = baseline_exec.get("pair_order")
    candidate_order = candidate_exec.get("pair_order")
    expected_count = baseline.manifest.trial_count
    if baseline.manifest.trial_count != candidate.manifest.trial_count:
        issues.append("paired regression requires equal baseline/candidate measured-trial counts")
    if not isinstance(baseline_order, list) or baseline_order != candidate_order:
        issues.append("both bundles must record the same pair_order metadata")
    elif len(baseline_order) != expected_count or any(
        order not in {"AB", "BA"} for order in baseline_order
    ):
        issues.append("pair_order must contain one AB/BA entry per measured pair")

    return tuple(issues)


def _normalized_regression_percent(
    baseline: float,
    candidate: float,
    direction: MetricDirection,
) -> float | None:
    if baseline == 0:
        return None
    raw = 100.0 * (candidate - baseline) / abs(baseline)
    return raw if direction == MetricDirection.LOWER_IS_BETTER else -raw


def _evaluate_accuracy_gate(
    comparison: ComparisonReport,
    gate: AccuracyGate,
) -> AccuracyGateResult:
    change = comparison.metric_changes.get(gate.metric)
    if change is None:
        return AccuracyGateResult(
            type=gate.type,
            metric=gate.metric,
            direction=gate.direction,
            passed=None,
            reason="metric is not available in both verified bundles",
        )

    baseline = change.baseline
    candidate = change.candidate
    if gate.type == "absolute_max":
        assert gate.limit is not None
        passed = candidate <= gate.limit
        return AccuracyGateResult(
            type=gate.type,
            metric=gate.metric,
            direction=gate.direction,
            passed=passed,
            baseline=baseline,
            candidate=candidate,
            threshold=gate.limit,
            reason=(
                f"candidate {candidate:.9g} {'<=' if passed else '>'} "
                f"absolute maximum {gate.limit:.9g}"
            ),
        )

    if gate.type == "relative_max_regression":
        assert gate.max_regression_percent is not None
        regression = _normalized_regression_percent(baseline, candidate, gate.direction)
        if regression is None:
            return AccuracyGateResult(
                type=gate.type,
                metric=gate.metric,
                direction=gate.direction,
                passed=None,
                baseline=baseline,
                candidate=candidate,
                threshold=gate.max_regression_percent,
                reason="baseline metric is zero, so relative regression is undefined",
            )
        passed = regression <= gate.max_regression_percent
        return AccuracyGateResult(
            type=gate.type,
            metric=gate.metric,
            direction=gate.direction,
            passed=passed,
            baseline=baseline,
            candidate=candidate,
            observed_regression_percent=regression,
            threshold=gate.max_regression_percent,
            reason=(
                f"normalized regression {regression:+.6g}% "
                f"{'<=' if passed else '>'} allowed {gate.max_regression_percent:.6g}%"
            ),
        )

    assert gate.margin is not None
    degradation = (
        candidate - baseline
        if gate.direction == MetricDirection.LOWER_IS_BETTER
        else baseline - candidate
    )
    passed = degradation <= gate.margin
    return AccuracyGateResult(
        type=gate.type,
        metric=gate.metric,
        direction=gate.direction,
        passed=passed,
        baseline=baseline,
        candidate=candidate,
        threshold=gate.margin,
        reason=(
            f"non-inferiority degradation {degradation:+.9g} "
            f"{'<=' if passed else '>'} margin {gate.margin:.9g}"
        ),
    )


def _percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("cannot take percentile of an empty population")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _bootstrap_median_interval(
    values: tuple[float, ...],
    *,
    confidence_level: float,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    medians = []
    for _ in range(samples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(float(statistics.median(sample)))
    medians.sort()
    alpha = (1.0 - confidence_level) / 2.0
    return _percentile(medians, alpha), _percentile(medians, 1.0 - alpha)


def _paired_performance_summary(
    baseline: _BundleRegressionView,
    candidate: _BundleRegressionView,
    gate: PerformanceGate,
) -> PairedPerformanceSummary | None:
    if gate.max_regression_percent is None:
        return None

    pair_changes: list[float] = []
    for index in range(1, min(baseline.manifest.trial_count, candidate.manifest.trial_count) + 1):
        before = _numeric_trial_value(baseline.root, index, "resources.json", gate.metric)
        after = _numeric_trial_value(candidate.root, index, "resources.json", gate.metric)
        if before is None or after is None:
            continue
        regression = _normalized_regression_percent(before, after, gate.direction)
        if regression is not None and math.isfinite(regression):
            pair_changes.append(regression)

    if len(pair_changes) < gate.min_valid_pairs:
        return None

    values = tuple(pair_changes)
    low, high = _bootstrap_median_interval(
        values,
        confidence_level=gate.confidence_level,
        samples=gate.bootstrap_samples,
        seed=gate.bootstrap_seed,
    )
    return PairedPerformanceSummary(
        metric=gate.metric,
        direction=gate.direction,
        valid_pairs=len(values),
        pair_regression_percent=values,
        median_regression_percent=float(statistics.median(values)),
        confidence_level=gate.confidence_level,
        confidence_interval_low_percent=low,
        confidence_interval_high_percent=high,
        practical_threshold_percent=gate.max_regression_percent,
        bootstrap_samples=gate.bootstrap_samples,
        bootstrap_seed=gate.bootstrap_seed,
    )


def regress_bundles(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    policy: RegressionPolicy | None = None,
    declared_differences: set[str] | frozenset[str] = frozenset(),
) -> RegressionReport:
    """Produce a conservative PASS/FAIL/INCONCLUSIVE decision from verified evidence."""

    effective_policy = policy or RegressionPolicy()
    baseline = _BundleRegressionView(Path(baseline_path))
    candidate = _BundleRegressionView(Path(candidate_path))

    try:
        comparison = compare_bundles(
            baseline.root,
            candidate.root,
            declared_differences=declared_differences,
        )
    except ComparisonError as exc:
        raise RegressionError(str(exc)) from exc

    validity_issues = _execution_validity_issues(baseline, candidate, effective_policy)
    if validity_issues:
        return RegressionReport(
            verdict=RegressionVerdict.FAIL_VALIDITY,
            baseline_result_id=str(baseline.manifest.result_id),
            candidate_result_id=str(candidate.manifest.result_id),
            comparison=comparison,
            policy=effective_policy,
            validity_issues=validity_issues,
        )

    comparability_issues: list[str] = []
    if not comparison.accuracy_comparable:
        comparability_issues.append("Step 11 accuracy comparability failed")
    if not comparison.performance_comparable:
        comparability_issues.append("Step 11 performance comparability failed")
    if not comparison.regression_comparable:
        comparability_issues.append("Step 11 regression comparability failed")
    comparability_issues.extend(_pairing_issues(baseline, candidate))
    if comparability_issues:
        return RegressionReport(
            verdict=RegressionVerdict.NOT_COMPARABLE,
            baseline_result_id=str(baseline.manifest.result_id),
            candidate_result_id=str(candidate.manifest.result_id),
            comparison=comparison,
            policy=effective_policy,
            comparability_issues=tuple(dict.fromkeys(comparability_issues)),
        )

    if not effective_policy.accuracy_gates:
        return RegressionReport(
            verdict=RegressionVerdict.INCONCLUSIVE,
            baseline_result_id=str(baseline.manifest.result_id),
            candidate_result_id=str(candidate.manifest.result_id),
            comparison=comparison,
            policy=effective_policy,
            warnings=("no explicit accuracy gate was supplied",),
        )

    accuracy_results = tuple(
        _evaluate_accuracy_gate(comparison, gate) for gate in effective_policy.accuracy_gates
    )
    if any(result.passed is False for result in accuracy_results):
        return RegressionReport(
            verdict=RegressionVerdict.FAIL_ACCURACY,
            baseline_result_id=str(baseline.manifest.result_id),
            candidate_result_id=str(candidate.manifest.result_id),
            comparison=comparison,
            policy=effective_policy,
            accuracy_gates=accuracy_results,
        )
    if any(result.passed is None for result in accuracy_results):
        return RegressionReport(
            verdict=RegressionVerdict.INCONCLUSIVE,
            baseline_result_id=str(baseline.manifest.result_id),
            candidate_result_id=str(candidate.manifest.result_id),
            comparison=comparison,
            policy=effective_policy,
            accuracy_gates=accuracy_results,
            warnings=("at least one configured accuracy gate could not be evaluated",),
        )

    if effective_policy.performance.max_regression_percent is None:
        return RegressionReport(
            verdict=RegressionVerdict.INCONCLUSIVE,
            baseline_result_id=str(baseline.manifest.result_id),
            candidate_result_id=str(candidate.manifest.result_id),
            comparison=comparison,
            policy=effective_policy,
            accuracy_gates=accuracy_results,
            warnings=("no explicit practical performance threshold was supplied",),
        )

    performance = _paired_performance_summary(
        baseline,
        candidate,
        effective_policy.performance,
    )
    if performance is None:
        return RegressionReport(
            verdict=RegressionVerdict.INCONCLUSIVE,
            baseline_result_id=str(baseline.manifest.result_id),
            candidate_result_id=str(candidate.manifest.result_id),
            comparison=comparison,
            policy=effective_policy,
            accuracy_gates=accuracy_results,
            warnings=(
                "insufficient valid paired performance observations for the configured metric",
            ),
        )

    threshold = performance.practical_threshold_percent
    if performance.confidence_interval_low_percent > threshold:
        verdict = RegressionVerdict.FAIL_PERFORMANCE
    elif performance.confidence_interval_high_percent <= threshold:
        verdict = RegressionVerdict.PASS
    else:
        verdict = RegressionVerdict.INCONCLUSIVE

    warnings: tuple[str, ...] = ()
    if verdict == RegressionVerdict.INCONCLUSIVE:
        warnings = ("paired confidence interval crosses the practical regression threshold",)

    return RegressionReport(
        verdict=verdict,
        baseline_result_id=str(baseline.manifest.result_id),
        candidate_result_id=str(candidate.manifest.result_id),
        comparison=comparison,
        policy=effective_policy,
        accuracy_gates=accuracy_results,
        performance=performance,
        warnings=warnings,
    )
