"""Normative enumerations used by LidarPerf benchmark protocols."""

from __future__ import annotations

from enum import StrEnum


class Track(StrEnum):
    """Estimator track supported by the v0.1 protocol schema."""

    LO = "lo"
    LIO = "lio"


class Sensor(StrEnum):
    """Runtime information sources whose use can affect benchmark conformance."""

    LIDAR = "lidar"
    IMU = "imu"
    CAMERA = "camera"
    WHEEL_ODOMETRY = "wheel_odometry"
    GNSS = "gnss"
    MAGNETOMETER = "magnetometer"
    EXTERNAL_LOCALIZATION = "external_localization"
    PREBUILT_MAP = "prebuilt_map"
    GROUND_TRUTH = "ground_truth"
    PRECOMPUTED_MOTION = "precomputed_motion"


class TemporalMode(StrEnum):
    """Estimator temporal semantics."""

    ONLINE_CAUSAL = "online_causal"
    ONLINE_FIXED_LAG = "online_fixed_lag"
    OFFLINE_NONCAUSAL = "offline_noncausal"


class TimestampAssociationMode(StrEnum):
    """How estimator and reference trajectory timestamps are associated."""

    EXACT = "exact"
    NEAREST = "nearest"
    INTERPOLATE_REFERENCE = "interpolate_reference"


class ScanTimestampReference(StrEnum):
    """Reference point for a LiDAR scan timestamp."""

    SCAN_START = "scan_start"
    SCAN_MID = "scan_mid"
    SCAN_END = "scan_end"
    UNKNOWN = "unknown"


class AlignmentMode(StrEnum):
    """Trajectory alignment allowed by an evaluation profile."""

    NONE = "none"
    ORIGIN = "origin"
    SE3 = "se3"


class TimingScope(StrEnum):
    """Performance timing boundary."""

    COMPUTE = "compute"
    PIPELINE = "pipeline"
    END_TO_END = "end_to_end"


class MeasurementClass(StrEnum):
    """Strength of the execution environment and repetition evidence."""

    EXPLORATORY = "exploratory"
    CONTROLLED = "controlled"
    PUBLICATION = "publication"


class TuningClass(StrEnum):
    """Granularity at which estimator configuration may be selected."""

    FROZEN = "frozen"
    DATASET = "dataset"
    SEQUENCE = "sequence"


class TuningSource(StrEnum):
    """Origin of an estimator configuration."""

    UPSTREAM_DEFAULT = "upstream_default"
    UPSTREAM_RECOMMENDED = "upstream_recommended"
    AUTHOR_PROVIDED = "author_provided"
    BENCHMARK_TUNED = "benchmark_tuned"
    CUSTOM = "custom"


class PreprocessingOwner(StrEnum):
    """Owner of a preprocessing operation."""

    DATASET = "dataset"
    BENCHMARK = "benchmark"
    ALGORITHM = "algorithm"
    NONE = "none"


class MotionCompensationInputState(StrEnum):
    """Whether the estimator input has already been motion compensated."""

    RAW = "raw"
    PRE_DESKEWED = "pre_deskewed"
    UNKNOWN = "unknown"


class MotionSource(StrEnum):
    """Motion source used to deskew a LiDAR scan."""

    NONE = "none"
    CONSTANT_VELOCITY = "constant_velocity"
    IMU = "imu"
    OTHER = "other"


class CachePolicy(StrEnum):
    """Dataset I/O cache policy for a benchmark trial."""

    WARM = "warm"
    COLD = "cold"
    UNCONTROLLED = "uncontrolled"
    NOT_APPLICABLE = "not_applicable"
