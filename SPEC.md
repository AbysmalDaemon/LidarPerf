# LidarPerf Benchmark Specification

**Document:** `SPEC.md`  
**Specification version:** `0.1.0`  
**Date:** 2026-09-14  
**Status:** Approved for implementation — Gate 1 approved 2026-09-14.  
**Project:** LidarPerf

---

## 0. Executive decision

LidarPerf is **not** a generic LiDAR odometry benchmark suite.

LidarPerf is a **conformance, provenance, repeatability, comparability, and performance-regression framework** for LiDAR odometry software.

Its central question is:

> Given two LiDAR-odometry results, can we establish that they were produced under sufficiently equivalent declared conditions, that both estimators remained valid and accurate, and that an observed performance change is a defensible improvement or regression rather than an artifact of different inputs, preprocessing, measurement boundaries, hardware, or run-to-run noise?

This specification deliberately prioritizes **meaningful comparisons over permissive comparisons**. When LidarPerf cannot establish comparability, it MUST say so instead of silently producing a ranking.

---

# 1. Normative language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

- **MUST / REQUIRED**: necessary for conformance.
- **SHOULD**: strongly recommended; deviations require a recorded reason.
- **MAY**: optional.

A LidarPerf result MUST declare the specification/protocol version against which it was produced.

---

# 2. Goals

LidarPerf v0.1 has seven primary goals.

1. **Conformance**  
   Verify that an experiment obeyed its declared sensor, preprocessing, evaluation, and execution rules.

2. **Provenance**  
   Record enough information to determine what data, software, configuration, build, environment, and hardware generated a result.

3. **Correctness before speed**  
   A broken estimator MUST NOT be reported as a performance improvement merely because it executes faster.

4. **Repeatability**  
   Multiple executions of nominally identical experiments MUST be representable and their variation MUST be measurable.

5. **Semantic comparability**  
   LidarPerf MUST distinguish “numbers can be displayed together” from “numbers are scientifically comparable.”

6. **Performance regression testing**  
   Baseline/candidate comparisons SHOULD support controlled, repeated, paired execution and practical regression thresholds.

7. **Interoperability**  
   LidarPerf SHOULD reuse existing algorithm/dataset/execution infrastructure rather than becoming another estimator zoo.

---

# 3. Non-goals for v0.1

LidarPerf v0.1 will not attempt to provide:

- a new SLAM algorithm
- a new ICP/GICP implementation
- a generic point-cloud processing library
- a generic dataset-loader ecosystem
- a ROS bag implementation
- a replacement for evalio
- a replacement for evo
- a replacement for BenchExec
- a replacement for ros2_tracing
- a benchmark SaaS / hosted database
- a universal public leaderboard
- a GPU-performance standard
- energy benchmarking
- visual odometry / camera benchmarking
- radar odometry
- semantic mapping
- loop-closure benchmarking
- pairwise registration benchmarking

Those may become separate future protocol families, but they are intentionally outside the first implementation.

---

# 4. Evidence and design basis

This specification is informed by the following external work.

## 4.1 evalio

`evalio` already supplies a common LiDAR/LIO data and pipeline interface, dataset management, normalized scan representation, CLI execution, and trajectory statistics.

LidarPerf therefore treats evalio as an **execution/data backend**, not functionality to reimplement.

Reference:

- https://github.com/contagon/evalio

Important implementation observation discovered during specification research:

- evalio's current trajectory alignment implementation spatially aligns the estimate to the **first pose** of the other trajectory.
- this is not semantically identical to a full-trajectory SE(3) Umeyama alignment used by tools such as evo for APE.

Therefore LidarPerf MUST NOT silently reuse a metric merely because two tools call it “ATE.” Metric semantics must be defined by the LidarPerf protocol and validated independently.

## 4.2 KITTI odometry protocol

The official KITTI odometry benchmark computes translational and rotational errors over all possible subsequences of lengths 100–800 m and reports translation in percent and rotation in degrees per metre.

Reference:

- https://www.cvlibs.net/datasets/kitti/eval_odometry.php

LidarPerf will eventually implement a separately versioned KITTI-compatible profile. It will not pretend that generic APE/RPE is “the KITTI metric.”

## 4.3 Quantitative trajectory evaluation

Zhang and Scaramuzza describe trajectory alignment, ATE/APE, and relative errors and emphasize that alignment semantics depend on the sensing modality.

Reference:

- https://rpg.ifi.uzh.ch/docs/IROS18_Zhang.pdf
- DOI: 10.1109/IROS.2018.8593941

LidarPerf therefore makes alignment a protocol field rather than an implicit evaluator option.

## 4.4 Reliable benchmarking / BenchExec

Reliable resource measurement requires careful process accounting, monotonic timing, child-process accounting, CPU/memory constraints, and isolation. BenchExec already provides Linux cgroup-based execution and process-tree measurements.

References:

- https://github.com/sosy-lab/benchexec
- https://www.sosy-lab.org/research/benchmarking/

LidarPerf SHOULD use BenchExec/runexec for benchmark-grade Linux process-level measurements rather than implement its own cgroup monitor.

## 4.5 Stable performance measurement

`pyperf` documents the impact of CPU affinity, CPU isolation, governor state, system load, and machine metadata on benchmark stability.

References:

- https://pyperf.readthedocs.io/en/latest/system.html
- https://pyperf.readthedocs.io/en/latest/cli.html

LidarPerf therefore records and grades benchmark-host state rather than treating all runs as equally authoritative.

## 4.6 LIO non-reproducibility

Recent LIO research demonstrates noteworthy run-to-run non-reproducibility caused by nondeterministic implementations under nominally constant conditions.

Reference:

- “Unveiling Non-Reproducibility in LiDAR-Inertial Odometry”
- IEEE Robotics and Automation Letters, Vol. 11, Issue 1
- DOI: 10.1109/LRA.2025.3636030
- https://ieeexplore.ieee.org/document/11266943/

LidarPerf therefore treats repeated execution and estimator-output variability as first-class data.

## 4.7 RobotPerf

RobotPerf demonstrates the importance of vendor-neutral, reproducible robotics-computing benchmarks and explicitly distinguishes robotics performance benchmarking from algorithm-development work.

