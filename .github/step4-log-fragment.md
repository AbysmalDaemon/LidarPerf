---

## Project execution log — 2026-09-14 — Step 4 result bundles and verifier

**Status:** implementation complete; this record is appended only after pre-PR remote Ruff + pytest validation passes on Python 3.13.

### Goal

Introduce LidarPerf's first durable benchmark artifact: a versioned `.lperf` directory that can be inspected and verified independently of the process that created it.

This step intentionally does **not** execute a real estimator. It establishes the artifact contract that later execution backends must populate.

### Work completed

The new `lidarperf.bundle` package contains:

- immutable Pydantic records for result manifests, methods, datasets, environments, trials, metrics, resource measurements, and run-set aggregates;
- explicit bundle schema identity `lidarperf.result.v1`;
- exact/weak dataset fingerprint classes;
- trial success/failure semantics;
- conformance status metadata;
- protocol ID/version/content-hash references;
- canonical algorithm-configuration fingerprints using the existing LidarPerf canonical JSON hashing rules;
- a one-shot `ResultBundleWriter` that refuses to overwrite non-empty destinations;
- path-traversal prevention for bundle-relative paths;
- deterministic JSON serialization and LF line endings;
- SHA-256 checksums for every declared payload file except `checksums.sha256` itself;
- a canonical sorted `file_inventory` stored in `manifest.json`;
- `lidarperf verify <bundle>`.

The verifier checks:

- `manifest.json` schema validity;
- required top-level payloads;
- declared file inventory versus actual regular files;
- absence of symlink payloads;
- checksum entry completeness and exact SHA-256 matches;
- protocol identity/version/content hash against a freshly resolved `protocol.yaml`;
- manifest track against the resolved protocol;
- method identity against `method.json`;
- algorithm config canonical hash against `config/algorithm.yaml`;
- dataset identity/content hash consistency;
- measurement class consistency between manifest and environment record;
- numbered trial structure and trial indices;
- per-trial metrics/resources schema validity;
- aggregate success/failure counts against actual trial records;
- unexpected numbered trials beyond `manifest.trial_count`.

A weak dataset fingerprint is accepted as an internally valid artifact but reported as `VALID WITH WARNINGS`, preserving the distinction between artifact integrity and reproducibility strength.

### Bundle structure now enforced

```text
<result>.lperf/
├── manifest.json
├── protocol.yaml
├── method.json
├── dataset.json
├── environment.json
├── aggregate.json
├── config/
│   └── algorithm.yaml
├── trials/
│   └── 0001/
│       ├── trial.json
│       ├── metrics.json
│       ├── resources.json
│       ├── trajectory.tum
│       ├── stdout.log
│       └── stderr.log
└── checksums.sha256
```

`telemetry.parquet` remains optional and will be introduced when telemetry-producing backends exist.

### Immutability rule

The public writer refuses an existing non-empty output directory. Once finalization writes `manifest.json` and `checksums.sha256`, the writer cannot append more payloads.

The verifier also rejects undeclared extra payloads. A corrected benchmark result must therefore be emitted as a new bundle instead of silently mutating an already published one.

This gives the later research workflow an audit-friendly artifact model rather than an editable results directory.

### Configuration hashing decision

The checksum of `config/algorithm.yaml` protects exact file bytes, but the method-level `config_sha256` has a different purpose: semantic configuration identity.

Therefore `config_sha256` is calculated from parsed YAML/JSON through LidarPerf's canonical JSON representation. Merely reordering YAML keys does not change the configuration fingerprint, while changing a value does.

Tests explicitly cover both cases.

### Verification status semantics

The new verifier returns exactly three artifact-integrity states:

```text
VALID
VALID WITH WARNINGS
INVALID
```

The CLI exits with code 0 for the first two and code 2 for `INVALID`.

A `VALID` bundle means the artifact is internally consistent with its declared LidarPerf metadata. It does **not** mean the estimator is accurate or scientifically good; correctness/accuracy gates belong to later execution and regression layers.

### Local implementation bug caught before publication

The first bundle-model draft attempted to express safe relative paths using a regular expression with negative look-ahead assertions.

Pydantic v2 delegates these patterns to Rust's regex engine, which deliberately does not support look-around. Test collection therefore failed before any tests ran with a `SchemaError`.

