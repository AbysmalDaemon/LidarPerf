from __future__ import annotations

import pytest
from pydantic import ValidationError

from lidarperf.spec.models import BenchmarkProtocol


def test_valid_lo_protocol(lo_protocol_data: dict) -> None:
    protocol = BenchmarkProtocol.model_validate(lo_protocol_data)
    assert protocol.track.value == "lo"
    assert protocol.trajectory.pose.transform == "T_W_B"
    assert protocol.validity.temporal_coverage_min == 0.98


def test_valid_lio_protocol(lio_protocol_data: dict) -> None:
    protocol = BenchmarkProtocol.model_validate(lio_protocol_data)
    assert protocol.track.value == "lio"
    assert {sensor.value for sensor in protocol.sensors.required} == {"lidar", "imu"}


def test_lo_rejects_imu_runtime_input(lo_protocol_data: dict) -> None:
    lo_protocol_data["sensors"]["required"] = ["lidar", "imu"]
    lo_protocol_data["sensors"]["forbidden"] = [
        value for value in lo_protocol_data["sensors"]["forbidden"] if value != "imu"
    ]

    with pytest.raises(ValidationError, match="LO protocols must require exactly LiDAR"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_lio_rejects_missing_forbidden_external_source(lio_protocol_data: dict) -> None:
    lio_protocol_data["sensors"]["forbidden"].remove("gnss")

    with pytest.raises(ValidationError, match="must forbid: gnss"):
        BenchmarkProtocol.model_validate(lio_protocol_data)


def test_protocol_rejects_unknown_fields(lo_protocol_data: dict) -> None:
    lo_protocol_data["trajectory"]["mystery_alignment"] = "magic"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_scale_correction_is_forbidden(lo_protocol_data: dict) -> None:
    lo_protocol_data["trajectory"]["scale_correction"] = True

    with pytest.raises(ValidationError, match="forbid scale correction"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_fixed_lag_requires_maximum(lo_protocol_data: dict) -> None:
    lo_protocol_data["estimator_semantics"]["max_fixed_lag_seconds"] = None

    with pytest.raises(ValidationError, match="max_fixed_lag_seconds is required"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_exact_timestamp_association_rejects_tolerance(lo_protocol_data: dict) -> None:
    lo_protocol_data["trajectory"]["association"]["max_time_delta_ns"] = 1_000_000

    with pytest.raises(ValidationError, match="exact timestamp association"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_nearest_timestamp_association_requires_tolerance(lo_protocol_data: dict) -> None:
    lo_protocol_data["trajectory"]["association"] = {"mode": "nearest"}

    with pytest.raises(ValidationError, match="requires max_time_delta_ns"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_repetition_strength_must_be_monotonic(lo_protocol_data: dict) -> None:
    lo_protocol_data["repetition"]["publication_min_trials"] = 3

    with pytest.raises(ValidationError, match="exploratory <= controlled <= publication"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_relative_windows_must_be_in_increasing_order(lo_protocol_data: dict) -> None:
    lo_protocol_data["trajectory"]["relative_error_windows"] = [
        {
            "distance_m": 100.0,
            "pairing": "all_starts_nearest_reference_distance",
            "relative_tolerance": 0.1,
        },
        {
            "distance_m": 10.0,
            "pairing": "all_starts_nearest_reference_distance",
            "relative_tolerance": 0.1,
        },
    ]

    with pytest.raises(ValidationError, match="ordered by increasing distance"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_relative_windows_require_pairing_semantics(lo_protocol_data: dict) -> None:
    lo_protocol_data["trajectory"]["relative_error_windows"] = [{"distance_m": 10.0}]

    with pytest.raises(ValidationError, match="Field required"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_none_preprocessing_cannot_hide_parameters(lo_protocol_data: dict) -> None:
    lo_protocol_data["preprocessing"]["crop"] = {
        "owner": "none",
        "parameters": {"min_x": -10.0},
    }

    with pytest.raises(ValidationError, match="parameters must be empty"):
        BenchmarkProtocol.model_validate(lo_protocol_data)


def test_end_to_end_requires_explicit_cache_policy(lo_protocol_data: dict) -> None:
    lo_protocol_data["measurement"]["cache_policy"] = "not_applicable"

    with pytest.raises(ValidationError, match="requires an explicit I/O cache policy"):
        BenchmarkProtocol.model_validate(lo_protocol_data)
