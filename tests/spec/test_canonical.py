from __future__ import annotations

from lidarperf.spec import canonical_json_bytes, sha256_fingerprint


def test_mapping_order_does_not_change_fingerprint() -> None:
    left = {"b": 2, "a": {"z": 9, "y": 8}}
    right = {"a": {"y": 8, "z": 9}, "b": 2}

    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert sha256_fingerprint(left) == sha256_fingerprint(right)


def test_set_order_does_not_change_fingerprint() -> None:
    assert sha256_fingerprint({"sensors": {"lidar", "imu"}}) == sha256_fingerprint(
        {"sensors": {"imu", "lidar"}}
    )


def test_sequence_order_changes_fingerprint() -> None:
    assert sha256_fingerprint(["lidar", "imu"]) != sha256_fingerprint(["imu", "lidar"])
