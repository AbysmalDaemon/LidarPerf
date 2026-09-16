# Validation evidence

This directory contains durable integration evidence produced while building LidarPerf. These artifacts validate software paths and benchmark semantics; they are not automatically authoritative performance baselines.

- `step8_kiss_evalio.json` records the first real evalio/KISS-ICP/Hilti integration validation.
- `step9_kiss_hilti.lperf/` is the first complete verified real `.lperf` artifact path. It is a one-trial `exploratory` result.
- `step10_kiss_hilti_repeated.lperf/` validates repeated-run execution with one warmup and five measured KISS-ICP/Hilti trials. It remains `exploratory` because it was produced on an ordinary GitHub-hosted runner; its BenchExec measurements are real integration evidence but not an authoritative performance baseline.
- `step11_compare_step9_step10.json` is the first durable semantic-comparison report. It proves that the Step 9 and Step 10 bundles are accuracy-comparable while strict performance and regression comparison are rejected; reported timing/resource deltas remain descriptive only.
- `step12_regression_engine.json` validates the Step 12 decision engine. It records the real hosted Step 9→Step 10 guardrail as `NOT_COMPARABLE` and separately exercises `PASS`, `FAIL_PERFORMANCE`, `FAIL_ACCURACY`, and `INCONCLUSIVE` with synthetic controlled decision fixtures derived from Step 10. Those synthetic scenarios validate decision logic only and are not controlled KISS-ICP benchmark claims.
- `lidarperf_validation_snapshot.svg` is the README-facing visual summary of the committed Step 9–11 evidence. Its numbers are derived from the durable result bundles and Step 11 comparison report; it is presentation material, not an additional benchmark result.
- [`step13_kiss_hilti_report.html`](step13_kiss_hilti_report.html) and [`step13_kiss_hilti_report.json`](step13_kiss_hilti_report.json) are the first durable `lidarperf report` outputs. They summarize the verified Step 10 real bundle and attach the Step 11 semantic-comparison context. The report preserves the hosted result's `exploratory` / non-authoritative status and makes no new performance claim.
- [`step14_kiss_hilti_bencher.json`](step14_kiss_hilti_bencher.json) is the first durable Bencher Metric Format export. It is derived from the verified Step 10 bundle and intentionally ends its benchmark identity with `-bencher-ignore`, so the hosted exploratory values may be stored without producing Bencher performance alerts. It is descriptive interoperability evidence, not a new benchmark run.
- [`step15_docker_backend.json`](step15_docker_backend.json) is the first real Docker-backend integration record. It executes `alpine:3.20` by immutable digest with network disabled, one declared CPU, a 64 MiB memory cap and a writable bind mount. The run validates immutable-image resolution, mount round-trip, output capture and cleanup semantics. Its elapsed wall time is functional hosted evidence only; Docker v0.1 explicitly does not claim authoritative process CPU/memory accounting across the daemon boundary.

Use `lidarperf verify <bundle>` to validate a committed `.lperf` directory. Measurement strength is determined by both repetition requirements and environment requirements. In particular, five measured trials alone do not make a result `controlled`; the v0.1 specification also requires a stable self-hosted or otherwise controlled Linux benchmark environment with the declared controls.

Reproduce the committed Step 11 semantic decision with:

```bash
lidarperf compare \
  docs/validation/step9_kiss_hilti.lperf \
  docs/validation/step10_kiss_hilti_repeated.lperf
```

Add `--json` to obtain the machine-readable `lidarperf.comparison.v1` report shape used by `step11_compare_step9_step10.json`.

Reproduce the Step 13 report with:

```bash
lidarperf report docs/validation/step10_kiss_hilti_repeated.lperf \
  --comparison docs/validation/step11_compare_step9_step10.json \
  --html docs/validation/step13_kiss_hilti_report.html \
  --json docs/validation/step13_kiss_hilti_report.json
```

Reproduce the Step 14 Bencher export with:

```bash
lidarperf export bencher docs/validation/step10_kiss_hilti_repeated.lperf \
  > docs/validation/step14_kiss_hilti_bencher.json
```

The warning about suppressed Bencher alerts is written to stderr and therefore does not contaminate the JSON stream. The same stdout can be consumed directly by Bencher's JSON adapter:

```bash
bencher run --adapter json \
  "lidarperf export bencher docs/validation/step10_kiss_hilti_repeated.lperf"
```

Reproduce the Step 15 Docker integration on a Linux host with a reachable Docker daemon:

```bash
docker pull alpine:3.20
python scripts/run_step15_docker_validation.py
```

The committed validation uses `--network none`, an explicit CPU allocation and a 64 MiB memory limit. The image is executed by immutable repository digest with `--pull never`; the JSON records both requested and immutable image identities plus Docker client/server versions. The 64 MiB cap is a fixture constraint chosen to prove memory-limit declaration and provenance, not a recommended estimator memory budget.