Reference:

- https://github.com/robotperf/benchmarks
- https://robotperf.github.io/

---

# 5. Fundamental entities

LidarPerf uses the following entities.

## 5.1 Protocol

A **protocol** is the complete set of rules that determines:

- allowed sensors
- estimator class
- causal semantics
- input/preprocessing semantics
- evaluation frame
- trajectory association
- trajectory metrics
- validity gates
- timing scope
- measurement profile
- repetition policy
- tuning policy

A protocol is **immutable once released**.

A behavioral change requires a new protocol version.

## 5.2 Method

A **method** is the estimator implementation being evaluated.

It includes:

- name
- upstream repository
- version/tag
- commit SHA where available
- build provenance
- runtime dependencies
- algorithm configuration
- patches / dirty-source state

## 5.3 Dataset sequence

A **dataset sequence** is the exact sensor-data input and associated reference trajectory used for an experiment.

It MUST have a stable fingerprint.

## 5.4 Trial

A **trial** is one execution of one method/configuration on one dataset sequence under one execution environment.

## 5.5 Run set

A **run set** is one or more trials that intentionally represent the same experiment, generally for repeatability/performance statistics.

## 5.6 Result bundle

A **result bundle** is the immutable LidarPerf artifact containing the protocol, provenance, per-trial outputs, aggregate metrics, logs, and checksums.

## 5.7 Comparison

A **comparison** places result bundles side by side after evaluating which dimensions are semantically comparable.

## 5.8 Regression experiment

A **regression experiment** is a controlled baseline/candidate comparison of the same method where differences are explicitly declared and accuracy validity is checked before performance conclusions are permitted.

---

# 6. Protocol identity and versioning

Each released protocol MUST have:

```yaml
protocol:
  id: lidarperf/lo-se3
  version: 1
```

The fully resolved protocol MUST also receive a canonical SHA-256 content fingerprint.

Example:

```yaml
protocol:
  id: lidarperf/lo-se3
  version: 1
  resolved_sha256: "..."
```

The human-readable ID/version is for communication.

The resolved hash is the authoritative check that two result bundles used semantically identical protocol content.

A released protocol MUST NOT be edited in a way that changes behavior.

Editorial corrections that do not alter semantics MAY retain the protocol version, but the repository history MUST retain the change.

---

# 7. Supported benchmark tracks in v0.1

v0.1 officially supports only two estimator tracks.

## 7.1 LO — LiDAR Odometry

Allowed runtime information:

- LiDAR geometry
- LiDAR intensity where provided
- LiDAR ring/channel identifiers
- LiDAR point timestamps
- static sensor calibration
- static sensor intrinsics/extrinsics
- declared algorithm constants/configuration

Forbidden runtime information:

- IMU measurements
- camera images/features
- wheel odometry
- GNSS/GPS
- magnetometer
- external localization
- a prebuilt map of the evaluation environment
- ground truth
- undeclared precomputed motion estimates

Use of a forbidden source makes the result **non-conformant for the LO track**.

## 7.2 LIO — LiDAR-Inertial Odometry

Allowed runtime information:

- everything permitted by LO
- IMU angular velocity
- IMU linear acceleration
- static LiDAR↔IMU calibration

Forbidden runtime information:

- camera observations
- wheel odometry
- GNSS/GPS
- magnetometer unless a future protocol explicitly permits it
- external localization
- prebuilt environment map
- ground truth

Use of forbidden information makes the result **non-conformant for the LIO track**.

---

# 8. Deferred tracks

The schema MAY reserve values for:

- `slam`
- `registration`

but v0.1 MUST NOT produce an “official/controlled” LidarPerf verdict for those tracks.

The reason is methodological: loop closure/global optimization and pairwise registration solve materially different problems from local odometry.

---

# 9. Online / fixed-lag / offline semantics

The estimator MUST declare one of:

```yaml
estimator_semantics:
  temporal_mode: online_causal
```

```yaml
estimator_semantics:
  temporal_mode: online_fixed_lag
  fixed_lag_seconds: 1.0
```

```yaml
estimator_semantics:
  temporal_mode: offline_noncausal
```

## 9.1 `online_causal`

The estimate at time `t` does not depend on sensor observations after `t`.

## 9.2 `online_fixed_lag`

The estimator may revise recent states using observations inside a bounded, declared lag.

Fixed-lag smoothing is permitted in LO/LIO and is not considered loop closure.

## 9.3 `offline_noncausal`

The estimate may depend on future observations or the full sequence.

Offline results MAY be evaluated for accuracy but MUST NOT make a strict “real-time odometry” claim against online estimators without explicit labeling.

Strict comparisons MUST require compatible temporal modes, unless the comparison is intentionally exploratory.

---

# 10. Loop-closure rule

LO/LIO protocols MUST NOT use nonlocal loop closure, place recognition, or global re-optimization based on revisiting a previously seen distant region.

A fixed-lag smoother is allowed if its lag is declared.

If nonlocal loop closure is enabled, the run is outside the official v0.1 LO/LIO tracks.

---

# 11. Canonical coordinate convention

LidarPerf MUST use a single internal pose convention.

The canonical pose is:

> `T_W_B`

where `T_W_B` transforms a point expressed in body frame `B` into world/reference frame `W`.

For a point `p_B`:

```text
p_W = R_W_B * p_B + t_W_B
```

Requirements:

- right-handed coordinates
- translation in metres
- rotation in SO(3)
- internal timestamps as signed 64-bit integer nanoseconds
- serialized quaternions, when used, MUST be `[x, y, z, w]`
- all external formats MUST be converted explicitly into this canonical convention

Adapters MUST document source conventions.

A pose-direction ambiguity MUST be treated as a validation failure, not guessed.

---

# 12. Evaluation body frame

Every trajectory MUST declare the physical frame whose pose it represents.

Examples:

- LiDAR frame
- IMU frame
- vehicle/base frame

A protocol MUST declare an `evaluation_frame`.

If estimate and ground truth are in different body frames:

- a fixed, declared extrinsic transform MUST be available, or
- the trajectories are not strictly comparable.

The applied extrinsic MUST be fingerprinted and stored.

---

