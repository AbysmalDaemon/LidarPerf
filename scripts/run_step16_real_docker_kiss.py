"""Run KISS-ICP in Docker on the PRBonn KITTI sequence-00 mini fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

import yaml

from lidarperf.backends import DockerBackend, DockerMount, DockerRunSpec
from lidarperf.spec.models import BenchmarkProtocol
from lidarperf.trajectory import EvaluationSupport, evaluate_trajectory, load_tum

SCHEMA = "lidarperf.step16-docker-kiss-kitti-validation.v1"
INPUT_SCHEMA = "lidarperf.step16-kitti-input.v1"
SOURCE_URL = "https://uni-bonn.sciebo.de/s/KwOuBiPZi8vSz2O/download"
SOURCE_REPOSITORY = "https://github.com/PRBonn/SHINE_mapping"
SOURCE_REPOSITORY_COMMIT = "0fbaf8a2a8ebd64d9819c81f823fe0ecc5d344bb"
KITTI_CAPTURE_RATE_HZ = 10.0
KITTI_RATE_SOURCE = "https://www.cvlibs.net/datasets/kitti/raw_data.php"

KISS_CONFIG = {
    "out_dir": "/output/kiss",
    "data": {"max_range": 100.0, "min_range": 0.0, "deskew": False},
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


def _aggregate_sha256(paths: list[Path], *, root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def _find_kitti_sequence(source: Path, *, length: int) -> tuple[Path, Path]:
    candidates: list[tuple[Path, Path]] = []
    for velodyne in source.rglob("velodyne"):
        if not velodyne.is_dir():
            continue
        scan_count = len(list(velodyne.glob("*.bin")))
        sequence = velodyne.parent
        if scan_count >= length and (sequence / "calib.txt").is_file():
            candidates.append((sequence, velodyne))
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected exactly one KITTI sequence with >= {length} scans, found {len(candidates)}"
        )
    return candidates[0]


def _find_required_file(source: Path, sequence: Path, filename: str) -> Path:
    direct = sequence / filename
    if direct.is_file():
        return direct
    matches = [path for path in source.rglob(filename) if path.is_file()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {filename}, found {len(matches)}")
    return matches[0]


def _find_optional_file(source: Path, sequence: Path, filename: str) -> Path | None:
    direct = sequence / filename
    if direct.is_file():
        return direct
    matches = [path for path in source.rglob(filename) if path.is_file()]
    if len(matches) > 1:
        raise RuntimeError(f"expected at most one {filename}, found {len(matches)}")
    return matches[0] if matches else None


def _copy_first_lines(source: Path, destination: Path, count: int) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    if len(lines) < count:
        raise RuntimeError(f"{source} contains {len(lines)} rows, expected at least {count}")
    destination.write_text("\n".join(lines[:count]) + "\n", encoding="utf-8")


def _write_reconstructed_times(destination: Path, count: int) -> None:
    values = (f"{index / KITTI_CAPTURE_RATE_HZ:.9f}" for index in range(count))
    destination.write_text("\n".join(values) + "\n", encoding="utf-8")


def _prepare_input(source: Path, destination: Path, *, length: int, archive: Path) -> dict:
    sequence, velodyne = _find_kitti_sequence(source, length=length)
    calib = _find_required_file(source, sequence, "calib.txt")
    source_times = _find_optional_file(source, sequence, "times.txt")
    poses = _find_required_file(source, sequence, "poses.txt")
    scans = sorted(velodyne.glob("*.bin"))[:length]
    if len(scans) != length:
        raise RuntimeError(f"expected {length} scans, found {len(scans)}")

    canonical_sequence = destination / "sequences" / "00"
    canonical_velodyne = canonical_sequence / "velodyne"
    canonical_poses = destination / "poses"
    canonical_velodyne.mkdir(parents=True, exist_ok=True)
    canonical_poses.mkdir(parents=True, exist_ok=True)
    shutil.copy2(calib, canonical_sequence / "calib.txt")
    canonical_times = canonical_sequence / "times.txt"
    if source_times is None:
        _write_reconstructed_times(canonical_times, length)
        timestamp_source = {
            "mode": "reconstructed_frame_index_fixed_rate",
            "source_times_file_present": False,
            "capture_rate_hz": KITTI_CAPTURE_RATE_HZ,
            "rule": "timestamp_seconds = zero_based_frame_index / 10.0",
            "authority": "official KITTI documentation states synchronized data are captured at 10 Hz",
            "authority_url": KITTI_RATE_SOURCE,
        }
    else:
        _copy_first_lines(source_times, canonical_times, length)
        timestamp_source = {
            "mode": "published_times_file",
            "source_times_file_present": True,
            "source_relative_path": source_times.relative_to(source).as_posix(),
        }
    _copy_first_lines(poses, canonical_poses / "00.txt", length)
    for scan in scans:
        shutil.copy2(scan, canonical_velodyne / scan.name)

    selected_sources = [calib, poses, *scans]
    if source_times is not None:
        selected_sources.append(source_times)
    manifest = {
        "schema_version": INPUT_SCHEMA,
        "dataset": "KITTI Odometry",
        "sequence": "00",
        "subset": f"first {length} frames",
        "scan_count": length,
        "source_provider": "PRBonn/SHINE_mapping convenience subset",
        "source_url": SOURCE_URL,
        "source_repository": SOURCE_REPOSITORY,
        "source_repository_commit": SOURCE_REPOSITORY_COMMIT,
        "source_archive_sha256": _sha256(archive),
        "selected_source_content_sha256": _aggregate_sha256(selected_sources, root=source),
        "body_frame": "KITTI Velodyne LiDAR frame",
        "ground_truth_source_frame": "KITTI camera reference frame",
        "ground_truth_body_conversion": "inv(Tr) @ T_camera @ Tr",
        "timestamp_source": timestamp_source,
        "canonical_times_sha256": _sha256(canonical_times),
        "point_timestamp_semantics": (
            "compact KITTI fixture contains no per-point timestamps; KISS deskew is disabled"
        ),
        "kiss_config": KISS_CONFIG,
    }
    (destination / "lidarperf_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (destination / "kiss_config.yaml").write_text(
        yaml.safe_dump(KISS_CONFIG, sort_keys=True), encoding="utf-8"
    )
    return manifest


def _validation_protocol(root: Path) -> BenchmarkProtocol:
    data = yaml.safe_load((root / "protocols/lo/se3_v1.yaml").read_text(encoding="utf-8"))
    data["preprocessing"]["motion_compensation"] = {
        "input_state": "raw",
        "performed_by": "none",
        "motion_source": "none",
        "parameters": {},
    }
    data["preprocessing"]["timestamp_reconstruction"] = {
        "owner": "dataset",
        "parameters": {
            "rule": "timestamp_seconds = zero_based_frame_index / 10.0",
            "capture_rate_hz": KITTI_CAPTURE_RATE_HZ,
            "reason": "PRBonn compact KITTI fixture omits sequences/00/times.txt",
        },
    }
    return BenchmarkProtocol.model_validate(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--length", type=int, default=100)
    parser.add_argument("--image", default="lidarperf-step16-kiss:1.3.0")
    parser.add_argument(
        "--output", type=Path, default=Path("docs/validation/step16_docker_kiss_kitti.json")
    )
    args = parser.parse_args()
    if args.length <= 1:
        raise ValueError("length must be greater than one")
    source = args.source.resolve()
    archive = args.archive.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"KITTI source directory does not exist: {source}")
    if not archive.is_file():
        raise FileNotFoundError(f"KITTI source archive does not exist: {archive}")

    root = Path(__file__).resolve().parents[1]
    work = (root / ".step16-docker-kiss").resolve()
    if work.exists():
        shutil.rmtree(work)
    input_dir = work / "input"
    output_dir = work / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir()

    manifest = _prepare_input(source, input_dir, length=args.length, archive=archive)
    protocol = _validation_protocol(root)
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
        environment={
            "MKL_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
        },
        timeout_s=300.0,
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
    if estimator_meta.get("evaluation_frame") != manifest["body_frame"]:
        raise RuntimeError("container and host disagree on the evaluation body frame")

    estimate = load_tum(output_dir / "trajectory.tum", body_frame="body")
    reference = load_tum(output_dir / "ground_truth.tum", body_frame="body")
    if len(estimate) != args.length or len(reference) != args.length:
        raise RuntimeError(
            "unexpected trajectory lengths: "
            f"estimate={len(estimate)}, reference={len(reference)}, expected={args.length}"
        )
    support = EvaluationSupport(
        start_ns=int(estimate.timestamps_ns[0]),
        end_ns=int(estimate.timestamps_ns[-1]),
    )
    evaluation = evaluate_trajectory(estimate, reference, protocol, support=support)
    if evaluation.association.matched_pose_count != args.length:
        raise RuntimeError(
            f"exact timestamp association matched {evaluation.association.matched_pose_count} "
            f"of {args.length} poses"
        )
    if not evaluation.temporal_coverage_pass:
        raise RuntimeError(
            "Docker KISS trajectory failed temporal coverage: "
            f"{evaluation.association.temporal_coverage:.6f}"
        )
    if evaluation.ape_translation_m is None or evaluation.ape_rotation_deg is None:
        raise RuntimeError("Docker KISS validation did not produce required APE metrics")

    evidence = {
        "schema_version": SCHEMA,
        "validation_scope": "real_estimator_real_dataset_docker_functional_integration",
        "performance_authoritative": False,
        "authority_reason": (
            "ordinary GitHub-hosted runner; Docker v0.1 intentionally does not claim "
            "authoritative container process CPU/memory accounting"
        ),
        "dataset": manifest,
        "validation_protocol": {
            "base": "protocols/lo/se3_v1.yaml",
            "association": "exact",
            "motion_compensation": "raw input; none performed; compact KITTI has no point times",
            "timestamp_reconstruction": manifest["timestamp_source"],
        },
        "estimator": estimator_meta,
        "container": {
            "execution_metadata": execution.execution_metadata(),
            "image": execution.image.model_dump(mode="json"),
            "wall_time_s": execution.wall_time_s,
            "return_code": execution.return_code,
            "timed_out": execution.timed_out,
            "process_log_sha256": _sha256(process_log),
            "dockerfile_sha256": _sha256(root / "docker/validation/kiss-kitti/Dockerfile"),
            "runner_sha256": _sha256(root / "docker/validation/kiss-kitti/runner.py"),
        },
        "result": {
            "estimate_pose_count": len(estimate),
            "reference_pose_count": len(reference),
            "trajectory_sha256": _sha256(output_dir / "trajectory.tum"),
            "ground_truth_sha256": _sha256(output_dir / "ground_truth.tum"),
            "metrics": evaluation.metric_values(),
        },
        "scientific_scope": (
            "functional real-data integration evidence for the Docker execution path; not an "
            "authoritative performance baseline or a publication-grade KISS-ICP ranking"
        ),
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
