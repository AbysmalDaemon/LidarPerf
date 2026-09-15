# Validation evidence

This directory contains durable integration evidence produced while building LidarPerf. These artifacts validate software paths and benchmark semantics; they are not automatically authoritative performance baselines.

- `step8_kiss_evalio.json` records the first real evalio/KISS-ICP/Hilti integration validation.
- `step9_kiss_hilti.lperf/` is the first complete verified real `.lperf` artifact path. It is a one-trial `exploratory` result.
- `step10_kiss_hilti_repeated.lperf/` validates repeated-run execution with one warmup and five measured KISS-ICP/Hilti trials. It remains `exploratory` because it was produced on an ordinary GitHub-hosted runner; its BenchExec measurements are real integration evidence but not an authoritative performance baseline.
- `step11_compare_step9_step10.json` is the first durable semantic-comparison report. It proves that the Step 9 and Step 10 bundles are accuracy-comparable while strict performance and regression comparison are rejected; reported timing/resource deltas remain descriptive only.

Use `lidarperf verify <bundle>` to validate a committed `.lperf` directory. Measurement strength is determined by both repetition requirements and environment requirements. In particular, five measured trials alone do not make a result `controlled`; the v0.1 specification also requires a stable self-hosted or otherwise controlled Linux benchmark environment with the declared controls.
