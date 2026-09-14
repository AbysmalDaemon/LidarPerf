"""Repeated evalio-backed benchmark orchestration for LidarPerf run sets."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from lidarperf import __version__
from lidarperf.backends import (
    BenchExecBackend,
    EvalioBackend,
    ResourceLimits,
    load_evalio_trajectory,
)
from lidarperf.bundle import (
    AggregateRecord,
    ConformanceStatus,
    DatasetRecord,
    EnvironmentRecord,
    MethodRecord,
    MethodSourceRecord,
    MetricsRecord,
    ProtocolReference,
    ResourcesRecord,
    ResultBundleWriter,
    ResultManifest,
    ResultManifestCore,
    TrialRecord,
    TrialStatus,
    VerificationReport,
    verify_bundle,
)
from lidarperf.host import HostSnapshot, probe_host
from lidarperf.repeatability import scalar_distributions, trajectory_repeatability
from lidarperf.runner import BenchmarkRunError, BenchmarkVerificationError
from lidarperf.spec import load_protocol, sha256_fingerprint
from lidarperf.spec.enums import MeasurementClass
from lidarperf.trajectory import EvaluationSupport, Trajectory, serialize_tum


def _required_trial_count(protocol, measurement_class: MeasurementClass) -> int:
    if measurement_class == MeasurementClass.EXPLORATORY:
        return protocol.repetition.exploratory_min_trials
    if measurement_class == MeasurementClass.CONTROLLED:
        return protocol.repetition.controlled_min_trials
    return protocol.repetition.publication_min_trials


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _algorithm_config_text(config: dict[str, Any]) -> str:
    return yaml.safe_dump(config, sort_keys=True, allow_unicode=True)


def _resource_values(execution, command_argv: tuple[str, ...]) -> dict[str, Any]:
    return {
        "backend": execution.backend,
        "backend_version": execution.backend_version,
        "command_argv": list(command_argv),
        "wall_time_s": execution.measurements.wall_time_s,
        "cpu_time_s": execution.measurements.cpu_time_s,
        "peak_memory_bytes": execution.measurements.peak_memory_bytes,
        "cpu_core_equivalents": execution.measurements.cpu_core_equivalents,
        "timed_out": execution.timed_out,
        "termination_reason": execution.termination_reason,
    }


def run_evalio_repeated_benchmark(
    *,
    protocol_path: str | Path,
    dataset: str,
    pipeline: str,
    length: int | None,
    input_support: EvaluationSupport | None,
    dataset_record: DatasetRecord,
    algorithm_config: dict[str, Any],
    method_version: str | None,
    bundle_dir: str | Path,
    workspace: str | Path,
    measurement_class: MeasurementClass = MeasurementClass.CONTROLLED,
    measured_trials: int | None = None,
    warmup_trials: int | None = None,
    resource_limits: ResourceLimits | None = None,
    method_source: MethodSourceRecord | None = None,
    host_snapshot: HostSnapshot | None = None,
    execution_metadata: dict[str, Any] | None = None,
    evalio_backend: EvalioBackend | None = None,
    execution_backend: BenchExecBackend | None = None,
) -> tuple[ResultManifest, VerificationReport]:
    """Run warmups plus repeated measured trials and emit a verified run-set bundle."""

    protocol_source = Path(protocol_path)
    resolved = load_protocol(protocol_source)
    protocol = resolved.document
    if dataset_record.id != dataset:
        raise ValueError("dataset_record.id must match the evalio dataset name")
    if measurement_class not in protocol.measurement.allowed_classes:
        raise BenchmarkRunError(
            f"protocol does not allow measurement class {measurement_class.value!r}"
        )

    minimum = _required_trial_count(protocol, measurement_class)
    measured_count = minimum if measured_trials is None else measured_trials
    if measured_count < minimum:
        raise BenchmarkRunError(
            f"{measurement_class.value}-class evidence requires at least {minimum} measured "
            f"trials under this protocol; requested {measured_count}"
        )
    if measured_count < 1:
        raise ValueError("measured_trials must be at least one")

    warmup_count = protocol.repetition.warmup_trials if warmup_trials is None else warmup_trials
    if warmup_count < 0:
        raise ValueError("warmup_trials must be non-negative")

    evalio = evalio_backend or EvalioBackend()
    executor = execution_backend or BenchExecBackend()
    capability = executor.probe_capability()
    if not capability.controlled_ready:
        raise BenchmarkRunError(
            "BenchExec process-tree accounting is unavailable: "
            f"{capability.reason or 'unknown capability failure'}"
        )

    working_root = Path(workspace)
    working_root.mkdir(parents=True, exist_ok=True)
    limits = resource_limits or ResourceLimits()

    warmups: list[tuple[Any, tuple[str, ...]]] = []
    for warmup_index in range(1, warmup_count + 1):
        warmup_root = working_root / "warmups" / f"{warmup_index:04d}"
        command = evalio.command(
            dataset=dataset,
            pipeline=pipeline,
            output_dir=warmup_root / "evalio",
            length=length,
        )
        execution = executor.execute(
            command,
            combined_output_log=warmup_root / "process.log",
            limits=limits,
        )
        warmups.append((execution, command.argv))
        if not execution.succeeded:
            raise BenchmarkRunError(
                f"warmup trial {warmup_index} failed under BenchExec: "
                f"return={execution.return_value}, signal={execution.exit_signal}, "
                f"termination={execution.termination_reason}"
            )

    measured: list[dict[str, Any]] = []
    successful_metric_records: list[dict[str, Any]] = []
    successful_resource_records: list[dict[str, Any]] = []
    successful_trajectories: list[Trajectory] = []
    first_ground_truth: Path | None = None
    ground_truth_sha256: str | None = None
    all_conformant = True

    for trial_index in range(1, measured_count + 1):
        trial_root = working_root / "trials" / f"{trial_index:04d}"
        command = evalio.command(
            dataset=dataset,
            pipeline=pipeline,
            output_dir=trial_root / "evalio",
            length=length,
        )
        execution = executor.execute(
            command,
            combined_output_log=trial_root / "process.log",
            limits=limits,
        )
        resources = _resource_values(execution, command.argv)
        record: dict[str, Any] = {
            "index": trial_index,
            "command": command,
            "execution": execution,
            "resources": resources,
            "metrics": {},
            "trajectory": None,
            "paths": None,
            "conformant": False,
        }

        if execution.succeeded:
            paths = evalio.result_paths(trial_root / "evalio", dataset=dataset, pipeline=pipeline)
            evaluation = evalio.evaluate(
                trial_root / "evalio",
                dataset=dataset,
                pipeline=pipeline,
                protocol=protocol,
                support=input_support,
            )
            trajectory = load_evalio_trajectory(
                paths.estimate,
                body_frame=protocol.trajectory.evaluation_frame,
            )
            metrics = evaluation.metric_values()
            trial_conformant = (
                evaluation.temporal_coverage_pass
                and evaluation.estimate_validation.invalid_pose_count == 0
                and evaluation.reference_validation.invalid_pose_count == 0
            )
            record.update(
                {
                    "metrics": metrics,
                    "trajectory": trajectory,
                    "paths": paths,
                    "conformant": trial_conformant,
                }
            )
            successful_metric_records.append(metrics)
            successful_resource_records.append(resources)
            successful_trajectories.append(trajectory)

            current_gt_hash = _sha256_file(paths.ground_truth)
            if ground_truth_sha256 is None:
                ground_truth_sha256 = current_gt_hash
                first_ground_truth = paths.ground_truth
            elif current_gt_hash != ground_truth_sha256:
                raise BenchmarkRunError(
                    "evalio ground-truth output changed across nominally identical measured trials"
                )
            all_conformant = all_conformant and trial_conformant
        else:
            all_conformant = False

        measured.append(record)

    config_text = _algorithm_config_text(algorithm_config)
    config_sha256 = sha256_fingerprint(yaml.safe_load(config_text))
    evalio_capability = evalio.probe_capability()
    snapshot = host_snapshot or probe_host()

    first_execution = measured[0]["execution"]
    first_command = measured[0]["command"]
    execution_record: dict[str, Any] = {
        "backend": first_execution.backend,
        "backend_version": first_execution.backend_version,
        "command_argv": list(first_command.argv),
        "command_argv_scope": (
            "representative first measured trial; exact argv is stored in every trial resources record"
        ),
        "timing_scope": protocol.timing.scope.value,
        "warmup_trials": warmup_count,
        "measured_trials": measured_count,
        "statistics_population": "successful measured trials only",
    }
    extra_execution = dict(execution_metadata or {})
    overlap = set(execution_record) & set(extra_execution)
    if overlap:
        raise ValueError(f"execution_metadata cannot replace reserved keys: {sorted(overlap)}")
    execution_record.update(extra_execution)

    writer = ResultBundleWriter(bundle_dir)
    writer.write_text("protocol.yaml", protocol_source.read_text(encoding="utf-8"))
    writer.write_text("config/algorithm.yaml", config_text)
    writer.write_json(
        "method.json",
        MethodRecord(
            name=pipeline,
            version=method_version,
            source=method_source or MethodSourceRecord(),
            config_sha256=config_sha256,
            build={},
        ),
    )
    writer.write_json("dataset.json", dataset_record)
    writer.write_json(
        "environment.json",
        EnvironmentRecord(
            measurement_class=measurement_class,
            host=snapshot.model_dump(mode="json"),
            software={"lidarperf": __version__, "evalio": evalio_capability.version},
            execution=execution_record,
        ),
    )

    for warmup_index, (execution, command_argv) in enumerate(warmups, start=1):
        directory = f"warmups/{warmup_index:04d}"
        writer.write_json(
            f"{directory}/resources.json",
            ResourcesRecord(values=_resource_values(execution, command_argv)),
        )
        writer.copy_file(f"{directory}/process.log", execution.combined_output_log)

    successful_trials = 0
    failed_trials = 0
    for record in measured:
        trial_index = record["index"]
        directory = f"trials/{trial_index:04d}"
        execution = record["execution"]
        if execution.succeeded:
            successful_trials += 1
            status = TrialStatus.SUCCESS
            trajectory_text = serialize_tum(record["trajectory"])
        else:
            failed_trials += 1
            status = TrialStatus.FAILED
            trajectory_text = ""

        writer.write_json(
            f"{directory}/trial.json",
            TrialRecord(
                trial_index=trial_index,
                status=status,
                exit_code=execution.return_value,
                timed_out=execution.timed_out,
            ),
        )
        writer.write_json(f"{directory}/metrics.json", MetricsRecord(values=record["metrics"]))
        writer.write_json(
            f"{directory}/resources.json",
            ResourcesRecord(values=record["resources"]),
        )
        writer.write_text(f"{directory}/trajectory.tum", trajectory_text)
        writer.copy_file(f"{directory}/process.log", execution.combined_output_log)
        if record["paths"] is not None:
            writer.copy_file(
                f"artifacts/trials/{trial_index:04d}/evalio_estimate.csv",
                record["paths"].estimate,
            )

    if first_ground_truth is not None:
        writer.copy_file("artifacts/evalio_ground_truth.csv", first_ground_truth)

    aggregate_metrics: dict[str, Any] = {
        "summary_schema": "lidarperf.repeatability.v1",
        "statistics_semantics": {
            "population": "successful measured trials only",
            "std": "population_ddof_0",
            "percentiles": "linear_interpolation",
            "warmups_excluded": True,
        },
        "warmups": {"count": warmup_count},
        "trial_metrics": scalar_distributions(successful_metric_records),
        "resources": scalar_distributions(successful_resource_records),
    }
    if len(successful_trajectories) >= 2:
        aggregate_metrics["trajectory_repeatability"] = trajectory_repeatability(
            successful_trajectories
        )

    writer.write_json(
        "aggregate.json",
        AggregateRecord(
            successful_trials=successful_trials,
            failed_trials=failed_trials,
            metrics=aggregate_metrics,
        ),
    )
    manifest = writer.finalize(
        ResultManifestCore(
            lidarperf_version=__version__,
            result_id=uuid4(),
            created_at=datetime.now(UTC),
            protocol=ProtocolReference(
                id=protocol.protocol.id,
                version=protocol.protocol.version,
                resolved_sha256=resolved.resolved_sha256,
            ),
            track=protocol.track,
            method_name=pipeline,
            dataset_id=dataset_record.id,
            dataset_content_sha256=dataset_record.content_sha256,
            trial_count=measured_count,
            measurement_class=measurement_class,
            conformance_status=(
                ConformanceStatus.CONFORMANT
                if all_conformant and failed_trials == 0
                else ConformanceStatus.NON_CONFORMANT
            ),
        )
    )
    report = verify_bundle(bundle_dir)
    if not report.valid:
        codes = ", ".join(issue.code for issue in report.issues)
        raise BenchmarkVerificationError(f"produced run-set bundle failed verification: {codes}")
    return manifest, report
