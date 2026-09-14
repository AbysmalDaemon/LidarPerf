"""Trajectory serialization adapters with canonical timestamp conversion."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from .model import Trajectory, TrajectoryFormatError

_NANOSECONDS_PER_SECOND = Decimal(1_000_000_000)
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


def _timestamp_token_to_ns(token: str, *, line_number: int) -> int:
    try:
        seconds = Decimal(token)
    except InvalidOperation as exc:
        raise TrajectoryFormatError(
            f"line {line_number}: invalid timestamp {token!r}"
        ) from exc
    if not seconds.is_finite():
        raise TrajectoryFormatError(f"line {line_number}: timestamp must be finite")
    nanoseconds = seconds * _NANOSECONDS_PER_SECOND
    integral = nanoseconds.to_integral_value()
    if nanoseconds != integral:
        raise TrajectoryFormatError(
            f"line {line_number}: timestamp has sub-nanosecond precision"
        )
    value = int(integral)
    if not _INT64_MIN <= value <= _INT64_MAX:
        raise TrajectoryFormatError(f"line {line_number}: timestamp exceeds int64 nanoseconds")
    return value


def parse_tum(text: str, *, body_frame: str = "body") -> Trajectory:
    """Parse TUM ``timestamp tx ty tz qx qy qz qw`` into canonical arrays.

    Decimal timestamp parsing avoids silently losing nanoseconds through a
    binary-float round trip. Numeric pose values may contain NaN/Inf so the
    structural validator can count and report them instead of the parser
    dropping the affected pose.
    """

    timestamps: list[int] = []
    positions: list[tuple[float, float, float]] = []
    quaternions: list[tuple[float, float, float, float]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.partition("#")[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 8:
            raise TrajectoryFormatError(
                f"line {line_number}: expected 8 TUM fields, found {len(fields)}"
            )
        timestamp_ns = _timestamp_token_to_ns(fields[0], line_number=line_number)
        try:
            numbers = tuple(float(value) for value in fields[1:])
        except ValueError as exc:
            raise TrajectoryFormatError(f"line {line_number}: invalid pose scalar") from exc
        timestamps.append(timestamp_ns)
        positions.append((numbers[0], numbers[1], numbers[2]))
        quaternions.append((numbers[3], numbers[4], numbers[5], numbers[6]))

    return Trajectory(
        timestamps_ns=np.asarray(timestamps, dtype=np.int64),
        positions_m=np.asarray(positions, dtype=np.float64).reshape((-1, 3)),
        quaternions_xyzw=np.asarray(quaternions, dtype=np.float64).reshape((-1, 4)),
        body_frame=body_frame,
    )


def load_tum(path: str | Path, *, body_frame: str = "body") -> Trajectory:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise TrajectoryFormatError(f"cannot read trajectory {source}: {exc}") from exc
    return parse_tum(text, body_frame=body_frame)


def _timestamp_ns_to_tum(value: int) -> str:
    return f"{Decimal(value) / _NANOSECONDS_PER_SECOND:.9f}"


def serialize_tum(trajectory: Trajectory) -> str:
    """Serialize canonical poses to deterministic TUM text."""

    lines: list[str] = []
    for timestamp, position, quaternion in zip(
        trajectory.timestamps_ns,
        trajectory.positions_m,
        trajectory.quaternions_xyzw,
        strict=True,
    ):
        values = [*position.tolist(), *quaternion.tolist()]
        scalar_text = " ".join(f"{value:.12f}" for value in values)
        lines.append(f"{_timestamp_ns_to_tum(int(timestamp))} {scalar_text}\n")
    return "".join(lines)


def write_tum(trajectory: Trajectory, path: str | Path) -> None:
    destination = Path(path)
    destination.write_text(serialize_tum(trajectory), encoding="utf-8", newline="\n")
