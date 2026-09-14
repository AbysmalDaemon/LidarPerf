from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from lidarperf.synthetic import (
    SyntheticFixtureConfig,
    fixture_identity,
    generate_fixture,
    write_fixture,
)


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_constant_speed_arc_ground_truth() -> None:
    config = SyntheticFixtureConfig(
        pose_count=3,
        scan_rate_hz=2.0,
        speed_mps=2.0,
        turn_radius_m=10.0,
        max_points_per_scan=16,
    )
    fixture = generate_fixture(config)

    assert fixture.poses[0].timestamp_ns == 0
    assert fixture.poses[0].x_m == 0.0
    assert fixture.poses[0].y_m == 0.0
    assert fixture.poses[0].qw == 1.0

    time_s = 0.5
    yaw = config.speed_mps / config.turn_radius_m * time_s
    second = fixture.poses[1]
    assert second.timestamp_ns == 500_000_000
    assert second.x_m == pytest.approx(config.turn_radius_m * math.sin(yaw), abs=1e-12)
    assert second.y_m == pytest.approx(
        config.turn_radius_m * (1.0 - math.cos(yaw)),
        abs=1e-12,
    )
    assert second.qz == pytest.approx(math.sin(yaw / 2.0), abs=1e-12)
    assert second.qw == pytest.approx(math.cos(yaw / 2.0), abs=1e-12)


def test_fixture_identity_changes_with_semantic_configuration() -> None:
    baseline = SyntheticFixtureConfig(pose_count=4, max_points_per_scan=8)
    changed = baseline.model_copy(update={"motion_distortion": True})

    assert fixture_identity(baseline) == fixture_identity(baseline)
    assert fixture_identity(baseline) != fixture_identity(changed)


def test_fixture_is_bitwise_deterministic(tmp_path: Path) -> None:
    config = SyntheticFixtureConfig(
        seed=17,
        pose_count=5,
        scan_rate_hz=10.0,
        max_points_per_scan=24,
        noise_std_m=0.01,
        motion_distortion=True,
    )
    left = tmp_path / "left"
    right = tmp_path / "right"

    left_manifest = write_fixture(left, config)
    right_manifest = write_fixture(right, config)

    assert left_manifest == right_manifest
    assert _files(left) == _files(right)


def test_cross_version_golden_fixture_digest(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    config = SyntheticFixtureConfig(
        seed=42,
        pose_count=4,
        scan_rate_hz=7.0,
        speed_mps=2.5,
        turn_radius_m=9.0,
        max_points_per_scan=32,
        noise_std_m=0.005,
        motion_distortion=True,
    )
    write_fixture(output, config)

    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in output.rglob("*") if candidate.is_file()):
        digest.update(path.relative_to(output).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")

    assert digest.hexdigest() == "84f4b8eed79a92de4c2a84df57fca13402a7d83dfa92aec4b3ceec3ed948fa0a"


def test_motion_distortion_preserves_landmark_selection_but_changes_coordinates() -> None:
    base = SyntheticFixtureConfig(
        pose_count=3,
        scan_rate_hz=5.0,
        speed_mps=4.0,
        turn_radius_m=8.0,
        max_points_per_scan=64,
    )
    undistorted = generate_fixture(base)
    distorted = generate_fixture(base.model_copy(update={"motion_distortion": True}))

    undistorted_points = undistorted.scans[1].points
    distorted_points = distorted.scans[1].points

    assert [point.landmark_id for point in undistorted_points] == [
        point.landmark_id for point in distorted_points
    ]
    assert [point.time_offset_ns for point in undistorted_points] == [
        point.time_offset_ns for point in distorted_points
    ]
    assert any(
        (plain.x_m, plain.y_m, plain.z_m) != (rolling.x_m, rolling.y_m, rolling.z_m)
        for plain, rolling in zip(undistorted_points, distorted_points, strict=True)
        if plain.time_offset_ns > 0
    )


def test_noise_changes_points_but_not_ground_truth() -> None:
    first = generate_fixture(
        SyntheticFixtureConfig(seed=1, pose_count=3, max_points_per_scan=32, noise_std_m=0.02)
    )
    second = generate_fixture(
        SyntheticFixtureConfig(seed=2, pose_count=3, max_points_per_scan=32, noise_std_m=0.02)
    )

    assert first.poses == second.poses
    assert first.scans[1].points != second.scans[1].points


def test_written_fixture_has_declared_time_semantics(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    config = SyntheticFixtureConfig(pose_count=4, max_points_per_scan=12)
    manifest = write_fixture(output, config)
    payload = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == "lidarperf.synthetic.v1"
    assert payload["coordinate_convention"] == "T_W_B"
    assert payload["scan_timestamp_reference"] == "scan_start"
    assert payload["point_time_semantics"] == "offset_from_scan_start"
    assert payload["point_coordinate_semantics"] == "scan_start_body"
    assert payload["noise_model"] == "hash_irwin_hall_6_v1"
    assert payload["fixture_id_sha256"] == manifest.fixture_id_sha256
    assert len(list((output / "scans").glob("*.jsonl"))) == config.pose_count
    index_payload = json.loads((output / "scans" / "index.json").read_text(encoding="utf-8"))
    assert [entry["timestamp_ns"] for entry in index_payload] == [
        pose.timestamp_ns for pose in generate_fixture(config).poses
    ]


def test_distorted_manifest_declares_acquisition_frame(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    manifest = write_fixture(
        output,
        SyntheticFixtureConfig(
            pose_count=2,
            max_points_per_scan=4,
            motion_distortion=True,
        ),
    )

    assert manifest.point_coordinate_semantics == "acquisition_body"


def test_scan_points_are_time_ordered_and_within_scan_period() -> None:
    config = SyntheticFixtureConfig(pose_count=3, scan_rate_hz=20.0, max_points_per_scan=128)
    fixture = generate_fixture(config)
    scan_period_ns = int(round(1_000_000_000 / config.scan_rate_hz))

    for scan in fixture.scans:
        offsets = [point.time_offset_ns for point in scan.points]
        assert offsets == sorted(offsets)
        assert all(0 <= offset < scan_period_ns for offset in offsets)


def test_output_directory_must_be_empty(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    output.mkdir()
    (output / "existing.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="not empty"):
        write_fixture(output, SyntheticFixtureConfig(pose_count=2, max_points_per_scan=4))


def test_output_path_cannot_be_an_existing_file(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="not a directory"):
        write_fixture(output, SyntheticFixtureConfig(pose_count=2, max_points_per_scan=4))


def test_invalid_range_window_is_rejected() -> None:
    with pytest.raises(ValidationError, match="max_range_m must be greater"):
        SyntheticFixtureConfig(min_range_m=10.0, max_range_m=10.0)
