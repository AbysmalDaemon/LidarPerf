from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
import yaml

from lidarperf import __version__
from lidarperf.bundle import (
    AggregateRecord,
    ConformanceStatus,
    DatasetFingerprintClass,
    DatasetRecord,
    EnvironmentRecord,
    MethodRecord,
    MethodSourceRecord,
    MetricsRecord,
    ProtocolReference,
    ResourcesRecord,
    ResultBundleWriter,
    ResultManifestCore,
    TrialRecord,
    TrialStatus,
)
from lidarperf.spec import load_protocol, sha256_fingerprint
from lidarperf.spec.enums import MeasurementClass


def _dataset_digest(label: str = "synthetic-input") -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _write_bundle(root: Path, *, weak_dataset: bool = False) -> Path:
    protocol_source = Path("protocols/lo/se3_v1.yaml")
    resolved = load_protocol(protocol_source)
    protocol_text = protocol_source.read_text(encoding="utf-8")
    config_text = "voxel_size: 0.5\nmax_iterations: 20\n"
    config_hash = sha256_fingerprint(yaml.safe_load(config_text))
    dataset_digest = None if weak_dataset else _dataset_digest()

    writer = ResultBundleWriter(root)
    writer.write_text("protocol.yaml", protocol_text)
    writer.write_json(
        "method.json",
        MethodRecord(
            name="synthetic-identity",
            version="1",
            source=MethodSourceRecord(repository="https://example.invalid/method", commit="abc123"),
            config_sha256=config_hash,
            build={"python": "test"},
        ),
    )
    writer.write_json(
        "dataset.json",
        DatasetRecord(
            id="lidarperf/synthetic/test",
            provider="lidarperf",
            sequence="test",
            fingerprint_class=(
                DatasetFingerprintClass.WEAK if weak_dataset else DatasetFingerprintClass.EXACT
            ),
            content_sha256=dataset_digest,
            metadata={"fixture": True},
        ),
    )
    writer.write_json(
        "environment.json",
        EnvironmentRecord(
            measurement_class=MeasurementClass.EXPLORATORY,
            host={"platform": "test"},
            software={"lidarperf": __version__},
        ),
    )
    writer.write_json(
        "aggregate.json",
        AggregateRecord(successful_trials=1, failed_trials=0, metrics={}),
    )
    writer.write_text("config/algorithm.yaml", config_text)
    writer.write_json(
        "trials/0001/trial.json",
        TrialRecord(trial_index=1, status=TrialStatus.SUCCESS, exit_code=0),
    )
    writer.write_json("trials/0001/metrics.json", MetricsRecord(values={"ape_m": 0.0}))
    writer.write_json(
        "trials/0001/resources.json",
        ResourcesRecord(values={"wall_time_s": 1.0}),
    )
    writer.write_text("trials/0001/trajectory.tum", "0.000000000 0 0 0 0 0 0 1\n")
    writer.write_text("trials/0001/stdout.log", "")
    writer.write_text("trials/0001/stderr.log", "")
    writer.finalize(
        ResultManifestCore(
            lidarperf_version=__version__,
            result_id=UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"),
            created_at=datetime(2026, 9, 14, 10, 0, tzinfo=UTC),
            protocol=ProtocolReference(
                id=resolved.document.protocol.id,
                version=resolved.document.protocol.version,
                resolved_sha256=resolved.resolved_sha256,
            ),
            track=resolved.document.track,
            method_name="synthetic-identity",
            dataset_id="lidarperf/synthetic/test",
            dataset_content_sha256=dataset_digest,
            trial_count=1,
            measurement_class=MeasurementClass.EXPLORATORY,
            conformance_status=ConformanceStatus.CONFORMANT,
        )
    )
    return root


def _refresh_checksums(root: Path) -> None:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    lines = []
    for relative_path in manifest["file_inventory"]:
        digest = hashlib.sha256((root / relative_path).read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative_path}\n")
    (root / "checksums.sha256").write_text("".join(lines), encoding="utf-8", newline="\n")


@pytest.fixture
def valid_bundle(tmp_path: Path) -> Path:
    return _write_bundle(tmp_path / "valid.lperf")


@pytest.fixture
def write_bundle():
    return _write_bundle


@pytest.fixture
def refresh_checksums():
    return _refresh_checksums
