import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lidarperf.cli import app
from lidarperf.regression import RegressionPolicy, RegressionVerdict, regress_bundles
from lidarperf.report import (
    BundleReport,
    ReportError,
    build_report,
    render_html,
    write_report,
)

STEP9 = Path("docs/validation/step9_kiss_hilti.lperf")
STEP10 = Path("docs/validation/step10_kiss_hilti_repeated.lperf")
STEP11 = Path("docs/validation/step11_compare_step9_step10.json")


def test_build_report_from_real_repeated_bundle() -> None:
    report = build_report(STEP10)

    assert report.schema_version == "lidarperf.report.v1"
    assert report.measurement_class == "exploratory"
    assert report.conformance_status == "conformant"
    assert report.performance_authoritative is False
    assert report.trial_count == 5
    assert report.successful_trials == 5
    assert report.failed_trials == 0
    assert report.warmup_trials == 1
    assert report.trajectory_pose_count == 120
    assert report.metrics["ape.translation.rmse_m"].median == pytest.approx(
        0.33748229509746835
    )
    assert report.resources["wall_time_s"].median == pytest.approx(3.5747101960000123)
    translation_repeatability = report.repeatability["translation_pairwise_rmse_m"]
    assert isinstance(translation_repeatability, dict)
    assert translation_repeatability["median"] == 0.0
    assert any("non-authoritative" in warning for warning in report.warnings)


def test_report_writes_portable_html_json_and_comparison_context(tmp_path: Path) -> None:
    html_path = tmp_path / "report.html"
    json_path = tmp_path / "report.json"

    report = write_report(
        STEP10,
        html_path=html_path,
        json_path=json_path,
        comparison_path=STEP11,
    )

    loaded = BundleReport.model_validate_json(json_path.read_text(encoding="utf-8"))
    assert loaded == report
    assert loaded.comparison is not None
    assert loaded.comparison.accuracy_comparable is True
    assert loaded.comparison.performance_comparable is False

    html = html_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in html.lower()
    assert "<svg" in html
    assert "NON-AUTHORITATIVE" in html
    assert "Accuracy comparable" in html
    assert ">YES<" in html
    assert "Performance comparable" in html
    assert ">NO<" in html
    assert "https://" not in html
    assert "http://" not in html
    assert "<script" not in html.lower()


def test_report_attaches_versioned_regression_context(tmp_path: Path) -> None:
    regression = regress_bundles(STEP9, STEP10, policy=RegressionPolicy())
    assert regression.verdict == RegressionVerdict.NOT_COMPARABLE
    regression_path = tmp_path / "regression.json"
    regression_path.write_text(regression.model_dump_json(indent=2), encoding="utf-8")
    html_path = tmp_path / "with-regression.html"

    report = write_report(STEP10, html_path=html_path, regression_path=regression_path)

    assert report.regression is not None
    assert report.regression.verdict == RegressionVerdict.NOT_COMPARABLE
    html = html_path.read_text(encoding="utf-8")
    assert "Regression context" in html
    assert "NOT_COMPARABLE" in html


def test_report_escapes_metadata_in_html() -> None:
    report = build_report(STEP10).model_copy(
        update={"method_name": "<script>alert('report')</script>"}
    )

    html = render_html(report, ())

    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


def test_report_rejects_invalid_bundle(tmp_path: Path) -> None:
    with pytest.raises(ReportError, match="bundle .* is invalid"):
        build_report(tmp_path / "missing.lperf")


def test_report_rejects_unrelated_comparison(tmp_path: Path) -> None:
    comparison = json.loads(STEP11.read_text(encoding="utf-8"))
    comparison["baseline_result_id"] = "unrelated-baseline"
    comparison["candidate_result_id"] = "unrelated-candidate"
    comparison_path = tmp_path / "comparison.json"
    comparison_path.write_text(json.dumps(comparison), encoding="utf-8")

    with pytest.raises(ReportError, match="does not reference this result bundle"):
        build_report(STEP10, comparison_path=comparison_path)


def test_report_supports_single_trial_bundle_resource_fallback() -> None:
    report = build_report(STEP9)

    assert report.trial_count == 1
    assert report.successful_trials == 1
    assert report.resources["wall_time_s"].count == 1
    assert report.resources["wall_time_s"].median == pytest.approx(3.5891886269999986)


def test_report_cli_writes_both_outputs(tmp_path: Path) -> None:
    runner = CliRunner()
    html_path = tmp_path / "step10.html"
    json_path = tmp_path / "step10.json"
    result = runner.invoke(
        app,
        [
            "report",
            str(STEP10),
            "--html",
            str(html_path),
            "--json",
            str(json_path),
            "--comparison",
            str(STEP11),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "LidarPerf report" in result.stdout
    assert "performance authority: NON-AUTHORITATIVE" in result.stdout
    assert html_path.is_file()
    assert json_path.is_file()
