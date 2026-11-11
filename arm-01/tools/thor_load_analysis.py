"""Pose-specific gravity analysis from explicit, provenance-bearing model inputs.

No default robot mass is invented. Supply a JSON snapshot with mounted body COMs,
world joint axes, mass assumptions and coverage status. Results are static model
estimates, never actuator qualification or physical validation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

GRAVITY_M_S2 = 9.80665
Vector = tuple[float, float, float]
MASS_KINDS = {"manufacturer_listing", "measured", "cad_density_estimate", "assumption"}


def finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("expected finite real number")
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("expected finite real number") from error
    if not math.isfinite(result):
        raise ValueError("expected finite real number")
    return result


def vector(value: Any) -> Vector:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError("expected three coordinates")
    return tuple(finite_number(component) for component in value)


def cross(left: Vector, right: Vector) -> Vector:
    ax, ay, az = left
    bx, by, bz = right
    return vector((ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx))


def dot(left: Vector, right: Vector) -> float:
    try:
        return finite_number(math.fsum(a * b for a, b in zip(left, right, strict=True)))
    except OverflowError as error:
        raise ValueError("moment calculation overflowed") from error


@dataclass(frozen=True)
class Body:
    identifier: str
    mass_kg: float
    com_m: Vector

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError("body identifier must be nonempty")
        if finite_number(self.mass_kg) < 0:
            raise ValueError("body mass must be nonnegative")
        vector(self.com_m)


@dataclass(frozen=True)
class Joint:
    name: str
    origin_m: Vector
    axis_unit: Vector
    downstream_body_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("joint name must be nonempty")
        vector(self.origin_m)
        axis = vector(self.axis_unit)
        if not math.isclose(math.hypot(*axis), 1.0, rel_tol=0, abs_tol=1e-9):
            raise ValueError("joint axis must be a unit vector")
        if len(set(self.downstream_body_ids)) != len(self.downstream_body_ids):
            raise ValueError("a body cannot be counted twice for one joint")


def gravity_torque_nm(joint: Joint, bodies: tuple[Body, ...]) -> float:
    """External gravity torque, projected onto a world-frame revolute axis.

    The required ideal quasi-static holding torque is the negative of this
    value. Joint downstream membership must come from the traced assembly tree.
    """
    by_id = {body.identifier: body for body in bodies}
    if len(by_id) != len(bodies):
        raise ValueError("duplicate mounted body IDs")
    if not set(joint.downstream_body_ids) <= set(by_id):
        raise ValueError("joint references a body absent from the snapshot")
    moments = []
    for identifier in joint.downstream_body_ids:
        body = by_id[identifier]
        displacement = vector(tuple(c - o for c, o in zip(body.com_m, joint.origin_m, strict=True)))
        force = vector((0.0, 0.0, -body.mass_kg * GRAVITY_M_S2))
        moments.append(dot(joint.axis_unit, cross(displacement, force)))
    try:
        return finite_number(math.fsum(moments))
    except OverflowError as error:
        raise ValueError("moment calculation overflowed") from error


def gravity_wrench(bodies: tuple[Body, ...], reference_m: Vector = (0, 0, 0)) -> dict:
    """Gravity force/moment about a declared world-frame reference point.

    The negative of this wrench is the ideal static support reaction. No clamp
    preload, dynamic load, cable force, compliance or contact sharing is inferred.
    """
    reference = vector(reference_m)
    force_z = finite_number(-math.fsum(body.mass_kg for body in bodies) * GRAVITY_M_S2)
    moments = []
    for body in bodies:
        displacement = vector(tuple(body.com_m[i] - reference[i] for i in range(3)))
        force = vector((0.0, 0.0, -body.mass_kg * GRAVITY_M_S2))
        moments.append(cross(displacement, force))
    moment = vector(tuple(math.fsum(value[i] for value in moments) for i in range(3)))
    return {
        "reference_m": list(reference),
        "external_force_n": [0.0, 0.0, force_z],
        "external_moment_nm": list(moment),
        "ideal_support_force_n": [0.0, 0.0, -force_z],
        "ideal_support_moment_nm": [-value for value in moment],
    }


def center_of_mass(bodies: tuple[Body, ...]) -> Vector | None:
    total = finite_number(math.fsum(body.mass_kg for body in bodies))
    if total == 0:
        return None
    return vector(
        tuple(math.fsum(body.mass_kg * body.com_m[i] for body in bodies) / total for i in range(3))
    )


def dense_volume_mass_kg(
    volume_mm3: float, material_density_kg_m3: float, effective_solid_fraction: float
) -> float:
    """Explicit scenario conversion, not a measured print mass or infill rule.

    Effective solid fraction includes walls, skins and infill together. A slicer
    infill setting alone must never be substituted for this whole-part fraction.
    """
    volume = finite_number(volume_mm3)
    density = finite_number(material_density_kg_m3)
    fraction = finite_number(effective_solid_fraction)
    if volume < 0 or density <= 0 or not 0 < fraction <= 1:
        raise ValueError("volume/density/fraction outside physical scenario bounds")
    return finite_number(volume * 1e-9 * density * fraction)


def nominal_channel_efforts(
    holding_joint_nm: tuple[float, ...], shoulder_b_fraction: float
) -> tuple[float, ...]:
    """Virtual-work dual of the nominal Thor drive-coordinate convention.

    These are generalized efforts conjugate to nominal GRBL channel coordinates,
    NOT motor shaft torques. Actual transmission ratios, efficiencies and load
    sharing require separate validation. Caller must choose shoulder sharing;
    the mechanism does not guarantee an equal split.
    """
    if len(holding_joint_nm) != 6:
        raise ValueError("exactly six joint holding torques required")
    t1, t2, t3, t4, t5, t6 = (finite_number(value) for value in holding_joint_nm)
    fraction = finite_number(shoulder_b_fraction)
    if not 0 <= fraction <= 1:
        raise ValueError("shoulder fraction must be 0..1")
    values = (t1, -fraction * t2, -(1 - fraction) * t2, -t3, t4, t6 / 4 - t5 / 2, t6 / 4 + t5 / 2)
    return tuple(finite_number(value) for value in values)


def validate_snapshot(data: dict) -> tuple[tuple[Joint, ...], tuple[Body, ...], Vector]:
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
    ):
        raise ValueError("snapshot requires schema_version 1")
    if not isinstance(data.get("coordinate_frame"), str) or not data["coordinate_frame"].strip():
        raise ValueError("coordinate_frame required")
    coverage = data.get("coverage")
    if not isinstance(coverage, dict) or type(coverage.get("complete")) is not bool:
        raise ValueError("explicit complete/partial mass coverage required")
    if not isinstance(coverage.get("omitted_components"), list):
        raise ValueError("explicit omitted_components list required")
    if coverage["complete"] and coverage["omitted_components"]:
        raise ValueError("complete coverage cannot also list omitted components")
    if not isinstance(data.get("sources"), list) or not data["sources"]:
        raise ValueError("source provenance required")
    bodies = []
    instance_paths = []
    for raw in data["bodies"]:
        for field in ("mass_kind", "com_kind", "evidence", "instance_path"):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                raise ValueError(f"body {field} provenance required")
        if raw["mass_kind"] not in MASS_KINDS:
            raise ValueError("unsupported mass evidence kind")
        instance_paths.append(raw["instance_path"])
        bodies.append(Body(raw["id"], finite_number(raw["mass_kg"]), vector(raw["com_m"])))
    if len(set(instance_paths)) != len(instance_paths):
        raise ValueError("duplicate mounted CAD instance path")
    if len({body.identifier for body in bodies}) != len(bodies):
        raise ValueError("duplicate mounted body IDs")
    joints = tuple(
        Joint(
            raw["name"],
            vector(raw["origin_m"]),
            vector(raw["axis_unit"]),
            tuple(raw["downstream_body_ids"]),
        )
        for raw in data["joints"]
    )
    if len(joints) != 6 or len({joint.name for joint in joints}) != 6:
        raise ValueError("exactly six distinct arm joints required")
    by_id = {body.identifier for body in bodies}
    if any(not set(joint.downstream_body_ids) <= by_id for joint in joints):
        raise ValueError("joint references absent body")
    return joints, tuple(bodies), vector(data["payload_position_m"])


def _rotate_vector(value: Vector, axis: Vector, angle: float) -> Vector:
    c, s = math.cos(angle), math.sin(angle)
    perpendicular = cross(axis, value)
    parallel = dot(axis, value)
    return vector(
        tuple(value[i] * c + perpendicular[i] * s + axis[i] * parallel * (1 - c) for i in range(3))
    )


def articulate_snapshot(data: dict, angles_rad: tuple[float, ...]) -> dict:
    """Rigidly articulate a declared zero-pose snapshot using its serial joint tree.

    The caller owns frame/zero-pose and downstream membership reconciliation.
    This function does not infer attachment or calibrate a physical robot.
    Joint order must run proximal to distal. Every rotation is applied only to
    that joint's declared downstream bodies; later joint axes and tool point
    follow the serial chain. Original input data is preserved.
    """
    joints, _, payload_position = validate_snapshot(data)
    if len(angles_rad) != 6:
        raise ValueError("exactly six joint angles required")
    angles = tuple(finite_number(angle) for angle in angles_rad)
    for joint, raw, angle in zip(joints, data["joints"], angles, strict=True):
        resolved = raw.get("body_membership_resolved", True)
        if type(resolved) is not bool:
            raise ValueError("body_membership_resolved must be boolean")
        if not resolved and angle != 0:
            raise ValueError(f"cannot articulate unresolved body membership at {joint.name}")
    for proximal, distal in zip(joints[:-1], joints[1:], strict=True):
        if not set(distal.downstream_body_ids) <= set(proximal.downstream_body_ids):
            raise ValueError("serial articulation requires nested downstream body sets")
    result = copy.deepcopy(data)
    points = {raw["id"]: vector(raw["com_m"]) for raw in result["bodies"]}
    origins = [joint.origin_m for joint in joints]
    axes = [joint.axis_unit for joint in joints]
    tool = payload_position
    for index, (joint, angle) in enumerate(zip(joints, angles, strict=True)):
        origin, axis = origins[index], axes[index]

        def rotate_point(
            point: Vector, origin: Vector = origin, axis: Vector = axis, angle: float = angle
        ) -> Vector:
            relative = vector(tuple(point[i] - origin[i] for i in range(3)))
            rotated = _rotate_vector(relative, axis, angle)
            return vector(tuple(origin[i] + rotated[i] for i in range(3)))

        for identifier in joint.downstream_body_ids:
            points[identifier] = rotate_point(points[identifier])
        for later in range(index + 1, 6):
            origins[later] = rotate_point(origins[later])
            axes[later] = _rotate_vector(axes[later], axis, angle)
        tool = rotate_point(tool)
    for raw in result["bodies"]:
        raw["com_m"] = list(points[raw["id"]])
    for index, raw in enumerate(result["joints"]):
        raw["origin_m"] = list(origins[index])
        raw["axis_unit"] = list(axes[index])
    result["payload_position_m"] = list(tool)
    result["pose"] = {
        "joint_angles_rad_from_declared_zero": list(angles),
        "method": "serial rigid articulation of supplied zero-pose axes/COMs",
        "physical_zero_or_limits_validated": False,
    }
    return result


def analyze(data: dict, payloads_kg: tuple[float, ...] = (0, 0.1, 0.2)) -> dict:
    joints, bodies, payload_position = validate_snapshot(data)
    if not payloads_kg:
        raise ValueError("at least one payload scenario required")
    if any(finite_number(mass) < 0 for mass in payloads_kg):
        raise ValueError("payload mass cannot be negative")
    scenarios = []
    for payload_kg in payloads_kg:
        rows = []
        for index, (joint, raw_joint) in enumerate(zip(joints, data["joints"], strict=True)):
            membership_resolved = raw_joint.get("body_membership_resolved", True)
            if type(membership_resolved) is not bool:
                raise ValueError("body_membership_resolved must be boolean")
            arm_torque = gravity_torque_nm(joint, bodies) if membership_resolved else None
            modeled_wrist_contribution = None
            if index >= 4 and "wrist_com_jacobians" in data:
                jacobians = data["wrist_com_jacobians"]
                if set(jacobians) != {body.identifier for body in bodies}:
                    raise ValueError("wrist Jacobians must cover each modeled body exactly once")
                modeled_wrist_contribution = finite_number(
                    math.fsum(
                        -body.mass_kg
                        * GRAVITY_M_S2
                        * vector(jacobians[body.identifier][index - 4])[2]
                        for body in bodies
                    )
                )
                if membership_resolved:
                    arm_torque = modeled_wrist_contribution
            payload_joint = Joint(joint.name, joint.origin_m, joint.axis_unit, ("__payload__",))
            payload_torque = gravity_torque_nm(
                payload_joint, (Body("__payload__", payload_kg, payload_position),)
            )
            external = (
                finite_number(arm_torque + payload_torque) if arm_torque is not None else None
            )
            rows.append(
                {
                    "joint": joint.name,
                    "arm_gravity_torque_nm": arm_torque,
                    "payload_gravity_torque_nm": payload_torque,
                    "required_ideal_holding_torque_nm": -external if external is not None else None,
                    "body_membership_resolved": membership_resolved,
                }
            )
            if modeled_wrist_contribution is not None:
                rows[-1]["conditional_modeled_wrist_gravity_contribution_nm"] = (
                    modeled_wrist_contribution
                )
                closure = data.get("wrist_conditional_gravity_closure")
                if closure is not None:
                    if (
                        not isinstance(closure, dict)
                        or not isinstance(closure.get("assumptions"), list)
                        or not closure["assumptions"]
                        or any(
                            not isinstance(item, str) or not item.strip()
                            for item in closure["assumptions"]
                        )
                        or not isinstance(closure.get("evidence"), str)
                        or not closure["evidence"].strip()
                    ):
                        raise ValueError(
                            "conditional wrist gravity closure requires assumptions/evidence"
                        )
                    rows[-1]["conditional_modeled_holding_torque_nm"] = finite_number(
                        -(modeled_wrist_contribution + payload_torque)
                    )
        scenarios.append(
            {
                "payload_kg": payload_kg,
                "joints": rows,
                "gravity_wrench_about_frame_origin": gravity_wrench(
                    bodies + (Body("__payload__", payload_kg, payload_position),)
                ),
            }
        )
    return {
        "schema_version": 1,
        "validation_class": "pose_specific_analytical_estimate_not_physical_validation",
        "coordinate_frame": data["coordinate_frame"],
        "gravity_m_s2": GRAVITY_M_S2,
        "coverage": data["coverage"],
        "modeled_body_count": len(bodies),
        "modeled_mass_kg": finite_number(math.fsum(body.mass_kg for body in bodies)),
        "modeled_center_of_mass_m": center_of_mass(bodies),
        "sources": data["sources"],
        "mass_assignment_summary": data.get("mass_assignment_summary"),
        "joint_geometry_evidence": data["joints"],
        "body_mass_and_com_evidence": data["bodies"],
        "snapshot_pose": data.get("pose", "explicit world-coordinate snapshot"),
        "payload_position_m": list(payload_position),
        "scenarios": scenarios,
        "actuator_qualification": False,
        "uncertainties": [
            "Static gravity only: no acceleration, friction, impacts or cable forces",
            "No moving torque/thermal qualification or physical load-sharing evidence",
            "CAD centroid and mass assumptions are not physical measurements",
            "A favorable saved pose does not establish worst-case payload capacity",
        ],
    }


MATERIAL_REFERENCES = {
    "PLA": {
        "reference_product": "Prusament PLA technical datasheet v1.1",
        "density_kg_m3": 1240,
        "source": "https://prusament.com/wp-content/uploads/2022/10/PLA_Prusament_TDS_2021_10_EN.pdf",
    },
    "PETG": {
        "reference_product": "Prusament PETG technical datasheet v1.1 (2022-02-16)",
        "density_kg_m3": 1270,
        "source": "https://prusament.com/wp-content/uploads/2022/10/PETG_Prusament_TDS_2021_10_EN.pdf",
    },
    "ABS": {
        "reference_product": "Polymaker PolyLite ABS TDS EN v5.5",
        "density_kg_m3": 1040,
        "source": "https://polymaker.com.cn/wp-content/uploads/lana-downloads/PolyLite-ABS_TDS_EN_V5.5.pdf",
    },
}


def material_reference(
    family: str, density_kg_m3: float | None = None, density_source: str | None = None
) -> dict:
    if family not in MATERIAL_REFERENCES:
        raise ValueError("material must be PLA, PETG or ABS")
    reference = dict(
        MATERIAL_REFERENCES[family], family=family, actual_user_brand_or_density_verified=False
    )
    if density_kg_m3 is not None:
        density = finite_number(density_kg_m3)
        if density <= 0:
            raise ValueError("material density must be positive")
        if not isinstance(density_source, str) or not density_source.strip():
            raise ValueError("custom material density requires its source or estimate provenance")
        reference.update(
            density_kg_m3=density,
            source=density_source,
            reference_product="caller-supplied density scenario",
        )
    elif density_source is not None:
        raise ValueError("density source override requires an explicit density")
    return reference


MOTOR_SOURCES = {
    "Stepper_Nema17x40": (0.290, "17HS15-0404S"),
    "Nema17_GearBox": (0.380, "17HS13-0404S-PG5"),
    "Stepper_Nema17x34": (0.230, "17HS13-0404S1"),
}
# Whole-asset engineering mass allowances, NOT manufacturer-qualified values.
ASSET_ALLOWANCES_KG = {
    "Servomotor": 0.055,
    "Fan_40x40": 0.012,
    "Fan_50x50": 0.025,
    "ArduinoMega": 0.040,
    "OnOffButton": 0.015,
    "ResetButton": 0.010,
    "JackDC": 0.003,
    "OpticSensor": 0.002,
    "MicroEndstop": 0.003,
    "M8Connector": 0.005,
}


def build_thor_snapshot(
    inventory: dict,
    printed_fraction: float = 0.5,
    payload_point_m: Vector = (0, 0, 0.7025242557054092),
    material: str = "PLA",
    material_density_kg_m3: float | None = None,
    material_density_source: str | None = None,
    instance_mass_overrides: dict[str, dict] | None = None,
) -> dict:
    """Mass-scenario overlay on installed native CAD leaves, with source frames.

    CAD->nominal frame Rz(-pi/2) is corroborated by shoulder/elbow cylindrical
    axis lines, not a calibration of all physical signs or the gripper TCP.
    Purchased asset masses are counted once; geometry volume supplies a COM
    proxy only. CAD material classification remains an explicit assumption.
    Optional positive per-leaf mass scenarios require evidence and cannot replace
    a whole purchased-asset mass. No internal rotor/stator split is inferred.
    """
    from raftel_arm01.kinematics import thor_model

    reference = material_reference(material, material_density_kg_m3, material_density_source)
    fraction = finite_number(printed_fraction)
    if not 0 < fraction <= 1:
        raise ValueError("printed solid fraction must be in (0,1]")
    leaves = inventory["mounted_bodies"]
    instance_ids = [leaf["instance_id"] for leaf in leaves]
    if len(instance_ids) != len(set(instance_ids)):
        raise ValueError("duplicate installed CAD leaf instance")
    if any("Invalid" in leaf.get("native_state", []) for leaf in leaves):
        raise ValueError("installed CAD leaf has invalid native state")
    if inventory.get("missing_object_records") or inventory.get("errors"):
        raise ValueError("installed geometry inventory has unresolved records/errors")
    overrides = {} if instance_mass_overrides is None else instance_mass_overrides
    if not isinstance(overrides, dict) or not set(overrides) <= set(instance_ids):
        raise ValueError("instance mass overrides must reference installed geometry leaves")
    for override in overrides.values():
        if (
            not isinstance(override, dict)
            or finite_number(override.get("mass_kg")) <= 0
            or not isinstance(override.get("evidence"), str)
            or not override["evidence"].strip()
        ):
            raise ValueError("instance mass override requires positive mass and evidence")
    groups = {}
    assets = {}
    assignments = []
    omitted = []
    for leaf in leaves:
        path = leaf["instance_id"]
        segments = path.split("/")
        asset = segments[2].split("::", 1)[1]
        root_group = leaf["root_subassembly"]
        com = vector(leaf["zero_world_com_m"])
        # Native Y pitch line -> source nominal X pitch line, preserving Z.
        nominal_com = vector((com[1], -com[0], com[2]))
        volume = finite_number(leaf["volume_mm3"])
        if volume <= 0 or leaf.get("solid_count", 0) <= 0:
            raise ValueError("mass overlay requires positive-solid installed leaves")
        product = next((name for name in MOTOR_SOURCES if asset.startswith(name)), None)
        allowance = next(
            (
                name
                for name in ASSET_ALLOWANCES_KG
                if asset == name or (asset.startswith(name) and asset[len(name) :].isdigit())
            ),
            None,
        )
        if product or allowance:
            if path in overrides:
                raise ValueError("whole purchased-asset mass cannot be replaced by a leaf override")
            key = "/".join(segments[:3])
            record = assets.setdefault(
                key,
                {
                    "root": root_group,
                    "asset": asset,
                    "product": product,
                    "allowance": allowance,
                    "parts": [],
                },
            )
            record["parts"].append((volume, nominal_com, path))
            continue
        linked = leaf.get("linked_object") or leaf["object_reference"]
        source_doc = linked.split("::", 1)[0]
        source_custom_print = not source_doc.startswith("Assembly")
        if path in overrides:
            mass = finite_number(overrides[path]["mass_kg"])
            category = "explicit_instance_mass_scenario"
        elif source_custom_print or "GripperFinger" in asset:
            mass = dense_volume_mass_kg(volume, reference["density_kg_m3"], fraction)
            category = f"printed_{material}_scenario"
        elif "Screw" in leaf["label"] or "Nut" in leaf["label"]:
            mass = dense_volume_mass_kg(volume, 7850, 1)
            category = "steel_fastener_density_assumption"
        elif any(word in asset for word in ("Bearing", "Collar", "Shaft")) or asset.startswith(
            "_x"
        ):
            mass = dense_volume_mass_kg(volume, 7850, 1)
            category = "steel_hardware_density_assumption"
        elif "Magnet" in asset:
            mass = dense_volume_mass_kg(volume, 7500, 1)
            category = "magnet_density_assumption"
        elif "Pulley" in asset or "GT2x40" in asset:
            mass = dense_volume_mass_kg(volume, 2700, 1)
            category = "aluminium_pulley_density_assumption"
        elif "Belt" in asset:
            mass = dense_volume_mass_kg(volume, 1200, 1)
            category = "belt_density_assumption"
        elif "WheelHorn" in asset:
            mass = dense_volume_mass_kg(volume, 1150, 1)
            category = "polymer_horn_density_assumption"
        else:
            omitted.append(
                {
                    "instance_path": path,
                    "label": leaf["label"],
                    "reason": "material/mass classification unresolved",
                }
            )
            continue
        assignments.append(
            {
                "instance_path": path,
                "root": root_group,
                "mass_kg": mass,
                "com_m": list(nominal_com),
                "category": category,
                "volume_mm3": volume,
            }
        )
        if path in overrides:
            assignments[-1]["mass_evidence"] = overrides[path]["evidence"]
    for path, record in assets.items():
        total_volume = math.fsum(part[0] for part in record["parts"])
        com = vector(
            tuple(
                math.fsum(volume * point[i] for volume, point, _ in record["parts"]) / total_volume
                for i in range(3)
            )
        )
        if record["product"]:
            mass, model = MOTOR_SOURCES[record["product"]]
            category = "manufacturer_motor_mass_" + model
        else:
            mass = ASSET_ALLOWANCES_KG[record["allowance"]]
            category = "whole_asset_mass_allowance_" + record["allowance"]
        assignments.append(
            {
                "instance_path": path,
                "root": record["root"],
                "mass_kg": mass,
                "com_m": list(com),
                "category": category,
                "volume_mm3": total_volume,
                "geometry_leaf_count": len(record["parts"]),
            }
        )
    for row in assignments:
        groups.setdefault(row["root"], []).append(row)
    active = {
        "AssemblyBase": 0,
        "AssemblyArt1": 1,
        "AssemblyArt2": 2,
        "AssemblyArt3": 3,
        "AssemblyArt4": 4,
        "AssemblyArt56": 5,
    }
    bodies = []
    for group, members in sorted(groups.items()):
        mass = math.fsum(row["mass_kg"] for row in members)
        com = vector(
            tuple(
                math.fsum(row["mass_kg"] * row["com_m"][i] for row in members) / mass
                for i in range(3)
            )
        )
        bodies.append(
            {
                "id": group,
                "instance_path": "Assembly::Model/" + group,
                "mass_kg": mass,
                "com_m": list(com),
                "mass_kind": "assumption",
                "com_kind": "mass_weighted_native_CAD_centroid_proxies",
                "evidence": "Installed CAD leaves with explicit mass/density/allowance overlay",
                "active_joint_count_assumption": active[group],
                "mass_assignments": members,
            }
        )
    frames, _ = thor_model.chain((0.0,) * 6)
    payload_point = vector(payload_point_m)
    joints = []
    for index, frame in enumerate(frames, 1):
        joints.append(
            {
                "name": frame.name,
                "origin_m": list(frame.origin_m),
                "axis_unit": list(frame.axis_unit),
                "body_membership_resolved": index <= 4,
                "downstream_body_ids": [
                    body["id"] for body in bodies if body["active_joint_count_assumption"] >= index
                ],
            }
        )
    snapshot = {
        "schema_version": 1,
        "coordinate_frame": "Thor-ROS nominal base_link from native CAD Rz(-pi/2)",
        "sources": [
            "Thor CAD286b081fe6f056d87c379b884781ef77ff6a0159 installed native leaves",
            "hardware/cad/thor-mounted-geometry.json and thor-axis-evidence.json",
            "Thor-ROS e11a56b5aa0d89f0b68a3ea7bd084eab4a050952 nominal axis lines",
            "StepperOnline exact linked motor manufacturer mass listings checked2026-11-11",
            "Prusament PLA TDS density1.24g/cm3; other material/asset masses assumed",
        ],
        "coverage": {
            "complete": False,
            "omitted_components": [
                "external cables, motor wiring absent from CAD, mount/protection changes",
                "unresolved wrist q5/q6 self-mass membership",
                *[row["instance_path"] for row in omitted],
            ],
        },
        "bodies": bodies,
        "joints": joints,
        "payload_position_m": list(payload_point),
        "mass_assignment_summary": {
            "printed_PLA_density_kg_m3": 1240,
            "printed_effective_whole_part_solid_fraction": fraction,
            "native_positive_leaf_count": len(leaves),
            "assigned_mass_record_count": len(assignments),
            "omitted_unclassified_instances": omitted,
            "all_material_and_COM_assignments_are_unmeasured": True,
            "payload_point_source": (
                "CAD two-finger distal plane at z702.524255705mm, "
                "axis-centered study point; not a calibrated TCP or measured object COM"
            ),
            "input_inventory_canonical_sha256": hashlib.sha256(
                json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "whole_asset_mass_allowances_kg": ASSET_ALLOWANCES_KG,
            "density_assumptions_kg_m3": {
                "steel": 7850,
                "magnet": 7500,
                "aluminium": 2700,
                "belt": 1200,
                "horn": 1150,
            },
            "cad_to_nominal_rotation": [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
            "native_input_geometry_validation_class": inventory.get("validation_class"),
        },
    }
    # Preserve the original PLA report schema/defaults for baseline traceability.
    if material != "PLA" or material_density_kg_m3 is not None:
        summary = snapshot["mass_assignment_summary"]
        summary.pop("printed_PLA_density_kg_m3")
        summary["printed_material_density_kg_m3"] = reference["density_kg_m3"]
        summary["printed_material_reference"] = reference
        snapshot["sources"][-1] = reference["source"]
    if overrides:
        snapshot["mass_assignment_summary"]["explicit_instance_mass_overrides"] = copy.deepcopy(
            overrides
        )
    return snapshot


def expand_mass_assignments(snapshot: dict, memberships: dict) -> dict:
    """Expose each mass record without splitting or duplicating purchased assets.

    An asset represented by multiple geometry leaves may be consolidated only
    if every leaf has the same wrist motion class. Membership is evidence input,
    never inferred from a part name here.
    """
    validate_snapshot(snapshot)
    rows = memberships["memberships"]
    by_path = {row["instance_id"]: row["motion_class"] for row in rows}
    if len(by_path) != len(rows):
        raise ValueError("duplicate wrist membership instance")
    result = copy.deepcopy(snapshot)
    result["bodies"] = []
    used = set()
    expanded = {}
    for group in snapshot["bodies"]:
        expanded[group["id"]] = []
        for assignment in group["mass_assignments"]:
            path = assignment["instance_path"]
            leaves = {key for key in by_path if key == path or key.startswith(path + "/")}
            if not leaves or leaves & used:
                raise ValueError("missing or multiply assigned wrist membership leaves")
            if len(leaves) != assignment.get("geometry_leaf_count", 1):
                raise ValueError("mass record geometry leaf count disagrees with membership")
            classes = {by_path[key] for key in leaves}
            if len(classes) != 1:
                raise ValueError("consolidated mass asset spans multiple wrist motion classes")
            used.update(leaves)
            identifier = path
            expanded[group["id"]].append(identifier)
            result["bodies"].append(
                {
                    "id": identifier,
                    "instance_path": path,
                    "mass_kg": assignment["mass_kg"],
                    "com_m": assignment["com_m"],
                    "mass_kind": "assumption",
                    "com_kind": group["com_kind"],
                    "evidence": group["evidence"],
                    "mass_assignment": copy.deepcopy(assignment),
                    "wrist_motion_class": classes.pop(),
                }
            )
    if used != set(by_path):
        raise ValueError("wrist membership contains leaves absent from mass ledger")
    for joint in result["joints"]:
        joint["downstream_body_ids"] = [
            identifier for group in joint["downstream_body_ids"] for identifier in expanded[group]
        ]
    validate_snapshot(result)
    return result


def articulate_wrist_snapshot(
    snapshot: dict, angles_rad: tuple[float, ...], motion_classes: dict
) -> dict:
    """Evaluate explicit wrist COM trajectories then carry them through q1–q4.

    Class steps use the snapshot's declared zero frame. Unresolved membership
    flags stay unresolved: this can report a conditional COM contribution while
    withholding full joint holding torque for omitted internal moving masses.
    """
    from raftel_arm01.kinematics.thor_wrist import MotionStep, point_state

    validate_snapshot(snapshot)
    if len(angles_rad) != 6:
        raise ValueError("exactly six joint angles required")
    angles = tuple(finite_number(angle) for angle in angles_rad)
    local = copy.deepcopy(snapshot)
    derivatives = {}

    def evaluate(point: Vector, name: str):
        raw = motion_classes[name]
        if not isinstance(raw.get("evidence"), str) or not raw["evidence"].strip():
            raise ValueError("every wrist motion class requires evidence, including fixed classes")
        steps = tuple(MotionStep(**step) for step in raw["steps"])
        return point_state(point, angles[4], angles[5], steps)

    for body in local["bodies"]:
        state = evaluate(vector(body["com_m"]), body["wrist_motion_class"])
        body["com_m"] = list(state.position_m)
        derivatives[body["id"]] = [state.dq5_m_rad, state.dq6_m_rad]
    payload = evaluate(vector(local["payload_position_m"]), "roll_tool")
    local["payload_position_m"] = list(payload.position_m)
    proximal = articulate_snapshot(local, (*angles[:4], 0.0, 0.0))
    # q1–q4 rotate the wrist velocities as vectors, without an origin offset.
    origins = [vector(joint["origin_m"]) for joint in snapshot["joints"]]
    axes = [vector(joint["axis_unit"]) for joint in snapshot["joints"]]
    for index, angle in enumerate(angles[:4]):
        origin, axis = origins[index], axes[index]
        carried = set(snapshot["joints"][index]["downstream_body_ids"])
        for identifier in carried:
            derivatives[identifier] = [
                _rotate_vector(value, axis, angle) for value in derivatives[identifier]
            ]
        for later in range(index + 1, 6):
            relative = vector(tuple(origins[later][i] - origin[i] for i in range(3)))
            rotated = _rotate_vector(relative, axis, angle)
            origins[later] = vector(tuple(origin[i] + rotated[i] for i in range(3)))
            axes[later] = _rotate_vector(axes[later], axis, angle)
    # Roll's carried axis changes with fold; an origin anywhere on the line is equivalent.
    fold_origin, fold_axis = origins[4], axes[4]
    relative = vector(tuple(origins[5][i] - fold_origin[i] for i in range(3)))
    rotated = _rotate_vector(relative, fold_axis, angles[4])
    proximal["joints"][5]["origin_m"] = [fold_origin[i] + rotated[i] for i in range(3)]
    proximal["joints"][5]["axis_unit"] = list(_rotate_vector(axes[5], fold_axis, angles[4]))
    proximal["wrist_com_jacobians"] = derivatives
    proximal["pose"] = {
        "joint_angles_rad_from_declared_zero": list(angles),
        "method": "evidence-declared wrist COM paths with analytical Jacobians; q1–q4 rigid carry",
        "physical_zero_or_limits_validated": False,
    }
    return proximal


def conditional_wrist_bounds(snapshot: dict) -> dict:
    """Upper triangle bounds on *modeled* Art56 contributions at q5=q6=0.

    Every modeled wrist-group member is included, irrespective of unresolved
    internal attachment. Bounds do not include omitted masses or validate
    physical material/COM assumptions, transmissions or actuator performance.
    """
    joints, _, point = validate_snapshot(snapshot)
    wrist = next(body for body in snapshot["bodies"] if body["id"] == "AssemblyArt56")
    result = {}
    for joint in joints[4:]:
        self_bound = 0.0
        for member in wrist["mass_assignments"]:
            displacement = vector(tuple(member["com_m"][i] - joint.origin_m[i] for i in range(3)))
            radius = math.hypot(*cross(joint.axis_unit, displacement))
            self_bound += member["mass_kg"] * GRAVITY_M_S2 * radius
        payload_displacement = vector(tuple(point[i] - joint.origin_m[i] for i in range(3)))
        payload_radius = math.hypot(*cross(joint.axis_unit, payload_displacement))
        result[joint.name] = {
            "modeled_self_mass_magnitude_bound_nm": self_bound,
            "payload200g_bound_at_study_point_nm": 0.2 * GRAVITY_M_S2 * payload_radius,
            "payload200g_total_radial_offset_sensitivity_nm": {
                str(offset): 0.2 * GRAVITY_M_S2 * (payload_radius + offset)
                for offset in (0.0, 0.025, 0.05)
            },
        }
    return {
        "scope": "modeled wrist group only; conditional on mass/COM and zero-q5 geometry",
        "formula": "sum(m_i*g*distance_perpendicular_to_axis_i)",
        "physical_load_bound_or_actuator_qualification": False,
        "joint_internal_membership_resolved": False,
        "joints": result,
    }


def cad_load_study(
    inventory: dict,
    material: str = "PLA",
    material_density_kg_m3: float | None = None,
    material_density_source: str | None = None,
) -> dict:
    """Compact reproducible CAD mass/pose/payload sensitivity report."""
    poses = {
        "upright": (0.0,) * 6,
        "shoulder_horizontal": (0.0, math.pi / 2, 0.0, 0.0, 0.0, 0.0),
        "elbow_horizontal": (0.0, 0.0, math.pi / 2, 0.0, 0.0, 0.0),
        "shoulder_elbow_45deg": (0.0, math.pi / 4, math.pi / 4, 0.0, 0.0, 0.0),
    }
    cases = []
    for fraction in (0.35, 0.5, 1.0):
        zero = build_thor_snapshot(
            inventory,
            fraction,
            material=material,
            material_density_kg_m3=material_density_kg_m3,
            material_density_source=material_density_source,
        )
        posed_results = {}
        for name, angles in poses.items():
            analysis = analyze(articulate_snapshot(zero, angles))
            posed_results[name] = {
                "joint_angles_rad": list(angles),
                "modeled_center_of_mass_m": analysis["modeled_center_of_mass_m"],
                "payload_cases": analysis["scenarios"],
            }
        cases.append(
            {
                "printed_whole_part_fraction": fraction,
                "modeled_mass_kg": math.fsum(body["mass_kg"] for body in zero["bodies"]),
                "group_masses_kg": {body["id"]: body["mass_kg"] for body in zero["bodies"]},
                "mass_assignment_summary": zero["mass_assignment_summary"],
                "coverage": zero["coverage"],
                "conditional_wrist_bounds": conditional_wrist_bounds(zero),
                "poses": posed_results,
            }
        )
    return {
        "schema_version": 1,
        "validation_class": "CAD_derived_mass_scenarios_not_physical_or_actuator_validation",
        "sources": zero["sources"],
        "coordinate_frame": zero["coordinate_frame"],
        "payload_position_m": zero["payload_position_m"],
        "pose_feasibility_or_collision_limits_validated": False,
        "motor_shaft_torques_or_capacity_qualified": False,
        "gravity_m_s2": GRAVITY_M_S2,
        "cases": cases,
    }


def material_comparison_report(inventory: dict) -> dict:
    """Reference-filament density comparison at identical geometry/fill assumptions."""
    cases = []
    for family in MATERIAL_REFERENCES:
        snapshot = build_thor_snapshot(inventory, 0.5, material=family)
        pose = articulate_snapshot(snapshot, (0, math.pi / 2, 0, 0, 0, 0))
        analysis = analyze(pose)
        rows = analysis["scenarios"][2]["joints"]
        cases.append(
            {
                "reference": material_reference(family),
                "modeled_mass_kg": analysis["modeled_mass_kg"],
                "group_masses_kg": {body["id"]: body["mass_kg"] for body in snapshot["bodies"]},
                "shoulder_horizontal_200g_holding_torque_nm": rows[1][
                    "required_ideal_holding_torque_nm"
                ],
                "elbow_horizontal_200g_holding_torque_nm": rows[2][
                    "required_ideal_holding_torque_nm"
                ],
                "input_inventory_canonical_sha256": snapshot["mass_assignment_summary"][
                    "input_inventory_canonical_sha256"
                ],
            }
        )
    return {
        "validation_class": "reference_filament_density_comparison_not_structural_approval",
        "user_available_material_families": ["PLA", "PETG", "ABS"],
        "actual_user_filament_brand_or_density_verified": False,
        "effective_whole_part_solid_fraction": 0.5,
        "nonprinted_materials_motors_and_horn_unchanged": True,
        "geometry_axes_pose_and_payload_same_as_PLA_baseline": True,
        "printed_material_stiffness_creep_or_strength_validated": False,
        "cases": cases,
    }


def wrist_motion_classes(memberships: dict, scenario_name: str) -> dict:
    """Convert an explicitly named native-frame conditional scenario to ROS."""
    if memberships["coordinate_frame"] != "native_CAD_world_m":
        raise ValueError("wrist membership requires native_CAD_world_m frame")
    classes = copy.deepcopy(memberships["motion_classes"])
    scenario = memberships["motion_scenarios"][scenario_name]
    for name, changes in scenario["motion_class_overrides"].items():
        classes[name].update(copy.deepcopy(changes))
    for declaration in classes.values():
        for step in declaration["steps"]:
            for field in ("origin_m", "axis_unit"):
                x, y, z = vector(step[field])
                step[field] = [y, -x, z]
    return classes


def wrist_load_study(inventory: dict, memberships: dict) -> dict:
    """Traceable reference-material COM-motion study, retaining unresolved totals."""
    if memberships.get("schema_version") == 2:
        required = memberships.get("required_instance_mass_overrides")
        overrides = memberships.get("instance_mass_overrides")
        if (
            not isinstance(required, list)
            or not required
            or len(set(required)) != len(required)
            or not isinstance(overrides, dict)
            or set(required) != set(overrides)
        ):
            raise ValueError("revised wrist study requires explicit masses for every added belt")
    poses = {
        "upright": (0.0,) * 6,
        "shoulder_horizontal": (0, math.pi / 2, 0, 0, 0, 0),
        "shoulder_horizontal_fold45_roll30": (0, math.pi / 2, 0, 0, math.pi / 4, math.pi / 6),
        "mixed_pose_fold_minus30_roll60": (0.2, 0.6, -0.3, 0.4, -math.pi / 6, math.pi / 3),
    }
    cases = []
    for family in MATERIAL_REFERENCES:
        zero = expand_mass_assignments(
            build_thor_snapshot(
                inventory,
                material=family,
                instance_mass_overrides=memberships.get("instance_mass_overrides"),
            ),
            memberships,
        )
        if memberships.get("schema_version") == 2:
            zero["wrist_conditional_gravity_closure"] = copy.deepcopy(
                memberships["conditional_gravity_closure"]
            )
            zero["sources"][1] = (
                "hardware/cad/thor-mounted-geometry-v2.json and thor-axis-evidence.json"
            )
        for scenario_name, scenario in memberships["motion_scenarios"].items():
            classes = wrist_motion_classes(memberships, scenario_name)
            results = {}
            for pose_name, angles in poses.items():
                posed = articulate_wrist_snapshot(zero, angles, classes)
                analysis = analyze(posed)
                results[pose_name] = {
                    "joint_angles_rad": list(angles),
                    "modeled_center_of_mass_m": analysis["modeled_center_of_mass_m"],
                    "payload_cases": analysis["scenarios"],
                }
            cases.append(
                {
                    "material_reference": material_reference(family),
                    "printed_effective_whole_part_solid_fraction": 0.5,
                    "scenario_name": scenario_name,
                    "side_rotor_sign_s": scenario["side_rotor_sign_s"],
                    "physical_handedness_verified": False,
                    "modeled_mass_kg": math.fsum(body["mass_kg"] for body in zero["bodies"]),
                    "modeled_mass_record_count": len(zero["bodies"]),
                    "mass_assignment_summary": zero["mass_assignment_summary"],
                    "poses": results,
                }
            )
            if memberships.get("schema_version") == 2:
                cases[-1]["phase_evidence_class"] = scenario["phase_evidence_class"]
    report = {
        "schema_version": 1,
        "validation_class": "conditional_CAD_COM_motion_not_full_wrist_load_or_actuator_validation",
        "coordinate_frame": zero["coordinate_frame"],
        "membership_canonical_sha256": hashlib.sha256(
            json.dumps(memberships, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "membership_geometry_source_sha256": memberships["source_geometry_sha256"],
        "membership_counts": memberships["counts"],
        "sources": [*zero["sources"], "hardware/cad/thor-wrist-membership.json"],
        "unresolved": memberships["unresolved"],
        "full_wrist_arm_and_holding_torques_remain_null": True,
        "contribution_scope": (
            "Declared composite COM paths only. Upstream motor internals and traveling belts "
            "are not decomposed; bearing COM paths do not model race inertia; jaws frozen."
        ),
        "pose_feasibility_or_collision_limits_validated": False,
        "cases": cases,
    }
    if memberships.get("schema_version") == 2:
        report.update(
            schema_version=2,
            validation_class="revised_conditional_CAD_gravity_model_not_physical_or_actuator_validation",
            sources=[*zero["sources"], "hardware/cad/thor-wrist-membership-v2.json"],
            conditional_gravity_closure=memberships["conditional_gravity_closure"],
            chosen_intended_phase=memberships["chosen_intended_phase"],
            inventory_coverage_revision=memberships["inventory_coverage_revision"],
            contribution_scope=(
                "Revised declared COM paths including input pulleys and two added belts; "
                "balanced internal motor rotors and uniform circulating fixed belt paths are "
                "explicit gravity-only assumptions. Jaws are frozen at the saved CAD pose."
            ),
        )
    return report


def nominal_payload_increment_report() -> dict:
    """Supplemental source-model payload increments with all arm mass excluded."""
    from raftel_arm01.kinematics import thor_model

    joint_frames, _ = thor_model.chain((0.0,) * 6)
    tool = thor_model.forward_kinematics((0.0,) * 6, "gripper_mid_point")
    zero = {
        "schema_version": 1,
        "coordinate_frame": "Thor-ROS nominal base_link",
        "sources": [
            "https://github.com/AngelLM/Thor-ROS/blob/"
            + thor_model.SOURCE_REVISION
            + "/"
            + thor_model.SOURCE_PATH
        ],
        "coverage": {"complete": False, "omitted_components": ["ALL robot self mass"]},
        "bodies": [],
        "joints": [
            {
                "name": joint.name,
                "origin_m": list(joint.origin_m),
                "axis_unit": list(joint.axis_unit),
                "downstream_body_ids": [],
            }
            for joint in joint_frames
        ],
        "payload_position_m": [tool[i][3] for i in range(3)],
    }
    poses = {
        "upright": (0.0,) * 6,
        "shoulder_horizontal": (0.0, math.pi / 2, 0.0, 0.0, 0.0, 0.0),
        "elbow_horizontal": (0.0, 0.0, math.pi / 2, 0.0, 0.0, 0.0),
        "shoulder_elbow_45deg": (0.0, math.pi / 4, math.pi / 4, 0.0, 0.0, 0.0),
    }
    return {
        "validation_class": "nominal_URDF_payload_increments_only_not_complete_arm_loads",
        "meaning": "ALL arm self mass omitted; never use these numbers to size actuators",
        "pose_feasibility_or_limits_validated": False,
        "poses": {
            name: analyze(articulate_snapshot(zero, angles)) for name, angles in poses.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "snapshot", nargs="?", type=Path, help="Explicit provenance-bearing world-frame model JSON"
    )
    parser.add_argument(
        "--nominal-payload-increments",
        action="store_true",
        help="Source-model payload increments; excludes ALL arm self mass",
    )
    parser.add_argument(
        "--cad-inventory",
        type=Path,
        help="Installed native geometry JSON; generate CAD mass/pose sensitivity",
    )
    parser.add_argument("--material", choices=tuple(MATERIAL_REFERENCES), default="PLA")
    parser.add_argument("--material-density-kg-m3", type=float)
    parser.add_argument("--material-density-source")
    parser.add_argument("--compare-materials", action="store_true")
    parser.add_argument(
        "--wrist-membership", type=Path, help="Explicit conditional wrist motion ledger"
    )
    parser.add_argument("--output", type=Path, help="New JSON report path; no overwriting")
    args = parser.parse_args()
    try:
        if (
            sum((bool(args.snapshot), args.nominal_payload_increments, bool(args.cad_inventory)))
            != 1
        ):
            raise ValueError("choose snapshot, --nominal-payload-increments OR --cad-inventory")
        material_override = (
            args.material != "PLA"
            or args.material_density_kg_m3 is not None
            or args.material_density_source is not None
        )
        if (material_override or args.compare_materials) and not args.cad_inventory:
            raise ValueError("material options require --cad-inventory")
        if args.compare_materials and material_override:
            raise ValueError("reference comparison cannot combine material overrides")
        if args.wrist_membership and (
            not args.cad_inventory or args.compare_materials or material_override
        ):
            raise ValueError(
                "--wrist-membership requires unmodified --cad-inventory reference cases"
            )
        if args.cad_inventory:
            inventory = json.loads(args.cad_inventory.read_text())
            if args.wrist_membership:
                membership = json.loads(args.wrist_membership.read_text())
                digest = hashlib.sha256(args.cad_inventory.read_bytes()).hexdigest()
                if digest != membership["source_geometry_sha256"]:
                    raise ValueError("wrist membership geometry digest does not match inventory")
                report = wrist_load_study(inventory, membership)
            else:
                report = (
                    material_comparison_report(inventory)
                    if args.compare_materials
                    else cad_load_study(
                        inventory,
                        args.material,
                        args.material_density_kg_m3,
                        args.material_density_source,
                    )
                )
        elif args.nominal_payload_increments:
            report = nominal_payload_increment_report()
        else:
            report = analyze(json.loads(args.snapshot.read_text()))
        text = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x") as stream:
                stream.write(text)
        else:
            print(text, end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
