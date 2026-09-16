import json
import math
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lidarperf.cli import app
from lidarperf.export import (
    BencherExportError,
    build_bencher_export,
    export_report_to_bencher,
)
from lidarperf.report import build_report

STEP9 = Path("docs/validation/step9_kiss_hilti.lperf")
STEP10 = Path("docs/validation/step10_kiss_hilti_repeated.lperf")


def test_real_repeated_bundle_exports_current_bmf_shape() -> None:
    report = build_report(STEP10)
    export = build_bencher_export(STEP10)
    payload = export.bmf()

    assert export.alerts_suppressed is True
    assert export.benchmark_name.endswith("-bencher-ignore")
    assert report.dataset_content_sha256 is not None
    assert report.dataset_content_sha256[:12] in export.benchmark_name
    assert report.protocol_sha256[:12] in export.benchmark_name
    assert len(export.benchmark_name) <= 1024

    assert list(payload) == [export.benchmark_name]
    metrics = payload[export.benchmark_name]
    assert metrics["lidarperf-wall-time-s"]["value"] == pytest.approx(
        report.resources["wall_time_s"].median
    )
    assert metrics["lidarperf-cpu-time-s"]["value"] == pytest.approx(
        report.resources["cpu_time_s"].median
    )
    assert metrics["lidarperf-ape-translation-rmse-m"]["value"] == pytest.approx(
        report.metrics["ape.translation.rmse_m"].median
    )
    assert metrics["lidarperf-trial-success-ratio"]["value"] == 1.0
    assert metrics["lidarperf-output-translation-rmse-m"]["value"] == 0.0

    for measure, metric in metrics.items():
        assert len(measure) <= 64
        assert set(metric) == {"value"}
        assert math.isfinite(metric["value"])


def test_export_is_a_public_safe_subset_not_bundle_metadata_dump() -> None:
    report = build_report(STEP10)
    text = json.dumps(build_bencher_export(STEP10).bmf(), sort_keys=True)

    assert report.result_id not in text
    assert report.host_sha256 is not None
    assert report.host_sha256 not in text
    assert report.cpu_model is not None
    assert report.cpu_model not in text
    assert "process.log" not in text
    assert "trials/0001" not in text


def test_single_trial_bundle_uses_report_resource_fallback() -> None:
    report = build_report(STEP9)
    export = build_bencher_export(STEP9)

    assert export.metrics["lidarperf-wall-time-s"].value == pytest.approx(
        report.resources["wall_time_s"].median
    )
    assert export.metrics["lidarperf-trial-success-ratio"].value == 1.0
    assert "lidarperf-output-translation-rmse-m" not in export.metrics


def test_authoritative_controlled_report_does_not_suppress_bencher_alerts() -> None:
    report = build_report(STEP10).model_copy(
        update={
            "performance_authoritative": True,
            "measurement_class": "controlled",
            "failed_trials": 0,
        }
    )
    export = export_report_to_bencher(report)

    assert export.alerts_suppressed is False
    assert not export.benchmark_name.endswith("-bencher-ignore")
    assert export.benchmark_name.endswith("-controlled")


def test_failed_or_nonconformant_evidence_suppresses_alerts_even_if_marked_authoritative() -> None:
    report = build_report(STEP10).model_copy(
        update={
            "performance_authoritative": True,
            "measurement_class": "controlled",
            "conformance_status": "non_conformant",
            "failed_trials": 1,
        }
    )
    export = export_report_to_bencher(report)

    assert export.alerts_suppressed is True
    assert export.benchmark_name.endswith("-bencher-ignore")


def test_invalid_bundle_is_rejected() -> None:
    with pytest.raises(BencherExportError, match="invalid"):
        build_bencher_export(Path("does-not-exist.lperf"))


def test_cli_stdout_is_pure_bmf_json_and_notice_stays_on_stderr() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["export", "bencher", str(STEP10)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert len(payload) == 1
    benchmark_name = next(iter(payload))
    assert benchmark_name.endswith("-bencher-ignore")
    assert "alerts suppressed" in result.stderr


def test_cli_output_file_is_valid_bmf(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "bencher.json"
    result = runner.invoke(
        app,
        ["export", "bencher", str(STEP10), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload) == 1
    assert "Bencher JSON:" in result.stderr
