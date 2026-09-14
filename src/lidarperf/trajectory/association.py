"""Protocol-defined timestamp association for estimator/reference trajectories."""

from __future__ import annotations

import numpy as np

from lidarperf.spec.enums import TimestampAssociationMode
from lidarperf.spec.models import TimestampAssociation

from .math import slerp
from .model import (
    AssociatedTrajectories,
    AssociationStats,
    Trajectory,
    TrajectoryAssociationError,
    TrajectoryValidationError,
)
from .validation import validate_trajectory


def _require_structurally_valid(trajectory: Trajectory, label: str) -> None:
    report = validate_trajectory(trajectory)
    if not report.valid:
        raise TrajectoryValidationError(f"{label} trajectory is structurally invalid", report)


def _coverage(reference: Trajectory, matched_estimate_timestamps: np.ndarray) -> float:
    if len(reference) == 0 or matched_estimate_timestamps.size == 0:
        return 0.0
    if reference.duration_ns == 0:
        timestamp = int(reference.timestamps_ns[0])
        return float(np.any(matched_estimate_timestamps == timestamp))
    overlap_start = max(int(reference.timestamps_ns[0]), int(matched_estimate_timestamps[0]))
    overlap_end = min(int(reference.timestamps_ns[-1]), int(matched_estimate_timestamps[-1]))
    if overlap_end <= overlap_start:
        return 0.0
    return (overlap_end - overlap_start) / reference.duration_ns


def _nearest_reference_index(reference_timestamps: np.ndarray, timestamp: int) -> int:
    insertion = int(np.searchsorted(reference_timestamps, timestamp, side="left"))
    candidates: list[int] = []
    if insertion > 0:
        candidates.append(insertion - 1)
    if insertion < reference_timestamps.size:
        candidates.append(insertion)
    if not candidates:
        raise TrajectoryAssociationError("reference trajectory is empty")
    # Stable tie break: earlier reference timestamp wins.
    return min(
        candidates,
        key=lambda index: (abs(int(reference_timestamps[index]) - timestamp), index),
    )


def associate_trajectories(
    estimate: Trajectory,
    reference: Trajectory,
    policy: TimestampAssociation,
) -> AssociatedTrajectories:
    """Associate estimate poses to reference poses under an explicit protocol policy."""

    _require_structurally_valid(estimate, "estimate")
    _require_structurally_valid(reference, "reference")

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
    else:  # pragma: no cover - enum + Pydantic make this defensive only.
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
        temporal_coverage=_coverage(reference, matched_estimate.timestamps_ns),
    )
    return AssociatedTrajectories(
        estimate=matched_estimate,
        reference=matched_reference,
        estimate_indices=estimate_index_array,
        reference_indices=reference_index_array,
        time_deltas_ns=time_delta_array,
        stats=stats,
    )
