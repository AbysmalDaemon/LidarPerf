from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from lidarperf.bundle import VerificationStatus, verify_bundle
from lidarperf.cli import app

runner = CliRunner()


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_valid_bundle_verifies(valid_bundle: Path) -> None:
    report = verify_bundle(valid_bundle)
    assert report.status == VerificationStatus.VALID
    assert report.issues == ()


def test_cli_verify_valid_bundle(valid_bundle: Path) -> None:
    result = runner.invoke(app, ["verify", str(valid_bundle)])
    assert result.exit_code == 0
    assert result.stdout.strip() == "VALID"


def test_tampered_payload_fails_checksum(valid_bundle: Path) -> None:
    trajectory = valid_bundle / "trials/0001/trajectory.tum"
    trajectory.write_text("tampered\n", encoding="utf-8")
    report = verify_bundle(valid_bundle)
    assert report.status == VerificationStatus.INVALID
    assert "CHECKSUM_MISMATCH" in _codes(report)


def test_undeclared_payload_is_rejected(valid_bundle: Path) -> None:
    (valid_bundle / "surprise.txt").write_text("extra", encoding="utf-8")
    report = verify_bundle(valid_bundle)
    assert "INVENTORY_EXTRA" in _codes(report)


def test_missing_payload_is_rejected(valid_bundle: Path) -> None:
    (valid_bundle / "trials/0001/stdout.log").unlink()
    report = verify_bundle(valid_bundle)
    assert "INVENTORY_MISSING" in _codes(report)
    assert "PAYLOAD_MISSING" in _codes(report)


def test_config_semantic_hash_is_verified(valid_bundle: Path, refresh_checksums) -> None:
    config = valid_bundle / "config/algorithm.yaml"
    config.write_text("voxel_size: 2.0\nmax_iterations: 20\n", encoding="utf-8")
    refresh_checksums(valid_bundle)
    report = verify_bundle(valid_bundle)
    assert "CONFIG_HASH_MISMATCH" in _codes(report)
    assert "CHECKSUM_MISMATCH" not in _codes(report)


def test_protocol_identity_is_verified(valid_bundle: Path, refresh_checksums) -> None:
    manifest_path = valid_bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["protocol"]["resolved_sha256"] = "0" * 64
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    refresh_checksums(valid_bundle)
    report = verify_bundle(valid_bundle)
    assert "PROTOCOL_HASH_MISMATCH" in _codes(report)


def test_trial_count_consistency_is_verified(valid_bundle: Path, refresh_checksums) -> None:
    aggregate_path = valid_bundle / "aggregate.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    aggregate["successful_trials"] = 0
    aggregate["failed_trials"] = 1
    aggregate_path.write_text(
        json.dumps(aggregate, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    refresh_checksums(valid_bundle)
    report = verify_bundle(valid_bundle)
    assert "AGGREGATE_SUCCESS_COUNT_MISMATCH" in _codes(report)
    assert "AGGREGATE_FAILURE_COUNT_MISMATCH" in _codes(report)


def test_weak_dataset_fingerprint_is_warning(tmp_path: Path, write_bundle) -> None:
    bundle = write_bundle(tmp_path / "weak.lperf", weak_dataset=True)
    report = verify_bundle(bundle)
    assert report.status == VerificationStatus.VALID_WITH_WARNINGS
    assert _codes(report) == {"WEAK_DATASET_FINGERPRINT"}


def test_cli_verify_invalid_bundle_returns_two(valid_bundle: Path) -> None:
    (valid_bundle / "trials/0001/stderr.log").write_text("tamper", encoding="utf-8")
    result = runner.invoke(app, ["verify", str(valid_bundle)])
    assert result.exit_code == 2
    assert "INVALID" in result.stdout
    assert "CHECKSUM_MISMATCH" in result.stderr


def test_config_hash_is_semantic_not_yaml_order(valid_bundle: Path, refresh_checksums) -> None:
    config = valid_bundle / "config/algorithm.yaml"
    config.write_text("max_iterations: 20\nvoxel_size: 0.5\n", encoding="utf-8")
    refresh_checksums(valid_bundle)
    report = verify_bundle(valid_bundle)
    assert report.status == VerificationStatus.VALID


def test_missing_checksum_file_is_invalid(valid_bundle: Path) -> None:
    (valid_bundle / "checksums.sha256").unlink()
    report = verify_bundle(valid_bundle)
    assert "CHECKSUM_FILE_MISSING" in _codes(report)


def test_extra_numbered_trial_is_invalid(valid_bundle: Path, refresh_checksums) -> None:
    manifest_path = valid_bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    extra_dir = valid_bundle / "trials/0002"
    extra_dir.mkdir()
    (extra_dir / "trial.json").write_text(
        '{"exit_code":0,"schema_version":"lidarperf.trial.v1",'
        '"status":"success","timed_out":false,"trial_index":2}\n',
        encoding="utf-8",
    )
    manifest["file_inventory"].append("trials/0002/trial.json")
    manifest["file_inventory"].sort()
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    refresh_checksums(valid_bundle)
    report = verify_bundle(valid_bundle)
    assert "UNEXPECTED_TRIAL" in _codes(report)


def test_bundle_path_must_be_directory(tmp_path: Path) -> None:
    path = tmp_path / "not-a-bundle"
    path.write_text("file", encoding="utf-8")
    report = verify_bundle(path)
    assert report.status == VerificationStatus.INVALID
    assert _codes(report) == {"BUNDLE_NOT_DIRECTORY"}


def test_bundle_root_symlink_is_invalid(tmp_path: Path, write_bundle) -> None:
    target = write_bundle(tmp_path / "target.lperf")
    link = tmp_path / "linked.lperf"
    link.symlink_to(target, target_is_directory=True)
    report = verify_bundle(link)
    assert report.status == VerificationStatus.INVALID
    assert _codes(report) == {"BUNDLE_SYMLINK"}
