"""Offline fixtures for pinned Thor-ROS integer-degree conversion.

This is a diagnostic transcription of the finite, complete-input paths of
thor_interface.cpp at e11a56b5aa0d89f0b68a3ea7bd084eab4a050952. It does not
send the returned strings anywhere. Unlike the upstream partial read path,
incomplete/malformed reports are rejected before any state is returned.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real

ROS_REVISION = "e11a56b5aa0d89f0b68a3ea7bd084eab4a050952"
ROS_SOURCE_SHA256 = "c2bd16032e43db1e30fc48a2c00a7ef2b0c4943c7018234ca56aaed11102f690"
GRBL_AXES = ("A", "B", "C", "D", "X", "Y", "Z")
FLY_AXES = ("X", "Y", "Z", "U", "V", "W")
EVIDENCE_CLASS = "offline_source_conversion_not_physical_state"
_INT_MIN, _INT_MAX = -(2**31), 2**31 - 1
_REPORT_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", re.ASCII)


def _finite(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("coordinates must be finite real numbers")
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("coordinates must be finite real numbers") from error
    if not math.isfinite(result):
        raise ValueError("coordinates must be finite real numbers")
    return result


def _values(values: Sequence[float], count: int) -> tuple[float, ...]:
    if not isinstance(values, Sequence) or isinstance(values, str | bytes) or len(values) != count:
        raise ValueError(f"expected exactly {count} coordinates")
    return tuple(_finite(value) for value in values)


def _int32(value: float | int) -> int:
    # static_cast<int> is undefined outside the C++ int range. Do not emulate UB.
    if type(value) is int:
        valid = _INT_MIN <= value <= _INT_MAX
    else:
        valid = math.isfinite(value) and _INT_MIN <= value <= _INT_MAX
    if not valid:
        raise ValueError("source expression is outside defined signed 32-bit integer range")
    return int(value)


def source_angles(joints_rad: Sequence[float]) -> tuple[int, ...]:
    """Return six source channel intermediates plus commanded gripper degrees.

    Ordering is art1, art2, art3, art4, m_art5, m_art6, end_effector.
    The source truncates the offset expressions before subtracting 90, and
    truncates each wrist joint before mixing. Those operations do not commute.
    """
    q1, q2, q3, q4, q5, q6, jaw = _values(joints_rad, 7)
    a1 = _int32(-90 + _int32(((q1 + math.pi / 2) * 180) / math.pi))
    a2 = _int32(90 - _int32(((q2 + math.pi / 2) * 180) / math.pi))
    a3 = _int32(90 - _int32(((q3 + math.pi / 2) * 180) / math.pi))
    a4 = _int32((q4 * 180) / math.pi)
    a5 = _int32((-q5 * 180) / math.pi)
    a6 = _int32((q6 * 180) / math.pi)
    twice_a6 = _int32(2 * a6)
    return (
        a1,
        a2,
        a3,
        a4,
        _int32(a5 + twice_a6),
        _int32(_int32(-a5) + twice_a6),
        _int32(180 + (jaw * 180 / math.pi)),
    )


@dataclass(frozen=True)
class SourceWrite:
    """Strings a source write would produce; no transmission or acceptance."""

    angles_deg: tuple[int, ...]
    diagnostic_lines: tuple[str, ...]
    board: str
    evidence_class: str = EVIDENCE_CLASS


def source_write(
    joints_rad: Sequence[float],
    *,
    board: str,
    previous_angles_deg: Sequence[int] = (0, 0, 0, 0, 0, 0, 0),
) -> SourceWrite:
    """Model suppression against an explicitly supplied prior successful write.

    The default prior vector matches on_activate(). A source write exception
    leaves its previous vector unchanged, so callers must not advance it after
    an injected send failure. The source does not include G90 in these lines.
    Only the two documented boards are accepted (upstream uses an else branch).
    """
    if not isinstance(board, str) or board not in {"thor_pcb", "fly"}:
        raise ValueError("board must be thor_pcb or fly")
    prior = _values(previous_angles_deg, 7)
    if any(type(value) is not int for value in previous_angles_deg):
        raise ValueError("previous source angles must be integers")
    for value in previous_angles_deg:
        _int32(value)
    angles = source_angles(joints_rad)
    lines = []
    if angles[:6] != prior[:6]:
        a1, a2, a3, a4, m5, m6 = angles[:6]
        if board == "thor_pcb":
            channels = (a1, a2, a2, a3, a4, m5, m6)
            axes = GRBL_AXES
        else:
            channels = angles[:6]
            axes = FLY_AXES
        words = " ".join(f"{axis}{v}" for axis, v in zip(axes, channels, strict=True))
        lines.append("G0 " + words + "\r\n")
    if angles[6] != prior[6]:
        if board == "thor_pcb":
            product = _int32(angles[6] * 255)
            pwm = math.trunc(product / 180)  # C++ integer division truncates toward zero.
            lines.append(f"M3 S{pwm}\r\n")
        else:
            lines.append(f"M280 P0 S{angles[6]}\r\n")
    return SourceWrite(angles, tuple(lines), board)


@dataclass(frozen=True)
class SourceReadback:
    """Source-inferred coordinates, never measured physical joint positions."""

    joints_rad: tuple[float, ...]
    board: str
    reported_channels_deg: tuple[float, ...]
    duplicate_shoulder_agrees: bool | None
    gripper_state_origin: str = "last_command_not_sensor"
    evidence_class: str = EVIDENCE_CLASS


def _read_angles(values: Sequence[float], gripper_deg: int) -> tuple[float, ...]:
    if type(gripper_deg) is not int:
        raise ValueError("commanded gripper source state must be an int32 integer")
    _int32(gripper_deg)
    a1, a2, a3, a4, m5, m6 = _values(values, 6)
    # Preserve the order of the source arithmetic rather than simplify it.
    a6 = (m5 + m6) / 4
    a5 = m6 - 2 * a6
    output = (
        a1 * math.pi / 180,
        a2 * math.pi / -180,
        a3 * math.pi / -180,
        a4 * math.pi / 180,
        a5 * math.pi / 180,
        a6 * math.pi / 180,
        _int32(gripper_deg - 180) * math.pi / 180,
    )
    return tuple(_finite(value) for value in output)


def read_grbl_report(report: str, *, commanded_gripper_deg: int) -> SourceReadback:
    """Model a complete legacy MPos report, exposing the source's B/C bug.

    At loop index 1 the source consumes B, then consumes C and uses C as the
    shoulder. This function reports mismatch separately; it does not silently
    fix the historical conversion. Partial reports are rejected atomically.
    """
    if not isinstance(report, str) or len(report) > 4096:
        raise ValueError("report must be a bounded string")
    marker, end = report.find("MPos:"), report.find(",WPos:")
    if marker < 0 or end <= marker + 5:
        raise ValueError("complete legacy MPos and WPos fields are required")
    tokens = report[marker + 5 : end].split(",")
    if len(tokens) != 7:
        raise ValueError("complete MPos requires seven channels")
    if any(not _REPORT_NUMBER.fullmatch(token.strip()) for token in tokens):
        raise ValueError("MPos contains a malformed number")
    try:
        channels = tuple(_finite(float(token)) for token in tokens)
    except (ValueError, TypeError) as error:
        raise ValueError("MPos contains a malformed or nonfinite number") from error
    a, b, c, d, x, y, z = channels
    return SourceReadback(
        _read_angles((a, c, d, x, y, z), commanded_gripper_deg),
        "thor_pcb",
        channels,
        b == c,
    )


def read_fly_report(report: str, *, commanded_gripper_deg: int) -> SourceReadback:
    """Model the six-channel Fly pos conversion of a complete JSON report.

    The source accepts a seventh pos value but then overwrites the gripper
    coordinate with its command. It also treats status/homed as local values;
    this diagnostic makes no homed or commissioned-state inference.
    """
    if not isinstance(report, str) or len(report) > 4096 or not report.startswith('{"status":'):
        raise ValueError("expected bounded source-format Fly status JSON")
    try:
        data = json.loads(report)
    except ValueError as error:
        raise ValueError("malformed Fly report") from error
    values = data.get("pos")
    if not isinstance(values, list) or len(values) not in {6, 7}:
        raise ValueError("complete Fly pos requires six or seven channels")
    channels = _values(values, len(values))
    return SourceReadback(_read_angles(channels[:6], commanded_gripper_deg), "fly", channels, None)
