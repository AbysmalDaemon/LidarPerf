"""Trajectory parsing, validation, association, alignment, and metrics."""

from .association import associate_trajectories
from .io import load_tum, parse_tum, serialize_tum, write_tum
from .metrics import evaluate_trajectory, summarize
from .model import (
    AlignmentTransform,
    AssociatedTrajectories,
    AssociationStats,
    MetricSummary,
    RelativeErrorResult,
    Trajectory,
    TrajectoryAssociationError,
    TrajectoryError,
    TrajectoryEvaluation,
    TrajectoryFormatError,
    TrajectoryMetricError,
    TrajectoryValidationError,
    TrajectoryValidationReport,
)
from .validation import DEFAULT_QUATERNION_NORM_TOLERANCE, validate_trajectory

__all__ = [
    "DEFAULT_QUATERNION_NORM_TOLERANCE",
    "AlignmentTransform",
    "AssociatedTrajectories",
    "AssociationStats",
    "MetricSummary",
    "RelativeErrorResult",
    "Trajectory",
    "TrajectoryAssociationError",
    "TrajectoryError",
    "TrajectoryEvaluation",
    "TrajectoryFormatError",
    "TrajectoryMetricError",
    "TrajectoryValidationError",
    "TrajectoryValidationReport",
    "associate_trajectories",
    "evaluate_trajectory",
    "load_tum",
    "parse_tum",
    "serialize_tum",
    "summarize",
    "validate_trajectory",
    "write_tum",
]
