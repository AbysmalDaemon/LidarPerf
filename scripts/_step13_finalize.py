"""One-shot Step 13 documentation finalizer; removed by its workflow."""

from pathlib import Path


README = Path("README.md")
VALIDATION_README = Path("docs/validation/README.md")
LIVING_RECORD = Path("LidarPerf_research_execution_plan.md")


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"documentation anchor not found: {old[:80]!r}")
    return text.replace(old, new, 1)


def update_readme() -> None:
    text = README.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "semantic result comparison, and the regression decision engine are implemented.",
        (
            "semantic result comparison, the regression decision engine, and self-contained "
            "HTML/JSON reporting are implemented."
        ),
    )
    text = replace_once(
        text,
        (
            "- an accuracy-gated regression engine with explicit policy thresholds, paired "
            "blocked-run metadata checks, deterministic bootstrap uncertainty, and `PASS` / "
            "`FAIL_ACCURACY` / `FAIL_PERFORMANCE` / `FAIL_VALIDITY` / `INCONCLUSIVE` / "
            "`NOT_COMPARABLE` verdicts.\n"
        ),
        (
            "- an accuracy-gated regression engine with explicit policy thresholds, paired "
            "blocked-run metadata checks, deterministic bootstrap uncertainty, and `PASS` / "
            "`FAIL_ACCURACY` / `FAIL_PERFORMANCE` / `FAIL_VALIDITY` / `INCONCLUSIVE` / "
            "`NOT_COMPARABLE` verdicts.\n"
            "- verified `lidarperf.report.v1` summaries and self-contained HTML/SVG reports "
            "covering accuracy, resources, repeatability, trajectory preview, provenance, "
            "scientific caveats, and optional comparison/regression context.\n"
        ),
    )
    step12_tail = (
        "only; its 5% performance and 2% accuracy limits are not package defaults.\n"
    )
    step13 = (
        "\nStep 13 implements `lidarperf report`. Reports verify the source `.lperf` bundle before "
        "rendering, emit a versioned `lidarperf.report.v1` JSON summary, and can produce a "
        "single self-contained HTML file using inline CSS/SVG only. The report preserves "
        "measurement class and performance-authority semantics instead of upgrading evidence "
        "through presentation. Optional Step 11 comparison and Step 12 regression JSON can be "
        "attached when they reference the reported result. The durable real report is "
        "`docs/validation/step13_kiss_hilti_report.html` with its machine-readable companion "
        "`step13_kiss_hilti_report.json`.\n"
    )
    text = replace_once(text, step12_tail, step12_tail + step13)
    text = replace_once(
        text,
        "lidarperf regress baseline.lperf candidate.lperf --policy policy.yaml\n",
        (
            "lidarperf regress baseline.lperf candidate.lperf --policy policy.yaml\n"
            "lidarperf report result.lperf --html report.html --json report.json\n"
        ),
    )
    text = replace_once(
        text,
        (
            "lidarperf regress baseline.lperf candidate.lperf --policy "
            "docs/examples/regression_policy.example.yaml\n"
        ),
        (
            "lidarperf regress baseline.lperf candidate.lperf --policy "
            "docs/examples/regression_policy.example.yaml\n"
            "lidarperf report result.lperf --html report.html --json report.json\n"
        ),
    )
    regression_end = (
        "silently invent a universal performance or accuracy threshold.\n"
    )
    report_docs = (
        "\n`report` first verifies the immutable source bundle, then builds a versioned "
        "`lidarperf.report.v1` summary. `--html` writes a portable, self-contained report with "
        "inline SVG trajectory/distribution graphics and no CDN, JavaScript, external fonts, "
        "or network requests; `--json` writes the same report semantics for downstream tools. "
        "The renderer surfaces verification warnings, failed trials, measurement class, host "
        "control, and `performance_authoritative` status prominently. `--comparison` and "
        "`--regression` may attach existing versioned decision reports, but presentation never "
        "changes their conclusions or the strength of the underlying evidence.\n"
    )
    text = replace_once(text, regression_end, regression_end + report_docs)
    README.write_text(text, encoding="utf-8")


