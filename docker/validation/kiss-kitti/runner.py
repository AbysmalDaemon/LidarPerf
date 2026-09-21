from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from kiss_icp import __version__ as kiss_version
from kiss_icp.datasets.kitti import KITTIOdometryDataset
from kiss_icp.pipeline import OdometryPipeline
from pyquaternion import Quaternion

INPUT = Path("/input")
OUTPUT = Path("/output")
SEQUENCE = "00"


class _Step16OdometryPipeline(OdometryPipeline):
    """Normalize KISS-ICP 1.3.0 KITTI timestamps without changing their values.

    The 1.3.0 KITTI loader returns frame timestamps with shape ``(N, 1)`` while
    the pipeline's TUM writer converts each indexed timestamp with ``float()``.
    New NumPy versions reject converting a one-dimensional array to a scalar.
    Flattening the timestamp array here preserves every timestamp value and lets
    the unmodified KISS pipeline complete its normal output/evaluation path.
    """

    def _get_frames_timestamps(self) -> np.ndarray:
        timestamps = super()._get_frames_timestamps()
        return np.asarray(timestamps, dtype=np.float64).reshape(-1)


def _write_tum(path: Path, poses: np.ndarray, timestamps: np.ndarray) -> None:
    if len(poses) != len(timestamps):
        raise ValueError("pose and timestamp counts differ")
    lines: list[str] = []
    for pose, timestamp in zip(poses, timestamps, strict=True):
        tx, ty, tz = pose[:3, 3]
        qw, qx, qy, qz = Quaternion(matrix=pose, atol=0.01).elements
        lines.append(
            f"{float(timestamp):.9f} "
            f"{tx:.12f} {ty:.12f} {tz:.12f} "
            f"{qx:.12f} {qy:.12f} {qz:.12f} {qw:.12f}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


def main() -> None:
    manifest = json.loads((INPUT / "lidarperf_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "lidarperf.step16-kitti-input.v1":
        raise ValueError("unsupported Step 16 KITTI manifest")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    dataset = KITTIOdometryDataset(str(INPUT), sequence=SEQUENCE)
    expected = int(manifest["scan_count"])
    if len(dataset) != expected:
        raise ValueError(f"expected {expected} KITTI scans, found {len(dataset)}")

    pipeline = _Step16OdometryPipeline(
        dataset=dataset,
        config=INPUT / "kiss_config.yaml",
        visualize=False,
        n_scans=expected,
    )
    pipeline.run()

    timestamps = np.asarray(
        dataset.get_frames_timestamps(), dtype=np.float64
    ).reshape(-1)[:expected]
    raw_estimate = np.asarray(pipeline.poses[:expected], dtype=np.float64)
    raw_ground_truth = np.asarray(dataset.gt_poses[:expected], dtype=np.float64)
    _write_tum(OUTPUT / "trajectory.tum", raw_estimate, timestamps)
    _write_tum(OUTPUT / "ground_truth.tum", raw_ground_truth, timestamps)

    estimator = {
        "schema_version": "lidarperf.step16-estimator.v1",
        "name": "KISS-ICP",
        "version": str(kiss_version),
        "source_repository": "https://github.com/PRBonn/kiss-icp",
        "dataset_loader": "kiss_icp.datasets.kitti.KITTIOdometryDataset",
        "input_scan_count": expected,
        "evaluation_frame": "KITTI Velodyne LiDAR frame",
        "ground_truth_conversion": "inv(Tr) @ T_camera @ Tr",
        "compatibility_adapter": {
            "reason": "KISS-ICP 1.3.0 KITTI timestamps are Nx1; current NumPy rejects float(array([timestamp])) in the upstream TUM writer",
            "operation": "flatten frame timestamp array from Nx1 to N before the upstream KISS output path",
            "timestamp_values_changed": False,
        },
        "configuration": manifest["kiss_config"],
        "outputs": {
            "estimate": "trajectory.tum",
            "ground_truth": "ground_truth.tum",
        },
    }
    (OUTPUT / "estimator.json").write_text(
        json.dumps(estimator, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
