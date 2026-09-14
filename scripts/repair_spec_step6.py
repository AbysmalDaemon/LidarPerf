"""Repair known transfer corruption in SPEC.md and apply the Step 6 log-layout amendment."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

TARGET_SHA256 = "43e4b0360689f27380c57454e5372f4ea0b0854bd03ba3abec068bb90662ce7a"
EXPECTED_BLOCK_HASHES = (
    "830e542efa70d1b4096b26d6ec96e8b6f40d3ea10cdce9d249d729535a28af19",
    "c61e196f8049f55130c8c2e50828c5b52eea0249896e572a4119cd26373d9cbc",
    "6fe43b219154af1dc499d4ea2a004bb60e5b5f1489c977747961377712f43614",
    "7b58642ab5350ee67720afd5ce3e23c22ed7a836590f53f3ca04d796662a6f27",
    "e40d7afcc5ac9dcbabe9c8e2bc44b3f0b21549a9b2223726560fdbb19dd97167",
    "a22770c8271c3d154fc09dcc5b715557277a4bc64864b0d198623adcadb1cce5",
    "5965873ae4e9930ba51626208d89d26a826be3454012a5046f14e078d8b9a099",
    "a61ddce476d405cf31e1f455b4e43fd3fadac0f55a4c0295a266fe0bf4d6ae81",
    "99aae1a4c2be36711e9ea168660b6cde958da944473f0068e458bab8737ea2fe",
    "e066a97c1c37fd2f7a9fc12629b5291e5ef62e6693ae7e74c85dbc57eb2fd0cb",
    "43a77cf8977fc2c94145719454d7c7185ea83d752d3594ae63c3c73909842aa8",
    "71f380ff5090a53f59dd3226447e4188b2cf70fdc9cad5c21e0dcbc09ad31bf9",
    "f66402261574e96d3685380036855b196eac80e5517f20b6ca804ed7032b97ed",
    "8e82d59e2e503113b032120d1821b89b1fde81bec12017f94a538c1558e01535",
    "44406434c1a59fcbe4e4dd3125e474e091229a7719f16034772322cd77611041",
    "16e81bc9ebefddf4d7e77d7a41b4735618eb200c09ded4674c1660b201bb1a72",
    "fa30f1f4e6d8636f979c14742ee14fa564dabb75d8767641fbfce93ee00ec3bd",
    "857a4a059c68420ff5f5e1e95868008cdc925bb1b5db6248dce3eb366a438bc2",
    "eb5b4bf4b377f269eb471c04f064461075efb529d329728a56a24b93459eadee",
    "af8762118453914aa27afe986aa992e6fbb084da3f6cfbcf4959992c02e1b73b",
    "45a7feb7beadc8116aaa70045a4cbc0d13fd303ec8c0449965356ee626fcde01",
    "2ceb6b31472908f44e64041b45b5a5be6ceb37ce423e3aca445f47357193df2a",
)

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
    lines = text.splitlines(keepends=True)
    mismatches: list[str] = []
    for index, expected in enumerate(EXPECTED_BLOCK_HASHES):
        start = index * 100
        block = "".join(lines[start : start + 100]).encode("utf-8")
        observed = hashlib.sha256(block).hexdigest()
        if observed != expected:
            mismatches.append(f"{start + 1}-{min(start + 100, len(lines))}: {observed}")
    raise RuntimeError(
        f"repaired SPEC.md hash {actual} != canonical hash {TARGET_SHA256}; "
        f"mismatched blocks: {mismatches}"
    )

path.write_text(text, encoding="utf-8")
print(f"SPEC.md repaired and verified: {actual}")
