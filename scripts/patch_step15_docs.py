from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"missing documentation anchor in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "README.md",
    "self-contained HTML/JSON reporting, and Bencher Metric Format export are implemented.",
    "self-contained HTML/JSON reporting, Bencher Metric Format export, and the first Docker CLI external-estimator backend are implemented.",
)
replace_once(
    "README.md",
    "- a verified Bencher Metric Format exporter with stable semantic benchmark identities and automatic alert suppression for evidence that is not authoritative enough for performance-regression claims.\n",
    "- a verified Bencher Metric Format exporter with stable semantic benchmark identities and automatic alert suppression for evidence that is not authoritative enough for performance-regression claims.\n- a Docker CLI backend for opaque external estimators with immutable image provenance, explicit bind mounts, CPU/memory limits, network/GPU declarations, timeout cleanup, and end-to-end wall-time semantics.\n",
)
replace_once(
    "README.md",
    "Step 14 implements `lidarperf export bencher`. The command verifies the source bundle through the reporting path and emits pure Bencher Metric Format JSON so the result can be consumed by Bencher without a LidarPerf-specific wrapper. Exported values are conservative medians from an explicit allowlist; LidarPerf does not fabricate Bencher lower/upper bounds from run-set spread. Dataset/protocol fingerprints and measurement class are part of the stable benchmark identity. Exploratory, non-conformant, partially failed, or otherwise non-authoritative evidence receives Bencher's `-bencher-ignore` suffix automatically, so it may be stored for history without creating performance alerts. The durable hosted example is `docs/validation/step14_kiss_hilti_bencher.json`.\n",
    "Step 14 implements `lidarperf export bencher`. The command verifies the source bundle through the reporting path and emits pure Bencher Metric Format JSON so the result can be consumed by Bencher without a LidarPerf-specific wrapper. Exported values are conservative medians from an explicit allowlist; LidarPerf does not fabricate Bencher lower/upper bounds from run-set spread. Dataset/protocol fingerprints and measurement class are part of the stable benchmark identity. Exploratory, non-conformant, partially failed, or otherwise non-authoritative evidence receives Bencher's `-bencher-ignore` suffix automatically, so it may be stored for history without creating performance alerts. The durable hosted example is `docs/validation/step14_kiss_hilti_bencher.json`.\n\nStep 15 adds the first Docker execution backend for estimators that are unsuitable for direct Python/evalio integration. A run resolves the requested image to an immutable repository digest (or content-addressed image ID fallback) and records Docker client/server versions, entrypoint/command, bind mounts, CPU allocation, memory limit, network mode, GPU access, working directory and declared environment. The backend executes the immutable image with `--pull never`, captures combined output, enforces timeouts with explicit cleanup, and measures end-to-end wall time. It deliberately reports `authoritative_process_accounting=false`: Docker daemon workloads are not descendants of the local CLI process, so wrapping only `docker run` in BenchExec would not honestly measure container CPU time or peak memory. The durable Alpine integration record is `docs/validation/step15_docker_backend.json`.\n",
)
replace_once(
    "README.md",
    "BenchExec writes command stdout and stderr into one output file; LidarPerf therefore names this artifact a **combined output log** at the backend layer rather than pretending the streams were measured separately. Result bundles accept either one `process.log` or a genuine `stdout.log` + `stderr.log` pair, never both. The backend disables BenchExec namespace/container mode by default so estimator output paths retain ordinary host filesystem semantics; software containerization remains a separate planned Docker backend.\n",
    "BenchExec writes command stdout and stderr into one output file; LidarPerf therefore names this artifact a **combined output log** at the backend layer rather than pretending the streams were measured separately. Result bundles accept either one `process.log` or a genuine `stdout.log` + `stderr.log` pair, never both. The backend disables BenchExec namespace/container mode by default so estimator output paths retain ordinary host filesystem semantics; software containerization is handled separately by the Docker backend described below.\n",
)
replace_once(
    "README.md",
    "For example, to exercise point-time semantics and deskew-related tests:\n",
    "### Docker backend\n\n`DockerBackend` is intended for opaque external estimators whose software environment is best represented by a container image. It uses Docker's CLI without invoking a shell, resolves the image to immutable content before execution, disables implicit pulls during the measured run, and records the execution semantics required by `SPEC.md`. Bind-mount sources must be absolute host paths; container targets must be canonical absolute POSIX paths. CPU sets, byte-exact memory limits, network mode and GPU access are explicit rather than inherited silently.\n\nDocker v0.1 is an **execution/provenance backend, not an authoritative CPU/RAM measurement backend**. It measures end-to-end elapsed wall time with a monotonic clock, while `process_cpu_time`, `peak_memory` and `authoritative_process_accounting` remain false. The Docker daemon owns the actual container processes, so timing/accounting the local Docker client process would be scientifically misleading. Controlled container performance claims therefore need a future accounting path that observes the container workload itself.\n\nThe declared container command and environment are benchmark provenance and may be recorded verbatim. Benchmark definitions should therefore not place credentials or other secrets in command arguments or environment values. A separate public-bundle sanitization step remains planned before release.\n\nFor example, to exercise point-time semantics and deskew-related tests:\n",
)

