"""One-shot Step 7 finalization: close protocol gaps and refresh documentation."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement target, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_protocol_schema() -> None:
    models = ROOT / "src/lidarperf/spec/models.py"
    old_model = (
        "class RelativeErrorWindow(StrictModel):\n"
        '    """Distance window requested for relative trajectory error."""\n'
        "\n"
        "    distance_m: float = Field(gt=0)\n"
    )
    new_model = (
        "class RelativeErrorWindow(StrictModel):\n"
        '    """Distance window plus explicit reference-path pairing semantics."""\n'
        "\n"
        "    distance_m: float = Field(gt=0)\n"
        '    pairing: Literal["all_starts_nearest_reference_distance"]\n'
        "    relative_tolerance: float = Field(ge=0, le=1)\n"
    )
    replace_once(models, old_model, new_model)

    old_windows = (
        "  relative_error_windows:\n"
        "    - distance_m: 10.0\n"
        "    - distance_m: 100.0\n"
    )
    new_windows = (
        "  relative_error_windows:\n"
        "    - distance_m: 10.0\n"
        "      pairing: all_starts_nearest_reference_distance\n"
        "      relative_tolerance: 0.1\n"
        "    - distance_m: 100.0\n"
        "      pairing: all_starts_nearest_reference_distance\n"
        "      relative_tolerance: 0.1\n"
    )
    for relative in ("protocols/lo/se3_v1.yaml", "protocols/lio/se3_v1.yaml"):
        replace_once(ROOT / relative, old_windows, new_windows)


def patch_dependencies() -> None:
    path = ROOT / "pyproject.toml"
    replace_once(
        path,
        """dependencies = [
  "pydantic>=2.8,<3",
  "PyYAML>=6.0,<7",
  "typer>=0.12,<1",
]""",
        """dependencies = [
  "numpy>=1.26,<3",
  "pydantic>=2.8,<3",
  "PyYAML>=6.0,<7",
  "typer>=0.12,<1",
]""",
    )


def patch_spec() -> None:
    path = ROOT / "SPEC.md"
    old = """## 26.3 Relative pose error

RPE MUST use explicitly declared windows.

Distance-window examples:

```text
10 m
100 m
```

Outputs SHOULD include:

- translational relative error in metres
- rotational relative error in degrees
- normalized translation %
- normalized rotation deg/m

The reference trajectory defines path-length windows.

The exact pairing/tolerance rule is protocol data.
"""
    new = """## 26.3 Relative pose error

RPE MUST use explicitly declared windows.

Distance-window examples:

```text
10 m
100 m
```

Each distance window MUST declare both its pairing rule and tolerance. The v0.1 generic
profile supports:

```yaml
relative_error_windows:
  - distance_m: 10.0
    pairing: all_starts_nearest_reference_distance
    relative_tolerance: 0.1
```

For `all_starts_nearest_reference_distance`:

1. cumulative path length is computed from the associated **reference** trajectory;
2. every associated reference pose is considered as a possible start;
3. the later endpoint whose reference path distance is closest to `distance_m` is chosen;
4. ties choose the earlier endpoint;
5. the pair is accepted only when
   `abs(actual_distance_m - distance_m) <= distance_m * relative_tolerance`;
6. overlapping windows are allowed;
7. the actual accepted reference distance distribution and pair count MUST be reported.

If no accepted pair exists for a requested window, that metric is unavailable. LidarPerf
MUST NOT fabricate a zero error.

Outputs SHOULD include:

- translational relative error in metres
- rotational relative error in degrees
- normalized translation %
- normalized rotation deg/m

The reference trajectory defines path-length windows. Pairing and tolerance are protocol
data and therefore participate in the protocol fingerprint.
"""
    replace_once(path, old, new)


def patch_spec_tests() -> None:
    path = ROOT / "tests/spec/test_models.py"
    old = """def test_relative_windows_must_be_in_increasing_order(lo_protocol_data: dict) -> None:
    lo_protocol_data["trajectory"]["relative_error_windows"] = [
        {"distance_m": 100.0},
        {"distance_m": 10.0},
    ]

    with pytest.raises(ValidationError, match="ordered by increasing distance"):
        BenchmarkProtocol.model_validate(lo_protocol_data)
