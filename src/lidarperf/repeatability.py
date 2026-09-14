"""Run-set statistics and trajectory-repeatability measurements."""

from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np

from lidarperf.trajectory import Trajectory


class RepeatabilityError(ValueError):
    """Raised when repeatability statistics cannot be computed honestly."""


def summarize_scalars(values: list[float]) -> dict[str, float | int]:
    """Return deterministic descriptive statistics for a finite scalar population.

    Standard deviation is the population standard deviation (``ddof=0``). Percentiles
    use NumPy's linear interpolation semantics so the definition is explicit and stable.
    """

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise RepeatabilityError("scalar summary requires at least one value")
    if not np.all(np.isfinite(array)):
        raise RepeatabilityError("scalar summary received a non-finite value")
    p90, p95, p99 = np.percentile(array, [90.0, 95.0, 99.0], method="linear")
    return {
        "count": int(array.size),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "std": float(np.std(array)),
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
        "p90": float(p90),
        "p95": float(p95),
        "p99": float(p99),
    }


def _numeric_scalar(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if np.isfinite(result) else None


def scalar_distributions(records: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    """Summarize numeric scalar keys present in every record.

    Nested structures, strings, booleans, and values missing from any record are not
    silently coerced into distributions.
    """

    if not records:
        return {}
    shared = set(records[0])
    for record in records[1:]:
        shared &= set(record)

    distributions: dict[str, dict[str, float | int]] = {}
    for key in sorted(shared):
        values = [_numeric_scalar(record[key]) for record in records]
        if all(value is not None for value in values):
            distributions[key] = summarize_scalars(
                [value for value in values if value is not None]
            )
    return distributions


def _pairwise_pose_deltas(first: Trajectory, second: Trajectory) -> tuple[np.ndarray, np.ndarray]:
    if first.body_frame != second.body_frame:
        raise RepeatabilityError("trajectory body frames differ across repeated trials")

    _, first_indices, second_indices = np.intersect1d(
        first.timestamps_ns,
        second.timestamps_ns,
        assume_unique=True,
        return_indices=True,
    )
    if first_indices.size == 0:
        raise RepeatabilityError("repeated trajectories have no common timestamps")

    translation_delta = np.linalg.norm(
        first.positions_m[first_indices] - second.positions_m[second_indices],
        axis=1,
    )

    first_q = first.quaternions_xyzw[first_indices]
    second_q = second.quaternions_xyzw[second_indices]
    first_q = first_q / np.linalg.norm(first_q, axis=1, keepdims=True)
    second_q = second_q / np.linalg.norm(second_q, axis=1, keepdims=True)
    dots = np.abs(np.sum(first_q * second_q, axis=1))
    dots = np.clip(dots, 0.0, 1.0)
    rotation_delta_deg = np.degrees(2.0 * np.arccos(dots))
    return translation_delta, rotation_delta_deg


def trajectory_repeatability(trajectories: list[Trajectory]) -> dict[str, Any]:
    """Measure raw estimator-output variability across all measured-trial pairs.

    The comparison uses exact common timestamps and deliberately performs no spatial
    alignment. Nominally identical repeated runs share the same input, initialization,
    and output frame, so gauge changes are themselves estimator-output variability.
    """

    if len(trajectories) < 2:
        raise RepeatabilityError("trajectory repeatability requires at least two trials")

    translation_pair_rmse: list[float] = []
    rotation_pair_rmse: list[float] = []
    common_counts: list[float] = []
    max_translation_delta = 0.0
    max_rotation_delta = 0.0
    timestamp_sets_identical = True

    for first, second in combinations(trajectories, 2):
        translation_delta, rotation_delta = _pairwise_pose_deltas(first, second)
        translation_pair_rmse.append(float(np.sqrt(np.mean(np.square(translation_delta)))))
        rotation_pair_rmse.append(float(np.sqrt(np.mean(np.square(rotation_delta)))))
        common_counts.append(float(translation_delta.size))
        max_translation_delta = max(max_translation_delta, float(np.max(translation_delta)))
        max_rotation_delta = max(max_rotation_delta, float(np.max(rotation_delta)))
        timestamp_sets_identical = timestamp_sets_identical and np.array_equal(
            first.timestamps_ns,
            second.timestamps_ns,
        )

    return {
        "semantics": "all_pairwise_exact_timestamp_pose_differences_no_spatial_alignment",
        "trial_pair_count": len(translation_pair_rmse),
        "timestamp_sets_identical": timestamp_sets_identical,
        "common_pose_count": summarize_scalars(common_counts),
        "translation_pairwise_rmse_m": summarize_scalars(translation_pair_rmse),
        "rotation_pairwise_rmse_deg": summarize_scalars(rotation_pair_rmse),
        "maximum_pose_translation_delta_m": max_translation_delta,
        "maximum_pose_rotation_delta_deg": max_rotation_delta,
    }