validation = Path("docs/validation/README.md")
text = validation.read_text(encoding="utf-8")
anchor = "- [`step14_kiss_hilti_bencher.json`](step14_kiss_hilti_bencher.json) is the first durable Bencher Metric Format export. It is derived from the verified Step 10 bundle and intentionally ends its benchmark identity with `-bencher-ignore`, so the hosted exploratory values may be stored without producing Bencher performance alerts. It is descriptive interoperability evidence, not a new benchmark run.\n"
addition = anchor + "- [`step15_docker_backend.json`](step15_docker_backend.json) is the first real Docker-backend integration record. It executes `alpine:3.20` by immutable digest with network disabled, one declared CPU, a 64 MiB memory cap and a writable bind mount. The run validates immutable-image resolution, mount round-trip, output capture and cleanup semantics. Its elapsed wall time is functional hosted evidence only; Docker v0.1 explicitly does not claim authoritative process CPU/memory accounting across the daemon boundary.\n"
if anchor not in text:
    raise RuntimeError("missing Step 14 validation anchor")
text = text.replace(anchor, addition, 1)
text += "\nReproduce the Step 15 Docker integration on a Linux host with a reachable Docker daemon:\n\n```bash\ndocker pull alpine:3.20\npython scripts/run_step15_docker_validation.py\n```\n\nThe committed validation uses `--network none`, an explicit CPU allocation and a 64 MiB memory limit. The image is executed by immutable repository digest with `--pull never`; the JSON records both requested and immutable image identities plus Docker client/server versions.\n"
validation.write_text(text, encoding="utf-8")

