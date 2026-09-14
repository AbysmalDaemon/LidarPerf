"""BenchExec ``runexec`` backend for process-tree resource measurement."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .models import (
    BenchExecCapability,
    CommandExecutionResult,
    CommandSpec,
    ExecutionMeasurements,
    ResourceLimits,
)

_TIME_KEYS = {"walltime", "cputime"}
_TIMEOUT_REASONS = {"cputime", "walltime", "softtimelimit", "timelimit"}
_MEMORY_PATTERN = re.compile(r"^(?P<value>\d+)(?:B)?$")
_MAX_DIAGNOSTIC_LENGTH = 600


class BenchExecError(RuntimeError):
    """Base error for BenchExec integration failures."""


class BenchExecUnavailableError(BenchExecError):
    """Raised when ``runexec`` cannot be used on the current host."""


class BenchExecOutputError(BenchExecError):
    """Raised when ``runexec`` does not emit the measurements LidarPerf requires."""


def _format_seconds(value: float) -> str:
    return f"{value:.12g}s"


def _format_ids(values: tuple[int, ...]) -> str:
    return ",".join(str(value) for value in values)


def _compact_diagnostic(value: str) -> str:
    compact = " ".join(value.split())
    if len(compact) <= _MAX_DIAGNOSTIC_LENGTH:
        return compact
    return compact[: _MAX_DIAGNOSTIC_LENGTH - 3] + "..."


def _parse_time(value: str, key: str) -> float:
    normalized = value[:-1] if value.endswith("s") else value
    try:
        result = float(normalized)
    except ValueError as exc:
        raise BenchExecOutputError(f"invalid {key} value from runexec: {value!r}") from exc
    if result < 0:
        raise BenchExecOutputError(f"negative {key} value from runexec: {value!r}")
    return result


def _parse_memory(value: str) -> int:
    match = _MEMORY_PATTERN.fullmatch(value)
    if not match:
        raise BenchExecOutputError(f"invalid memory value from runexec: {value!r}")
    return int(match.group("value"))


def parse_runexec_stdout(stdout: str) -> dict[str, str]:
    """Extract stable ``key=value`` run results from runexec's mixed stdout."""

    measurements: dict[str, str] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", key):
            continue
        measurements[key] = value.strip()
    return measurements


