from __future__ import annotations

import numpy as np
import pytest

from lidarperf.repeatability import (
    scalar_distributions,
    summarize_scalars,
    trajectory_repeatability,
)
from lidarperf.trajectory import Trajectory


def _trajectory(offset: float = 0.0) -> Trajectory:
    return Trajectory(
        timestamps_ns=np.array([0, 1_000_000_000, 2_000_000_000], dtype=np.int64),
        positions_m=np.array(
            [[0.0, 0.0, 0.0], [1.0 + offset, 0.0, 0.0], [2.0, 0.0, 0.0]],
            dtype=np.float64,
        ),
        quaternions_xyzw=np.array(
            [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]],
            dtype=np.float64,
        ),
        body_frame="body",
    )


def test_scalar_summary_has_explicit_distribution_statistics() -> None:
    result = summarize_scalars([1.0, 2.0, 3.0, 4.0, 5.0])
    assert result["count"] == 5
    assert result["median"] == 3.0
    assert result["std"] == pytest.approx(np.std([1, 2, 3, 4, 5]))
    assert result["p95"] == pytest.approx(4.8)


def test_scalar_distributions_ignore_non_numeric_and_non_shared_values() -> None:
    result = scalar_distributions(
        [
            {"wall": 1.0, "ok": True, "backend": "runexec", "only_first": 1},
            {"wall": 2.0, "ok": False, "backend": "runexec"},
        ]
    )
    assert set(result) == {"wall"}
    assert result["wall"]["mean"] == 1.5


def test_trajectory_repeatability_is_all_pairwise_without_hidden_alignment() -> None:
    result = trajectory_repeatability([_trajectory(), _trajectory(0.3), _trajectory(-0.3)])
    assert result["trial_pair_count"] == 3
    assert result["timestamp_sets_identical"] is True
    assert result["common_pose_count"]["minimum"] == 3.0
    assert result["maximum_pose_translation_delta_m"] == pytest.approx(0.6)
    assert result["maximum_pose_rotation_delta_deg"] == pytest.approx(0.0)
    assert result["translation_pairwise_rmse_m"]["maximum"] > 0.0
