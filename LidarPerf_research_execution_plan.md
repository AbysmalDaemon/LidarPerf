# LidarPerf — Research, Scope, and Execution Plan

**Research snapshot:** 14 September 2026  
**Project status:** Proposed / pre-implementation  
**Working project name:** `LidarPerf`  
**Primary goal:** Build a serious open-source benchmarking and regression-testing framework for LiDAR odometry software, while keeping owner involvement deliberately minimal.

---

## 1. Executive decision

### GO — but only with a narrow definition

A generic “LiDAR odometry benchmark suite” is **not sufficiently differentiated in 2026**.

Existing projects already cover large parts of that space:

- **evalio** — datasets, LiDAR/LIO pipelines, normalized execution, trajectory evaluation
- **MapsHD** — Dockerized LO/LIO integrations, ROS1/ROS2 support, benchmark adapters
- **SLAM-Hive** — repeatable Docker-based SLAM benchmarking, experiment management, CPU/RAM analysis
- **SLAMFuse** — containerized SLAM evaluation, frame-level diagnostics, fuzzing
- **LIO-Benchmark** — research focused on reproducibility / nondeterminism in LIO
- **SLAMBench** — accuracy, execution time, memory, and energy benchmarking
- **RobotPerf** — reproducible robotics-computing benchmarking
- **BenchExec** — robust process-level execution accounting
- **Bencher** — continuous benchmark histories and regression thresholds
- **ros2_tracing** — low-overhead ROS 2 execution tracing

Therefore, **LidarPerf should not try to replace these projects**.

### The defensible niche

> **LidarPerf: conformance-aware, provenance-rich, accuracy-gated performance regression testing for LiDAR odometry and LiDAR-inertial odometry software.**

The core problem it should solve is:

> Given a baseline build and a candidate build, were they run under equivalent declared conditions, are the outputs valid, are the results comparable, did the candidate preserve estimation quality, and did its computational performance improve or regress?

That is substantially more specific than “run several SLAM methods and print ATE”.

---

# 2. What LidarPerf must *not* become

The following directions are rejected because they are either already well served or would produce a bloated, derivative project:

- another generic dataset loader
- another ROS bag abstraction layer
- another algorithm zoo
- another KISS-ICP / FAST-LIO / LIO-SAM wrapper collection
- another generic ATE/RPE package
- another Docker farm whose main selling point is “reproducibility”
- another web benchmark dashboard
- another SLAM implementation
- another ICP implementation
- another ROS tracing system
- another Linux process-accounting implementation
- another benchmark-history SaaS

Where possible, LidarPerf should **depend on existing, tested infrastructure** rather than reimplement it.

---

# 3. Existing projects and what we reuse

## 3.1 evalio

Closest existing project to the original “PointCloudBench” concept.

Useful capabilities include:

- multiple LiDAR/LIO pipelines
- multiple configured datasets
- normalized sensor input
- dataset downloading
- CLI/YAML experiment execution
- trajectory evaluation
- no ROS requirement for the core workflow

### LidarPerf strategy

Use `evalio` as an **execution backend**.

LidarPerf should not rebuild:

- dataset loaders
- common estimator wrappers
- normalization layers
- experiment orchestration already handled cleanly by evalio

Conceptual division:

**evalio:**  
> Run these LO/LIO methods on these datasets.

**LidarPerf:**  
> Prove exactly what benchmark was performed, validate comparability, capture full execution provenance, quantify repeatability, and detect correctness/performance regressions.

Reference: <https://github.com/contagon/evalio>

---

## 3.2 MapsHD

MapsHD is a recent benchmark suite for LiDAR odometry frameworks with:

- many LO/LIO adapters
- Dockerized algorithm environments
- ROS1/ROS2 integration
- trajectory evaluation
- large integration coverage

### LidarPerf strategy

Do **not** compete on the number of supported algorithms.

Where useful, consume or interoperate with compatible external execution environments.

Reference: <https://www.sciencedirect.com/science/article/pii/S2352711026003146>

---

## 3.3 SLAM-Hive

Provides:

- reproducible containerized SLAM execution
- experiment configuration
- database-backed results
- CPU and memory analysis
- large-scale evaluation infrastructure

### LidarPerf implication

We cannot claim that containerized reproducible SLAM benchmarking is new.

The differentiator must instead be:

- protocol conformance
- exact experiment provenance
- semantic comparability
- regression testing
- accuracy-gated performance conclusions

Reference: <https://github.com/SLAM-Hive>

---

## 3.4 SLAMFuse

Relevant capabilities:

- Dockerized multimodal SLAM evaluation
- LiDAR support
- diagnostics
- execution-time failure conditions
- frame-level analysis
- fuzzing / stress testing

### LidarPerf implication

“Trajectory accuracy + execution diagnostics” is not novel by itself.

Reference: <https://arxiv.org/html/2410.04242v1>

---

## 3.5 LIO-Benchmark and nondeterminism research

Recent work explicitly studies non-reproducibility in LiDAR-inertial odometry and identifies implementation patterns that can produce differing outputs under nominally identical conditions.

### LidarPerf implication

We should **not** claim to discover LIO nondeterminism.

Instead, repeated-run analysis should become a **first-class benchmark output**.

For example:

- trajectory variation across repeated runs
- performance variation across repeated runs
- completion-rate variation
- deterministic vs native execution metadata

Reference: <https://github.com/LIO-Benchmark/LIO-Benchmark>

---

## 3.6 BenchExec

BenchExec already handles difficult Linux benchmarking details such as:

- subprocess trees
- cgroups
- CPU time
- wall time
- memory
- core limits
- NUMA restrictions
- isolation / namespaces

### LidarPerf strategy

Use BenchExec (or `runexec`) for authoritative Linux process-level measurements rather than writing our own low-level monitor.

Reference: <https://github.com/sosy-lab/benchexec>

---

## 3.7 Bencher

Bencher already provides:

- benchmark histories
- regression thresholds
- statistical comparisons
- CI-oriented performance tracking

### LidarPerf strategy

Export LidarPerf results to Bencher-compatible JSON rather than building our own benchmark-history web service.

Reference: <https://bencher.dev/>

---

## 3.8 ros2_tracing

Useful for instrumented ROS 2 runs where true message-level or frame-level latency matters.

### LidarPerf strategy

Use it later for:

- input-to-output latency
- output frequency
- jitter
- missed deadlines
- message timing
- blocking / execution gaps

This belongs in a later milestone, not the first public release.

Reference: <https://github.com/ros2/ros2_tracing>

---

# 4. The actual LidarPerf product

## 4.1 Primary abstraction

The central object is **not the algorithm** and not the dataset.

It is a **benchmark run with enough information to prove what that run means**.

Example:

```bash
lidarperf run \
  --backend evalio \
  --method kiss \
  --dataset boreas/glen \
  --protocol lo-v1 \
  --repeat 10
```

The output should include:

- protocol ID/version
- dataset fingerprint
- software version + git commit
- clean/dirty tree state
- estimator configuration hash
- preprocessing declaration
- sensor declaration
- execution environment
- host hardware
- CPU/thread settings
- timing scope
- completion validity
- trajectory validity
- accuracy metrics
- system-performance metrics
- repeated-run statistics
- checksums
- provenance

---

# 5. Benchmark tracks

These must be structurally separated.

## 5.1 LO

**LiDAR-only odometry**

Permitted sensors:

- LiDAR

Disallowed by default:

- IMU
- loop closure
- global corrections

## 5.2 LIO

**LiDAR-inertial odometry**

Permitted sensors:

- LiDAR
- IMU

No hidden use of other sensors.

## 5.3 SLAM

Allows:

- loop closure
- global optimization
- backend corrections

SLAM should not be directly ranked against pure odometry without an explicit protocol that permits it.

## 5.4 Registration

Pairwise or local point-cloud registration is a different problem and should be a separate benchmark family if added later.

Not part of v0.1.

---

# 6. Protocol conformance

The strongest differentiator should be a **versioned protocol specification**.

Example:

```yaml
protocol:
  id: lidarperf/lo-standard
  version: 1

sensors:
  lidar: true
  imu: false

trajectory:
  alignment: se3
  scale_correction: false

timing:
  scope: compute

tuning:
  class: frozen
```

A run that violates the protocol should not silently proceed as if it were comparable.

Example:

```text
CONFORMANCE ERROR

Protocol lo-v1 permits LiDAR input only.
IMU input was declared.
```

---

# 7. Preprocessing must be explicit

Benchmark numbers can become meaningless if one method receives already processed data while another performs the work internally.

LidarPerf should declare:

```yaml
input:
  timestamps:
    available: true
    type: relative_per_point
    reference: scan_start

  motion_compensation:
    input_already_deskewed: false

preprocessing:
  crop: null
  voxel_downsample: null
  deskew:
    owner: algorithm
```

Relevant preprocessing fields should include, where applicable:

- deskewing
- voxelization
- cropping
- filtering
- ground removal
- outlier removal
- intensity filtering
- range clipping
- timestamp reconstruction
- coordinate transforms

---

# 8. Timing scopes

“Runtime” is not one thing.

LidarPerf should distinguish at least:

| Scope | Meaning |
|---|---|
| `compute` | estimator/algorithm processing only |
| `pipeline` | preprocessing + estimator |
| `end_to_end` | input decoding/I/O + preprocessing + estimator + output |

Results with different timing scopes should not be directly ranked without a warning.

---

# 9. Accuracy must gate performance

A benchmark must never reward a broken estimator for being faster.

Correct evaluation order:

```text
execution succeeded?
        ↓
result structurally valid?
        ↓
trajectory coverage sufficient?
        ↓
accuracy within validity limits?
        ↓
only then evaluate performance
```

Example:

```text
before:
ATE = 0.42 m
latency = 37 ms

after:
ATE = 87.3 m
latency = 15 ms
```

This is **not** a performance improvement.

It is a failed candidate.

---

# 10. Failure is itself a metric

Every run should track:

- expected frames
- consumed frames
- produced poses
- trajectory coverage
- invalid / NaN / Inf poses
- timestamp gaps
- process exit code
- timeouts
- tracking-loss events
- successful distance
- total distance
- completion ratio

A method that only succeeds on easy portions must not receive an artificially good score.

---

# 11. Repeated runs

Repeated execution should be required for authoritative performance measurements.

Example:

```bash
lidarperf run ... --repeat 10 --warmup 2
```

Two forms of variability should be reported separately:

1. **estimator/output variability**
2. **system/runtime variability**

Potential summary fields:

- median
- mean
- standard deviation
- p50
- p90
- p95
- p99
- confidence interval
- minimum
- maximum

---

# 12. Process-level vs per-frame metrics

## 12.1 Black-box / command backend

Can reliably report:

- total wall time
- CPU time
- peak RSS
- process success/failure
- total throughput
- total sequence completion

Cannot magically know internal frame latency.

## 12.2 Instrumented backend

Can potentially report:

- per-frame processing time
- input-to-output latency
- p95/p99 latency
- output frequency
- jitter
- missed deadlines
- queueing delays
- dropped messages

Instrumented ROS 2 support should use existing tracing infrastructure rather than a custom tracer.

---

# 13. Host provenance

Performance numbers require machine metadata.

At minimum:

```json
{
  "cpu": {
    "model": "...",
    "physical_cores": 16,
    "logical_cores": 32,
    "affinity": [4, 5, 6, 7],
    "governor": "performance"
  },
  "memory": {
    "total_bytes": 68719476736
  },
  "os": {
    "distribution": "Ubuntu",
    "version": "24.04",
    "kernel": "..."
  },
  "gpu": {
    "model": "...",
    "driver": "...",
    "cuda": "..."
  }
}
```

---

# 14. `lidarperf doctor`

A first-class command should inspect benchmark quality:

```text
$ lidarperf doctor

Benchmark host
────────────────────────────────────
Linux                  ✓
cgroups v2             ✓
BenchExec setup        ✓

CPU governor           ⚠ powersave
CPU affinity           ⚠ unrestricted
background load        ⚠ elevated
NUMA                   ✓
swap activity          ✓ none

GPU
NVIDIA RTX ...         ✓

Benchmark grade: C

2 conditions may make performance comparisons noisy.
```

Initial versions should **warn and record**, not aggressively modify the machine.

---

# 15. Result bundle

A versioned result bundle should be the core artifact.

Proposed format:

```text
kiss-boreas-20260913.lperf/
│
├── manifest.json
├── protocol.yaml
├── metrics.json
├── environment.json
├── trajectory.tum
├── config/
│   └── algorithm.yaml
├── telemetry.parquet
├── stdout.log
├── stderr.log
└── checksums.json
```

Design goal:

> A result should still be understandable and verifiable months later even if the original machine is gone.

---

# 16. `lidarperf verify`

Example:

```bash
lidarperf verify result.lperf
```

Expected checks:

```text
✓ schema valid
✓ protocol exists
✓ checksums valid
✓ benchmark version recorded
✓ estimator version recorded
✓ git commit recorded
✓ configuration fingerprint recorded
✓ dataset fingerprint recorded
✓ environment information present
✓ trajectory timestamps valid
✓ trajectory coverage valid
✓ required conformance metadata present

VERIFIED
```

---

# 17. Semantic comparability

LidarPerf should refuse meaningless comparisons.

Example:

```text
Result A
  lo-v1
  8 threads
  compute scope
  dataset fingerprint ABC

Result B
  lio-v1
  16 threads
  end_to_end scope
  dataset fingerprint XYZ
```

Then:

```bash
lidarperf compare A B
```

should produce:

```text
NOT COMPARABLE

✗ benchmark tracks differ
✗ dataset fingerprints differ
✗ timing scopes differ
✗ thread limits differ
```

Exploratory override may exist, but results must be visibly marked as incomparable.

---

# 18. Tuning classification

Recommended categories:

