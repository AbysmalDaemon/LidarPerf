from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from lidarperf.regression import (
    AccuracyGate,
    PerformanceGate,
    RegressionPolicy,
    RegressionVerdict,
    regress_bundles,
)
from lidarperf.repeatability import summarize_scalars

STEP9 = Path("docs/validation/step9_kiss_hilti.lperf")
STEP10 = Path("docs/validation/step10_kiss_hilti_repeated.lperf")
PAIR_ORDER = ["AB", "BA", "AB", "BA", "AB"]


def _refresh_checksums(bundle: Path) -> None:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    lines = []
    for relative in manifest["file_inventory"]:
        digest = hashlib.sha256((bundle / relative).read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative}\n")
    (bundle / "checksums.sha256").write_text("".join(lines), encoding="utf-8")


def _controlled_copy(tmp_path: Path, name: str) -> Path:
    bundle = tmp_path / f"{name}.lperf"
    shutil.copytree(STEP10, bundle)

    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["measurement_class"] = "controlled"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    environment_path = bundle / "environment.json"
    environment = json.loads(environment_path.read_text(encoding="utf-8"))
    environment["measurement_class"] = "controlled"
    environment["execution"].update(
        {
            "performance_authoritative": True,
            "performance_authority_reason": "synthetic Step 12 controlled fixture",
            "host_control_mode": "self_hosted",
            "host_control_reason": "dedicated unit-test host",
            "benchmark_host_id": "test-host-01",
            "cpu_allocation": [0],
            "thread_policy": "single_thread",
            "pairing_id": "step12-test-pairing",
            "paired_execution": True,
            "pairing_seed": 20260916,
            "pair_order": PAIR_ORDER,
        }
    )
    environment["host"]["cpu"]["governors"] = ["performance"]
    environment_path.write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_checksums(bundle)
    return bundle


def _policy(*, threshold: float = 5.0) -> RegressionPolicy:
    return RegressionPolicy(
        performance=PerformanceGate(
            metric="wall_time_s",
            max_regression_percent=threshold,
            bootstrap_samples=2_000,
            bootstrap_seed=12345,
            min_valid_pairs=5,
        ),
        accuracy_gates=(
            AccuracyGate(
                type="relative_max_regression",
                metric="ape.translation.rmse_m",
                max_regression_percent=2.0,
            ),
            AccuracyGate(
                type="relative_max_regression",
                metric="ape.rotation.rmse_deg",
                max_regression_percent=2.0,
            ),
        ),
    )


def _scale_trial_resource(bundle: Path, metric: str, factors: list[float]) -> None:
    values: list[float] = []
    for index, factor in enumerate(factors, start=1):
        path = bundle / "trials" / f"{index:04d}" / "resources.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["values"][metric] = float(payload["values"][metric]) * factor
        values.append(float(payload["values"][metric]))
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    aggregate_path = bundle / "aggregate.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    aggregate["metrics"]["resources"][metric] = summarize_scalars(values)
    aggregate_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_checksums(bundle)


def _scale_trial_metric(bundle: Path, metric: str, factor: float) -> None:
    values: list[float] = []
    for index in range(1, 6):
        path = bundle / "trials" / f"{index:04d}" / "metrics.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["values"][metric] = float(payload["values"][metric]) * factor
        values.append(float(payload["values"][metric]))
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    aggregate_path = bundle / "aggregate.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    aggregate["metrics"]["trial_metrics"][metric] = summarize_scalars(values)
    aggregate_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_checksums(bundle)


def test_real_hosted_step9_step10_regression_is_not_comparable() -> None:
    report = regress_bundles(STEP9, STEP10, policy=_policy())

    assert report.verdict == RegressionVerdict.NOT_COMPARABLE
    assert report.comparison.accuracy_comparable is True
    assert report.comparison.performance_comparable is False


def test_identical_controlled_paired_evidence_passes(tmp_path: Path) -> None:
    baseline = _controlled_copy(tmp_path, "baseline")
    candidate = _controlled_copy(tmp_path, "candidate")

    report = regress_bundles(baseline, candidate, policy=_policy())

    assert report.verdict == RegressionVerdict.PASS
    assert all(result.passed is True for result in report.accuracy_gates)
    assert report.performance is not None
    assert report.performance.valid_pairs == 5
    assert report.performance.median_regression_percent == pytest.approx(0.0)
    assert report.performance.confidence_interval_low_percent == pytest.approx(0.0)
    assert report.performance.confidence_interval_high_percent == pytest.approx(0.0)


def test_missing_explicit_gates_is_inconclusive(tmp_path: Path) -> None:
    baseline = _controlled_copy(tmp_path, "baseline")
    candidate = _controlled_copy(tmp_path, "candidate")

    report = regress_bundles(baseline, candidate)

    assert report.verdict == RegressionVerdict.INCONCLUSIVE
    assert "accuracy gate" in report.warnings[0]


def test_slow_candidate_fails_performance(tmp_path: Path) -> None:
    baseline = _controlled_copy(tmp_path, "baseline")
    candidate = _controlled_copy(tmp_path, "candidate")
    _scale_trial_resource(candidate, "wall_time_s", [1.10] * 5)

    report = regress_bundles(baseline, candidate, policy=_policy(threshold=5.0))

    assert report.verdict == RegressionVerdict.FAIL_PERFORMANCE
    assert report.performance is not None
    assert report.performance.median_regression_percent == pytest.approx(10.0)
    assert report.performance.confidence_interval_low_percent > 5.0


def test_threshold_crossing_uncertainty_is_inconclusive(tmp_path: Path) -> None:
    baseline = _controlled_copy(tmp_path, "baseline")
    candidate = _controlled_copy(tmp_path, "candidate")
    _scale_trial_resource(candidate, "wall_time_s", [1.00, 1.00, 1.05, 1.10, 1.10])

    report = regress_bundles(baseline, candidate, policy=_policy(threshold=5.0))

    assert report.verdict == RegressionVerdict.INCONCLUSIVE
    assert report.performance is not None
    assert report.performance.confidence_interval_low_percent <= 5.0
    assert report.performance.confidence_interval_high_percent > 5.0


def test_accuracy_regression_fails_before_performance(tmp_path: Path) -> None:
    baseline = _controlled_copy(tmp_path, "baseline")
    candidate = _controlled_copy(tmp_path, "candidate")
    _scale_trial_metric(candidate, "ape.translation.rmse_m", 1.10)
    _scale_trial_resource(candidate, "wall_time_s", [0.50] * 5)

    report = regress_bundles(baseline, candidate, policy=_policy())

    assert report.verdict == RegressionVerdict.FAIL_ACCURACY
    translation = next(
        result for result in report.accuracy_gates if result.metric == "ape.translation.rmse_m"
    )
    assert translation.passed is False
    assert report.performance is None


def test_missing_randomized_pair_metadata_is_not_comparable(tmp_path: Path) -> None:
    baseline = _controlled_copy(tmp_path, "baseline")
    candidate = _controlled_copy(tmp_path, "candidate")

    environment_path = candidate / "environment.json"
    environment = json.loads(environment_path.read_text(encoding="utf-8"))
    environment["execution"].pop("pairing_seed")
    environment_path.write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_checksums(candidate)

    report = regress_bundles(baseline, candidate, policy=_policy())

    assert report.verdict == RegressionVerdict.NOT_COMPARABLE
    assert any("pairing_seed" in issue for issue in report.comparability_issues)


def test_accuracy_gate_requires_type_specific_parameter() -> None:
    with pytest.raises(ValueError, match="requires max_regression_percent"):
        AccuracyGate(type="relative_max_regression", metric="ape.translation.rmse_m")
