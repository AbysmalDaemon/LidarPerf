from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lidarperf.spec import load_protocol
from lidarperf.spec.enums import AlignmentMode
from lidarperf.spec.models import BenchmarkProtocol
from lidarperf.trajectory import (
    EvaluationSupport,
    Trajectory,
    TrajectoryAssociationError,
    evaluate_trajectory,
)

ROOT = Path(__file__).resolve().parents[2]


def _trajectory(timestamps: list[int], positions: list[list[float]]) -> Trajectory:
    return Trajectory(
        timestamps_ns=np.asarray(timestamps, dtype=np.int64),
        positions_m=np.asarray(positions, dtype=np.float64),
        quaternions_xyzw=np.asarray([[0.0, 0.0, 0.0, 1.0]] * len(timestamps)),
    )


def _protocol() -> BenchmarkProtocol:
    base = load_protocol(ROOT / "protocols/lo/se3_v1.yaml").document
    trajectory = base.trajectory.model_copy(
        update={
            "alignment": AlignmentMode.NONE,
            "relative_error_windows": (),
        }
    )
    return base.model_copy(update={"trajectory": trajectory})


def test_explicit_input_support_prevents_full_ground_truth_from_penalizing_prefix() -> None:
    reference = _trajectory(
        [0, 10, 20, 30, 40, 50, 60],
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 2, 0], [1, 2, 0], [2, 2, 0]],
    )
    estimate = reference.subset([1, 2, 3])
    protocol = _protocol()

    without_support = evaluate_trajectory(estimate, reference, protocol)
    with_support = evaluate_trajectory(
        estimate,
        reference,
        protocol,
        support=EvaluationSupport(start_ns=10, end_ns=30),
    )

    assert without_support.association.temporal_coverage == pytest.approx(1 / 3)
    assert with_support.association.temporal_coverage == pytest.approx(1.0)
    assert with_support.association.distance_coverage == pytest.approx(1.0)
    assert with_support.association.input_support_start_ns == 10
    assert with_support.association.input_support_end_ns == 30
    assert with_support.association.coverage_support_start_ns == 10
    assert with_support.association.coverage_support_end_ns == 30
    assert with_support.temporal_coverage_pass is True


def test_input_support_is_clipped_to_reference_for_accuracy_coverage() -> None:
    reference = _trajectory(
        [10, 20, 30],
        [[0, 0, 0], [1, 0, 0], [1, 1, 0]],
    )
    evaluation = evaluate_trajectory(
        reference,
        reference,
        _protocol(),
        support=EvaluationSupport(start_ns=0, end_ns=40),
    )

    assert evaluation.association.input_support_start_ns == 0
    assert evaluation.association.input_support_end_ns == 40
    assert evaluation.association.coverage_support_start_ns == 10
    assert evaluation.association.coverage_support_end_ns == 30
    assert evaluation.association.temporal_coverage == pytest.approx(1.0)
    assert evaluation.association.distance_coverage == pytest.approx(1.0)
    assert evaluation.temporal_coverage_pass is True


def test_input_support_without_reference_overlap_is_rejected() -> None:
    reference = _trajectory([10, 20, 30], [[0, 0, 0], [1, 0, 0], [1, 1, 0]])
    with pytest.raises(TrajectoryAssociationError, match="does not overlap reference trajectory"):
        evaluate_trajectory(
            reference,
            reference,
            _protocol(),
            support=EvaluationSupport(start_ns=0, end_ns=5),
        )


def test_association_only_counts_estimates_inside_declared_support() -> None:
    reference = _trajectory(
        [0, 10, 20, 30, 40],
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 2, 0]],
    )
    evaluation = evaluate_trajectory(
        reference,
        reference,
        _protocol(),
        support=EvaluationSupport(start_ns=10, end_ns=30),
    )
    assert evaluation.association.matched_pose_count == 3
    assert evaluation.association.temporal_coverage == pytest.approx(1.0)


def test_metric_values_retain_input_and_evaluable_support() -> None:
    reference = _trajectory(
        [10, 20, 30],
        [[0, 0, 0], [1, 0, 0], [1, 1, 0]],
    )
    evaluation = evaluate_trajectory(
        reference,
        reference,
        _protocol(),
        support=EvaluationSupport(start_ns=0, end_ns=40),
    )
    values = evaluation.metric_values()

    assert values["coverage.input_support_start_ns"] == 0
    assert values["coverage.input_support_end_ns"] == 40
    assert values["coverage.support_start_ns"] == 10
    assert values["coverage.support_end_ns"] == 30