# 13. Time semantics

Every sensor stream MUST declare:

- source time unit
- source time base
- scan timestamp reference
- whether per-point timestamps exist
- whether timestamps were reconstructed

LiDAR scan timestamp reference MUST be one of:

```text
scan_start
scan_mid
scan_end
unknown
```

`unknown` is allowed for import, but a protocol MAY reject it.

If per-point timestamps are synthesized or reconstructed, the reconstruction rule MUST be recorded.

---

# 14. Trajectory timestamp association

Timestamp association is part of the protocol.

Allowed modes in v0.1:

```text
exact
nearest
interpolate_reference
```

## 14.1 `exact`

Estimate/reference timestamps must match exactly after time-base normalization.

## 14.2 `nearest`

Reference poses are matched to estimate timestamps by nearest neighbor subject to an explicit maximum temporal difference.

## 14.3 `interpolate_reference`

The reference trajectory is interpolated to estimator timestamps.

Translation interpolation:

- linear interpolation

Rotation interpolation:

- quaternion SLERP

Rules:

- extrapolation outside reference support is forbidden
- maximum reference bracketing gap MUST be specified
- unmatched estimator poses remain unmatched
- association statistics MUST be reported

There is deliberately **no hidden universal tolerance**.

The protocol/dataset profile MUST state it.

---

# 15. Preprocessing declaration

Preprocessing is part of the experiment.

Every relevant stage MUST declare an owner:

```text
dataset
benchmark
algorithm
none
```

The following fields are included in the v0.1 model:

- coordinate transform
- deskew / motion compensation
- voxel downsampling
- crop / ROI
- minimum range
- maximum range
- statistical/radius filtering
- ground removal
- intensity filtering
- timestamp reconstruction
- point reordering
- duplicate removal

Example:

```yaml
preprocessing:
  deskew:
    owner: algorithm
    input_already_deskewed: false

  voxel_downsample:
    owner: algorithm

  crop:
    owner: none
```

A preprocessing operation that materially affects the estimator input MUST NOT occur without being declared.

---

# 16. Deskew / motion-compensation semantics

Deskewing requires explicit treatment because benchmark fairness can depend on whether a dataset is already motion-corrected.

A run MUST declare:

```yaml
motion_compensation:
  input_state: raw | pre_deskewed | unknown
  performed_by: dataset | benchmark | algorithm | none
  motion_source: none | constant_velocity | imu | other
```

Strict comparison requires compatible **benchmark-owned/dataset-owned** input semantics.

Algorithm-owned internal deskewing may differ between algorithms; that is considered part of the method.

---

# 17. Tuning policy

Every result MUST declare one tuning class.

## 17.1 `frozen`

One configuration is used across the declared benchmark suite.

## 17.2 `dataset`

One configuration may be selected per dataset, but not per sequence.

## 17.3 `sequence`

Configuration may be changed per sequence.

Results from different tuning classes MAY be shown together, but strict ranking MUST flag the difference.

A public benchmark SHOULD prefer `frozen` unless the protocol explicitly studies tuning sensitivity.

The tuning source SHOULD also be recorded:

```text
upstream_default
upstream_recommended
author_provided
benchmark_tuned
custom
```

---

# 18. Method configuration fingerprint

All estimator configuration that can affect results MUST be captured.

The canonicalized configuration MUST be hashed with SHA-256.

Canonicalization MUST:

- sort mapping keys
- preserve array order
- normalize scalar types
- encode UTF-8
- avoid nondeterministic serialization

The bundle stores both:

- human-readable configuration
- configuration SHA-256

---

# 19. Source-code provenance

Where source provenance is available, the method record SHOULD include:

```yaml
source:
  repository: https://github.com/...
  commit: ...
  tag: ...
  dirty: false
```

If the worktree is dirty:

```yaml
source:
  dirty: true
  patch_sha256: ...
```

For publication-grade open-source results, the exact patch SHOULD be archived where licensing permits.

For binary-only or proprietary methods, the bundle MUST state that exact source reproduction is unavailable.

---

# 20. Build provenance

Where applicable, record:

- compiler
- compiler version
- build type
- relevant compile flags
- architecture flags
- Python version
- dependency-lock hash
- CUDA version
- cuDNN version
- container image digest
- package versions

A baseline/candidate regression experiment MUST flag unexpected build/dependency changes.

---

# 21. Dataset fingerprint

A dataset sequence MUST be fingerprinted.

The v0.1 preferred exact fingerprint is:
1. enumerate all input files used by the sequence
2. use normalized relative paths
3. record file size
4. compute SHA-256 for each file
5. sort manifest entries by normalized path
6. SHA-256 hash the canonical manifest

Example conceptual record:

```yaml
dataset:
  id: boreas/glen/...
  provider: boreas
  sequence: ...
  content_sha256: ...
  manifest_sha256: ...
```

Hash results MAY be cached locally because large datasets are expensive to rehash.

If an adapter cannot provide exact input hashes, it MUST report a weaker fingerprint class and the result cannot receive the strongest reproducibility grade.

---

# 22. Ground-truth provenance

Ground truth MUST be treated as an independent input.

Record:

- source/provider
- reference frame
- timestamp semantics
- file/content fingerprint
- any interpolation
- any conversion
- any calibration/extrinsic applied

Ground truth MUST NOT be available to the estimator process unless explicitly required for a non-odometry experiment, in which case the run is not an official LO/LIO result.

---

# 23. Trajectory validity

Before accuracy is computed, trajectory structural validity MUST be checked.

Checks include:

- parse success
- finite translations
- valid rotations
- no NaN/Inf
- monotonically increasing timestamps unless the format explicitly permits otherwise
- declared pose convention
- declared body frame
- nonempty trajectory
- temporal overlap with reference

Invalid poses MUST be counted and reported.

They MUST NOT simply be dropped without disclosure.

---

# 24. Completion and coverage

Each run MUST report at least:

- sensor sequence start/end
- estimator trajectory start/end
- expected LiDAR scan count when available
- consumed scan count when observable
- emitted pose count
- matched pose count
- temporal coverage
- distance coverage where reference distance is available
- invalid pose count
- process exit code
- timeout status

## 24.1 Coverage

