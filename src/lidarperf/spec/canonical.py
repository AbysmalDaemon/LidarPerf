"""Deterministic serialization and hashing for benchmark protocol identity."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel


def _canonicalize(value: Any) -> Any:
    """Convert supported values into a deterministic JSON-compatible structure.

    Mapping keys are sorted during JSON serialization. Sets are semantically unordered,
    so they are converted to a list sorted by their canonical JSON representation.
    """

    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="python", exclude_none=False))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        items = [_canonicalize(item) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ),
        )
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes used for LidarPerf content hashes."""

    normalized = _canonicalize(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_fingerprint(value: Any) -> str:
    """Return a lowercase SHA-256 hex digest for a canonicalized value."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