| Class | Meaning |
|---|---|
| `frozen` | one configuration across the whole suite |
| `dataset` | one configuration per dataset |
| `sequence` | one configuration per individual sequence |

`frozen` results should receive the strongest comparability status.

Sequence-specific tuning is not forbidden, but it must be explicitly declared.

---

# 19. Synthetic CI fixture

A small deterministic synthetic dataset should be created by us.

Purpose:

- unit testing
- CI
- SE(3) convention testing
- timestamp handling
- protocol validation
- trajectory association
- bundle testing
- regression logic

It should **not** be advertised as a meaningful real-world ranking dataset.

Possible fixture:

- 200–500 poses
- simple planes / poles / walls
- deterministic noise
- known exact SE(3) trajectory
- configurable motion distortion
- configurable scan timing

---

# 20. Proposed architecture

```text
lidarperf/
│
├── src/lidarperf/
│   ├── cli/
│   ├── spec/
│   │   ├── protocol.py
│   │   ├── manifest.py
│   │   ├── result.py
│   │   └── schemas/
│   ├── backends/
│   │   ├── command.py
│   │   ├── benchexec.py
│   │   ├── evalio.py
│   │   └── docker.py
│   ├── protocols/
│   │   ├── lo.py
│   │   ├── lio.py
│   │   └── slam.py
│   ├── metrics/
│   │   ├── trajectory.py
│   │   ├── execution.py
│   │   ├── validity.py
│   │   └── reproducibility.py
│   ├── telemetry/
│   │   ├── host.py
│   │   ├── cpu.py
│   │   └── gpu.py
│   ├── bundle/
│   ├── conformance/
│   ├── compare/
│   ├── regress/
│   ├── report/
│   ├── export/
│   │   └── bencher.py
│   └── synthetic/
│
├── protocols/
├── examples/
├── tests/
├── docs/
├── .github/
├── pyproject.toml
└── LICENSE
```

---

# 21. Proposed technology stack

| Area | Proposed choice |
|---|---|
| Language | Python 3.11+ |
| CLI | Typer |
| Validation | Pydantic v2 |
| Interchange schemas | JSON Schema |
| Config | YAML / JSON |
| Numeric work | NumPy |
| Statistics | SciPy |
| Telemetry tables | PyArrow / Parquet |
| Reporting | Jinja2 + Plotly/Matplotlib |
| Process benchmarking | BenchExec |
| LO/LIO execution | evalio backend |
| ROS 2 tracing | ros2_tracing, later |
| CI benchmark history | Bencher export |
| Tests | pytest |
| Linting | Ruff |
| Static typing | Pyright or mypy |
| Package metadata | `pyproject.toml` |
| Project license | Apache-2.0 |

The critical architectural rule is to keep the **benchmark specification independent of execution backends**.

---

# 22. Reuse vs original work

Estimated reuse:

| Area | Existing work usable | LidarPerf work |
|---|---:|---:|
| LO algorithms | 95–100% | metadata / integration |
| LIO algorithms | 95–100% | metadata / integration |
| dataset ingestion | 90–95% | fingerprints / conformance |
| normalized sensor input | 90%+ | protocol checks |
| trajectory basics | 70–90% | protocol semantics / tests |
| process CPU/wall/RAM | 70–85% | orchestration / normalization |
| ROS tracing infrastructure | ~100% | interpretation / adapter |
| benchmark history | 90–100% | export layer |
| Docker estimator environments | 80–100% | execution contract |
| protocol specification | <20% | mostly ours |
| LiDAR conformance engine | <10% | ours |
| provenance model | ~20% | mostly ours |
| result bundle | ~10% | ours |
| semantic comparability | ~10% | ours |
| correctness-gated regression | ~10% | ours |
| repeated-run orchestration | 30–50% primitives | ours |
| synthetic CI dataset | 0% | ours |
| reports | ~30% libraries | mostly ours |

### Important implementation policy

Prefer:

```python
import existing_project
```

over copying its source into LidarPerf.

This keeps authorship boundaries clean and lets upstream projects continue to evolve.

---

# 23. Licensing policy

Proposed LidarPerf license:

> **Apache-2.0**

Reasons:

- permissive
- explicit patent grant
- suitable for infrastructure software
- friendly to research and industry users

Third-party estimators keep their own licenses.

LidarPerf must not imply that its own license relicenses dependencies.

An eventual result manifest should contain component licenses and versions.

---

# 24. Dataset policy

Do not redistribute large third-party datasets in the repository.

Use:

- official dataset downloads
- external dataset managers
- evalio where appropriate
- checksums / fingerprints
- our own tiny synthetic CI data

This avoids licensing and repository-size problems.

---

# 25. GitHub / CI philosophy

Ordinary GitHub-hosted runners are fine for:

- unit tests
- schema validation
- package tests
- synthetic benchmark smoke tests
- CLI tests
- bundle verification
- regression-logic tests

They should **not** be treated as authoritative performance machines.

Serious performance regression testing should use:

- a stable self-hosted Linux runner
- fixed hardware
- repeated baseline/candidate execution
- fixed protocol
- same benchmark session where possible

---

# 26. Key developer experience

The project should eventually support a workflow like:

```bash
pip install lidarperf
```

```bash
lidarperf doctor
```

```bash
lidarperf run \
  --backend evalio \
  --method kiss \
  --dataset boreas/glen \
  --protocol lo-v1 \
  --repeat 5
```

```bash
lidarperf verify result.lperf
```

```bash
lidarperf compare baseline.lperf candidate.lperf
```

```bash
lidarperf regress baseline.lperf candidate.lperf
```

```bash
lidarperf report result.lperf --html report.html
```

```bash
lidarperf export bencher result.lperf > bencher.json
```

---

# 27. The feature most likely to earn GitHub stars

The strongest user-facing feature is **PR-level regression reporting**.

Concept:

```text
PR #184

Accuracy
✓ no regression

Correctness
✓ 100% trajectory coverage
✓ no invalid poses

Performance
median       33.8 → 29.1 ms    -13.9%
p95          46.4 → 39.7 ms    -14.4%
peak RSS      1.2 → 1.1 GB      -8.3%

Repeatability
trajectory variation unchanged

✓ PASS
```

Potential CI usage:

```yaml
- uses: lidarperf/action@v1
```

This is more compelling than merely supporting many algorithms.

---

# 28. Estimated build effort

## Launch-worthy version

Planning estimate:

> **~210 active engineering hours**

Realistic uncertainty band:

> **~190–240 hours**

This estimate already assumes:

- implementation mistakes
- debugging
- retries
- integration failures
- incorrect assumptions
- external dependency mismatches
- Docker problems
- cgroup issues
- dataset problems
- coordinate-frame bugs
- trajectory-convention bugs
- CI failures

This is **engineering workload**, not required owner involvement.

---

# 29. Workstream estimate

| Workstream | Estimated effort |
|---|---:|
| benchmark specification + protocol design | 9–14 h |
| repository/package/CI foundation | 5–8 h |
| schema + manifest system | 8–13 h |
| BenchExec + command backend | 11–18 h |
| `doctor` + host fingerprinting | 8–12 h |
| trajectory/validity/conformance layer | 13–22 h |
| evalio integration | 13–22 h |
| repeatability/nondeterminism analysis | 6–10 h |
| bundles/checksums/verification | 9–14 h |
| compare/regression engine | 8–12 h |
| synthetic fixture + golden tests | 11–18 h |
| report generation | 8–13 h |
| Bencher export | 4–7 h |
| Docker execution backend | 14–24 h |
| GitHub Action integration | 8–14 h |
| real LO/LIO/dataset integration tests | 20–36 h |
| documentation/examples/release work | 13–20 h |
| license/security/refactor/hardening | 8–12 h |
| optional first NVIDIA/NVML support | 8–14 h |

The ranges do not simply sum at their upper bounds because some waiting, builds, and validation can overlap with other work.

---

# 30. Milestones

| Milestone | Definition | Cumulative active work |
|---|---|---:|
| Alpha | spec, schemas, synthetic fixture, BenchExec, bundles, verify | 55–80 h |
| Public v0.1 | real evalio/KISS integration, metrics, repeats, reports, Bencher | 145–190 h |
| Launch-worthy v0.2 | Docker, GitHub Action, validation, polished docs | 190–240 h |
| Stable v1.0 | ROS2 tracing, schema stability, extra adapters, hardening | 285–360 h |

---

# 31. Owner involvement target

The owner should not need to spend 210 hours supervising this project.

Target owner involvement for the software build:

> **~5–10 hours total through v0.2**

The execution model should use **decision gates**, not constant micro-approval.

---

# 32. Five owner decision gates

## Gate 1 — Specification approval

I will deliver:

- full benchmark specification
- tracks
- timing scopes
- conformance rules
- tuning policy
- validity policy
- result schema
- provenance requirements

Owner task:

- read
- challenge any domain assumptions
- approve or request changes

## Gate 2 — Alpha approval

I will deliver a complete synthetic path:

```text
synthetic data
→ estimator execution
→ result bundle
→ verification
→ comparison
```

Owner task:

- inspect behavior
- approve project direction

## Gate 3 — v0.1 approval

I will deliver:

- real KISS/evalio integration
- real dataset output
- package
- docs
- tests
- reports

Owner task:

- review representative outputs
- approve public technical-preview release

## Gate 4 — Research experiment approval

I will deliver:

- research questions
- hypotheses
- experiment matrix
- datasets
- methods
- hardware plan
- statistical methodology
- expected compute/runtime cost

Owner task:

- review scientific design
- approve before expensive benchmark execution

## Gate 5 — Publication approval

I will deliver:

- raw findings
- statistical analysis
- plots
- limitations
- paper draft
- response-to-reviewer drafts where needed

Owner task:

- seriously inspect claims and evidence
- make/approve final scientific conclusions
- submit as author

---

# 33. Expected PR structure

Estimated:

> **~18–25 PRs to v0.2**

Likely order:

```text
PR 01  benchmark specification
PR 02  repository foundation
PR 03  schema models
PR 04  synthetic fixture
PR 05  bundle format
PR 06  verifier
PR 07  host doctor
PR 08  BenchExec backend
PR 09  trajectory validation + metrics
PR 10  protocol conformance
PR 11  evalio backend
PR 12  first KISS end-to-end run
PR 13  repeated-run analysis
PR 14  comparator
PR 15  regression engine
PR 16  reports
PR 17  Bencher export
PR 18  Docker backend
PR 19  real-dataset validation
PR 20  GitHub Action
PR 21  docs/demo
PR 22+ fixes, hardening, release
```

PRs should remain small enough to audit but large enough that the owner is not constantly interrupted.

---

# 34. Likely failure points

| Failure mode | Probability | Cost |
|---|---:|---:|
| SE(3)/frame convention error | high | medium |
| timestamp-association edge case | high | medium |
| evalio API mismatch | medium-high | medium |
| cgroup / BenchExec setup issue | medium | medium |
| Docker + accounting mismatch | medium-high | high |
| hidden dataset preprocessing assumption | high | high |
| estimator behaves differently from docs | high | high |
| cloud CI too noisy for perf claims | near-certain | low / known |
| GPU telemetry inconsistency | medium-high | medium |
| ROS2 tracing interpretation difficulty | high | high |
| package/license issue | low-medium | medium |
| schema too rigid | medium | high if late |

This is why the benchmark specification must be frozen early.

---

# 35. Hardware requirements

Core development can use:

- synthetic fixtures
- ordinary CI
- public OSS
- existing datasets / evalio

For credible published system-performance results, eventually use a stable Linux machine.

Preferred:

```text
Ubuntu 24.04
bare metal
known CPU
sufficient SSD
self-hosted GitHub runner
```

GPU support should be delayed until it materially improves the research.

Initial project should be **CPU-first**.

---

# 36. Research publication opportunities

The project may plausibly support **two genuinely different publications**.

Not two rewrites of the same contribution.

## 36.1 Software publication

### Proposed paper

> **LidarPerf: Conformance-Aware Performance Regression Testing for LiDAR Odometry**

### Preferred venue

**Journal of Open Source Software (JOSS)**

Why:

- peer-reviewed research-software venue
- appropriate for substantial open-source infrastructure
- DOI
- no publication fee
- strong fit if the repository has documentation, tests, releases, and users

Important planning constraint:

JOSS expects meaningful public development history, so the repository should become public early rather than being developed privately for many months.

Reference: <https://joss.theoj.org/about>

Alternative:

**SoftwareX**

Reference: <https://www.sciencedirect.com/journal/softwarex>

---

## 36.2 Research paper

The research paper should not merely describe the software.

It should use LidarPerf to answer a real scientific question.

### Strong candidate topic

> **Benchmarking the Benchmark: Reproducibility and Protocol Sensitivity in Modern LiDAR Odometry**

Possible questions:

- Do algorithm rankings remain stable across hardware?
- How much runtime variance comes from hardware vs estimator nondeterminism?
- Are “real-time” conclusions stable across timing scopes?
- How sensitive are rankings to preprocessing inclusion/exclusion?
- How often do speed optimizations degrade localization quality?
- Do mean and p95/p99 latency lead to different conclusions?
- How different are LO and LIO repeatability characteristics?
- How much does containerization affect ranking?
- How much can formal conformance rules reduce invalid comparisons?
- How much do thread count, CPU affinity, and host state affect conclusions?

---

# 37. Possible research venues

## IROS

Good robotics venue if the contribution includes:

- rigorous benchmarking methodology
- a meaningful experimental campaign
- strong empirical findings

Target only if the work contains real scientific results, not merely a tool release.

## IEEE Robotics and Automation Letters (RA-L)

Potentially a strong fit for:

- concise methodology
- rigorous empirical results
- robotics relevance
- systems-performance analysis

Rolling submission makes it useful if conference deadlines do not align.

Reference: <https://www.ieee-ras.org/publications/ra-l/ra-l-information-for-authors/>

