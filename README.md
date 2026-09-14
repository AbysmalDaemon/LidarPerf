# LidarPerf

**Conformance-aware performance regression testing for LiDAR odometry.**

> **Status:** pre-alpha. The benchmark specification is approved; protocol, synthetic-fixture, result-bundle integrity, and host-provenance layers are implemented.

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
- read-only host fingerprinting and `lidarperf doctor` benchmark-readiness diagnostics.

Estimator execution and real trajectory metrics are **not implemented yet**.

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

`verify` validates a `.lperf` directory's versioned metadata, protocol/config provenance links, declared file inventory, trial-count consistency, and SHA-256 payload checksums. It returns `VALID`, `VALID WITH WARNINGS`, or `INVALID`.

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
lidarperf/lo-se3@1   d3f93d00b1958433d0f9b7093810d840a8cd41cd323e27957563531f29da8703
lidarperf/lio-se3@1  b4bcef011bb82e9368edebfba8263b0cc41c6e5de91add0b7db1d847a6c40c41
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
