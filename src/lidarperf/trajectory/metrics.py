"""Protocol-scoped APE and distance-window relative pose metrics."""

from __future__ import annotations

import math

import numpy as np

from lidarperf.spec.models import BenchmarkProtocol, RelativeErrorWindow

from .alignment import apply_alignment_positions, apply_alignment_rotations, estimate_alignment
from .association import associate_trajectories
from .math import pose_matrix, quaternions_to_matrices, relative_pose, rotation_angle_rad
from .model import (
    MetricSummary,
    RelativeErrorResult,
    Trajectory,
    TrajectoryEvaluation,
    TrajectoryMetricError,
    TrajectoryValidationError,
)
from .validation import validate_trajectory


def summarize(values: np.ndarray | list[float]) -> MetricSummary:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise TrajectoryMetricError("metric summary requires at least one scalar value")
    if not np.all(np.isfinite(array)):
        raise TrajectoryMetricError("metric summary received a non-finite scalar")
    return MetricSummary(
        count=int(array.size),
        rmse=float(np.sqrt(np.mean(np.square(array)))),
        mean=float(np.mean(array)),
        median=float(np.median(array)),
        std=float(np.std(array)),
        minimum=float(np.min(array)),
        maximum=float(np.max(array)),
    )


def _ape_translation(
    aligned_estimate_positions: np.ndarray,
    reference_positions: np.ndarray,
) -> MetricSummary:
    errors = np.linalg.norm(aligned_estimate_positions - reference_positions, axis=1)
    return summarize(errors)


def _ape_rotation(
    aligned_estimate_rotations: np.ndarray,
    reference_rotations: np.ndarray,
) -> MetricSummary:
    errors_deg = [
        math.degrees(rotation_angle_rad(reference.T @ estimate))
        for estimate, reference in zip(
            aligned_estimate_rotations,
            reference_rotations,
            strict=True,
        )
    ]
    return summarize(errors_deg)


def _cumulative_path_distance(positions: np.ndarray) -> np.ndarray:
    if positions.shape[0] == 0:
        return np.empty(0, dtype=np.float64)
    increments = np.linalg.norm(np.diff(positions, axis=0), axis=1)
    return np.concatenate((np.array([0.0], dtype=np.float64), np.cumsum(increments)))


def _distance_window_pairs(
    reference_positions: np.ndarray,
    window: RelativeErrorWindow,
) -> list[tuple[int, int, float]]:
    """Select one nearest later endpoint for every possible start pose.

    Pairing is based only on accumulated *reference* path length. The endpoint
    closest to ``distance_m`` is accepted only when its absolute distance error
    is within ``distance_m * relative_tolerance``. Ties use the earlier pose.
    """

    if window.pairing != "all_starts_nearest_reference_distance":
        raise TrajectoryMetricError(f"unsupported relative-error pairing: {window.pairing}")
    cumulative = _cumulative_path_distance(reference_positions)
    if cumulative.size < 2:
        return []
    target_distance = float(window.distance_m)
    tolerance = target_distance * float(window.relative_tolerance)
    pairs: list[tuple[int, int, float]] = []
    final_distance = float(cumulative[-1])
    for start in range(cumulative.size - 1):
        desired = float(cumulative[start]) + target_distance
        if desired > final_distance + tolerance:
            break
        insertion = int(np.searchsorted(cumulative, desired, side="left"))
        candidates: list[int] = []
        if insertion < cumulative.size and insertion > start:
            candidates.append(insertion)
        if insertion - 1 > start:
            candidates.append(insertion - 1)
        if not candidates:
            continue
        end = min(
            candidates,
            key=lambda index: (abs(float(cumulative[index]) - desired), index),
        )
        actual_distance = float(cumulative[end] - cumulative[start])
        if actual_distance <= 0.0:
            continue
        if abs(actual_distance - target_distance) <= tolerance + 1e-12:
            pairs.append((start, end, actual_distance))
    return pairs


