"""Regenerate checked-in JSON Schema artifacts from Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from lidarperf.spec import protocol_json_schema


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "schemas" / "protocol-v0.1.0.schema.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(protocol_json_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
