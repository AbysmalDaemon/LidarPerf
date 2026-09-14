from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
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
from lidarperf.bundle import (
    DatasetFingerprintClass,
    DatasetRecord,
    VerificationStatus,
    verify_bundle,
)
from lidarperf.host import (
    CgroupSnapshot,
    CPUSnapshot,
    HostSnapshot,
    MemorySnapshot,
    OSSnapshot,
    RuntimeSnapshot,
    StorageSnapshot,
)
from lidarperf.runner import BenchmarkRunError
from lidarperf.runset import run_evalio_repeated_benchmark
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
        return CommandSpec(argv=("fake-evalio", "run", "-o", str(output_dir)))

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
    def __init__(self, *, fail_calls: set[int] | None = None) -> None:
        self.calls = 0
        self.fail_calls = fail_calls or set()

    def probe_capability(self) -> BenchExecCapability:
        return BenchExecCapability(
            backend_version="runexec 3.35",
            installed=True,
            controlled_ready=True,
            reason=None,
        )

    def execute(
        self,
        command: CommandSpec,
        *,
        combined_output_log: Path,
        limits: ResourceLimits | None = None,
    ) -> CommandExecutionResult:
        self.calls += 1
        combined_output_log.parent.mkdir(parents=True, exist_ok=True)
        combined_output_log.write_text(f"fake call {self.calls}\n", encoding="utf-8")
        failed = self.calls in self.fail_calls
        wall = 1.0 + self.calls / 10.0
        return CommandExecutionResult(
            backend_version="runexec 3.35",
            backend_returncode=0,
            command=command,
            limits=limits or ResourceLimits(),
            measurements=ExecutionMeasurements(
                wall_time_s=wall,
                cpu_time_s=wall * 0.8,
                peak_memory_bytes=100000 + self.calls,
            ),
            return_value=7 if failed else 0,
            combined_output_log=combined_output_log,
            raw_measurements={
                "walltime": f"{wall}s",
                "cputime": f"{wall * 0.8}s",
                "memory": f"{100000 + self.calls}B",
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


def controlled_host_snapshot() -> HostSnapshot:
    return HostSnapshot(
        captured_at=datetime.now(UTC),
        host_sha256="0" * 64,
        os=OSSnapshot(
            system="Linux",
            distribution="Test Linux",
            distribution_version="1",
            kernel_release="test",
            kernel_version="test",
            architecture="x86_64",
            libc="glibc",
        ),
        cpu=CPUSnapshot(
            model="test-cpu",
            architecture="x86_64",
            logical_cpus=1,
            physical_cores=1,
            affinity_cpus=(0,),
            governors=("performance",),
        ),
        memory=MemorySnapshot(
            total_bytes=1_000_000,
            available_bytes=900_000,
            swap_total_bytes=0,
            swap_free_bytes=0,
        ),
        cgroups=CgroupSnapshot(
            version="v2",
            controllers=("cpu", "cpuset", "memory"),
            writable=True,
        ),
        storage=StorageSnapshot(
            inspected=True,
            exists=True,
            filesystem_type="ext4",
            network_filesystem=False,
        ),
        runtime=RuntimeSnapshot(benchexec_available=True, runexec_available=True),
    )


def test_controlled_runset_separates_warmup_and_five_measured_trials(tmp_path: Path) -> None:
    executor = FakeBenchExecBackend()
    bundle = tmp_path / "result.lperf"
    manifest, report = run_evalio_repeated_benchmark(
        protocol_path="protocols/lo/se3_v1.yaml",
        dataset="example/sequence",
        pipeline="kiss",
        length=4,
        input_support=None,
        dataset_record=dataset_record(),
        algorithm_config={"voxel_size": 1.0},
        method_version="1.3.0",
        bundle_dir=bundle,
        workspace=tmp_path / "work",
        measurement_class=MeasurementClass.CONTROLLED,
        measured_trials=5,
        resource_limits=ResourceLimits(cpu_cores=(0,)),
        host_snapshot=controlled_host_snapshot(),
        host_control_mode="self_hosted",
        host_control_reason="dedicated synthetic unit-test host",
        thread_policy="single_thread",
        warmup_trials=1,
        evalio_backend=FakeEvalioBackend(),
        execution_backend=executor,
    )

    assert executor.calls == 6
    assert manifest.trial_count == 5
    assert manifest.measurement_class == MeasurementClass.CONTROLLED
    assert report.status == VerificationStatus.VALID
    assert (bundle / "warmups/0001/process.log").is_file()
    assert not (bundle / "warmups/0001/trial.json").exists()
    assert all((bundle / f"trials/{index:04d}/trial.json").is_file() for index in range(1, 6))

    aggregate = json.loads((bundle / "aggregate.json").read_text(encoding="utf-8"))
    metrics = aggregate["metrics"]
    assert aggregate["successful_trials"] == 5
    assert aggregate["failed_trials"] == 0
    assert metrics["warmups"]["count"] == 1
    assert metrics["resources"]["wall_time_s"]["count"] == 5
    assert metrics["trajectory_repeatability"]["trial_pair_count"] == 10
    assert metrics["trajectory_repeatability"]["maximum_pose_translation_delta_m"] == 0.0


def test_controlled_runset_refuses_too_few_measured_trials(tmp_path: Path) -> None:
    executor = FakeBenchExecBackend()
    with pytest.raises(BenchmarkRunError, match="requires at least 5 measured trials"):
        run_evalio_repeated_benchmark(
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
            measurement_class=MeasurementClass.CONTROLLED,
            measured_trials=4,
            evalio_backend=FakeEvalioBackend(),
            execution_backend=executor,
        )
    assert executor.calls == 0


def test_failed_measured_trial_is_retained_as_runset_evidence(tmp_path: Path) -> None:
    executor = FakeBenchExecBackend(fail_calls={2})
    bundle = tmp_path / "result.lperf"
    manifest, report = run_evalio_repeated_benchmark(
        protocol_path="protocols/lo/se3_v1.yaml",
        dataset="example/sequence",
        pipeline="kiss",
        length=4,
        input_support=None,
        dataset_record=dataset_record(),
        algorithm_config={},
        method_version="1.3.0",
        bundle_dir=bundle,
        workspace=tmp_path / "work",
        measurement_class=MeasurementClass.EXPLORATORY,
        measured_trials=3,
        warmup_trials=0,
        evalio_backend=FakeEvalioBackend(),
        execution_backend=executor,
    )

    assert report.status == VerificationStatus.VALID
    assert manifest.conformance_status.value == "non_conformant"
    failed_trial = json.loads((bundle / "trials/0002/trial.json").read_text(encoding="utf-8"))
    assert failed_trial["status"] == "failed"
    assert failed_trial["exit_code"] == 7
    assert (bundle / "trials/0002/trajectory.tum").read_text(encoding="utf-8") == ""
    aggregate = json.loads((bundle / "aggregate.json").read_text(encoding="utf-8"))
    assert aggregate["successful_trials"] == 2
    assert aggregate["failed_trials"] == 1
    assert aggregate["metrics"]["resources"]["wall_time_s"]["count"] == 2


def _refresh_checksum(bundle: Path, relative_path: str) -> None:
    digest = hashlib.sha256((bundle / relative_path).read_bytes()).hexdigest()
    checksum_path = bundle / "checksums.sha256"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    rewritten = [
        f"{digest}  {relative_path}" if line.endswith(f"  {relative_path}") else line
        for line in lines
    ]
    checksum_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def test_verifier_recomputes_runset_resource_distributions(tmp_path: Path) -> None:
    bundle = tmp_path / "result.lperf"
    run_evalio_repeated_benchmark(
        protocol_path="protocols/lo/se3_v1.yaml",
        dataset="example/sequence",
        pipeline="kiss",
        length=4,
        input_support=None,
        dataset_record=dataset_record(),
        algorithm_config={},
        method_version="1.3.0",
        bundle_dir=bundle,
        workspace=tmp_path / "work",
        measurement_class=MeasurementClass.CONTROLLED,
        measured_trials=5,
        resource_limits=ResourceLimits(cpu_cores=(0,)),
        host_snapshot=controlled_host_snapshot(),
        host_control_mode="self_hosted",
        host_control_reason="dedicated synthetic unit-test host",
        thread_policy="single_thread",
        warmup_trials=0,
        evalio_backend=FakeEvalioBackend(),
        execution_backend=FakeBenchExecBackend(),
    )
    aggregate_path = bundle / "aggregate.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    aggregate["metrics"]["resources"]["wall_time_s"]["median"] = 999.0
    aggregate_path.write_text(
        json.dumps(aggregate, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    _refresh_checksum(bundle, "aggregate.json")
    report = verify_bundle(bundle)
    assert report.status == VerificationStatus.INVALID
    assert "AGGREGATE_RESOURCE_DISTRIBUTION_MISMATCH" in {issue.code for issue in report.issues}


def test_controlled_runset_refuses_uncontrolled_host_before_execution(tmp_path: Path) -> None:
    executor = FakeBenchExecBackend()
    with pytest.raises(BenchmarkRunError, match="stable self-hosted or otherwise controlled"):
        run_evalio_repeated_benchmark(
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
            measurement_class=MeasurementClass.CONTROLLED,
            measured_trials=5,
            resource_limits=ResourceLimits(cpu_cores=(0,)),
            host_snapshot=controlled_host_snapshot(),
            thread_policy="single_thread",
            evalio_backend=FakeEvalioBackend(),
            execution_backend=executor,
        )
    assert executor.calls == 0


def test_verifier_rejects_forged_controlled_class_on_uncontrolled_host(tmp_path: Path) -> None:
    bundle = tmp_path / "result.lperf"
    run_evalio_repeated_benchmark(
        protocol_path="protocols/lo/se3_v1.yaml",
        dataset="example/sequence",
        pipeline="kiss",
        length=4,
        input_support=None,
        dataset_record=dataset_record(),
        algorithm_config={},
        method_version="1.3.0",
        bundle_dir=bundle,
        workspace=tmp_path / "work",
        measurement_class=MeasurementClass.EXPLORATORY,
        measured_trials=5,
        warmup_trials=0,
        host_snapshot=controlled_host_snapshot(),
        host_control_mode="uncontrolled",
        host_control_reason="ephemeral hosted CI",
        thread_policy="single_thread",
        evalio_backend=FakeEvalioBackend(),
        execution_backend=FakeBenchExecBackend(),
    )
    for relative_path in ("manifest.json", "environment.json"):
        changed = bundle / relative_path
        payload = json.loads(changed.read_text(encoding="utf-8"))
        payload["measurement_class"] = "controlled"
        changed.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        _refresh_checksum(bundle, relative_path)

    report = verify_bundle(bundle)
    assert report.status == VerificationStatus.INVALID
    assert "CONTROLLED_HOST_NOT_DECLARED" in {issue.code for issue in report.issues}
