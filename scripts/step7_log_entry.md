
---

## Project execution log — 2026-09-14 — Step 7 trajectory validity and metrics

**Status:** implementation finalized on `trajectory-metrics` after full pre-PR lint/test validation. Pull-request CI remains the cross-version merge gate.

### Goal

Implement the first protocol-scoped trajectory evaluation layer: canonical trajectory loading, structural validity, timestamp association, rigid alignment, coverage accounting, APE-style accuracy, and explicitly defined distance-window relative pose errors. Keep all metric semantics visible in the protocol/result keys rather than hiding evaluator defaults.

### Work completed

Step 7 adds:

- canonical in-memory `T_W_B` trajectories with signed int64 nanosecond timestamps;
- deterministic TUM parsing/serialization with decimal timestamp conversion rather than binary-float timestamp rounding;
- structural validation for nonempty trajectories, finite translations, unit rotations, invalid-pose counts, duplicate/non-increasing timestamps, and declared body frame;
- `exact`, `nearest`, and `interpolate_reference` association modes driven by protocol data;
- bounded nearest-neighbor association with deterministic tie-breaking;
- reference interpolation using linear translation plus shortest-arc quaternion SLERP, with extrapolation forbidden and reference gaps bounded;
- explicit temporal and distance coverage accounting;
- rigid `none`, `origin`, and full-trajectory SE(3) alignment, with no scale correction;
- translation and rotation APE summaries under the declared alignment;
- reference-distance-window relative pose error with translation metres, rotation degrees, translation percent, and rotation degrees/metre;
- semantic metric keys such as `ape.translation.rmse_m` and `rpe.distance_10m.translation.rmse_m`, never naked `ATE`/`RPE` fields;
- explicit representation of unavailable relative-error windows instead of fabricated zero errors;
- a NumPy runtime dependency for vectorized trajectory mathematics;
- unit tests covering parsing, timestamp precision, structural failures, association/interpolation, alignment, RPE, coverage, unavailable windows, and metric naming.

### Protocol gap found and closed before release

The approved `SPEC.md` already stated that a distance-window relative error's **exact pairing/tolerance rule is protocol data**, but the v0.1 Pydantic schema and reference YAML documents only stored `distance_m`. That meant two evaluators could both claim the same protocol identity while choosing materially different RPE pairs.

Step 7 closes that gap by making both fields mandatory:

```yaml
relative_error_windows:
  - distance_m: 10.0
    pairing: all_starts_nearest_reference_distance
    relative_tolerance: 0.1
```

The implemented pairing rule is now normative and explicit:

1. compute cumulative path length on the associated reference trajectory;
2. consider every reference pose as a start;
3. select the later endpoint closest to the requested reference distance;
4. break equal-distance ties toward the earlier endpoint;
5. accept only when the distance mismatch is within the declared relative tolerance;
6. permit overlapping windows;
7. retain pair count and actual accepted-distance statistics.

If no valid pair exists, the metric is unavailable rather than zero.

Because these protocols are still pre-release/pre-alpha and have not been published as immutable released protocol versions, this correction remains version `1` but intentionally changes the canonical protocol content hashes. Once a protocol is released, equivalent semantic changes must use a new protocol version.

### Alignment decision

The generic metric profile uses full-trajectory rigid SE(3) alignment with **no scale correction**, matching the approved metric-scale LO/LIO semantics. The implementation refuses an underdetermined SE(3) fit (for example a static or collinear position trajectory) instead of silently inventing an arbitrary rotation that would make rotation APE ambiguous.

### Structural validity and disclosure

Parsing and structural validation are deliberately separate. A parseable TUM pose containing NaN/Inf is retained long enough for validation to count and report the invalid pose. LidarPerf does not silently drop such poses before metrics. Metric evaluation itself refuses structurally invalid trajectories.

### Coverage decision

Temporal coverage is the fraction of reference time span covered by the matched estimator span. Distance coverage is the matched-reference path length divided by full reference path length where a reference path distance exists. Both are retained alongside matched/unmatched pose counts. The protocol's temporal coverage threshold remains the accuracy/performance gate.

### Validation strategy and learnings

The development container could not clone GitHub because outbound GitHub DNS/network access is unavailable there. This is an environment limitation, not a project failure. The trajectory core was therefore exercised in an isolated local module harness before publication, then the complete repository was validated remotely only after the branch was assembled.

Before opening the PR, a review of `SPEC.md` against the implementation also caught the missing distance-coverage output required by section 24. It was added before the final validation run rather than deferred to another corrective PR.

A methodological cross-check of existing trajectory-evaluation conventions was used only to challenge our assumptions; no external evaluator source code is vendored or copied. LidarPerf's pairing semantics remain independently implemented and, crucially, encoded in protocol data.

**Learning:** trajectory metrics are not identified by labels like “ATE” and “RPE.” Association, alignment, scale, pairing, tolerance, body frame, and coverage semantics must all be explicit if a result is supposed to remain comparable months later.

**Learning:** generated protocol JSON Schema remains machine-owned output. The schema is regenerated from the modified Pydantic model under the pinned development toolchain and tested for exact equality rather than edited by hand.

### Next action

Open PR #7 and require the normal Python 3.11/3.12/3.13 CI matrix to pass. After merge, Step 8 is the first real external execution integration through evalio, beginning with a KISS-ICP end-to-end path.
