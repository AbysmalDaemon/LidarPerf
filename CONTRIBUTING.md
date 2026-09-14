# Contributing to LidarPerf

LidarPerf values **benchmark correctness over feature count**.

Before proposing a change that affects sensor permissions, timing boundaries, trajectory semantics, metrics, tuning policy, conformance, or comparability, read [`SPEC.md`](SPEC.md). Behavioral protocol changes require explicit versioning; they must not be introduced as incidental implementation details.

## Local setup

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
```

## Pull requests

Keep pull requests narrowly scoped. Explain benchmark-semantic changes explicitly. Tests should target failure modes, not only happy paths.

Do not vendor external algorithm implementations without a compelling reason and a license review. Prefer dependencies/adapters.

## Research integrity

Do not silently discard failed trials, alter benchmark settings after seeing favorable results, or change metric semantics without updating the protocol. Reproducibility and provenance are product requirements, not optional documentation.
