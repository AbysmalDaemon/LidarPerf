# LidarPerf

**Conformance-aware performance regression testing for LiDAR odometry.**

> **Status:** pre-alpha. The benchmark specification is approved and the first protocol and synthetic-fixture layers are implemented.

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
- bitwise fixture golden tests across the supported Python CI matrix.

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
lidarperf protocol validate protocols/lo/se3_v1.yaml
lidarperf protocol validate protocols/lio/se3_v1.yaml
lidarperf synthetic generate ./synthetic-fixture --poses 240
```

`protocol validate` parses YAML/JSON with the v0.1 Pydantic schema, rejects unknown or contradictory fields, and prints the canonical SHA-256 protocol fingerprint.

`synthetic generate` creates a tiny project-owned LiDAR sequence for conformance and CI testing. The generated fixture contains an exact TUM ground-truth trajectory, per-scan point files, a timestamped scan index, and an explicit manifest. It is deliberately **not** a real-world ranking dataset.

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
