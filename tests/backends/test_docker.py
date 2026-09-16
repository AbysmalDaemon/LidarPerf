import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from lidarperf.backends import (
    DockerBackend,
    DockerGpuAccess,
    DockerImageError,
    DockerImageProvenance,
    DockerMount,
    DockerRunSpec,
)

IMAGE_ID = "sha256:" + "1" * 64
REPO_DIGEST = "example/estimator@sha256:" + "2" * 64


class FakeDockerRunner:
    def __init__(self, *, timeout: bool = False, repo_digests: list[str] | None = None) -> None:
        self.timeout = timeout
        self.repo_digests = [REPO_DIGEST] if repo_digests is None else repo_digests
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args, **kwargs):
        argv = tuple(str(item) for item in args)
        self.calls.append(argv)
        if argv[1] == "version":
            return subprocess.CompletedProcess(argv, 0, "27.3.1\t27.3.1\n", "")
        if argv[1:3] == ("image", "inspect"):
            payload = [{"Id": IMAGE_ID, "RepoDigests": self.repo_digests}]
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")
        if argv[1] == "run":
            if self.timeout:
                raise subprocess.TimeoutExpired(argv, 0.01)
            output = kwargs.get("stdout")
            if output is not None:
                output.write("container output\n")
            return subprocess.CompletedProcess(argv, 0)
        if argv[1:3] == ("rm", "-f"):
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected fake Docker invocation: {argv}")


def test_probe_reports_honest_measurement_capabilities() -> None:
    runner = FakeDockerRunner()
    capability = DockerBackend("/usr/bin/docker", runner=runner).probe_capability()

    assert capability.installed is True
    assert capability.daemon_reachable is True
    assert capability.process_wall_time is True
    assert capability.process_cpu_time is False
    assert capability.peak_memory is False
    assert capability.default_timing_scope == "end_to_end"
    assert capability.authoritative_process_accounting is False


def test_probe_reports_unreachable_daemon() -> None:
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "", "Cannot connect to Docker daemon")

    capability = DockerBackend("/usr/bin/docker", runner=runner).probe_capability()

    assert capability.installed is True
    assert capability.daemon_reachable is False
    assert "unreachable" in (capability.reason or "").lower()


def test_image_inspection_prefers_registry_digest() -> None:
    runner = FakeDockerRunner()
    provenance = DockerBackend("/usr/bin/docker", runner=runner).inspect_image("example/estimator:1")

    assert provenance.image_id == IMAGE_ID
    assert provenance.repo_digest == REPO_DIGEST
    assert provenance.immutable_digest == "sha256:" + "2" * 64
    assert provenance.digest_kind == "repo_digest"


def test_image_inspection_falls_back_to_content_addressed_image_id() -> None:
    runner = FakeDockerRunner(repo_digests=[])
    provenance = DockerBackend("/usr/bin/docker", runner=runner).inspect_image("local:test")

    assert provenance.repo_digest is None
    assert provenance.immutable_digest == IMAGE_ID
    assert provenance.digest_kind == "image_id"


def test_image_inspection_rejects_malformed_image_identity() -> None:
    class BadRunner(FakeDockerRunner):
        def __call__(self, args, **kwargs):
            argv = tuple(str(item) for item in args)
            if argv[1] == "version":
                return subprocess.CompletedProcess(argv, 0, "27.3.1\t27.3.1\n", "")
            if argv[1:3] == ("image", "inspect"):
                return subprocess.CompletedProcess(argv, 0, '[{"Id":"not-a-digest"}]', "")
            raise AssertionError(argv)

    with pytest.raises(DockerImageError, match="sha256 image ID"):
        DockerBackend("/usr/bin/docker", runner=BadRunner()).inspect_image("bad:test")


