"""Explicit rigid alignment semantics for associated trajectories."""

from __future__ import annotations

import numpy as np

from lidarperf.spec.enums import AlignmentMode

from .math import quaternion_to_matrix, quaternions_to_matrices
from .model import AlignmentTransform, Trajectory, TrajectoryMetricError


def _identity(mode: AlignmentMode) -> AlignmentTransform:
    return AlignmentTransform(
        mode=mode.value,
        rotation=np.eye(3, dtype=np.float64),
        translation_m=np.zeros(3, dtype=np.float64),
    )


def estimate_alignment(
    estimate: Trajectory,
    reference: Trajectory,
    mode: AlignmentMode,
) -> AlignmentTransform:
    """Estimate the protocol's rigid world-frame alignment transform."""

    if len(estimate) != len(reference):
        raise TrajectoryMetricError("alignment requires equal-length associated trajectories")
    if len(estimate) == 0:
        raise TrajectoryMetricError("alignment requires at least one associated pose")
    if mode == AlignmentMode.NONE:
        return _identity(mode)

    if mode == AlignmentMode.ORIGIN:
        estimate_rotation = quaternion_to_matrix(estimate.quaternions_xyzw[0])
        reference_rotation = quaternion_to_matrix(reference.quaternions_xyzw[0])
        rotation = reference_rotation @ estimate_rotation.T
        translation = reference.positions_m[0] - rotation @ estimate.positions_m[0]
        return AlignmentTransform(
            mode=mode.value,
            rotation=rotation,
            translation_m=translation,
        )

    if mode != AlignmentMode.SE3:  # pragma: no cover - defensive against future enums.
        raise TrajectoryMetricError(f"unsupported alignment mode: {mode}")
    if len(estimate) < 3:
        raise TrajectoryMetricError("SE(3) alignment requires at least three associated poses")

    source = estimate.positions_m
    target = reference.positions_m
    source_centered = source - source.mean(axis=0)
    target_centered = target - target.mean(axis=0)
    if np.linalg.matrix_rank(source_centered) < 2 or np.linalg.matrix_rank(target_centered) < 2:
        raise TrajectoryMetricError(
            "SE(3) alignment is underdetermined for a collinear or static trajectory"
        )

    covariance = source_centered.T @ target_centered
    u, _singular_values, vt = np.linalg.svd(covariance)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0.0:
        vt = vt.copy()
        vt[-1, :] *= -1.0
        rotation = vt.T @ u.T
    translation = target.mean(axis=0) - rotation @ source.mean(axis=0)
    return AlignmentTransform(
        mode=mode.value,
        rotation=rotation,
        translation_m=translation,
    )


def apply_alignment_positions(trajectory: Trajectory, alignment: AlignmentTransform) -> np.ndarray:
    """Apply the alignment's left world-frame transform to all positions."""

    return (alignment.rotation @ trajectory.positions_m.T).T + alignment.translation_m


def apply_alignment_rotations(trajectory: Trajectory, alignment: AlignmentTransform) -> np.ndarray:
    """Apply the alignment's world-frame rotation to all body orientations."""

    rotations = quaternions_to_matrices(trajectory.quaternions_xyzw)
    return np.einsum("ij,njk->nik", alignment.rotation, rotations)
