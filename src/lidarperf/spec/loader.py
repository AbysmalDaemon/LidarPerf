"""Load, validate, fingerprint, and export LidarPerf protocol documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .canonical import sha256_fingerprint
from .models import BenchmarkProtocol, ResolvedProtocol


class ProtocolLoadError(ValueError):
    """Raised when a protocol file cannot be parsed or validated."""


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProtocolLoadError(f"unable to read protocol file {path}: {exc}") from exc

    try:
        if path.suffix.lower() == ".json":
            value = json.loads(text)
        else:
            value = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ProtocolLoadError(f"unable to parse protocol file {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise ProtocolLoadError(f"protocol file {path} must contain a top-level mapping/object")
    return value


def resolve_protocol_data(data: dict[str, Any]) -> ResolvedProtocol:
    """Validate in-memory protocol data and attach its canonical SHA-256 fingerprint."""

    try:
        document = BenchmarkProtocol.model_validate(data)
    except ValidationError as exc:
        raise ProtocolLoadError(str(exc)) from exc

    return ResolvedProtocol(
        document=document,
        resolved_sha256=sha256_fingerprint(document),
    )


def load_protocol(path: str | Path) -> ResolvedProtocol:
    """Load a YAML/JSON protocol file, validate it, and compute its content fingerprint."""

    source = Path(path)
    return resolve_protocol_data(_load_mapping(source))


def protocol_json_schema() -> dict[str, Any]:
    """Return the JSON Schema corresponding to the current protocol model."""

    return BenchmarkProtocol.model_json_schema()