class BenchExecBackend:
    """Execute one command through BenchExec's stable ``runexec`` CLI."""

    def __init__(self, runexec_path: str | Path | None = None, *, container_mode: bool = False):
        discovered = str(runexec_path) if runexec_path is not None else shutil.which("runexec")
        self._runexec_path = discovered
        self._container_mode = container_mode
        self._version: str | None = None

    @property
    def runexec_path(self) -> str | None:
        return self._runexec_path

    @property
    def container_mode(self) -> bool:
        return self._container_mode

    def _require_available(self) -> str:
        if platform.system().lower() != "linux":
            raise BenchExecUnavailableError("BenchExec-controlled execution is Linux-only in v0.1")
        if not self._runexec_path:
            raise BenchExecUnavailableError(
                "runexec was not found; install the optional benchmark dependency "
                "with `pip install 'lidarperf[benchmark]'`"
            )
        return self._runexec_path

    def version(self) -> str | None:
        """Return a normalized runexec version string when discoverable."""

        if self._version is not None:
            return self._version
        executable = self._require_available()
        try:
            result = subprocess.run(
                [executable, "--version"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise BenchExecUnavailableError(f"cannot execute runexec: {exc}") from exc
        if result.returncode != 0:
            return None
        line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), None)
        self._version = line
        return line

    def build_command(
        self,
        command: CommandSpec,
        limits: ResourceLimits,
        combined_output_log: Path,
    ) -> tuple[str, ...]:
        """Build the exact runexec command without invoking a shell."""

        executable = self._require_available()
        args: list[str] = [executable, "--output", str(combined_output_log)]
        if not self._container_mode:
            args.append("--no-container")
        if command.working_directory is not None:
            args.extend(("--dir", str(command.working_directory)))
        if limits.cpu_time_s is not None:
            args.extend(("--timelimit", _format_seconds(limits.cpu_time_s)))
        if limits.wall_time_s is not None:
            args.extend(("--walltimelimit", _format_seconds(limits.wall_time_s)))
        if limits.memory_bytes is not None:
            args.extend(("--memlimit", str(limits.memory_bytes)))
        if limits.cpu_cores:
            args.extend(("--cores", _format_ids(limits.cpu_cores)))
        if limits.memory_nodes:
            args.extend(("--memoryNodes", _format_ids(limits.memory_nodes)))
        args.append("--")
        args.extend(command.argv)
        return tuple(args)

    def execute(
        self,
        command: CommandSpec,
        *,
        combined_output_log: Path,
        limits: ResourceLimits | None = None,
    ) -> CommandExecutionResult:
        """Execute one process tree and normalize BenchExec's measurements."""

        selected_limits = limits or ResourceLimits()
        if combined_output_log.exists():
            raise FileExistsError(
                f"refusing to replace existing combined output log: {combined_output_log}"
            )
        combined_output_log.parent.mkdir(parents=True, exist_ok=True)
        args = self.build_command(command, selected_limits, combined_output_log)
        environment = os.environ.copy()
        environment.update(command.environment)
        try:
            result = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
        except OSError as exc:
            raise BenchExecUnavailableError(f"cannot execute runexec: {exc}") from exc
        raw = parse_runexec_stdout(result.stdout)
        if not _TIME_KEYS.issubset(raw):
            diagnostic = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
            raise BenchExecOutputError(
                "runexec did not report both walltime and cputime; "
                f"backend exit={result.returncode}: {_compact_diagnostic(diagnostic)}"
            )
        wall_time = _parse_time(raw["walltime"], "walltime")
        cpu_time = _parse_time(raw["cputime"], "cputime")
        memory = _parse_memory(raw["memory"]) if "memory" in raw else None

        def parse_optional_int(key: str) -> int | None:
            value = raw.get(key)
            if value is None:
                return None
            try:
                return int(value)
            except ValueError as exc:
                raise BenchExecOutputError(
                    f"invalid integer {key} value from runexec: {value!r}"
                ) from exc

        termination_reason = raw.get("terminationreason")
        timed_out = termination_reason in _TIMEOUT_REASONS
        return CommandExecutionResult(
            backend_version=self.version(),
            backend_returncode=result.returncode,
            command=command,
            limits=selected_limits,
            measurements=ExecutionMeasurements(
                wall_time_s=wall_time,
                cpu_time_s=cpu_time,
                peak_memory_bytes=memory,
            ),
            return_value=parse_optional_int("returnvalue"),
            exit_signal=parse_optional_int("exitsignal"),
            termination_reason=termination_reason,
            timed_out=timed_out,
            combined_output_log=combined_output_log,
            raw_measurements=raw,
        )

    def probe_capability(self) -> BenchExecCapability:
        """Actively verify that runexec can produce controlled process-tree measurements."""

        installed = self._runexec_path is not None
        try:
            backend_version = self.version()
        except BenchExecUnavailableError as exc:
            return BenchExecCapability(
                backend_version=None,
                installed=installed,
                controlled_ready=False,
                reason=str(exc),
            )

        with tempfile.TemporaryDirectory(prefix="lidarperf-benchexec-probe-") as directory:
            output = Path(directory) / "process.log"
            try:
                result = self.execute(
                    CommandSpec(argv=(sys.executable, "-c", "pass")),
                    combined_output_log=output,
                )
            except BenchExecError as exc:
                reason = str(exc)
                if "cgroup" in reason.lower():
                    reason = (
                        "runexec is installed but cannot access delegated cgroups required for "
                        "controlled CPU/memory accounting on this host"
                    )
                return BenchExecCapability(
                    backend_version=backend_version,
                    installed=installed,
                    controlled_ready=False,
                    reason=reason,
                )

        if not result.succeeded:
            return BenchExecCapability(
                backend_version=backend_version,
                installed=installed,
                controlled_ready=False,
                reason="runexec probe process did not complete successfully",
            )
        if result.measurements.peak_memory_bytes is None:
            return BenchExecCapability(
                backend_version=backend_version,
                installed=installed,
                controlled_ready=False,
                reason="runexec probe did not provide process-tree memory measurement",
            )
        return BenchExecCapability(
            backend_version=backend_version,
            installed=installed,
            controlled_ready=True,
        )
