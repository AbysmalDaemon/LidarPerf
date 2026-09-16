"""Generate durable Step 13 report evidence from committed real validation bundles."""

from __future__ import annotations

from pathlib import Path

from lidarperf.report import BundleReport, write_report

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "docs/validation/step10_kiss_hilti_repeated.lperf"
COMPARISON = ROOT / "docs/validation/step11_compare_step9_step10.json"
HTML = ROOT / "docs/validation/step13_kiss_hilti_report.html"
JSON = ROOT / "docs/validation/step13_kiss_hilti_report.json"


def main() -> None:
    report = write_report(
        BUNDLE,
        html_path=HTML,
        json_path=JSON,
        comparison_path=COMPARISON,
    )
    assert report.schema_version == "lidarperf.report.v1"
    assert report.measurement_class == "exploratory"
    assert report.performance_authoritative is False
    assert report.successful_trials == 5
    assert report.failed_trials == 0
    assert report.warmup_trials == 1
    assert report.trajectory_pose_count == 120
    assert report.comparison is not None
    assert report.comparison.accuracy_comparable is True
    assert report.comparison.performance_comparable is False
    assert report.resources["wall_time_s"].median == 3.5747101960000123
    assert report.metrics["ape.translation.rmse_m"].median == 0.33748229509746835

    loaded = BundleReport.model_validate_json(JSON.read_text(encoding="utf-8"))
    assert loaded == report
    html = HTML.read_text(encoding="utf-8")
    assert "NON-AUTHORITATIVE" in html
    assert "<svg" in html
    assert "https://" not in html
    assert "http://" not in html
    assert "<script" not in html.lower()
    print(JSON)
    print(HTML)


if __name__ == "__main__":
    main()
