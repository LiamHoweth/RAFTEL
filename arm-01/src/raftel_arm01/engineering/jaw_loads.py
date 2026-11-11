"""Connect a declared ideal jaw COM overlay to the existing arm load ledger.

No mass is allocated here. Existing mass-record IDs and values are preserved,
and saved CAD and ideal jaw configurations remain distinct. Payload position
is held in the declared roll-tool frame, independent of jaw angle; retention
and actual object/contact kinematics are not modeled.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence

from raftel_arm01.engineering.scenarios import finite_number
from raftel_arm01.kinematics import thor_model
from raftel_arm01.kinematics.thor_jaw_bodies import jaw_body_states
from raftel_arm01.kinematics.thor_wrist import MotionStep, point_state

Vector3 = tuple[float, float, float]
NATIVE_TO_ROS = ((0, 1, 0), (-1, 0, 0), (0, 0, 1))
SNAPSHOT_FRAME = "Thor-ROS nominal base_link from native CAD Rz(-pi/2)"


def _vector(value: Sequence[float]) -> Vector3:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 3:
        raise ValueError("expected three finite vector coordinates")
    return tuple(finite_number(item) for item in value)


def _native_to_ros(value: Sequence[float]) -> Vector3:
    x, y, z = _vector(value)
    return y, -x, z


def _body_ids(snapshot: dict) -> set[str]:
    if not isinstance(snapshot, dict) or snapshot.get("coordinate_frame") != SNAPSHOT_FRAME:
        raise ValueError("jaw load overlay requires the existing nominal ROS-frame snapshot")
    rows = snapshot.get("bodies")
    if not isinstance(rows, list) or not rows:
        raise ValueError("jaw load overlay requires expanded mass bodies")
    expected_count = snapshot.get("mass_assignment_summary", {}).get("assigned_mass_record_count")
    if type(expected_count) is not int or expected_count != len(rows):
        raise ValueError("expanded jaw load body count disagrees with original mass assignments")
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("jaw load body requires a mass-record ID")
        if row["id"] in ids:
            raise ValueError("duplicate jaw load body ID")
        ids.add(row["id"])
        _vector(row.get("com_m"))
        if finite_number(row.get("mass_kg")) <= 0:
            raise ValueError("jaw load body mass must remain positive")
    return ids


def apply_jaw_overlay(
    snapshot: dict,
    ledger: dict,
    closing_angle_rad: float | None = None,
    *,
    mode: str = "ideal",
) -> dict:
    """Return a copied zero-arm snapshot with source-declared COM changes only.

    Call ``validate_jaw_ledger`` with the bound inventory and membership before
    this function. All fixed bodies retain their saved COM; moving jaw records
    must be part of roll_tool. No servo internals or hardware mass are split.
    """
    ids = _body_ids(snapshot)
    states = jaw_body_states(ledger, closing_angle_rad, mode=mode)
    if not set(states) <= ids:
        raise ValueError("jaw ledger contains a mass record absent from expanded load snapshot")
    result = copy.deepcopy(snapshot)
    derivatives = {identifier: (0.0, 0.0, 0.0) for identifier in ids}
    records = {record["mass_record_id"]: record for record in ledger["records"]}
    for body in result["bodies"]:
        identifier = body["id"]
        if identifier not in states:
            continue
        record, state = records[identifier], states[identifier]
        if _native_to_ros(record["saved_com_native_m"]) != _vector(body["com_m"]):
            raise ValueError("jaw overlay requires saved COM input, not an already posed snapshot")
        if record["wrist_motion_class"] != body.get("wrist_motion_class"):
            raise ValueError("jaw overlay cannot change wrist membership")
        if record["jaw_motion_class"] != "jaw_fixed" and body["wrist_motion_class"] != "roll_tool":
            raise ValueError("moving jaw mass must belong to roll_tool")
        body["com_m"] = list(_native_to_ros(state.position_m))
        derivatives[identifier] = _native_to_ros(state.derivative_m_rad)
    result["jaw_com_jacobians_zero_arm_m_rad"] = derivatives
    result["jaw_overlay"] = {
        "configuration": "ideal_body_overlay" if mode == "ideal" else "saved_frozen",
        "closing_angle_rad": closing_angle_rad,
        "native_to_ros_rotation": [list(row) for row in NATIVE_TO_ROS],
        "mass_records_added_removed_or_reweighted": False,
        "physical_motion_qualified": False,
        "payload_jaw_derivative_assumption": (
            "fixed payload point relative to roll_tool; zero dCOM/dqjaw"
        ),
        "ideal_zero_is_saved_configuration": False,
    }
    return result


def carry_jaw_derivatives(
    zero_snapshot: dict, joint_angles_rad: Sequence[float], motion_classes: Mapping[str, dict]
) -> dict[str, Vector3]:
    """Rotate dCOM/dqjaw through declared wrist and q1–q4 arm orientations.

    Translation has no effect on derivative vectors. The wrist's existing
    MotionStep evaluator is reused with zero origins to obtain its orientation
    action; the existing nominal FK supplies the proximal orientation.
    """
    ids = _body_ids(zero_snapshot)
    if not isinstance(joint_angles_rad, Sequence) or len(joint_angles_rad) != 6:
        raise ValueError("exactly six finite joint angles required")
    angles = tuple(finite_number(item) for item in joint_angles_rad)
    derivatives = zero_snapshot.get("jaw_com_jacobians_zero_arm_m_rad")
    if not isinstance(derivatives, Mapping) or set(derivatives) != ids:
        raise ValueError("jaw derivatives must cover every expanded body exactly once")
    nominal_axes, _ = thor_model.chain((0.0,) * 6)
    raw_axes = zero_snapshot.get("joints")
    if not isinstance(raw_axes, list) or len(raw_axes) != 6:
        raise ValueError("jaw derivative carry requires six nominal zero-pose joint axes")
    for actual, expected in zip(raw_axes, nominal_axes, strict=True):
        if (
            _vector(actual.get("origin_m")) != expected.origin_m
            or _vector(actual.get("axis_unit")) != expected.axis_unit
        ):
            raise ValueError("jaw derivative carry requires unposed nominal source axes")
    _, proximal = thor_model.chain((*angles[:4], 0.0, 0.0))
    result = {}
    for body in zero_snapshot["bodies"]:
        identifier = body["id"]
        derivative = _vector(derivatives[identifier])
        raw = motion_classes[body["wrist_motion_class"]]
        steps = tuple(MotionStep(**{**step, "origin_m": (0, 0, 0)}) for step in raw["steps"])
        rotated = point_state(derivative, angles[4], angles[5], steps).position_m
        result[identifier] = _vector(
            tuple(math.fsum(proximal[i][j] * rotated[j] for j in range(3)) for i in range(3))
        )
    return result


def jaw_gravity_torque_nm(
    snapshot: dict,
    carried_derivatives_m_rad: Mapping[str, Sequence[float]],
    gravity_m_s2: Sequence[float] = (0, 0, -9.80665),
) -> float:
    """External model gravity effort conjugate to qjaw; holding is its negative."""
    ids = _body_ids(snapshot)
    if not isinstance(carried_derivatives_m_rad, Mapping) or set(carried_derivatives_m_rad) != ids:
        raise ValueError("jaw gravity derivatives must cover every expanded body exactly once")
    gravity = _vector(gravity_m_s2)
    return finite_number(
        math.fsum(
            finite_number(body["mass_kg"])
            * math.fsum(
                gravity[i] * _vector(carried_derivatives_m_rad[body["id"]])[i] for i in range(3)
            )
            for body in snapshot["bodies"]
        )
    )
