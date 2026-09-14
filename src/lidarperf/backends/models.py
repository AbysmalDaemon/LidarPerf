"""Execution-backend data models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictFrozenModel(BaseModel):
    """Immutable backend model base."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CommandSpec(StrictFrozenModel):
    """A command executed without a shell."""

    argv: tuple[str, ...]
    working_directory: Path | None = None
    environment: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def argv_is_nonempty(self) -> Self:
        if not self.argv or not self.argv[0]:
            raise ValueError("argv must contain a non-empty executable")
        if any("\x00" in item for item in self.argv):
            raise ValueError("argv must not contain NUL bytes")
        return self


class ResourceLimits(StrictFrozenModel):
    """Resource constraints delegated to BenchExec/runexec."""

    cpu_time_s: float | None = Field(default=None, gt=0)
    wall_time_s: float | None = Field(default=None, gt=0)
    memory_bytes: int | None = Field(default=None, gt=0)
    cpu_cores: tuple[int, ...] = ()
    memory_nodes: tuple[int, ...] = ()

    @field_validator("cpu_cores", "memory_nodes")
    @classmethod
    def normalize_ids(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(item < 0 for item in value):
            raise ValueError("resource IDs must be non-negative")
        return tuple(sorted(set(value)))


class ExecutionMeasurements(StrictFrozenModel):
    """Process-tree measurements reported by BenchExec."""

    wall_time_s: float = Field(ge=0)
    cpu_time_s: float = Field(ge=0)
    peak_memory_bytes: int | None = Field(default=None, ge=0)

    @property
    def cpu_core_equivalents(self) -> float | None:
        if self.wall_time_s <= 0:
            return None
        return self.cpu_time_s / self.wall_time_s


class BenchExecCapability(StrictFrozenModel):
    """Result of an active, harmless BenchExec capability probe."""

    schema_version: Literal["lidarperf.benchexec-capability.v1"] = (
        "lidarperf.benchexec-capability.v1"
    )
    backend: Literal["benchexec-runexec"] = "benchexec-runexec"
    backend_version: str | None = None
    installed: bool
    controlled_ready: bool
    reason: str | None = None

    @model_validator(mode="after")
    def readiness_has_consistent_reason(self) -> Self:
        if self.controlled_ready and not self.installed:
            raise ValueError("a controlled-ready backend must be installed")
        if self.controlled_ready and self.reason is not None:
            raise ValueError("a controlled-ready backend must not have a failure reason")
        if not self.controlled_ready and not self.reason:
            raise ValueError("an unavailable backend requires a reason")
        return self


class CommandExecutionResult(StrictFrozenModel):
    """Normalized result of one BenchExec-backed process execution."""

    schema_version: Literal["lidarperf.execution.v1"] = "lidarperf.execution.v1"
    backend: Literal["benchexec-runexec"] = "benchexec-runexec"
    backend_version: str | None = None
    backend_returncode: int
    command: CommandSpec
    limits: ResourceLimits
    measurements: ExecutionMeasurements
    return_value: int | None = None
    exit_signal: int | None = None
    termination_reason: str | None = None
    timed_out: bool = False
    combined_output_log: Path
    raw_measurements: dict[str, str] = Field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return (
            self.backend_returncode == 0
            and not self.timed_out
            and self.termination_reason is None
            and self.exit_signal is None
            and self.return_value == 0
        )
