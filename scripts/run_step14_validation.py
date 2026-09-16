"""Regenerate and validate the durable Step 14 Bencher export evidence."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

BUNDLE = Path("docs/validation/step10_kiss_hilti_repeated.lperf")
OUTPUT = Path("docs/validation/step14_kiss_hilti_bencher.json")


def main() -> None:
    completed = subprocess.run(
        ["lidarperf", "export", "bencher", str(BUNDLE)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if len(payload) != 1:
        raise RuntimeError("expected exactly one Bencher benchmark object")

    benchmark_name, measures = next(iter(payload.items()))
    if not benchmark_name.endswith("-bencher-ignore"):
        raise RuntimeError("hosted exploratory evidence must suppress Bencher alerts")
    if "alerts suppressed" not in completed.stderr:
        raise RuntimeError("CLI did not explain the authority guardrail on stderr")
    if not isinstance(measures, dict):
        raise RuntimeError("Bencher benchmark measures must be a JSON object")

    required = {
        "lidarperf-wall-time-s",
        "lidarperf-cpu-time-s",
        "lidarperf-peak-memory-bytes",
        "lidarperf-ape-translation-rmse-m",
        "lidarperf-ape-rotation-rmse-deg",
        "lidarperf-trial-success-ratio",
    }
    missing = required.difference(measures)
    if missing:
        raise RuntimeError(f"missing required Step 14 measures: {sorted(missing)}")

    wall = float(measures["lidarperf-wall-time-s"]["value"])
    if not math.isclose(wall, 3.5747101960000123, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"unexpected Step 10 wall-time median: {wall}")
    if float(measures["lidarperf-trial-success-ratio"]["value"]) != 1.0:
        raise RuntimeError("Step 10 success ratio must be 1.0")

    for measure_name, metric in measures.items():
        if len(measure_name) > 64:
            raise RuntimeError(f"Bencher measure name too long: {measure_name}")
        if set(metric) != {"value"}:
            raise RuntimeError(f"unexpected BMF fields for {measure_name}: {sorted(metric)}")
        if not math.isfinite(float(metric["value"])):
            raise RuntimeError(f"non-finite BMF value for {measure_name}")

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    forbidden = (
        "d76a6442-cda2-4718-bf8d-9ac9bfaf10d7",
        "8e1dde09caec98446dc98306bad670d96472614ab08c27cb8ae44c597daf5f30",
        "process.log",
        "trials/0001",
    )
    if any(item in text for item in forbidden):
        raise RuntimeError("Bencher export leaked nonessential result/host/local-path metadata")

    OUTPUT.write_text(text, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
