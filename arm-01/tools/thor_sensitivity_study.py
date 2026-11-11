"""Bounded conditional load sweeps with witness cases, never physical limits."""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
from collections.abc import Mapping
from pathlib import Path

import thor_load_analysis as loads
from thor_scenario_analysis import validate_bound_model

from raftel_arm01.engineering.jaw_loads import (
    apply_jaw_overlay,
    carry_jaw_derivatives,
    jaw_gravity_torque_nm,
)
from raftel_arm01.engineering.scenarios import (
    canonical_sha256,
    finite_number,
    load_scenario_manifest,
    validate_scenario_manifest,
    verify_scenario_inputs,
)
from raftel_arm01.kinematics import thor_model
from raftel_arm01.kinematics.thor_jaw_bodies import validate_jaw_ledger
from raftel_arm01.kinematics.thor_wrist import MotionStep, point_state

MAX_CASES = 4096


def _keys(value, expected: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{name} requires exactly {sorted(expected)}")
    return value


def _text(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} requires explicit nonempty text")
    return value


def _values(value, name: str) -> list:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} requires an explicit nonempty list")
    return value


def _vector(value, size: int, name: str) -> list[float]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{name} requires {size} finite values")
    return [finite_number(item) for item in value]


def documented_reference_request(manifest: dict) -> dict:
    """Earlier declared study values, not recommended materials/travel/payloads."""
    unique_poses = {}
    for case in manifest["cases"]:
        angles = case["joint_angles_rad"]
        unique_poses.setdefault(
            tuple(angles),
            {"name": case["name"].removesuffix("_saved"), "joint_angles_rad": angles},
        )
    return {
        "schema_version": 1,
        "evidence_class": "conditional_analytical_sensitivity",
        "units": {"angle": "rad", "mass": "kg", "position": "m", "torque": "N*m"},
        "materials": [
            {
                "name": family,
                "density_kg_m3": reference["density_kg_m3"],
                "evidence": reference["source"],
            }
            for family in ("PLA", "PETG", "ABS")
            for reference in (loads.material_reference(family),)
        ],
        "printed_fractions": {
            "values": [0.35, 0.5, 1.0],
            "evidence": (
                "Earlier thor-load-analysis.md effective whole-part fraction scenarios; "
                "not slicer infill or measured fractions."
            ),
        },
        "poses": list(unique_poses.values()),
        "pose_evidence": (
            "Explicit arm poses from bound scenario manifest; no calibrated stops, "
            "collision or physical feasibility proof."
        ),
        "jaws": [
            {"configuration": "saved_frozen", "closing_angle_rad": None},
            {"configuration": "ideal_body_overlay", "closing_angle_rad": 0},
            {"configuration": "ideal_body_overlay", "closing_angle_rad": math.pi / 3},
        ],
        "jaw_evidence": (
            "Saved pose kept independent; ideal q=0/60deg examples from "
            "thor-gripper-kinematics.md with explicit body alignment proposal."
        ),
        "payload_masses": {
            "values": [0, 0.1, 0.2],
            "evidence": "Earlier load-study payload scenarios only; no safe payload rating.",
        },
        "payload_point_zero_m": [0, 0, 0.7025242557054092],
        "payload_offsets_zero_m": {
            "values": [[0, 0, 0], [0.025, 0, 0], [0.05, 0, 0], [0, 0.025, 0], [0, 0.05, 0]],
            "evidence": (
                "Earlier 25/50mm radial COM sensitivity values along explicit nominal "
                "ROS +X/+Y directions; object COM and overhang unmeasured."
            ),
        },
        "payload_attachment_evidence": (
            "Fixed relative to roll_tool, independent of jaw q; no pad contact, "
            "retention or object motion model."
        ),
    }