Coverage uses three distinct temporal supports when the benchmarked sensor interval and
available reference trajectory are not identical:

- **input support** — the sensor-time interval the estimator was asked to process;
- **reference support** — the time interval for which ground truth exists;
- **evaluable support** — `input support ∩ reference support`.

For trajectory accuracy evaluation, temporal coverage is measured over the evaluable
support, not over an unrelated full ground-truth file and not over sensor time for which
no reference exists. Distance coverage is likewise measured against reference path length
inside the evaluable support.

If explicit input support is supplied and it differs from reference support, the result
MUST disclose both intervals and the derived evaluable support. Restricting accuracy
metrics to their intersection MUST NOT erase or disguise missing reference data outside
that intersection. If the intersection is empty, trajectory accuracy cannot be evaluated.

Estimator completion over the requested input and reference availability are separate
facts. Input scan counts, consumed scans, emitted poses, trajectory start/end, and the
three support intervals MUST remain available so a high accuracy-coverage value cannot be
misread as proof that ground truth covered every requested sensor instant.

The default v0.1 conformance recommendation is:

```text
temporal coverage >= 98%
```

This is a **default recommendation**, not a universal scientific law.

A protocol MAY use another threshold, but it MUST be explicit.

An estimator with lower evaluable coverage MUST NOT receive a normal accuracy/performance
“pass” simply because its successful subset is easy.

---

# 25. Accuracy evaluation profiles

Metric names MUST include their semantics.

LidarPerf MUST NOT store a naked field named merely `ATE` or `RPE` without alignment/window semantics.

---

# 26. Generic metric LiDAR profile

The first generic profile is intended for metric-scale LiDAR odometry.

Scale correction is forbidden.

## 26.1 APE translation

Recommended canonical output:

```text
ape.translation.rmse_m
```

Alignment:

- full-trajectory rigid SE(3) alignment
- no scale correction

The alignment transform MUST be stored.

This metric measures global trajectory shape/consistency after removing an arbitrary rigid world-frame offset.

## 26.2 APE rotation

Recommended output:

```text
ape.rotation.rmse_deg
```

with the same SE(3) alignment policy.

## 26.3 Relative pose error

RPE MUST use explicitly declared windows.

Distance-window examples:

```text
10 m
100 m
```

Each distance window MUST declare both its pairing rule and tolerance. The v0.1 generic
profile supports:

```yaml
relative_error_windows:
  - distance_m: 10.0
    pairing: all_starts_nearest_reference_distance
    relative_tolerance: 0.1
```

For `all_starts_nearest_reference_distance`:

1. cumulative path length is computed from the associated **reference** trajectory;
2. every associated reference pose is considered as a possible start;
3. the later endpoint whose reference path distance is closest to `distance_m` is chosen;
4. ties choose the earlier endpoint;
5. the pair is accepted only when
   `abs(actual_distance_m - distance_m) <= distance_m * relative_tolerance`;
6. overlapping windows are allowed;
7. the actual accepted reference distance distribution and pair count MUST be reported.

If no accepted pair exists for a requested window, that metric is unavailable. LidarPerf
MUST NOT fabricate a zero error.

Outputs SHOULD include:

- translational relative error in metres
- rotational relative error in degrees
- normalized translation %
- normalized rotation deg/m

The reference trajectory defines path-length windows. Pairing and tolerance are protocol
data and therefore participate in the protocol fingerprint.

---

# 27. KITTI-compatible profile

A separate protocol profile will reproduce the official KITTI odometry development-kit semantics.

It MUST:

- use segment lengths 100, 200, 300, 400, 500, 600, 700, 800 m
- report translational error in percent
- report rotational error in degrees per metre
- preserve the official sequence/segment aggregation semantics
- be golden-tested against the official development kit

It MUST NOT be implemented as an alias for generic APE/RPE.

---

# 28. Scale correction

For LO/LIO metric trajectories:

> Sim(3) / free scale correction is forbidden in official v0.1 protocols.

If scale correction is requested, the result becomes exploratory/non-conformant for the standard LO/LIO protocol.

LiDAR and LiDAR-inertial estimators are metric systems; silently correcting scale would conceal estimator error.

---

# 29. Timing scopes

LidarPerf recognizes three timing scopes.

## 29.1 `compute`

Boundary:

> normalized estimator input is available → estimator output for that input is available

Includes:

- estimator-internal preprocessing
- state estimation
- map update performed by the method

Excludes:

- dataset file decoding
- benchmark-owned preprocessing
- process startup
- final report serialization

Requirement:

- MUST be instrumented
- MUST NOT be inferred from opaque process wall time

## 29.2 `pipeline`

Boundary:

> decoded benchmark input is handed to the benchmark/algorithm pipeline → estimator output is produced

Includes:

- benchmark-owned preprocessing
- algorithm preprocessing
- estimation
- algorithm map update

Excludes:

- dataset disk I/O/decompression before handoff
- process/container startup

Requires an instrumented backend.

## 29.3 `end_to_end`

Boundary:

> benchmarked process starts → benchmarked process exits after producing its declared outputs

Includes:

- initialization
- file I/O
- dataset decoding
- preprocessing
- estimation
- output serialization

This is the default authoritative timing scope for an opaque command/Docker backend.

---

# 30. Timing-clock requirement

Wall-time measurement MUST use a monotonic clock or a benchmarking backend that guarantees appropriate monotonic measurement.

Naive subtraction of wall-clock calendar timestamps is not benchmark-grade.

---

# 31. Process accounting

On Linux, controlled process-level measurements SHOULD use BenchExec/runexec.

At minimum record:

- wall time
- total CPU time including child processes
- maximum resident memory / equivalent BenchExec memory metric
- exit status
- timeout
- CPU allocation

LidarPerf MUST NOT claim authoritative process-tree CPU/memory measurements from a simplistic single-parent `psutil` loop when BenchExec is available.

---

# 32. Core performance metrics

For process-level runs v0.1 SHOULD report:

```text
wall_time_s
cpu_time_s
peak_memory_bytes
sequence_duration_s
processing_ratio
speed_factor
```

Definitions:

```text
processing_ratio = wall_time_s / sequence_duration_s
```

