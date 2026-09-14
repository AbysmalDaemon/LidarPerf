"""Integration surface for evalio-backed LiDAR odometry experiments."""

from __future__ import annotations

import csv
import importlib.metadata
import shutil
from dataclasses import dataclass
from io import StringIO
from pathlib import Path, PurePosixPath

from lidarperf.spec.models import BenchmarkProtocol
from lidarperf.trajectory import (
    EvaluationSupport,
    Trajectory,
    TrajectoryEvaluation,
    evaluate_trajectory,
    parse_tum,
)

from .models import CommandSpec


class EvalioError(RuntimeError):
    """Base error for evalio integration failures."""


class EvalioUnavailableError(EvalioError):
    """Raised when the optional evalio integration is not installed."""


class EvalioOutputError(EvalioError):
    """Raised when evalio output files are absent or structurally unexpected."""


@dataclass(frozen=True, slots=True)
class EvalioCapability:
    """Availability information for the optional evalio backend."""

    installed: bool
    executable: str | None
    version: str | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class EvalioResultPaths:
    """Canonical output locations produced by ``evalio run`` for one experiment."""

    estimate: Path
    ground_truth: Path


def _safe_dataset_path(dataset: str) -> PurePosixPath:
    if not dataset or "\\" in dataset or dataset.startswith("/") or "//" in dataset:
        raise ValueError("dataset must be a canonical relative evalio dataset name")
    path = PurePosixPath(dataset)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("dataset must not contain empty, dot, or parent components")
    if len(path.parts) < 2:
        raise ValueError("evalio dataset names must include dataset and sequence, e.g. a/b")
    return path


def _safe_pipeline_name(pipeline: str) -> str:
    if (
        not pipeline
        or "/" in pipeline
        or "\\" in pipeline
        or pipeline in {".", ".."}
        or "\x00" in pipeline
    ):
        raise ValueError("pipeline must be a single canonical evalio pipeline name")
    return pipeline


def evalio_version() -> str | None:
    """Return the installed evalio distribution version without importing evalio itself."""

    try:
        return importlib.metadata.version("evalio")
    except importlib.metadata.PackageNotFoundError:
        return None


def probe_evalio(executable: str = "evalio") -> EvalioCapability:
    """Report whether the evalio package and CLI entry point are both available."""

    version = evalio_version()
    resolved = shutil.which(executable)
    if version is None and resolved is None:
        return EvalioCapability(
            installed=False,
            executable=None,
            version=None,
            reason="evalio package and CLI entry point are not installed",
        )
    if version is None:
        return EvalioCapability(
            installed=False,
            executable=resolved,
            version=None,
            reason="evalio CLI exists but Python distribution metadata is unavailable",
        )
    if resolved is None:
        return EvalioCapability(
            installed=False,
            executable=None,
            version=version,
            reason=f"evalio {version} is installed but the CLI entry point is not on PATH",
        )
    return EvalioCapability(installed=True, executable=resolved, version=version)


def build_evalio_run_command(
    *,
    dataset: str,
    pipeline: str,
    output_dir: str | Path,
    length: int | None = None,
    executable: str = "evalio",
) -> CommandSpec:
    """Build the shell-free command used to launch one evalio experiment."""

    dataset_path = _safe_dataset_path(dataset)
    pipeline_name = _safe_pipeline_name(pipeline)
    if length is not None and length <= 0:
        raise ValueError("length must be positive when provided")
    argv = [
        executable,
        "run",
        "-o",
        str(Path(output_dir)),
        "-d",
        dataset_path.as_posix(),
        "-p",
        pipeline_name,
    ]
    if length is not None:
        argv.extend(("-l", str(length)))
    return CommandSpec(argv=tuple(argv))


def expected_evalio_result_paths(
    output_dir: str | Path,
    *,
    dataset: str,
    pipeline: str,
) -> EvalioResultPaths:
    """Return the result and normalized ground-truth paths written by evalio."""

    dataset_path = _safe_dataset_path(dataset)
    pipeline_name = _safe_pipeline_name(pipeline)
    root = Path(output_dir).joinpath(*dataset_path.parts)
    return EvalioResultPaths(
        estimate=root / f"{pipeline_name}.csv",
        ground_truth=root / "gt.csv",
    )