"""
    new = """def test_relative_windows_must_be_in_increasing_order(lo_protocol_data: dict) -> None:
    lo_protocol_data["trajectory"]["relative_error_windows"] = [
        {
            "distance_m": 100.0,
            "pairing": "all_starts_nearest_reference_distance",
            "relative_tolerance": 0.1,
        },
        {
            "distance_m": 10.0,
            "pairing": "all_starts_nearest_reference_distance",
            "relative_tolerance": 0.1,
        },
    ]

    with pytest.raises(ValidationError, match="ordered by increasing distance"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_relative_windows_require_pairing_semantics(lo_protocol_data: dict) -> None:
    lo_protocol_data["trajectory"]["relative_error_windows"] = [{"distance_m": 10.0}]

    with pytest.raises(ValidationError, match="Field required"):
        BenchmarkProtocol.model_validate(lo_protocol_data)
"""
    replace_once(path, old, new)


def patch_readme() -> None:
    path = ROOT / "README.md"
    replace_once(
        path,
        """- a Linux BenchExec/`runexec` backend for process-tree wall time, CPU time, memory, CPU-core/NUMA constraints, resource-limit termination semantics, and an active controlled-readiness probe.

Real estimator/dataset orchestration and trajectory metrics are **not implemented yet**.
""",
        """- a Linux BenchExec/`runexec` backend for process-tree wall time, CPU time, memory, CPU-core/NUMA constraints, resource-limit termination semantics, and an active controlled-readiness probe;
- canonical trajectory parsing/validation, explicit timestamp association, rigid SE(3) alignment, APE, distance-window relative-pose errors, and coverage accounting.

Real estimator/dataset orchestration is **not implemented yet**.
""",
    )


def patch_distance_coverage() -> None:
    model_path = ROOT / "src/lidarperf/trajectory/model.py"
    replace_once(
        model_path,
        """    max_abs_time_delta_ns: int | None
    mean_abs_time_delta_ns: float | None
    temporal_coverage: float
""",
        """    max_abs_time_delta_ns: int | None
    mean_abs_time_delta_ns: float | None
    temporal_coverage: float
    distance_coverage: float | None
""",
    )
    replace_once(
        model_path,
        """            "coverage.temporal_fraction": self.association.temporal_coverage,
            "coverage.temporal_min_required": self.temporal_coverage_min,
            "coverage.temporal_pass": self.temporal_coverage_pass,
            "alignment.transform": self.alignment.as_dict(),
""",
        """            "coverage.temporal_fraction": self.association.temporal_coverage,
            "coverage.temporal_min_required": self.temporal_coverage_min,
            "coverage.temporal_pass": self.temporal_coverage_pass,
            "trajectory.estimate.invalid_pose_count": self.estimate_validation.invalid_pose_count,
            "trajectory.reference.invalid_pose_count": self.reference_validation.invalid_pose_count,
            "alignment.transform": self.alignment.as_dict(),
""",
    )
    replace_once(
        model_path,
        """        if self.association.max_abs_time_delta_ns is not None:
            values["association.max_abs_time_delta_ns"] = self.association.max_abs_time_delta_ns
""",
        """        if self.association.distance_coverage is not None:
            values["coverage.distance_fraction"] = self.association.distance_coverage
        if self.association.max_abs_time_delta_ns is not None:
            values["association.max_abs_time_delta_ns"] = self.association.max_abs_time_delta_ns
""",
    )

    association_path = ROOT / "src/lidarperf/trajectory/association.py"
    replace_once(
        association_path,
        """def _nearest_reference_index(reference_timestamps: np.ndarray, timestamp: int) -> int:
""",
        """def _path_length(positions: np.ndarray) -> float:
    if positions.shape[0] < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(positions, axis=0), axis=1).sum())


def _distance_coverage(reference: Trajectory, matched_reference: Trajectory) -> float | None:
    full_distance = _path_length(reference.positions_m)
    if full_distance <= np.finfo(np.float64).eps:
        return 1.0 if len(matched_reference) else 0.0
    matched_distance = _path_length(matched_reference.positions_m)
    return min(1.0, matched_distance / full_distance)


def _nearest_reference_index(reference_timestamps: np.ndarray, timestamp: int) -> int:
""",
    )
    replace_once(
        association_path,
        """        mean_abs_time_delta_ns=float(abs_deltas.mean()) if abs_deltas.size else None,
        temporal_coverage=_coverage(reference, matched_estimate.timestamps_ns),
    )
""",
        """        mean_abs_time_delta_ns=float(abs_deltas.mean()) if abs_deltas.size else None,
        temporal_coverage=_coverage(reference, matched_estimate.timestamps_ns),
        distance_coverage=_distance_coverage(reference, matched_reference),
    )
""",
    )

    test_path = ROOT / "tests/trajectory/test_trajectory.py"
    replace_once(
        test_path,
        """    assert evaluation.association.temporal_coverage == pytest.approx(0.5)
    assert evaluation.temporal_coverage_pass is False
""",
        """    assert evaluation.association.temporal_coverage == pytest.approx(0.5)
    assert evaluation.association.distance_coverage is not None
    assert 0.0 < evaluation.association.distance_coverage < 1.0
    assert evaluation.temporal_coverage_pass is False
""",
    )


def refresh_hashes() -> None:
    from lidarperf.spec import load_protocol

    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    identities = {
        "lidarperf/lo-se3@1": load_protocol(ROOT / "protocols/lo/se3_v1.yaml").resolved_sha256,
        "lidarperf/lio-se3@1": load_protocol(ROOT / "protocols/lio/se3_v1.yaml").resolved_sha256,
    }
    for identity, digest in identities.items():
        pattern = rf"^({re.escape(identity)}\s+)[0-9a-f]{{64}}$"
        text, count = re.subn(pattern, rf"\g<1>{digest}", text, count=1, flags=re.MULTILINE)
        if count != 1:
            raise RuntimeError(f"README: could not refresh hash for {identity}")
    readme.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hashes", action="store_true")
    args = parser.parse_args()
    if args.hashes:
        refresh_hashes()
        return

    patch_dependencies()
    patch_protocol_schema()
    patch_spec()
    patch_spec_tests()
    patch_readme()
    patch_distance_coverage()


if __name__ == "__main__":
    main()
