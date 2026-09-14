
### Final remote-document verification caught a second formatting defect

After the remote finalization workflow succeeded, `SPEC.md` was fetched back from the `foundation` branch instead of assuming the workflow output was correct. That verification caught two editorial remnants:

- the status line still ended with an unintended `**` delimiter because the normalization string itself repeated the original formatting mistake;
- the specification version still said `Draft 0.1.0` despite Gate 1 already being approved.

Neither affected benchmark semantics, but both are incorrect project-state metadata. They are being corrected to:

```text
Specification version: 0.1.0
Status: Approved for implementation — Gate 1 approved 2026-09-14.
```

**Learning:** verification must check the resulting content, not merely the success status of the automation that produced it. A green workflow proves execution success, not semantic correctness of the generated document.
