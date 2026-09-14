"""Protocol-defined timestamp association for estimator/reference trajectories."""

from __future__ import annotations

import numpy as np

from lidarperf.spec.enums import TimestampAssociationMode
from lidarperf.spec.models import TimestampAssociation

from .math import slerp
from .model import (
    AssociatedTrajectories,
    AssociationStats,
    EvaluationSupport,
    Trajectory,
    TrajectoryAssociationError,
    TrajectoryValidationError,
)
from .validation import validate_trajectory


def _require_structurally_valid(trajectory: Trajectory, label: str) -> None:
    report = validate_trajectory(trajectory)
    if not report.valid:
        raise TrajectoryValidationError(f"{label} trajectory is structurally invalid", report)


def _reference_support(reference: Trajectory) -> EvaluationSupport:
    if reference.start_ns is None or reference.end_ns is None:
        raise TrajectoryAssociationError("reference trajectory is empty")
    return EvaluationSupport(start_ns=reference.start_ns, end_ns=reference.end_ns)


def _evaluable_support(
    reference: Trajectory,
    input_support: EvaluationSupport,
) -> EvaluationSupport:
    """Return the portion of declared input support covered by reference ground truth."""

    reference_support = _reference_support(reference)
    start_ns = max(input_support.start_ns, reference_support.start_ns)
    end_ns = min(input_support.end_ns, reference_support.end_ns)
    if end_ns < start_ns:
        raise TrajectoryAssociationError(
            "declared input support does not overlap reference trajectory time support"
        )
    return EvaluationSupport(start_ns=start_ns, end_ns=end_ns)


def _coverage(support: EvaluationSupport, matched_estimate_timestamps: np.ndarray) -> float:
    if matched_estimate_timestamps.size == 0:
        return 0.0
    if support.duration_ns == 0:
        return float(np.any(matched_estimate_timestamps == support.start_ns))
    overlap_start = max(support.start_ns, int(matched_estimate_timestamps[0]))
    overlap_end = min(support.end_ns, int(matched_estimate_timestamps[-1]))
    if overlap_end <= overlap_start:
        return 0.0
    return min(1.0, (overlap_end - overlap_start) / support.duration_ns)


def _path_length(positions: np.ndarray) -> float:
    if positions.shape[0] < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(positions, axis=0), axis=1).sum())


def _reference_position_at(reference: Trajectory, timestamp_ns: int) -> np.ndarray:
    timestamps = reference.timestamps_ns
    insertion = int(np.searchsorted(timestamps, timestamp_ns, side="left"))
    if insertion < len(reference) and int(timestamps[insertion]) == timestamp_ns:
        return reference.positions_m[insertion]
    if insertion == 0 or insertion >= len(reference):
        raise TrajectoryAssociationError(
            "evaluation support boundary cannot be interpolated inside reference trajectory"
        )
    left = insertion - 1
    right = insertion
    left_ns = int(timestamps[left])
    right_ns = int(timestamps[right])
    fraction = (timestamp_ns - left_ns) / (right_ns - left_ns)
    return (1.0 - fraction) * reference.positions_m[left] + fraction * reference.positions_m[right]


def _reference_positions_for_support(
    reference: Trajectory,
    support: EvaluationSupport,
) -> np.ndarray:
    """Sample reference path on the exact evaluable support including boundaries."""

    if support.duration_ns == 0:
        return np.asarray([_reference_position_at(reference, support.start_ns)], dtype=np.float64)
    interior_mask = (reference.timestamps_ns > support.start_ns) & (
        reference.timestamps_ns < support.end_ns
    )
    positions: list[np.ndarray] = [_reference_position_at(reference, support.start_ns)]
    positions.extend(reference.positions_m[interior_mask])
    positions.append(_reference_position_at(reference, support.end_ns))
    return np.asarray(positions, dtype=np.float64)


def _distance_coverage(
    reference: Trajectory,
    matched_reference: Trajectory,
    support: EvaluationSupport,
) -> float | None:
    support_distance = _path_length(_reference_positions_for_support(reference, support))
    if support_distance <= np.finfo(np.float64).eps:
        return 1.0 if len(matched_reference) else 0.0
    matched_distance = _path_length(matched_reference.positions_m)
    return min(1.0, matched_distance / support_distance)


def _nearest_reference_index(reference_timestamps: np.ndarray, timestamp: int) -> int:
    insertion = int(np.searchsorted(reference_timestamps, timestamp, side="left"))
    candidates: list[int] = []
    if insertion > 0:
        candidates.append(insertion - 1)
    if insertion < reference_timestamps.size:
        candidates.append(insertion)
    if not candidates:
        raise TrajectoryAssociationError("reference trajectory is empty")
    return min(
        candidates,
        key=lambda index: (abs(int(reference_timestamps[index]) - timestamp), index),
    )