def _relative_error(
    estimate: Trajectory,
    reference: Trajectory,
    window: RelativeErrorWindow,
) -> RelativeErrorResult:
    pairs = _distance_window_pairs(reference.positions_m, window)
    if not pairs:
        return RelativeErrorResult(
            distance_window_m=float(window.distance_m),
            relative_tolerance=float(window.relative_tolerance),
            pairing=window.pairing,
            pair_count=0,
            actual_distance_m=None,
            translation_error_m=None,
            rotation_error_deg=None,
            translation_error_percent=None,
            rotation_error_deg_per_m=None,
        )

    estimate_poses = [
        pose_matrix(position, quaternion)
        for position, quaternion in zip(
            estimate.positions_m,
            estimate.quaternions_xyzw,
            strict=True,
        )
    ]
    reference_poses = [
        pose_matrix(position, quaternion)
        for position, quaternion in zip(
            reference.positions_m,
            reference.quaternions_xyzw,
            strict=True,
        )
    ]

    distances: list[float] = []
    translation_errors: list[float] = []
    rotation_errors_deg: list[float] = []
    translation_percent: list[float] = []
    rotation_deg_per_m: list[float] = []
    for start, end, actual_distance in pairs:
        reference_delta = relative_pose(reference_poses[start], reference_poses[end])
        estimate_delta = relative_pose(estimate_poses[start], estimate_poses[end])
        error = relative_pose(reference_delta, estimate_delta)
        translation_error = float(np.linalg.norm(error[:3, 3]))
        rotation_error_deg = math.degrees(rotation_angle_rad(error[:3, :3]))
        distances.append(actual_distance)
        translation_errors.append(translation_error)
        rotation_errors_deg.append(rotation_error_deg)
        translation_percent.append(100.0 * translation_error / actual_distance)
        rotation_deg_per_m.append(rotation_error_deg / actual_distance)

    return RelativeErrorResult(
        distance_window_m=float(window.distance_m),
        relative_tolerance=float(window.relative_tolerance),
        pairing=window.pairing,
        pair_count=len(pairs),
        actual_distance_m=summarize(distances),
        translation_error_m=summarize(translation_errors),
        rotation_error_deg=summarize(rotation_errors_deg),
        translation_error_percent=summarize(translation_percent),
        rotation_error_deg_per_m=summarize(rotation_deg_per_m),
    )


def evaluate_trajectory(
    estimate: Trajectory,
    reference: Trajectory,
    protocol: BenchmarkProtocol,
) -> TrajectoryEvaluation:
    """Validate, associate, align, and evaluate one estimate/reference pair."""

    estimate_validation = validate_trajectory(estimate)
    reference_validation = validate_trajectory(reference)
    if not estimate_validation.valid:
        raise TrajectoryValidationError(
            "estimate trajectory is structurally invalid",
            estimate_validation,
        )
    if not reference_validation.valid:
        raise TrajectoryValidationError(
            "reference trajectory is structurally invalid",
            reference_validation,
        )
    expected_frame = protocol.trajectory.evaluation_frame
    if estimate.body_frame != expected_frame:
        raise TrajectoryMetricError(
            f"estimate body frame {estimate.body_frame!r} does not match protocol "
            f"evaluation_frame {expected_frame!r}"
        )
    if reference.body_frame != expected_frame:
        raise TrajectoryMetricError(
            f"reference body frame {reference.body_frame!r} does not match protocol "
            f"evaluation_frame {expected_frame!r}"
        )

    associated = associate_trajectories(
        estimate,
        reference,
        protocol.trajectory.association,
    )
    alignment = estimate_alignment(
        associated.estimate,
        associated.reference,
        protocol.trajectory.alignment,
    )
    aligned_positions = apply_alignment_positions(associated.estimate, alignment)
    aligned_rotations = apply_alignment_rotations(associated.estimate, alignment)
    reference_rotations = quaternions_to_matrices(associated.reference.quaternions_xyzw)

    ape_translation = (
        _ape_translation(aligned_positions, associated.reference.positions_m)
        if protocol.trajectory.ape_translation
        else None
    )
    ape_rotation = (
        _ape_rotation(aligned_rotations, reference_rotations)
        if protocol.trajectory.ape_rotation
        else None
    )
    relative_errors = tuple(
        _relative_error(associated.estimate, associated.reference, window)
        for window in protocol.trajectory.relative_error_windows
    )
    minimum_coverage = protocol.validity.temporal_coverage_min
    return TrajectoryEvaluation(
        estimate_validation=estimate_validation,
        reference_validation=reference_validation,
        association=associated.stats,
        alignment=alignment,
        temporal_coverage_min=minimum_coverage,
        temporal_coverage_pass=associated.stats.temporal_coverage >= minimum_coverage,
        ape_translation_m=ape_translation,
        ape_rotation_deg=ape_rotation,
        relative_errors=relative_errors,
    )
