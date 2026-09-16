#!/usr/bin/env python3
"""Temporary Step 12 documentation closer; removed by its one-shot workflow."""

from pathlib import Path


README_STEP12 = """
Step 12 implements `lidarperf regress`. Regression decisions reuse Step 11 comparability
rather than bypassing it, require recorded paired blocked-randomization metadata for strict
performance regression, apply explicit accuracy gates before speed, and require an explicit
practical performance threshold. Paired runtime effects are summarized by median normalized
change with a deterministic bootstrap confidence interval. If evidence is incomparable, a
gate is missing, or uncertainty crosses the threshold, LidarPerf refuses a binary performance
claim. The example policy in `docs/examples/regression_policy.example.yaml` is illustrative
only; its 5% performance and 2% accuracy limits are not package defaults.
""".strip()

REGRESS_DOC = """
`regress` builds on the verified Step 11 comparison and emits `lidarperf.regression.v1`.
Strict regression requires comparable controlled evidence plus paired execution metadata
(`pairing_id`, randomization seed, and one `AB`/`BA` order record per pair). Accuracy gates
run before the performance gate. The performance decision uses paired normalized changes, a
median effect estimate, a bootstrap confidence interval, and an explicit practical threshold
from a policy file. Missing gates or a confidence interval that straddles the threshold
produce `INCONCLUSIVE`; incompatible evidence produces `NOT_COMPARABLE`. LidarPerf does not
silently invent a universal performance or accuracy threshold.
""".strip()

HISTORY = """

---

## Step 12 — regression decision engine — 16 September 2026

Step 12 implements the v0.1 regression-decision layer on top of Step 11 semantic
comparability rather than duplicating or weakening comparison rules.

### Implemented semantics

- Added `lidarperf regress BASELINE CANDIDATE` and versioned `lidarperf.regression.v1`
  reports.
- Normative verdicts are `PASS`, `FAIL_ACCURACY`, `FAIL_PERFORMANCE`, `FAIL_VALIDITY`,
  `INCONCLUSIVE`, and `NOT_COMPARABLE`.
- Both bundles are independently verified and Step 11 comparability is evaluated before
  regression gates.
- Strict paired regression additionally requires equal measured-pair counts, the same
  non-empty `pairing_id`, `paired_execution=true`, the same recorded integer `pairing_seed`,
  and the same one-entry-per-pair `AB`/`BA` order metadata.
- Accuracy gates execute before performance. Implemented gate primitives are `absolute_max`,
  `relative_max_regression`, and `non_inferiority_margin`; multiple configured gates are
  all-of, providing the v0.1 `multi_metric_all` behavior.
- Performance policy records metric direction, explicit practical regression threshold,
  confidence level, bootstrap sample count/seed, and minimum valid pair count.
- The paired effect is normalized so positive percentages always mean worse performance,
  independent of metric direction.
- The primary performance statistic is the median paired normalized regression. A
  deterministic percentile bootstrap estimates its confidence interval.
- `FAIL_PERFORMANCE` requires the entire confidence interval to be worse than the practical
  threshold; `PASS` requires the entire interval to remain at or below the threshold;
  overlap produces `INCONCLUSIVE`.
- No explicit accuracy gate means `INCONCLUSIVE`. No explicit practical performance
  threshold means `INCONCLUSIVE`. LidarPerf does not invent a hidden 5% rule.
- CLI exit codes are 0 for `PASS`, 1 for substantive `FAIL_*`, 2 for invalid
  invocation/evidence, and 3 for `INCONCLUSIVE` or `NOT_COMPARABLE`.
- Added `docs/examples/regression_policy.example.yaml`; its 5% performance and 2% accuracy
  values are examples only, not defaults.

### Validation

- The real committed Step 9→Step 10 GitHub-hosted evidence is intentionally rejected as
  `NOT_COMPARABLE` for strict regression, proving that Step 12 does not bypass Step 11
  host/control safeguards.
- Durable `docs/validation/step12_regression_engine.json` also contains clearly labeled
  synthetic decision-engine fixtures derived from the existing Step 10 payload. These
  fixtures demonstrate `PASS`, `FAIL_PERFORMANCE`, `FAIL_ACCURACY` even when the candidate is
  faster, and threshold-crossing `INCONCLUSIVE`. They are not new controlled benchmark runs
  or KISS-ICP performance claims.
- The accuracy-regression fixture deliberately makes the candidate 50% faster while
  worsening translation APE by 10%; the engine returns `FAIL_ACCURACY` and does not evaluate
  a performance win, preserving the accuracy-before-speed invariant.

### Failures and fixes preserved

- Initial Step 12 CI stopped at seven Ruff findings before behavioral tests: one CLI long
  line, one modern-annotation fix, and several long regression-engine diagnostic lines.
- The first temporary formatter workflow used `ruff check --fix` before `ruff format`;
  because Ruff returned nonzero on E501, shell `-e` prevented the formatter and all tests
  from running. No product commit was produced.
- The second formatter attempt corrected the step order, reformatted two files, and
  auto-fixed one issue, but two E501 diagnostic strings remained because Ruff formatting
  intentionally did not split them. Again, no product commit was produced.
- The third formatter gate explicitly split those two diagnostics, then Ruff passed and the
  complete behavioral suite reached 149 passing tests. The temporary formatter workflow
  self-deleted in bot commit `73aad28`.
- Two CLI regression tests were then added to lock the `NOT_COMPARABLE` human/JSON behavior
  and exit code 3 for the real hosted Step 9→Step 10 evidence, bringing the final Step 12
  suite to 151 tests before merge.
- The first Step 12 closure workflow stopped before evidence generation because the durable
  validation script contained one 111-character evidence-label line. The line was split;
  no evidence or documentation from that failed closure run was committed.

Step 12 exit condition: regression verdict semantics, explicit gate policy, paired
uncertainty handling, CLI, durable guardrail/decision evidence, documentation, full
supported-Python CI, merge, and post-merge CI must all be complete before the step is closed.
"""


