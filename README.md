# LidarPerf

**Conformance-aware performance regression testing for LiDAR odometry.**

> **Status:** pre-alpha. The benchmark specification has been approved; implementation is beginning.

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

The package currently contains only the repository/package foundation. Benchmark execution is **not implemented yet**.

## Planned CLI

The final interface is expected to grow toward:

```bash
lidarperf doctor
lidarperf run ...
lidarperf verify result.lperf
lidarperf compare baseline.lperf candidate.lperf
lidarperf regress baseline.lperf candidate.lperf
```

For now:

```bash
lidarperf --version
```

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
