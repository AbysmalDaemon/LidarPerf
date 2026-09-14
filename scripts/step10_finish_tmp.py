from __future__ import annotations

import hashlib
import json
from pathlib import Path


def patch_runset() -> None:
    path = Path("src/lidarperf/runset.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace("from typing import Any\n", "from typing import Any, Literal\n", 1)
    anchor = (
        "from lidarperf.trajectory import EvaluationSupport, Trajectory, parse_tum, serialize_tum\n"
        "\n\n"
        "def _required_trial_count"
    )
    insertion = '''from lidarperf.trajectory import EvaluationSupport, Trajectory, parse_tum, serialize_tum


HostControlMode = Literal[
    "uncontrolled",
    "self_hosted",
    "dedicated_vm",
    "bare_metal",
    "other_controlled",
]
_CONTROLLED_HOST_MODES = {"self_hosted", "dedicated_vm", "bare_metal", "other_controlled"}
_ALL_HOST_CONTROL_MODES = {"uncontrolled", *_CONTROLLED_HOST_MODES}


def _validate_measurement_environment(
    *,
    measurement_class: MeasurementClass,
    snapshot: HostSnapshot,
    limits: ResourceLimits,
    host_control_mode: HostControlMode,
    thread_policy: str | None,
) -> None:
    if host_control_mode not in _ALL_HOST_CONTROL_MODES:
        raise ValueError(f"unknown host_control_mode: {host_control_mode!r}")
    if measurement_class == MeasurementClass.EXPLORATORY:
        return

    problems: list[str] = []
    if host_control_mode not in _CONTROLLED_HOST_MODES:
        problems.append("host is not declared stable self-hosted or otherwise controlled")
    if snapshot.os.system.lower() != "linux":
        problems.append("controlled measurements require Linux")
    if not limits.cpu_cores:
        problems.append("controlled measurements require an explicit BenchExec CPU allocation")
    if not thread_policy or not thread_policy.strip():
        problems.append("controlled measurements require an explicit thread policy")
    if not snapshot.cpu.governors:
        problems.append("CPU governor state must be recorded")
    if not snapshot.storage.inspected or snapshot.storage.network_filesystem is not False:
        problems.append("benchmark storage must be inspected and local/controlled")
    swap_used = snapshot.memory.swap_used_bytes
    if swap_used is None:
        problems.append("swap state must be known")
    elif swap_used > 0:
        problems.append("swap must not be in use during controlled measurement")

    if problems:
        raise BenchmarkRunError(
            f"{measurement_class.value}-class evidence does not satisfy controlled-host "
            f"requirements: {'; '.join(problems)}"
        )


def _required_trial_count'''
    assert anchor in text
    text = text.replace(anchor, insertion, 1)
    text = text.replace(
        "    measurement_class: MeasurementClass = MeasurementClass.CONTROLLED,\n",
        "    measurement_class: MeasurementClass = MeasurementClass.EXPLORATORY,\n",
        1,
    )
    signature_anchor = (
        "    host_snapshot: HostSnapshot | None = None,\n"
        "    execution_metadata: dict[str, Any] | None = None,\n"
    )
    signature_replacement = '''    host_snapshot: HostSnapshot | None = None,
    host_control_mode: HostControlMode = "uncontrolled",
    host_control_reason: str | None = None,
    thread_policy: str | None = None,
    execution_metadata: dict[str, Any] | None = None,
'''
    assert signature_anchor in text
    text = text.replace(signature_anchor, signature_replacement, 1)
    limits_anchor = "    limits = resource_limits or ResourceLimits()\n\n    warmups: list[tuple[Any, tuple[str, ...]]] = []\n"
    limits_replacement = '''    limits = resource_limits or ResourceLimits()
    snapshot = host_snapshot or probe_host()
    _validate_measurement_environment(
        measurement_class=measurement_class,
        snapshot=snapshot,
        limits=limits,
        host_control_mode=host_control_mode,
        thread_policy=thread_policy,
    )

    warmups: list[tuple[Any, tuple[str, ...]]] = []
'''
    assert limits_anchor in text
    text = text.replace(limits_anchor, limits_replacement, 1)
    text = text.replace(
        "    evalio_capability = evalio.probe_capability()\n    snapshot = host_snapshot or probe_host()\n\n",
        "    evalio_capability = evalio.probe_capability()\n\n",
        1,
    )
    execution_anchor = '        "statistics_population": "successful measured trials only",\n    }\n'
    execution_replacement = '''        "statistics_population": "successful measured trials only",
        "host_control_mode": host_control_mode,
        "host_control_reason": host_control_reason,
        "cpu_allocation": list(limits.cpu_cores),
        "thread_policy": thread_policy,
    }
'''
    assert execution_anchor in text
    text = text.replace(execution_anchor, execution_replacement, 1)
    path.write_text(text, encoding="utf-8")


def patch_verifier() -> None:
    path = Path("src/lidarperf/bundle/verify.py")
    text = path.read_text(encoding="utf-8")
    minimum_anchor = '''def _minimum_trials(protocol, measurement_class: MeasurementClass) -> int:
    if measurement_class == MeasurementClass.EXPLORATORY:
        return protocol.repetition.exploratory_min_trials
    if measurement_class == MeasurementClass.CONTROLLED:
        return protocol.repetition.controlled_min_trials
    return protocol.repetition.publication_min_trials


def verify_bundle'''
    replacement = '''def _minimum_trials(protocol, measurement_class: MeasurementClass) -> int:
    if measurement_class == MeasurementClass.EXPLORATORY:
        return protocol.repetition.exploratory_min_trials
    if measurement_class == MeasurementClass.CONTROLLED:
        return protocol.repetition.controlled_min_trials
    return protocol.repetition.publication_min_trials


_CONTROLLED_HOST_MODES = {"self_hosted", "dedicated_vm", "bare_metal", "other_controlled"}


def _verify_measurement_environment(
    manifest: ResultManifest,
    environment: EnvironmentRecord,
    collector: _Collector,
) -> None:
    if environment.measurement_class != manifest.measurement_class:
        collector.error(
            "MEASUREMENT_CLASS_MISMATCH",
            "manifest measurement_class differs from environment.json",
        )
    if manifest.measurement_class == MeasurementClass.EXPLORATORY:
        return

    execution = environment.execution
    host = environment.host
    host_control_mode = execution.get("host_control_mode")
    if host_control_mode not in _CONTROLLED_HOST_MODES:
        collector.error(
            "CONTROLLED_HOST_NOT_DECLARED",
            "controlled/publication evidence requires a stable self-hosted or otherwise controlled host declaration",
        )
    if execution.get("backend") != "benchexec-runexec":
        collector.error(
            "CONTROLLED_BENCHEXEC_REQUIRED",
            "controlled/publication process measurements require BenchExec/runexec",
        )
    cpu_allocation = execution.get("cpu_allocation")
    if not isinstance(cpu_allocation, list) or not cpu_allocation:
        collector.error(
            "CONTROLLED_CPU_ALLOCATION_MISSING",
            "controlled/publication evidence requires an explicit CPU allocation",
        )
    thread_policy = execution.get("thread_policy")
    if not isinstance(thread_policy, str) or not thread_policy.strip():
        collector.error(
            "CONTROLLED_THREAD_POLICY_MISSING",
            "controlled/publication evidence requires an explicit thread policy",
        )

    os_record = host.get("os") if isinstance(host, dict) else None
    if not isinstance(os_record, dict) or str(os_record.get("system", "")).lower() != "linux":
        collector.error("CONTROLLED_LINUX_REQUIRED", "controlled/publication evidence requires Linux")
    cpu_record = host.get("cpu") if isinstance(host, dict) else None
    governors = cpu_record.get("governors") if isinstance(cpu_record, dict) else None
    if not isinstance(governors, list) or not governors:
        collector.error(
            "CONTROLLED_GOVERNOR_STATE_MISSING",
            "controlled/publication evidence requires recorded CPU governor state",
        )
    storage_record = host.get("storage") if isinstance(host, dict) else None
    storage_ok = (
        isinstance(storage_record, dict)
        and storage_record.get("inspected") is True
        and storage_record.get("network_filesystem") is False
    )
    if not storage_ok:
        collector.error(
            "CONTROLLED_STORAGE_NOT_PROVEN",
            "controlled/publication evidence requires inspected local/controlled benchmark storage",
        )
    memory_record = host.get("memory") if isinstance(host, dict) else None
    if not isinstance(memory_record, dict):
        collector.error("CONTROLLED_SWAP_STATE_MISSING", "controlled/publication swap state is missing")
    else:
        total = memory_record.get("swap_total_bytes")
        free = memory_record.get("swap_free_bytes")
        if not isinstance(total, int) or not isinstance(free, int):
            collector.error(
                "CONTROLLED_SWAP_STATE_MISSING",
                "controlled/publication evidence requires known swap state",
            )
        elif max(0, total - free) > 0:
            collector.error(
                "CONTROLLED_SWAP_IN_USE",
                "controlled/publication evidence cannot be recorded while swap is in use",
            )


def verify_bundle'''
    assert minimum_anchor in text
    text = text.replace(minimum_anchor, replacement, 1)
    env_anchor = '''    if environment is not None and environment.measurement_class != manifest.measurement_class:
        collector.error(
            "MEASUREMENT_CLASS_MISMATCH",
            "manifest measurement_class differs from environment.json",
        )
'''
    assert env_anchor in text
    text = text.replace(
        env_anchor,
        "    if environment is not None:\n        _verify_measurement_environment(manifest, environment, collector)\n",
        1,
    )
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = Path("tests/test_runset.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace("import hashlib\n", "import hashlib\nfrom datetime import UTC, datetime\n", 1)
    import_anchor = '''from lidarperf.bundle import (
    DatasetFingerprintClass,
    DatasetRecord,
    VerificationStatus,
    verify_bundle,
)
'''
    replacement = import_anchor + '''from lidarperf.host import (
    CgroupSnapshot,
    CPUSnapshot,
    HostSnapshot,
    MemorySnapshot,
    OSSnapshot,
    RuntimeSnapshot,
    StorageSnapshot,
)
'''
    assert import_anchor in text
    text = text.replace(import_anchor, replacement, 1)
    test_anchor = "def test_controlled_runset_separates_warmup_and_five_measured_trials(tmp_path: Path) -> None:\n"
    helper = '''def controlled_host_snapshot() -> HostSnapshot:
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


'''
    assert test_anchor in text
    text = text.replace(test_anchor, helper + test_anchor, 1)
    controlled_call = '''        measurement_class=MeasurementClass.CONTROLLED,
        measured_trials=5,
'''
    controlled_replacement = '''        measurement_class=MeasurementClass.CONTROLLED,
        measured_trials=5,
        resource_limits=ResourceLimits(cpu_cores=(0,)),
        host_snapshot=controlled_host_snapshot(),
        host_control_mode="self_hosted",
        host_control_reason="dedicated synthetic unit-test host",
        thread_policy="single_thread",
'''
    assert text.count(controlled_call) >= 2
    text = text.replace(controlled_call, controlled_replacement)
    text += '''

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
'''
    path.write_text(text, encoding="utf-8")


def patch_real_script() -> None:
    path = Path("scripts/run_step10_real.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "        measurement_class=MeasurementClass.CONTROLLED,\n",
        "        measurement_class=MeasurementClass.EXPLORATORY,\n",
        1,
    )
    anchor = "        host_snapshot=host,\n        execution_metadata={\n"
    replacement = '''        host_snapshot=host,
        host_control_mode="uncontrolled",
        host_control_reason="ordinary GitHub-hosted runner",
        thread_policy="KISS-ICP evalio default; max_num_threads=0",
        execution_metadata={
'''
    assert anchor in text
    text = text.replace(anchor, replacement, 1)
    path.write_text(text, encoding="utf-8")


def relabel_evidence() -> None:
    old = Path("docs/validation/step10_kiss_hilti_controlled.lperf")
    new = Path("docs/validation/step10_kiss_hilti_repeated.lperf")
    assert old.is_dir() and not new.exists()
    old.rename(new)

    manifest_path = new / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["measurement_class"] = "exploratory"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    environment_path = new / "environment.json"
    environment = json.loads(environment_path.read_text(encoding="utf-8"))
    environment["measurement_class"] = "exploratory"
    execution = environment["execution"]
    execution["host_control_mode"] = "uncontrolled"
    execution["host_control_reason"] = "ordinary GitHub-hosted runner"
    execution["cpu_allocation"] = []
    execution["thread_policy"] = "KISS-ICP evalio default; max_num_threads=0"
    environment_path.write_text(
        json.dumps(environment, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = []
    for relative_path in manifest["file_inventory"]:
        digest = hashlib.sha256((new / relative_path).read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative_path}")
    (new / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_docs() -> None:
    readme = Path("README.md")
    text = readme.read_text(encoding="utf-8")
    text = text.replace(
        "> **Status:** pre-alpha. The benchmark specification is approved; protocol, synthetic-fixture, result-bundle integrity, host-provenance, controlled process-execution, trajectory-evaluation, real evalio/KISS-ICP integration, and the first complete verified real `.lperf` artifact path are implemented.",
        "> **Status:** pre-alpha. The benchmark specification is approved; protocol, synthetic-fixture, result-bundle integrity, host-provenance, controlled process-execution, trajectory-evaluation, real evalio/KISS-ICP integration, complete `.lperf` artifact production, and repeated-run/repeatability analysis are implemented.",
        1,
    )
    text = text.replace(
        "- a single-trial orchestration path that connects evalio execution, BenchExec accounting, LidarPerf trajectory evaluation, provenance capture, immutable bundle writing, and independent bundle verification.",
        "- a single-trial orchestration path that connects evalio execution, BenchExec accounting, LidarPerf trajectory evaluation, provenance capture, immutable bundle writing, and independent bundle verification;\n- a repeated-run orchestration path with explicit warmups, retained failed trials, per-metric/resource distributions, and all-pairs estimator-output repeatability recomputed by the verifier from immutable trajectory payloads.",
        1,
    )
    stale = "The committed Step 9 result is intentionally `exploratory`: it contains one measured trial, while the approved protocol requires at least five trials for `controlled` evidence and ten for `publication`. The verifier enforces that measurement-strength rule. BenchExec resource accounting in the real bundle is genuine, but the recorded wall/CPU/memory values are explicitly non-authoritative because the run used a GitHub-hosted VM. Step 10 will add repeated-run execution and legitimately controlled measurement bundles."
    replacement = """The committed Step 9 result is intentionally `exploratory`: it contains one measured trial. Step 10 adds explicit warmups and repeated measured trials, scalar runtime/resource distributions, estimator-output repeatability, and verifier-side aggregate recomputation. The durable Step 10 integration bundle is `docs/validation/step10_kiss_hilti_repeated.lperf/`: one warmup plus five measured KISS-ICP/Hilti executions, all successful and independently verified.

The Step 10 hosted bundle remains `exploratory` even with five measured trials. The specification requires a stable self-hosted or otherwise controlled Linux machine, explicit CPU allocation/thread policy, recorded governor state, controlled storage, and no swap pressure before a result may claim `controlled` strength. Ordinary GitHub-hosted runners therefore validate the repeated-run machinery but are not authoritative performance baselines."""
    assert stale in text
    text = text.replace(stale, replacement, 1)
    readme.write_text(text, encoding="utf-8")

    log = Path("LidarPerf_research_execution_plan.md")
    entry = '''

---

## Step 10 — repeated-run execution and repeatability — COMPLETE (2026-09-14)

### Goal

Extend the Step 9 single-trial artifact path into an auditable run set: explicit warmups, multiple measured trials, retained failures, runtime/resource distributions, estimator-output repeatability, and independent verifier recomputation.

### Implemented

- added `run_evalio_repeated_benchmark` as the repeated-run orchestration path;
- warmups are explicit evidence under `warmups/` but never contribute to `manifest.trial_count` or measured statistics;
- measured execution failures are retained as failed trial records instead of disappearing from the run set;
- successful measured trials contribute scalar distributions with count/min/max/mean/median/population-std/p90/p95/p99;
- trajectory repeatability is computed over every measured trial pair at exact common timestamps with no hidden spatial alignment;
- repeatability uses the canonical serialized TUM payload representation, so producer and verifier operate on the same immutable evidence;
- verifier independently recomputes scalar metric/resource distributions and trajectory repeatability and rejects checksum-refreshed aggregate tampering;
- repeated-run environment metadata now records host-control declaration, CPU allocation, and thread policy;
- `controlled`/`publication` producer requests now fail before execution unless the declared environment satisfies the v0.1 controlled-host requirements that can be checked here: Linux, stable controlled-host declaration, explicit CPU allocation, explicit thread policy, recorded governor state, inspected local/controlled storage, known zero swap use, and BenchExec readiness;
- verifier applies the same controlled-host evidence checks so a bundle cannot be promoted merely by editing `measurement_class` and refreshing checksums.

### Real validation

Dataset/pipeline remained `hilti_2022/basement_2` + KISS-ICP 1.3.0 through evalio 0.6.1 and BenchExec `runexec 3.35`, using 120 LiDAR scans per execution.

The successful real validation workflow was GitHub Actions run `34889567816`. It performed one warmup execution, five measured executions, five successful measured trials, zero failed trials, and independent `lidarperf verify` before committing evidence.

The durable bundle is `docs/validation/step10_kiss_hilti_repeated.lperf/`.

The measured hosted-runner resource distribution is retained as integration evidence but is explicitly non-authoritative. Wall time across the five measured trials had mean `3.5721830594 s`, median `3.5747101960 s`, minimum `3.5140726920 s`, maximum `3.6202339240 s`, and population standard deviation `0.0419640896 s`. Mean CPU time was `4.4439166 s`; mean peak memory was `129227161.6 bytes`.

All five serialized estimator trajectories had identical timestamp sets and translation payloads. Across the 10 trial pairs, maximum pose translation delta was `0.0 m`; maximum pose rotation delta was approximately `2.41484e-06 deg`, with pairwise rotation RMSE approximately `8.39423e-07 deg`. This is integration evidence of extremely stable output for this short KISS/Hilti prefix, not a general determinism claim for KISS-ICP or LIO systems.

### Errors / bugs discovered and resolved

1. The first real repeated run (`34888575461`) failed bundle self-verification with `AGGREGATE_TRAJECTORY_REPEATABILITY_MISMATCH`. The producer had computed repeatability from higher-precision in-memory poses while the verifier recomputed from canonical TUM payloads whose pose scalars are serialized to 12 decimal places. Fix: canonicalize producer-side repeatability through serialize→parse before aggregation. Added a regression test demonstrating a sub-serialization-precision in-memory difference collapses in the actual immutable payload.
2. After the corrected real run passed, a specification audit caught a more important semantic error: five trials and genuine BenchExec accounting do **not** make an ordinary GitHub-hosted VM `controlled`. `SPEC.md` requires a stable self-hosted or otherwise controlled Linux machine plus additional host controls. The real bundle was therefore reclassified from `controlled` to `exploratory`, renamed from `step10_kiss_hilti_controlled.lperf` to `step10_kiss_hilti_repeated.lperf`, and its checksums were regenerated and independently verified.
3. A first attempt at the final semantic-cleanup workflow was invalid YAML and created no job; no source or evidence files were modified by that failed workflow. The cleanup was rerun through a temporary Python patch script and minimal workflow instead. This tooling failure is retained here as project history.

### Measurement-class conclusion

Trial count is necessary but not sufficient for measurement strength. A repeated run set may contain five or more measured trials and still be `exploratory` when host control cannot be established. This distinction is now enforced by both producer and verifier.

### Step 10 exit condition

Satisfied when the final PR matrix passes on Python 3.11/3.12/3.13, PR #11 is squash-merged, and post-merge `main` CI is green. Controlled real performance evidence is intentionally deferred until a stable controlled Linux benchmark host is available; it is not a blocker for Step 11 comparator development.
'''
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(entry)


def main() -> None:
    patch_runset()
    patch_verifier()
    patch_tests()
    patch_real_script()
    relabel_evidence()
    update_docs()


if __name__ == "__main__":
    main()