def parse_evalio_trajectory(text: str, *, body_frame: str = "body") -> Trajectory:
    """Parse evalio's metadata-prefixed CSV trajectory into LidarPerf's canonical form.

    evalio serializes poses as ``timestamp,x,y,z,qx,qy,qz,qw`` and prefixes
    metadata/header lines with ``#``. We intentionally parse the serialized
    interchange representation instead of relying on evalio's Python trajectory
    object so result bundles remain readable without evalio installed.
    """

    tum_lines: list[str] = []
    reader = csv.reader(StringIO(text))
    for line_number, row in enumerate(reader, start=1):
        if not row or not any(field.strip() for field in row):
            continue
        if row[0].lstrip().startswith("#"):
            continue
        if len(row) != 8:
            raise EvalioOutputError(
                f"line {line_number}: expected 8 evalio trajectory fields, found {len(row)}"
            )
        fields = [field.strip() for field in row]
        tum_lines.append(" ".join(fields))
    if not tum_lines:
        raise EvalioOutputError("evalio trajectory contains no pose rows")
    return parse_tum("\n".join(tum_lines) + "\n", body_frame=body_frame)


def load_evalio_trajectory(path: str | Path, *, body_frame: str = "body") -> Trajectory:
    """Load an evalio CSV trajectory from disk."""

    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvalioOutputError(f"cannot read evalio trajectory {source}: {exc}") from exc
    return parse_evalio_trajectory(text, body_frame=body_frame)


def evaluate_evalio_outputs(
    paths: EvalioResultPaths,
    protocol: BenchmarkProtocol,
    *,
    body_frame: str | None = None,
    support: EvaluationSupport | None = None,
) -> TrajectoryEvaluation:
    """Evaluate one evalio result using LidarPerf's protocol-defined metrics."""

    frame = body_frame or protocol.trajectory.evaluation_frame
    if not paths.estimate.is_file():
        raise EvalioOutputError(f"evalio estimate is missing: {paths.estimate}")
    if not paths.ground_truth.is_file():
        raise EvalioOutputError(f"evalio normalized ground truth is missing: {paths.ground_truth}")
    estimate = load_evalio_trajectory(paths.estimate, body_frame=frame)
    reference = load_evalio_trajectory(paths.ground_truth, body_frame=frame)
    return evaluate_trajectory(estimate, reference, protocol, support=support)


class EvalioBackend:
    """Thin adapter around evalio's CLI and serialized experiment outputs.

    The adapter deliberately does not duplicate evalio's dataset or estimator
    registries. It builds a command that can be executed by LidarPerf's process
    backend, then parses the resulting portable CSV files with LidarPerf's own
    metric semantics.
    """

    def __init__(self, executable: str = "evalio") -> None:
        self.executable = executable

    def probe_capability(self) -> EvalioCapability:
        return probe_evalio(self.executable)

    def command(
        self,
        *,
        dataset: str,
        pipeline: str,
        output_dir: str | Path,
        length: int | None = None,
    ) -> CommandSpec:
        capability = self.probe_capability()
        if not capability.installed:
            raise EvalioUnavailableError(capability.reason or "evalio is unavailable")
        return build_evalio_run_command(
            dataset=dataset,
            pipeline=pipeline,
            output_dir=output_dir,
            length=length,
            executable=self.executable,
        )

    def result_paths(
        self,
        output_dir: str | Path,
        *,
        dataset: str,
        pipeline: str,
    ) -> EvalioResultPaths:
        return expected_evalio_result_paths(output_dir, dataset=dataset, pipeline=pipeline)

    def evaluate(
        self,
        output_dir: str | Path,
        *,
        dataset: str,
        pipeline: str,
        protocol: BenchmarkProtocol,
        support: EvaluationSupport | None = None,
    ) -> TrajectoryEvaluation:
        paths = self.result_paths(output_dir, dataset=dataset, pipeline=pipeline)
        return evaluate_evalio_outputs(paths, protocol, support=support)
