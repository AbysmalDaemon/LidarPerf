# Validation evidence

This directory contains durable integration evidence produced while building LidarPerf. These artifacts validate software paths and benchmark semantics; they are not automatically authoritative performance baselines.

- `step8_kiss_evalio.json` records the first real evalio/KISS-ICP/Hilti integration validation.
- `step9_kiss_hilti.lperf/` is the first complete verified real `.lperf` artifact path. It is a one-trial `exploratory` result.
- `step10_kiss_hilti_repeated.lperf/` validates repeated-run execution with one warmup and five measured KISS-ICP/Hilti trials. It remains `exploratory` because it was produced on an ordinary GitHub-hosted runner; its BenchExec measurements are real integration evidence but not an authoritative performance baseline.
- `step11_compare_step9_step10.json` is the first durable semantic-comparison report. It proves that the Step 9 and Step 10 bundles are accuracy-comparable while strict performance and regression comparison are rejected; reported timing/resource deltas remain descriptive only.
- `lidarperf_validation_snapshot.svg` is the README-facing visual summary of the committed Step 9–11 evidence. Its numbers are derived from the durable result bundles and Step 11 comparison report; it is presentation material, not an additional benchmark result.

Use `lidarperf verify <bundle>` to validate a committed `.lperf` directory. Measurement strength is determined by both repetition requirements and environment requirements. In particular, five measured trials alone do not make a result `controlled`; the v0.1 specification also requires a stable self-hosted or otherwise controlled Linux benchmark environment with the declared controls.

Reproduce the committed Step 11 semantic decision with:

```bash
lidarperf compare \
  docs/validation/step9_kiss_hilti.lperf \
  docs/validation/step10_kiss_hilti_repeated.lperf
```

Add `--json` to obtain the machine-readable `lidarperf.comparison.v1` report shape used by `step11_compare_step9_step10.json`.
