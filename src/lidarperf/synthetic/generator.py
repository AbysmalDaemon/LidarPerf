"""Deterministic synthetic LiDAR fixture generation."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from .models import (
    SyntheticFixture,
    SyntheticFixtureConfig,
    SyntheticFixtureManifest,
    SyntheticPoint,
    SyntheticPose,
    SyntheticScan,
)

_TWO_PI = 2.0 * math.pi
_FLOAT_DIGITS = 12
_IRWIN_HALL_6_STD = 0.7071067811865476
_UINT32_MAX = 4_294_967_295


@dataclass(frozen=True, slots=True)
class _Landmark:
    landmark_id: int
    x_m: float
    y_m: float
    z_m: float
    intensity: float
    ring: int


def _stable_float(value: float) -> float:
    """Round generated values so serialized fixtures are stable across CPython versions."""

    rounded = round(value, _FLOAT_DIGITS)
    if rounded == 0.0:
        return 0.0
    return rounded


def _pose_at_seconds(time_s: float, config: SyntheticFixtureConfig) -> SyntheticPose:
    """Evaluate the exact constant-speed circular ground-truth trajectory."""

    omega = config.speed_mps / config.turn_radius_m
    yaw = omega * time_s
    x_m = config.turn_radius_m * math.sin(yaw)
    y_m = config.turn_radius_m * (1.0 - math.cos(yaw))
    half_yaw = 0.5 * yaw

    return SyntheticPose(
        timestamp_ns=max(0, int(round(time_s * 1_000_000_000))),
        x_m=_stable_float(x_m),
        y_m=_stable_float(y_m),
        z_m=_stable_float(config.lidar_height_m),
        qx=0.0,
        qy=0.0,
        qz=_stable_float(math.sin(half_yaw)),
        qw=_stable_float(math.cos(half_yaw)),
    )


def _yaw_from_pose(pose: SyntheticPose) -> float:
    """Recover yaw from a z-axis-only quaternion."""

    return 2.0 * math.atan2(pose.qz, pose.qw)


def _world_to_body(
    landmark: _Landmark,
    pose: SyntheticPose,
) -> tuple[float, float, float]:
    """Transform a static world landmark into the body frame for T_W_B."""

    yaw = _yaw_from_pose(pose)
    cosine = math.cos(yaw)
    sine = math.sin(yaw)
    dx = landmark.x_m - pose.x_m
    dy = landmark.y_m - pose.y_m
    dz = landmark.z_m - pose.z_m

    return (
        cosine * dx + sine * dy,
        -sine * dx + cosine * dy,
        dz,
    )


def _scene_landmarks() -> tuple[_Landmark, ...]:
    """Build a static scene containing ground, walls, poles, and box corners."""

    raw: list[tuple[float, float, float, float, int]] = []

    # Ground plane: intentionally sparse so later frame-convention tests remain cheap.
    for x_index in range(-3, 19):
        x_m = 2.0 * x_index
        for y_index in range(-6, 7):
            y_m = 2.0 * y_index
            raw.append((x_m, y_m, 0.0, 0.25, (x_index - y_index) % 64))

    # Parallel walls create strong planar structure.
    for wall_y in (-10.0, 10.0):
        for x_index in range(-4, 25):
            x_m = 1.5 * x_index
            for z_m in (0.5, 1.5, 2.5, 3.5):
                raw.append((x_m, wall_y, z_m, 0.65, (x_index + int(z_m * 10)) % 64))

    # Cylindrical poles provide repeated vertical structure.
    pole_centers = ((5.0, 4.0), (12.0, -3.0), (18.0, 6.0), (25.0, -6.0), (31.0, 2.0))
    for pole_index, (center_x, center_y) in enumerate(pole_centers):
        for z_index in range(1, 11):
            z_m = 0.4 * z_index
            for angle_index in range(8):
                angle = _TWO_PI * angle_index / 8.0
                raw.append(
                    (
                        center_x + 0.15 * math.cos(angle),
                        center_y + 0.15 * math.sin(angle),
                        z_m,
                        0.9,
                        (pole_index * 11 + z_index) % 64,
                    )
                )

    # A few boxes break the scene's planar/cylindrical symmetry.
    for center_x, center_y, size in ((8.0, -6.0, 1.0), (21.0, 4.5, 1.5), (29.0, -1.5, 0.8)):
        half = 0.5 * size
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                for z_m in (0.0, size):
                    raw.append((center_x + sx * half, center_y + sy * half, z_m, 0.75, 32))

    return tuple(
        _Landmark(
            landmark_id=index,
            x_m=_stable_float(x_m),
            y_m=_stable_float(y_m),
            z_m=_stable_float(z_m),
            intensity=intensity,
            ring=ring,
        )
        for index, (x_m, y_m, z_m, intensity, ring) in enumerate(raw)
    )


def _time_offset_ns(x_m: float, y_m: float, scan_period_ns: int) -> int:
    """Map scan-start azimuth deterministically onto a 360-degree acquisition interval."""

    azimuth = math.atan2(y_m, x_m) % _TWO_PI
    fraction = azimuth / _TWO_PI
    return min(scan_period_ns - 1, int(fraction * scan_period_ns))


def _point_noise(
    seed: int,
    scan_index: int,
    landmark_id: int,
    std_m: float,
) -> tuple[float, float, float]:
    """Generate order-independent deterministic zero-mean noise with unit variance."""

    if std_m == 0.0:
        return (0.0, 0.0, 0.0)

    samples: list[float] = []
    for axis in range(3):
        payload = f"{seed}:{scan_index}:{landmark_id}:{axis}".encode("ascii")
        digest = hashlib.sha256(payload).digest()
        uniforms = [
            int.from_bytes(digest[offset : offset + 4], "big") / _UINT32_MAX
            for offset in range(0, 24, 4)
        ]
        unit_sample = (sum(uniforms) - 3.0) / _IRWIN_HALL_6_STD
        samples.append(unit_sample * std_m)

    return (samples[0], samples[1], samples[2])


def _uniform_subsample(points: list[SyntheticPoint], limit: int) -> tuple[SyntheticPoint, ...]:
    """Keep an azimuth/time-distributed deterministic subset without random sampling."""

    if len(points) <= limit:
        return tuple(points)

    step = len(points) / limit
    return tuple(points[int(index * step)] for index in range(limit))


def _scan_for_pose(
    scan_index: int,
    pose: SyntheticPose,
    landmarks: tuple[_Landmark, ...],
    config: SyntheticFixtureConfig,
    scan_period_ns: int,
) -> SyntheticScan:
    """Generate one scan using scan-start visibility and optional rolling-scan distortion."""

    candidates: list[tuple[_Landmark, tuple[float, float, float], int]] = []
    for landmark in landmarks:
        reference_xyz = _world_to_body(landmark, pose)
        range_m = math.sqrt(sum(axis * axis for axis in reference_xyz))
        if not (config.min_range_m <= range_m <= config.max_range_m):
            continue
        offset_ns = _time_offset_ns(reference_xyz[0], reference_xyz[1], scan_period_ns)
        candidates.append((landmark, reference_xyz, offset_ns))

    points: list[SyntheticPoint] = []
    for landmark, reference_xyz, offset_ns in candidates:
        if config.motion_distortion and offset_ns:
            acquisition_s = (pose.timestamp_ns + offset_ns) / 1_000_000_000
            point_pose = _pose_at_seconds(acquisition_s, config)
            point_xyz = _world_to_body(landmark, point_pose)
        else:
            point_xyz = reference_xyz

        noise = _point_noise(config.seed, scan_index, landmark.landmark_id, config.noise_std_m)
        points.append(
            SyntheticPoint(
                x_m=_stable_float(point_xyz[0] + noise[0]),
                y_m=_stable_float(point_xyz[1] + noise[1]),
                z_m=_stable_float(point_xyz[2] + noise[2]),
                intensity=landmark.intensity,
                ring=landmark.ring,
                time_offset_ns=offset_ns,
                landmark_id=landmark.landmark_id,
            )
        )

    points.sort(key=lambda point: (point.time_offset_ns, point.landmark_id))
    return SyntheticScan(
        scan_index=scan_index,
        timestamp_ns=pose.timestamp_ns,
        points=_uniform_subsample(points, config.max_points_per_scan),
    )


def generate_fixture(config: SyntheticFixtureConfig | None = None) -> SyntheticFixture:
    """Generate a deterministic in-memory fixture from an explicit configuration."""

    resolved = config or SyntheticFixtureConfig()
    scan_period_ns = int(round(1_000_000_000 / resolved.scan_rate_hz))
    landmarks = _scene_landmarks()
    poses = tuple(
        _pose_at_seconds(index / resolved.scan_rate_hz, resolved)
        for index in range(resolved.pose_count)
    )
    scans = tuple(
        _scan_for_pose(index, pose, landmarks, resolved, scan_period_ns)
        for index, pose in enumerate(poses)
    )
    return SyntheticFixture(config=resolved, poses=poses, scans=scans)


def fixture_identity(config: SyntheticFixtureConfig) -> str:
    """Return a stable identity for generator version 1 plus the canonical configuration."""

    payload = {
        "config": config.model_dump(mode="json"),
        "generator_version": 1,
        "schema_version": "lidarperf.synthetic.v1",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _pose_tum_line(pose: SyntheticPose) -> str:
    """Serialize one ground-truth pose in TUM trajectory format."""

    timestamp_s = pose.timestamp_ns / 1_000_000_000
    return (
        f"{timestamp_s:.9f} {pose.x_m:.12f} {pose.y_m:.12f} {pose.z_m:.12f} "
        f"{pose.qx:.12f} {pose.qy:.12f} {pose.qz:.12f} {pose.qw:.12f}\n"
    )


def _point_json_line(point: SyntheticPoint) -> str:
    """Serialize a point using sorted compact JSON for bitwise-stable fixtures."""

    return json.dumps(
        point.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"


def write_fixture(
    output_dir: str | Path,
    config: SyntheticFixtureConfig | None = None,
) -> SyntheticFixtureManifest:
    """Generate a fixture and write a deterministic directory representation."""

    resolved_output = Path(output_dir)
    if resolved_output.exists() and not resolved_output.is_dir():
        raise FileExistsError(f"output path exists and is not a directory: {resolved_output}")
    if resolved_output.exists() and any(resolved_output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {resolved_output}")

    fixture = generate_fixture(config)
    scans_dir = resolved_output / "scans"
    scans_dir.mkdir(parents=True, exist_ok=True)

    (resolved_output / "ground_truth.tum").write_text(
        "".join(_pose_tum_line(pose) for pose in fixture.poses),
        encoding="utf-8",
        newline="\n",
    )

    total_point_count = 0
    scan_index: list[dict[str, int | str]] = []
    for scan in fixture.scans:
        total_point_count += len(scan.points)
        filename = f"{scan.scan_index:06d}.jsonl"
        scan_path = scans_dir / filename
        scan_path.write_text(
            "".join(_point_json_line(point) for point in scan.points),
            encoding="utf-8",
            newline="\n",
        )
        scan_index.append(
            {
                "filename": filename,
                "point_count": len(scan.points),
                "scan_index": scan.scan_index,
                "timestamp_ns": scan.timestamp_ns,
            }
        )

    (scans_dir / "index.json").write_text(
        json.dumps(scan_index, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest = SyntheticFixtureManifest(
        fixture_id_sha256=fixture_identity(fixture.config),
        point_coordinate_semantics=(
            "acquisition_body" if fixture.config.motion_distortion else "scan_start_body"
        ),
        config=fixture.config,
        scan_count=len(fixture.scans),
        total_point_count=total_point_count,
    )
    manifest_payload = json.dumps(
        manifest.model_dump(mode="json"),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    (resolved_output / "manifest.json").write_text(
        manifest_payload,
        encoding="utf-8",
        newline="\n",
    )
    return manifest
