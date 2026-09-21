from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
from kiss_icp import __version__ as kiss_version
from kiss_icp.pipeline import OdometryPipeline

INPUT = Path("/input")
OUTPUT = Path("/output")


class ExportedEvalioDataset:
    def __init__(self, manifest: dict) -> None:
        self.manifest = manifest
        self.sequence_id = str(manifest["sequence_id"])
        self.scans = list(manifest["scans"])
        self._timestamps = np.asarray(
            [int(scan["stamp_ns"]) * 1e-9 for scan in self.scans], dtype=np.float64
        )
        self._lidar_T_imu = np.asarray(manifest["lidar_T_imu"], dtype=np.float64)
        if self._lidar_T_imu.shape != (4, 4):
            raise ValueError("lidar_T_imu must be a 4x4 matrix")

    def __len__(self) -> int:
        return len(self.scans)

    def __getitem__(self, idx: int) -> tuple[np.ndarray, np.ndarray]:
        scan_path = INPUT / "scans" / self.scans[idx]["file"]
        with np.load(scan_path) as scan:
            points = np.asarray(scan["points"], dtype=np.float64)
            point_times = np.asarray(scan["point_times_s"], dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError(f"invalid point array shape in {scan_path}: {points.shape}")
        if point_times.shape != (points.shape[0],):
            raise ValueError(
                f"point timestamp count does not match point count in {scan_path}"
            )
        return points, point_times

    def get_frames_timestamps(self) -> np.ndarray:
        return self._timestamps

    def apply_calibration(self, poses: np.ndarray) -> np.ndarray:
        # evalio's KISS adapter saves kiss_pose * lidar_T_imu. Reproduce that
        # explicit frame conversion so the Docker output is in the same IMU/body
        # frame as evalio's normalized ground truth.
        return poses @ self._lidar_T_imu


def main() -> None:
    manifest = json.loads((INPUT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "lidarperf.step16-input.v1":
        raise ValueError("unsupported Step 16 input manifest")
    if not manifest.get("scans"):
        raise ValueError("Step 16 input manifest contains no scans")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    dataset = ExportedEvalioDataset(manifest)
    pipeline = OdometryPipeline(
        dataset=dataset,
        config=INPUT / "kiss_config.yaml",
        visualize=False,
        n_scans=len(dataset),
    )
    pipeline.run()

    result_dir = Path(pipeline.results_dir)
    trajectory = result_dir / f"{dataset.sequence_id}_poses_tum.txt"
    if not trajectory.is_file():
        raise FileNotFoundError(f"KISS output trajectory missing: {trajectory}")
    shutil.copy2(trajectory, OUTPUT / "trajectory.tum")

    estimator = {
        "schema_version": "lidarperf.step16-estimator.v1",
        "name": "KISS-ICP",
        "version": str(kiss_version),
        "source_repository": "https://github.com/PRBonn/kiss-icp",
        "input_scan_count": len(dataset),
        "configuration": manifest["kiss_config"],
        "output_trajectory": "trajectory.tum",
    }
    (OUTPUT / "estimator.json").write_text(
        json.dumps(estimator, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
