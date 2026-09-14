"""Execution backends for LidarPerf."""

from .benchexec import (
    BenchExecBackend,
    BenchExecError,
    BenchExecOutputError,
    BenchExecUnavailableError,
    parse_runexec_stdout,
)
from .evalio import (
    EvalioBackend,
    EvalioCapability,
    EvalioError,
    EvalioOutputError,
    EvalioResultPaths,
    EvalioUnavailableError,
    build_evalio_run_command,
    evalio_version,
    evaluate_evalio_outputs,
    expected_evalio_result_paths,
    load_evalio_trajectory,
    parse_evalio_trajectory,
    probe_evalio,
)
from .models import (
    BenchExecCapability,
    CommandExecutionResult,
    CommandSpec,
    ExecutionMeasurements,
    ResourceLimits,
)

__all__ = [
    "BenchExecBackend",
    "BenchExecCapability",
    "BenchExecError",
    "BenchExecOutputError",
    "BenchExecUnavailableError",
    "CommandExecutionResult",
    "CommandSpec",
    "EvalioBackend",
    "EvalioCapability",
    "EvalioError",
    "EvalioOutputError",
    "EvalioResultPaths",
    "EvalioUnavailableError",
    "ExecutionMeasurements",
    "ResourceLimits",
    "build_evalio_run_command",
    "evalio_version",
    "evaluate_evalio_outputs",
    "expected_evalio_result_paths",
    "load_evalio_trajectory",
    "parse_evalio_trajectory",
    "parse_runexec_stdout",
    "probe_evalio",
]
