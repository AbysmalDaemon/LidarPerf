"""Data models for LidarPerf's deterministic synthetic conformance fixture."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictFrozenModel(BaseModel):
    """Base model used for immutable synthetic-fixture records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SyntheticFixtureConfig(StrictFrozenModel):
    """Configuration for a deterministic synthetic LiDAR sequence."""

    seed: int = 20260914
    pose_count: int = Field(default=240, ge=2, le=100_000)
    scan_rate_hz: float = Field(default=10.0, gt=0.0, le=1000.0)
    speed_mps: float = Field(default=1.0, gt=0.0, le=100.0)
    turn_radius_m: float = Field(default=20.0, gt=0.0, le=10_000.0)
    lidar_height_m: float = Field(default=1.5, gt=0.0, le=20.0)
    min_range_m: float = Field(default=0.5, ge=0.0)
    max_range_m: float = Field(default=30.0, gt=0.0)
    max_points_per_scan: int = Field(default=384, ge=1, le=100_000)
    noise_std_m: float = Field(default=0.0, ge=0.0, le=10.0)
    motion_distortion: bool = False

    @model_validator(mode="after")
    def validate_range_window(self) -> SyntheticFixtureConfig:
        """Require a non-empty LiDAR range interval."""

        if self.max_range_m <= self.min_range_m:
            raise ValueError("max_range_m must be greater than min_range_m")
        return self


class SyntheticPose(StrictFrozenModel):
    """Ground-truth body pose using LidarPerf's canonical T_W_B convention."""

    timestamp_ns: int = Field(ge=0)
    x_m: float
    y_m: float
    z_m: float
    qx: float
    qy: float
    qz: float
    qw: float


class SyntheticPoint(StrictFrozenModel):
    """One LiDAR return represented in the body frame at acquisition time."""

    x_m: float
    y_m: float
    z_m: float
    intensity: float = Field(ge=0.0, le=1.0)
    ring: int = Field(ge=0, le=255)
    time_offset_ns: int = Field(ge=0)
    landmark_id: int = Field(ge=0)


class SyntheticScan(StrictFrozenModel):
    """One synthetic LiDAR scan referenced to scan start."""

    scan_index: int = Field(ge=0)
    timestamp_ns: int = Field(ge=0)
    points: tuple[SyntheticPoint, ...]


class SyntheticFixture(StrictFrozenModel):
    """In-memory deterministic synthetic sequence and exact ground truth."""

    config: SyntheticFixtureConfig
    poses: tuple[SyntheticPose, ...]
    scans: tuple[SyntheticScan, ...]

    @model_validator(mode="after")
    def validate_lengths(self) -> SyntheticFixture:
        """Keep generated pose/scan counts consistent with the configuration."""

        if len(self.poses) != self.config.pose_count:
            raise ValueError("pose count does not match fixture configuration")
        if len(self.scans) != self.config.pose_count:
            raise ValueError("scan count does not match fixture configuration")
        return self


class SyntheticFixtureManifest(StrictFrozenModel):
    """Portable metadata written next to a generated synthetic fixture."""

    schema_version: Literal["lidarperf.synthetic.v1"] = "lidarperf.synthetic.v1"
    generator_version: Literal[1] = 1
    fixture_id_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    coordinate_convention: Literal["T_W_B"] = "T_W_B"
    quaternion_order: Literal["xyzw"] = "xyzw"
    timestamp_unit: Literal["int64_ns"] = "int64_ns"
    scan_timestamp_reference: Literal["scan_start"] = "scan_start"
    point_time_semantics: Literal["offset_from_scan_start"] = "offset_from_scan_start"
    point_coordinate_semantics: Literal["scan_start_body", "acquisition_body"]
    trajectory_model: Literal["constant_speed_circle"] = "constant_speed_circle"
    scene_model: Literal["planes_poles_boxes_v1"] = "planes_poles_boxes_v1"
    noise_model: Literal["hash_irwin_hall_6_v1"] = "hash_irwin_hall_6_v1"
    ground_truth_file: Literal["ground_truth.tum"] = "ground_truth.tum"
    scan_directory: Literal["scans"] = "scans"
    scan_index_file: Literal["scans/index.json"] = "scans/index.json"
    scan_file_format: Literal["jsonl"] = "jsonl"
    config: SyntheticFixtureConfig
    scan_count: int = Field(ge=1)
    total_point_count: int = Field(ge=0)
