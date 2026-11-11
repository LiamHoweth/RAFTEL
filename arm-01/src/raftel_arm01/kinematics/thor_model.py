"""Nominal six-axis Thor geometry transcribed from a pinned upstream ROS model.

This is an upstream mathematical model, not a calibrated ARM-01 robot model.
Native CAD attachment points corroborate selected axis-line positions only;
CAD joint signs, limits, TCP and complete geometry reconciliation remain open.
No source inertial/effort values are used: upstream values are placeholders.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real

SOURCE_REVISION = "e11a56b5aa0d89f0b68a3ea7bd084eab4a050952"
SOURCE_PATH = "ws_thor/src/thor_urdf/urdf/thor.urdf.xacro"
VALIDATION_CLASS = "upstream_nominal_kinematics_not_hardware_calibrated"
# Direct source origins in metres, all with zero origin RPY.
JOINT_Z_OFFSETS_M = (0.099, 0.103, 0.160, 0.0895, 0.1045, 0.0135)
JOINT_LOCAL_AXES = (
    (0.0, 0.0, 1.0),
    (1.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
)
TOOL_Z_OFFSETS_M = (0.043, 0.075)
Vector3 = tuple[float, float, float]
Matrix4 = tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class JointFrame:
    """An axis line at a configuration, expressed in the source base_link frame."""

    name: str
    origin_m: Vector3
    axis_unit: Vector3


def _angles(values: Sequence[float]) -> tuple[float, ...]:
    if not isinstance(values, Sequence) or len(values) != 6:
        raise ValueError("exactly six finite joint angles in radians are required")
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
        raise ValueError("joint angles must be finite real numbers")
    try:
        angles = tuple(float(value) for value in values)
    except (ValueError, OverflowError) as error:
        raise ValueError("joint angles must be finite real numbers") from error
    if not all(math.isfinite(value) for value in angles):
        raise ValueError("joint angles must be finite real numbers")
    return angles


def _multiply(a: Matrix4, b: Matrix4) -> Matrix4:
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)) for i in range(4)
    )


def _translation(z_m: float) -> Matrix4:
    return ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, z_m), (0.0, 0.0, 0.0, 1.0))


def _rotation(axis: Vector3, angle: float) -> Matrix4:
    c, s = math.cos(angle), math.sin(angle)
    if axis == (1.0, 0.0, 0.0):
        return ((1.0, 0.0, 0.0, 0.0), (0.0, c, -s, 0.0), (0.0, s, c, 0.0), (0.0, 0.0, 0.0, 1.0))
    return ((c, -s, 0.0, 0.0), (s, c, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def chain(joints_rad: Sequence[float]) -> tuple[tuple[JointFrame, ...], Matrix4]:
    """Return nominal world axis lines and link_6 transform, without limit claims.

    URDF origin translations precede each joint rotation. No collision checking,
    inverse kinematics, joint-limit enforcement or motion permission is implied.
    """
    angles = _angles(joints_rad)
    transform = _translation(0.0)
    frames = []
    for index, (offset, axis, angle) in enumerate(
        zip(JOINT_Z_OFFSETS_M, JOINT_LOCAL_AXES, angles, strict=True), 1
    ):
        transform = _multiply(transform, _translation(offset))
        origin = tuple(transform[i][3] for i in range(3))
        world_axis = tuple(sum(transform[i][j] * axis[j] for j in range(3)) for i in range(3))
        frames.append(JointFrame(f"joint_{index}", origin, world_axis))
        transform = _multiply(transform, _rotation(axis, angle))
    return tuple(frames), transform


def forward_kinematics(joints_rad: Sequence[float], target: str = "link_6") -> Matrix4:
    """Pose of link_6 or the source gripper midpoint in nominal base_link metres.

    The source midpoint's fixed offsets describe that upstream model, not the
    actual ARM-01 grasp point or a measured gripper aperture.
    """
    if target not in {"link_6", "gripper_base", "gripper_mid_point"}:
        raise ValueError("target must be link_6, gripper_base or gripper_mid_point")
    _, transform = chain(joints_rad)
    if target != "link_6":
        transform = _multiply(transform, _translation(TOOL_Z_OFFSETS_M[0]))
    if target == "gripper_mid_point":
        transform = _multiply(transform, _translation(TOOL_Z_OFFSETS_M[1]))
    return transform
