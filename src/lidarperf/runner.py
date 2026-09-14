"""Single-trial orchestration for complete evalio-backed LidarPerf result bundles."""

from __future__ import annotations

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
from lidarperf.spec import load_protocol, sha256_fingerprint
from lidarperf.spec.enums import MeasurementClass
from lidarperf.trajectory import EvaluationSupport, serialize_tum


class BenchmarkRunError(RuntimeError):
    """Raised when a complete benchmark trial cannot be produced honestly."""


class BenchmarkVerificationError(BenchmarkRunError):
    """Raised when a produced result bundle fails LidarPerf verification."""


def _algorithm_config_text(config: dict[str, Any]) -> str:
    return yaml.safe_dump(config, sort_keys=True, allow_unicode=True)


def _conformance_status(
    *,
    execution_succeeded: bool,
    temporal_coverage_pass: bool,
    estimate_invalid_pose_count: int,
    reference_invalid_pose_count: int,
) -> ConformanceStatus:
    if (
        execution_succeeded
        and temporal_coverage_pass
        and estimate_invalid_pose_count == 0
        and reference_invalid_pose_count == 0
    ):
        return ConformanceStatus.CONFORMANT
    return ConformanceStatus.NON_CONFORMANT


def run_evalio_benchmark(
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
    resource_limits: ResourceLimits | None = None,
    method_source: MethodSourceRecord | None = None,
    host_snapshot: HostSnapshot | None = None,
    evalio_backend: EvalioBackend | None = None,
    execution_backend: BenchExecBackend | None = None,
) -> tuple[ResultManifest, VerificationReport]:
    """Run one evalio experiment through BenchExec and emit a verified `.lperf` bundle.

    This is deliberately a single-trial primitive. Repetition and aggregate statistics
    belong to the next execution phase rather than being hidden inside this function.
    """

    protocol_source = Path(protocol_path)
    resolved = load_protocol(protocol_source)
    if dataset_record.id != dataset:
        raise ValueError("dataset_record.id must match the evalio dataset name")
    if measurement_class == MeasurementClass.PUBLICATION:
        raise BenchmarkRunError(
            "publication-class evidence requires repeated trials; use controlled for one trial"
        )

    evalio = evalio_backend or EvalioBackend()
    executor = execution_backend or BenchExecBackend()
    if measurement_class == MeasurementClass.CONTROLLED:
        capability = executor.probe_capability()
        if not capability.controlled_ready:
            raise BenchmarkRunError(
                "controlled BenchExec execution is unavailable: "
                f"{capability.reason or 'unknown capability failure'}"
            )

    working_root = Path(workspace)
    working_root.mkdir(parents=True, exist_ok=True)
    evalio_output = working_root / "evalio"
    process_log = working_root / "process.log"
    command = evalio.command(
        dataset=dataset,
        pipeline=pipeline,
        output_dir=evalio_output,
        length=length,
    )
    execution = executor.execute(
        command,
        combined_output_log=process_log,
        limits=resource_limits or ResourceLimits(),
    )
    if not execution.succeeded:
        raise BenchmarkRunError(
            "evalio process failed under BenchExec: "
            f"return={execution.return_value}, signal={execution.exit_signal}, "
            f"termination={execution.termination_reason}"
        )

    paths = evalio.result_paths(evalio_output, dataset=dataset, pipeline=pipeline)
    evaluation = evalio.evaluate(
        evalio_output,
        dataset=dataset,
        pipeline=pipeline,
        protocol=resolved.document,
        support=input_support,
    )
    estimate = load_evalio_trajectory(
        paths.estimate,
        body_frame=resolved.document.trajectory.evaluation_frame,
    )

    config_text = _algorithm_config_text(algorithm_config)
    config_sha256 = sha256_fingerprint(yaml.safe_load(config_text))
    evalio_capability = evalio.probe_capability()
    snapshot = host_snapshot or probe_host()
    conformance = _conformance_status(
        execution_succeeded=True,
        temporal_coverage_pass=evaluation.temporal_coverage_pass,
        estimate_invalid_pose_count=evaluation.estimate_validation.invalid_pose_count,
        reference_invalid_pose_count=evaluation.reference_validation.invalid_pose_count,
    )

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
            software={
                "lidarperf": __version__,
                "evalio": evalio_capability.version,
            },
            execution={
                "backend": execution.backend,
                "backend_version": execution.backend_version,
                "command_argv": list(command.argv),
                "timing_scope": resolved.document.timing.scope.value,
            },
        ),
    )
    writer.write_json(
        "trials/0001/trial.json",
        TrialRecord(
            trial_index=1,
            status=TrialStatus.SUCCESS,
            exit_code=execution.return_value,
            timed_out=execution.timed_out,
        ),
    )
    writer.write_json(
        "trials/0001/metrics.json",
        MetricsRecord(values=evaluation.metric_values()),
    )
    resources: dict[str, Any] = {
        "backend": execution.backend,
        "backend_version": execution.backend_version,
        "wall_time_s": execution.measurements.wall_time_s,
        "cpu_time_s": execution.measurements.cpu_time_s,
        "peak_memory_bytes": execution.measurements.peak_memory_bytes,
        "cpu_core_equivalents": execution.measurements.cpu_core_equivalents,
        "timed_out": execution.timed_out,
        "termination_reason": execution.termination_reason,
    }
    writer.write_json("trials/0001/resources.json", ResourcesRecord(values=resources))
    writer.write_text("trials/0001/trajectory.tum", serialize_tum(estimate))
    writer.copy_file("trials/0001/process.log", execution.combined_output_log)
    writer.copy_file("artifacts/evalio_estimate.csv", paths.estimate)
    writer.copy_file("artifacts/evalio_ground_truth.csv", paths.ground_truth)
    writer.write_json(
        "aggregate.json",
        AggregateRecord(
            successful_trials=1,
            failed_trials=0,
            metrics=evaluation.metric_values(),
        ),
    )
    manifest = writer.finalize(
        ResultManifestCore(
            lidarperf_version=__version__,
            result_id=uuid4(),
            created_at=datetime.now(UTC),
            protocol=ProtocolReference(
                id=resolved.document.protocol.id,
                version=resolved.document.protocol.version,
                resolved_sha256=resolved.resolved_sha256,
            ),
            track=resolved.document.track,
            method_name=pipeline,
            dataset_id=dataset_record.id,
            dataset_content_sha256=dataset_record.content_sha256,
            trial_count=1,
            measurement_class=measurement_class,
            conformance_status=conformance,
        )
    )
    report = verify_bundle(bundle_dir)
    if not report.valid:
        codes = ", ".join(issue.code for issue in report.issues)
        raise BenchmarkVerificationError(f"produced bundle failed verification: {codes}")
    return manifest, report
