from datetime import UTC, datetime
from pathlib import Path

from lidarperf.host import (
    CPUSnapshot,
    CgroupSnapshot,
    GPUSnapshot,
    HostSnapshot,
    MemorySnapshot,
    OSSnapshot,
    RuntimeSnapshot,
    StorageSnapshot,
    assess_host,
    probe_host,
)
from lidarperf.host.probe import _parse_cpuinfo, _parse_meminfo


def _snapshot(**overrides):
    values = {
        "captured_at": datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        "host_sha256": "a" * 64,
        "os": OSSnapshot(
            system="Linux",
            distribution="Ubuntu",
            distribution_version="24.04",
            kernel_release="6.8.0",
            kernel_version="#1",
            architecture="x86_64",
            libc="glibc 2.39",
        ),
        "cpu": CPUSnapshot(
            model="Example CPU",
            architecture="x86_64",
            logical_cpus=8,
            physical_cores=4,
            affinity_cpus=(2, 3, 4, 5),
            scaling_drivers=("intel_pstate",),
            governors=("performance",),
            numa_nodes=(0,),
        ),
        "memory": MemorySnapshot(
            total_bytes=16 * 1024**3,
            available_bytes=12 * 1024**3,
            swap_total_bytes=0,
            swap_free_bytes=0,
        ),
        "cgroups": CgroupSnapshot(version="v2", controllers=("cpu", "memory"), writable=True),
        "storage": StorageSnapshot(),
        "gpu": GPUSnapshot(),
        "runtime": RuntimeSnapshot(
            load_1m=0.1,
            load_5m=0.1,
            load_15m=0.1,
            benchexec_available=True,
            runexec_available=True,
        ),
    }
    values.update(overrides)
    return HostSnapshot(**values)


def test_parse_meminfo_converts_kib_to_bytes() -> None:
    values = _parse_meminfo("MemTotal:       1024 kB\nSwapTotal:       128 kB\n")
    assert values == {"MemTotal": 1024 * 1024, "SwapTotal": 128 * 1024}


def test_parse_cpuinfo_counts_physical_cores() -> None:
    text = """processor : 0
model name : Test CPU
physical id : 0
core id : 0

processor : 1
model name : Test CPU
physical id : 0
core id : 1
"""
    model, cores = _parse_cpuinfo(text)
    assert model == "Test CPU"
    assert cores == 2


def test_doctor_marks_clean_linux_host_controlled_eligible() -> None:
    report = assess_host(_snapshot())
    assert report.eligible_measurement_classes == ("exploratory", "controlled")
    assert not [issue for issue in report.issues if issue.blocks_controlled]


def test_doctor_blocks_controlled_without_benchexec() -> None:
    runtime = RuntimeSnapshot(load_1m=0.1, benchexec_available=False, runexec_available=False)
    report = assess_host(_snapshot(runtime=runtime))
    assert report.eligible_measurement_classes == ("exploratory",)
    assert "BENCHEXEC_UNAVAILABLE" in {issue.code for issue in report.issues}


def test_doctor_warns_for_network_dataset() -> None:
    storage = StorageSnapshot(
        inspected=True,
        exists=True,
        filesystem_type="nfs4",
        network_filesystem=True,
    )
    report = assess_host(_snapshot(storage=storage))
    assert "NETWORK_FILESYSTEM" in {issue.code for issue in report.issues}


def test_doctor_reports_missing_data_path_as_error() -> None:
    storage = StorageSnapshot(inspected=True, exists=False)
    report = assess_host(_snapshot(storage=storage))
    issue = next(issue for issue in report.issues if issue.code == "DATA_PATH_MISSING")
    assert issue.severity.value == "error"


def test_probe_host_is_read_only_smoke(tmp_path: Path) -> None:
    snapshot = probe_host(tmp_path)
    assert snapshot.host_sha256
    assert snapshot.cpu.logical_cpus >= 1
    assert snapshot.storage.inspected is True
    assert snapshot.storage.exists is True