Less than `1.0` means the whole measured scope completed faster than sensor playback duration.

```text
speed_factor = sequence_duration_s / wall_time_s
```

Greater than `1.0` means faster than real time.

LidarPerf avoids an unlabeled “RTF” field because conventions differ.

---

# 33. CPU utilization normalization

Where sufficient data exists:

```text
cpu_core_equivalents = cpu_time_s / wall_time_s
```

If `N` logical CPUs are allocated:

```text
allocated_cpu_utilization_percent =
    100 * cpu_core_equivalents / N
```

Both the raw CPU time and normalization denominator MUST be preserved.

---

# 34. Per-frame latency

Per-frame/input-to-output latency MUST NOT be fabricated for opaque binaries.

It may only be reported when the backend can identify both input and corresponding output events.

Potential future/instrumented sources include:

- direct Python/C++ benchmark callbacks
- evalio hooks where semantics are clear
- ROS 2 tracing

If unavailable:

```text
per_frame_latency: unavailable
```

is correct behavior.

---

# 35. GPU metrics in v0.1

GPU telemetry is not required for the first controlled CPU-oriented release.

A method that materially uses a GPU MAY be executed, but v0.1 MUST label GPU performance results as:

```text
experimental
```

until a GPU measurement protocol is defined.

Accuracy results remain valid if the estimator otherwise conforms.

---

# 36. Host fingerprint

A result SHOULD record as much as available from:

## CPU

- vendor/model
- architecture
- sockets
- physical cores
- logical CPUs
- assigned CPU set
- SMT state if discoverable
- scaling driver
- governor
- frequency policy

## Memory

- total RAM
- NUMA topology
- assigned NUMA nodes where controlled
- swap state/activity

## Operating system

- distribution
- version
- kernel
- libc where relevant

## Storage

- input path filesystem/device metadata where available
- local vs network filesystem

## GPU

- model
- driver
- CUDA runtime/toolkit where relevant

## Runtime conditions

- system load
- runnable task count where available
- thermal throttling indicators where available
- power source where relevant

---

# 37. `lidarperf doctor`

`lidarperf doctor` MUST inspect the host and produce:

- machine metadata
- warnings
- capability availability
- benchmark measurement class eligibility

The command SHOULD warn about:

- powersave governor
- unrestricted CPU affinity
- missing cgroups
- missing BenchExec
- elevated background load
- swap activity
- network-mounted dataset
- thermal throttling
- missing exact software provenance

v0.1 SHOULD **not automatically reconfigure the host by default**.

A future opt-in tuning command may be considered separately.

---

# 38. Measurement classes

Every result MUST declare a measurement class.

## 38.1 `exploratory`

Minimum:

- execution completed
- protocol metadata captured
- host information captured where possible

May use:

- one trial
- uncontrolled host
- macOS/Windows
- ordinary GitHub-hosted runner
- non-BenchExec resource measurement

Exploratory results MUST NOT be labeled authoritative performance regressions.

## 38.2 `controlled`

Requirements:

- Linux
- stable self-hosted or otherwise controlled machine
- BenchExec/runexec for process-level timing where applicable
- explicit CPU allocation
- explicit thread policy
- governor state recorded
- same dataset fingerprint
- exact protocol fingerprint
- local or explicitly controlled storage
- at least **5 measured trials** for performance comparison
- run-to-run data retained
- no known swap pressure
- no unexplained host/config change between compared results

Controlled results MAY support regression conclusions.

## 38.3 `publication`

Recommended requirements:

- all controlled requirements
- dedicated/bare-metal or equivalently characterized host
- at least **10 measured trials**
- baseline/candidate paired blocked execution for regression studies
- predeclared experiment plan
- stable software environment
- system-load/thermal observations retained
- all failed trials retained
- exclusions documented
- raw result bundles archived

Publication class is deliberately demanding.

---

# 39. Thread policy

The experiment MUST declare its thread policy.

Examples:

```yaml
resources:
  cpu_set: [4, 5, 6, 7]
  logical_cpu_count: 4
  thread_policy:
    mode: fixed
    requested_threads: 4
```

Where relevant, adapters SHOULD record environment settings such as:

- `OMP_NUM_THREADS`
- `MKL_NUM_THREADS`
- `OPENBLAS_NUM_THREADS`

CPU-set restriction SHOULD be enforced independently where possible.

A strict performance comparison MUST use compatible CPU allocation policies.

---

# 40. NUMA policy

On NUMA machines, controlled/publication results MUST record:

- CPU NUMA node allocation
- memory NUMA policy where observable

If baseline and candidate use different NUMA placement, strict performance-regression comparability fails.

---

# 41. Dataset I/O and cache policy

The experiment MUST declare:

```text
cache_policy:
  warm
  cold
  uncontrolled
  not_applicable
```

`cold` means the benchmark intentionally controls cold-cache conditions.

`warm` means data may already reside in operating-system cache and the experiment intentionally uses that state.

`uncontrolled` is permitted for exploratory runs only.

Strict end-to-end comparisons require compatible cache policies.

For `compute`/`pipeline` scopes where dataset disk I/O is outside the measured boundary, cache state may be `not_applicable`.

---

# 42. Warm-up policy

Warm-up is explicit.

Example:

```yaml
repetition:
  warmup_trials: 1
  measured_trials: 5
```

Warm-up trials MUST NOT be silently mixed with measured trials.

For full-sequence estimators, a protocol MAY specify zero warm-up if a full warm-up is prohibitively expensive, but this choice MUST be identical across strict comparisons.

---

# 43. Repetition policy

Minimum requirements:

- exploratory: `>= 1` measured trial
- controlled performance comparison: `>= 5`
- publication performance study: `>= 10`

All trials MUST be retained, including failures.

The aggregate MUST NOT hide failed trials by averaging only successful runs without disclosure.

---

# 44. Regression run ordering

For baseline/candidate performance regressions, the preferred controlled ordering is **paired blocked randomization**.

For each pair/block:

- randomly select `AB` or `BA`
- execute both on the same host session
- preserve order metadata

Example:

```text
pair 1: B A
pair 2: A B
pair 3: B A
...
```

This reduces bias from machine drift, temperature, cache/system-state trends, and background variation.