**Fix:** replace regex look-around with an explicit `AfterValidator` using `PurePosixPath` plus checks for absolute paths, backslashes, duplicate separators, dot components, and parent traversal.

**Learning:** validation logic that depends on regex features must respect the regex engine actually used by the schema/runtime. For filesystem security invariants, explicit path-component validation is clearer and less engine-dependent than a compact look-around-heavy expression.

This failure happened entirely during local pre-publication validation and therefore did not create a red project CI run.


### Additional filesystem-safety review

After the first passing bundle implementation, a second review found two cases worth hardening before publication:

1. the writer used `pathlib.Path` normalization, which could silently normalize `nested/./file` and, on Linux, treat backslashes as literal filename characters rather than reject Windows-style path spelling;
2. an existing symlink to an empty directory could satisfy the writer's initial “directory exists and is empty” check and redirect bundle output outside the path the caller appeared to request.

**Fix:** bundle writer paths must already be canonical POSIX-relative spellings, backslashes are rejected, and both writer and verifier reject a symlink as the bundle root. Bundle payloads, the manifest, and the checksum file are also created with exclusive-create filesystem modes so the writer never replaces an entry that appears after initialization.

**Learning:** provenance containers should never silently normalize caller-supplied artifact paths, and an integrity writer must reason about symlinks explicitly rather than treating `is_dir()` as sufficient containment evidence.

### Local validation

After the path-validation fix and additional filesystem-safety self-review:

```text
66 passed
```

Additional checks:

- `compileall` succeeds for `src/` and `tests/`;
- no Python source/test line exceeds the configured 100-character Ruff line limit;
- tampering with a trajectory produces `CHECKSUM_MISMATCH`;
- adding an undeclared file produces `INVENTORY_EXTRA`;
- deleting a payload produces inventory/checksum failures;
- semantically changing algorithm YAML while refreshing file checksums still produces `CONFIG_HASH_MISMATCH`;
- reordering unchanged YAML keys remains valid because the semantic configuration hash is canonical;
- changing the manifest protocol hash while recomputing file checksums still produces `PROTOCOL_HASH_MISMATCH`;
- inconsistent aggregate trial counts are rejected;
- a weak dataset fingerprint produces `VALID WITH WARNINGS` rather than a false exact-reproducibility claim;
- the CLI returns exit code 2 for invalid bundles;
- writer paths reject parent traversal, Windows-style separators, dot-normalized aliases, and symlink bundle roots;
- verifier rejects a symlink presented as the bundle root;
- writer payload creation is exclusive and refuses a file created after writer initialization instead of replacing it.

### Pre-PR remote validation

A clean Ubuntu/Python 3.13 GitHub runner was used before opening the PR so the normal PR matrix would not become the first place we discover avoidable lint/toolchain problems.

The first remote validation attempt found exactly one Ruff issue: `UP017` in `tests/bundle/conftest.py`, where the test fixture used `timezone.utc` instead of Python 3.11+'s `datetime.UTC` alias. No project test ran in that attempt because Ruff correctly stopped the workflow first.

**Fix:** import `UTC` directly and use `tzinfo=UTC`. The second clean validation passed Ruff and all **66 tests** on Python 3.13.15.

This is precisely why Step 4 used a pre-PR validation branch: the small compatibility/style fix happened before the review PR and did not create a red PR CI run.

### Publication-workflow mistake

Before the validation workflow above, I attempted to combine validation and automatic engineering-log appending in one temporary GitHub Actions workflow. GitHub rejected that workflow before scheduling any jobs, so no project code, lint, or tests ran.

Rather than keep iterating on a nonessential logging workflow, I removed it and replaced it with a minimal validation-only workflow copied from the already proven Step 3 pattern. The living log is being updated directly after validation instead.

**Learning:** temporary automation used only to move documentation should not be coupled to the code-validation path. Keep pre-PR validation workflows minimal; update the durable engineering record separately after the validation result is known.

### Next action

Open the Step 4 PR and run the normal clean Python 3.11–3.13 GitHub Actions matrix. Any remote-only failure will be retained here rather than hidden.

After merge, Step 5 is host fingerprinting and `lidarperf doctor`.
