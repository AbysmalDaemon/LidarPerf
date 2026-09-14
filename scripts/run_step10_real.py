"""Produce the first real repeated-run LidarPerf result bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import yaml

from lidarperf.bundle import DatasetFingerprintClass, DatasetRecord, MethodSourceRecord
from lidarperf.host import probe_host
from lidarperf.runset import run_evalio_repeated_benchmark
from lidarperf.spec import sha256_fingerprint
from lidarperf.spec.enums import MeasurementClass
from lidarperf.trajectory import EvaluationSupport

_DATASET = "hilti_2022/basement_2"
_PIPELINE = "kiss"
_KISS_DEFAULTS = {
    "convergence_criterion": 0.0001,
    "deskew": False,
    "initial_threshold": 2.0,
    "max_num_iterations": 500,
    "max_num_threads": 0,
    "max_points_per_voxel": 20,
    "min_motion_th": 0.1,
    "voxel_size": 1.0,
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_sequence(dataset_name: str, length: int):
    from evalio import datasets as ds

    parsed = ds.parse_config({"name": dataset_name, "length": length})
    if isinstance(parsed, ds.DatasetConfigError):
        raise RuntimeError(f"cannot resolve evalio dataset {dataset_name}: {parsed}")
    return parsed[0][0]


def _input_support(sequence, requested_lidar_scans: int) -> EvaluationSupport:
    timestamps: list[int] = []
    for measurement in sequence.lidar():
        timestamps.append(int(measurement.stamp.to_nsec()))
        if len(timestamps) >= requested_lidar_scans:
            break
    if len(timestamps) != requested_lidar_scans:
        raise RuntimeError(
            f"requested {requested_lidar_scans} LiDAR scans but dataset yielded {len(timestamps)}"
        )
    return EvaluationSupport(start_ns=timestamps[0], end_ns=timestamps[-1])


def _dataset_record(sequence) -> DatasetRecord:
    entries: list[dict[str, object]] = []
    ground_truth_sha256: str | None = None
    files = list(sequence.files())
    for index, declared in enumerate(files):
        path = declared if isinstance(declared, Path) else sequence.folder / declared
        resolved = Path(path)
        digest = _sha256_file(resolved)
        try:
            relative_path = resolved.relative_to(sequence.folder).as_posix()
        except ValueError:
            relative_path = resolved.name
        entries.append(
            {
                "path": relative_path,
                "size_bytes": resolved.stat().st_size,
                "sha256": digest,
            }
        )
        if index == len(files) - 1:
            ground_truth_sha256 = digest

    entries.sort(key=lambda item: str(item["path"]))
    manifest_sha256 = sha256_fingerprint(entries)
    return DatasetRecord(
        id=sequence.full_name,
        provider=sequence.dataset_name(),
        sequence=sequence.seq_name,
        fingerprint_class=DatasetFingerprintClass.EXACT,
        content_sha256=manifest_sha256,
        manifest_sha256=manifest_sha256,
        ground_truth_sha256=ground_truth_sha256,
        metadata={
            "fingerprint_algorithm": "sha256-canonical-file-manifest-v1",
            "files": entries,
        },
    )


def _write_integration_protocol(root: Path, destination: Path) -> None:
    data = yaml.safe_load((root / "protocols/lo/se3_v1.yaml").read_text(encoding="utf-8"))
    data["protocol"] = {
        "id": "lidarperf/lo-se3-hilti-step10",
        "version": 1,
    }
    data["trajectory"]["association"] = {
        "mode": "nearest",
        "max_time_delta_ns": 10_000_000,
    }
    data["repetition"]["warmup_trials"] = 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )


def _kiss_version() -> str:
    from evalio.pipelines import PipelineNotFound, get_pipeline

    pipeline = get_pipeline(_PIPELINE)
    if isinstance(pipeline, PipelineNotFound):
        raise RuntimeError("evalio installation does not contain KISS-ICP")
    return str(pipeline.version())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--length", type=int, default=120)
    parser.add_argument("--measured-trials", type=int, default=5)
    parser.add_argument("--warmup-trials", type=int, default=1)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    if args.bundle.exists():
        raise RuntimeError(f"refusing to replace existing bundle: {args.bundle}")
    if args.workspace.exists():
        shutil.rmtree(args.workspace)
    args.workspace.mkdir(parents=True)

    sequence = _resolve_sequence(_DATASET, args.length)
    dataset = _dataset_record(sequence)
    support = _input_support(sequence, args.length)
    protocol_path = args.workspace / "step10-protocol.yaml"
    _write_integration_protocol(root, protocol_path)
    host = probe_host(data_path=sequence.folder)
    kiss_version = _kiss_version()

    manifest, report = run_evalio_repeated_benchmark(
        protocol_path=protocol_path,
        dataset=_DATASET,
        pipeline=_PIPELINE,
        length=args.length,
        input_support=support,
        dataset_record=dataset,
        algorithm_config={
            "pipeline": _PIPELINE,
            "pipeline_version": kiss_version,
            "parameter_source": "evalio 0.6.x KISS-ICP defaults",
            "parameters": _KISS_DEFAULTS,
        },
        method_version=kiss_version,
        method_source=MethodSourceRecord(repository="https://github.com/PRBonn/kiss-icp"),
        bundle_dir=args.bundle,
        workspace=args.workspace / "run",
        measurement_class=MeasurementClass.CONTROLLED,
        measured_trials=args.measured_trials,
        warmup_trials=args.warmup_trials,
        host_snapshot=host,
        execution_metadata={
            "performance_authoritative": False,
            "performance_authority_reason": (
                "GitHub-hosted runner; repeated BenchExec accounting validates run-set "
                "semantics but is not a stable performance baseline"
            ),
        },
    )

    aggregate = json.loads((args.bundle / "aggregate.json").read_text(encoding="utf-8"))
    summary = {
        "bundle": str(args.bundle),
        "conformance_status": manifest.conformance_status.value,
        "dataset_content_sha256": manifest.dataset_content_sha256,
        "measurement_class": manifest.measurement_class.value,
        "protocol_sha256": manifest.protocol.resolved_sha256,
        "result_id": str(manifest.result_id),
        "successful_trials": aggregate["successful_trials"],
        "failed_trials": aggregate["failed_trials"],
        "trial_count": manifest.trial_count,
        "warmup_trials": aggregate["metrics"]["warmups"]["count"],
        "verification_status": report.status.value,
        "wall_time_s": aggregate["metrics"]["resources"].get("wall_time_s"),
        "trajectory_repeatability": aggregate["metrics"].get("trajectory_repeatability"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