def update_readme() -> None:
    path = Path("README.md")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "repeated-run/repeatability analysis, and semantic result comparison are implemented.",
        "repeated-run/repeatability analysis, semantic result comparison, and the regression "
        "decision engine are implemented.",
    )

    comparator = (
        "- a semantic comparator that independently verifies both bundles, evaluates "
        "accuracy/performance/regression comparability separately, enumerates evidence "
        "differences, and refuses strict performance ranking when required semantics are "
        "missing or incompatible.\n"
    )
    regression = (
        "- an accuracy-gated regression engine with explicit policy thresholds, paired "
        "blocked-run metadata checks, deterministic bootstrap uncertainty, and `PASS` / "
        "`FAIL_ACCURACY` / `FAIL_PERFORMANCE` / `FAIL_VALIDITY` / `INCONCLUSIVE` / "
        "`NOT_COMPARABLE` verdicts.\n"
    )
    if regression not in text:
        text = text.replace(comparator, comparator + regression)

    marker = "\n## Validation snapshot\n"
    if README_STEP12 not in text:
        text = text.replace(marker, "\n" + README_STEP12 + "\n" + marker)

    available = "lidarperf compare baseline.lperf candidate.lperf\n"
    regress_command = (
        "lidarperf regress baseline.lperf candidate.lperf --policy "
        "docs/examples/regression_policy.example.yaml\n"
    )
    if regress_command not in text:
        text = text.replace(available, available + regress_command, 1)

    compare_doc_end = (
        "`--json` emits the complete machine-readable report.\n"
    )
    if REGRESS_DOC not in text:
        text = text.replace(compare_doc_end, compare_doc_end + "\n" + REGRESS_DOC + "\n", 1)

    path.write_text(text, encoding="utf-8")


def update_validation_index() -> None:
    path = Path("docs/validation/README.md")
    text = path.read_text(encoding="utf-8")
    line = (
        "- `step12_regression_engine.json` validates the Step 12 decision engine. It records "
        "the real hosted Step 9→Step 10 guardrail as `NOT_COMPARABLE` and separately "
        "exercises `PASS`, `FAIL_PERFORMANCE`, `FAIL_ACCURACY`, and `INCONCLUSIVE` with "
        "synthetic controlled decision fixtures derived from Step 10. Those synthetic "
        "scenarios validate decision logic only and are not controlled KISS-ICP benchmark "
        "claims.\n"
    )
    if line not in text:
        anchor = (
            "- `step11_compare_step9_step10.json` is the first durable semantic-comparison "
            "report. It proves that the Step 9 and Step 10 bundles are accuracy-comparable "
            "while strict performance and regression comparison are rejected; reported "
            "timing/resource deltas remain descriptive only.\n"
        )
        text = text.replace(anchor, anchor + line)
    path.write_text(text, encoding="utf-8")


def update_history() -> None:
    path = Path("LidarPerf_research_execution_plan.md")
    text = path.read_text(encoding="utf-8")
    if "## Step 12 — regression decision engine — 16 September 2026" not in text:
        path.write_text(text + HISTORY, encoding="utf-8")


def main() -> None:
    update_readme()
    update_validation_index()
    update_history()


if __name__ == "__main__":
    main()