## ACM SIGMETRICS / POMACS

A more ambitious systems/performance venue.

Potential fit if the research contribution broadens beyond “robotics benchmark tooling” into serious performance-measurement methodology.

Possible framing:

> **How Reproducible Are Robotics Performance Claims? A Systems Study of LiDAR Odometry**

This is a stretch target and should only be pursued if the results are strong enough.

Reference: <https://www.sigmetrics.org/>

---

# 38. Recommended publication strategy

Do not plan three papers from day one.

Best strategy:

### Paper 1 — research contribution

Focus:

> What did we discover about LiDAR odometry benchmarking, reproducibility, timing boundaries, hardware dependence, and regression behavior?

Target:

- IROS
- RA-L
- possibly SIGMETRICS/POMACS if the systems contribution becomes broader

### Paper 2 — software contribution

Focus:

> What reusable open-source software makes these experiments reproducible and auditable?

Target:

- JOSS
- or SoftwareX

These are distinct enough to avoid obvious salami slicing if written carefully.

---

# 39. Sole-student authorship and AI-assisted development

A sole student can be the sole human author **if that is factually correct**.

No professor should be added merely for status.

However:

- anyone who makes a substantial scientific contribution should receive appropriate authorship
- AI-assisted coding / analysis / manuscript drafting must follow venue disclosure policies
- the human author remains responsible for every scientific claim

Therefore, from day one maintain:

```text
AI_USAGE.md
```

It should document:

- what AI assisted with
- what was independently validated
- what scientific decisions were made by the human author
- how experimental outputs were verified
- what checks were performed before publication

The human author must genuinely inspect and approve:

- benchmark specification
- experimental design
- representative outputs
- scientific claims
- manuscript
- responses to reviewers

Minimal involvement is compatible with the engineering workflow.

Zero intellectual ownership is not compatible with honest sole authorship.

---

# 40. Target owner workload for publications

### Software engineering

Target:

> **~5–10 hours total through v0.2**

### Sole-authored research publication

Likely additional involvement:

> **~15–30 hours spread over the research and submission process**

Mostly:

- research-design review
- methodology approval
- evidence review
- paper reading/editing
- reviewer responses

Not programming.

---

# 41. Execution plan

The following is the proposed execution sequence.

## Phase 0 — Repository and research setup

### Deliverables

- create GitHub repository
- choose final package/repo name
- Apache-2.0 license
- `README.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `AI_USAGE.md`
- citation metadata
- issue / PR templates
- branch protection
- CI skeleton

### Goal

Create an immediately public, professionally structured OSS project.

---

## Phase 1 — Freeze `SPEC.md`

This is the highest-risk design phase.

### Define

- LO / LIO / SLAM tracks
- timing scopes
- preprocessing semantics
- sensor declarations
- tuning classes
- trajectory validity
- completion criteria
- accuracy gates
- repeated-run rules
- host metadata
- provenance fields
- comparability rules
- result bundle format
- protocol versioning

### Exit condition

Owner approves the specification.

No large implementation begins before this.

---

## Phase 2 — Core schemas and protocol engine

Build:

- Pydantic models
- JSON Schemas
- versioned protocols
- manifest model
- validation errors
- conformance engine
- schema tests

### Exit condition

Invalid benchmark definitions fail deterministically and clearly.

---

## Phase 3 — Synthetic conformance fixture

Build:

- deterministic scene generator
- exact known trajectory
- deterministic point clouds
- optional noise
- optional timing distortion

Use it to test:

- coordinate conventions
- timestamps
- trajectory comparison
- protocol validation
- result serialization

---

## Phase 4 — Result bundle

Implement:

- manifest
- metrics
- config capture
- logs
- trajectory
- environment info
- telemetry
- checksums

Add:

```bash
lidarperf verify
```

---

## Phase 5 — Host fingerprinting and doctor

Implement:

```bash
lidarperf doctor
```

Capture:

- CPU model
- core count
- affinity
- governor
- memory
- OS
- kernel
- cgroups
- NUMA
- GPU metadata if available
- obvious benchmark-noise warnings

---

## Phase 6 — BenchExec backend

Integrate BenchExec for process-level execution.

Support:

- command execution
- wall time
- CPU time
- peak RSS
- exit status
- timeout
- process-tree accounting

---

## Phase 7 — Trajectory validity and metrics

Implement / validate:

- trajectory loading
- timestamp association
- coverage
- invalid pose detection
- alignment semantics
- ATE-style metrics where protocol permits
- relative error
- KITTI-style protocol where appropriate

Golden-test against known references.

---

## Phase 8 — evalio backend

Integrate evalio.

First target:

- KISS-ICP
- one real dataset

Then add additional pipelines only when they help validate the abstraction.

---

## Phase 9 — First real end-to-end run

Complete:

```text
real dataset
→ evalio
→ estimator
→ BenchExec
→ trajectory
→ validity
→ accuracy
→ performance
→ result bundle
→ verification
```

This is the first major proof that LidarPerf is real.

---

## Phase 10 — Repeated-run analysis

Implement:

- repeat scheduling
- warmups
- run distributions
- trajectory repeatability
- runtime repeatability
- summary statistics

---

## Phase 11 — Comparator

Implement:

```bash
lidarperf compare A.lperf B.lperf
```

Check:

- protocol
- sensors
- timing scope
- dataset fingerprint
- thread limits
- tuning
- software/environment differences

Refuse invalid comparisons by default.

---

## Phase 12 — Regression engine

Implement:

```bash
lidarperf regress baseline.lperf candidate.lperf
```

Order:

1. execution validity
2. structural validity
3. trajectory coverage
4. accuracy gate
5. performance comparison

---

## Phase 13 — Reports

Produce:

- terminal summary
- JSON
- CSV where useful
- HTML report
- plots

Focus on:

- accuracy
- latency / throughput
- resource usage
- repeatability
- validity
- comparability

---

## Phase 14 — Bencher export

Implement:

```bash
lidarperf export bencher result.lperf
```

Avoid building our own historical benchmark service.

---

## Phase 15 — Docker backend

Support external estimator execution where direct Python integration is unsuitable.

Capture:

- image digest
- host metadata
- container metadata
- execution scope
- estimator provenance

---

## Phase 16 — GitHub Action

Build CI interface.

Target experience:

```yaml
- uses: lidarperf/action@v1
```

Generate:

- correctness summary
- accuracy status
- performance change
- repeatability change
- pass/fail status

Authoritative performance should require a stable/self-hosted runner.

---

## Phase 17 — Public v0.1 / v0.2 releases

### v0.1

Technical preview:

- working package
- evalio integration
- result bundles
- repeated runs
- metrics
- reports
- verification

### v0.2

Launch-worthy:

- Docker backend
- GitHub Action
- polished docs
- real-world validation
- stable self-hosted benchmark recipe
- clean public demo

---

## Phase 18 — Research campaign design

Before running a large benchmark matrix, freeze:

- research questions
- hypotheses
- methods
- datasets
- hardware
- number of repeats
- timing scopes
- statistical tests
- exclusions
- failure policy
- preprocessing policy
- tuning policy

Owner approval required here.

---

## Phase 19 — Research campaign execution

Potential experiment dimensions:

- several LO/LIO systems
- multiple datasets
- multiple sequences
- repeated runs
- different CPU/thread settings
- different timing scopes
- native vs Docker
- controlled preprocessing variations
- potentially multiple hardware systems

Capture all outputs as versioned result bundles.

---

## Phase 20 — Research analysis

Generate:

- raw result tables
- confidence intervals
- ranking stability
- latency distributions
- completion statistics
- nondeterminism analysis
- protocol-sensitivity analysis
- resource trade-offs
- limitations

All claims must trace back to auditable result bundles.

---

## Phase 21 — Research manuscript

Draft:

- abstract
- introduction
- related work
- methodology
- benchmark specification
- experiments
- results
- discussion
- limitations
- reproducibility statement
- AI-use disclosure

Potential venues:

- IROS
- RA-L
- possibly SIGMETRICS/POMACS

---

## Phase 22 — JOSS / software paper

Once the project has enough public development history:

- archive a stable release
- create DOI
- verify documentation
- verify installation instructions
- ensure tests are complete
- ensure contributor/research-use documentation
- prepare software paper

Target:

- JOSS

---

# 42. Definition of “done”

The project is not complete merely because the package installs.

A launch-worthy LidarPerf must demonstrate:

- clear benchmark protocols
- protocol conformance
- full provenance
- valid process-level performance measurement
- accuracy-before-performance gating
- repeated-run analysis
- semantic comparability checking
- result verification
- real LO/LIO integration
- useful reports
- CI regression workflow
- high-quality documentation
- public releases
- enough test coverage to trust its own benchmark logic

---

# 43. Final project thesis

LidarPerf should not ask:

> “Which LiDAR odometry algorithm has the smallest number?”

It should ask:

> **“Can we prove that these two LiDAR-odometry results were produced under comparable conditions, that both estimators remained valid and accurate, that the measurements are reproducible, and that a code change genuinely improved or regressed system performance?”**

That is the project.

---

# 44. Immediate next step

**Do not begin with algorithm integrations.**

The first implementation deliverable should be:

> `SPEC.md` — LidarPerf Benchmark Specification v0.1

It must freeze:

- tracks
- sensor rules
- timing scopes
- preprocessing declarations
- validity criteria
- accuracy gates
- tuning classes
- repetition policy
- host provenance
- result schema
- comparability rules

Only after that specification is reviewed should large-scale implementation begin.

---

## Project execution log — 2026-09-14 — Step 1: Benchmark specification

**Status:** Draft completed; awaiting Gate 1 approval.  
**Artifact:** `SPEC.md` — LidarPerf Benchmark Specification, draft v0.1.0.

### Work completed

A dedicated specification pass was performed before implementation. The research was narrowed to decisions that affect benchmark semantics rather than adding more feature ideas.

Sources reviewed during this step included:

- official KITTI odometry evaluation semantics
- Zhang & Scaramuzza's trajectory-evaluation methodology
- evalio's current repository, trajectory statistics implementation, and normalized data model
- BenchExec and the “Reliable Benchmarking” methodology
- pyperf's CPU-affinity/system-stability guidance
- 2026 LIO non-reproducibility research
- RobotPerf's reproducible robotics-computing benchmark philosophy

### Major decisions made in the draft

1. Official v0.1 scope is **LO and LIO only**.
2. SLAM and pairwise registration are deferred rather than weakly specified.
3. Canonical pose convention is **`T_W_B`**, right-handed, metres.
4. Canonical internal time representation is **int64 nanoseconds**.
5. Metric LiDAR/LIO protocols forbid silent Sim(3)/scale correction.
6. Preprocessing ownership and deskew semantics are first-class protocol data.
7. Estimators declare `online_causal`, `online_fixed_lag`, or `offline_noncausal`.
8. Opaque process backends cannot claim internal/per-frame latency.
9. BenchExec is the intended benchmark-grade Linux process-accounting backend.
10. Performance claims are gated behind execution validity, trajectory validity, coverage, and accuracy.
11. Controlled performance comparisons require repeated trials.
12. Baseline/candidate regression experiments use paired blocked randomized ordering.
13. No hidden universal “5% regression” rule: practical thresholds must be declared.
14. Exact dataset/config/protocol fingerprints are part of the result identity.
15. Unknown semantics cause strict comparability to fail rather than being guessed.

### Important research finding / avoided semantic bug

During inspection of evalio's current `stats.py`, its spatial alignment was found to align an estimated trajectory to the **first pose** of the reference trajectory. This is not the same operation as full-trajectory SE(3) Umeyama alignment commonly used for aligned APE in evo-style evaluation.

**Consequence:** LidarPerf will not inherit an evaluator merely because it uses familiar metric names such as “ATE”. Every metric profile will define its own alignment and pairing semantics, and implementations will be validated against independent golden references.

This avoids a subtle but serious future bug where two values both labeled “ATE” could be placed in the same table despite measuring different things.

### Additional design learning

The specification now separates:

- **algorithm/input semantics** from **measurement semantics**
- **accuracy comparability** from **performance comparability**
- **process-level metrics** from **instrumented per-frame metrics**
- **algorithm nondeterminism** from **system/runtime variance**
- **container provenance** from **host provenance**
- **valid artifact** from **good estimator**
- **displayable together** from **scientifically comparable**

This separation is expected to reduce later architectural rewrites.

### No implementation code written yet

This is intentional.

The highest-cost failure at this stage would be building schemas/backends around an unstable definition of a valid benchmark. Implementation begins only after Gate 1 approval.

### Gate 1 recommendations awaiting approval

The current specification recommends:

- LO + LIO only for official v0.1
- `T_W_B` canonical pose convention
- no scale correction for standard metric LO/LIO
- BenchExec for controlled Linux process metrics
- minimum 5 measured trials for controlled comparisons
- minimum 10 measured trials for publication-class experiments
- 98% default temporal-coverage validity threshold
- end-to-end timing only for opaque processes
- paired blocked randomized baseline/candidate regression runs
- explicit regression thresholds rather than a hidden default
- mandatory accuracy gate before speed conclusions
- exact SHA-256 dataset manifests where feasible
- evalio as backend/dependency rather than metric authority
- authoritative GPU benchmarking deferred beyond the initial CPU-controlled release

### Errors / bugs recorded in this step

No implementation bugs exist yet because implementation has not started.

One **design-level semantic hazard** was found and documented: incompatible trajectory-alignment semantics can share the same informal metric name. The spec now prevents that class of ambiguity by requiring explicit metric/alignment semantics.

### Tooling / artifact issue encountered

The first attempt to update the living project log through the user-visible Python environment could create the new `SPEC.md`, but could not overwrite the existing living-plan file because that mounted file was owned by a different runtime user and was not writable from that environment. The plan file itself was not corrupted. The update was then applied through the container environment with appropriate file permissions.

**Learning:** future updates to the living plan should use a writable working copy or the container path directly rather than assuming cross-tool write permissions are identical.

### Next action after Gate 1

Create the repository/package foundation and implement the protocol/schema models directly from the approved `SPEC.md`.

---

## Project execution log — 2026-09-14 — Gate 1 approved / Step 2 repository foundation

**Gate 1:** APPROVED by project owner.  
**Specification status:** `SPEC.md` draft v0.1.0 accepted as the implementation contract.  
**Step 2 status:** Local repository/package foundation completed and validated; remote GitHub repository creation is the remaining publication step.

### Gate 1 consequence

The 15 recommendations in `SPEC.md` Section 82 are now frozen as the initial implementation defaults. Future semantic changes will be made as explicit specification/protocol revisions rather than silent implementation changes.

### Repository foundation created

A local Git repository was initialized with `main` as the default branch and the following foundation:

- `README.md`
- approved `SPEC.md`
- `LidarPerf_research_execution_plan.md`
- `LICENSE` (Apache-2.0)
- `AI_USAGE.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `CITATION.cff`
- `pyproject.toml`
- Python package under `src/lidarperf/`
- Typer CLI entry point
- initial tests under `tests/`
- GitHub Actions CI skeleton for Python 3.11/3.12/3.13
- bug/feature issue templates
- pull-request template
- placeholder protocol directories

