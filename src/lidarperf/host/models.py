"""Versioned host-provenance and doctor-report models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class StrictFrozenModel(BaseModel):
    """Immutable base for host-provenance records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DoctorSeverity(StrEnum):
    """Severity of one host-doctor finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class OSSnapshot(StrictFrozenModel):
    """Operating-system identity relevant to benchmark provenance."""

    system: str
    distribution: str | None = None
    distribution_version: str | None = None
    kernel_release: str
    kernel_version: str
    architecture: str
    libc: str | None = None


class CPUSnapshot(StrictFrozenModel):
    """CPU topology, scheduling allocation, and frequency-policy metadata."""

    model: str | None = None
    architecture: str
    logical_cpus: int = Field(ge=1)
    physical_cores: int | None = Field(default=None, ge=1)
    affinity_cpus: tuple[int, ...] = ()
    scaling_drivers: tuple[str, ...] = ()
    governors: tuple[str, ...] = ()
    numa_nodes: tuple[int, ...] = ()
    boost_enabled: bool | None = None
    thermal_throttle_count: int | None = Field(default=None, ge=0)

    @property
    def affinity_count(self) -> int:
        return len(self.affinity_cpus)

    @property
    def smt_enabled(self) -> bool | None:
        if self.physical_cores is None:
            return None
        return self.logical_cpus > self.physical_cores


class MemorySnapshot(StrictFrozenModel):
    """Physical-memory and swap state at probe time."""

    total_bytes: int | None = Field(default=None, ge=0)
    available_bytes: int | None = Field(default=None, ge=0)
    swap_total_bytes: int | None = Field(default=None, ge=0)
    swap_free_bytes: int | None = Field(default=None, ge=0)

    @property
    def swap_used_bytes(self) -> int | None:
        if self.swap_total_bytes is None or self.swap_free_bytes is None:
            return None
        return max(0, self.swap_total_bytes - self.swap_free_bytes)


class CgroupSnapshot(StrictFrozenModel):
    """Linux cgroup capabilities visible to the current process."""

    version: Literal["v1", "v2", "none", "unknown"]
    controllers: tuple[str, ...] = ()
    writable: bool | None = None
    containerized: bool = False


class StorageSnapshot(StrictFrozenModel):
    """Filesystem classification for the benchmark data path, if requested."""

    inspected: bool = False
    exists: bool | None = None
    filesystem_type: str | None = None
    network_filesystem: bool | None = None


class GPUDeviceSnapshot(StrictFrozenModel):
    """Non-unique NVIDIA device identity used for performance provenance."""

    name: str
    driver_version: str | None = None


class GPUSnapshot(StrictFrozenModel):
    """GPU tooling and device metadata without serial numbers or UUIDs."""

    nvidia_smi_available: bool = False
    devices: tuple[GPUDeviceSnapshot, ...] = ()
    cuda_toolkit_version: str | None = None


class RuntimeSnapshot(StrictFrozenModel):
    """Dynamic host conditions and benchmark-tool capabilities."""

    load_1m: float | None = Field(default=None, ge=0.0)
    load_5m: float | None = Field(default=None, ge=0.0)
    load_15m: float | None = Field(default=None, ge=0.0)
    ac_power_online: bool | None = None
    benchexec_available: bool = False
    runexec_available: bool = False


class HostSnapshot(StrictFrozenModel):
    """Portable host snapshot embedded into LidarPerf environment provenance."""

    schema_version: Literal["lidarperf.host.v1"] = "lidarperf.host.v1"
    captured_at: datetime
    host_sha256: str = Field(pattern=SHA256_PATTERN)
    os: OSSnapshot
    cpu: CPUSnapshot
    memory: MemorySnapshot
    cgroups: CgroupSnapshot
    storage: StorageSnapshot = Field(default_factory=StorageSnapshot)
    gpu: GPUSnapshot = Field(default_factory=GPUSnapshot)
    runtime: RuntimeSnapshot = Field(default_factory=RuntimeSnapshot)

    @model_validator(mode="after")
    def captured_at_is_timezone_aware(self) -> Self:
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must include an explicit timezone offset")
        return self


class DoctorIssue(StrictFrozenModel):
    """One machine-readable host-readiness finding."""

    severity: DoctorSeverity
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    blocks_controlled: bool = False


class DoctorReport(StrictFrozenModel):
    """Host snapshot plus benchmark-readiness assessment."""

    schema_version: Literal["lidarperf.doctor.v1"] = "lidarperf.doctor.v1"
    snapshot: HostSnapshot
    eligible_measurement_classes: tuple[Literal["exploratory", "controlled"], ...]
    issues: tuple[DoctorIssue, ...] = ()