def validate_sweep_request(data) -> dict:
    keys = {
        "schema_version",
        "evidence_class",
        "units",
        "materials",
        "printed_fractions",
        "poses",
        "pose_evidence",
        "jaws",
        "jaw_evidence",
        "payload_masses",
        "payload_point_zero_m",
        "payload_offsets_zero_m",
        "payload_attachment_evidence",
    }
    result = copy.deepcopy(_keys(data, keys, "sweep request"))
    if type(result["schema_version"]) is not int or result["schema_version"] != 1:
        raise ValueError("unsupported sensitivity schema version")
    if result["evidence_class"] != "conditional_analytical_sensitivity":
        raise ValueError("sensitivity evidence class must remain conditional analytical")
    if result["units"] != {"angle": "rad", "mass": "kg", "position": "m", "torque": "N*m"}:
        raise ValueError("sensitivity request requires explicit SI units")
    materials = _values(result["materials"], "materials")
    names = []
    for material in materials:
        _keys(material, {"name", "density_kg_m3", "evidence"}, "material")
        name = material["name"]
        if not isinstance(name, str) or name not in {"PLA", "PETG", "ABS"}:
            raise ValueError("material name must be PLA, PETG or ABS")
        names.append(name)
        material["density_kg_m3"] = finite_number(material["density_kg_m3"])
        if material["density_kg_m3"] <= 0:
            raise ValueError("material density must be positive")
        _text(material["evidence"], "material density evidence")
    if len(set(names)) != len(names):
        raise ValueError("material names must be unique")
    for name in ("printed_fractions", "payload_masses", "payload_offsets_zero_m"):
        section = _keys(result[name], {"values", "evidence"}, name)
        values = _values(section["values"], name)
        _text(section["evidence"], name + " evidence")
        if name == "payload_offsets_zero_m":
            section["values"] = [_vector(value, 3, name) for value in values]
        else:
            section["values"] = [finite_number(value) for value in values]
            if name == "printed_fractions" and any(
                not 0 < value <= 1 for value in section["values"]
            ):
                raise ValueError("whole-part fractions must lie in (0,1]")
            if name == "payload_masses" and any(value < 0 for value in section["values"]):
                raise ValueError("payload masses must be nonnegative")
        if len({canonical_sha256(value) for value in section["values"]}) != len(values):
            raise ValueError(f"duplicate {name} values")
    poses = _values(result["poses"], "poses")
    pose_names = []
    for pose in poses:
        _keys(pose, {"name", "joint_angles_rad"}, "pose")
        pose_names.append(_text(pose["name"], "pose name"))
        pose["joint_angles_rad"] = _vector(pose["joint_angles_rad"], 6, "arm joint angles")
    if len(set(pose_names)) != len(pose_names):
        raise ValueError("pose names must be unique")
    jaws = _values(result["jaws"], "jaws")
    for jaw in jaws:
        _keys(jaw, {"configuration", "closing_angle_rad"}, "jaw")
        if jaw["configuration"] == "saved_frozen":
            if jaw["closing_angle_rad"] is not None:
                raise ValueError("saved jaw has no common solved closing coordinate")
        elif jaw["configuration"] == "ideal_body_overlay":
            q = finite_number(jaw["closing_angle_rad"])
            if not 0 <= q < math.pi / 2:
                raise ValueError("ideal jaw angle outside mathematical study branch")
            jaw["closing_angle_rad"] = q
        else:
            raise ValueError("jaw mode must distinguish saved/ideal configurations")
    if len({canonical_sha256(jaw) for jaw in jaws}) != len(jaws):
        raise ValueError("jaw configurations must be unique")
    for name in ("pose_evidence", "jaw_evidence", "payload_attachment_evidence"):
        _text(result[name], name)
    result["payload_point_zero_m"] = _vector(result["payload_point_zero_m"], 3, "payload point")
    count = math.prod(
        (
            len(materials),
            len(result["printed_fractions"]["values"]),
            len(poses),
            len(jaws),
            len(result["payload_masses"]["values"]),
            len(result["payload_offsets_zero_m"]["values"]),
        )
    )
    if count > MAX_CASES:
        raise ValueError(f"sweep has {count} cases; bounded maximum is {MAX_CASES}")
    return result


def _carried_offset(offset: list[float], angles: list[float], classes: Mapping) -> tuple:
    steps = tuple(
        MotionStep(**{**step, "origin_m": (0, 0, 0)}) for step in classes["roll_tool"]["steps"]
    )
    wrist = point_state(offset, angles[4], angles[5], steps).position_m
    _, proximal = thor_model.chain((*angles[:4], 0.0, 0.0))
    return tuple(math.fsum(proximal[i][j] * wrist[j] for j in range(3)) for i in range(3))


def _witness(case: dict, coordinate: int) -> dict:
    return {
        **case["parameters"],
        "coordinate": f"joint_{coordinate + 1}" if coordinate < 6 else "ideal_jaw_q",
        "signed_conditional_holding_nm": case["holding_nm"][coordinate],
    }