The package version remains `0.0.0`; `0.1.0` is intentionally reserved for a real technical-preview benchmark implementation rather than a repository scaffold.

### Initial local commits

```text
46138f4 chore: initialize LidarPerf repository
6323879 fix: use PEP 639 license metadata
3eb5fc5 fix: make empty CLI invocation exit successfully
```

These commit IDs are local and may change if history is deliberately squashed before the first remote PR.

### Validation performed

After editable installation of the package itself:

```text
pytest: 2 passed
compileall: passed
lidarperf --version: lidarperf 0.0.0
lidarperf with no arguments: help displayed successfully, exit code 0
```

The GitHub Actions workflow is configured to additionally run Ruff on supported Python versions once the repository is on GitHub.

### Errors / mistakes / bugs encountered and resolved

#### 1. Test invocation before editable installation

**Symptom:** `pytest` initially failed during collection with:

```text
ModuleNotFoundError: No module named 'lidarperf'
```

**Cause:** The package uses a `src/` layout and the first local test command was run before installing the package into the environment.

**Resolution:** Use an editable package installation before executing package-import tests. CI already follows this order.

**Learning:** Do not make local validation subtly different from CI package-install semantics when using a `src/` layout.

#### 2. PEP 639 / setuptools license metadata conflict

**Symptom:** Editable package metadata generation failed with:

```text
setuptools.errors.InvalidConfigError:
License classifiers have been superseded by license expressions.
```

**Cause:** `pyproject.toml` correctly used the SPDX expression:

```toml
license = "Apache-2.0"
```

but also included the legacy PyPI classifier:

```text
License :: OSI Approved :: Apache Software License
```

Modern setuptools treats that combination as invalid under the newer PEP 639 metadata path.

**Resolution:** Removed the obsolete license classifier and retained the SPDX license expression.

**Learning:** Packaging metadata should follow current PEP 639 semantics rather than copying older Python project templates.

#### 3. Development-extra installation blocked by execution environment networking

**Symptom:** `pip install -e '.[dev]'` could not fetch Ruff because the current execution container has no usable outbound package-index network access.

**Cause:** Environment limitation, not a LidarPerf dependency-resolution bug.

**Resolution:** Installed LidarPerf locally with `--no-deps` because runtime dependencies were already present, then ran pytest/compile checks. The remote GitHub Actions environment is configured to install the full development extra and run Ruff.

**Learning:** Distinguish project failures from sandbox/network limitations and record both rather than changing dependencies merely to accommodate the development agent environment.

#### 4. Typer `no_args_is_help` exit semantics

**Symptom:** The first CLI test expected an empty invocation to display help and exit successfully, but Typer returned exit code `2`.

**Cause:** Relying on `no_args_is_help=True` did not provide the CLI semantics we wanted for this callback-only initial application.

**Resolution:** Changed the app to an explicit `invoke_without_command=True` callback and print `ctx.get_help()` when no command is selected.

**Validation:** Both CLI tests now pass.

**Learning:** CLI behavior, including exit status, is part of developer UX and should be tested rather than assumed from framework option names.

### External-name check

The connected GitHub search currently returns no public repository named `LidarPerf`, and no installed repository with that name is available to the connector. The name therefore remains suitable for the project at this stage.

### Current blocker: remote repository creation

The connected GitHub integration can create branches, files, commits, issues, and pull requests **inside an existing repository**, but it does not expose a create-repository action. The local environment also has no authenticated `gh` CLI.

Therefore the only unavoidable owner action at this step is creation of the empty public GitHub repository:

```text
AbysmalDaemon/LidarPerf
```

Recommended settings for creation:

- visibility: **Public**
- repository name: **LidarPerf**
- initialize with README: **No**
- add `.gitignore`: **No**
- add license: **No**

Those files already exist in the prepared repository. After the repository exists and is visible to the GitHub connector, all normal file/branch/PR work can be handled through the integration.

### Next engineering step

Once the remote exists, publish the foundation as the first PR, then begin the protocol/schema models specified by the approved benchmark specification.

---

## Project execution log — 2026-09-14 — Gate 1 approved and remote foundation publication

**Status:** Gate 1 approved by the project owner; repository foundation publication in progress.

### Gate 1 approval

The project owner explicitly approved `SPEC.md` on 2026-09-14. The benchmark semantics in that document are therefore the initial implementation contract. Future implementation fixes may correct code without changing those semantics; any intentional semantic change must be versioned and logged rather than silently rewriting the approved protocol.

### Remote repository created

The project owner completed the one unavoidable account-level action that the connected GitHub interface could not perform: creating the empty public repository:

```text
AbysmalDaemon/LidarPerf
```

The GitHub integration confirmed administrator/push access and the repository's public visibility.

### Publication strategy

Rather than pushing directly to `main`, the repository foundation is being published on a dedicated `foundation` branch and will be offered as a pull request for owner approval. This preserves the agreed workflow: substantive changes are reviewable, and the owner only needs to approve milestone PRs rather than supervise individual file writes.

### Remote foundation work completed so far

The remote foundation branch now contains the package and repository scaffold, including:

- Python `src/` package layout
- Typer CLI entry point
- initial CLI tests
- Python 3.11–3.13 GitHub Actions CI
- Ruff + pytest configuration
- Apache-2.0 license
- contribution/security/conduct documentation
- `AI_USAGE.md`
- citation metadata
- issue and pull-request templates
- placeholder LO/LIO protocol directories

### Error / limitation: direct container `git push` is not a valid publication path

The local build environment does not have a normal authenticated GitHub network path suitable for direct `git push`. Repository publication therefore uses the connected GitHub API actions (trees, commits, refs, pull requests) instead of treating this as a project defect.

**Learning:** Keep repository transport concerns separate from code correctness. The GitHub connector is the authoritative remote-write path in this environment.

### Error: first large-document bootstrap attempt failed

`SPEC.md` and the living execution record are much larger than the small source/config files. To publish them without manually pasting them through many independent file updates, a temporary one-shot GitHub Actions bootstrap workflow was created: bounded spec fragments plus a compressed project-log payload would be assembled on the `foundation` runner, committed, and then the temporary bootstrap files/workflow would delete themselves.

The first workflow run failed with:

```text
gzip: .bootstrap/plan.md.gz: unexpected end of file
```

The failure was reproduced from the GitHub Actions job log, not inferred.

#### Root cause

A single large compressed/base64 payload was sent through one connector tool argument. The resulting blob was truncated/corrupted before GitHub Actions attempted decompression. The specification chunks themselves were not the failing component.

#### Fix

The project-log gzip is now represented as Base64 text split into bounded chunks. The runner reconstructs it with:

```bash
cat .bootstrap/plan-gzb64/part-* | base64 -d | gzip -dc \
  > LidarPerf_research_execution_plan.md
```

This deliberately uses small connector payloads and verifies the actual reconstruction on GitHub's runner rather than assuming a large write arrived intact.

**Learning:** For connector-mediated repository writes, large opaque payloads need explicit chunking and end-to-end validation. A successful blob-create response is not enough evidence that a transport encoding strategy produced a usable artifact.

### Documentation correction found during publication

The approved specification's status line contained an extra Markdown delimiter after the approval wording. This was an editorial formatting defect only; it did not change any approved benchmark semantics. The local source was normalized before final remote assembly.

### Next action

1. stage the corrected approved `SPEC.md` and updated living project log;
2. trigger and verify the one-shot remote assembly workflow;
3. verify the final remote documents and CI state;
4. open the `foundation -> main` pull request;
5. request only the owner's merge approval;
6. after merge, begin protocol/schema implementation.

### Bootstrap retry result

The bounded-chunk bootstrap retry completed successfully on GitHub Actions. The bot commit reconstructed and published the approved `SPEC.md` and the living project record, then removed the temporary chunk files and bootstrap workflow from the branch as designed.

The first failed bootstrap run remains in the Actions history as an auditable record of the mistake and retry rather than being hidden.

**Learning:** the self-cleaning bootstrap pattern works for large connector-mediated documentation, provided opaque payloads are chunked and reconstruction is actually validated on the remote runner.

### Publication state after retry

The `foundation` branch now has the complete repository foundation and approved specification in normal repository paths. A final small documentation pass will append this incident record and normalize the specification status-line formatting before the pull request is opened.

### Final remote-document verification caught a second formatting defect

After the remote finalization workflow succeeded, `SPEC.md` was fetched back from the `foundation` branch instead of assuming the workflow output was correct. That verification caught two editorial remnants:

- the status line still ended with an unintended `**` delimiter because the normalization string itself repeated the original formatting mistake;
- the specification version still said `Draft 0.1.0` despite Gate 1 already being approved.

Neither affected benchmark semantics, but both are incorrect project-state metadata. They are being corrected to:

```text
Specification version: 0.1.0
Status: Approved for implementation — Gate 1 approved 2026-09-14.
```

**Learning:** verification must check the resulting content, not merely the success status of the automation that produced it. A green workflow proves execution success, not semantic correctness of the generated document.

### Remote CI retries for PR #2

The first remote CI pass for the protocol/schema implementation failed at Ruff before tests ran. Six formatting/static-style issues were reported across the new files: import grouping/order, one simplifiable conditional assignment, one overlong line, and test-file formatting. These were corrected in a follow-up commit.

A second CI pass reduced the failure set to one `I001` import-block error in `scripts/export_schemas.py`. I initially misread Ruff's compact diagnostic and removed the blank line between standard-library and first-party imports. That was the wrong interpretation: the actual remaining issue was an **extra blank line after the import block**, not the section separator. This produced a third failed lint pass.

**Fix:** restore the stdlib/first-party separator and remove the extra blank line between the final import and the module constant. This is a small formatting error, but it is recorded because the retry was caused by my diagnosis rather than by the project requirements.

**Learning:** when a formatter/linter provides an auto-fixable structural diagnostic, do not infer the exact patch from abbreviated terminal context if the tool itself can be used as the authority. In this environment Ruff is only available in remote CI, so exact diagnostics and remote revalidation are necessary.

After Ruff passed, CI reached the test suite and caught a more important publication error: `test_checked_in_json_schema_matches_model` failed because the JSON Schema committed through the connector had been manually reconstructed and did **not** exactly match Pydantic's generated schema. Differences included enum descriptions, definition ordering/default serialization, and the representation emitted for `JsonValue`.

#### Root cause

The local generated JSON Schema was correct and local tests passed. During connector publication, I manually supplied a schema payload instead of treating the generated artifact as machine-owned output. That created drift between source models and the checked-in derived artifact.

#### Fix

The schema is regenerated **from the committed Pydantic models on GitHub's runner** using `scripts/export_schemas.py`, rather than patched by hand. Ruff and pytest are then run against the regenerated working tree before it is committed.

A related reproducibility issue was identified at the same time: exact generated-schema equality can drift when the Pydantic generator version changes. The runtime dependency remains compatible with a wider Pydantic 2.x range, but the development/schema-generation environment is now pinned to Pydantic 2.13.5. Ruff and pytest are also pinned for deterministic project CI. Upgrading these tools later must be an explicit maintenance change rather than an accidental change caused by a new package release.

**Learning:** generated artifacts must remain generated artifacts, and the generator toolchain is part of their provenance. Never hand-maintain or manually reconstruct a checked-in schema whose exact equality to source models is itself an invariant.

### Step 2 final remote verification

The protocol/schema implementation was revalidated on a clean GitHub Actions matrix for Python 3.11, 3.12, and 3.13 after regenerating the checked-in JSON Schema from the pinned Pydantic 2.13.5 development environment. Ruff passed and all 28 tests passed on each supported Python version.

The final implementation therefore verifies both source behavior and the generated-schema invariant in the same pinned toolchain used by CI.

**Step 2 status:** complete and ready for merge as PR #2.

**Next implementation step after merge:** deterministic synthetic conformance fixture plus the first versioned result-bundle models/checksum machinery.

---

## Project execution log — 2026-09-14 — Step 3 synthetic conformance fixture

**Status:** implementation complete; remote pre-PR validation passed on Python 3.13.

### Starting state

PR #2 (`feat: implement protocol schema and validation`) was merged into `main`. Step 3 therefore starts from the approved protocol semantics already represented in code.

The goal of this step is deliberately narrow: create a project-owned deterministic LiDAR fixture that can exercise coordinate, timestamp, serialization, motion-distortion, and future metric logic without requiring an external real-world dataset or dataset license in routine CI.

### Work completed

The synthetic layer now contains:

