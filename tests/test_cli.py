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


def test_compare_real_validation_bundles() -> None:
    result = runner.invoke(
        app,
        [
            "compare",
            "docs/validation/step9_kiss_hilti.lperf",
            "docs/validation/step10_kiss_hilti_repeated.lperf",
        ],
    )
    assert result.exit_code == 0
    assert "Accuracy comparable:    YES" in result.stdout
    assert "Performance comparable: NO" in result.stdout
    assert "NO STRICT PERFORMANCE RANKING" in result.stdout
    assert "ape.translation.rmse_m" in result.stdout
    assert "wall_time_s" in result.stdout


def test_compare_json_output() -> None:
    result = runner.invoke(
        app,
        [
            "compare",
            "docs/validation/step10_kiss_hilti_repeated.lperf",
            "docs/validation/step10_kiss_hilti_repeated.lperf",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert '"schema_version": "lidarperf.comparison.v1"' in result.stdout
    assert '"accuracy_comparable": true' in result.stdout
    assert '"performance_comparable": false' in result.stdout


def test_regress_real_hosted_evidence_is_not_comparable() -> None:
    result = runner.invoke(
        app,
        [
            "regress",
            "docs/validation/step9_kiss_hilti.lperf",
            "docs/validation/step10_kiss_hilti_repeated.lperf",
            "--policy",
            "docs/examples/regression_policy.example.yaml",
        ],
    )
    assert result.exit_code == 3
    assert "verdict:   NOT_COMPARABLE" in result.stdout
    assert "Step 11 performance comparability failed" in result.stdout


def test_regress_json_preserves_noncomparable_exit_code() -> None:
    result = runner.invoke(
        app,
        [
            "regress",
            "docs/validation/step9_kiss_hilti.lperf",
            "docs/validation/step10_kiss_hilti_repeated.lperf",
            "--policy",
            "docs/examples/regression_policy.example.yaml",
            "--json",
        ],
    )
    assert result.exit_code == 3
    assert '"schema_version": "lidarperf.regression.v1"' in result.stdout
    assert '"verdict": "NOT_COMPARABLE"' in result.stdout


def test_synthetic_generate(tmp_path) -> None:
    output = tmp_path / "synthetic"
    result = runner.invoke(
        app,
        [
            "synthetic",
            "generate",
            str(output),
            "--poses",
            "3",
            "--max-points",
            "8",
            "--motion-distortion",
        ],
    )

    assert result.exit_code == 0
    assert "GENERATED" in result.stdout
    assert "fixture_sha256:" in result.stdout
    assert (output / "manifest.json").is_file()
    assert (output / "ground_truth.tum").is_file()
    assert (output / "scans" / "index.json").is_file()
    assert len(list((output / "scans").glob("*.jsonl"))) == 3


def test_synthetic_generate_refuses_nonempty_directory(tmp_path) -> None:
    output = tmp_path / "synthetic"
    output.mkdir()
    (output / "keep.txt").write_text("do not overwrite", encoding="utf-8")

    result = runner.invoke(
        app,
        ["synthetic", "generate", str(output), "--poses", "2", "--max-points", "4"],
    )

    assert result.exit_code == 2
    assert "not empty" in result.stderr
    assert (output / "keep.txt").read_text(encoding="utf-8") == "do not overwrite"