def _summarize(cases: list[dict]) -> tuple[list[dict], list[dict]]:
    extrema = []
    for coordinate in range(7):
        available = [case for case in cases if case["holding_nm"][coordinate] is not None]
        if not available:
            continue
        witness = max(available, key=lambda case: abs(case["holding_nm"][coordinate]))
        extrema.append(
            {
                "coordinate": f"joint_{coordinate + 1}" if coordinate < 6 else "ideal_jaw_q",
                "sampled_max_absolute_conditional_holding_nm": abs(
                    witness["holding_nm"][coordinate]
                ),
                "sampled_min_signed_holding_nm": min(
                    case["holding_nm"][coordinate] for case in available
                ),
                "sampled_max_signed_holding_nm": max(
                    case["holding_nm"][coordinate] for case in available
                ),
                "witness": _witness(witness, coordinate),
            }
        )
    labels = {
        "material": "Actual filament product/density and measured printed masses",
        "printed_fraction": "Per-part slicer/model mass and weighed effective whole-part mass",
        "payload_mass_kg": "Actual object mass",
        "payload_offset_zero_m": "Actual grasped-object COM and overhang in the tool frame",
        "jaw": "Realizable jaw alignment, closure coordinate and moving-part COM ownership",
    }
    rankings = []
    for parameter, measurement in labels.items():
        groups = {}
        for case in cases:
            remainder = {
                key: value for key, value in case["parameters"].items() if key != parameter
            }
            groups.setdefault(canonical_sha256(remainder), []).append(case)
        best = None
        for group in groups.values():
            for coordinate in range(7):
                available = [case for case in group if case["holding_nm"][coordinate] is not None]
                if len(available) < 2:
                    continue
                low = min(available, key=lambda case: case["holding_nm"][coordinate])
                high = max(available, key=lambda case: case["holding_nm"][coordinate])
                span = high["holding_nm"][coordinate] - low["holding_nm"][coordinate]
                if best is None or span > best[0]:
                    best = span, coordinate, low, high
        if best is not None:
            span, coordinate, low, high = best
            rankings.append(
                {
                    "varied_parameter": parameter,
                    "missing_measurement": measurement,
                    "maximum_sampled_conditional_holding_spread_nm": span,
                    "low_witness": _witness(low, coordinate),
                    "high_witness": _witness(high, coordinate),
                }
            )
    rankings.sort(
        key=lambda item: item["maximum_sampled_conditional_holding_spread_nm"], reverse=True
    )
    return extrema, rankings