- immutable Pydantic models for fixture configuration, poses, points, scans, and the fixture manifest;
- an exact constant-speed circular `T_W_B` trajectory;
- a deterministic scene containing ground, parallel walls, vertical poles, and asymmetric boxes;
- scan-start visibility and range filtering;
- deterministic per-point acquisition-time offsets over a 360-degree scan interval;
- optional rolling-scan motion distortion using the exact body pose at each point's acquisition time;
- optional deterministic per-axis point noise;
- deterministic time-distributed point subsampling;
- a stable fixture identity derived from generator version plus canonical configuration;
- `manifest.json`, `ground_truth.tum`, timestamped `scans/index.json`, and per-scan JSONL files;
- `lidarperf synthetic generate`;
- unit and CLI tests for geometry, timing, determinism, noise, distortion, file safety, and manifest semantics.

### Geometry and timing semantics

The fixture uses the canonical `T_W_B` convention. The trajectory is an analytic constant-speed circular arc, allowing the exact body pose to be evaluated at arbitrary point-acquisition timestamps instead of numerically integrating motion.

Landmarks are selected using the scan-start pose. Acquisition offset is derived from scan-start azimuth. With motion distortion disabled, point coordinates are expressed in the scan-start body frame. With distortion enabled, the same selected landmarks are expressed in the instantaneous body frame at acquisition time. Thus distortion changes coordinates without silently changing the sampled world landmarks.

The manifest records the distinction explicitly as `scan_start_body` or `acquisition_body`.

### Deterministic noise design

The first local draft used Python's `random.gauss`. That was replaced before publication because a cross-version bitwise fixture should not depend unnecessarily on random-library implementation details.

Noise is now derived from SHA-256 keyed by `(seed, scan_index, landmark_id, axis)` and mapped through a standardized six-uniform Irwin-Hall construction. A point's noise is therefore independent of iteration order and of any global RNG stream. The manifest records this model as `hash_irwin_hall_6_v1`.

### Self-review issues caught before publication

1. **Scan timestamps were initially implicit.** Zero-padded filenames corresponded to trajectory rows but did not explicitly carry timestamps. **Fix:** add `scans/index.json` with scan index, filename, `timestamp_ns`, and point count.
2. **Point-coordinate semantics were initially implicit.** Point-time offsets alone did not state whether a coordinate lived in the scan-start or acquisition-time body frame. **Fix:** add `point_coordinate_semantics` and test both cases.
3. **An existing file used as the output path produced a low-level path error.** **Fix:** reject it deliberately with `FileExistsError` and never touch the existing path.

### Cross-version golden fixture

A small fixture exercising both nonzero noise and motion distortion has the whole-directory SHA-256 golden digest:

```text
84f4b8eed79a92de4c2a84df57fca13402a7d83dfa92aec4b3ceec3ed948fa0a
```

The same golden digest is asserted by CI. An intentional generator change that modifies fixture bytes must therefore be versioned rather than silently drifting.

### Validation

Local Python 3.13.5 validation completed with **42 passing tests**, successful `compileall`, and no Python lines above the repository's 100-character Ruff limit. The execution container remains unable to install Ruff because it has no DNS/PyPI access, so the branch was validated again on GitHub's clean Python 3.13 runner before this record was committed. Ruff and pytest both passed there.

Unlike PR #2, Step 3 was batched and locally validated before its first remote publication rather than using CI as an iterative formatter/debugger.

### Remote workflow mistake before validation

The first one-shot pre-PR validation workflow was rejected by GitHub before any job started because I embedded a shell here-document whose body was not indented as YAML block content. **No project test or lint step ran in that failed workflow.** The code itself was not implicated.

**Fix:** replace the fragile multiline YAML payload with a base64-encoded log payload, validate the workflow syntax locally, and rerun the pre-PR validation once. This failure is retained in the project record because it was a tooling mistake in how I published the log.

### Scope boundary

This is a conformance/CI fixture, **not a real-world ranking dataset**. Its analytic trajectory and simple geometry are designed to expose convention and pipeline bugs. No research claim about real-world odometry accuracy should be based on performance on this fixture.

### Next step after merge

Step 4: versioned result-bundle models, SHA-256 payload checksums, immutable bundle semantics, and `lidarperf verify`.
---

## Project execution log — 2026-09-14 — Step 4 result bundles and verifier

**Status:** implementation complete; this record is appended only after pre-PR remote Ruff + pytest validation passes on Python 3.13.

### Goal

Introduce LidarPerf's first durable benchmark artifact: a versioned `.lperf` directory that can be inspected and verified independently of the process that created it.

This step intentionally does **not** execute a real estimator. It establishes the artifact contract that later execution backends must populate.

### Work completed

The new `lidarperf.bundle` package contains:

- immutable Pydantic records for result manifests, methods, datasets, environments, trials, metrics, resource measurements, and run-set aggregates;
- explicit bundle schema identity `lidarperf.result.v1`;
- exact/weak dataset fingerprint classes;
- trial success/failure semantics;
- conformance status metadata;
- protocol ID/version/content-hash references;
- canonical algorithm-configuration fingerprints using the existing LidarPerf canonical JSON hashing rules;
- a one-shot `ResultBundleWriter` that refuses to overwrite non-empty destinations;
- path-traversal prevention for bundle-relative paths;
- deterministic JSON serialization and LF line endings;
- SHA-256 checksums for every declared payload file except `checksums.sha256` itself;
- a canonical sorted `file_inventory` stored in `manifest.json`;
- `lidarperf verify <bundle>`.

The verifier checks:

- `manifest.json` schema validity;
- required top-level payloads;
- declared file inventory versus actual regular files;
- absence of symlink payloads;
- checksum entry completeness and exact SHA-256 matches;
- protocol identity/version/content hash against a freshly resolved `protocol.yaml`;
- manifest track against the resolved protocol;
- method identity against `method.json`;
- algorithm config canonical hash against `config/algorithm.yaml`;
- dataset identity/content hash consistency;
- measurement class consistency between manifest and environment record;
- numbered trial structure and trial indices;
- per-trial metrics/resources schema validity;
- aggregate success/failure counts against actual trial records;
- unexpected numbered trials beyond `manifest.trial_count`.

A weak dataset fingerprint is accepted as an internally valid artifact but reported as `VALID WITH WARNINGS`, preserving the distinction between artifact integrity and reproducibility strength.

### Bundle structure now enforced

```text
<result>.lperf/
├── manifest.json
├── protocol.yaml
├── method.json
├── dataset.json
├── environment.json
├── aggregate.json
├── config/
│   └── algorithm.yaml
├── trials/
│   └── 0001/
│       ├── trial.json
│       ├── metrics.json
│       ├── resources.json
│       ├── trajectory.tum
│       ├── stdout.log
│       └── stderr.log
└── checksums.sha256
```

`telemetry.parquet` remains optional and will be introduced when telemetry-producing backends exist.

### Immutability rule

The public writer refuses an existing non-empty output directory. Once finalization writes `manifest.json` and `checksums.sha256`, the writer cannot append more payloads.

The verifier also rejects undeclared extra payloads. A corrected benchmark result must therefore be emitted as a new bundle instead of silently mutating an already published one.

This gives the later research workflow an audit-friendly artifact model rather than an editable results directory.

### Configuration hashing decision

The checksum of `config/algorithm.yaml` protects exact file bytes, but the method-level `config_sha256` has a different purpose: semantic configuration identity.

Therefore `config_sha256` is calculated from parsed YAML/JSON through LidarPerf's canonical JSON representation. Merely reordering YAML keys does not change the configuration fingerprint, while changing a value does.

Tests explicitly cover both cases.

### Verification status semantics

The new verifier returns exactly three artifact-integrity states:

```text
VALID
VALID WITH WARNINGS
INVALID
```

The CLI exits with code 0 for the first two and code 2 for `INVALID`.

A `VALID` bundle means the artifact is internally consistent with its declared LidarPerf metadata. It does **not** mean the estimator is accurate or scientifically good; correctness/accuracy gates belong to later execution and regression layers.

### Local implementation bug caught before publication

The first bundle-model draft attempted to express safe relative paths using a regular expression with negative look-ahead assertions.

Pydantic v2 delegates these patterns to Rust's regex engine, which deliberately does not support look-around. Test collection therefore failed before any tests ran with a `SchemaError`.

**Fix:** replace regex look-around with an explicit `AfterValidator` using `PurePosixPath` plus checks for absolute paths, backslashes, duplicate separators, dot components, and parent traversal.

**Learning:** validation logic that depends on regex features must respect the regex engine actually used by the schema/runtime. For filesystem security invariants, explicit path-component validation is clearer and less engine-dependent than a compact look-around-heavy expression.

This failure happened entirely during local pre-publication validation and therefore did not create a red project CI run.


### Additional filesystem-safety review

After the first passing bundle implementation, a second review found two cases worth hardening before publication:

1. the writer used `pathlib.Path` normalization, which could silently normalize `nested/./file` and, on Linux, treat backslashes as literal filename characters rather than reject Windows-style path spelling;
2. an existing symlink to an empty directory could satisfy the writer's initial “directory exists and is empty” check and redirect bundle output outside the path the caller appeared to request.

**Fix:** bundle writer paths must already be canonical POSIX-relative spellings, backslashes are rejected, and both writer and verifier reject a symlink as the bundle root. Bundle payloads, the manifest, and the checksum file are also created with exclusive-create filesystem modes so the writer never replaces an entry that appears after initialization.

**Learning:** provenance containers should never silently normalize caller-supplied artifact paths, and an integrity writer must reason about symlinks explicitly rather than treating `is_dir()` as sufficient containment evidence.

### Local validation

After the path-validation fix and additional filesystem-safety self-review:

```text
66 passed
```

Additional checks:

- `compileall` succeeds for `src/` and `tests/`;
- no Python source/test line exceeds the configured 100-character Ruff line limit;
- tampering with a trajectory produces `CHECKSUM_MISMATCH`;
- adding an undeclared file produces `INVENTORY_EXTRA`;
- deleting a payload produces inventory/checksum failures;
- semantically changing algorithm YAML while refreshing file checksums still produces `CONFIG_HASH_MISMATCH`;
- reordering unchanged YAML keys remains valid because the semantic configuration hash is canonical;
- changing the manifest protocol hash while recomputing file checksums still produces `PROTOCOL_HASH_MISMATCH`;
- inconsistent aggregate trial counts are rejected;
- a weak dataset fingerprint produces `VALID WITH WARNINGS` rather than a false exact-reproducibility claim;
- the CLI returns exit code 2 for invalid bundles;
- writer paths reject parent traversal, Windows-style separators, dot-normalized aliases, and symlink bundle roots;
- verifier rejects a symlink presented as the bundle root;
- writer payload creation is exclusive and refuses a file created after writer initialization instead of replacing it.

### Pre-PR remote validation

A clean Ubuntu/Python 3.13 GitHub runner was used before opening the PR so the normal PR matrix would not become the first place we discover avoidable lint/toolchain problems.

The first remote validation attempt found exactly one Ruff issue: `UP017` in `tests/bundle/conftest.py`, where the test fixture used `timezone.utc` instead of Python 3.11+'s `datetime.UTC` alias. No project test ran in that attempt because Ruff correctly stopped the workflow first.

**Fix:** import `UTC` directly and use `tzinfo=UTC`. The second clean validation passed Ruff and all **66 tests** on Python 3.13.15.

This is precisely why Step 4 used a pre-PR validation branch: the small compatibility/style fix happened before the review PR and did not create a red PR CI run.

### Publication-workflow mistake

Before the validation workflow above, I attempted to combine validation and automatic engineering-log appending in one temporary GitHub Actions workflow. GitHub rejected that workflow before scheduling any jobs, so no project code, lint, or tests ran.

Rather than keep iterating on a nonessential logging workflow, I removed it and replaced it with a minimal validation-only workflow copied from the already proven Step 3 pattern. The living log is being updated directly after validation instead.

**Learning:** temporary automation used only to move documentation should not be coupled to the code-validation path. Keep pre-PR validation workflows minimal; update the durable engineering record separately after the validation result is known.

### Next action

Open the Step 4 PR and run the normal clean Python 3.11–3.13 GitHub Actions matrix. Any remote-only failure will be retained here rather than hidden.

After merge, Step 5 is host fingerprinting and `lidarperf doctor`.
---

## Project execution log — 2026-09-14 — Step 5 host fingerprinting and `lidarperf doctor`

**Status:** implementation staged on `host-doctor`; local focused validation complete; normal PR CI is the remaining gate before merge.

### Goal

Implement the read-only host-provenance layer required by the benchmark specification before process execution is introduced. The host probe must expose enough machine and runtime state to explain benchmark conditions without silently tuning the system or collecting unnecessary identifying information.

### Work completed

A new `lidarperf.host` package now provides:

- versioned `lidarperf.host.v1` host snapshots;
- versioned `lidarperf.doctor.v1` readiness reports;
- CPU model, architecture, logical/physical core count, process affinity, NUMA nodes, scaling drivers, governors, boost state, and available thermal-throttle counters;
- RAM, available-memory, swap-total, and swap-use state;
- OS/distribution, kernel, architecture, and libc provenance;
- cgroup version, visible controllers, direct-writability state, and coarse container detection;
- optional dataset-filesystem inspection through `--data-path`, including network-filesystem classification;
- NVIDIA device name/driver discovery and CUDA toolkit discovery when the standard tools are available;
- one/five/fifteen-minute system load and AC-power state where exposed by the OS;
- BenchExec/runexec capability discovery;
- a canonical `host_sha256` identity derived from static-enough host attributes;
- `lidarperf doctor`, `lidarperf doctor --json`, and `lidarperf doctor --data-path ...`.

The doctor command is deliberately read-only. It never changes CPU governors, affinity, cgroups, boost state, or power settings.

### Stable host identity versus dynamic run state

The host hash intentionally excludes conditions that can change from one run to another on the same machine, including:

