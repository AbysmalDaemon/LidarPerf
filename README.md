# LidarPerf

**Conformance-aware performance regression testing for LiDAR odometry.**

> **Status:** pre-alpha. The benchmark specification is approved; protocol, synthetic-fixture, result-bundle integrity, host-provenance, controlled process-execution, trajectory-evaluation, and first real evalio/KISS-ICP integration layers are implemented.

LidarPerf is being built to answer a stricter question than “which odometry method is fastest?”:

> Were the compared results produced under sufficiently equivalent declared conditions, did both estimators remain valid and accurate, and is the observed performance change defensible rather than an artifact of different inputs, preprocessing, timing boundaries, hardware, or run-to-run noise?

The project focuses on:

- versioned benchmark protocols for LiDAR Odometry (LO) and LiDAR-Inertial Odometry (LIO);
- explicit preprocessing, timing-scope, sensor, tuning, and trajectory semantics;
- provenance-rich, checksummed result bundles;
- correctness and accuracy gates before performance claims;
- repeated-run and repeatability analysis;
- semantic comparability checks;
- controlled baseline/candidate regression testing;
- interoperability with existing tools instead of reimplementing estimator and dataset ecosystems.

## Current state

The normative design is in [`SPEC.md`](SPEC.md). The longer research and execution log is maintained in [`LidarPerf_research_execution_plan.md`](LidarPerf_research_execution_plan.md).

The package currently includes:

- strict protocol validation;
- canonical protocol fingerprints;
- reference LO/LIO protocol documents;
- a deterministic synthetic LiDAR conformance fixture with exact `T_W_B` ground truth;
- optional deterministic point noise and rolling-scan motion distortion;
- bitwise fixture golden tests across the supported Python CI matrix;
- versioned `.lperf` result metadata, immutable bundle writing, SHA-256 payload checksums, and verification;
- read-only host fingerprinting and `lidarperf doctor` benchmark-readiness diagnostics;
- a Linux BenchExec/`runexec` backend for process-tree wall time, CPU time, memory, CPU-core/NUMA constraints, resource-limit termination semantics, and an active controlled-readiness probe;
- canonical trajectory parsing/validation, explicit timestamp association, rigid SE(3) alignment, APE, distance-window relative-pose errors, and coverage accounting;
- a thin evalio execution adapter, validated with real KISS-ICP 1.3.0 on the public Hilti 2022 `basement_2` sequence.

A real estimator/dataset path has now been functionally validated: evalio 0.6.1 → KISS-ICP 1.3.0 → 120 Hilti LiDAR scans → LidarPerf trajectory validation/evaluation. The durable evidence is in `docs/validation/step8_kiss_evalio.json`. GitHub-hosted runner timing from this validation is explicitly non-authoritative; controlled performance claims still require the BenchExec/self-hosted path.

## Planned CLI

The final interface is expected to grow toward:

```bash
lidarperf doctor
lidarperf run ...
lidarperf verify result.lperf
lidarperf compare baseline.lperf candidate.lperf
lidarperf regress baseline.lperf candidate.lperf
```

Available now:

```bash
lidarperf --version
lidarperf doctor
lidarperf doctor --json
lidarperf doctor --data-path /path/to/dataset
lidarperf protocol validate protocols/lo/se3_v1.yaml
lidarperf protocol validate protocols/lio/se3_v1.yaml
lidarperf synthetic generate ./synthetic-fixture --poses 240
lidarperf verify ./result.lperf
```

`doctor` performs a read-only host probe and reports benchmark-relevant operating-system, CPU/topology, affinity, governor, memory/swap, cgroup, storage, NVIDIA/CUDA, system-load, power, and BenchExec capability metadata. It does not silently tune or modify the machine. `--json` emits the complete versioned `lidarperf.doctor.v1` report. Passing `--data-path` also classifies the dataset filesystem and warns about network storage.

The host fingerprint intentionally excludes usernames, hostnames, MAC addresses, serial numbers, GPU UUIDs, and other unnecessary machine identifiers. Dynamic conditions such as current load, swap use, governor, and CPU affinity are recorded in the snapshot but excluded from the stable `host_sha256` identity.

`protocol validate` parses YAML/JSON with the v0.1 Pydantic schema, rejects unknown or contradictory fields, and prints the canonical SHA-256 protocol fingerprint.

