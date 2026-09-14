from __future__ import annotations

import json
from pathlib import Path

import pytest

from lidarperf.spec import (
    ProtocolLoadError,
    load_protocol,
    protocol_json_schema,
    resolve_protocol_data,
)

ROOT = Path(__file__).resolve().parents[2]


def test_load_lo_protocol_and_fingerprint() -> None:
    resolved = load_protocol(ROOT / "protocols/lo/se3_v1.yaml")

    assert resolved.document.protocol.id == "lidarperf/lo-se3"
    assert len(resolved.resolved_sha256) == 64


def test_load_lio_protocol_and_fingerprint() -> None:
    resolved = load_protocol(ROOT / "protocols/lio/se3_v1.yaml")

    assert resolved.document.protocol.id == "lidarperf/lio-se3"
    assert len(resolved.resolved_sha256) == 64


def test_equivalent_sensor_set_order_has_same_protocol_hash(lo_protocol_data: dict) -> None:
    first = resolve_protocol_data(lo_protocol_data)
    lo_protocol_data["sensors"]["forbidden"] = list(
        reversed(lo_protocol_data["sensors"]["forbidden"])
    )
    second = resolve_protocol_data(lo_protocol_data)

    assert first.resolved_sha256 == second.resolved_sha256


def test_semantic_change_changes_protocol_hash(lo_protocol_data: dict) -> None:
    first = resolve_protocol_data(lo_protocol_data)
    lo_protocol_data["validity"]["temporal_coverage_min"] = 0.99
    second = resolve_protocol_data(lo_protocol_data)

    assert first.resolved_sha256 != second.resolved_sha256


def test_invalid_yaml_is_wrapped(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("track: [", encoding="utf-8")

    with pytest.raises(ProtocolLoadError, match="unable to parse protocol file"):
        load_protocol(path)


def test_top_level_sequence_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "not-a-protocol.yaml"
    path.write_text("- lo\n- lio\n", encoding="utf-8")

    with pytest.raises(ProtocolLoadError, match="top-level mapping"):
        load_protocol(path)


def test_checked_in_json_schema_matches_model() -> None:
    schema_path = ROOT / "schemas/protocol-v0.1.0.schema.json"
    checked_in = json.loads(schema_path.read_text(encoding="utf-8"))

    assert checked_in == protocol_json_schema()


def test_resolved_protocol_rejects_incorrect_hash(lo_protocol_data: dict) -> None:
    from pydantic import ValidationError

    from lidarperf.spec.models import BenchmarkProtocol, ResolvedProtocol

    document = BenchmarkProtocol.model_validate(lo_protocol_data)
    with pytest.raises(ValidationError, match="does not match"):
        ResolvedProtocol(document=document, resolved_sha256="0" * 64)