- current CPU affinity;
- governor selection;
- boost state;
- current load;
- swap usage;
- thermal-throttle counters;
- dataset path/filesystem choice.

Those values remain in the snapshot because they matter for benchmark interpretation, but they are not used as the stable host identity.

The hash does include OS/kernel/libc, CPU model/topology, scaling-driver family, total memory, NUMA topology, and non-unique GPU model/driver information. A material platform update can therefore intentionally produce a new host identity.

### Privacy / provenance decision

The host probe intentionally does **not** collect:

- usernames;
- hostnames;
- IP or MAC addresses;
- disk serials;
- motherboard/BIOS serials;
- GPU UUIDs/serials;
- raw cgroup paths or container IDs.

Those identifiers are not needed to compare LiDAR-odometry performance and would make public result bundles unnecessarily identifying. This is now a project-level provenance rule rather than an accidental omission.

### Doctor readiness semantics

Every successfully probed machine is eligible for `exploratory` measurement.

`controlled` eligibility is withheld when the doctor cannot establish prerequisites that are required by the v0.1 specification, currently including:

- non-Linux execution;
- unknown CPU affinity;
- unavailable/unclassifiable Linux cgroups;
- missing BenchExec/runexec.

Other conditions are warnings rather than automatic blockers because the specification requires them to be recorded but does not universally forbid them. Examples include unrestricted affinity before the execution backend pins CPUs, powersave governor state, visible cgroup-root non-writability pending delegation checks, swap use, elevated load, and network-mounted dataset storage.

The next BenchExec step remains responsible for the definitive execution-time cgroup/delegation check. `doctor` is a preflight assessment, not a substitute for backend capability verification.

### Filesystem and GPU scope

`--data-path` is opt-in. LidarPerf does not store the caller's absolute path in the portable host snapshot; it stores only the existence/filesystem classification needed for performance interpretation.

NVIDIA discovery uses standard tooling when available but stores device names and driver/toolkit versions only. GPU benchmarking remains experimental in v0.1; this metadata is provenance groundwork, not a claim that GPU timing is authoritative.

### Local focused validation

A standalone local harness exercised the new host package and CLI surface before publication:

```text
9 passed
```

The focused tests cover:

- `/proc/meminfo` byte conversion;
- physical-core parsing from `/proc/cpuinfo`;
- controlled eligibility on a clean synthetic Linux snapshot;
- controlled blocking when BenchExec is absent;
- network-filesystem warning generation;
- missing dataset-path error generation;
- a read-only real-host probe smoke test;
- JSON doctor output;
- CLI nonzero exit for an explicitly missing `--data-path`.

`compileall` also succeeds for the staged source/tests, and staged Python lines were checked against the repository's 100-character source-line limit.

### Development mistakes / self-review findings

1. The first isolated test harness omitted a root `lidarperf/__init__.py`, causing test collection to fail with `ModuleNotFoundError`. This was a scratch-harness packaging mistake, not a repository implementation failure. The harness was corrected and all focused tests passed.
2. A pre-publication static review caught that the first `probe.py` draft imported `Iterable` from `typing`. With the repository's Ruff `UP` rule family, that would be flagged in modern Python. It was changed to `collections.abc.Iterable` before the branch commit.

**Learning:** keep the remote PR matrix as the authoritative lint/toolchain gate, but perform a focused local import/compile/test pass and a manual Ruff-rule review before opening the PR so trivial failures do not become review-history noise.

### Next action

Update public documentation, open PR #5, and require the normal Python 3.11/3.12/3.13 Ruff + pytest matrix to pass before merge. After Step 5 merges, Step 6 is the BenchExec execution backend and controlled process resource measurement.


---

## Project execution log - 2026-09-14 - Step 6 BenchExec execution backend

**Status:** implementation complete on `benchexec-backend`; pre-PR validation passed. PR CI is the remaining merge gate.

### Implemented

Step 6 adds the controlled Linux process-execution layer using BenchExec/`runexec` rather than a custom monitor. It includes versioned command/resource/measurement/result/capability models, direct argv execution, wall and CPU time, peak-memory accounting, CPU/wall/memory/core/NUMA limits, return/signal/timeout/termination normalization, backend-version capture, compact diagnostics, and an active `probe_capability()` readiness check. The backend defaults to `--no-container`; software containers remain a separate Docker backend.

BenchExec combines command stdout and stderr in `runexec --output`. The result-bundle contract, SPEC, verifier, tests, and README now preserve this honestly: a trial has either `process.log` or a genuine `stdout.log` + `stderr.log` pair, never both.

The portable `benchmark` extra uses `benchexec>=3.31,<4`. Controlled hosts may add BenchExec systemd integration or run in a delegated systemd scope as documented.

### Validation

Final pre-PR validation on Ubuntu 24.04 / Python 3.13: `runexec 3.35` smoke PASS; Ruff PASS; pytest PASS (`87 passed`). The PR Python 3.11/3.12/3.13 matrix is the authoritative cross-version gate.

### Errors and learnings

1. Real `runexec` on GitHub-hosted CI failed because delegated cgroups are unavailable. This is an environment capability result, not a product failure; an active readiness probe was added.
2. Forcing `benchexec[systemd]` caused a `pystemd` build failure due missing `libsystemd.pc`. The dependency was returned to portable BenchExec and host prerequisites were documented.
3. The original split stdout/stderr bundle contract did not match BenchExec reality. It was changed to support `process.log` without fabricating stream separation.
4. Old transfer corruption was found in remote `SPEC.md`. Multiple hash-driven repair attempts were too brittle and generated unnecessary failed CI. Semantic invariant repair succeeded. Learning: validate transferred artifacts immediately and avoid whole-file hashes as the sole repair criterion when intended semantic changes are known.
5. One verifier test over-specified `TRIAL_LOG_MISSING`; the more precise inventory/checksum errors were retained.
6. Two temporary Step 6 finalizer attempts failed (invalid YAML indentation, then a corrupted copied base64 payload). These were workflow/tooling mistakes, not product-code failures. This entry records them explicitly.

### Next

Open PR #6, pass the normal Python 3.11/3.12/3.13 CI matrix, merge, then begin Step 7: trajectory representation and structural validation.

---

## Project execution log — 2026-09-14 — Step 7 trajectory validity and metrics

**Status:** implementation finalized on `trajectory-metrics` after full pre-PR lint/test validation. Pull-request CI remains the cross-version merge gate.

### Goal

Implement the first protocol-scoped trajectory evaluation layer: canonical trajectory loading, structural validity, timestamp association, rigid alignment, coverage accounting, APE-style accuracy, and explicitly defined distance-window relative pose errors. Keep all metric semantics visible in the protocol/result keys rather than hiding evaluator defaults.

### Work completed

Step 7 adds:

- canonical in-memory `T_W_B` trajectories with signed int64 nanosecond timestamps;
- deterministic TUM parsing/serialization with decimal timestamp conversion rather than binary-float timestamp rounding;
- structural validation for nonempty trajectories, finite translations, unit rotations, invalid-pose counts, duplicate/non-increasing timestamps, and declared body frame;
- `exact`, `nearest`, and `interpolate_reference` association modes driven by protocol data;
- bounded nearest-neighbor association with deterministic tie-breaking;
- reference interpolation using linear translation plus shortest-arc quaternion SLERP, with extrapolation forbidden and reference gaps bounded;
- explicit temporal and distance coverage accounting;
- rigid `none`, `origin`, and full-trajectory SE(3) alignment, with no scale correction;
- translation and rotation APE summaries under the declared alignment;
- reference-distance-window relative pose error with translation metres, rotation degrees, translation percent, and rotation degrees/metre;
- semantic metric keys such as `ape.translation.rmse_m` and `rpe.distance_10m.translation.rmse_m`, never naked `ATE`/`RPE` fields;
- explicit representation of unavailable relative-error windows instead of fabricated zero errors;
- a NumPy runtime dependency for vectorized trajectory mathematics;
- unit tests covering parsing, timestamp precision, structural failures, association/interpolation, alignment, RPE, coverage, unavailable windows, and metric naming.

### Protocol gap found and closed before release

The approved `SPEC.md` already stated that a distance-window relative error's **exact pairing/tolerance rule is protocol data**, but the v0.1 Pydantic schema and reference YAML documents only stored `distance_m`. That meant two evaluators could both claim the same protocol identity while choosing materially different RPE pairs.

Step 7 closes that gap by making both fields mandatory:

```yaml
relative_error_windows:
  - distance_m: 10.0
    pairing: all_starts_nearest_reference_distance
    relative_tolerance: 0.1
```

The implemented pairing rule is now normative and explicit:

1. compute cumulative path length on the associated reference trajectory;
2. consider every reference pose as a start;
3. select the later endpoint closest to the requested reference distance;
4. break equal-distance ties toward the earlier endpoint;
5. accept only when the distance mismatch is within the declared relative tolerance;
6. permit overlapping windows;
7. retain pair count and actual accepted-distance statistics.

If no valid pair exists, the metric is unavailable rather than zero.

Because these protocols are still pre-release/pre-alpha and have not been published as immutable released protocol versions, this correction remains version `1` but intentionally changes the canonical protocol content hashes. Once a protocol is released, equivalent semantic changes must use a new protocol version.

### Alignment decision

The generic metric profile uses full-trajectory rigid SE(3) alignment with **no scale correction**, matching the approved metric-scale LO/LIO semantics. The implementation refuses an underdetermined SE(3) fit (for example a static or collinear position trajectory) instead of silently inventing an arbitrary rotation that would make rotation APE ambiguous.

### Structural validity and disclosure

Parsing and structural validation are deliberately separate. A parseable TUM pose containing NaN/Inf is retained long enough for validation to count and report the invalid pose. LidarPerf does not silently drop such poses before metrics. Metric evaluation itself refuses structurally invalid trajectories.

### Coverage decision

Temporal coverage is the fraction of reference time span covered by the matched estimator span. Distance coverage is the matched-reference path length divided by full reference path length where a reference path distance exists. Both are retained alongside matched/unmatched pose counts. The protocol's temporal coverage threshold remains the accuracy/performance gate.

### Validation strategy and learnings

The development container could not clone GitHub because outbound GitHub DNS/network access is unavailable there. This is an environment limitation, not a project failure. The trajectory core was therefore exercised in an isolated local module harness before publication, then the complete repository was validated remotely only after the branch was assembled.

Before opening the PR, a review of `SPEC.md` against the implementation also caught the missing distance-coverage output required by section 24. It was added before the final validation run rather than deferred to another corrective PR.

A methodological cross-check of existing trajectory-evaluation conventions was used only to challenge our assumptions; no external evaluator source code is vendored or copied. LidarPerf's pairing semantics remain independently implemented and, crucially, encoded in protocol data.

**Learning:** trajectory metrics are not identified by labels like “ATE” and “RPE.” Association, alignment, scale, pairing, tolerance, body frame, and coverage semantics must all be explicit if a result is supposed to remain comparable months later.

**Learning:** generated protocol JSON Schema remains machine-owned output. The schema is regenerated from the modified Pydantic model under the pinned development toolchain and tested for exact equality rather than edited by hand.

### Next action

Open PR #7 and require the normal Python 3.11/3.12/3.13 CI matrix to pass. After merge, Step 8 is the first real external execution integration through evalio, beginning with a KISS-ICP end-to-end path.

---

## Project execution log — 2026-09-14 — Step 8 evalio + real KISS-ICP integration

**Status:** functional integration complete on `evalio-kiss`; durable real-data evidence is committed. The final `main` pull request and its normal Python 3.11/3.12/3.13 matrix are the remaining publication gate for this step.

### Goal

Prove that LidarPerf can use an existing execution ecosystem rather than becoming another estimator/dataset zoo: run a real public LiDAR sequence through evalio and real KISS-ICP, parse the resulting trajectories into LidarPerf's canonical representation, evaluate them under explicit LidarPerf semantics, and retain auditable evidence without treating a GitHub-hosted runner as an authoritative performance machine.

### Backend implemented

Step 8 adds a thin evalio adapter rather than duplicating evalio registries or metrics. The adapter:

- exposes an optional `evalio>=0.6,<0.7` dependency;
- probes the installed evalio CLI/package capability;
- builds shell-free `evalio run` argument vectors;
- validates dataset/pipeline names and expected output paths;
- parses evalio CSV trajectories while preserving nanosecond timestamps;
- converts estimate and ground truth into LidarPerf `Trajectory` objects;
- delegates trajectory validity, association, alignment, coverage, and metrics to LidarPerf;
- propagates explicit benchmark input support through `EvalioBackend.evaluate()`.

The integration target is evalio 0.6.1, KISS-ICP 1.3.0, and `hilti_2022/basement_2`.

### Real-data semantic failure 1 — wrong coverage denominator

Workflow run `34855048114` successfully installed evalio/KISS, downloaded the real Hilti sequence, processed the requested 120 LiDAR scans, and produced nonempty estimate/ground-truth CSV files. LidarPerf then failed the run with temporal coverage `0.159893`.

The estimator had intentionally processed only a 120-scan prefix while evalio's `gt.csv` covered much more of the sequence. Dividing the valid prefix by the entire ground-truth file therefore made a complete requested prefix look roughly 16% complete.

**Correction:** coverage cannot automatically use whatever full reference file happens to be on disk. The benchmarked sensor/input interval must be represented explicitly.

### Real-data semantic failure 2 — input support is not necessarily ground-truth support

The first correction introduced `EvaluationSupport` and measured the prefix against the actual first/last LiDAR timestamps. Workflow run `34856259804` again executed the real KISS path successfully but LidarPerf rejected evaluation because it required the declared input interval to lie wholly inside reference support.

Real Hilti data disproved that assumption. In the successful run, the first requested LiDAR timestamp precedes the first available normalized ground-truth timestamp by **99.988 ms**.

**Final semantic model:**