def sensitivity_report(manifest: dict, request: dict, project_root: Path | str) -> dict:
    """Verify inputs then enumerate a bounded grid, reusing body pose results."""
    scenario, sweep = validate_scenario_manifest(manifest), validate_sweep_request(request)
    inputs = verify_scenario_inputs(scenario, project_root)
    validate_bound_model(scenario, inputs)
    if "jaw_bodies" not in inputs:
        raise ValueError("sensitivity study requires the bound jaw body ledger")
    inventory, membership, jaw = (inputs[key] for key in ("inventory", "membership", "jaw_bodies"))
    validate_jaw_ledger(jaw, inventory, membership)
    classes = loads.wrist_motion_classes(membership, scenario["wrist_motion_scenario"])
    cases, mass_cases = [], []
    for material, fraction in itertools.product(
        sweep["materials"], sweep["printed_fractions"]["values"]
    ):
        zero = loads.expand_mass_assignments(
            loads.build_thor_snapshot(
                inventory,
                printed_fraction=fraction,
                material=material["name"],
                material_density_kg_m3=material["density_kg_m3"],
                material_density_source=material["evidence"],
                payload_point_m=sweep["payload_point_zero_m"],
                instance_mass_overrides=scenario["belt_mass_overrides"],
            ),
            membership,
        )
        motors = [
            body
            for body in zero["bodies"]
            if body["mass_assignment"]["category"].startswith("manufacturer_motor_mass_")
        ]
        if (
            len(zero["bodies"]) != 517
            or len(motors) != 7
            or not math.isclose(
                math.fsum(body["mass_kg"] for body in motors), 2.120, rel_tol=0, abs_tol=1e-12
            )
        ):
            raise ValueError("sensitivity mass records/motor assets were not conserved")
        mass_cases.append(
            {
                "material": material,
                "printed_fraction": fraction,
                "modeled_mass_kg": math.fsum(body["mass_kg"] for body in zero["bodies"]),
            }
        )
        for pose, jaw_case in itertools.product(sweep["poses"], sweep["jaws"]):
            angles = pose["joint_angles_rad"]
            overlay = apply_jaw_overlay(
                zero,
                jaw,
                jaw_case["closing_angle_rad"],
                mode="saved" if jaw_case["configuration"] == "saved_frozen" else "ideal",
            )
            posed = loads.articulate_wrist_snapshot(overlay, tuple(angles), classes)
            result = loads.analyze(posed, payloads_kg=(0,))
            self_efforts = [
                row["arm_gravity_torque_nm"]
                if row["arm_gravity_torque_nm"] is not None
                else row["conditional_modeled_wrist_gravity_contribution_nm"]
                for row in result["scenarios"][0]["joints"]
            ]
            jaw_holding = None
            if jaw_case["configuration"] == "ideal_body_overlay":
                jaw_holding = -jaw_gravity_torque_nm(
                    overlay, carry_jaw_derivatives(overlay, angles, classes)
                )
            for offset in sweep["payload_offsets_zero_m"]["values"]:
                delta = _carried_offset(offset, angles, classes)
                payload_point = tuple(posed["payload_position_m"][i] + delta[i] for i in range(3))
                payload = loads.Body("__payload__", 1, payload_point)
                unit_efforts = [
                    loads.gravity_torque_nm(
                        loads.Joint(
                            row["name"], row["origin_m"], row["axis_unit"], ("__payload__",)
                        ),
                        (payload,),
                    )
                    for row in posed["joints"]
                ]
                for payload_mass in sweep["payload_masses"]["values"]:
                    cases.append(
                        {
                            "parameters": {
                                "material": material,
                                "printed_fraction": fraction,
                                "pose": pose,
                                "jaw": jaw_case,
                                "payload_mass_kg": payload_mass,
                                "payload_offset_zero_m": offset,
                            },
                            "holding_nm": [
                                finite_number(-(self_efforts[i] + payload_mass * unit_efforts[i]))
                                for i in range(6)
                            ]
                            + [jaw_holding],
                        }
                    )
    extrema, rankings = _summarize(cases)
    return {
        "schema_version": 1,
        "validation_class": (
            "bounded_conditional_gravity_sensitivity_not_capacity_or_physical_validation"
        ),
        "manifest_canonical_sha256": canonical_sha256(scenario),
        "sweep_request_canonical_sha256": canonical_sha256(sweep),
        "bound_inputs": scenario["inputs"],
        "source_revisions": scenario["source_revisions"],
        "wrist_motion_scenario": scenario["wrist_motion_scenario"],
        "request": sweep,
        "sampling": {
            "method": "complete declared Cartesian grid",
            "random_seed": None,
            "case_count": len(cases),
            "maximum_allowed_cases": MAX_CASES,
            "sampled_extrema_are_certified_worst_cases": False,
        },
        "mass_conservation": {
            "native_leaves": 518,
            "mass_records_per_scenario": 517,
            "motor_assets": 7,
            "whole_motor_mass_kg": 2.120,
            "jaw_overlay_adds_removes_or_reweights_records": False,
            "material_fraction_mass_cases": mass_cases,
        },
        "sampled_extrema": extrema,
        "ranked_missing_measurements_by_modeled_sensitivity": rankings,
        "ranking_scope": (
            "matched grid cases varying one declared parameter; not risk priority, "
            "confidence, tolerances or physical uncertainty bounds"
        ),
        "full_physical_wrist_holding_torques_remain_unknown": True,
        "ideal_jaw_effort_is_servo_shaft_torque": False,
        "pose_limits_collision_actuator_or_fabrication_qualification": False,
        "native_recompute_or_hardware_access": False,
        "unresolved_gates": scenario["unresolved_gates"],
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request", type=Path, help="explicit versioned sweep request JSON")
    source.add_argument("--documented-reference-study", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        manifest = load_scenario_manifest(args.manifest)
        request = (
            json.loads(args.request.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
            if args.request is not None
            else documented_reference_request(manifest)
        )
        report = sensitivity_report(manifest, request, args.project_root)
        rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            print(rendered, end="")
        else:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(rendered)
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
