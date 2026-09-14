"""Repair known SPEC.md transfer corruption and apply the Step 6 log-layout amendment."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

path = Path("SPEC.md")
text = path.read_text(encoding="utf-8")

regex_repairs = (
    (r"(  fixed_lag_seconds: 1\.0)\nb`{2,3}\n", r"\1\n```\n"),
    (r"(  temporal_mode: offline_noncausal)\nb`{2,3}\n", r"\1\n```\n"),
)
for pattern, replacement in regex_repairs:
    text, count = re.subn(pattern, replacement, text, count=1)
    if count not in (0, 1):
        raise RuntimeError(f"unexpected match count for transfer-corruption pattern {pattern!r}: {count}")

for old, new in (
    ("## 9.2 `online_fixed_lagg\n", "## 9.2 `online_fixed_lag`\n"),
    ("body frame bB`", "body frame `B`"),
    ("- repeatition policy", "- repetition policy"),
):
    if old in text:
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
if old_bundle in text:
    text = text.replace(old_bundle, new_bundle, 1)
elif new_bundle not in text:
    raise RuntimeError("could not locate either supported trial-log tree layout")

layout_rule = """Each trial MUST contain exactly one execution-log layout:

- `process.log` when the execution backend exposes a single combined stdout/stderr stream; or
- both `stdout.log` and `stderr.log` when the backend can preserve the streams separately.

The two layouts are mutually exclusive. LidarPerf MUST NOT relabel a combined stream as stdout or fabricate an empty stderr file merely to satisfy an artifact shape. This rule preserves measurement provenance across backends such as BenchExec, whose `runexec --output` file contains both command stdout and stderr.

"""
archive_line = "An archived transport format MAY be introduced later.\n"
if layout_rule not in text:
    if text.count(archive_line) != 1:
        raise RuntimeError("expected exactly one archived-transport sentence")
    text = text.replace(archive_line, layout_rule + archive_line, 1)

for forbidden in (
    "fixed_lag_seconds: 1.0\nb``",
    "temporal_mode: offline_noncausal\nb``",
    "online_fixed_lagg",
    "body frame bB`",
    "repeatition policy",
):
    if forbidden in text:
        raise RuntimeError(f"SPEC repair left known corruption behind: {forbidden!r}")

if "process.log              # combined stdout + stderr" not in text:
    raise RuntimeError("Step 6 process.log layout amendment is missing")
if layout_rule not in text:
    raise RuntimeError("Step 6 execution-log provenance rule is missing")

path.write_text(text, encoding="utf-8")
actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
print(f"SPEC.md repaired successfully: {actual}")