- **input support** = sensor interval requested from the estimator;
- **reference support** = interval where ground truth exists;
- **evaluable support** = intersection of input and reference support.

Accuracy association and coverage operate on the evaluable support. Input and reference supports remain separately recorded, so restricting metrics to the intersection cannot hide missing ground truth. No-overlap inputs are rejected.

This distinction is encoded in trajectory association models/tests, propagated through the evalio backend, emitted as metric/evidence fields, and clarified in `SPEC.md` before release.

### Pre-real validation findings

Before spending another multi-gigabyte dataset download, the support fix was isolated behind an internal PR into `evalio-kiss` and exercised with the normal Python matrix. That process found and fixed three non-methodological test/tooling issues:

1. three Ruff line-length violations in the validation script;
2. an evalio smoke fixture that was collinear and therefore correctly underdetermined for SE(3) alignment;
3. a rotation-zero assertion that demanded `1e-12` degree precision even though SVD-based rigid alignment produced a harmless micro-degree floating-point residue.

The implementation was not weakened for those failures: the fixture became non-collinear and the numerical assertion received a realistic tolerance. The final lightweight matrix passed on Python 3.11, 3.12, and 3.13.

The internal support-fix PR used pull-request number #8 with base `evalio-kiss`; therefore the final Step 8 PR to `main` will use the next available repository PR number. This is recorded to avoid later confusion with the original planning note that called the final integration PR “PR #8”.

### Expensive-workflow correction

The first real workflow versions ran the 6.3 GB Hilti download before repository lint/tests. Step 8 now performs cheap Ruff + pytest validation first so ordinary code failures cannot waste a large dataset transfer.

The one-shot real-data workflow was designed to remove itself after success. That happened in the successful run, so the expensive Hilti download is not a permanent push-time CI job.

### Successful real validation

Workflow run `34860064110` completed successfully on Ubuntu 24.04 / Python 3.11.

Pre-download validation:

```text
Ruff: all checks passed
pytest: 119 passed
```

Real execution:

```text
dataset: hilti_2022/basement_2
evalio: 0.6.1
KISS-ICP: 1.3.0
requested LiDAR scans: 120
KISS processed: 120/120
```

The public dataset download was approximately 6.3 GB and took 17:07 on this hosted runner. The estimator execution itself was only a few seconds, but **no hosted-runner runtime from this workflow is an authoritative LidarPerf performance result**.

The workflow produced and committed:

```text
docs/validation/step8_kiss_evalio.json
```

and then deleted `.github/workflows/step8-real-kiss.yml` as intended.

### Durable evidence

The committed evidence records:

- validation scope `functional_integration_only`;
- `performance_authoritative: false` and the hosted-runner reason;
- evalio 0.6.1 and KISS-ICP 1.3.0;
- 120 estimator poses and 689 reference poses;
- SHA-256 fingerprints of both generated trajectory files;
- the explicit Step 8 association override `nearest`, maximum 10 ms;
- input, reference, and evaluable support timestamps/durations;
- 119 matched poses and one unmatched estimate pose;
- zero invalid estimator/reference poses;
- evaluable temporal coverage 1.0 against a required 0.98;
- evaluable distance coverage 1.0;
- translation APE RMSE `0.33748229509746847 m`;
- rotation APE RMSE `47.89751763041684 deg`;
- unavailable 10 m/100 m RPE windows represented with pair count zero rather than fabricated zero errors.

Input support is `11.899040 s`; evaluable support is `11.799052 s`. The difference is the disclosed ground-truth gap at the beginning of the requested sensor prefix.

### Frame and metric interpretation

Upstream evalio's Hilti adapter declares `imu_T_gt()` as identity, so normalized Hilti ground truth is already expressed for the IMU body frame. The evalio KISS adapter receives `imu_T_lidar`, stores its inverse as `lidar_T_imu`, and serializes `kiss_icp_->pose() * lidar_T_imu`. The Step 8 integration therefore treats both serialized trajectories as the same evalio IMU/body frame.

The relatively large rotation APE in this short prefix is retained exactly rather than explained away. Step 8 is a functional integration validation, not a KISS accuracy publication or an accuracy-gated performance comparison. Before Hilti rotation accuracy is used for a scientific benchmark claim, the result should be investigated under a longer, protocol-selected sequence and an explicit accuracy-validity policy. This does not invalidate the Step 8 proof that the real execution and LidarPerf evaluation path function end to end.

### Association decision

The built-in LO reference protocol defaults to exact timestamp association. Step 8 used an explicit temporary integration-protocol copy with nearest association and a declared 10 ms maximum difference because Hilti ground truth is higher-rate than LiDAR. The override is stored in evidence and is not a hidden evaluator default. In this successful prefix, matched pose timestamps happened to have zero recorded nearest-neighbor delta.

### Repository-history mistakes retained

Two earlier no-op commits on `main` accidentally added and immediately removed a `.step8-placeholder` file. Public history is intentionally not rewritten to hide them. They are harmless repository-history noise and are retained here as a tooling mistake.

### Step 8 conclusion

LidarPerf has now proven the following real functional path:

```text
public Hilti LiDAR data
→ evalio
→ real KISS-ICP
→ evalio trajectory files
→ LidarPerf parsing
→ structural validation
→ explicit timestamp association
→ explicit input/reference/evaluable support semantics
→ rigid SE(3) alignment
→ APE/coverage metrics
→ durable validation evidence
```

This validates the evalio abstraction without claiming hosted-runner performance authority.

### Next action

Open the final `evalio-kiss -> main` integration PR, require the normal Python 3.11/3.12/3.13 Ruff + pytest matrix to pass, merge only when green, and then proceed to Phase 9: the first complete real run including controlled execution, result-bundle writing, and bundle verification.


---

## Project execution log — 2026-09-14 — Step 9 first complete real `.lperf` run

**Status:** complete on `step9-end-to-end`; the real evidence bundle is committed and independently verifies. Final PR merge to `main` is the remaining publication gate for this step.

### Step 8 publication gate closed

The final Step 8 pull request was PR #9, `feat: add real evalio KISS-ICP integration`. It was squash-merged to `main`; the post-merge Python 3.11/3.12/3.13 matrix passed. Step 9 therefore began from a published real evalio/KISS integration rather than an unmerged feature branch.

### Goal

Produce the first complete LidarPerf artifact path on real public data:

```text
Hilti dataset
→ evalio
→ KISS-ICP
→ BenchExec/runexec process-tree accounting
→ LidarPerf trajectory validity + association + coverage + accuracy
→ resource record
→ immutable `.lperf` bundle
→ checksum/inventory verification
→ independent `lidarperf verify`
```

### Orchestration layer implemented

Step 9 adds a single-trial orchestration primitive in `src/lidarperf/runner.py`. It owns experiment composition rather than bloating either the evalio adapter or BenchExec backend. It:

- builds the evalio command through `EvalioBackend`;
- executes that exact argument vector through `BenchExecBackend`;
- refuses to proceed unless real BenchExec process-tree accounting is available;
- evaluates the resulting trajectory using LidarPerf semantics and explicit input support;
- captures host, software, execution, method, dataset, config, trajectory, metrics, resources, logs, and raw evalio trajectory artifacts;
- writes an immutable checksummed result bundle;
- immediately verifies the completed bundle and raises if verification fails.

The real-run producer is `scripts/run_step9_real.py`.

### Measurement-strength semantic guard discovered during Step 9

A single trial cannot honestly claim `controlled` or `publication` measurement strength under the approved protocol, because the protocol requires at least five measured trials for controlled evidence and ten for publication-class evidence.

The Step 9 runner therefore defaults to `exploratory` and refuses stronger classes when their required trial count exceeds one. The verifier was hardened independently with the same rule, so a hand-crafted bundle cannot bypass it by merely declaring `measurement_class: controlled` with one trial.

This is a deliberate boundary between Step 9 and Step 10: Step 9 proves the complete artifact path; Step 10 will own repeated execution and controlled measurement strength.

### BenchExec / cgroup investigation

The pip-installed BenchExec probe initially suggested the hosted runner was unsuitable for controlled-ready execution. The official Ubuntu/SoSy-Lab BenchExec package installed successfully, but `cpuset` delegation was missing under the GitHub runner's user cgroup hierarchy.

Several short probes were used before the expensive dataset download. The successful sequence was:

1. enable `cpuset` in the user's parent cgroup;
2. create a delegated transient user scope with `systemd-run --user --scope --slice=benchexec -p Delegate=yes`;
3. enable `cpuset` in `benchexec.slice` after the slice exists;
4. run `runexec` inside that delegated scope.

The successful probe returned real wall time, CPU time, and peak-memory accounting. One intermediate probe failed because `--pipe` had been combined with systemd scope mode, which systemd rejects; that was a command-line mistake, not a BenchExec limitation.

The final real workflow used the proven delegated-scope setup and BenchExec `runexec 3.35`.

### Cheap-gate findings before the real run

The normal PR matrix caught one Ruff `I001` import-layout issue in `tests/test_runner.py`. The file looked visually sorted; the pinned Ruff version's canonical rewrite removed one extra blank line after the import block. A one-shot fixer applied exactly the pinned tool's rewrite and deleted itself.

The final lightweight matrix then passed on Python 3.11, 3.12, and 3.13. The real-data workflow re-ran Ruff and pytest before downloading Hilti and reported:

```text
Ruff: all checks passed
pytest: 124 passed
```

### Real Step 9 workflow

Workflow run `34882174888` completed successfully on GitHub-hosted Ubuntu 24.04 / Python 3.11.

The public Hilti `hilti_2022/basement_2` sequence downloaded successfully. The 6.3 GB bag transferred in approximately 3 minutes 18 seconds on this runner.

The benchmark then ran a 120-scan KISS-ICP prefix under BenchExec and created:

```text
docs/validation/step9_kiss_hilti.lperf/
```

The producer's internal verification returned `VALID`, and a separate CLI invocation:

```text
lidarperf verify docs/validation/step9_kiss_hilti.lperf
```

also returned `VALID` before the evidence was committed. The one-shot expensive workflow deleted itself after success.

### Durable bundle identity

The committed result records:

```text
result_id: 507fe1d4-b803-4d0e-8fe6-a7ff7348b7cd
protocol: lidarperf/lo-se3-hilti-step9@1
protocol SHA-256: ca98119dbf045a99c0208935d61b0b43e7752b495a5786d12834bbb7b8eae95d
dataset: hilti_2022/basement_2
dataset content SHA-256: dc43d3e3e1345369ff73fec2b92d2cd5195a8e044770545abe8bdc4a0ccd198e
measurement class: exploratory
trial count: 1
conformance: conformant
verification: VALID
```

The dataset identity is an exact SHA-256 canonical file manifest. It fingerprints both the raw 6,260,771,085-byte bag and evalio's Hilti ground-truth text file. The latter has SHA-256 `dec7b20cc11002482ccb416a6e1a1c410d385b843504d3aedf7b5956746af1b6`.

The filename `exp14_basement_2_imu.txt` was explicitly audited because it could be mistaken for an IMU-only file. Upstream evalio's Hilti adapter returns that file as the second dataset file and loads it in `ground_truth_raw()`, so recording it as the raw ground-truth fingerprint is correct.

### Real trajectory / accuracy evidence

The Step 9 artifact reproduces the Step 8 trajectory behavior under the same explicit 10 ms nearest-association integration protocol:

```text
matched poses: 119
unmatched estimate poses: 1
invalid estimate poses: 0
invalid reference poses: 0
evaluable temporal coverage: 1.0
evaluable distance coverage: 1.0
translation APE RMSE: 0.3374822950974683 m
rotation APE RMSE: 47.89751763041686 deg
10 m RPE pairs: 0
100 m RPE pairs: 0
```

The large rotation APE remains an explicit unresolved scientific/metric caveat. Step 9 does not reinterpret or hide it. This real bundle proves the artifact and accounting path, not that this short KISS/Hilti prefix satisfies a future publication accuracy threshold.

### Real BenchExec resource evidence

`runexec 3.35` measured the full end-to-end evalio command process tree for the 120-scan trial:

```text
wall time: 3.5891886269999986 s
CPU time: 4.458963 s
peak memory: 130203648 bytes
CPU-core equivalents: 1.242331753326377
timed out: false
termination reason: null
```

These measurements are genuine BenchExec accounting, but they are **not an authoritative performance baseline** because the machine is a GitHub-hosted VM. `environment.json` records both facts explicitly with `performance_authoritative: false` and the hosted-runner reason. Controlled/publication performance conclusions remain reserved for stable repeated runs, preferably on a fixed self-hosted Linux host.

### Result bundle contents

The committed `.lperf` directory includes:

- `manifest.json` with protocol/dataset/result identity and exact file inventory;
- `protocol.yaml` containing the integration protocol;
- `method.json` and `config/algorithm.yaml` with KISS-ICP 1.3.0 provenance/default configuration;
- `dataset.json` with exact raw-file SHA-256 manifest;
- `environment.json` with host fingerprint, evalio version, BenchExec backend/version, exact argv, timing scope, and authority disclaimer;
- `aggregate.json`;
- trial status, metrics, resources, normalized TUM trajectory, and combined process log;
- raw evalio estimate and normalized ground-truth CSV artifacts;
- `checksums.sha256` covering every declared payload.

### Verifier hardening

Step 9 extends bundle verification beyond structural trial-count consistency. The verifier now checks whether the manifest's measurement class has enough measured trials under the bundled protocol. This prevents a structurally valid but scientifically overstated bundle from claiming controlled/publication strength.

### Tooling / repository mistakes retained

During Step 9 repository transport, an accidental one-line `noop` file was briefly created on `main` and removed immediately; no product code changed. Several temporary branch names were also accidentally created while trying to establish a CI branch. These are tooling noise rather than product changes and are recorded rather than hidden.