`synthetic generate` creates a tiny project-owned LiDAR sequence for conformance and CI testing. The generated fixture contains exact `T_W_B` TUM ground truth, per-scan point files, a timestamped scan index, and an explicit manifest. It is deliberately **not** a real-world ranking dataset.

`verify` validates a `.lperf` directory's versioned metadata, protocol/config provenance links, declared file inventory, trial-count consistency, execution-log layout, and SHA-256 payload checksums. It returns `VALID`, `VALID WITH WARNINGS`, or `INVALID`.

### evalio backend

Install the optional evalio integration with:

```bash
python -m pip install -e '.[evalio]'
```

The adapter delegates dataset loading and estimator execution to evalio while keeping
LidarPerf authoritative for protocol-scoped trajectory validation and metrics. Step 8
validated `hilti_2022/basement_2` with KISS-ICP for a 120-scan prefix. The input interval
starts about 100 ms before Hilti ground truth, so LidarPerf records input support,
reference support, and their evaluable intersection separately rather than silently
penalizing the prefix or inventing unavailable ground truth.

The committed Step 8 evidence is a functional-integration record, not a performance
benchmark or a publication-quality KISS accuracy claim.

### BenchExec backend

Authoritative v0.1 process-level measurement uses BenchExec's `runexec` integration surface instead of a custom process monitor. Install the optional dependency with:

```bash
python -m pip install -e '.[benchmark]'
```

The `benchmark` extra intentionally installs the portable BenchExec Python package only. On cgroups-v2 hosts where BenchExec needs to create its own delegated scope, use the distribution's recommended BenchExec package or install the optional systemd integration with the required `libsystemd` development files available. Running BenchExec inside an already delegated `systemd-run --user --scope ... -p Delegate=yes` scope is another supported host setup.

The backend executes argument vectors directly without a shell and can delegate CPU-time, wall-time, memory, CPU-core, and NUMA-node limits to `runexec`. It normalizes `walltime`, `cputime`, peak memory, child return/signal information, and BenchExec termination reasons into versioned LidarPerf execution records.

`BenchExecBackend.probe_capability()` performs an actual tiny `runexec` execution instead of treating “binary exists” as proof of benchmark readiness. A host is controlled-ready only if process-tree timing and memory accounting succeed. This intentionally rejects ordinary GitHub-hosted runners whose cgroups are not delegated for BenchExec accounting.

BenchExec writes command stdout and stderr into one output file; LidarPerf therefore names this artifact a **combined output log** at the backend layer rather than pretending the streams were measured separately. Result bundles accept either one `process.log` or a genuine `stdout.log` + `stderr.log` pair, never both. The backend disables BenchExec namespace/container mode by default so estimator output paths retain ordinary host filesystem semantics; software containerization remains a separate planned Docker backend.

For example, to exercise point-time semantics and deskew-related tests:

```bash
lidarperf synthetic generate ./distorted-fixture \
  --poses 50 \
  --max-points 256 \
  --noise-std 0.005 \
  --motion-distortion
```

### Built-in protocol identities

The current reference documents resolve to:

```text
lidarperf/lo-se3@1   12d51a84c47c9ff75f0feb828ba24a8210c87ecac8e595d09485dec72719ba41
lidarperf/lio-se3@1  440847ba6e087fe178e5273d2788e6531de679092920f737045462610f6cd735
```

These hashes identify the fully resolved protocol content. A semantic protocol change must produce a different content hash and, once a protocol is released, a new protocol version rather than silently changing the old definition.

## Development

Python 3.11+ is required.

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
```

## Scope

Official v0.1 protocol work is limited to:

- LiDAR-only odometry (LO)
- LiDAR-inertial odometry (LIO)
- CPU-oriented controlled process benchmarking

SLAM loop closure, pairwise registration, authoritative GPU benchmarking, energy benchmarking, camera/radar odometry, and a hosted benchmark service are intentionally deferred.

## License

Apache-2.0. Third-party estimators, datasets, and integrations retain their own licenses.

## AI-assisted development

AI tools are used substantially in implementation, research assistance, documentation, and test generation. Human responsibility, validation, design authority, and disclosure policy are documented in [`AI_USAGE.md`](AI_USAGE.md).
