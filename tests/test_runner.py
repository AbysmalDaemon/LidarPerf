from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lidarperf.backends import (
    BenchExecCapability,
    CommandExecutionResult,
    CommandSpec,
    EvalioCapability,
    EvalioResultPaths,
    ExecutionMeasurements,
    ResourceLimits,
)
from lidarperf.bundle import DatasetFingerprintClass, DatasetRecord, VerificationStatus
from lidarperf.runner import BenchmarkRunError, run_evalio_benchmark
from lidarperf.spec.enums import MeasurementClass
from lidarperf.trajectory import evaluate_trajectory, parse_tum

TRAJECTORY = """0.000000000 0 0 0 0 0 0 1
1.000000000 1 0 0 0 0 0 1
2.000000000 1 1 0 0 0 0 1
3.000000000 2 1 1 0 0 0 1
"""


class FakeEvalioBackend:
    def probe_capability(self) -> EvalioCapability:
        return EvalioCapability(installed=True, executable="fake-evalio", version="0.6.1")

    def command(
        self,
        *,
        dataset: str,
        pipeline: str,
        output_dir: str | Path,
        length: int | None = None,
    ) -> CommandSpec:
        del length
        root = Path(output_dir) / dataset
        root.mkdir(parents=True, exist_ok=True)
        csv_text = "# timestamp,x,y,z,qx,qy,qz,qw\n" + TRAJECTORY.replace(" ", ",")
        (root / f"{pipeline}.csv").write_text(csv_text, encoding="utf-8")
        (root / "gt.csv").write_text(csv_text, encoding="utf-8")
        return CommandSpec(argv=("fake-evalio", "run"))

    def result_paths(
        self,
        output_dir: str | Path,
        *,
        dataset: str,
        pipeline: str,
    ) -> EvalioResultPaths:
        root = Path(output_dir) / dataset
        return EvalioResultPaths(
            estimate=root / f"{pipeline}.csv",
            ground_truth=root / "gt.csv",
        )

    def evaluate(self, output_dir, *, dataset, pipeline, protocol, support=None):
        del output_dir, dataset, pipeline
        estimate = parse_tum(TRAJECTORY, body_frame=protocol.trajectory.evaluation_frame)
        reference = parse_tum(TRAJECTORY, body_frame=protocol.trajectory.evaluation_frame)
        return evaluate_trajectory(estimate, reference, protocol, support=support)


class FakeBenchExecBackend:
    def __init__(self, *, controlled_ready: bool = True) -> None:
        self.controlled_ready = controlled_ready
        self.executed = False

    def probe_capability(self) -> BenchExecCapability:
        return BenchExecCapability(
            backend_version="runexec 3.35",
            installed=True,
            controlled_ready=self.controlled_ready,
            reason=None if self.controlled_ready else "test cgroup failure",
        )

    def execute(
        self,
        command: CommandSpec,
        *,
        combined_output_log: Path,
        limits: ResourceLimits | None = None,
    ) -> CommandExecutionResult:
        self.executed = True
        combined_output_log.parent.mkdir(parents=True, exist_ok=True)
        combined_output_log.write_text("fake evalio output\n", encoding="utf-8")
        return CommandExecutionResult(
            backend_version="runexec 3.35",
            backend_returncode=0,
            command=command,
            limits=limits or ResourceLimits(),
            measurements=ExecutionMeasurements(
                wall_time_s=1.25,
                cpu_time_s=1.0,
                peak_memory_bytes=123456,
            ),
            return_value=0,
            combined_output_log=combined_output_log,
            raw_measurements={
                "walltime": "1.25s",
                "cputime": "1.0s",
                "memory": "123456B",
            },
        )


def dataset_record() -> DatasetRecord:
    digest = hashlib.sha256(b"test-dataset").hexdigest()
    return DatasetRecord(
        id="example/sequence",
        provider="example",
        sequence="sequence",
        fingerprint_class=DatasetFingerprintClass.EXACT,
        content_sha256=digest,
        ground_truth_sha256=digest,
    )


def test_run_evalio_benchmark_writes_verified_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "result.lperf"
    manifest, report = run_evalio_benchmark(
        protocol_path="protocols/lo/se3_v1.yaml",
        dataset="example/sequence",
        pipeline="kiss",
        length=4,
        input_support=None,
        dataset_record=dataset_record(),
        algorithm_config={"voxel_size": 1.0, "deskew": False},
        method_version="1.3.0",
        bundle_dir=bundle,
        workspace=tmp_path / "work",
        measurement_class=MeasurementClass.EXPLORATORY,
        evalio_backend=FakeEvalioBackend(),
        execution_backend=FakeBenchExecBackend(),
    )

    assert report.status == VerificationStatus.VALID
    assert manifest.measurement_class == MeasurementClass.EXPLORATORY
    assert manifest.conformance_status.value == "conformant"
    assert (bundle / "trials/0001/process.log").is_file()
    assert (bundle / "artifacts/evalio_estimate.csv").is_file()
    assert (bundle / "artifacts/evalio_ground_truth.csv").is_file()
    assert "trials/0001/resources.json" in manifest.file_inventory


def test_run_refuses_unready_benchexec_even_for_exploratory(tmp_path: Path) -> None:
    executor = FakeBenchExecBackend(controlled_ready=False)
    with pytest.raises(BenchmarkRunError, match="BenchExec process-tree accounting is unavailable"):
        run_evalio_benchmark(
            protocol_path="protocols/lo/se3_v1.yaml",
            dataset="example/sequence",
            pipeline="kiss",
            length=4,
            input_support=None,
            dataset_record=dataset_record(),
            algorithm_config={},
            method_version="1.3.0",
            bundle_dir=tmp_path / "result.lperf",
            workspace=tmp_path / "work",
            measurement_class=MeasurementClass.EXPLORATORY,
            evalio_backend=FakeEvalioBackend(),
            execution_backend=executor,
        )
    assert not executor.executed


@pytest.mark.parametrize(
    ("measurement_class", "minimum"),
    [
        (MeasurementClass.CONTROLLED, 5),
        (MeasurementClass.PUBLICATION, 10),
    ],
)
def test_stronger_measurement_classes_require_repeated_run_phase(
    tmp_path: Path,
    measurement_class: MeasurementClass,
    minimum: int,
) -> None:
    with pytest.raises(
        BenchmarkRunError,
        match=rf"{measurement_class.value}-class evidence requires at least {minimum}",
    ):
        run_evalio_benchmark(
            protocol_path="protocols/lo/se3_v1.yaml",
            dataset="example/sequence",
            pipeline="kiss",
            length=4,
            input_support=None,
            dataset_record=dataset_record(),
            algorithm_config={},
            method_version="1.3.0",
            bundle_dir=tmp_path / "result.lperf",
            workspace=tmp_path / "work",
            measurement_class=measurement_class,
            evalio_backend=FakeEvalioBackend(),
            execution_backend=FakeBenchExecBackend(),
        )
