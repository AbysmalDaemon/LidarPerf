from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from lidarperf.comparison import ComparisonError, compare_bundles
from lidarperf.spec import sha256_fingerprint

STEP9 = Path("docs/validation/step9_kiss_hilti.lperf")
STEP10 = Path("docs/validation/step10_kiss_hilti_repeated.lperf")


def _refresh_checksums(bundle: Path) -> None:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    lines = []
    for relative in manifest["file_inventory"]:
        digest = hashlib.sha256((bundle / relative).read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative}\n")
    (bundle / "checksums.sha256").write_text("".join(lines), encoding="utf-8")


def _controlled_copy(tmp_path: Path) -> Path:
    bundle = tmp_path / "controlled.lperf"
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
    execution = environment["execution"]
    execution.update(
        {
            "performance_authoritative": True,
            "performance_authority_reason": "synthetic controlled comparison fixture",
            "host_control_mode": "self_hosted",
            "host_control_reason": "dedicated unit-test host",
            "benchmark_host_id": "test-host-01",
            "cpu_allocation": [0],
            "thread_policy": "single_thread",
            "pairing_id": "test-pairing-01",
            "paired_execution": True,
        }
    )
    environment["host"]["cpu"]["governors"] = ["performance"]
    environment_path.write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_checksums(bundle)
    return bundle


def test_real_step9_step10_are_accuracy_comparable_but_not_performance_comparable() -> None:
    report = compare_bundles(STEP9, STEP10)

    assert report.accuracy_comparable is True
    assert report.performance_comparable is False
    assert report.performance_authoritative is False
    assert report.regression_comparable is False
    assert "protocol.resolved_sha256" in report.observed_differences
    assert "manifest.trial_count" in report.observed_differences
    assert report.metric_changes["ape.translation.rmse_m"].absolute == pytest.approx(5.55e-17)
    assert "wall_time_s" in report.resource_changes


def test_controlled_identical_paired_evidence_is_strictly_comparable(tmp_path: Path) -> None:
    bundle = _controlled_copy(tmp_path)
    report = compare_bundles(bundle, bundle)

    assert report.accuracy_comparable is True
    assert report.performance_comparable is True
    assert report.performance_authoritative is True
    assert report.regression_comparable is True
    assert all(check.comparable for check in report.checks)


def test_declared_config_difference_is_explicit_not_silent(tmp_path: Path) -> None:
    baseline = _controlled_copy(tmp_path / "baseline")
    candidate = tmp_path / "candidate" / "controlled.lperf"
    candidate.parent.mkdir(parents=True)
    shutil.copytree(baseline, candidate)

    config_path = candidate / "config" / "algorithm.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["step11_test_variant"] = True
    config_text = yaml.safe_dump(config, sort_keys=True, allow_unicode=True)
    config_path.write_text(config_text, encoding="utf-8")

    method_path = candidate / "method.json"
    method = json.loads(method_path.read_text(encoding="utf-8"))
    method["config_sha256"] = sha256_fingerprint(yaml.safe_load(config_text))
    method_path.write_text(
        json.dumps(method, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_checksums(candidate)

    strict = compare_bundles(baseline, candidate)
    declared = compare_bundles(baseline, candidate, declared_differences={"config"})

    assert strict.regression_comparable is False
    config_check = next(check for check in strict.checks if check.code == "ALGORITHM_CONFIG")
    assert config_check.comparable is False
    assert declared.regression_comparable is True
    assert declared.declared_differences == ("config",)
    assert "method.config_sha256" in declared.observed_differences


def test_invalid_bundle_is_refused_before_comparison(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.lperf"
    invalid.mkdir()
    with pytest.raises(ComparisonError, match="invalid"):
        compare_bundles(invalid, STEP10)


def test_unknown_declared_difference_is_rejected() -> None:
    with pytest.raises(ComparisonError, match="unknown declared difference"):
        compare_bundles(STEP10, STEP10, declared_differences={"magic"})