history = Path("LidarPerf_research_execution_plan.md")
with history.open("a", encoding="utf-8") as handle:
    handle.write(
        """

---

## Step 15 execution record — Docker backend — 16 September 2026

Step 15 implements Phase 15's external-estimator Docker execution backend on branch `step15-docker-backend` / PR #17, based on main `ae69b5cd4b5e9e07991e1ac8f71d2a04cbc73fa0`.

### Implemented semantics

- `DockerBackend` uses the Docker CLI directly and never invokes an estimator command through a host shell.
- `DockerRunSpec` declares image, command, entrypoint, bind mounts, CPU-core allocation, byte-exact memory limit, network mode, GPU access, environment, working directory and timeout.
- requested images are inspected before execution and resolved to an immutable repository digest when available, with the content-addressed image ID retained and used as the fallback immutable identity;
- the measured invocation uses the immutable image reference and `--pull never`, preventing a mutable tag from changing during the run;
- bind mounts require absolute host sources and canonical absolute container targets; duplicate container targets are rejected;
- CPU sets, memory limits, network and GPU access are explicit Docker arguments rather than implicit host state;
- combined stdout/stderr is retained in one process log;
- timeout handling force-removes the named container and records cleanup failure if cleanup itself fails;
- Docker client/server versions and the complete declared execution semantics are available as versioned execution metadata for bundle provenance.

### Measurement/accounting decision

Docker v0.1 intentionally exposes only end-to-end wall time as a measured resource. It advertises `process_cpu_time=false`, `peak_memory=false` and `authoritative_process_accounting=false`.

This is deliberate: the estimator processes belong to the Docker daemon/container runtime and are not descendants of the local `docker` CLI process. Wrapping only the CLI in BenchExec would measure the wrong process tree and create a false impression of authoritative CPU/RAM accounting. Container software reproducibility and trustworthy system-resource accounting are therefore kept as separate concerns. A later controlled-container accounting design must observe the actual container cgroup/workload before LidarPerf may make authoritative Docker CPU/memory claims.

### Real integration evidence

`scripts/run_step15_docker_validation.py` exercises the backend on an ordinary Ubuntu GitHub-hosted runner using `alpine:3.20`:

- image is resolved to immutable registry digest `sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc`;
- Docker client/server version observed: 28.0.4;
- network mode: `none`;
- CPU allocation: one explicit CPU from the runner affinity;
- memory limit: 64 MiB (`67108864` bytes);
- writable bind mount round-trip is verified;
- combined container output contains `docker-backend-ok`;
- return code is zero and the container is cleaned up;
- evidence remains explicitly non-authoritative for performance because the host is ephemeral and Docker v0.1 does not provide authoritative container process CPU/RAM accounting.

Durable evidence: `docs/validation/step15_docker_backend.json`.

### Validation and tests

After closing the memory-limit provenance gap, Ruff passes and the full suite contains **176 passing tests**. Docker-specific tests cover daemon capability semantics, immutable image resolution and image-ID fallback, malformed image provenance, exact command construction, CPU/memory/network/GPU/mount/environment provenance, successful execution/output capture, timeout cleanup and unsafe/ambiguous spec rejection.

### Failures and learnings preserved

1. Early Step 15 CI/formatter iterations (`35141129564`, `35141189675`, `35141256369`, `35141260868`, `35141351687`) failed before the stable backend/test tree was reached; formatter repair run `35141346675` succeeded and the owner-authored head later passed normal CI (`35141482591`). These were development/tooling failures, not successful benchmark evidence.
2. The first real Docker validation run `35141496389` proved the host Docker daemon itself was healthy (`docker version` and image pull succeeded) but the backend capability probe rejected its own version-template output with `docker version did not report both client and server versions`. The probe was corrected to request explicit client/server fields; retry `35141669041` then passed the real Alpine execution and committed the first durable evidence.
3. Post-implementation SPEC audit found a genuine normative omission: SPEC requires Docker/container execution to record the memory limit, but the initial `DockerRunSpec` did not expose one. Step 15 was not merged with that gap. `memory_limit_bytes` was added, validated as positive, mapped to Docker `--memory`, recorded in execution metadata and exercised at 64 MiB by the real validation.
4. The first memory-gap closer `35143313051` was rejected by GitHub before any job due temporary workflow YAML. No product code changed.
5. The repaired closer `35143422365` applied the product patch but failed because Ruff inspected the disposable patch helper itself and reported line-length errors. Permanent files had not been committed.
6. Corrected closure run `35143594101` removed patch scaffolding before lint, passed Ruff, passed all **176 tests**, pulled and executed real Alpine with the 64 MiB memory cap, asserted the durable evidence, committed the permanent fix and self-deleted the temporary workflow/helper.

### Security/provenance note

Container commands and explicitly declared environment values are benchmark semantics and are recorded as provenance. They must not contain credentials or other secrets. Public-bundle sanitization is a separate release-hardening task already required by the specification.

### Next

After final PR-head and post-merge matrices, Step 16 moves to broader real-dataset / estimator validation before the GitHub Action layer, so the Docker abstraction is exercised by a real LO/LIO estimator rather than only the minimal Alpine integration fixture.
"""
    )
