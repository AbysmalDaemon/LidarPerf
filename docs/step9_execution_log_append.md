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