def test_build_command_uses_immutable_reference_and_declared_semantics(tmp_path: Path) -> None:
    source = tmp_path.resolve()
    spec = DockerRunSpec(
        image="example/estimator:1",
        command=("estimate", "--input", "/data"),
        entrypoint="/usr/local/bin/runner",
        mounts=(DockerMount(source=source, target="/data"),),
        cpu_cores=(3, 1, 3),
        gpu_access=DockerGpuAccess(mode="devices", device_ids=("0", "2")),
        network="none",
        environment={"OMP_NUM_THREADS": "2", "MODE": "benchmark"},
        working_directory="/work",
    )
    provenance = DockerImageProvenance(
        requested_image=spec.image,
        image_id=IMAGE_ID,
        repo_digest=REPO_DIGEST,
        immutable_digest="sha256:" + "2" * 64,
        digest_kind="repo_digest",
    )
    command = DockerBackend("docker").build_command(
        spec,
        provenance,
        container_name="lidarperf-test",
    )

    assert command[:7] == (
        "docker",
        "run",
        "--rm",
        "--pull",
        "never",
        "--name",
        "lidarperf-test",
    )
    assert ("--network", "none") == command[7:9]
    assert "--cpuset-cpus" in command
    assert command[command.index("--cpuset-cpus") + 1] == "1,3"
    assert command[command.index("--gpus") + 1] == "device=0,2"
    assert REPO_DIGEST in command
    assert "example/estimator:1" not in command
    assert command[-3:] == ("estimate", "--input", "/data")


def test_execute_captures_wall_time_log_and_spec66_metadata(tmp_path: Path) -> None:
    runner = FakeDockerRunner()
    source = tmp_path.resolve()
    spec = DockerRunSpec(
        image="example/estimator:1",
        command=("estimate",),
        mounts=(DockerMount(source=source, target="/dataset"),),
        cpu_cores=(0, 1),
        network="none",
        environment={"OMP_NUM_THREADS": "2"},
    )
    log = tmp_path / "process.log"

    result = DockerBackend("/usr/bin/docker", runner=runner).execute(
        spec,
        combined_output_log=log,
    )

    assert result.succeeded is True
    assert result.wall_time_s >= 0.0
    assert log.read_text(encoding="utf-8") == "container output\n"
    run_call = next(call for call in runner.calls if call[1] == "run")
    assert REPO_DIGEST in run_call
    metadata = result.execution_metadata()
    assert metadata["timing_scope"] == "end_to_end"
    assert metadata["container"]["immutable_image_digest"] == "sha256:" + "2" * 64
    assert metadata["container"]["mounts"][0]["source"] == str(source)
    assert metadata["container"]["cpu_allocation"] == [0, 1]
    assert metadata["container"]["gpu_access"] == {"mode": "none", "device_ids": []}
    assert metadata["container"]["network"] == "none"
    assert metadata["container"]["environment"] == {"OMP_NUM_THREADS": "2"}
    assert metadata["container"]["pull_policy"] == "never"
    assert metadata["capabilities"]["authoritative_process_accounting"] is False


def test_execute_timeout_force_removes_named_container(tmp_path: Path) -> None:
    runner = FakeDockerRunner(timeout=True)
    result = DockerBackend("/usr/bin/docker", runner=runner).execute(
        DockerRunSpec(image="example/estimator:1", timeout_s=0.01),
        combined_output_log=tmp_path / "process.log",
    )

    assert result.timed_out is True
    assert result.succeeded is False
    assert result.return_code is None
    cleanup = next(call for call in runner.calls if call[1:3] == ("rm", "-f"))
    assert cleanup[3] == result.container_name


def test_run_spec_rejects_ambiguous_or_unsafe_semantics(tmp_path: Path) -> None:
    relative = Path("relative-dataset")
    with pytest.raises(ValidationError, match="absolute host path"):
        DockerMount(source=relative, target="/data")
    with pytest.raises(ValidationError, match="targets must be unique"):
        DockerRunSpec(
            image="x",
            mounts=(
                DockerMount(source=tmp_path.resolve(), target="/data"),
                DockerMount(source=tmp_path.resolve(), target="/data"),
            ),
        )
    with pytest.raises(ValidationError, match="environment variable name"):
        DockerRunSpec(image="x", environment={"BAD-NAME": "1"})
    with pytest.raises(ValidationError, match="devices GPU mode"):
        DockerGpuAccess(mode="devices")
