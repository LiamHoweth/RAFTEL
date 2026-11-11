"""Explicit saved-to-ideal jaw COM scenarios in native assembly-world axes.

This is an analytical overlay, not a repaired CAD assembly or servo calibration.
Masses belong to the existing load ledger and are deliberately not stored here.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Real

from raftel_arm01.kinematics.thor_gripper import IdealThorGripper

Vector3 = tuple[float, float, float]
SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
FRAME = "Thor native assembly-world XYZ, metres; zero arm pose"
CLASSES = {"jaw_fixed", "finger_translation", "link_rotation"}


def canonical_sha256(value: object) -> str:
    """Hash JSON content independently of whitespace and object key order."""
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("jaw evidence must be finite JSON content") from error
    return hashlib.sha256(encoded.encode()).hexdigest()


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("jaw coordinate must be a finite real number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("jaw coordinate must be a finite real number") from error
    if not math.isfinite(result):
        raise ValueError("jaw coordinate must be a finite real number")
    return result


def _vector(value: object) -> Vector3:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 3:
        raise ValueError("jaw point requires three finite SI components")
    return tuple(_finite(component) for component in value)


def _frame(value: object) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, Sequence) or len(value) != 4:
        raise ValueError("native_from_gripper_bot must be a rigid 4x4 SI transform")
    rows = []
    for row in value:
        if not isinstance(row, Sequence) or len(row) != 4:
            raise ValueError("native_from_gripper_bot must be a rigid 4x4 SI transform")
        rows.append(tuple(_finite(v) for v in row))
    if rows[3] != (0, 0, 0, 1):
        raise ValueError("invalid homogeneous transform bottom row")
    for i in range(3):
        for j in range(3):
            dot = math.fsum(rows[k][i] * rows[k][j] for k in range(3))
            if not math.isclose(dot, float(i == j), abs_tol=1e-10):
                raise ValueError("jaw frame rotation must be orthonormal")
    r = rows
    determinant = (
        r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
        - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
        + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0])
    )
    if not math.isclose(determinant, 1, abs_tol=1e-10):
        raise ValueError("jaw frame must be a proper rotation")
    return tuple(rows)


def _native_point(frame: tuple, point: Vector3) -> Vector3:
    return _vector(
        tuple(frame[i][3] + math.fsum(frame[i][j] * point[j] for j in range(3)) for i in range(3))
    )


def _native_vector(frame: tuple, value: Vector3) -> Vector3:
    return _vector(tuple(math.fsum(frame[i][j] * value[j] for j in range(3)) for i in range(3)))


def _bot_point(frame: tuple, point: Vector3) -> Vector3:
    relative = tuple(point[i] - frame[i][3] for i in range(3))
    return _vector(tuple(math.fsum(frame[j][i] * relative[j] for j in range(3)) for i in range(3)))


def _validated(ledger: object) -> tuple[tuple, list[dict]]:
    if (
        not isinstance(ledger, dict)
        or type(ledger.get("schema_version")) is not int
        or ledger["schema_version"] != 1
    ):
        raise ValueError("unsupported jaw ledger schema")
    if ledger.get("source_revision") != SOURCE_REVISION or ledger.get("coordinate_frame") != FRAME:
        raise ValueError("jaw source revision or coordinate frame differs")
    if ledger.get("validation_class") != "source_XML_ownership_and_conditional_ideal_COM_overlay":
        raise ValueError("unsupported jaw evidence class")
    for flag in ("physical_motion_qualified", "native_recompute_performed", "source_saved"):
        if ledger.get(flag) is not False:
            raise ValueError(
                "jaw ledger cannot declare native/physical qualification or source saves"
            )
    frame = _frame(ledger.get("native_from_gripper_bot"))
    records = ledger.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("jaw ledger requires explicit record coverage")
    ids, leaves = set(), set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid jaw record")
        identifier = record.get("mass_record_id")
        covered = record.get("leaf_instance_ids")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("missing or duplicated jaw mass record ID")
        if not isinstance(covered, list) or not covered:
            raise ValueError("jaw mass record requires explicit geometry leaves")
        for leaf in covered:
            if not isinstance(leaf, str) or not leaf or leaf in leaves:
                raise ValueError("missing or duplicated jaw geometry leaf")
            if leaf != identifier and not leaf.startswith(identifier + "/"):
                raise ValueError("jaw geometry leaf does not belong to its mass record")
            leaves.add(leaf)
        ids.add(identifier)
        motion = record.get("jaw_motion_class")
        if not isinstance(motion, str) or motion not in CLASSES:
            raise ValueError("unknown jaw motion class")
        _vector(record.get("saved_com_native_m"))
        if not isinstance(record.get("evidence"), str) or not record["evidence"].strip():
            raise ValueError("jaw motion requires evidence")
        if motion != "jaw_fixed":
            side = record.get("side")
            if isinstance(side, bool) or side not in (-1, 1):
                raise ValueError("moving jaw record requires explicit left/right side")
        if motion == "link_rotation":
            _vector(record.get("saved_pivot_bot_m"))
            _vector(record.get("ideal_pivot_bot_m"))
            phase = _finite(record.get("saved_closing_phase_rad"))
            if abs(phase) >= math.pi / 2:
                raise ValueError("saved jaw phase is outside this scenario branch")
    if ledger.get("geometry_leaf_count") != len(leaves) or ledger.get("mass_record_count") != len(
        ids
    ):
        raise ValueError("jaw coverage counts disagree")
    if ledger.get("motion_counts") != dict(
        Counter(record["jaw_motion_class"] for record in records)
    ):
        raise ValueError("jaw motion counts disagree")
    return frame, records


def validate_jaw_ledger(ledger: dict, inventory: dict, memberships: dict) -> None:
    """Reject stale inputs, missing/disjoint coverage and changed saved COMs.

    This checks the declared input artifacts, not physical completeness of CAD.
    Call before connecting this overlay to a load scenario.
    """
    _, records = _validated(ledger)
    bindings = ledger.get("input_canonical_sha256")
    if not isinstance(bindings, Mapping):
        raise ValueError("jaw ledger needs input provenance hashes")
    for name, value in (("inventory", inventory), ("membership", memberships)):
        if bindings.get(name) != canonical_sha256(value):
            raise ValueError(f"stale jaw {name} evidence")
    source_rows = inventory.get("mounted_bodies")
    members = memberships.get("memberships")
    if not isinstance(source_rows, list) or not isinstance(members, list):
        raise ValueError("invalid jaw input coverage")
    by_leaf = {row["instance_id"]: row for row in source_rows}
    by_motion = {row["instance_id"]: row["motion_class"] for row in members}
    if len(by_leaf) != len(source_rows) or len(by_motion) != len(members):
        raise ValueError("duplicate source inventory or membership IDs")
    expected = {
        row["instance_id"] for row in source_rows if row.get("root_subassembly") == "AssemblyArt56"
    }
    covered = {leaf for record in records for leaf in record["leaf_instance_ids"]}
    if covered != expected:
        raise ValueError("jaw scope must cover every Art56 leaf exactly once")
    for record in records:
        leaves = record["leaf_instance_ids"]
        # This revision has one native geometry leaf per jaw mass record.
        if len(leaves) != 1:
            raise ValueError("jaw ledger revision does not model consolidated geometry COMs")
        leaf = leaves[0]
        if _vector(record["saved_com_native_m"]) != _vector(by_leaf[leaf]["zero_world_com_m"]):
            raise ValueError("jaw record changed the saved native COM")
        if record.get("wrist_motion_class") != by_motion.get(leaf):
            raise ValueError("jaw record changed wrist membership")
        if record["jaw_motion_class"] != "jaw_fixed" and by_motion.get(leaf) != "roll_tool":
            raise ValueError("moving jaw geometry must belong to carried roll tool")


@dataclass(frozen=True)
class JawBodyState:
    """COM and dCOM/dqjaw in native assembly-world axes, at zero arm pose."""

    position_m: Vector3
    derivative_m_rad: Vector3


def jaw_body_states(
    ledger: dict, closing_angle_rad: float | None = None, *, mode: str = "ideal"
) -> dict[str, JawBodyState]:
    """Evaluate an explicit ideal scenario, or return the independent saved pose.

    Saved mode requires no angle, so it cannot be confused with ideal q=0.
    Ideal q=0 normalizes saved driven phases and the asymmetric active pivot.
    Link/pivot fastener retention and balanced servo internals are assumptions.
    No mass, motor command, physical stroke or gripping force is inferred.
    """
    frame, records = _validated(ledger)
    if mode == "saved":
        if closing_angle_rad is not None:
            raise ValueError("saved jaw configuration has no solved closing coordinate")
        return {
            record["mass_record_id"]: JawBodyState(_vector(record["saved_com_native_m"]), (0, 0, 0))
            for record in records
        }
    if mode != "ideal":
        raise ValueError("jaw mode must be saved or ideal")
    q = _finite(closing_angle_rad)
    model = IdealThorGripper()
    jaw = model.state(q)
    result = {}
    for record in records:
        saved = _vector(record["saved_com_native_m"])
        position, derivative = saved, (0, 0, 0)
        motion = record["jaw_motion_class"]
        if motion == "finger_translation":
            side_index = 0 if record["side"] == -1 else 1
            shift = (*jaw.finger_translation_m[side_index], 0)
            delta = _native_vector(frame, shift)
            position = _vector(tuple(saved[i] + delta[i] for i in range(3)))
            derivative = _native_vector(
                frame, (*jaw.finger_translation_derivative_m_rad[side_index], 0)
            )
        elif motion == "link_rotation":
            side = record["side"]
            saved_pivot = _vector(record["saved_pivot_bot_m"])
            ideal_pivot = _vector(record["ideal_pivot_bot_m"])
            local = _bot_point(frame, saved)
            relative = tuple(local[i] - saved_pivot[i] for i in range(3))
            angle = side * (q - record["saved_closing_phase_rad"])
            c, s = math.cos(angle), math.sin(angle)
            x, y, z = relative
            rotated = (c * x - s * y, s * x + c * y, z)
            position = _native_point(
                frame, _vector(tuple(ideal_pivot[i] + rotated[i] for i in range(3)))
            )
            derivative = _native_vector(frame, (-side * rotated[1], side * rotated[0], 0))
        result[record["mass_record_id"]] = JawBodyState(position, derivative)
    return result
