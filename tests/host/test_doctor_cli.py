import json

from typer.testing import CliRunner

from lidarperf.cli import app

runner = CliRunner()


def test_doctor_json_smoke() -> None:
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "lidarperf.doctor.v1"
    assert payload["snapshot"]["schema_version"] == "lidarperf.host.v1"
    assert len(payload["snapshot"]["host_sha256"]) == 64
    assert "exploratory" in payload["eligible_measurement_classes"]


def test_doctor_missing_data_path_exits_nonzero(tmp_path) -> None:
    missing = tmp_path / "does-not-exist"
    result = runner.invoke(app, ["doctor", "--data-path", str(missing)])
    assert result.exit_code == 2
    assert "ERROR [DATA_PATH_MISSING]" in result.stdout
