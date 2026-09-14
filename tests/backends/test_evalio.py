from __future__ import annotations

from pathlib import Path

import pytest

from lidarperf.backends.evalio import (
    EvalioBackend,
    EvalioOutputError,
    build_evalio_run_command,
    expected_evalio_result_paths,
    parse_evalio_trajectory,
)
from lidarperf.spec import load_protocol
from lidarperf.trajectory import evaluate_trajectory

ROOT = Path(__file__).resolve().parents[2]


def test_build_evalio_run_command_is_shell_free() -> None:
    command = build_evalio_run_command(
        dataset="hilti_2022/basement_2",
        pipeline="kiss",
        output_dir="results",
        length=120,
    )
    assert command.argv == (
        "evalio",
        "run",
        "-o",
        "results",
        "-d",
        "hilti_2022/basement_2",
        "-p",
        "kiss",
        "-l",
        "120",
    )


def test_evalio_result_paths_follow_upstream_layout(tmp_path: Path) -> None:
    paths = expected_evalio_result_paths(
        tmp_path,
        dataset="hilti_2022/basement_2",
        pipeline="kiss",
    )
    expected_root = tmp_path / "hilti_2022" / "basement_2"
    assert paths.estimate == expected_root / "kiss.csv"
    assert paths.ground_truth == expected_root / "gt.csv"


@pytest.mark.parametrize(
    "dataset",
    ["", "hilti_2022", "/hilti_2022/basement_2", "hilti_2022/../secret", "a\\b"],
)
def test_evalio_dataset_path_rejects_ambiguous_or_unsafe_names(dataset: str) -> None:
    with pytest.raises(ValueError):
        expected_evalio_result_paths("results", dataset=dataset, pipeline="kiss")


def test_parse_evalio_trajectory_ignores_metadata_without_losing_nanoseconds() -> None:
    text = """# status: complete
# type: experiment
# timestamp, x, y, z, qx, qy, qz, qw
1720000000.123456789,1.0,2.0,3.0,0.0,0.0,0.0,1.0
1720000000.223456789,2.0,2.0,3.0,0.0,0.0,0.0,1.0
"""
    trajectory = parse_evalio_trajectory(text)
    assert trajectory.timestamps_ns.tolist() == [
        1_720_000_000_123_456_789,
        1_720_000_000_223_456_789,
    ]
    assert trajectory.positions_m.tolist() == [[1.0, 2.0, 3.0], [2.0, 2.0, 3.0]]


def test_parse_evalio_trajectory_rejects_wrong_field_count() -> None:
    with pytest.raises(EvalioOutputError, match="expected 8 evalio trajectory fields"):
        parse_evalio_trajectory("1.0,0,0,0,0,0,1\n")


def test_parse_evalio_trajectory_rejects_empty_result() -> None:
    with pytest.raises(EvalioOutputError, match="contains no pose rows"):
        parse_evalio_trajectory("# status: failed\n")


def test_evalio_csv_can_flow_into_lidarperf_metrics() -> None:
    protocol = load_protocol(ROOT / "protocols/lo/se3_v1.yaml").document
    text = """# timestamp, x, y, z, qx, qy, qz, qw
0.000000000,0,0,0,0,0,0,1
1.000000000,1,0,0,0,0,0,1
2.000000000,2,0,0,0,0,0,1
"""
    estimate = parse_evalio_trajectory(text)
    reference = parse_evalio_trajectory(text)
    evaluation = evaluate_trajectory(estimate, reference, protocol)
    assert evaluation.association.matched_pose_count == 3
    assert evaluation.ape_translation_m is not None
    assert evaluation.ape_translation_m.rmse == pytest.approx(0.0, abs=1e-12)
    assert evaluation.ape_rotation_deg is not None
    assert evaluation.ape_rotation_deg.rmse == pytest.approx(0.0, abs=1e-12)


def test_backend_requires_installed_evalio_for_command(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = EvalioBackend()
    monkeypatch.setattr(
        backend,
        "probe_capability",
        lambda: type(
            "Capability",
            (),
            {"installed": False, "reason": "not installed"},
        )(),
    )
    with pytest.raises(RuntimeError, match="not installed"):
        backend.command(
            dataset="hilti_2022/basement_2",
            pipeline="kiss",
            output_dir="results",
        )
