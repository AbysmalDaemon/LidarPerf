"""Core in-memory trajectory types used by LidarPerf evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


class TrajectoryError(ValueError):
    """Base error for trajectory parsing, validation, association, or metrics."""


class TrajectoryFormatError(TrajectoryError):
    """Raised when a serialized trajectory cannot be parsed unambiguously."""


class TrajectoryValidationError(TrajectoryError):
    """Raised when structurally invalid trajectory data reaches an evaluator."""

    def __init__(self, message: str, report: TrajectoryValidationReport) -> None:
        super().__init__(message)
        self.report = report


class TrajectoryAssociationError(TrajectoryError):
    """Raised when a protocol cannot associate any usable trajectory poses."""


class TrajectoryMetricError(TrajectoryError):
    """Raised when a requested metric has undefined or underdetermined semantics."""


def _readonly_array(value: object, *, dtype: np.dtype, ndim: int, name: str) -> NDArray:
    array = np.asarray(value, dtype=dtype)
    if array.ndim != ndim:
        raise ValueError(f"{name} must have {ndim} dimensions, got shape {array.shape}")
    array = np.array(array, dtype=dtype, copy=True)
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True)
class Trajectory:
    """Canonical ``T_W_B`` trajectory with int64-nanosecond timestamps.

    Shape and storage invariants are enforced here. Scientific validity (finite
    poses, unit quaternions, timestamp monotonicity) is deliberately checked by
    :func:`validate_trajectory` so invalid poses can be counted and reported
    instead of disappearing during parsing.
    """

    timestamps_ns: IntArray
    positions_m: FloatArray
    quaternions_xyzw: FloatArray
    body_frame: str = "body"

    def __post_init__(self) -> None:
        timestamps = _readonly_array(
            self.timestamps_ns,
            dtype=np.dtype(np.int64),
            ndim=1,
            name="timestamps_ns",
        )
        positions = _readonly_array(
            self.positions_m,
            dtype=np.dtype(np.float64),
            ndim=2,
            name="positions_m",
        )
        quaternions = _readonly_array(
            self.quaternions_xyzw,
            dtype=np.dtype(np.float64),
            ndim=2,
            name="quaternions_xyzw",
        )
        count = timestamps.shape[0]
        if positions.shape != (count, 3):
            raise ValueError(f"positions_m must have shape ({count}, 3), got {positions.shape}")
        if quaternions.shape != (count, 4):
            raise ValueError(
                f"quaternions_xyzw must have shape ({count}, 4), got {quaternions.shape}"
            )
        if not self.body_frame.strip():
            raise ValueError("body_frame must be non-empty")
        object.__setattr__(self, "timestamps_ns", timestamps)
        object.__setattr__(self, "positions_m", positions)
        object.__setattr__(self, "quaternions_xyzw", quaternions)
        object.__setattr__(self, "body_frame", self.body_frame.strip())

    def __len__(self) -> int:
        return int(self.timestamps_ns.shape[0])

    @property
    def start_ns(self) -> int | None:
        return int(self.timestamps_ns[0]) if len(self) else None

    @property
    def end_ns(self) -> int | None:
        return int(self.timestamps_ns[-1]) if len(self) else None

    @property
    def duration_ns(self) -> int:
        if len(self) < 2:
            return 0
        return int(self.timestamps_ns[-1] - self.timestamps_ns[0])

    def subset(self, indices: NDArray[np.integer] | list[int] | tuple[int, ...]) -> Trajectory:
        resolved = np.asarray(indices, dtype=np.int64)
        return Trajectory(
            timestamps_ns=self.timestamps_ns[resolved],
            positions_m=self.positions_m[resolved],
            quaternions_xyzw=self.quaternions_xyzw[resolved],
            body_frame=self.body_frame,
        )


@dataclass(frozen=True, slots=True)
class EvaluationSupport:
    """Declared sensor/input time interval that an estimator was expected to cover.

    Coverage must be measured against the input actually benchmarked, not against
    whichever reference trajectory happens to be available on disk. This matters
    for prefix/segment experiments where ground truth spans a longer sequence.
    """

    start_ns: int
    end_ns: int

    def __post_init__(self) -> None:
        if self.end_ns < self.start_ns:
            raise ValueError("evaluation support end_ns must be >= start_ns")

    @property
    def duration_ns(self) -> int:
        return self.end_ns - self.start_ns


@dataclass(frozen=True, slots=True)
class TrajectoryValidationReport:
    """Structural validity findings for one trajectory."""

    pose_count: int
    invalid_translation_count: int
    invalid_rotation_count: int
    invalid_pose_count: int
    duplicate_timestamp_count: int
    non_increasing_timestamp_count: int
    quaternion_norm_tolerance: float
    start_ns: int | None
    end_ns: int | None

    @property
    def empty(self) -> bool:
        return self.pose_count == 0

    @property
    def valid(self) -> bool:
        return (
            not self.empty
            and self.invalid_pose_count == 0
            and self.duplicate_timestamp_count == 0
            and self.non_increasing_timestamp_count == 0
        )


@dataclass(frozen=True, slots=True)
class AssociationStats:
    """Timestamp-association evidence retained with every metric evaluation."""

    mode: str
    estimate_pose_count: int
    reference_pose_count: int
    matched_pose_count: int
    unmatched_estimate_pose_count: int
    interpolated_pose_count: int
    max_abs_time_delta_ns: int | None
    mean_abs_time_delta_ns: float | None
    coverage_support_start_ns: int
    coverage_support_end_ns: int
    temporal_coverage: float
    distance_coverage: float | None


@dataclass(frozen=True, slots=True)
class AssociatedTrajectories:
    """Equal-length estimate/reference pose pairs after protocol association."""

    estimate: Trajectory
    reference: Trajectory
    estimate_indices: IntArray
    reference_indices: IntArray
    time_deltas_ns: IntArray
    stats: AssociationStats

    def __post_init__(self) -> None:
        count = len(self.estimate)
        if len(self.reference) != count:
            raise ValueError("associated estimate/reference trajectories must have equal length")
        for name in ("estimate_indices", "reference_indices", "time_deltas_ns"):
            array = _readonly_array(
                getattr(self, name),
                dtype=np.dtype(np.int64),
                ndim=1,
                name=name,
            )
            if array.shape != (count,):
                raise ValueError(f"{name} must have shape ({count},), got {array.shape}")
            object.__setattr__(self, name, array)


@dataclass(frozen=True, slots=True)
class MetricSummary:
    """Descriptive statistics for one scalar error population."""

    count: int
    rmse: float
    mean: float
    median: float
    std: float
    minimum: float
    maximum: float


@dataclass(frozen=True, slots=True)
class AlignmentTransform:
    """Rigid transform applied to the estimated world frame before APE."""

    mode: str
    rotation: FloatArray
    translation_m: FloatArray

    def __post_init__(self) -> None:
        rotation = _readonly_array(
            self.rotation,
            dtype=np.dtype(np.float64),
            ndim=2,
            name="rotation",
        )
        translation = _readonly_array(
            self.translation_m,
            dtype=np.dtype(np.float64),
            ndim=1,
            name="translation_m",
        )
        if rotation.shape != (3, 3):
            raise ValueError(f"rotation must have shape (3, 3), got {rotation.shape}")
        if translation.shape != (3,):
            raise ValueError(f"translation_m must have shape (3,), got {translation.shape}")
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "translation_m", translation)

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "rotation_matrix": self.rotation.tolist(),
            "translation_m": self.translation_m.tolist(),
        }


@dataclass(frozen=True, slots=True)
class RelativeErrorResult:
    """Distance-window relative-pose error under explicit pairing semantics."""

    distance_window_m: float
    relative_tolerance: float
    pairing: str
    pair_count: int
    actual_distance_m: MetricSummary | None
    translation_error_m: MetricSummary | None
    rotation_error_deg: MetricSummary | None
    translation_error_percent: MetricSummary | None
    rotation_error_deg_per_m: MetricSummary | None


@dataclass(frozen=True, slots=True)
class TrajectoryEvaluation:
    """Protocol-scoped trajectory evaluation result."""

    estimate_validation: TrajectoryValidationReport
    reference_validation: TrajectoryValidationReport
    association: AssociationStats
    alignment: AlignmentTransform
    temporal_coverage_min: float
    temporal_coverage_pass: bool
    ape_translation_m: MetricSummary | None
    ape_rotation_deg: MetricSummary | None
    relative_errors: tuple[RelativeErrorResult, ...]

    def metric_values(self) -> dict[str, object]:
        """Return bundle-ready metric names with semantics encoded in each key."""

        values: dict[str, object] = {
            "association.mode": self.association.mode,
            "association.matched_pose_count": self.association.matched_pose_count,
            "association.unmatched_estimate_pose_count": (
                self.association.unmatched_estimate_pose_count
            ),
            "association.interpolated_pose_count": self.association.interpolated_pose_count,
            "coverage.support_start_ns": self.association.coverage_support_start_ns,
            "coverage.support_end_ns": self.association.coverage_support_end_ns,
            "coverage.temporal_fraction": self.association.temporal_coverage,
            "coverage.temporal_min_required": self.temporal_coverage_min,
            "coverage.temporal_pass": self.temporal_coverage_pass,
            "trajectory.estimate.invalid_pose_count": self.estimate_validation.invalid_pose_count,
            "trajectory.reference.invalid_pose_count": self.reference_validation.invalid_pose_count,
            "alignment.transform": self.alignment.as_dict(),
        }
        if self.association.distance_coverage is not None:
            values["coverage.distance_fraction"] = self.association.distance_coverage
        if self.association.max_abs_time_delta_ns is not None:
            values["association.max_abs_time_delta_ns"] = self.association.max_abs_time_delta_ns
        if self.association.mean_abs_time_delta_ns is not None:
            values["association.mean_abs_time_delta_ns"] = self.association.mean_abs_time_delta_ns
        if self.ape_translation_m is not None:
            values["ape.translation.rmse_m"] = self.ape_translation_m.rmse
        if self.ape_rotation_deg is not None:
            values["ape.rotation.rmse_deg"] = self.ape_rotation_deg.rmse
        for result in self.relative_errors:
            window = f"{result.distance_window_m:g}m"
            prefix = f"rpe.distance_{window}"
            values[f"{prefix}.pair_count"] = result.pair_count
            values[f"{prefix}.pairing"] = result.pairing
            values[f"{prefix}.relative_tolerance"] = result.relative_tolerance
            if result.translation_error_m is not None:
                values[f"{prefix}.translation.rmse_m"] = result.translation_error_m.rmse
            if result.rotation_error_deg is not None:
                values[f"{prefix}.rotation.rmse_deg"] = result.rotation_error_deg.rmse
            if result.translation_error_percent is not None:
                values[f"{prefix}.translation.rmse_percent"] = (
                    result.translation_error_percent.rmse
                )
            if result.rotation_error_deg_per_m is not None:
                values[f"{prefix}.rotation.rmse_deg_per_m"] = (
                    result.rotation_error_deg_per_m.rmse
                )
        return values
