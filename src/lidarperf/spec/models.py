"""Pydantic models for the LidarPerf benchmark protocol specification."""

from __future__ import annotations

import re
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from .canonical import sha256_fingerprint
from .enums import (
    AlignmentMode,
    CachePolicy,
    MeasurementClass,
    MotionCompensationInputState,
    MotionSource,
    PreprocessingOwner,
    Sensor,
    TemporalMode,
    TimestampAssociationMode,
    TimingScope,
    Track,
    TuningClass,
)

SPEC_VERSION = "0.1.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ProtocolId = Annotated[str, StringConstraints(pattern=r"^lidarperf/[a-z0-9][a-z0-9._/-]*$")]


class StrictModel(BaseModel):
    """Base model for versioned protocol data.

    Unknown fields are rejected so spelling errors cannot silently alter benchmark semantics.
    Models are immutable after validation to discourage accidental protocol mutation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProtocolIdentity(StrictModel):
    """Human-readable identity of an immutable released protocol."""

    id: ProtocolId
    version: int = Field(ge=1)


class SensorPolicy(StrictModel):
    """Runtime sensor/information policy for an estimator track."""

    required: frozenset[Sensor]
    optional: frozenset[Sensor] = frozenset()
    forbidden: frozenset[Sensor]

    @model_validator(mode="after")
    def disjoint_sets(self) -> Self:
        overlaps = {
            "required_optional": self.required & self.optional,
            "required_forbidden": self.required & self.forbidden,
            "optional_forbidden": self.optional & self.forbidden,
        }
        nonempty = {name: values for name, values in overlaps.items() if values}
        if nonempty:
            raise ValueError(f"sensor policy sets must be disjoint: {nonempty}")
        return self


class EstimatorSemanticsPolicy(StrictModel):
    """Temporal estimator modes permitted by a protocol."""

    allowed_modes: frozenset[TemporalMode]
    max_fixed_lag_seconds: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def fixed_lag_consistency(self) -> Self:
        fixed_lag_allowed = TemporalMode.ONLINE_FIXED_LAG in self.allowed_modes
        if fixed_lag_allowed and self.max_fixed_lag_seconds is None:
            raise ValueError(
                "max_fixed_lag_seconds is required when online_fixed_lag is permitted"
            )
        if not fixed_lag_allowed and self.max_fixed_lag_seconds is not None:
            raise ValueError(
                "max_fixed_lag_seconds must be omitted when online_fixed_lag is not permitted"
            )
        return self


class PoseConvention(StrictModel):
    """Canonical pose representation required by SPEC.md section 11."""

    transform: Literal["T_W_B"] = "T_W_B"
    handedness: Literal["right"] = "right"
    translation_unit: Literal["metre"] = "metre"
    quaternion_order: Literal["xyzw"] = "xyzw"
    timestamp_unit: Literal["int64_ns"] = "int64_ns"


class TimestampAssociation(StrictModel):
    """Explicit estimator/reference timestamp association semantics."""

    mode: TimestampAssociationMode
    max_time_delta_ns: int | None = Field(default=None, gt=0)
    max_reference_gap_ns: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def mode_specific_fields(self) -> Self:
        if self.mode == TimestampAssociationMode.EXACT:
            if self.max_time_delta_ns is not None or self.max_reference_gap_ns is not None:
                raise ValueError("exact timestamp association does not accept tolerance fields")
        elif self.mode == TimestampAssociationMode.NEAREST:
            if self.max_time_delta_ns is None:
                raise ValueError("nearest timestamp association requires max_time_delta_ns")
            if self.max_reference_gap_ns is not None:
                raise ValueError("nearest association does not use max_reference_gap_ns")
        elif self.mode == TimestampAssociationMode.INTERPOLATE_REFERENCE:
            if self.max_reference_gap_ns is None:
                raise ValueError(
                    "interpolate_reference requires max_reference_gap_ns to bound interpolation"
                )
            if self.max_time_delta_ns is not None:
                raise ValueError("interpolate_reference does not use max_time_delta_ns")
        return self


class RelativeErrorWindow(StrictModel):
    """Distance window requested for relative trajectory error."""

    distance_m: float = Field(gt=0)


class TrajectoryPolicy(StrictModel):
    """Pose, association, alignment, and metric semantics."""

    pose: PoseConvention = Field(default_factory=PoseConvention)
    evaluation_frame: str = Field(min_length=1)
    association: TimestampAssociation
    alignment: AlignmentMode
    scale_correction: bool = False
    ape_translation: bool = True
    ape_rotation: bool = True
    relative_error_windows: tuple[RelativeErrorWindow, ...] = ()

    @model_validator(mode="after")
    def metric_lidar_is_metric_scale(self) -> Self:
        if self.scale_correction:
            raise ValueError("official v0.1 LO/LIO protocols forbid scale correction")
        distances = [window.distance_m for window in self.relative_error_windows]
        if len(distances) != len(set(distances)):
            raise ValueError("relative_error_windows must not contain duplicate distances")
        if distances != sorted(distances):
            raise ValueError("relative_error_windows must be ordered by increasing distance")
        return self


class PreprocessingOperation(StrictModel):
    """Ownership and explicit parameters for a material preprocessing stage."""

    owner: PreprocessingOwner
    parameters: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def none_has_no_parameters(self) -> Self:
        if self.owner == PreprocessingOwner.NONE and self.parameters:
            raise ValueError("preprocessing parameters must be empty when owner is none")
        return self


class MotionCompensationPolicy(StrictModel):
    """Declared input and ownership semantics for deskew/motion compensation."""

    input_state: MotionCompensationInputState
    performed_by: PreprocessingOwner
    motion_source: MotionSource
    parameters: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def source_consistency(self) -> Self:
        if self.performed_by == PreprocessingOwner.NONE and self.motion_source != MotionSource.NONE:
            raise ValueError("motion_source must be none when performed_by is none")
        if self.performed_by == PreprocessingOwner.NONE and self.parameters:
            raise ValueError(
                "motion-compensation parameters must be empty when performed_by is none"
            )
        if self.performed_by != PreprocessingOwner.NONE and self.motion_source == MotionSource.NONE:
            raise ValueError("a performed motion-compensation stage requires a motion_source")
        return self


class PreprocessingPolicy(StrictModel):
    """Protocol-visible preprocessing ownership declarations."""

    coordinate_transform: PreprocessingOperation
    motion_compensation: MotionCompensationPolicy
    voxel_downsample: PreprocessingOperation
    crop: PreprocessingOperation
    range_filter: PreprocessingOperation
    outlier_filter: PreprocessingOperation
    ground_removal: PreprocessingOperation
    intensity_filter: PreprocessingOperation
    timestamp_reconstruction: PreprocessingOperation
    point_reordering: PreprocessingOperation
    duplicate_removal: PreprocessingOperation


class TimingPolicy(StrictModel):
    """Timing boundary and clock requirements."""

    scope: TimingScope
    clock: Literal["monotonic"] = "monotonic"


class ValidityPolicy(StrictModel):
    """Minimum structural validity required before accuracy/performance claims."""

    temporal_coverage_min: float = Field(ge=0, le=1)
    finite_poses_required: bool = True
    successful_process_exit_required: bool = True


class RepetitionPolicy(StrictModel):
    """Minimum repetition evidence for different measurement classes."""

    exploratory_min_trials: int = Field(default=1, ge=1)
    controlled_min_trials: int = Field(default=5, ge=1)
    publication_min_trials: int = Field(default=10, ge=1)
    warmup_trials: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def monotonic_strength(self) -> Self:
        if not (
            self.exploratory_min_trials
            <= self.controlled_min_trials
            <= self.publication_min_trials
        ):
            raise ValueError(
                "trial minimums must satisfy exploratory <= controlled <= publication"
            )
        return self


class MeasurementPolicy(StrictModel):
    """Authoritative measurement capabilities promised by the protocol."""

    cpu_authoritative: bool = True
    gpu_authoritative: bool = False
    allowed_classes: frozenset[MeasurementClass] = frozenset(MeasurementClass)
    cache_policy: CachePolicy


class TuningPolicy(StrictModel):
    """Allowed tuning granularity for runs under the protocol."""

    allowed_classes: frozenset[TuningClass] = frozenset(TuningClass)
    preferred_class: TuningClass = TuningClass.FROZEN

    @model_validator(mode="after")
    def preferred_is_allowed(self) -> Self:
        if self.preferred_class not in self.allowed_classes:
            raise ValueError("preferred tuning class must be included in allowed_classes")
        return self


class BenchmarkProtocol(StrictModel):
    """Fully explicit v0.1 LidarPerf protocol document."""

    spec_version: Literal[SPEC_VERSION]
    protocol: ProtocolIdentity
    track: Track
    sensors: SensorPolicy
    estimator_semantics: EstimatorSemanticsPolicy
    trajectory: TrajectoryPolicy
    preprocessing: PreprocessingPolicy
    timing: TimingPolicy
    validity: ValidityPolicy
    repetition: RepetitionPolicy
    measurement: MeasurementPolicy
    tuning: TuningPolicy

    @model_validator(mode="after")
    def official_track_constraints(self) -> Self:
        external_sources = frozenset(
            {
                Sensor.CAMERA,
                Sensor.WHEEL_ODOMETRY,
                Sensor.GNSS,
                Sensor.MAGNETOMETER,
                Sensor.EXTERNAL_LOCALIZATION,
                Sensor.PREBUILT_MAP,
                Sensor.GROUND_TRUTH,
                Sensor.PRECOMPUTED_MOTION,
            }
        )

        if self.track == Track.LO:
            if self.sensors.required != frozenset({Sensor.LIDAR}):
                raise ValueError("LO protocols must require exactly LiDAR runtime input")
            required_forbidden = external_sources | {Sensor.IMU}
        else:
            if self.sensors.required != frozenset({Sensor.LIDAR, Sensor.IMU}):
                raise ValueError("LIO protocols must require exactly LiDAR and IMU runtime input")
            required_forbidden = external_sources

        missing_forbidden = required_forbidden - self.sensors.forbidden
        if missing_forbidden:
            names = ", ".join(sorted(sensor.value for sensor in missing_forbidden))
            raise ValueError(f"official {self.track.value} protocol must forbid: {names}")

        if self.sensors.optional:
            raise ValueError("official v0.1 LO/LIO protocols do not allow optional runtime sensors")

        unsupported_modes = self.estimator_semantics.allowed_modes - {
            TemporalMode.ONLINE_CAUSAL,
            TemporalMode.ONLINE_FIXED_LAG,
        }
        if unsupported_modes:
            raise ValueError(
                "official v0.1 LO/LIO protocols cannot permit offline_noncausal estimators"
            )

        if (
            self.timing.scope == TimingScope.END_TO_END
            and self.measurement.cache_policy == CachePolicy.NOT_APPLICABLE
        ):
            raise ValueError("end_to_end timing requires an explicit I/O cache policy")
        return self


class ResolvedProtocol(StrictModel):
    """Validated protocol plus its canonical content fingerprint."""

    document: BenchmarkProtocol
    resolved_sha256: str

    @model_validator(mode="after")
    def valid_digest(self) -> Self:
        if not SHA256_RE.fullmatch(self.resolved_sha256):
            raise ValueError("resolved_sha256 must be a lowercase 64-character SHA-256 digest")
        expected = sha256_fingerprint(self.document)
        if self.resolved_sha256 != expected:
            raise ValueError("resolved_sha256 does not match the canonical protocol document")
        return self
