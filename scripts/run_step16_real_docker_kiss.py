"""Run KISS-ICP in Docker on evalio-normalized real Hilti LiDAR scans."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

import numpy as np
import yaml

from lidarperf.backends import DockerBackend, DockerMount, DockerRunSpec
from lidarperf.backends.evalio import expected_evalio_result_paths, load_evalio_trajectory
from lidarperf.spec.models import BenchmarkProtocol
from lidarperf.trajectory import EvaluationSupport, evaluate_trajectory, load_tum

SCHEMA = "lidarperf.step16-docker-kiss-validation.v1"
INPUT_SCHEMA = "lidarperf.step16-input.v1"

KISS_CONFIG = {
    "out_dir": "/output/kiss",
    "data": {"max_range": 120.0, "min_range": 0.5, "deskew": False},
    "mapping": {"voxel_size": 1.0, "max_points_per_voxel": 20},
    "registration": {
        "max_num_iterations": 500,
        "convergence_criterion": 0.0001,
        "max_num_threads": 1,
    },
    "adaptive_threshold": {"initial_threshold": 2.0, "min_motion_th": 0.1},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validation_protocol(root: Path) -> BenchmarkProtocol:
    data = yaml.safe_load((root / "protocols/lo/se3_v1.yaml").read_text(encoding="utf-8"))
    data["trajectory"]["association"] = {
        "mode": "nearest",
        "max_time_delta_ns": 10_000_000,
    }
    return BenchmarkProtocol.model_validate(data)


def _export_real_input(dataset_name: str, length: int, destination: Path) -> dict:
    from evalio import datasets as ds

    parsed = ds.parse_config({"name": dataset_name, "length": length})
    if isinstance(parsed, ds.DatasetConfigError):
        raise RuntimeError(f"cannot resolve evalio dataset {dataset_name}: {parsed}")
    sequence, _ = parsed[0]
    lidar_params = sequence.lidar_params()
    lidar_t_imu = np.asarray(sequence.imu_T_lidar().inverse().to_mat(), dtype=np.float64)

    scans_dir = destination / "scans"
    scans_dir.mkdir(parents=True, exist_ok=True)
    semantic_hash = hashlib.sha256()
    scans: list[dict] = []
    for index, measurement in enumerate(sequence.lidar()):
        if index >= length:
            break
        points = np.asarray(measurement.to_vec_positions(), dtype=np.float64)
        point_times = np.asarray(measurement.to_vec_stamps(), dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3:
            raise RuntimeError(f"unexpected evalio point shape at scan {index}: {points.shape}")
        if point_times.shape != (points.shape[0],):
            raise RuntimeError(f"point timestamp count mismatch at scan {index}")
        stamp_ns = int(measurement.stamp.to_nsec())
        filename = f"{index:06d}.npz"
        np.savez(scans_dir / filename, points=points, point_times_s=point_times)
        semantic_hash.update(stamp_ns.to_bytes(8, "little", signed=False))
        semantic_hash.update(np.asarray(points.shape, dtype=np.int64).tobytes())
        semantic_hash.update(points.tobytes(order="C"))
        semantic_hash.update(point_times.tobytes(order="C"))
        scans.append(
            {
                "index": index,
                "file": filename,
                "stamp_ns": stamp_ns,
                "point_count": int(points.shape[0]),
            }
        )

    if len(scans) != length:
        raise RuntimeError(f"requested {length} LiDAR scans but evalio yielded {len(scans)}")

    manifest = {
        "schema_version": INPUT_SCHEMA,
        "dataset": dataset_name,
        "sequence_id": dataset_name.replace("/", "_"),
        "scan_count": len(scans),
        "normalized_input_content_sha256": semantic_hash.hexdigest(),
        "lidar_params": {
            "num_rows": int(lidar_params.num_rows),
            "num_columns": int(lidar_params.num_columns),
            "min_range_m": float(lidar_params.min_range),
            "max_range_m": float(lidar_params.max_range),
            "rate_hz": float(lidar_params.rate),
            "brand": str(lidar_params.brand),
            "model": str(lidar_params.model),
        },
        "lidar_T_imu": lidar_t_imu.tolist(),
        "point_timestamp_semantics": "seconds_relative_to_scan_start",
        "scan_timestamp_semantics": "scan_start_int64_nanoseconds",
        "kiss_config": KISS_CONFIG,
        "scans": scans,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (destination / "kiss_config.yaml").write_text(
        yaml.safe_dump(KISS_CONFIG, sort_keys=True), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evalio-results", type=Path, required=True)
    parser.add_argument("--dataset", default="hilti_2022/basement_2")
    parser.add_argument("--pipeline", default="kiss")
    parser.add_argument("--length", type=int, default=120)
    parser.add_argument("--image", default="lidarperf-step16-kiss:1.3.0")
    parser.add_argument(
        "--output", type=Path, default=Path("docs/validation/step16_docker_kiss_hilti.json")
    )
    args = parser.parse_args()
    if args.length <= 0:
        raise ValueError("length must be positive")

    root = Path(__file__).resolve().parents[1]
    work = (root / ".step16-docker-kiss").resolve()
    if work.exists():
        shutil.rmtree(work)
    input_dir = work / "input"
    output_dir = work / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir()

    exported = _export_real_input(args.dataset, args.length, input_dir)
    evalio_paths = expected_evalio_result_paths(
        args.evalio_results, dataset=args.dataset, pipeline=args.pipeline
    )
    protocol = _validation_protocol(root)
    native_estimate = load_evalio_trajectory(
        evalio_paths.estimate, body_frame=protocol.trajectory.evaluation_frame
    )
    reference = load_evalio_trajectory(
        evalio_paths.ground_truth, body_frame=protocol.trajectory.evaluation_frame
    )
    support = EvaluationSupport(
        start_ns=int(exported["scans"][0]["stamp_ns"]),
        end_ns=int(exported["scans"][-1]["stamp_ns"]),
    )
    native_eval = evaluate_trajectory(native_estimate, reference, protocol, support=support)

    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    cpu_cores = tuple(affinity[:1])
    backend = DockerBackend()
    capability = backend.probe_capability()
    if not capability.daemon_reachable:
        raise RuntimeError(capability.reason or "Docker daemon is unreachable")

    process_log = work / "docker.log"
    spec = DockerRunSpec(
        image=args.image,
        mounts=(
            DockerMount(source=input_dir, target="/input", read_only=True),
            DockerMount(source=output_dir, target="/output", read_only=False),
        ),
        cpu_cores=cpu_cores,
        memory_limit_bytes=2 * 1024 * 1024 * 1024,
        network="none",
        environment={"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
        timeout_s=180.0,
    )
    execution = backend.execute(spec, combined_output_log=process_log)
    if not execution.succeeded:
        tail = process_log.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(
            "Docker KISS execution failed: "
            f"return={execution.return_code}, timeout={execution.timed_out}\n{tail}"
        )

    estimator_meta = json.loads((output_dir / "estimator.json").read_text(encoding="utf-8"))
    if estimator_meta.get("version") != "1.3.0":
        raise RuntimeError(f"unexpected KISS version: {estimator_meta.get('version')!r}")
    docker_estimate = load_tum(
        output_dir / "trajectory.tum", body_frame=protocol.trajectory.evaluation_frame
    )
    docker_eval = evaluate_trajectory(docker_estimate, reference, protocol, support=support)

    if len(docker_estimate) != args.length:
        raise RuntimeError(
            f"Docker KISS produced {len(docker_estimate)} poses for {args.length} scans"
        )
    if docker_eval.association.matched_pose_count < int(args.length * 0.95):
        raise RuntimeError(
            "too few Docker KISS poses associated to ground truth: "
            f"{docker_eval.association.matched_pose_count}"
        )
    if not docker_eval.temporal_coverage_pass:
        raise RuntimeError(
            "Docker KISS trajectory failed temporal coverage: "
            f"{docker_eval.association.temporal_coverage:.6f}"
        )
    if docker_eval.ape_translation_m is None or docker_eval.ape_rotation_deg is None:
        raise RuntimeError("Docker KISS validation did not produce required APE metrics")

    evidence = {
        "schema_version": SCHEMA,
        "validation_scope": "real_estimator_real_dataset_docker_functional_integration",
        "performance_authoritative": False,
        "authority_reason": (
            "ordinary GitHub-hosted runner; Docker v0.1 intentionally does not claim "
            "authoritative container process CPU/memory accounting"
        ),
        "dataset": {
            "id": args.dataset,
            "requested_lidar_scans": args.length,
            "normalized_input_content_sha256": exported["normalized_input_content_sha256"],
            "input_support": {"start_ns": support.start_ns, "end_ns": support.end_ns},
            "lidar_params": exported["lidar_params"],
            "point_timestamp_semantics": exported["point_timestamp_semantics"],
        },
        "estimator": estimator_meta,
        "container": {
            "execution_metadata": execution.execution_metadata(),
            "image": execution.image.model_dump(mode="json"),
            "wall_time_s": execution.wall_time_s,
            "return_code": execution.return_code,
            "timed_out": execution.timed_out,
            "process_log_sha256": _sha256(process_log),
            "dockerfile_sha256": _sha256(root / "docker/validation/kiss-evalio/Dockerfile"),
            "runner_sha256": _sha256(root / "docker/validation/kiss-evalio/runner.py"),
        },
        "docker_result": {
            "pose_count": len(docker_estimate),
            "trajectory_sha256": _sha256(output_dir / "trajectory.tum"),
            "metrics": docker_eval.metric_values(),
        },
        "native_evalio_reference_path": {
            "pipeline": args.pipeline,
            "pose_count": len(native_estimate),
            "estimate_sha256": _sha256(evalio_paths.estimate),
            "ground_truth_sha256": _sha256(evalio_paths.ground_truth),
            "metrics": native_eval.metric_values(),
            "comparison_scope": (
                "descriptive cross-backend integration check only; execution/thread environments "
                "are not declared performance-comparable"
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False))
    shutil.rmtree(work)


if __name__ == "__main__":
    main()
