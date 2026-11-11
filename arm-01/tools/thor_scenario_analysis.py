"""Run a hash-bound conditional load scenario; no native CAD or hardware I/O."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

import thor_load_analysis as loads

from raftel_arm01.engineering.jaw_loads import (
    apply_jaw_overlay,
    carry_jaw_derivatives,
    jaw_gravity_torque_nm,
)
from raftel_arm01.engineering.scenarios import (
    canonical_sha256,
    load_scenario_manifest,
    validate_scenario_manifest,
    verify_scenario_inputs,
)
from raftel_arm01.kinematics.thor_jaw_bodies import validate_jaw_ledger
from raftel_arm01.kinematics.thor_model import SOURCE_REVISION


def validate_bound_model(manifest: dict, inputs: dict[str, dict]) -> None:
    """Check cross-file contracts after exact-byte input verification."""
    scenario = validate_scenario_manifest(manifest)
    inventory, membership = inputs["inventory"], inputs["membership"]
    if inventory.get("coordinate_frame") != "native Assembly::Model zero-pose frame, metres":
        raise ValueError("bound inventory must use the native zero-pose SI frame")
    revisions = scenario["source_revisions"]
    if revisions["thor_ros"] != SOURCE_REVISION:
        raise ValueError("scenario ROS revision does not match installed nominal model")
    if any(
        inputs[role].get("native_source_revision") != revisions["thor_cad"]
        for role in ("inventory", "membership", "moving_mass")
    ):
        raise ValueError("scenario native CAD revision disagrees with a bound input")
    if membership.get("schema_version") != 2:
        raise ValueError("scenario v1 requires the revised v2 membership")
    if membership.get("source_geometry_sha256") != scenario["inputs"]["inventory"]["sha256"]:
        raise ValueError("membership is stale for bound inventory")
    if scenario["belt_mass_overrides"] != membership.get("instance_mass_overrides"):
        raise ValueError("scenario belt masses/evidence disagree with bound membership")
    required = membership.get("required_instance_mass_overrides")
    if not isinstance(required, list) or set(required) != set(scenario["belt_mass_overrides"]):
        raise ValueError("scenario must retain every revised belt mass override")
    if scenario["wrist_motion_scenario"] not in membership.get("motion_scenarios", {}):
        raise ValueError("unknown bound wrist motion scenario")
    if inventory.get("instance_count") != 518 or sum(membership.get("counts", {}).values()) != 518:
        raise ValueError("scenario expects the explicit revised 518-leaf inventory")


def sampled_extrema(cases: list[dict]) -> dict:
    """Report explicit witness cases, never a certified limit or maximum."""
    joint_witnesses = []
    for index in range(6):
        candidates = []
        for case in cases:
            row = case["joints"][index]
            value = row["required_ideal_holding_torque_nm"]
            if value is None:
                value = row["conditional_modeled_holding_torque_nm"]
            candidates.append((abs(value), value, case["name"]))
        _, signed, witness = max(candidates, key=lambda item: item[0])
        joint_witnesses.append(
            {
                "joint": cases[0]["joints"][index]["joint"],
                "sampled_max_absolute_conditional_holding_nm": abs(signed),
                "signed_witness_holding_nm": signed,
                "witness_case": witness,
            }
        )
    jaw_candidates = [
        (abs(case["conditional_jaw_holding_torque_nm"]), case)
        for case in cases
        if case["conditional_jaw_holding_torque_nm"] is not None
    ]
    jaw_witness = None
    if jaw_candidates:
        absolute, case = max(jaw_candidates, key=lambda item: item[0])
        jaw_witness = {
            "sampled_max_absolute_conditional_holding_nm": absolute,
            "signed_witness_holding_nm": case["conditional_jaw_holding_torque_nm"],
            "witness_case": case["name"],
            "coordinate": "ideal mathematical jaw closing q, not servo shaft",
        }
    return {
        "scope": "listed cases only; sampled maxima are not worst-case or physical capacity bounds",
        "arm_joints": joint_witnesses,
        "ideal_jaw": jaw_witness,
    }


def scenario_report(manifest: dict, project_root: Path | str) -> dict:
    """Verify bound files and reuse the existing mass/wrist/load engine.

    Verification happens inside this public report API so a caller cannot
    mutate an already verified input dict while retaining pinned output hashes.
    """
    scenario = validate_scenario_manifest(manifest)
    inputs = verify_scenario_inputs(scenario, project_root)
    validate_bound_model(scenario, inputs)
    inventory, membership = inputs["inventory"], inputs["membership"]
    material = scenario["material"]
    classes = loads.wrist_motion_classes(membership, scenario["wrist_motion_scenario"])
    cases = []
    mass_summary = None
    for case in scenario["cases"]:
        snapshot = loads.expand_mass_assignments(
            loads.build_thor_snapshot(
                inventory,
                printed_fraction=material["effective_whole_part_solid_fraction"],
                payload_point_m=case["payload"]["point_zero_m"],
                material=material["family"],
                material_density_kg_m3=material["density_kg_m3"],
                material_density_source=material["density_evidence"],
                instance_mass_overrides=scenario["belt_mass_overrides"],
            ),
            membership,
        )
        snapshot["wrist_conditional_gravity_closure"] = copy.deepcopy(
            membership["conditional_gravity_closure"]
        )
        bodies = snapshot["bodies"]
        motor_bodies = [
            body
            for body in bodies
            if body["mass_assignment"]["category"].startswith("manufacturer_motor_mass_")
        ]
        motor_mass = math.fsum(body["mass_kg"] for body in motor_bodies)
        if (
            len(bodies) != 517
            or len(motor_bodies) != 7
            or not math.isclose(motor_mass, 2.120, rel_tol=0, abs_tol=1e-12)
        ):
            raise ValueError("revised mass ledger must conserve 517 records and 7 motors/2.120 kg")
        mass_summary = {
            "native_leaf_count": 518,
            "mass_record_count": len(bodies),
            "motor_asset_count": len(motor_bodies),
            "motor_mass_kg": motor_mass,
            "modeled_mass_kg": math.fsum(body["mass_kg"] for body in bodies),
            "mass_record_identity_sha256": canonical_sha256(
                {body["id"]: body["mass_kg"] for body in bodies}
            ),
        }
        jaw_external = None
        if case["jaw"]["configuration"] == "ideal_body_overlay":
            ledger = inputs["jaw_bodies"]
            validate_jaw_ledger(ledger, inventory, membership)
            snapshot = apply_jaw_overlay(snapshot, ledger, case["jaw"]["closing_angle_rad"])
            jaw_external = jaw_gravity_torque_nm(
                snapshot,
                carry_jaw_derivatives(snapshot, case["joint_angles_rad"], classes),
            )
        posed = loads.articulate_wrist_snapshot(snapshot, tuple(case["joint_angles_rad"]), classes)
        result = loads.analyze(posed, payloads_kg=(case["payload"]["mass_kg"],))
        cases.append(
            {
                "name": case["name"],
                "joint_angles_rad": case["joint_angles_rad"],
                "jaw": case["jaw"],
                "payload": case["payload"],
                "modeled_center_of_mass_m": result["modeled_center_of_mass_m"],
                "payload_position_m": result["payload_position_m"],
                "joints": result["scenarios"][0]["joints"],
                "gravity_wrench_about_frame_origin": result["scenarios"][0][
                    "gravity_wrench_about_frame_origin"
                ],
                "conditional_jaw_gravity_torque_nm": jaw_external,
                "conditional_jaw_holding_torque_nm": (
                    -jaw_external if jaw_external is not None else None
                ),
                "jaw_coordinate_status": (
                    "ideal mathematical q; not servo coordinate or realized native linkage"
                    if jaw_external is not None
                    else "saved assembly has no solved common jaw coordinate"
                ),
            }
        )
    return {
        "schema_version": 1,
        "validation_class": "hash_bound_conditional_gravity_study_not_physical_validation",
        "scenario_id": scenario["scenario_id"],
        "manifest_canonical_sha256": canonical_sha256(scenario),
        "bound_inputs": scenario["inputs"],
        "source_revisions": scenario["source_revisions"],
        "coordinate_frame": scenario["coordinate_frame"],
        "units": scenario["units"],
        "gravity_m_s2": scenario["gravity_m_s2"],
        "material": material,
        "belt_mass_overrides": scenario["belt_mass_overrides"],
        "wrist_motion_scenario": scenario["wrist_motion_scenario"],
        "mass_conservation": mass_summary,
        "case_count": len(cases),
        "cases": cases,
        "sampled_extrema": sampled_extrema(cases),
        "full_physical_wrist_holding_torques_remain_unknown": True,
        "actuator_or_fabrication_qualification": False,
        "pose_feasibility_or_collision_limits_validated": False,
        "native_recompute_performed": False,
        "unresolved_gates": scenario["unresolved_gates"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        manifest = load_scenario_manifest(args.manifest)
        report = scenario_report(manifest, args.project_root)
        rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            print(rendered, end="")
        else:
            # Evidence is append-only by path: the caller chooses a new path.
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(rendered)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
