"""Deterministic synthetic conformance fixtures for LidarPerf."""

from .generator import fixture_identity, generate_fixture, write_fixture
from .models import (
    SyntheticFixture,
    SyntheticFixtureConfig,
    SyntheticFixtureManifest,
    SyntheticPoint,
    SyntheticPose,
    SyntheticScan,
)

__all__ = [
    "SyntheticFixture",
    "SyntheticFixtureConfig",
    "SyntheticFixtureManifest",
    "SyntheticPoint",
    "SyntheticPose",
    "SyntheticScan",
    "fixture_identity",
    "generate_fixture",
    "write_fixture",
]
