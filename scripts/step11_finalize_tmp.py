from pathlib import Path

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
text = text.replace(
    "complete `.lperf` artifact production, and repeated-run/repeatability analysis are implemented.",
    "complete `.lperf` artifact production, repeated-run/repeatability analysis, and semantic result comparison are implemented.",
    1,
)
anchor = "- a repeated-run orchestration path with explicit warmups, retained failed trials, per-metric/resource distributions, and all-pairs estimator-output repeatability recomputed by the verifier from immutable trajectory payloads.\n"
addition = anchor + "- a semantic comparator that independently verifies both bundles, evaluates accuracy/performance/regression comparability separately, enumerates evidence differences, and refuses strict performance ranking when required semantics are missing or incompatible.\n"
if anchor not in text:
    raise SystemExit("README package-list anchor missing")
text = text.replace(anchor, addition, 1)
anchor = "The Step 10 hosted bundle remains `exploratory` even with five measured trials. The specification requires a stable self-hosted or otherwise controlled Linux machine, explicit CPU allocation/thread policy, recorded governor state, controlled storage, and no swap pressure before a result may claim `controlled` strength. Ordinary GitHub-hosted runners therefore validate the repeated-run machinery but are not authoritative performance baselines.\n"
addition = anchor + "\nStep 11 implements `lidarperf compare`. Comparability is dimension-aware: accuracy can be comparable even when performance is not. The durable Step 11 report compares the real Step 9 and Step 10 bundles and finds accuracy semantics compatible, while strict performance/regression comparison is rejected because the hosted evidence lacks controlled physical-host identity, explicit CPU allocation/paired execution, and authoritative performance status. The comparator still reports raw metric/resource deltas, but does not rank them.\n"
if anchor not in text:
    raise SystemExit("README Step 10 anchor missing")
text = text.replace(anchor, addition, 1)
anchor = "lidarperf verify ./result.lperf\n"
addition = anchor + "lidarperf compare baseline.lperf candidate.lperf\n"
if anchor not in text:
    raise SystemExit("README CLI anchor missing")
text = text.replace(anchor, addition, 1)
anchor = "`verify` validates a `.lperf` directory's versioned metadata, protocol/config provenance links, declared file inventory, execution-log layout, SHA-256 payload checksums, trial-count consistency, and the minimum trial count required by the declared measurement class. It returns `VALID`, `VALID WITH WARNINGS`, or `INVALID`.\n"
addition = anchor + "\n`compare` verifies both bundles first and emits a versioned `lidarperf.comparison.v1` report. It checks accuracy, performance, and regression comparability separately against the v0.1 specification; reports all failed checks and observed evidence differences; summarizes common accuracy/resource scalar changes; and never converts incomparable evidence into a strict performance ranking. Intentional configuration, build-environment, or dependency changes can be declared explicitly with repeated `--declare-change` options rather than being silently ignored. `--json` emits the complete machine-readable report.\n"
if anchor not in text:
    raise SystemExit("README verify anchor missing")
text = text.replace(anchor, addition, 1)
readme.write_text(text, encoding="utf-8")

validation = Path("docs/validation/README.md")
text = validation.read_text(encoding="utf-8")
anchor = "- `step10_kiss_hilti_repeated.lperf/` validates repeated-run execution with one warmup and five measured KISS-ICP/Hilti trials. It remains `exploratory` because it was produced on an ordinary GitHub-hosted runner; its BenchExec measurements are real integration evidence but not an authoritative performance baseline.\n"
addition = anchor + "- `step11_compare_step9_step10.json` is the first durable semantic-comparison report. It proves that the Step 9 and Step 10 bundles are accuracy-comparable while strict performance and regression comparison are rejected; reported timing/resource deltas remain descriptive only.\n"
if anchor not in text:
    raise SystemExit("validation index anchor missing")
validation.write_text(text.replace(anchor, addition, 1), encoding="utf-8")

plan = Path("LidarPerf_research_execution_plan.md")
with plan.open("a", encoding="utf-8") as handle:
    handle.write('''

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
''')
