"""Cross-platform host fingerprinting with Linux benchmark-grade detail."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from lidarperf.spec.canonical import sha256_fingerprint

from .models import (
    CgroupSnapshot,
    CPUSnapshot,
    GPUDeviceSnapshot,
    GPUSnapshot,
    HostSnapshot,
    MemorySnapshot,
    OSSnapshot,
    RuntimeSnapshot,
    StorageSnapshot,
)

_REMOTE_FILESYSTEMS = {
    "9p",
    "ceph",
    "cifs",
    "fuse.sshfs",
    "glusterfs",
    "lustre",
    "nfs",
    "nfs4",
    "smb3",
    "sshfs",
}


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _parse_key_value_lines(text: str, separator: str = "=") -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        if separator not in raw_line:
            continue
        key, value = raw_line.split(separator, 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def _parse_meminfo(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^([^:]+):\s+(\d+)\s+kB$", line)
        if match:
            values[match.group(1)] = int(match.group(2)) * 1024
    return values


def _parse_cpuinfo(text: str) -> tuple[str | None, int | None]:
    blocks = [block for block in text.split("\n\n") if block.strip()]
    model: str | None = None
    physical_pairs: set[tuple[str, str]] = set()
    for block in blocks:
        fields = _parse_key_value_lines(block, separator=":")
        if model is None:
            model = fields.get("model name") or fields.get("Hardware") or fields.get("Processor")
        physical_id = fields.get("physical id")
        core_id = fields.get("core id")
        if physical_id is not None and core_id is not None:
            physical_pairs.add((physical_id, core_id))
    physical_cores = len(physical_pairs) or None
    return model, physical_cores


def _numeric_suffixes(paths: Iterable[Path], prefix: str) -> tuple[int, ...]:
    values: list[int] = []
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    for path in paths:
        match = pattern.match(path.name)
        if match:
            values.append(int(match.group(1)))
    return tuple(sorted(set(values)))


def _read_unique(paths: Iterable[Path]) -> tuple[str, ...]:
    values: set[str] = set()
    for path in paths:
        value = _read_text(path)
        if value is not None and value.strip():
            values.add(value.strip())
    return tuple(sorted(values))


def _probe_boost(sys_root: Path) -> bool | None:
    generic = _read_text(sys_root / "devices/system/cpu/cpufreq/boost")
    if generic is not None and generic.strip() in {"0", "1"}:
        return generic.strip() == "1"
    no_turbo = _read_text(sys_root / "devices/system/cpu/intel_pstate/no_turbo")
    if no_turbo is not None and no_turbo.strip() in {"0", "1"}:
        return no_turbo.strip() == "0"
    return None


def _probe_thermal_throttle_count(sys_root: Path) -> int | None:
    paths = list(sys_root.glob("devices/system/cpu/cpu*/thermal_throttle/*_throttle_count"))
    if not paths:
        return None
    total = 0
    readable = False
    for path in paths:
        value = _read_text(path)
        if value is None:
            continue
        try:
            total += int(value.strip())
            readable = True
        except ValueError:
            continue
    return total if readable else None


def _probe_os(etc_root: Path) -> OSSnapshot:
    release_values: dict[str, str] = {}
    os_release = _read_text(etc_root / "os-release")
    if os_release:
        release_values = _parse_key_value_lines(os_release)
    libc_name, libc_version = platform.libc_ver()
    libc = " ".join(part for part in (libc_name, libc_version) if part) or None
    return OSSnapshot(
        system=platform.system() or "unknown",
        distribution=release_values.get("NAME"),
        distribution_version=release_values.get("VERSION_ID"),
        kernel_release=platform.release() or "unknown",
        kernel_version=platform.version() or "unknown",
        architecture=platform.machine() or "unknown",
        libc=libc,
    )


def _probe_cpu(proc_root: Path, sys_root: Path) -> CPUSnapshot:
    logical_cpus = os.cpu_count() or 1
    cpuinfo = _read_text(proc_root / "cpuinfo") or ""
    model, physical_cores = _parse_cpuinfo(cpuinfo)
    try:
        affinity = tuple(sorted(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        affinity = ()
    cpufreq_root = sys_root / "devices/system/cpu/cpufreq"
    scaling_drivers = _read_unique(cpufreq_root.glob("policy*/scaling_driver"))
    governors = _read_unique(cpufreq_root.glob("policy*/scaling_governor"))
    numa_nodes = _numeric_suffixes((sys_root / "devices/system/node").glob("node*"), "node")
    return CPUSnapshot(
        model=model,
        architecture=platform.machine() or "unknown",
        logical_cpus=logical_cpus,
        physical_cores=physical_cores,
        affinity_cpus=affinity,
        scaling_drivers=scaling_drivers,
        governors=governors,
        numa_nodes=numa_nodes,
        boost_enabled=_probe_boost(sys_root),
        thermal_throttle_count=_probe_thermal_throttle_count(sys_root),
    )


def _probe_memory(proc_root: Path) -> MemorySnapshot:
    meminfo = _parse_meminfo(_read_text(proc_root / "meminfo") or "")
    return MemorySnapshot(
        total_bytes=meminfo.get("MemTotal"),
        available_bytes=meminfo.get("MemAvailable"),
        swap_total_bytes=meminfo.get("SwapTotal"),
        swap_free_bytes=meminfo.get("SwapFree"),
    )


def _probe_cgroups(proc_root: Path, sys_root: Path) -> CgroupSnapshot:
    cgroup_root = sys_root / "fs/cgroup"
    controllers_text = _read_text(cgroup_root / "cgroup.controllers")
    if controllers_text is not None:
        version = "v2"
        controllers = tuple(sorted(controllers_text.split()))
    elif (proc_root / "cgroups").exists() and cgroup_root.exists():
        version = "v1"
        controllers = ()
    elif cgroup_root.exists():
        version = "unknown"
        controllers = ()
    else:
        version = "none"
        controllers = ()
    cgroup_text = _read_text(proc_root / "self/cgroup") or ""
    markers = ("docker", "kubepods", "containerd", "podman", "lxc")
    containerized = Path("/.dockerenv").exists() or any(marker in cgroup_text for marker in markers)
    writable = os.access(cgroup_root, os.W_OK) if cgroup_root.exists() else None
    return CgroupSnapshot(
        version=version,
        controllers=controllers,
        writable=writable,
        containerized=containerized,
    )


def _run_command(args: list[str], timeout: float = 2.0) -> str | None:
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _probe_filesystem(data_path: Path | None) -> StorageSnapshot:
    if data_path is None:
        return StorageSnapshot()
    path = data_path.expanduser()
    if not path.exists():
        return StorageSnapshot(inspected=True, exists=False)
    filesystem_type: str | None = None
    if shutil.which("findmnt"):
        output = _run_command(["findmnt", "-T", str(path), "-n", "-o", "FSTYPE"])
        if output:
            filesystem_type = output.splitlines()[0].strip().lower()
    network = filesystem_type in _REMOTE_FILESYSTEMS if filesystem_type else None
    return StorageSnapshot(
        inspected=True,
        exists=True,
        filesystem_type=filesystem_type,
        network_filesystem=network,
    )


def _probe_gpu() -> GPUSnapshot:
    nvidia_smi = shutil.which("nvidia-smi")
    devices: list[GPUDeviceSnapshot] = []
    if nvidia_smi:
        output = _run_command(
            [
                nvidia_smi,
                "--query-gpu=name,driver_version",
                "--format=csv,noheader,nounits",
            ]
        )
        if output:
            for line in output.splitlines():
                parts = [part.strip() for part in line.split(",", maxsplit=1)]
                if parts and parts[0]:
                    devices.append(
                        GPUDeviceSnapshot(
                            name=parts[0],
                            driver_version=parts[1] if len(parts) > 1 and parts[1] else None,
                        )
                    )
    cuda_version: str | None = None
    nvcc = shutil.which("nvcc")
    if nvcc:
        output = _run_command([nvcc, "--version"])
        if output:
            match = re.search(r"release\s+([0-9]+(?:\.[0-9]+)*)", output)
            if match:
                cuda_version = match.group(1)
    return GPUSnapshot(
        nvidia_smi_available=nvidia_smi is not None,
        devices=tuple(devices),
        cuda_toolkit_version=cuda_version,
    )


def _probe_ac_power(sys_root: Path) -> bool | None:
    power_root = sys_root / "class/power_supply"
    states: list[bool] = []
    for supply in power_root.glob("*"):
        kind = (_read_text(supply / "type") or "").strip().lower()
        if kind not in {"mains", "usb", "usb_c"}:
            continue
        online = (_read_text(supply / "online") or "").strip()
        if online in {"0", "1"}:
            states.append(online == "1")
    return any(states) if states else None


def _probe_runtime(sys_root: Path) -> RuntimeSnapshot:
    try:
        load1, load5, load15 = os.getloadavg()
    except (AttributeError, OSError):
        load1 = load5 = load15 = None
    return RuntimeSnapshot(
        load_1m=load1,
        load_5m=load5,
        load_15m=load15,
        ac_power_online=_probe_ac_power(sys_root),
        benchexec_available=shutil.which("benchexec") is not None,
        runexec_available=shutil.which("runexec") is not None,
    )


def _stable_host_identity(
    os_snapshot: OSSnapshot,
    cpu: CPUSnapshot,
    memory: MemorySnapshot,
    gpu: GPUSnapshot,
) -> dict[str, object]:
    """Return static-enough hardware/software identity; exclude dynamic runtime state."""

    return {
        "os": os_snapshot.model_dump(mode="json"),
        "cpu": {
            "model": cpu.model,
            "architecture": cpu.architecture,
            "logical_cpus": cpu.logical_cpus,
            "physical_cores": cpu.physical_cores,
            "scaling_drivers": cpu.scaling_drivers,
            "numa_nodes": cpu.numa_nodes,
        },
        "memory_total_bytes": memory.total_bytes,
        "gpu_devices": [device.model_dump(mode="json") for device in gpu.devices],
    }


def probe_host(
    data_path: Path | None = None,
    *,
    proc_root: Path = Path("/proc"),
    sys_root: Path = Path("/sys"),
    etc_root: Path = Path("/etc"),
) -> HostSnapshot:
    """Capture benchmark-relevant host provenance without modifying machine state."""

    os_snapshot = _probe_os(etc_root)
    cpu = _probe_cpu(proc_root, sys_root)
    memory = _probe_memory(proc_root)
    cgroups = _probe_cgroups(proc_root, sys_root)
    storage = _probe_filesystem(data_path)
    gpu = _probe_gpu()
    runtime = _probe_runtime(sys_root)
    host_sha256 = sha256_fingerprint(_stable_host_identity(os_snapshot, cpu, memory, gpu))
    return HostSnapshot(
        captured_at=datetime.now(UTC),
        host_sha256=host_sha256,
        os=os_snapshot,
        cpu=cpu,
        memory=memory,
        cgroups=cgroups,
        storage=storage,
        gpu=gpu,
        runtime=runtime,
    )