The BenchExec/cgroup probe history also contains several failed one-shot workflow attempts while discovering the correct hosted-runner delegation sequence. The first Step 9 documentation-finalizer workflow was also invalid YAML because a large embedded Markdown block escaped the YAML scalar indentation; it created no job and changed no project file. None of these failures are erased from project history.

### Step 9 conclusion

LidarPerf has now demonstrated its first complete real artifact path:

```text
real public LiDAR dataset
→ exact dataset fingerprint
→ evalio 0.6.1
→ KISS-ICP 1.3.0
→ BenchExec runexec 3.35 process-tree accounting
→ LidarPerf trajectory validity/association/coverage/accuracy
→ resource record
→ immutable provenance-rich `.lperf` bundle
→ SHA-256 inventory integrity
→ independent `lidarperf verify`: VALID
```

This is the first durable proof that LidarPerf is more than disconnected components.

### Next action

Finalize PR #10 documentation, require the normal Python 3.11/3.12/3.13 matrix on the exact final branch head, squash-merge only when green, verify post-merge `main`, then begin Step 10: repeated-run scheduling, warmups, runtime distributions, trajectory repeatability, and the first legitimately controlled measurement-class bundle.


---

## Step 10 — repeated-run execution and repeatability — COMPLETE (2026-09-14)

### Goal

Extend the Step 9 single-trial artifact path into an auditable run set: explicit warmups, multiple measured trials, retained failures, runtime/resource distributions, estimator-output repeatability, and independent verifier recomputation.

### Implemented

- added `run_evalio_repeated_benchmark` as the repeated-run orchestration path;
- warmups are explicit evidence under `warmups/` but never contribute to `manifest.trial_count` or measured statistics;
- measured execution failures are retained as failed trial records instead of disappearing from the run set;
- successful measured trials contribute scalar distributions with count/min/max/mean/median/population-std/p90/p95/p99;
- trajectory repeatability is computed over every measured trial pair at exact common timestamps with no hidden spatial alignment;
- repeatability uses the canonical serialized TUM payload representation, so producer and verifier operate on the same immutable evidence;
- verifier independently recomputes scalar metric/resource distributions and trajectory repeatability and rejects checksum-refreshed aggregate tampering;
- repeated-run environment metadata now records host-control declaration, CPU allocation, and thread policy;
- `controlled`/`publication` producer requests now fail before execution unless the declared environment satisfies the v0.1 controlled-host requirements that can be checked here: Linux, stable controlled-host declaration, explicit CPU allocation, explicit thread policy, recorded governor state, inspected local/controlled storage, known zero swap use, and BenchExec readiness;
- verifier applies the same controlled-host evidence checks so a bundle cannot be promoted merely by editing `measurement_class` and refreshing checksums.

### Real validation

Dataset/pipeline remained `hilti_2022/basement_2` + KISS-ICP 1.3.0 through evalio 0.6.1 and BenchExec `runexec 3.35`, using 120 LiDAR scans per execution.

The successful real validation workflow was GitHub Actions run `34889567816`. It performed one warmup execution, five measured executions, five successful measured trials, zero failed trials, and independent `lidarperf verify` before committing evidence.

The durable bundle is `docs/validation/step10_kiss_hilti_repeated.lperf/`.

The measured hosted-runner resource distribution is retained as integration evidence but is explicitly non-authoritative. Wall time across the five measured trials had mean `3.5721830594 s`, median `3.5747101960 s`, minimum `3.5140726920 s`, maximum `3.6202339240 s`, and population standard deviation `0.0419640896 s`. Mean CPU time was `4.4439166 s`; mean peak memory was `129227161.6 bytes`.

All five serialized estimator trajectories had identical timestamp sets and translation payloads. Across the 10 trial pairs, maximum pose translation delta was `0.0 m`; maximum pose rotation delta was approximately `2.41484e-06 deg`, with pairwise rotation RMSE approximately `8.39423e-07 deg`. This is integration evidence of extremely stable output for this short KISS/Hilti prefix, not a general determinism claim for KISS-ICP or LIO systems.

### Errors / bugs discovered and resolved

1. The first real repeated run (`34888575461`) failed bundle self-verification with `AGGREGATE_TRAJECTORY_REPEATABILITY_MISMATCH`. The producer had computed repeatability from higher-precision in-memory poses while the verifier recomputed from canonical TUM payloads whose pose scalars are serialized to 12 decimal places. Fix: canonicalize producer-side repeatability through serialize→parse before aggregation. Added a regression test demonstrating a sub-serialization-precision in-memory difference collapses in the actual immutable payload.
2. After the corrected real run passed, a specification audit caught a more important semantic error: five trials and genuine BenchExec accounting do **not** make an ordinary GitHub-hosted VM `controlled`. `SPEC.md` requires a stable self-hosted or otherwise controlled Linux machine plus additional host controls. The real bundle was therefore reclassified from `controlled` to `exploratory`, renamed from `step10_kiss_hilti_controlled.lperf` to `step10_kiss_hilti_repeated.lperf`, and its checksums were regenerated and independently verified.
3. A first attempt at the final semantic-cleanup workflow was invalid YAML and created no job; no source or evidence files were modified by that failed workflow. The cleanup was rerun through a temporary Python patch script and minimal workflow instead. This tooling failure is retained here as project history.

### Measurement-class conclusion

Trial count is necessary but not sufficient for measurement strength. A repeated run set may contain five or more measured trials and still be `exploratory` when host control cannot be established. This distinction is now enforced by both producer and verifier.

### Step 10 exit condition

Satisfied when the final PR matrix passes on Python 3.11/3.12/3.13, PR #11 is squash-merged, and post-merge `main` CI is green. Controlled real performance evidence is intentionally deferred until a stable controlled Linux benchmark host is available; it is not a blocker for Step 11 comparator development.

### Step 10 post-merge closure — 2026-09-14

- PR #11 was squash-merged as 79e6e840a68f6b8f4a8393bd39ddd2167143c6bf.
- Post-merge main CI run 34900803913 passed on Python 3.11, 3.12, and 3.13.
- Final validation before merge collected 134 tests; all 134 passed, Ruff passed, and the repeated bundle verified VALID.
- A final evidence-packaging trap was discovered after semantic cleanup: .lperf directories are gitignored, so renaming the validated controlled-named directory to the exploratory repeated name succeeded in the workflow worktree but git add -A recorded only the deletion. The already-successful bundle was restored from Git history, relabeled exploratory, checksums regenerated, independently verified, and force-added without rerunning the 6.3 GB Hilti download or estimator trials.
- Durable Step 10 evidence is docs/validation/step10_kiss_hilti_repeated.lperf/ and remains explicitly non-authoritative for performance because it was produced on an ordinary GitHub-hosted runner.
- Step 10 is complete. Step 11 comparator work is next; controlled real performance evidence is deferred until a stable controlled Linux host is available.


## Step 11 — semantic result comparison — 2026-09-15

### Normative basis

Step 11 implements SPEC.md sections 56–59 and the conservative default in section 77. Comparability is evaluated by dimension rather than reduced to one boolean. Unknown or unrecorded semantics are treated as `NOT COMPARABLE`, never guessed.

### Implemented

- added `src/lidarperf/comparison.py` and `lidarperf compare BASELINE CANDIDATE`;
- both bundles are independently verified before comparison, so edited checksums/metadata cannot be used as trusted comparison inputs when bundle invariants fail;
- accuracy comparability checks track, temporal estimator semantics, runtime sensor policy, exact dataset fingerprint, ground-truth fingerprint, evaluation frame, timestamp association, benchmark/dataset-owned preprocessing semantics, and trajectory metric semantics;
- performance comparability additionally checks timing scope, measurement class, host fingerprint, explicit same physical benchmark-host identity, controlled-host declaration, CPU allocation, thread policy, cache policy, benchmark backend/version, software environment, and explicit performance authority;
- `host_sha256` is not treated as proof of same physical host. Strict regression performance requires an explicit `benchmark_host_id` plus a controlled host mode. This prevents two nominally identical ephemeral cloud machines from being silently treated as one host;
- source-code regression comparability additionally requires the same method family/repository, exact resolved protocol, compatible config/build/dependency declarations, and repeated paired execution with an explicit shared `pairing_id`;
- intentional `config`, `build_environment`, and `dependencies` differences may be declared explicitly. Undeclared differences remain visible and can block regression comparability;
- common numeric accuracy/resource fields are reported as baseline, candidate, absolute delta, and relative-percent delta. Repeated-run aggregates use their median (mean fallback); single-trial aggregates use their direct scalar values;
- a comparison can therefore report useful descriptive deltas while simultaneously refusing a strict performance ranking.

### Real validation result

The first durable comparison is `docs/validation/step11_compare_step9_step10.json`, produced from the already-verified real Step 9 and Step 10 KISS-ICP/Hilti bundles. The result is:

- accuracy comparable: **true**;
- performance comparable: **false**;
- performance authoritative: **false**;
- regression comparable: **false**.

This is the intended result. Both bundles use compatible dataset/reference/trajectory semantics, so their accuracy outputs can be compared. Their hosted performance evidence is not a strict regression baseline because ordinary GitHub-hosted execution does not establish stable physical-host identity, explicit controlled CPU allocation, paired execution, or authoritative performance status. LidarPerf still exposes the measured wall/CPU/memory changes but refuses to rank them.

### Failures and fixes retained as project history

1. Initial PR #12 CI run `35010546182` stopped at Ruff before behavioral tests. It found one Typer mutable/list-option lint issue and five line-length/style issues. No comparator behavior failed in that run.
2. Temporary formatting workflow run `35010699412` reformatted the source but still stopped on B008 because changing the list default from `[]` to `None` did not address the repository's preferred Typer declaration style. The permanent fix uses `typing.Annotated[...]` with `typer.Option`, matching existing CLI code.
3. A subsequent temporary patch workflow contained a missing comma in its inline Python and failed before touching product code (`35010877609`).
4. The next patch attempt used an indentation-sensitive textual anchor and failed to find the CLI option block (`35010947453`). This reinforced the decision to stop using brittle text anchors for the permanent CLI change and patch the source directly.
5. Once tests actually ran, validation run `35011099965` produced 138 passes and three failures. Two exposed a real comparator bug: Step 9 single-trial `aggregate.json` stores metric scalars directly under `metrics`, while Step 10 repeated-run aggregates store distributions under `metrics.trial_metrics`/`metrics.resources`; the initial reader assumed only the repeated layout, hiding Step 9 metric/resource deltas. The reader now supports both schemas and falls back to per-trial resources when necessary.
6. The third behavioral failure was a bad test construction, not a verifier defect: the test changed only `method.config_sha256`, so `verify_bundle` correctly rejected it with `CONFIG_HASH_MISMATCH`. The test now changes the actual algorithm YAML, recomputes the semantic canonical config fingerprint, refreshes payload checksums, and thereby exercises a legitimate declared configuration difference without weakening verification.
7. Repair validation run `35011310594` passed Ruff, the full 141-test suite, and the real Step 9→Step 10 CLI comparison. Temporary repair workflow/script were removed in the same successful commit.

### Step 11 exit condition

Step 11 is complete when the durable comparison report and documentation are committed, the exact final PR head passes Python 3.11/3.12/3.13 CI, PR #12 is squash-merged, and post-merge `main` CI is green. Step 12 then builds the regression decision engine on top of this comparator rather than duplicating comparability logic.

8. Finalize workflow run `35011531083` generated the comparison evidence and documentation successfully, but its validation step failed because `ruff check .` also linted the temporary documentation patcher and reported long string literals. No permanent closure changes were committed by that failed run. The corrected closure removes temporary scaffolding before linting the permanent tree.

### Step 11 post-merge closure — 2026-09-15

- PR #12 (`feat: add semantic result comparator`) was squash-merged as `97fcaf90478bac8b19486c1697aefccd62057946`.
- Exact final PR head `0825eeca2bcb537157dd7a1def917eab3e787a75` passed CI run `35011827443` on Python 3.11, 3.12, and 3.13.
- Post-merge `main` CI run `35011938896` passed on Python 3.11, 3.12, and 3.13.
- Final Step 11 validation contains 141 passing tests, green Ruff, successful real Step 9 → Step 10 CLI comparison, and durable `docs/validation/step11_compare_step9_step10.json` evidence.
- Step 11 is complete. Step 12 is the regression decision engine: baseline/candidate paired experiments, accuracy/correctness gates, thresholds/uncertainty, and PASS/FAIL/INCONCLUSIVE decisions built on the Step 11 comparator rather than duplicated comparability rules.

---

## README validation visual — 15 September 2026

A documentation mini-step after Step 11 added a README-facing visual summary of the durable Step 9–11 evidence.

- PR #13 (`docs: add README validation snapshot`) was squash-merged as `aa6236bb8662ecd4e1d653a0da3c3b4933021d0f`.
- Added `docs/validation/lidarperf_validation_snapshot.svg` and embedded it in the main README.
- The visual reports the real committed KISS-ICP/Hilti evidence: Step 9/10 APE translation RMSE ≈ 0.3375 m, rotation RMSE ≈ 47.90° (known short-prefix caveat), Step 10 5/5 measured trials successful, zero pairwise translation repeatability RMSE, and 3.5747 s median hosted wall time.
- The presentation explicitly preserves Step 11 semantics: accuracy comparable = yes; strict performance comparable = no; performance authoritative = no; regression comparable = no.
- Hosted timing remains labeled descriptive-only; the visual does not promote GitHub-hosted measurements into authoritative performance claims.
- PR #13 CI and post-merge `main` CI both passed Python 3.11/3.12/3.13.
- The first history-closure workflow attempt used an unsafe heredoc/YAML layout: its workspace append step ran, but the intended commit step was not parsed/executed. No project file was changed by that failed closure attempt; this replacement workflow fixes the tooling mistake and removes itself.

This visual is presentation derived from existing durable evidence, not a new benchmark result.
