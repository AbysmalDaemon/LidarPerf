from __future__ import annotations

from pathlib import Path


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one replacement target in {path}, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def _update_spec() -> None:
    path = Path("SPEC.md")
    text = path.read_text(encoding="utf-8")
    start_marker = "## 24.1 Coverage\n"
    end_marker = "\n---\n\n# 25. Accuracy evaluation profiles"
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    replacement = """## 24.1 Coverage

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
"""
    path.write_text(text[:start] + replacement + text[end:], encoding="utf-8", newline="\n")


def _update_readme() -> None:
    path = Path("README.md")
    old_status = (
        "> **Status:** pre-alpha. The benchmark specification is approved; protocol, "
        "synthetic-fixture, result-bundle integrity, host-provenance, and controlled "
        "process-execution layers are implemented."
    )
    new_status = (
        "> **Status:** pre-alpha. The benchmark specification is approved; protocol, "
        "synthetic-fixture, result-bundle integrity, host-provenance, controlled "
        "process-execution, trajectory-evaluation, and first real evalio/KISS-ICP "
        "integration layers are implemented."
    )
    _replace_once(path, old_status, new_status)

    old_tail = (
        "- canonical trajectory parsing/validation, explicit timestamp association, rigid "
        "SE(3) alignment, APE, distance-window relative-pose errors, and coverage accounting.\n\n"
        "Real estimator/dataset orchestration is **not implemented yet**."
    )
    new_tail = (
        "- canonical trajectory parsing/validation, explicit timestamp association, rigid "
        "SE(3) alignment, APE, distance-window relative-pose errors, and coverage accounting;\n"
        "- a thin evalio execution adapter, validated with real KISS-ICP 1.3.0 on the public "
        "Hilti 2022 `basement_2` sequence.\n\n"
        "A real estimator/dataset path has now been functionally validated: evalio 0.6.1 → "
        "KISS-ICP 1.3.0 → 120 Hilti LiDAR scans → LidarPerf trajectory validation/evaluation. "
        "The durable evidence is in `docs/validation/step8_kiss_evalio.json`. GitHub-hosted "
        "runner timing from this validation is explicitly non-authoritative; controlled "
        "performance claims still require the BenchExec/self-hosted path."
    )
    _replace_once(path, old_tail, new_tail)

    marker = "### BenchExec backend\n"
    section = """### evalio backend

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
"""
    text = path.read_text(encoding="utf-8")
    if text.count(marker) != 1:
        raise RuntimeError("README BenchExec insertion marker is missing or ambiguous")
    path.write_text(text.replace(marker, section), encoding="utf-8", newline="\n")


def _append_log() -> None:
    path = Path("LidarPerf_research_execution_plan.md")
    text = path.read_text(encoding="utf-8")
    title = "## Project execution log — 2026-09-14 — Step 8 evalio + real KISS-ICP integration"
    if title in text:
        return
    entry = r"""

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
"""
    path.write_text(text.rstrip() + entry + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    _update_spec()
    _update_readme()
    _append_log()


if __name__ == "__main__":
    main()
