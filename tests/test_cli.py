from typer.testing import CliRunner

from lidarperf import __version__
from lidarperf.cli import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"lidarperf {__version__}"


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Conformance-aware performance regression testing" in result.stdout


def test_protocol_validate_valid_file() -> None:
    result = runner.invoke(app, ["protocol", "validate", "protocols/lo/se3_v1.yaml"])
    assert result.exit_code == 0
    assert "VALID" in result.stdout
    assert "lidarperf/lo-se3@1" in result.stdout
    assert "track: lo" in result.stdout
    assert "sha256:" in result.stdout


def test_protocol_validate_invalid_file(tmp_path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("spec_version: 0.1.0\ntrack: lo\n", encoding="utf-8")

    result = runner.invoke(app, ["protocol", "validate", str(path)])
    assert result.exit_code == 2
    assert "INVALID:" in result.stderr