def update_validation_readme() -> None:
    text = VALIDATION_README.read_text(encoding="utf-8")
    anchor = (
        "- `lidarperf_validation_snapshot.svg` is the README-facing visual summary of the "
        "committed Step 9–11 evidence. Its numbers are derived from the durable result bundles "
        "and Step 11 comparison report; it is presentation material, not an additional "
        "benchmark result.\n"
    )
    addition = (
        "- `step13_kiss_hilti_report.html` and `step13_kiss_hilti_report.json` are the first "
        "durable `lidarperf report` outputs. They summarize the verified Step 10 real bundle "
        "and attach the Step 11 semantic-comparison context. The report preserves the hosted "
        "result's `exploratory` / non-authoritative status and makes no new performance claim.\n"
    )
    text = replace_once(text, anchor, anchor + addition)
    reproduce = (
        "\nReproduce the Step 13 report with:\n\n"
        "```bash\n"
        "lidarperf report docs/validation/step10_kiss_hilti_repeated.lperf \\\n"
        "  --comparison docs/validation/step11_compare_step9_step10.json \\\n"
        "  --html docs/validation/step13_kiss_hilti_report.html \\\n"
        "  --json docs/validation/step13_kiss_hilti_report.json\n"
        "```\n"
    )
    if "Reproduce the Step 13 report with:" not in text:
        text += reproduce
    VALIDATION_README.write_text(text, encoding="utf-8")


def update_living_record() -> None:
    text = LIVING_RECORD.read_text(encoding="utf-8")
    heading = "## Step 13 — self-contained reporting — 16 September 2026"
    if heading in text:
        return
    entry = f"""

---

{heading}

Step 13 turns verified LidarPerf evidence into portable presentation without changing the
scientific strength of that evidence.

### Implemented

- Added `lidarperf report RESULT.lperf` and versioned `lidarperf.report.v1` summaries.
- Reports independently verify the source bundle and reject invalid evidence before rendering.
- `--html` writes a single self-contained HTML document using inline CSS and SVG only; there
  are no external fonts, scripts, CDNs, or network requests.
- `--json` writes the same versioned report semantics for downstream tools.
- Reports include bundle/conformance status, measurement class, explicit performance authority,
  trial outcomes, warmups, accuracy/coverage metrics, runtime/resource distributions,
  estimator-output repeatability, a first-successful-trial XY trajectory preview, protocol,
  dataset/method/host provenance, and scientific caveats.
- Single-trial bundles are supported by reconstructing resource summaries from successful trial
  payloads when repeated-run resource distributions are absent.
- Optional `lidarperf.comparison.v1` and `lidarperf.regression.v1` reports may be attached only
  when their baseline/candidate result IDs reference the reported bundle.
- Presentation does not upgrade an exploratory or non-authoritative result. The committed Step 10
  GitHub-hosted result remains explicitly `exploratory` and `NON-AUTHORITATIVE` in Step 13 output.
- No plotting dependency was added: compact inline SVG provides trajectory and distribution
  visuals while keeping the report portable and the package dependency surface unchanged.

### Dedicated validation

- Added six Step 13 tests covering the real repeated Step 10 bundle, Step 9 single-trial resource
  fallback, portable HTML/JSON generation, Step 11 comparison attachment, invalid bundle and
  unrelated-comparison rejection, and the Typer CLI path.
- Full suite increased from 151 to 157 tests.
- CI run `35135211926` passed Ruff and all 157 tests on Python 3.11, 3.12, and 3.13.
- Durable real presentation evidence is generated by `scripts/run_step13_validation.py` into
  `docs/validation/step13_kiss_hilti_report.html` and
  `docs/validation/step13_kiss_hilti_report.json` from the already committed Step 10 bundle plus
  Step 11 comparison report. This is presentation derived from existing evidence, not a new
  benchmark execution.

### Failures and fixes preserved

1. Initial report implementation CI run `35134916364` failed at Ruff before tests. It found a
   B023 loop-closure capture in a local percentile helper plus E501 line-length findings from the
   intentionally embedded self-contained HTML/CSS template. No report behavior was tested in that
   run.
2. Temporary repair workflow run `35135017485` bound the percentile helper state explicitly,
   scoped the E501 exemption to the renderer module where embedded HTML/CSS is intentional, ran
   Ruff formatting/checks, and confirmed the pre-Step-13 151-test suite still passed. The workflow
   then removed itself in commit `74e854d6aed26189ef90c0cc57d289af7a9caf76`.
3. Dedicated behavior was then added rather than treating the lint-clean implementation as proof.
   The real report tests and CLI path passed in CI run `35135211926` across all supported Python
   versions.

Step 13 exit condition: durable real HTML/JSON report evidence, documentation, living history,
157-test full-suite validation, exact final-head Python 3.11/3.12/3.13 CI, merge, and post-merge
`main` CI must all be green before the step is closed.
"""
    LIVING_RECORD.write_text(text + entry, encoding="utf-8")


def main() -> None:
    update_readme()
    update_validation_readme()
    update_living_record()


if __name__ == "__main__":
    main()
