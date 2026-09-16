from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"patch anchor missing in {path}: {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/lidarperf/backends/docker.py",
    "    working_directory: str | None = None\n    timeout_s: float | None = Field(default=None, gt=0)\n",
    "    working_directory: str | None = None\n    memory_limit_bytes: int | None = Field(default=None, gt=0)\n    timeout_s: float | None = Field(default=None, gt=0)\n",
)
replace_once(
    "src/lidarperf/backends/docker.py",
    '                "working_directory": self.spec.working_directory,\n                "pull_policy": "never",\n',
    '                "working_directory": self.spec.working_directory,\n                "memory_limit_bytes": self.spec.memory_limit_bytes,\n                "pull_policy": "never",\n',
)
replace_once(
    "src/lidarperf/backends/docker.py",
    '        if spec.cpu_cores:\n            args.extend(("--cpuset-cpus", ",".join(str(core) for core in spec.cpu_cores)))\n        if spec.gpu_access.mode == "all":\n',
    '        if spec.cpu_cores:\n            args.extend(("--cpuset-cpus", ",".join(str(core) for core in spec.cpu_cores)))\n        if spec.memory_limit_bytes is not None:\n            args.extend(("--memory", str(spec.memory_limit_bytes)))\n        if spec.gpu_access.mode == "all":\n',
)
replace_once(
    "tests/backends/test_docker.py",
    '        cpu_cores=(3, 1, 3),\n        gpu_access=DockerGpuAccess(mode="devices", device_ids=("0", "2")),\n',
    '        cpu_cores=(3, 1, 3),\n        memory_limit_bytes=536870912,\n        gpu_access=DockerGpuAccess(mode="devices", device_ids=("0", "2")),\n',
)
replace_once(
    "tests/backends/test_docker.py",
    '    assert command[command.index("--cpuset-cpus") + 1] == "1,3"\n    assert command[command.index("--gpus") + 1] == "device=0,2"\n',
    '    assert command[command.index("--cpuset-cpus") + 1] == "1,3"\n    assert command[command.index("--memory") + 1] == "536870912"\n    assert command[command.index("--gpus") + 1] == "device=0,2"\n',
)
replace_once(
    "tests/backends/test_docker.py",
    '        cpu_cores=(0, 1),\n        network="none",\n',
    '        cpu_cores=(0, 1),\n        memory_limit_bytes=268435456,\n        network="none",\n',
)
replace_once(
    "tests/backends/test_docker.py",
    '    assert metadata["container"]["cpu_allocation"] == [0, 1]\n    assert metadata["container"]["gpu_access"] == {"mode": "none", "device_ids": []}\n',
    '    assert metadata["container"]["cpu_allocation"] == [0, 1]\n    assert metadata["container"]["memory_limit_bytes"] == 268435456\n    assert metadata["container"]["gpu_access"] == {"mode": "none", "device_ids": []}\n',
)
replace_once(
    "tests/backends/test_docker.py",
    '    with pytest.raises(ValidationError, match="environment variable name"):\n        DockerRunSpec(image="x", environment={"BAD-NAME": "1"})\n',
    '    with pytest.raises(ValidationError):\n        DockerRunSpec(image="x", memory_limit_bytes=0)\n    with pytest.raises(ValidationError, match="environment variable name"):\n        DockerRunSpec(image="x", environment={"BAD-NAME": "1"})\n',
)
replace_once(
    "scripts/run_step15_docker_validation.py",
    '        cpu_cores=cpu_cores,\n        network="none",\n',
    '        cpu_cores=cpu_cores,\n        memory_limit_bytes=64 * 1024 * 1024,\n        network="none",\n',
)
replace_once(
    "scripts/run_step15_docker_validation.py",
    '            "network_disabled": spec.network == "none",\n            "immutable_runtime_image": result.image.repo_digest or result.image.image_id,\n',
    '            "network_disabled": spec.network == "none",\n            "memory_limit_bytes": spec.memory_limit_bytes,\n            "immutable_runtime_image": result.image.repo_digest or result.image.image_id,\n',
)
