"""Validate a real evalio/KISS-ICP experiment with LidarPerf trajectory semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from lidarperf.backends.evalio import (
    evalio_version,
    expected_evalio_result_paths,
    load_evalio_trajectory,
)
from lidarperf.spec.models import BenchmarkProtocol
from lidarperf.trajectory import evaluate_trajectory


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _kiss_version() -> str:
    from evalio.pipelines import PipelineNotFound, get_pipeline

    pipeline = get_pipeline("kiss")
    if isinstance(pipeline, PipelineNotFound):
        raise RuntimeError("evalio installation does not contain the kiss pipeline")
    return str(pipeline.version())


def _validation_protocol(root: Path) -> BenchmarkProtocol:
    data = yaml.safe_load((root / "protocols/lo/se3_v1.yaml").read_text(encoding="utf-8"))
    # Hilti GT is higher-rate than LiDAR. Association tolerance is explicit and
    # intentionally belongs to this integration validation, not a hidden evaluator default.
    data["trajectory"]["association"] = {
        "mode": "nearest",
        "max_time_delta_ns": 10_000_000,
    }
    return BenchmarkProtocol.model_validate(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--dataset", default="hilti_2022/basement_2")
    parser.add_argument("--pipeline", default="kiss")
    parser.add_argument("--length", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    paths = expected_evalio_result_paths(
        args.results,
        dataset=args.dataset,
        pipeline=args.pipeline,
    )
    protocol = _validation_protocol(root)
    estimate = load_evalio_trajectory(paths.estimate, body_frame=protocol.trajectory.evaluation_frame)
    reference = load_evalio_trajectory(
        paths.ground_truth,
        body_frame=protocol.trajectory.evaluation_frame,
    )
    evaluation = evaluate_trajectory(estimate, reference, protocol)

    if len(estimate) < 20:
        raise RuntimeError(f"KISS produced too few poses for integration validation: {len(estimate)}")
    if evaluation.association.matched_pose_count < 20:
        raise RuntimeError(
            "too few KISS poses could be associated to Hilti ground truth: "
            f"{evaluation.association.matched_pose_count}"
        )
    if not evaluation.temporal_coverage_pass:
        raise RuntimeError(
            "KISS trajectory failed the LidarPerf temporal coverage gate: "
            f"{evaluation.association.temporal_coverage:.6f}"
        )
    if evaluation.ape_translation_m is None or evaluation.ape_rotation_deg is None:
        raise RuntimeError("required APE metrics were not produced")

    evidence = {
        "schema_version": "lidarperf.validation.evalio-kiss.v1",
        "validation_scope": "functional_integration_only",
        "performance_authoritative": False,
        "reason_performance_not_authoritative": (
            "GitHub-hosted runner; this validation proves estimator/data/trajectory integration only"
        ),
        "dataset": args.dataset,
        "requested_lidar_scans": args.length,
        "pipeline": args.pipeline,
        "evalio_version": evalio_version(),
        "kiss_version": _kiss_version(),
        "estimate_pose_count": len(estimate),
        "reference_pose_count": len(reference),
        "estimate_sha256": _sha256(paths.estimate),
        "ground_truth_sha256": _sha256(paths.ground_truth),
        "association_override": {
            "mode": "nearest",
            "max_time_delta_ns": 10_000_000,
        },
        "metrics": evaluation.metric_values(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
