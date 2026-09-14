"""Repair known transfer corruption in SPEC.md and apply the Step 6 log-layout amendment."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

TARGET_SHA256 = "43e4b0360689f27380c57454e5372f4ea0b0854bd03ba3abec068bb90662ce7a"

path = Path("SPEC.md")
text = path.read_text(encoding="utf-8")

regex_repairs = (
    (r"(  fixed_lag_seconds: 1\.0)\nb`{2,3}\n", r"\1\n```\n"),
    (r"(  temporal_mode: offline_noncausal)\nb`{2,3}\n", r"\1\n```\n"),
)
for pattern, replacement in regex_repairs:
    text, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"expected exactly one match for transfer-corruption pattern {pattern!r}")

replacements = (
    ("## 9.2 `online_fixed_lagg\n", "## 9.2 `online_fixed_lag`\n"),
    ("body frame bB`", "body frame `B`"),
    ("- repeatition policy", "- repetition policy"),
)
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one occurrence of {old!r}, found {count}")
    text = text.replace(old, new, 1)

old_bundle = """│   │   ├── telemetry.parquet        # optional
│   │   ├── stdout.log
│   │   └── stderr.log
│   ├── 0002/
"""
new_bundle = """│   │   ├── telemetry.parquet        # optional
│   │   └── process.log              # combined stdout + stderr
│   ├── 0002/
"""
if text.count(old_bundle) != 1:
    raise RuntimeError("expected exactly one canonical pre-Step-6 trial-log tree")
text = text.replace(old_bundle, new_bundle, 1)

old_archive = "An archived transport format MAY be introduced later.\n"
new_archive = """Each trial MUST contain exactly one execution-log layout:

- `process.log` when the execution backend exposes a single combined stdout/stderr stream; or
- both `stdout.log` and `stderr.log` when the backend can preserve the streams separately.

The two layouts are mutually exclusive. LidarPerf MUST NOT relabel a combined stream as stdout or fabricate an empty stderr file merely to satisfy an artifact shape. This rule preserves measurement provenance across backends such as BenchExec, whose `runexec --output` file contains both command stdout and stderr.

An archived transport format MAY be introduced later.
"""
if text.count(old_archive) != 1:
    raise RuntimeError("expected exactly one archived-transport sentence")
text = text.replace(old_archive, new_archive, 1)

actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
if actual != TARGET_SHA256:
    raise RuntimeError(f"repaired SPEC.md hash {actual} != canonical hash {TARGET_SHA256}")

path.write_text(text, encoding="utf-8")
print(f"SPEC.md repaired and verified: {actual}")
