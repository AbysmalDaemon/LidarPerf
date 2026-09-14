"""Internal consistency and integrity verification for LidarPerf result bundles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from lidarperf.spec import ProtocolLoadError, load_protocol, sha256_fingerprint

from .models import (
    AggregateRecord,
    DatasetFingerprintClass,
    DatasetRecord,
    EnvironmentRecord,
    MethodRecord,
    MetricsRecord,
    ResourcesRecord,
    ResultManifest,
    TrialRecord,
    TrialStatus,
)

_REQUIRED_TOP_LEVEL = {
    "manifest.json",
    "protocol.yaml",
    "method.json",
    "dataset.json",
    "environment.json",
    "aggregate.json",
    "config/algorithm.yaml",
}
_REQUIRED_TRIAL_FILES = (
    "trial.json",
    "metrics.json",
    "resources.json",
    "trajectory.tum",
    "stdout.log",
    "stderr.log",
)


class VerificationStatus(StrEnum):
    """Overall verifier status."""

    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID WITH WARNINGS"
    INVALID = "INVALID"


class IssueSeverity(StrEnum):
    """Severity of a verification issue."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class VerificationIssue:
    """One machine-readable verifier finding."""

    severity: IssueSeverity
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Final verification result plus all findings."""

    status: VerificationStatus
    issues: tuple[VerificationIssue, ...]

    @property
    def valid(self) -> bool:
        return self.status != VerificationStatus.INVALID


class _Collector:
    def __init__(self) -> None:
        self.issues: list[VerificationIssue] = []

    def error(self, code: str, message: str) -> None:
        self.issues.append(VerificationIssue(IssueSeverity.ERROR, code, message))

    def warn(self, code: str, message: str) -> None:
        self.issues.append(VerificationIssue(IssueSeverity.WARNING, code, message))

    def report(self) -> VerificationReport:
        if any(issue.severity == IssueSeverity.ERROR for issue in self.issues):
            status = VerificationStatus.INVALID
        elif self.issues:
            status = VerificationStatus.VALID_WITH_WARNINGS
        else:
            status = VerificationStatus.VALID
        return VerificationReport(status=status, issues=tuple(self.issues))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, model: type[Any], collector: _Collector, code: str) -> Any | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return model.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        collector.error(code, f"{path.name}: {exc}")
        return None


def _parse_checksums(path: Path, collector: _Collector) -> dict[str, str]:
    checksums: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        collector.error("CHECKSUM_FILE_READ", str(exc))
        return checksums

    for line_number, line in enumerate(lines, start=1):
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            collector.error(
                "CHECKSUM_FORMAT",
                f"checksums.sha256 line {line_number} is not '<sha256>  <path>'",
            )
            continue
        digest, relative_path = parts
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            collector.error("CHECKSUM_FORMAT", f"invalid SHA-256 on line {line_number}")
            continue
        if relative_path in checksums:
            collector.error("CHECKSUM_DUPLICATE", f"duplicate checksum entry: {relative_path}")
            continue
        checksums[relative_path] = digest
    return checksums


def _actual_payload_files(root: Path, collector: _Collector) -> set[str]:
    payloads: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            collector.error(
                "SYMLINK_FORBIDDEN",
                f"bundle contains symlink: {path.relative_to(root)}",
            )
            continue
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative != "checksums.sha256":
                payloads.add(relative)
    return payloads


def _verify_checksums(
    root: Path,
    manifest: ResultManifest,
    collector: _Collector,
) -> None:
    checksum_path = root / "checksums.sha256"
    if not checksum_path.is_file():
        collector.error("CHECKSUM_FILE_MISSING", "checksums.sha256 is required")
        return

    checksums = _parse_checksums(checksum_path, collector)
    expected_paths = set(manifest.file_inventory)
    if set(checksums) != expected_paths:
        missing = sorted(expected_paths - set(checksums))
        extra = sorted(set(checksums) - expected_paths)
        if missing:
            collector.error("CHECKSUM_ENTRY_MISSING", f"missing checksum entries: {missing}")
        if extra:
            collector.error("CHECKSUM_ENTRY_EXTRA", f"undeclared checksum entries: {extra}")

    for relative_path in sorted(expected_paths & set(checksums)):
        path = root / relative_path
        if not path.is_file() or path.is_symlink():
            collector.error("PAYLOAD_MISSING", f"missing regular payload file: {relative_path}")
            continue
        actual = _sha256_file(path)
        if actual != checksums[relative_path]:
            collector.error("CHECKSUM_MISMATCH", f"checksum mismatch: {relative_path}")


def _fingerprint_config(path: Path, collector: _Collector) -> str | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return sha256_fingerprint(data)
    except (OSError, yaml.YAMLError, ValueError, TypeError) as exc:
        collector.error("CONFIG_PARSE", f"cannot canonicalize algorithm config: {exc}")
        return None


def verify_bundle(bundle_dir: str | Path) -> VerificationReport:
    """Verify a result bundle's schema, provenance links, inventory, and SHA-256 integrity."""

    root = Path(bundle_dir)
    collector = _Collector()
    if root.is_symlink():
        collector.error("BUNDLE_SYMLINK", f"bundle path must not be a symlink: {root}")
        return collector.report()
    if not root.is_dir():
        collector.error("BUNDLE_NOT_DIRECTORY", f"bundle path is not a directory: {root}")
        return collector.report()

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        collector.error("MANIFEST_MISSING", "manifest.json is required")
        return collector.report()
    manifest = _load_json(manifest_path, ResultManifest, collector, "MANIFEST_INVALID")
    if manifest is None:
        return collector.report()

    actual_payloads = _actual_payload_files(root, collector)
    declared_payloads = set(manifest.file_inventory)
    if actual_payloads != declared_payloads:
        missing = sorted(declared_payloads - actual_payloads)
        extra = sorted(actual_payloads - declared_payloads)
        if missing:
            collector.error("INVENTORY_MISSING", f"declared payload files missing: {missing}")
        if extra:
            collector.error("INVENTORY_EXTRA", f"undeclared payload files present: {extra}")

    missing_top_level = sorted(_REQUIRED_TOP_LEVEL - declared_payloads)
    if missing_top_level:
        collector.error("REQUIRED_FILE_MISSING", f"required payloads missing: {missing_top_level}")

    _verify_checksums(root, manifest, collector)

    protocol_path = root / "protocol.yaml"
    if protocol_path.is_file():
        try:
            resolved = load_protocol(protocol_path)
            if resolved.document.protocol.id != manifest.protocol.id:
                collector.error(
                    "PROTOCOL_ID_MISMATCH",
                    "manifest protocol id differs from protocol.yaml",
                )
            if resolved.document.protocol.version != manifest.protocol.version:
                collector.error(
                    "PROTOCOL_VERSION_MISMATCH",
                    "manifest protocol version differs from protocol.yaml",
                )
            if resolved.resolved_sha256 != manifest.protocol.resolved_sha256:
                collector.error(
                    "PROTOCOL_HASH_MISMATCH",
                    "manifest protocol hash differs from resolved protocol.yaml",
                )
            if resolved.document.track != manifest.track:
                collector.error("TRACK_MISMATCH", "manifest track differs from protocol.yaml")
        except ProtocolLoadError as exc:
            collector.error("PROTOCOL_INVALID", str(exc))

    method = _load_json(root / "method.json", MethodRecord, collector, "METHOD_INVALID")
    dataset = _load_json(root / "dataset.json", DatasetRecord, collector, "DATASET_INVALID")
    environment = _load_json(
        root / "environment.json", EnvironmentRecord, collector, "ENVIRONMENT_INVALID"
    )
    aggregate = _load_json(root / "aggregate.json", AggregateRecord, collector, "AGGREGATE_INVALID")

    if method is not None:
        if method.name != manifest.method_name:
            collector.error("METHOD_NAME_MISMATCH", "manifest method_name differs from method.json")
        config_path = root / method.config_file
        if not config_path.is_file():
            collector.error("CONFIG_MISSING", f"method config is missing: {method.config_file}")
        else:
            actual_config_hash = _fingerprint_config(config_path, collector)
            if actual_config_hash is not None and actual_config_hash != method.config_sha256:
                collector.error(
                    "CONFIG_HASH_MISMATCH",
                    "algorithm config fingerprint does not match",
                )

    if dataset is not None:
        if dataset.id != manifest.dataset_id:
            collector.error("DATASET_ID_MISMATCH", "manifest dataset_id differs from dataset.json")
        if dataset.content_sha256 != manifest.dataset_content_sha256:
            collector.error(
                "DATASET_HASH_MISMATCH",
                "manifest dataset content hash differs from dataset.json",
            )
        if dataset.fingerprint_class == DatasetFingerprintClass.WEAK:
            collector.warn("WEAK_DATASET_FINGERPRINT", "dataset identity is not content-exact")

    if environment is not None and environment.measurement_class != manifest.measurement_class:
        collector.error(
            "MEASUREMENT_CLASS_MISMATCH",
            "manifest measurement_class differs from environment.json",
        )

    expected_trial_records = {
        f"trials/{trial_index:04d}/trial.json"
        for trial_index in range(1, manifest.trial_count + 1)
    }
    declared_trial_records = {
        path
        for path in declared_payloads
        if path.startswith("trials/") and path.endswith("/trial.json")
    }
    unexpected_trial_records = sorted(declared_trial_records - expected_trial_records)
    if unexpected_trial_records:
        collector.error(
            "UNEXPECTED_TRIAL",
            f"trial records exceed manifest trial_count: {unexpected_trial_records}",
        )

    successful_trials = 0
    failed_trials = 0
    for trial_index in range(1, manifest.trial_count + 1):
        directory = f"trials/{trial_index:04d}"
        for filename in _REQUIRED_TRIAL_FILES:
            relative_path = f"{directory}/{filename}"
            if relative_path not in declared_payloads:
                collector.error(
                    "TRIAL_FILE_MISSING",
                    f"required trial payload missing: {relative_path}",
                )

        trial = _load_json(root / directory / "trial.json", TrialRecord, collector, "TRIAL_INVALID")
        _load_json(root / directory / "metrics.json", MetricsRecord, collector, "METRICS_INVALID")
        _load_json(
            root / directory / "resources.json", ResourcesRecord, collector, "RESOURCES_INVALID"
        )
        if trial is not None:
            if trial.trial_index != trial_index:
                collector.error(
                    "TRIAL_INDEX_MISMATCH",
                    f"{directory}/trial.json has trial_index={trial.trial_index}",
                )
            if trial.status == TrialStatus.SUCCESS:
                successful_trials += 1
            else:
                failed_trials += 1

    if aggregate is not None:
        if aggregate.successful_trials != successful_trials:
            collector.error(
                "AGGREGATE_SUCCESS_COUNT_MISMATCH",
                "aggregate successful_trials does not match trial records",
            )
        if aggregate.failed_trials != failed_trials:
            collector.error(
                "AGGREGATE_FAILURE_COUNT_MISMATCH",
                "aggregate failed_trials does not match trial records",
            )
        if aggregate.successful_trials + aggregate.failed_trials != manifest.trial_count:
            collector.error(
                "AGGREGATE_TRIAL_COUNT_MISMATCH",
                "aggregate trial counts do not match manifest trial_count",
            )

    return collector.report()
