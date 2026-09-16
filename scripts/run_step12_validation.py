#!/usr/bin/env python3
"""Generate durable Step 12 regression-engine validation evidence.

The synthetic controlled scenarios below are decision-logic fixtures derived from the
already committed Step 10 payload. They are not new benchmark runs and MUST NOT be
reported as controlled KISS-ICP performance evidence.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from lidarperf.regression import (
    AccuracyGate,
    PerformanceGate,
    RegressionPolicy,
    RegressionVerdict,
    regress_bundles,
)
from lidarperf.repeatability import summarize_scalars

ROOT = Path(__file__).resolve().parents[1]
STEP9 = ROOT / "docs/validation/step9_kiss_hilti.lperf"
STEP10 = ROOT / "docs/validation/step10_kiss_hilti_repeated.lperf"
OUTPUT = ROOT / "docs/validation/step12_regression_engine.json"
PAIR_ORDER = ["AB", "BA", "AB", "BA", "AB"]


def _refresh_checksums(bundle: Path) -> None:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    lines = []
    for relative in manifest["file_inventory"]:
        digest = hashlib.sha256((bundle / relative).read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative}\n")
    (bundle / "checksums.sha256").write_text("".join(lines), encoding="utf-8")


def _controlled_copy(parent: Path, name: str) -> Path:
    bundle = parent / f"{name}.lperf"
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
            "performance_authority_reason": "synthetic Step 12 decision fixture",
            "host_control_mode": "self_hosted",
            "host_control_reason": "synthetic decision fixture; not a benchmark claim",
            "benchmark_host_id": "step12-fixture-host",
            "cpu_allocation": [0],
            "thread_policy": "single_thread",
            "pairing_id": "step12-validation-pairing",
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


def _policy() -> RegressionPolicy:
    return RegressionPolicy(
        performance=PerformanceGate(
            metric="wall_time_s",
            max_regression_percent=5.0,
            confidence_level=0.95,
            bootstrap_samples=10_000,
            bootstrap_seed=20260916,
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


def _scale_resource(bundle: Path, factors: list[float]) -> None:
    values: list[float] = []
    for index, factor in enumerate(factors, start=1):
        path = bundle / "trials" / f"{index:04d}" / "resources.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["values"]["wall_time_s"] = float(payload["values"]["wall_time_s"]) * factor
        values.append(float(payload["values"]["wall_time_s"]))
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    aggregate_path = bundle / "aggregate.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    aggregate["metrics"]["resources"]["wall_time_s"] = summarize_scalars(values)
    aggregate_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_checksums(bundle)


def _scale_accuracy(bundle: Path, factor: float) -> None:
    metric = "ape.translation.rmse_m"
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


def _compact(report) -> dict[str, object]:
    performance = report.performance
    return {
        "verdict": report.verdict.value,
        "accuracy_comparable": report.comparison.accuracy_comparable,
        "performance_comparable": report.comparison.performance_comparable,
        "regression_comparable": report.comparison.regression_comparable,
        "accuracy_gates": [
            {
                "metric": gate.metric,
                "passed": gate.passed,
                "observed_regression_percent": gate.observed_regression_percent,
                "threshold": gate.threshold,
            }
            for gate in report.accuracy_gates
        ],
        "performance": (
            None
            if performance is None
            else {
                "metric": performance.metric,
                "valid_pairs": performance.valid_pairs,
                "median_regression_percent": performance.median_regression_percent,
                "confidence_level": performance.confidence_level,
                "confidence_interval_percent": [
                    performance.confidence_interval_low_percent,
                    performance.confidence_interval_high_percent,
                ],
                "practical_threshold_percent": performance.practical_threshold_percent,
                "bootstrap_samples": performance.bootstrap_samples,
                "bootstrap_seed": performance.bootstrap_seed,
            }
        ),
        "comparability_issues": list(report.comparability_issues),
        "warnings": list(report.warnings),
    }


def main() -> None:
    policy = _policy()
    hosted = regress_bundles(STEP9, STEP10, policy=policy)
    assert hosted.verdict == RegressionVerdict.NOT_COMPARABLE

    with tempfile.TemporaryDirectory(prefix="lidarperf-step12-") as tmp:
        root = Path(tmp)

        pass_baseline = _controlled_copy(root, "pass-baseline")
        pass_candidate = _controlled_copy(root, "pass-candidate")
        passed = regress_bundles(pass_baseline, pass_candidate, policy=policy)
        assert passed.verdict == RegressionVerdict.PASS

        slow_baseline = _controlled_copy(root, "slow-baseline")
        slow_candidate = _controlled_copy(root, "slow-candidate")
        _scale_resource(slow_candidate, [1.10] * 5)
        slow = regress_bundles(slow_baseline, slow_candidate, policy=policy)
        assert slow.verdict == RegressionVerdict.FAIL_PERFORMANCE

        accuracy_baseline = _controlled_copy(root, "accuracy-baseline")
        accuracy_candidate = _controlled_copy(root, "accuracy-candidate")
        _scale_accuracy(accuracy_candidate, 1.10)
        _scale_resource(accuracy_candidate, [0.50] * 5)
        accuracy = regress_bundles(accuracy_baseline, accuracy_candidate, policy=policy)
        assert accuracy.verdict == RegressionVerdict.FAIL_ACCURACY
        assert accuracy.performance is None

        noisy_baseline = _controlled_copy(root, "noisy-baseline")
        noisy_candidate = _controlled_copy(root, "noisy-candidate")
        _scale_resource(noisy_candidate, [1.00, 1.00, 1.05, 1.10, 1.10])
        noisy = regress_bundles(noisy_baseline, noisy_candidate, policy=policy)
        assert noisy.verdict == RegressionVerdict.INCONCLUSIVE

    payload = {
        "schema_version": "lidarperf.step12-validation.v1",
        "evidence_kind": "decision-engine validation; synthetic controlled scenarios are not benchmark claims",
        "source_evidence": {
            "real_hosted_baseline": "docs/validation/step9_kiss_hilti.lperf",
            "real_hosted_candidate": "docs/validation/step10_kiss_hilti_repeated.lperf",
            "synthetic_scenarios_derived_from": "docs/validation/step10_kiss_hilti_repeated.lperf",
        },
        "policy": policy.model_dump(mode="json"),
        "real_hosted_guardrail": _compact(hosted),
        "synthetic_decision_scenarios": {
            "pass": _compact(passed),
            "performance_regression": _compact(slow),
            "accuracy_regression_even_when_faster": _compact(accuracy),
            "uncertainty_crosses_threshold": _compact(noisy),
        },
        "assertions": {
            "hosted_evidence_refused": True,
            "pass_path_demonstrated": True,
            "performance_failure_path_demonstrated": True,
            "accuracy_precedes_speed": True,
            "inconclusive_uncertainty_path_demonstrated": True,
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
