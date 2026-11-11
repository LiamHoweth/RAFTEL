"""Evidence-bearing wrist COM trajectories and their analytical Jacobians.

This module evaluates declared axis/angle chains. It does not infer which CAD
part follows a chain, calibrate command signs, or map motor shaft torques. All
points and axis origins in one call must use the same declared zero-pose frame.
Angles are radians; positions and derivatives are metres and metres/radian.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real

Vector3 = tuple[float, float, float]


def _finite(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("expected finite real values")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("expected finite real values") from error
    if not math.isfinite(result):
        raise ValueError("expected finite real values")
    return result


def _vector(value: Sequence[float]) -> Vector3:
    if not isinstance(value, Sequence) or len(value) != 3:
        raise ValueError("expected three finite vector coordinates")
    return tuple(_finite(component) for component in value)


def _cross(left: Vector3, right: Vector3) -> Vector3:
    ax, ay, az = left
    bx, by, bz = right
    return _vector((ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx))


def _dot(left: Vector3, right: Vector3) -> float:
    try:
        return _finite(math.fsum(a * b for a, b in zip(left, right, strict=True)))
    except OverflowError as error:
        raise ValueError("wrist calculation overflowed") from error


def _rotate(vector: Vector3, axis: Vector3, angle: float) -> Vector3:
    c, s = math.cos(angle), math.sin(angle)
    perpendicular = _cross(axis, vector)
    parallel = _dot(axis, vector)
    return _vector(
        tuple(vector[i] * c + perpendicular[i] * s + axis[i] * parallel * (1 - c) for i in range(3))
    )


@dataclass(frozen=True)
class MotionStep:
    """One declared rotation whose angle is a*q5 + b*q6.

    Axis origin/direction are expressed at the common zero pose. Earlier steps
    carry this axis; later steps do not. The evidence field must identify why
    this specific body/axis/coefficient relation is being evaluated. A valid
    numeric declaration is not evidence that it matches a physical mechanism.
    """

    origin_m: Vector3
    axis_unit: Vector3
    q5_coefficient: float
    q6_coefficient: float
    evidence: str

    def __post_init__(self) -> None:
        origin, axis = _vector(self.origin_m), _vector(self.axis_unit)
        if not math.isclose(math.hypot(*axis), 1, rel_tol=0, abs_tol=1e-9):
            raise ValueError("motion axis must be unit length")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("motion step requires explicit evidence")
        object.__setattr__(self, "origin_m", origin)
        object.__setattr__(self, "axis_unit", axis)
        object.__setattr__(self, "q5_coefficient", _finite(self.q5_coefficient))
        object.__setattr__(self, "q6_coefficient", _finite(self.q6_coefficient))


@dataclass(frozen=True)
class WristPointState:
    position_m: Vector3
    dq5_m_rad: Vector3
    dq6_m_rad: Vector3

    def __post_init__(self) -> None:
        for field in ("position_m", "dq5_m_rad", "dq6_m_rad"):
            object.__setattr__(self, field, _vector(getattr(self, field)))


def point_state(
    point_m: Sequence[float],
    q5_rad: float,
    q6_rad: float,
    steps: Sequence[MotionStep],
) -> WristPointState:
    """Evaluate a declared COM trajectory, with derivatives for both wrist DOFs.

    An empty chain denotes a fixed point. A side rotor can use one step driven
    by both coordinates; a tool body can use fold then carried roll. Coefficients
    and membership must be supplied by a separately justified mechanism model.
    No full-body inertia, collision, angle limit, or physical safety is implied.
    """
    point = _vector(point_m)
    q5, q6 = _finite(q5_rad), _finite(q6_rad)
    if not isinstance(steps, Sequence) or any(not isinstance(step, MotionStep) for step in steps):
        raise ValueError("steps must be a sequence of MotionStep declarations")
    origins = [step.origin_m for step in steps]
    axes = [step.axis_unit for step in steps]
    active_axes = []
    for index, step in enumerate(steps):
        origin, axis = origins[index], axes[index]
        angle = _finite(step.q5_coefficient * q5 + step.q6_coefficient * q6)
        active_axes.append((origin, axis, step.q5_coefficient, step.q6_coefficient))

        def rotate_point(
            value: Vector3, origin: Vector3 = origin, axis: Vector3 = axis, angle: float = angle
        ) -> Vector3:
            relative = _vector(tuple(value[i] - origin[i] for i in range(3)))
            rotated = _rotate(relative, axis, angle)
            return _vector(tuple(origin[i] + rotated[i] for i in range(3)))

        point = rotate_point(point)
        for later in range(index + 1, len(steps)):
            origins[later] = rotate_point(origins[later])
            axes[later] = _rotate(axes[later], axis, angle)
    terms = []
    for origin, axis, coefficient5, coefficient6 in active_axes:
        lever = _vector(tuple(point[i] - origin[i] for i in range(3)))
        velocity = _cross(axis, lever)
        terms.append((velocity, coefficient5, coefficient6))
    try:
        derivative5 = _vector(
            tuple(math.fsum(velocity[i] * a for velocity, a, _ in terms) for i in range(3))
        )
        derivative6 = _vector(
            tuple(math.fsum(velocity[i] * b for velocity, _, b in terms) for i in range(3))
        )
    except OverflowError as error:
        raise ValueError("wrist derivative overflowed") from error
    return WristPointState(point, derivative5, derivative6)


def gravity_generalized_torque_nm(
    state: WristPointState, mass_kg: float, gravity_m_s2: Sequence[float] = (0, 0, -9.80665)
) -> tuple[float, float]:
    """Return external gravity moments conjugate to q5/q6; holding is negative.

    Virtual work gives tau_j = force dot dCOM/dq_j. These are generalized joint
    efforts, not actuator shaft torques; no gearbox/efficiency is inferred.
    """
    if not isinstance(state, WristPointState):
        raise ValueError("state must be a WristPointState")
    mass = _finite(mass_kg)
    if mass < 0:
        raise ValueError("mass must be nonnegative")
    gravity = _vector(gravity_m_s2)
    force = _vector(tuple(mass * component for component in gravity))
    return (
        _dot(force, _vector(state.dq5_m_rad)),
        _dot(force, _vector(state.dq6_m_rad)),
    )