def associate_trajectories(
    estimate: Trajectory,
    reference: Trajectory,
    policy: TimestampAssociation,
    *,
    support: EvaluationSupport | None = None,
) -> AssociatedTrajectories:
    """Associate estimate/reference poses under explicit protocol and support semantics.

    ``support`` is the declared sensor/input interval of the benchmark trial. Accuracy
    coverage is measured on the intersection of that interval and the available
    reference trajectory. This keeps prefix/segment runs honest without penalizing an
    estimator for reference data that does not exist outside the ground-truth support.
    """

    _require_structurally_valid(estimate, "estimate")
    _require_structurally_valid(reference, "reference")
    input_support = support or _reference_support(reference)
    evaluable_support = _evaluable_support(reference, input_support)

    estimate_indices: list[int] = []
    reference_indices: list[int] = []
    reference_positions: list[np.ndarray] = []
    reference_quaternions: list[np.ndarray] = []
    reference_output_timestamps: list[int] = []
    time_deltas: list[int] = []
    interpolated_count = 0

    reference_ts = reference.timestamps_ns

    if policy.mode == TimestampAssociationMode.EXACT:
        lookup = {int(timestamp): index for index, timestamp in enumerate(reference_ts)}
        for estimate_index, timestamp_value in enumerate(estimate.timestamps_ns):
            timestamp = int(timestamp_value)
            if timestamp < input_support.start_ns or timestamp > input_support.end_ns:
                continue
            reference_index = lookup.get(timestamp)
            if reference_index is None:
                continue
            estimate_indices.append(estimate_index)
            reference_indices.append(reference_index)
            reference_positions.append(reference.positions_m[reference_index])
            reference_quaternions.append(reference.quaternions_xyzw[reference_index])
            reference_output_timestamps.append(timestamp)
            time_deltas.append(0)

    elif policy.mode == TimestampAssociationMode.NEAREST:
        assert policy.max_time_delta_ns is not None
        for estimate_index, timestamp_value in enumerate(estimate.timestamps_ns):
            timestamp = int(timestamp_value)
            if timestamp < input_support.start_ns or timestamp > input_support.end_ns:
                continue
            reference_index = _nearest_reference_index(reference_ts, timestamp)
            reference_timestamp = int(reference_ts[reference_index])
            delta = reference_timestamp - timestamp
            if abs(delta) > policy.max_time_delta_ns:
                continue
            estimate_indices.append(estimate_index)
            reference_indices.append(reference_index)
            reference_positions.append(reference.positions_m[reference_index])
            reference_quaternions.append(reference.quaternions_xyzw[reference_index])
            reference_output_timestamps.append(reference_timestamp)
            time_deltas.append(delta)

    elif policy.mode == TimestampAssociationMode.INTERPOLATE_REFERENCE:
        assert policy.max_reference_gap_ns is not None
        for estimate_index, timestamp_value in enumerate(estimate.timestamps_ns):
            timestamp = int(timestamp_value)
            if timestamp < input_support.start_ns or timestamp > input_support.end_ns:
                continue
            insertion = int(np.searchsorted(reference_ts, timestamp, side="left"))
            if insertion < len(reference) and int(reference_ts[insertion]) == timestamp:
                estimate_indices.append(estimate_index)
                reference_indices.append(insertion)
                reference_positions.append(reference.positions_m[insertion])
                reference_quaternions.append(reference.quaternions_xyzw[insertion])
                reference_output_timestamps.append(timestamp)
                time_deltas.append(0)
                continue
            if insertion == 0 or insertion >= len(reference):
                continue
            left = insertion - 1
            right = insertion
            left_time = int(reference_ts[left])
            right_time = int(reference_ts[right])
            gap = right_time - left_time
            if gap > policy.max_reference_gap_ns:
                continue
            fraction = (timestamp - left_time) / gap
            position = (
                (1.0 - fraction) * reference.positions_m[left]
                + fraction * reference.positions_m[right]
            )
            quaternion = slerp(
                reference.quaternions_xyzw[left],
                reference.quaternions_xyzw[right],
                fraction,
            )
            estimate_indices.append(estimate_index)
            reference_indices.append(-1)
            reference_positions.append(position)
            reference_quaternions.append(quaternion)
            reference_output_timestamps.append(timestamp)
            time_deltas.append(0)
            interpolated_count += 1
    else:  # pragma: no cover
        raise TrajectoryAssociationError(f"unsupported association mode: {policy.mode}")

    if not estimate_indices:
        raise TrajectoryAssociationError(
            f"timestamp association mode {policy.mode.value!r} produced no pose pairs"
        )

    estimate_index_array = np.asarray(estimate_indices, dtype=np.int64)
    reference_index_array = np.asarray(reference_indices, dtype=np.int64)
    time_delta_array = np.asarray(time_deltas, dtype=np.int64)
    matched_estimate = estimate.subset(estimate_index_array)
    matched_reference = Trajectory(
        timestamps_ns=np.asarray(reference_output_timestamps, dtype=np.int64),
        positions_m=np.asarray(reference_positions, dtype=np.float64),
        quaternions_xyzw=np.asarray(reference_quaternions, dtype=np.float64),
        body_frame=reference.body_frame,
    )
    abs_deltas = np.abs(time_delta_array)
    stats = AssociationStats(
        mode=policy.mode.value,
        estimate_pose_count=len(estimate),
        reference_pose_count=len(reference),
        matched_pose_count=len(estimate_indices),
        unmatched_estimate_pose_count=len(estimate) - len(estimate_indices),
        interpolated_pose_count=interpolated_count,
        max_abs_time_delta_ns=int(abs_deltas.max()) if abs_deltas.size else None,
        mean_abs_time_delta_ns=float(abs_deltas.mean()) if abs_deltas.size else None,
        input_support_start_ns=input_support.start_ns,
        input_support_end_ns=input_support.end_ns,
        coverage_support_start_ns=evaluable_support.start_ns,
        coverage_support_end_ns=evaluable_support.end_ns,
        temporal_coverage=_coverage(evaluable_support, matched_estimate.timestamps_ns),
        distance_coverage=_distance_coverage(reference, matched_reference, evaluable_support),
    )
    return AssociatedTrajectories(
        estimate=matched_estimate,
        reference=matched_reference,
        estimate_indices=estimate_index_array,
        reference_indices=reference_index_array,
        time_deltas_ns=time_delta_array,
        stats=stats,
    )
