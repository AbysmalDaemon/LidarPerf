from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from lidarperf.spec import load_protocol
from lidarperf.spec.enums import AlignmentMode, TimestampAssociationMode
from lidarperf.spec.models import BenchmarkProtocol, RelativeErrorWindow, TimestampAssociation
from lidarperf.trajectory import (
    Trajectory,
    TrajectoryAssociationError,
    TrajectoryFormatError,
    TrajectoryMetricError,
    associate_trajectories,
    evaluate_trajectory,
    parse_tum,
    serialize_tum,
    validate_trajectory,
)


def _trajectory(
    timestamps: list[int] | np.ndarray,
    positions: list[list[float]] | np.ndarray,
    quaternions: list[list[float]] | np.ndarray | None = None,
    *,
    body_frame: str = "body",
) -> Trajectory:
    count = len(timestamps)
    if quaternions is None:
        quaternions = [[0.0, 0.0, 0.0, 1.0]] * count
    return Trajectory(
        timestamps_ns=np.asarray(timestamps, dtype=np.int64),
        positions_m=np.asarray(positions, dtype=np.float64),
        quaternions_xyzw=np.asarray(quaternions, dtype=np.float64),
        body_frame=body_frame,
    )


ROOT = Path(__file__).resolve().parents[2]


def _protocol(
    *,
    association: TimestampAssociation | None = None,
    alignment: AlignmentMode = AlignmentMode.SE3,
    windows: tuple[RelativeErrorWindow, ...] = (),
    coverage: float = 0.98,
) -> BenchmarkProtocol:
    base = load_protocol(ROOT / "protocols/lo/se3_v1.yaml").document
    trajectory = base.trajectory.model_copy(
        update={
            "association": association or TimestampAssociation(mode=TimestampAssociationMode.EXACT),
            "alignment": alignment,
            "relative_error_windows": windows,
        }
    )
    validity = base.validity.model_copy(update={"temporal_coverage_min": coverage})
    return base.model_copy(update={"trajectory": trajectory, "validity": validity})


def test_tum_parser_preserves_nan_for_structural_reporting() -> None:
    trajectory = parse_tum("0 nan 0 0 0 0 0 1\n")
    report = validate_trajectory(trajectory)
    assert report.valid is False
    assert report.invalid_translation_count == 1
    assert report.invalid_pose_count == 1


def test_tum_timestamp_round_trip_is_exact_to_one_nanosecond() -> None:
    trajectory = parse_tum("123.000000001 1 2 3 0 0 0 1\n")
    assert trajectory.timestamps_ns.tolist() == [123_000_000_001]
    assert parse_tum(serialize_tum(trajectory)).timestamps_ns.tolist() == [123_000_000_001]


def test_tum_parser_rejects_sub_nanosecond_timestamp() -> None:
    with pytest.raises(TrajectoryFormatError, match="sub-nanosecond"):
        parse_tum("0.0000000001 0 0 0 0 0 0 1\n")


def test_validation_counts_rotation_and_timestamp_failures() -> None:
    trajectory = _trajectory(
        [0, 10, 10],
        [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
        [[0, 0, 0, 1], [0, 0, 0, 2], [0, 0, 0, 1]],
    )
    report = validate_trajectory(trajectory)
    assert report.invalid_rotation_count == 1
    assert report.duplicate_timestamp_count == 1
    assert report.non_increasing_timestamp_count == 1
    assert report.valid is False


def test_nearest_association_uses_tolerance_and_stable_tie_break() -> None:
    reference = _trajectory([0, 10, 20], [[0, 0, 0], [1, 0, 0], [2, 0, 0]])
    estimate = _trajectory([5, 11, 30], [[0, 0, 0], [1, 0, 0], [3, 0, 0]])
    associated = associate_trajectories(
        estimate,
        reference,
        TimestampAssociation(mode=TimestampAssociationMode.NEAREST, max_time_delta_ns=5),
    )
    assert associated.reference_indices.tolist() == [0, 1]
    assert associated.time_deltas_ns.tolist() == [-5, -1]
    assert associated.stats.unmatched_estimate_pose_count == 1


def test_interpolate_reference_uses_linear_translation_and_slerp() -> None:
    quarter_turn = [0.0, 0.0, math.sin(math.pi / 4), math.cos(math.pi / 4)]
    reference = _trajectory(
        [0, 20],
        [[0, 0, 0], [2, 0, 0]],
        [[0, 0, 0, 1], quarter_turn],
    )
    estimate = _trajectory([10], [[1, 0, 0]])
    associated = associate_trajectories(
        estimate,
        reference,
        TimestampAssociation(
            mode=TimestampAssociationMode.INTERPOLATE_REFERENCE,
            max_reference_gap_ns=20,
        ),
    )
    expected = [0.0, 0.0, math.sin(math.pi / 8), math.cos(math.pi / 8)]
    assert associated.reference_indices.tolist() == [-1]
    assert np.allclose(associated.reference.positions_m[0], [1, 0, 0])
    assert np.allclose(associated.reference.quaternions_xyzw[0], expected)
    assert associated.stats.interpolated_pose_count == 1


def test_interpolation_never_extrapolates() -> None:
    reference = _trajectory([10, 20], [[0, 0, 0], [1, 0, 0]])
    estimate = _trajectory([0], [[0, 0, 0]])
    with pytest.raises(TrajectoryAssociationError, match="produced no pose pairs"):
        associate_trajectories(
            estimate,
            reference,
            TimestampAssociation(
                mode=TimestampAssociationMode.INTERPOLATE_REFERENCE,
                max_reference_gap_ns=20,
            ),
        )


def test_full_se3_alignment_removes_only_global_rigid_offset() -> None:
    timestamps = np.arange(4, dtype=np.int64)
    reference = _trajectory(
        timestamps,
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
    )
    angle = math.pi / 2
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.float64)
    translation = np.array([5.0, 2.0, 0.0])
    estimate_positions = np.array(
        [rotation.T @ (position - translation) for position in reference.positions_m]
    )
    estimate_quaternion = [0.0, 0.0, -math.sin(angle / 2), math.cos(angle / 2)]
    estimate = _trajectory(
        timestamps,
        estimate_positions,
        [estimate_quaternion] * len(timestamps),
    )
    evaluation = evaluate_trajectory(estimate, reference, _protocol())
    assert evaluation.ape_translation_m is not None
    assert evaluation.ape_rotation_deg is not None
    assert evaluation.ape_translation_m.rmse < 1e-12
    assert evaluation.ape_rotation_deg.rmse < 1e-8
    assert np.allclose(evaluation.alignment.rotation, rotation)
    assert np.allclose(evaluation.alignment.translation_m, translation)


