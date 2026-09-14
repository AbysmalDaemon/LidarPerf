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
