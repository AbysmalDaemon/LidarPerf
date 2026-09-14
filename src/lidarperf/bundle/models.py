"""Versioned models for portable LidarPerf result bundles."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from lidarperf.spec.enums import MeasurementClass, Track

BUNDLE_SCHEMA_VERSION = "lidarperf.result.v1"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


def _validate_safe_relative_path(value: str) -> str:
    """Require canonical POSIX paths rooted inside a bundle directory."""

    if "\\" in value or value.startswith("/") or "//" in value:
        raise ValueError("path must be a canonical bundle-relative POSIX path")
    path = PurePosixPath(value)
    if value in {"", "."} or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path must not contain empty, dot, or parent components")
    if path.as_posix() != value:
        raise ValueError("path must use canonical POSIX spelling")
    return value


SafeRelativePath = Annotated[
    str,
    StringConstraints(min_length=1),
    AfterValidator(_validate_safe_relative_path),
]


class StrictFrozenModel(BaseModel):
    """Immutable model base used by bundle metadata records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ConformanceStatus(StrEnum):
    """Overall conformance state of a produced result bundle."""

    CONFORMANT = "conformant"
    CONFORMANT_WITH_WARNINGS = "conformant_with_warnings"
    NON_CONFORMANT = "non_conformant"


class TrialStatus(StrEnum):
    """Execution outcome of one benchmark trial."""

    SUCCESS = "success"
    FAILED = "failed"


class DatasetFingerprintClass(StrEnum):
    """Strength of dataset identity evidence."""

    EXACT = "exact"
    WEAK = "weak"


class ProtocolReference(StrictFrozenModel):
    """Identity and content fingerprint of the benchmark protocol."""

    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    resolved_sha256: str = Field(pattern=SHA256_PATTERN)


class MethodSourceRecord(StrictFrozenModel):
    """Source provenance for an estimator implementation."""

    repository: str | None = None
    commit: str | None = None
    tag: str | None = None
    dirty: bool = False
    patch_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def patch_matches_dirty_state(self) -> Self:
        if not self.dirty and self.patch_sha256 is not None:
            raise ValueError("patch_sha256 must be omitted when dirty is false")
        return self


class MethodRecord(StrictFrozenModel):
    """Estimator identity, configuration, source, and build provenance."""

    schema_version: Literal["lidarperf.method.v1"] = "lidarperf.method.v1"
    name: str = Field(min_length=1)
    version: str | None = None
    source: MethodSourceRecord = Field(default_factory=MethodSourceRecord)
    config_file: Literal["config/algorithm.yaml"] = "config/algorithm.yaml"
    config_sha256: str = Field(pattern=SHA256_PATTERN)
    build: dict[str, JsonValue] = Field(default_factory=dict)


class DatasetRecord(StrictFrozenModel):
    """Dataset and ground-truth provenance captured by a result bundle."""

    schema_version: Literal["lidarperf.dataset.v1"] = "lidarperf.dataset.v1"
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    sequence: str = Field(min_length=1)
    fingerprint_class: DatasetFingerprintClass
    content_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    manifest_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    ground_truth_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def exact_fingerprint_has_content_digest(self) -> Self:
        if self.fingerprint_class == DatasetFingerprintClass.EXACT and self.content_sha256 is None:
            raise ValueError("exact dataset fingerprints require content_sha256")
        return self


class EnvironmentRecord(StrictFrozenModel):
    """Execution-environment and host metadata known when the result was produced."""

    schema_version: Literal["lidarperf.environment.v1"] = "lidarperf.environment.v1"
    measurement_class: MeasurementClass
    host: dict[str, JsonValue] = Field(default_factory=dict)
    software: dict[str, JsonValue] = Field(default_factory=dict)
    execution: dict[str, JsonValue] = Field(default_factory=dict)


class TrialRecord(StrictFrozenModel):
    """Execution outcome for one numbered trial."""

    schema_version: Literal["lidarperf.trial.v1"] = "lidarperf.trial.v1"
    trial_index: int = Field(ge=1)
    status: TrialStatus
    exit_code: int | None = None
    timed_out: bool = False

    @model_validator(mode="after")
    def success_is_clean(self) -> Self:
        if self.status == TrialStatus.SUCCESS:
            if self.timed_out:
                raise ValueError("successful trials cannot be marked timed_out")
            if self.exit_code != 0:
                raise ValueError("successful trials require exit_code=0")
        return self


class MetricsRecord(StrictFrozenModel):
    """Protocol-scoped metrics for one trial."""

    schema_version: Literal["lidarperf.metrics.v1"] = "lidarperf.metrics.v1"
    values: dict[str, JsonValue] = Field(default_factory=dict)


class ResourcesRecord(StrictFrozenModel):
    """Measured execution resources for one trial."""

    schema_version: Literal["lidarperf.resources.v1"] = "lidarperf.resources.v1"
    values: dict[str, JsonValue] = Field(default_factory=dict)


class AggregateRecord(StrictFrozenModel):
    """Run-set outcome counts plus aggregate metric summaries."""

    schema_version: Literal["lidarperf.aggregate.v1"] = "lidarperf.aggregate.v1"
    successful_trials: int = Field(ge=0)
    failed_trials: int = Field(ge=0)
    metrics: dict[str, JsonValue] = Field(default_factory=dict)


class ResultManifestCore(StrictFrozenModel):
    """Manifest fields known before the writer discovers the final file inventory."""

    lidarperf_version: str = Field(min_length=1)
    result_id: UUID
    created_at: datetime
    protocol: ProtocolReference
    track: Track
    method_name: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    dataset_content_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    trial_count: int = Field(ge=1)
    measurement_class: MeasurementClass
    conformance_status: ConformanceStatus

    @model_validator(mode="after")
    def created_at_is_timezone_aware(self) -> Self:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include an explicit timezone offset")
        return self


class ResultManifest(ResultManifestCore):
    """Top-level immutable manifest for one LidarPerf result bundle."""

    schema_version: Literal[BUNDLE_SCHEMA_VERSION] = BUNDLE_SCHEMA_VERSION
    file_inventory: tuple[SafeRelativePath, ...]

    @model_validator(mode="after")
    def inventory_is_canonical(self) -> Self:
        inventory = list(self.file_inventory)
        if inventory != sorted(inventory):
            raise ValueError("file_inventory must be sorted")
        if len(inventory) != len(set(inventory)):
            raise ValueError("file_inventory must not contain duplicates")
        if "checksums.sha256" in inventory:
            raise ValueError("checksums.sha256 must not checksum itself")
        if "manifest.json" not in inventory:
            raise ValueError("file_inventory must include manifest.json")
        return self
