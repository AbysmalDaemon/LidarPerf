from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from lidarperf.bundle import (
    BundleWriteError,
    DatasetFingerprintClass,
    DatasetRecord,
    ResultBundleWriter,
    ResultManifestCore,
    TrialRecord,
    TrialStatus,
)


def test_exact_dataset_requires_content_hash() -> None:
    with pytest.raises(ValidationError, match="content_sha256"):
        DatasetRecord(
            id="dataset",
            provider="provider",
            sequence="sequence",
            fingerprint_class=DatasetFingerprintClass.EXACT,
        )


def test_success_trial_requires_zero_exit_code() -> None:
    with pytest.raises(ValidationError, match="exit_code=0"):
        TrialRecord(trial_index=1, status=TrialStatus.SUCCESS, exit_code=1)


def test_manifest_core_requires_timezone() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        ResultManifestCore.model_validate(
            {
                "lidarperf_version": "0.0.0",
                "result_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                "created_at": datetime(2026, 9, 14, 10, 0),
                "protocol": {
                    "id": "lidarperf/lo-se3",
                    "version": 1,
                    "resolved_sha256": "0" * 64,
                },
                "track": "lo",
                "method_name": "method",
                "dataset_id": "dataset",
                "dataset_content_sha256": "1" * 64,
                "trial_count": 1,
                "measurement_class": "exploratory",
                "conformance_status": "conformant",
            }
        )


def test_writer_refuses_nonempty_directory(tmp_path: Path) -> None:
    root = tmp_path / "bundle.lperf"
    root.mkdir()
    (root / "existing.txt").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(BundleWriteError, match="not empty"):
        ResultBundleWriter(root)
    assert (root / "existing.txt").read_text(encoding="utf-8") == "do not overwrite"


def test_writer_rejects_path_traversal(tmp_path: Path) -> None:
    writer = ResultBundleWriter(tmp_path / "bundle.lperf")
    with pytest.raises(BundleWriteError, match="unsafe"):
        writer.write_text("../escape.txt", "bad")
    with pytest.raises(BundleWriteError, match="unsafe"):
        writer.write_text("nested/../escape.txt", "bad")
    with pytest.raises(BundleWriteError, match="unsafe"):
        writer.write_text("nested\\windows.txt", "bad")
    with pytest.raises(BundleWriteError, match="unsafe"):
        writer.write_text("nested/./dot.txt", "bad")


def test_writer_reserves_manifest_and_checksum_paths(tmp_path: Path) -> None:
    writer = ResultBundleWriter(tmp_path / "bundle.lperf")
    with pytest.raises(BundleWriteError, match="reserved"):
        writer.write_text("manifest.json", "{}")
    with pytest.raises(BundleWriteError, match="reserved"):
        writer.write_text("checksums.sha256", "")


def test_writer_blocks_writes_after_finalize(valid_bundle: Path) -> None:
    # A new writer cannot reopen a non-empty finalized bundle. This is the public immutability rule.
    with pytest.raises(BundleWriteError, match="not empty"):
        ResultBundleWriter(valid_bundle)


def test_writer_rejects_symlink_root(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "bundle.lperf"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(BundleWriteError, match="symlink"):
        ResultBundleWriter(link)


def test_writer_never_overwrites_file_created_after_initialization(tmp_path: Path) -> None:
    root = tmp_path / "bundle.lperf"
    writer = ResultBundleWriter(root)
    path = root / "payload.txt"
    path.write_text("external", encoding="utf-8")
    with pytest.raises(BundleWriteError, match="already exists"):
        writer.write_text("payload.txt", "replacement")
    assert path.read_text(encoding="utf-8") == "external"