The random seed MUST be recorded.

---

# 45. Statistical summary

For repeated performance metrics, LidarPerf SHOULD report:

- count
- median
- mean
- standard deviation
- median absolute deviation where useful
- minimum
- maximum
- p25/p75
- a 95% confidence interval for the primary comparison statistic

Raw trial values MUST always remain available.

LidarPerf SHOULD prefer robust point estimates such as medians for noisy runtime distributions.

---

# 46. Regression effect size

For a paired baseline/candidate metric where lower is better:

```text
relative_change =
    (candidate - baseline) / baseline
```

For each pair, LidarPerf can calculate the paired ratio/change.

The regression report SHOULD include:

- median relative change
- confidence interval
- practical threshold
- direction of better/worse
- number of valid pairs

---

# 47. Practical threshold before “regression”

A performance regression verdict MUST have an explicit practical threshold.

Example:

```yaml
gate:
  performance:
    metric: wall_time_s
    max_regression_percent: 5
```

LidarPerf MUST NOT silently invent a universal 5% rule.

If no threshold is supplied:

- numeric differences MAY be reported
- a strict PASS/FAIL performance-regression verdict MUST NOT be produced

This avoids converting statistical noise or arbitrary tiny changes into scientific claims.

---

# 48. Accuracy gate before performance gate

`lidarperf regress` MUST evaluate in this order:

1. execution validity
2. structural output validity
3. sequence/trajectory coverage
4. accuracy gate
5. only then performance regression

Example:

```text
baseline:
  APE = 0.42 m
  wall = 37 s

candidate:
  APE = 87.3 m
  wall = 15 s
```

The candidate is:

```text
INVALID FOR PERFORMANCE IMPROVEMENT CLAIM
```

not “59% faster.”

---

# 49. Accuracy-gate policy

There is no universal v0.1 accuracy threshold.

The regression protocol MUST specify the acceptable accuracy change.

Supported conceptual gate types:

```text
absolute_max
relative_max_regression
non_inferiority_margin
multi_metric_all
```

Example:

```yaml
accuracy_gate:
  type: relative_max_regression
  metric: rpe.translation.100m.mean_percent
  max_regression_percent: 2.0
```

Research papers SHOULD justify their gate scientifically rather than relying on a package default.

---

# 50. Trial failure handling

A trial is marked failed if any REQUIRED condition fails, including:

- process crash
- timeout
- missing required output
- unparseable trajectory
- non-finite pose
- insufficient coverage
- conformance violation

A run set MUST report:

- successful trials
- failed trials
- failure reasons
- completion rate

A failure MUST NOT disappear from aggregate statistics.

---

# 51. Result bundle v1

The proposed canonical unarchived structure is:

```text
<result>.lperf/
│
├── manifest.json
├── protocol.yaml
├── method.json
├── dataset.json
├── environment.json
├── aggregate.json
│
├── config/
│   └── algorithm.yaml
│
├── trials/
│   ├── 0001/
│   │   ├── trial.json
│   │   ├── metrics.json
│   │   ├── resources.json
│   │   ├── trajectory.tum
│   │   ├── telemetry.parquet        # optional
│   │   └── process.log              # combined stdout + stderr
│   ├── 0002/
│   │   └── ...
│   └── ...
│
└── checksums.sha256
```

Each trial MUST contain exactly one execution-log layout:

- `process.log` when the execution backend exposes a single combined stdout/stderr stream; or
- both `stdout.log` and `stderr.log` when the backend can preserve the streams separately.

The two layouts are mutually exclusive. LidarPerf MUST NOT relabel a combined stream as stdout or fabricate an empty stderr file merely to satisfy an artifact shape. This rule preserves measurement provenance across backends such as BenchExec, whose `runexec --output` file contains both command stdout and stderr.

An archived transport format MAY be introduced later.

---

# 52. Bundle manifest

`manifest.json` MUST include at least:

- bundle schema version
- LidarPerf version
- protocol ID/version/hash
- result UUID
- creation timestamp
- track
- method identity
- dataset identity/fingerprint
- number of trials
- measurement class
- overall conformance status
- file inventory

---

# 53. Bundle checksums

`checksums.sha256` MUST contain SHA-256 checksums for every bundle payload file except the checksum file itself.

`lidarperf verify` MUST fail if:

- a required file is absent
- a checksum mismatches
- a schema fails
- the protocol cannot be resolved
- critical provenance is internally inconsistent

---

# 54. Immutability

A published result bundle is treated as immutable.

If an error is discovered:

- do not edit the original bundle silently
- generate a corrected bundle
- record supersession/retraction metadata
- preserve the original for audit when appropriate

This is essential for research traceability.

---

# 55. `lidarperf verify`

The verifier MUST distinguish:

```text
VALID
VALID WITH WARNINGS
INVALID
```

Example checks:

- schema validation
- checksum validity
- protocol hash
- config hash
- dataset fingerprint
- method provenance
- host metadata
- trajectory structure
- required metric presence
- conformance status
- trial-count consistency

Verification means:

> “This artifact is internally valid according to its declared LidarPerf protocol.”

It does **not** mean:

> “The estimator is scientifically good.”

---

# 56. Comparability dimensions

LidarPerf MUST evaluate comparability by dimension.

At minimum:

- track
- temporal estimator semantics
- sensor policy
- dataset identity/content
- ground-truth identity
- evaluation frame
- timestamp association
- benchmark-owned preprocessing
- trajectory metric protocol
- timing scope
- measurement class
- hardware
- CPU allocation
- cache policy
- repetition policy
- tuning class
- software environment

Comparability is not a single Boolean internally.

---

# 57. Accuracy comparability

Strict accuracy comparison requires:

- compatible track
- identical dataset sequence/fingerprint
- identical reference/ground-truth fingerprint
- identical evaluation frame semantics
- identical metric protocol
- compatible timestamp association
- compatible benchmark/dataset preprocessing semantics

Different algorithms MAY have different internal preprocessing.

That is part of the method.

---

# 58. Performance comparability

Strict performance comparison additionally requires:

- same timing scope
- compatible measurement class
- same physical benchmark host for regression studies
- same CPU allocation
- same thread policy
- same cache policy
- same benchmark backend semantics
- same input fingerprints
- no unexplained environment difference

Cross-machine numbers MAY be displayed but MUST be marked **not strict performance comparable** unless a future protocol explicitly supports hardware normalization.

---

# 59. Regression comparability

A strict source-code regression comparison requires:

- same method identity
- same dataset
- same protocol
- same config unless the config change is the declared subject
- same host
- same resource allocation
- same build environment except declared candidate differences
- same dependency set unless dependency change is the declared subject
- repeated paired execution

The result MUST enumerate observed baseline/candidate differences.

Unexpected differences should fail strict regression comparability.

---

# 60. `lidarperf compare`

The command MUST report both metrics and comparability.

Example:

```text
COMPARABILITY

Accuracy              YES
Performance           NO
Regression semantics  NO

Reasons:
✗ timing scopes differ
✗ CPU allocations differ
✓ dataset fingerprint identical
✓ accuracy protocol identical
```

The tool SHOULD refuse to produce a strict ranking from incomparable metrics.

An override MAY exist for exploratory analysis, but the output MUST retain a prominent warning.

---

# 61. `lidarperf regress`

The command MUST produce one of:

```text
PASS
FAIL_ACCURACY
FAIL_PERFORMANCE
FAIL_VALIDITY
INCONCLUSIVE
NOT_COMPARABLE
```

A result may also contain warnings.

`PASS` is only possible if every required correctness/accuracy gate passes before the performance gate.

---

# 62. Synthetic conformance fixture

LidarPerf MUST include a small deterministic fixture owned by the project.

Purpose:

- test pose conventions
- test timestamp handling
- test trajectory interpolation
- test APE/RPE implementation
- test bundle serialization
- test checksums
- test failure detection
- test comparability rules
- test regression logic

It is **not** intended to rank real estimators.

Suggested initial scene:

- ground plane
- orthogonal walls
- poles
- boxes
- 200–500 poses
- deterministic trajectory
- deterministic scan model
- deterministic noise option
- optional synthetic motion distortion

The exact ground-truth pose is known by construction.

---

# 63. Metric golden tests

Trajectory metrics MUST be tested against independent references.

Planned checks:

- synthetic analytically known transformations
- evo outputs for explicitly matched APE/RPE semantics
- official KITTI development kit for KITTI profile
- hand-computed minimal examples

A disagreement MUST be investigated.

LidarPerf MUST NOT simply choose whichever implementation produces the preferred number.

---

# 64. Backend model

v0.1 backend types:

```text
command
benchexec
evalio
docker
```

The backend MUST report its measurement capabilities.

Example:

```yaml
capabilities:
  process_wall_time: true
  process_cpu_time: true
  peak_memory: true
  per_frame_latency: false
  internal_phase_timing: false
```

A requested metric that the backend cannot validly measure MUST be marked unavailable rather than estimated.

---

# 65. evalio backend contract

The evalio backend will be used primarily for:

- dataset access
- normalized LiDAR/LIO streams
- running integrated pipelines
- obtaining estimator trajectories

LidarPerf remains responsible for:

- protocol resolution
- provenance
- conformance
- result bundle
- metric semantics chosen by LidarPerf
- repeatability orchestration
- performance measurement
- comparability
- regression verdicts

evalio metrics MAY be stored as external/reference metrics, but MUST NOT silently replace LidarPerf-defined metrics.

---

# 66. Docker semantics

Docker/container execution MUST record:

- image name
- immutable image digest
- entrypoint/command
- mounted dataset paths
- CPU allocation
- GPU access if any
- network setting
- relevant environment variables

Containerization does not make hardware identical.

Host provenance remains mandatory.

---

# 67. Network policy

Controlled/publication benchmark execution SHOULD not require network access once dependencies and datasets are prepared.

If runtime network access occurs, it MUST be declared.

A benchmark whose performance depends on remote services is outside the intended v0.1 authoritative model.

---

# 68. GitHub Actions policy

Ordinary GitHub-hosted runners MAY be used for:

- unit tests
- schema tests
- package tests
- synthetic conformance tests
- bundle verification
- CLI smoke tests

They MUST NOT be the default basis for authoritative fine-grained performance-regression claims.

Authoritative CI performance regression SHOULD use a stable self-hosted runner.

---

# 69. Performance-regression GitHub workflow

The intended future workflow is:

1. checkout/build baseline
2. checkout/build candidate
3. verify build provenance
4. run paired randomized benchmark trials on the same machine
5. validate both result bundles
6. apply accuracy gates
7. compare performance only if accuracy passes
8. publish PR summary
9. retain raw bundles as CI artifacts

Example summary:

```text
Accuracy
✓ gate passed

Validity
✓ baseline valid
✓ candidate valid
✓ 100% sequence coverage

Performance
median wall time    33.8 → 29.1 s   -13.9%
peak RSS             1.2 → 1.1 GB   -8.3%

Repeatability
✓ within declared bounds

PASS
```

---

# 70. Result-grade honesty

LidarPerf reports MUST distinguish:

- what was directly measured
- what was derived
- what was unavailable
- what was inferred
- what failed conformance

The absence of a measurement is preferable to a fabricated precision.

---

# 71. Research-integrity rules

For publication-oriented use:

- all planned sequences SHOULD be retained
- failed runs MUST be retained
- exclusions MUST state reasons
- exclusions SHOULD be predeclared where possible
- metric/protocol changes after seeing results MUST be versioned/disclosed
- source/config changes MUST be fingerprinted
- raw result bundles SHOULD be archived
- plots/tables MUST be reproducible from stored bundles

LidarPerf should make cherry-picking inconvenient rather than convenient.

---

# 72. Security and privacy

Result bundles MAY contain logs with local paths, usernames, hostnames, or proprietary command lines.

Before public release, LidarPerf SHOULD support a sanitization/export step.

Sanitization MUST NOT alter benchmark-relevant semantic fields without recording that sanitization occurred.

---

# 73. Error taxonomy

v0.1 SHOULD use stable error categories.

Suggested top-level classes:

```text
SPEC_ERROR
CONFORMANCE_ERROR
INPUT_ERROR
EXECUTION_ERROR
OUTPUT_ERROR
METRIC_ERROR
PROVENANCE_ERROR
COMPARABILITY_ERROR
ENVIRONMENT_WARNING
```

Errors should contain:

- machine-readable code
- human-readable explanation
- affected field
- remediation hint where possible

---

# 74. Planned protocol files

Initial repository protocol layout:

```text
protocols/
├── lo/
│   └── se3_v1.yaml
├── lio/
│   └── se3_v1.yaml
└── datasets/
    └── kitti_odometry_v1.yaml   # added only when golden-tested
```

The resolved protocol may compose track, metric, and execution defaults, but the stored resolved form MUST be self-contained.

---

# 75. Proposed initial LO protocol defaults

Subject to Gate 1 approval, the first built-in LO protocol will use:

```yaml
track: lo

estimator_semantics:
  temporal_mode:
    allowed:
      - online_causal
      - online_fixed_lag

scale_correction: false

validity:
  temporal_coverage_min: 0.98
  finite_poses_required: true
  successful_process_exit_required: true

measurement:
  cpu_authoritative: true
  gpu_authoritative: false
```

Metric windows and timestamp tolerance will be dataset/evaluation-profile fields rather than hidden package constants.

---

# 76. Proposed initial LIO protocol defaults

Same as LO except:

```yaml
track: lio

sensors:
  lidar: required
  imu: required
```

All other external aiding sources remain forbidden.

---

# 77. Default behavior when semantics are unknown

LidarPerf MUST prefer:

```text
UNKNOWN / NOT COMPARABLE
```

over guessing.

Examples:

- unknown pose convention
- unknown deskew state
- unknown body frame
- unknown dataset content version
- unknown timing scope

Unknown metadata may still permit exploratory execution, but it reduces conformance/comparability.

---

# 78. Reproducibility levels

The bundle SHOULD calculate a reproducibility classification based on available provenance.

Proposed labels:

```text
R0  insufficient provenance
R1  identified inputs/software, incomplete exact fingerprints
R2  exact data/config/software fingerprints
R3  R2 + controlled execution environment and repeat trials
```

This classification is informational and MUST NOT be confused with estimator accuracy.

The exact scoring implementation will be specified before code is released; v0.1 MAY initially expose reasons rather than a numeric score.

---

# 79. Known limitations of v0.1

The first version will not fully solve:

- cross-machine performance normalization
- GPU-kernel timing
- energy use
- thermal normalization
- ROS 2 end-to-end latency
- networked/distributed estimators
- multi-LiDAR systems with complex synchronization
- SLAM loop-closure fairness
- learned methods requiring model-training provenance
- proprietary binary source reproducibility

These limitations MUST be stated rather than hidden.

---

# 80. Acceptance tests for the specification implementation

Before calling v0.1 implementation conformant, the software must demonstrate all of the following.

1. A valid synthetic LO run creates a verifiable bundle.
2. A pose-direction error is caught by a golden test.
3. A modified payload causes checksum verification failure.
4. An LO run declaring IMU input fails conformance.
5. Different dataset fingerprints fail strict comparability.
6. Different timing scopes fail strict performance comparability.
7. A candidate with catastrophic accuracy but lower runtime cannot PASS regression.
8. Failed trials remain visible in aggregate output.
9. A metric implementation matches its independent golden reference.
10. An opaque command backend does not claim per-frame latency.
11. A controlled result with too few repeats is downgraded.
12. Baseline/candidate unexpected environment changes prevent strict regression PASS.

---

# 81. Implementation order dictated by this specification

Once Gate 1 is approved:

1. repository foundation
2. protocol/schema models
3. synthetic fixture
4. result-bundle schema
5. verification/checksums
6. host fingerprint + `doctor`
7. BenchExec execution backend
8. trajectory representation/validation
9. metric golden tests
10. conformance engine
11. evalio backend
12. first real KISS/evalio dataset run
13. repeated-run analysis
14. comparability engine
15. regression engine
16. reports
17. Bencher export
18. Docker backend
19. GitHub Action
20. real-world hardening/release

---

# 82. Gate 1 decisions

This draft makes the following concrete recommendations.

Approval of `SPEC.md v0.1` means approving these defaults unless explicitly changed.

| # | Decision | Recommendation |
|---|---|---|
| 1 | Official v0.1 tracks | **LO + LIO only**; defer SLAM/registration |
| 2 | Pose convention | **`T_W_B`, metres, int64 ns, quaternion xyzw** |
| 3 | Metric scale handling | **No Sim(3)/scale correction for official LO/LIO** |
| 4 | Process benchmarking | **BenchExec on Linux for controlled process metrics** |
| 5 | Controlled repetitions | **minimum 5 measured trials** |
| 6 | Publication repetitions | **minimum 10 measured trials** |
| 7 | Default validity coverage | **98% temporal coverage**, override only explicitly |
| 8 | Opaque process timing | **end-to-end only**; no fake per-frame latency |
| 9 | Regression execution | **paired blocked randomized baseline/candidate runs** |
| 10 | Regression thresholds | **explicit; no universal hidden 5% threshold** |
| 11 | Accuracy before speed | **mandatory** |
| 12 | Unknown semantics | **fail strict comparability rather than guess** |
| 13 | Dataset identity | **exact SHA-256 manifest when feasible** |
| 14 | evalio relationship | **backend/dependency, not metric authority** |
| 15 | GPU authoritative benchmarking | **defer beyond first CPU-controlled release** |

---

# 83. Approval consequences

If Gate 1 is approved:

- these semantics become the initial implementation contract
- the protocol/schema layer is implemented against them
- changing a fundamental rule later will require an explicit spec/protocol revision
- implementation bugs will be fixed without changing the intended protocol semantics
- research findings that challenge the specification will be logged and may cause a versioned protocol revision, never a silent rewrite

---

# 84. Final specification thesis

LidarPerf v0.1 exists to enforce one principle:

> **A performance number is not meaningful until the input, estimator behavior, preprocessing, evaluation rules, hardware, measurement boundary, validity, and repeatability are known well enough to establish what the number actually represents.**

The project should reject invalid certainty rather than generate convenient benchmark tables.
