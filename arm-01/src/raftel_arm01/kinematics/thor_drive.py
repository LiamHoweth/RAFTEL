"""Pure continuous-coordinate model of a pinned Thor-ROS drive convention.

Source: AngelLM/Thor-ROS e11a56b5aa0d89f0b68a3ea7bd084eab4a050952,
ws_thor/src/thor_controller/src/thor_interface.cpp, write() lines 269-309.

Inputs and outputs are radians. Outputs follow GRBL channel order A,B,C,D,X,Y,Z,
not raw rotor angles, step pulses, current/torque commands, or gripper commands.
The source's +/-90 degree intermediates algebraically cancel in the continuous
model. Its integer-degree truncation is deliberately not reproduced. Actual
CAD axes, zero offsets, limits, coupling and physical calibration are unverified.
No hardware API, arming, planning, or safety approval is provided by this module.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Real

# Numerical comparison tolerance only; not a physical synchronization allowance.
_SHOULDER_MATCH_ABS_TOL_RAD = 1e-9


def _coordinates(values: Sequence[float], size: int) -> tuple[float, ...]:
    try:
        length = len(values)
    except TypeError as exc:
        raise ValueError(f"Expected a sequence of exactly {size} coordinates") from exc
    if length != size:
        raise ValueError(f"Expected exactly {size} coordinates; received {length}")
    result = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("Coordinates must be finite real numbers")
        try:
            coordinate = float(value)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Coordinates must be finite real numbers") from exc
        if not math.isfinite(coordinate):
            raise ValueError("Coordinates must be finite real numbers")
        result.append(coordinate)
    return tuple(result)


def joints_to_drive(joints_rad: Sequence[float]) -> tuple[float, ...]:
    """Map six nominal joint coordinates to seven continuous channel coordinates.

    q1->A, -q2->B=C, -q3->D, q4->X;
    Y=-q5+2*q6 and Z=q5+2*q6 in the pinned source convention.
    Values are unbounded model coordinates, not commands permitted for motion.
    """
    q1, q2, q3, q4, q5, q6 = _coordinates(joints_rad, 6)
    return _coordinates((q1, -q2, -q2, -q3, q4, -q5 + 2 * q6, q5 + 2 * q6), 7)


def drive_to_joints(drive_rad: Sequence[float]) -> tuple[float, ...]:
    """Invert the nominal model, rejecting inconsistent shoulder channels.

    The 1e-9 rad absolute tolerance handles floating-point representations. It
    is not an acceptable physical shoulder-motor mismatch or a fault threshold.
    """
    a, b, c, d, x, y, z = _coordinates(drive_rad, 7)
    if not math.isclose(b, c, rel_tol=0.0, abs_tol=_SHOULDER_MATCH_ABS_TOL_RAD):
        raise ValueError("Duplicate shoulder coordinates B and C must agree")
    # Divide before adding/subtracting to avoid intermediate sum overflow.
    return _coordinates((a, -b, -d, x, z / 2 - y / 2, y / 4 + z / 4), 6)
