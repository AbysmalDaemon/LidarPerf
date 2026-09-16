"""Run a small real Docker-backend validation and write durable evidence."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from lidarperf.backends import DockerBackend, DockerMount, DockerRunSpec

IMAGE = "alpine:3.20"
OUTPUT = Path("docs/validation/step15_docker_backend.json")
WORK = Path(".step15-docker-validation").resolve()


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    output_dir = WORK / "output"
    output_dir.mkdir()
    process_log = WORK / "process.log"

    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    cpu_cores = tuple(affinity[:1])
    backend = DockerBackend()
    capability = backend.probe_capability()
    if not capability.daemon_reachable:
        raise RuntimeError(capability.reason or "Docker daemon is unreachable")

    spec = DockerRunSpec(
        image=IMAGE,
        command=(
            "sh",
            "-c",
            'printf "%s\\n" "$LIDARPERF_VALIDATION" > /out/result.txt; '
            "echo docker-backend-ok",
        ),
        mounts=(DockerMount(source=output_dir, target="/out", read_only=False),),
        cpu_cores=cpu_cores,
        network="none",
        environment={"LIDARPERF_VALIDATION": "step15"},
        timeout_s=30.0,
    )
    result = backend.execute(spec, combined_output_log=process_log)
    if not result.succeeded:
        raise RuntimeError(
            "Docker validation container failed: "
            f"return={result.return_code}, timed_out={result.timed_out}"
        )
    produced = (output_dir / "result.txt").read_text(encoding="utf-8").strip()
    if produced != "step15":
        raise RuntimeError(f"unexpected bind-mount output: {produced!r}")
    log_text = process_log.read_text(encoding="utf-8").strip()
    if "docker-backend-ok" not in log_text:
        raise RuntimeError("combined container output was not captured")

    evidence = {
        "schema_version": "lidarperf.step15-docker-validation.v1",
        "purpose": "functional Docker backend integration evidence",
        "authoritative_performance": False,
        "authority_reason": (
            "ordinary GitHub-hosted runner and Docker v0.1 does not claim process-tree "
            "CPU/memory accounting across the daemon boundary"
        ),
        "capability": capability.model_dump(mode="json"),
        "image": result.image.model_dump(mode="json"),
        "execution_metadata": result.execution_metadata(),
        "execution_result": {
            "timing_scope": result.timing_scope,
            "wall_time_s": result.wall_time_s,
            "return_code": result.return_code,
            "timed_out": result.timed_out,
            "cleanup_error": result.cleanup_error,
        },
        "validation": {
            "network_disabled": spec.network == "none",
            "immutable_runtime_image": result.image.repo_digest or result.image.image_id,
            "bind_mount_round_trip": produced,
            "combined_output": log_text,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.rmtree(WORK)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
