"""Structural trajectory validation required before metric evaluation."""

from __future__ import annotations

import numpy as np

from .model import Trajectory, TrajectoryValidationReport

DEFAULT_QUATERNION_NORM_TOLERANCE = 1e-3


def validate_trajectory(
    trajectory: Trajectory,
    *,
    quaternion_norm_tolerance: float = DEFAULT_QUATERNION_NORM_TOLERANCE,
) -> TrajectoryValidationReport:
    """Validate structural trajectory invariants without silently dropping bad poses."""

    if quaternion_norm_tolerance < 0:
        raise ValueError("quaternion_norm_tolerance must be non-negative")
    pose_count = len(trajectory)
    if pose_count == 0:
        return TrajectoryValidationReport(
            pose_count=0,
            invalid_translation_count=0,
            invalid_rotation_count=0,
            invalid_pose_count=0,
            duplicate_timestamp_count=0,
            non_increasing_timestamp_count=0,
            quaternion_norm_tolerance=quaternion_norm_tolerance,
            start_ns=None,
            end_ns=None,
        )

    translation_valid = np.all(np.isfinite(trajectory.positions_m), axis=1)
    quaternion_finite = np.all(np.isfinite(trajectory.quaternions_xyzw), axis=1)
    quaternion_norms = np.linalg.norm(trajectory.quaternions_xyzw, axis=1)
    rotation_valid = (
        quaternion_finite
        & (quaternion_norms > np.finfo(np.float64).eps)
        & (np.abs(quaternion_norms - 1.0) <= quaternion_norm_tolerance)
    )
    invalid_pose = ~(translation_valid & rotation_valid)

    deltas = np.diff(trajectory.timestamps_ns)
    duplicate_count = int(np.count_nonzero(deltas == 0))
    non_increasing_count = int(np.count_nonzero(deltas <= 0))

    return TrajectoryValidationReport(
        pose_count=pose_count,
        invalid_translation_count=int(np.count_nonzero(~translation_valid)),
        invalid_rotation_count=int(np.count_nonzero(~rotation_valid)),
        invalid_pose_count=int(np.count_nonzero(invalid_pose)),
        duplicate_timestamp_count=duplicate_count,
        non_increasing_timestamp_count=non_increasing_count,
        quaternion_norm_tolerance=quaternion_norm_tolerance,
        start_ns=trajectory.start_ns,
        end_ns=trajectory.end_ns,
    )
