"""Small, dependency-light SO(3)/SE(3) helpers for trajectory evaluation."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def normalize_quaternion(quaternion_xyzw: FloatArray) -> FloatArray:
    quaternion = np.asarray(quaternion_xyzw, dtype=np.float64)
    norm = float(np.linalg.norm(quaternion))
    if not math.isfinite(norm) or norm <= np.finfo(np.float64).eps:
        raise ValueError("quaternion norm must be finite and non-zero")
    return quaternion / norm


def quaternion_to_matrix(quaternion_xyzw: FloatArray) -> FloatArray:
    """Convert an ``[x, y, z, w]`` quaternion to a 3x3 rotation matrix."""

    x, y, z, w = normalize_quaternion(quaternion_xyzw)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def quaternions_to_matrices(quaternions_xyzw: FloatArray) -> FloatArray:
    quaternions = np.asarray(quaternions_xyzw, dtype=np.float64)
    return np.stack([quaternion_to_matrix(quaternion) for quaternion in quaternions], axis=0)


def matrix_to_quaternion(rotation: FloatArray) -> FloatArray:
    """Convert a proper rotation matrix to deterministic ``[x, y, z, w]`` form."""

    matrix = np.asarray(rotation, dtype=np.float64)
    if matrix.shape != (3, 3):
        raise ValueError("rotation matrix must have shape (3, 3)")
    trace = float(np.trace(matrix))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * scale
        x = (matrix[2, 1] - matrix[1, 2]) / scale
        y = (matrix[0, 2] - matrix[2, 0]) / scale
        z = (matrix[1, 0] - matrix[0, 1]) / scale
    else:
        diagonal = np.diag(matrix)
        index = int(np.argmax(diagonal))
        if index == 0:
            scale = math.sqrt(max(0.0, 1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2])) * 2.0
            x = 0.25 * scale
            y = (matrix[0, 1] + matrix[1, 0]) / scale
            z = (matrix[0, 2] + matrix[2, 0]) / scale
            w = (matrix[2, 1] - matrix[1, 2]) / scale
        elif index == 1:
            scale = math.sqrt(max(0.0, 1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2])) * 2.0
            x = (matrix[0, 1] + matrix[1, 0]) / scale
            y = 0.25 * scale
            z = (matrix[1, 2] + matrix[2, 1]) / scale
            w = (matrix[0, 2] - matrix[2, 0]) / scale
        else:
            scale = math.sqrt(max(0.0, 1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1])) * 2.0
            x = (matrix[0, 2] + matrix[2, 0]) / scale
            y = (matrix[1, 2] + matrix[2, 1]) / scale
            z = 0.25 * scale
            w = (matrix[1, 0] - matrix[0, 1]) / scale
    quaternion = normalize_quaternion(np.array([x, y, z, w], dtype=np.float64))
    if quaternion[3] < 0.0:
        quaternion = -quaternion
    return quaternion


def slerp(quaternion_a: FloatArray, quaternion_b: FloatArray, fraction: float) -> FloatArray:
    """Shortest-arc quaternion SLERP with deterministic antipodal handling."""

    if not 0.0 <= fraction <= 1.0:
        raise ValueError("SLERP fraction must lie in [0, 1]")
    first = normalize_quaternion(quaternion_a)
    second = normalize_quaternion(quaternion_b)
    dot = float(np.dot(first, second))
    if dot < 0.0:
        second = -second
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return normalize_quaternion(first + fraction * (second - first))
    angle = math.acos(dot)
    sin_angle = math.sin(angle)
    weight_a = math.sin((1.0 - fraction) * angle) / sin_angle
    weight_b = math.sin(fraction * angle) / sin_angle
    return normalize_quaternion(weight_a * first + weight_b * second)


def rotation_angle_rad(rotation: FloatArray) -> float:
    matrix = np.asarray(rotation, dtype=np.float64)
    cosine = (float(np.trace(matrix)) - 1.0) / 2.0
    return math.acos(max(-1.0, min(1.0, cosine)))


def pose_matrix(position_m: FloatArray, quaternion_xyzw: FloatArray) -> FloatArray:
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = quaternion_to_matrix(quaternion_xyzw)
    transform[:3, 3] = np.asarray(position_m, dtype=np.float64)
    return transform


def relative_pose(first: FloatArray, second: FloatArray) -> FloatArray:
    """Return ``inv(first) @ second`` for two rigid 4x4 transforms."""

    rotation = first[:3, :3]
    translation = first[:3, 3]
    inverse = np.eye(4, dtype=np.float64)
    inverse[:3, :3] = rotation.T
    inverse[:3, 3] = -(rotation.T @ translation)
    return inverse @ second