def test_se3_alignment_rejects_collinear_trajectory() -> None:
    reference = _trajectory([0, 1, 2], [[0, 0, 0], [1, 0, 0], [2, 0, 0]])
    with pytest.raises(TrajectoryMetricError, match="underdetermined"):
        evaluate_trajectory(reference, reference, _protocol())


def test_distance_window_rpe_uses_reference_path_and_reports_normalized_drift() -> None:
    timestamps = np.arange(21, dtype=np.int64)
    reference_positions = np.column_stack(
        (np.arange(21, dtype=np.float64), np.zeros(21), np.zeros(21))
    )
    estimate_positions = reference_positions * 1.1
    reference = _trajectory(timestamps, reference_positions)
    estimate = _trajectory(timestamps, estimate_positions)
    window = RelativeErrorWindow(
        distance_m=10.0,
        pairing="all_starts_nearest_reference_distance",
        relative_tolerance=0.01,
    )
    evaluation = evaluate_trajectory(
        estimate,
        reference,
        _protocol(alignment=AlignmentMode.NONE, windows=(window,)),
    )
    result = evaluation.relative_errors[0]
    assert result.pair_count == 11
    assert result.translation_error_m is not None
    assert result.translation_error_percent is not None
    assert result.translation_error_m.rmse == pytest.approx(1.0)
    assert result.translation_error_percent.rmse == pytest.approx(10.0)


def test_requested_relative_window_can_be_unavailable_without_fabricating_value() -> None:
    reference = _trajectory([0, 1, 2], [[0, 0, 0], [1, 0, 0], [1, 1, 0]])
    window = RelativeErrorWindow(
        distance_m=100.0,
        pairing="all_starts_nearest_reference_distance",
        relative_tolerance=0.1,
    )
    evaluation = evaluate_trajectory(reference, reference, _protocol(windows=(window,)))
    result = evaluation.relative_errors[0]
    assert result.pair_count == 0
    assert result.translation_error_m is None
    values = evaluation.metric_values()
    assert values["rpe.distance_100m.pair_count"] == 0
    assert "rpe.distance_100m.translation.rmse_m" not in values


def test_temporal_coverage_is_reference_duration_fraction() -> None:
    reference = _trajectory(
        [0, 10, 20, 30, 40],
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 2, 0]],
    )
    estimate = reference.subset([1, 2, 3])
    evaluation = evaluate_trajectory(estimate, reference, _protocol(coverage=0.8))
    assert evaluation.association.temporal_coverage == pytest.approx(0.5)
    assert evaluation.association.distance_coverage is not None
    assert 0.0 < evaluation.association.distance_coverage < 1.0
    assert evaluation.temporal_coverage_pass is False


def test_metric_values_never_use_naked_ate_or_rpe_names() -> None:
    trajectory = _trajectory(
        [0, 1, 2, 3],
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
    )
    evaluation = evaluate_trajectory(trajectory, trajectory, _protocol())
    values = evaluation.metric_values()
    assert values["ape.translation.rmse_m"] == pytest.approx(0.0)
    assert values["ape.rotation.rmse_deg"] == pytest.approx(0.0)
    assert "ATE" not in values
    assert "RPE" not in values
