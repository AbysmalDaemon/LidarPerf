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
