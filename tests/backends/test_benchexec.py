import platform
from pathlib import Path

import pytest

from lidarperf.backends import (
    BenchExecBackend,
    BenchExecOutputError,
    CommandSpec,
    ResourceLimits,
    parse_runexec_stdout,
)


def test_resource_limits_normalize_ids() -> None:
    limits = ResourceLimits(cpu_cores=(4, 2, 4), memory_nodes=(1, 0, 1))
    assert limits.cpu_cores == (2, 4)
    assert limits.memory_nodes == (0, 1)


def test_parse_runexec_stdout_ignores_log_lines() -> None:
    parsed = parse_runexec_stdout(
        "2026-01-01 INFO Starting command\nreturnvalue=0\nwalltime=1.25s\n"
        "cputime=0.75s\nmemory=4096\n"
    )
    assert parsed == {
        "returnvalue": "0",
        "walltime": "1.25s",
        "cputime": "0.75s",
        "memory": "4096",
    }


@pytest.mark.skipif(platform.system().lower() != "linux", reason="BenchExec backend is Linux-only")
def test_build_command_has_explicit_boundary(tmp_path: Path) -> None:
    backend = BenchExecBackend("/usr/bin/runexec", container_mode=False)
    command = CommandSpec(argv=("tool", "--flag", "value"), working_directory=tmp_path)
    limits = ResourceLimits(
        cpu_time_s=5,
        wall_time_s=7.5,
        memory_bytes=1024,
        cpu_cores=(1, 3),
        memory_nodes=(0,),
    )
    result = backend.build_command(command, limits, tmp_path / "tool.log")
    assert result == (
        "/usr/bin/runexec",
        "--output",
        str(tmp_path / "tool.log"),
        "--no-container",
        "--dir",
        str(tmp_path),
        "--timelimit",
        "5s",
        "--walltimelimit",
        "7.5s",
        "--memlimit",
        "1024",
        "--cores",
        "1,3",
        "--memoryNodes",
        "0",
        "--",
        "tool",
        "--flag",
        "value",
    )


def _fake_runexec(
    path: Path,
    *,
    missing_metrics: bool = False,
    omit_memory: bool = False,
) -> Path:
    body = """#!/usr/bin/env python3
import os
import pathlib
import sys
if '--version' in sys.argv:
    print('runexec 3.31')
    raise SystemExit(0)
output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])
output.write_text('estimator output\\n', encoding='utf-8')
if os.environ.get('FAKE_TERMINATION'):
    print('terminationreason=walltime')
    print('exitsignal=9')
else:
    print('returnvalue=0')
"""
    if not missing_metrics:
        body += "print('walltime=0.25s')\nprint('cputime=0.125s')\n"
        if not omit_memory:
            body += "print('memory=4096B')\n"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.mark.skipif(platform.system().lower() != "linux", reason="BenchExec backend is Linux-only")
def test_execute_normalizes_fake_runexec_result(tmp_path: Path) -> None:
    backend = BenchExecBackend(_fake_runexec(tmp_path / "runexec"))
    output = tmp_path / "estimator.log"
    result = backend.execute(CommandSpec(argv=("ignored-tool",)), combined_output_log=output)
    assert result.succeeded is True
    assert result.backend_version == "runexec 3.31"
    assert result.measurements.wall_time_s == 0.25
    assert result.measurements.cpu_time_s == 0.125
    assert result.measurements.peak_memory_bytes == 4096
    assert result.measurements.cpu_core_equivalents == 0.5
    assert output.read_text(encoding="utf-8") == "estimator output\n"


@pytest.mark.skipif(platform.system().lower() != "linux", reason="BenchExec backend is Linux-only")
def test_execute_refuses_existing_output_log(tmp_path: Path) -> None:
    backend = BenchExecBackend(_fake_runexec(tmp_path / "runexec"))
    output = tmp_path / "estimator.log"
    output.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        backend.execute(CommandSpec(argv=("ignored-tool",)), combined_output_log=output)
    assert output.read_text(encoding="utf-8") == "keep"


@pytest.mark.skipif(platform.system().lower() != "linux", reason="BenchExec backend is Linux-only")
def test_execute_rejects_missing_core_measurements(tmp_path: Path) -> None:
    backend = BenchExecBackend(_fake_runexec(tmp_path / "runexec", missing_metrics=True))
    with pytest.raises(BenchExecOutputError, match="walltime and cputime"):
        backend.execute(
            CommandSpec(argv=("ignored-tool",)),
            combined_output_log=tmp_path / "estimator.log",
        )


@pytest.mark.skipif(platform.system().lower() != "linux", reason="BenchExec backend is Linux-only")
def test_execute_marks_walltime_termination(tmp_path: Path) -> None:
    backend = BenchExecBackend(_fake_runexec(tmp_path / "runexec"))
    result = backend.execute(
        CommandSpec(argv=("ignored-tool",), environment={"FAKE_TERMINATION": "1"}),
        combined_output_log=tmp_path / "estimator.log",
    )
    assert result.succeeded is False
    assert result.timed_out is True
    assert result.termination_reason == "walltime"
    assert result.exit_signal == 9
    assert result.return_value is None


@pytest.mark.skipif(platform.system().lower() != "linux", reason="BenchExec backend is Linux-only")
def test_probe_capability_requires_real_process_metrics(tmp_path: Path) -> None:
    backend = BenchExecBackend(_fake_runexec(tmp_path / "runexec"))
    capability = backend.probe_capability()
    assert capability.installed is True
    assert capability.controlled_ready is True
    assert capability.backend_version == "runexec 3.31"
    assert capability.reason is None


@pytest.mark.skipif(platform.system().lower() != "linux", reason="BenchExec backend is Linux-only")
def test_probe_capability_rejects_missing_memory_accounting(tmp_path: Path) -> None:
    backend = BenchExecBackend(_fake_runexec(tmp_path / "runexec", omit_memory=True))
    capability = backend.probe_capability()
    assert capability.installed is True
    assert capability.controlled_ready is False
    assert capability.reason == "runexec probe did not provide process-tree memory measurement"


@pytest.mark.skipif(platform.system().lower() != "linux", reason="BenchExec backend is Linux-only")
def test_probe_capability_reports_missing_core_measurements(tmp_path: Path) -> None:
    backend = BenchExecBackend(_fake_runexec(tmp_path / "runexec", missing_metrics=True))
    capability = backend.probe_capability()
    assert capability.installed is True
    assert capability.controlled_ready is False
    assert capability.reason is not None
    assert "walltime and cputime" in capability.reason
