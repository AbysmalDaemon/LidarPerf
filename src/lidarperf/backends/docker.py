"""Docker CLI backend for opaque external estimator execution."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NETWORK_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_MAX_DIAGNOSTIC_LENGTH = 600


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DockerError(RuntimeError):
    """Base error for Docker backend failures."""


class DockerUnavailableError(DockerError):
    """Raised when Docker CLI or daemon access is unavailable."""


class DockerImageError(DockerError):
    """Raised when an image cannot be resolved to immutable provenance."""


class DockerMount(_FrozenModel):
    """One explicit bind mount made visible to the container."""

    source: Path
    target: str
    read_only: bool = True

    @field_validator("source")
    @classmethod
    def source_is_absolute_and_mount_safe(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("Docker mount source must be an absolute host path")
        if "," in str(value) or "\x00" in str(value):
            raise ValueError("Docker mount source contains a character unsafe for --mount")
        return value

    @field_validator("target")
    @classmethod
    def target_is_safe_absolute_posix_path(cls, value: str) -> str:
        if not value.startswith("/") or value == "/" or "\x00" in value or "," in value:
            raise ValueError("Docker mount target must be a safe absolute container path")
        path = PurePosixPath(value)
        if ".." in path.parts or path.as_posix() != value:
            raise ValueError("Docker mount target must be canonical and must not contain '..'")
        return value


class DockerGpuAccess(_FrozenModel):
    """Declared GPU access for a container execution."""

    mode: Literal["none", "all", "devices"] = "none"
    device_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_devices(self) -> Self:
        if self.mode == "devices":
            if not self.device_ids:
                raise ValueError("devices GPU mode requires at least one device ID")
            if any(not item or "," in item or "\x00" in item for item in self.device_ids):
                raise ValueError("GPU device IDs must be non-empty and comma-free")
        elif self.device_ids:
            raise ValueError("GPU device IDs are only valid in devices mode")
        if len(set(self.device_ids)) != len(self.device_ids):
            raise ValueError("GPU device IDs must be unique")
        return self


class DockerRunSpec(_FrozenModel):
    """Declared container semantics that affect benchmark meaning."""

    image: str = Field(min_length=1)
    command: tuple[str, ...] = ()
    entrypoint: str | None = None
    mounts: tuple[DockerMount, ...] = ()
    cpu_cores: tuple[int, ...] = ()
    gpu_access: DockerGpuAccess = Field(default_factory=DockerGpuAccess)
    network: str = "none"
    environment: dict[str, str] = Field(default_factory=dict)
    working_directory: str | None = None
    memory_limit_bytes: int | None = Field(default=None, gt=0)
    timeout_s: float | None = Field(default=None, gt=0)

    @field_validator("image", "entrypoint")
    @classmethod
    def strings_have_no_nul(cls, value: str | None) -> str | None:
        if value is not None and "\x00" in value:
            raise ValueError("Docker string fields must not contain NUL bytes")
        return value

    @field_validator("command")
    @classmethod
    def command_has_no_nul(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any("\x00" in item for item in value):
            raise ValueError("Docker command arguments must not contain NUL bytes")
        return value

    @field_validator("cpu_cores")
    @classmethod
    def normalize_cpu_cores(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(core < 0 for core in value):
            raise ValueError("CPU core IDs must be non-negative")
        return tuple(sorted(set(value)))

    @field_validator("network")
    @classmethod
    def network_is_explicit_and_safe(cls, value: str) -> str:
        if not _NETWORK_RE.fullmatch(value):
            raise ValueError("Docker network must be an explicit Docker network name")
        return value

    @field_validator("environment")
    @classmethod
    def environment_is_explicit(cls, value: dict[str, str]) -> dict[str, str]:
        for key, item in value.items():
            if not _ENV_KEY_RE.fullmatch(key):
                raise ValueError(f"invalid environment variable name: {key!r}")
            if "\x00" in item:
                raise ValueError(f"environment variable {key!r} contains a NUL byte")
        return dict(sorted(value.items()))

    @field_validator("working_directory")
    @classmethod
    def workdir_is_absolute(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("/") or "\x00" in value:
            raise ValueError("container working directory must be an absolute path")
        return value

    @model_validator(mode="after")
    def mount_targets_are_unique(self) -> Self:
        targets = [mount.target for mount in self.mounts]
        if len(targets) != len(set(targets)):
            raise ValueError("Docker mount targets must be unique")
        return self


class DockerImageProvenance(_FrozenModel):
    """Immutable identity of the image selected for one execution."""

    schema_version: Literal["lidarperf.docker-image.v1"] = "lidarperf.docker-image.v1"
    requested_image: str
    image_id: str
    repo_digest: str | None = None
    immutable_digest: str
    digest_kind: Literal["repo_digest", "image_id"]

    @field_validator("image_id", "immutable_digest")
    @classmethod
    def digest_is_sha256(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("Docker image digests must use sha256:<64 lowercase hex>")
        return value

    @field_validator("repo_digest")
    @classmethod
    def repo_digest_is_immutable(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "@" not in value or not _SHA256_RE.fullmatch(value.rsplit("@", 1)[1]):
            raise ValueError("repo_digest must be a name@sha256:<digest> reference")
        return value


class DockerCapability(_FrozenModel):
    """Docker execution and measurement capabilities available on this host."""

    schema_version: Literal["lidarperf.docker-capability.v1"] = "lidarperf.docker-capability.v1"
    backend: Literal["docker-cli"] = "docker-cli"
    installed: bool
    daemon_reachable: bool
    client_version: str | None = None
    server_version: str | None = None
    process_wall_time: bool = True
    process_cpu_time: bool = False
    peak_memory: bool = False
    per_frame_latency: bool = False
    internal_phase_timing: bool = False
    default_timing_scope: Literal["end_to_end"] = "end_to_end"
    authoritative_process_accounting: bool = False
    reason: str | None = None

    @model_validator(mode="after")
    def capability_is_consistent(self) -> Self:
        if self.daemon_reachable and not self.installed:
            raise ValueError("reachable Docker daemon requires an installed Docker CLI")
        if self.daemon_reachable and self.reason is not None:
            raise ValueError("reachable Docker capability must not include a failure reason")
        if not self.daemon_reachable and not self.reason:
            raise ValueError("unavailable Docker capability requires a reason")
        return self


class DockerExecutionResult(_FrozenModel):
    """Result and provenance of one opaque Docker execution."""

    schema_version: Literal["lidarperf.docker-execution.v1"] = "lidarperf.docker-execution.v1"
    backend: Literal["docker-cli"] = "docker-cli"
    client_version: str
    server_version: str
    timing_scope: Literal["end_to_end"] = "end_to_end"
    image: DockerImageProvenance
    spec: DockerRunSpec
    container_name: str
    wall_time_s: float = Field(ge=0)
    return_code: int | None = None
    timed_out: bool = False
    combined_output_log: Path
    cleanup_error: str | None = None
    capabilities: DockerCapability

    @property
    def succeeded(self) -> bool:
        return not self.timed_out and self.return_code == 0

    def execution_metadata(self) -> dict[str, Any]:
        """Return SPEC §66 metadata suitable for environment.json execution provenance."""

        mounts = [
            {
                "source": str(mount.source),
                "target": mount.target,
                "read_only": mount.read_only,
            }
            for mount in self.spec.mounts
        ]
        return {
            "backend": self.backend,
            "backend_version": {
                "client": self.client_version,
                "server": self.server_version,
            },
            "timing_scope": self.timing_scope,
            "capabilities": self.capabilities.model_dump(mode="json"),
            "container": {
                "image": self.image.requested_image,
                "image_id": self.image.image_id,
                "immutable_image_digest": self.image.immutable_digest,
                "digest_kind": self.image.digest_kind,
                "repo_digest": self.image.repo_digest,
                "entrypoint": self.spec.entrypoint,
                "command": list(self.spec.command),
                "mounts": mounts,
                "cpu_allocation": list(self.spec.cpu_cores),
                "gpu_access": self.spec.gpu_access.model_dump(mode="json"),
                "network": self.spec.network,
                "environment": self.spec.environment,
                "working_directory": self.spec.working_directory,
                "memory_limit_bytes": self.spec.memory_limit_bytes,
                "pull_policy": "never",
            },
        }


_Run = Callable[..., subprocess.CompletedProcess[str]]


def _compact_diagnostic(value: str) -> str:
    compact = " ".join(value.split())
    if len(compact) <= _MAX_DIAGNOSTIC_LENGTH:
        return compact
    return compact[: _MAX_DIAGNOSTIC_LENGTH - 3] + "..."


def _requested_repo_digest(image: str) -> str | None:
    if "@" not in image:
        return None
    digest = image.rsplit("@", 1)[1]
    return image if _SHA256_RE.fullmatch(digest) else None


def _select_repo_digest(image: str, repo_digests: list[str]) -> str | None:
    requested = _requested_repo_digest(image)
    if requested is not None:
        return requested
    valid = sorted(
        item
        for item in repo_digests
        if "@" in item and _SHA256_RE.fullmatch(item.rsplit("@", 1)[1])
    )
    return valid[0] if valid else None


class DockerBackend:
    """Run an opaque container with exact image and execution provenance.

    Docker daemon descendants are not children of the local ``docker`` client process. This
    v0.1 backend therefore measures end-to-end wall time with a monotonic clock but deliberately
    does not claim process-tree CPU time or peak memory. Wrapping only the Docker client in
    BenchExec would be misleading and is not treated as authoritative container accounting.
    """

    def __init__(
        self,
        docker_path: str | Path | None = None,
        *,
        runner: _Run | None = None,
    ) -> None:
        discovered = str(docker_path) if docker_path is not None else shutil.which("docker")
        self._docker_path = discovered
        self._run = runner or subprocess.run
        self._capability: DockerCapability | None = None

    @property
    def docker_path(self) -> str | None:
        return self._docker_path

    def _require_available(self) -> str:
        if not self._docker_path:
            raise DockerUnavailableError("docker CLI was not found on PATH")
        return self._docker_path

    def probe_capability(self) -> DockerCapability:
        """Check both Docker CLI presence and daemon reachability."""

        if self._capability is not None:
            return self._capability
        if not self._docker_path:
            self._capability = DockerCapability(
                installed=False,
                daemon_reachable=False,
                reason="docker CLI was not found on PATH",
            )
            return self._capability

        try:
            result = self._run(
                [
                    self._docker_path,
                    "version",
                    "--format",
                    "{{.Client.Version}}|{{.Server.Version}}",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            self._capability = DockerCapability(
                installed=True,
                daemon_reachable=False,
                reason=f"cannot execute docker CLI: {exc}",
            )
            return self._capability

        if result.returncode != 0:
            diagnostic = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
            self._capability = DockerCapability(
                installed=True,
                daemon_reachable=False,
                reason="Docker daemon is unreachable: " + _compact_diagnostic(diagnostic),
            )
            return self._capability

        fields = result.stdout.strip().split("|", 1)
        if len(fields) != 2 or not all(fields):
            self._capability = DockerCapability(
                installed=True,
                daemon_reachable=False,
                reason="docker version did not report both client and server versions",
            )
            return self._capability

        self._capability = DockerCapability(
            installed=True,
            daemon_reachable=True,
            client_version=fields[0],
            server_version=fields[1],
        )
        return self._capability

    def inspect_image(self, image: str) -> DockerImageProvenance:
        """Resolve a local Docker image to immutable content-addressed provenance."""

        executable = self._require_available()
        capability = self.probe_capability()
        if not capability.daemon_reachable:
            raise DockerUnavailableError(capability.reason or "Docker daemon is unreachable")
        try:
            result = self._run(
                [executable, "image", "inspect", image],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise DockerUnavailableError(f"cannot inspect Docker image: {exc}") from exc
        if result.returncode != 0:
            diagnostic = result.stderr.strip() or result.stdout.strip() or "image not found"
            raise DockerImageError(
                f"cannot inspect local image {image!r}: {_compact_diagnostic(diagnostic)}"
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise DockerImageError("docker image inspect returned invalid JSON") from exc
        if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
            raise DockerImageError("docker image inspect did not return exactly one image object")

        record = payload[0]
        image_id = record.get("Id")
        repo_digests = record.get("RepoDigests") or []
        if not isinstance(image_id, str) or not _SHA256_RE.fullmatch(image_id):
            raise DockerImageError("Docker image does not expose a valid sha256 image ID")
        if not isinstance(repo_digests, list) or not all(
            isinstance(item, str) for item in repo_digests
        ):
            raise DockerImageError("Docker image RepoDigests field is malformed")

        repo_digest = _select_repo_digest(image, repo_digests)
        if repo_digest is not None:
            immutable_digest = repo_digest.rsplit("@", 1)[1]
            digest_kind: Literal["repo_digest", "image_id"] = "repo_digest"
        else:
            immutable_digest = image_id
            digest_kind = "image_id"
        return DockerImageProvenance(
            requested_image=image,
            image_id=image_id,
            repo_digest=repo_digest,
            immutable_digest=immutable_digest,
            digest_kind=digest_kind,
        )

    def build_command(
        self,
        spec: DockerRunSpec,
        image: DockerImageProvenance,
        *,
        container_name: str,
    ) -> tuple[str, ...]:
        """Build the exact Docker CLI argv without invoking a shell or pulling an image."""

        executable = self._require_available()
        args = [
            executable,
            "run",
            "--rm",
            "--pull",
            "never",
            "--name",
            container_name,
            "--network",
            spec.network,
        ]
        if spec.cpu_cores:
            args.extend(("--cpuset-cpus", ",".join(str(core) for core in spec.cpu_cores)))
        if spec.memory_limit_bytes is not None:
            args.extend(("--memory", str(spec.memory_limit_bytes)))
        if spec.gpu_access.mode == "all":
            args.extend(("--gpus", "all"))
        elif spec.gpu_access.mode == "devices":
            args.extend(("--gpus", "device=" + ",".join(spec.gpu_access.device_ids)))
        for key, value in spec.environment.items():
            args.extend(("--env", f"{key}={value}"))
        for mount in spec.mounts:
            mount_arg = f"type=bind,source={mount.source},target={mount.target}"
            if mount.read_only:
                mount_arg += ",readonly"
            args.extend(("--mount", mount_arg))
        if spec.working_directory is not None:
            args.extend(("--workdir", spec.working_directory))
        if spec.entrypoint is not None:
            args.extend(("--entrypoint", spec.entrypoint))

        runtime_image = image.repo_digest or image.image_id
        args.append(runtime_image)
        args.extend(spec.command)
        return tuple(args)

    def execute(self, spec: DockerRunSpec, *, combined_output_log: Path) -> DockerExecutionResult:
        """Run one container and measure its end-to-end elapsed wall time."""

        capability = self.probe_capability()
        if not capability.daemon_reachable:
            raise DockerUnavailableError(capability.reason or "Docker daemon is unreachable")
        assert capability.client_version is not None
        assert capability.server_version is not None

        image = self.inspect_image(spec.image)
        if combined_output_log.exists():
            raise FileExistsError(
                f"refusing to replace existing combined output log: {combined_output_log}"
            )
        combined_output_log.parent.mkdir(parents=True, exist_ok=True)
        container_name = "lidarperf-" + uuid4().hex[:16]
        args = self.build_command(spec, image, container_name=container_name)
        timed_out = False
        return_code: int | None = None
        cleanup_error: str | None = None

        start_ns = time.monotonic_ns()
        with combined_output_log.open("w", encoding="utf-8") as output:
            try:
                result = self._run(
                    args,
                    check=False,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=spec.timeout_s,
                )
                return_code = result.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                cleanup = self._run(
                    [self._require_available(), "rm", "-f", container_name],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if cleanup.returncode != 0:
                    diagnostic = cleanup.stderr.strip() or cleanup.stdout.strip()
                    cleanup_error = _compact_diagnostic(diagnostic or "container cleanup failed")
            except OSError as exc:
                raise DockerUnavailableError(f"cannot execute docker run: {exc}") from exc
        wall_time_s = (time.monotonic_ns() - start_ns) / 1_000_000_000
        if not math.isfinite(wall_time_s):
            raise DockerError("monotonic Docker wall-time measurement is not finite")

        return DockerExecutionResult(
            client_version=capability.client_version,
            server_version=capability.server_version,
            image=image,
            spec=spec,
            container_name=container_name,
            wall_time_s=wall_time_s,
            return_code=return_code,
            timed_out=timed_out,
            combined_output_log=combined_output_log,
            cleanup_error=cleanup_error,
            capabilities=capability,
        )
