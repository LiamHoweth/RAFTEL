"""Independent cross-artifact accounting audit; no CAD or physical validation.

The load implementation may provide a mass snapshot, but coverage, aggregation,
gravity-wrench identities and input digests are checked here without importing
its calculations.  This audit cannot recover omitted native source geometry.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _number(value: Any) -> float:
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        "finite numeric value required",
    )
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("finite numeric value required") from exc
    _require(math.isfinite(number), "finite numeric value required")
    return number


def _vector(value: Any) -> tuple[float, float, float]:
    _require(isinstance(value, (list, tuple)) and len(value) == 3, "three-vector required")
    return tuple(_number(x) for x in value)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def file_sha256(path: Path) -> str:
    """Exact file bytes, deliberately distinct from canonical JSON hashing."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_coverage(inventory: dict, membership: dict, historical: dict) -> dict:
    """Check internal retained-leaf coverage, never native source completeness."""
    _require(inventory.get("inventory_revision") == 2, "inventory revision 2 required")
    _require(membership.get("schema_version") == 2, "membership schema 2 required")
    _require(not inventory.get("errors"), "inventory errors remain")
    _require(not inventory.get("missing_object_records"), "inventory has missing objects")
    _require(inventory.get("complete_mass_model") is False, "physical completeness must stay false")
    leaves = inventory["mounted_bodies"]
    by_id = {row["instance_id"]: row for row in leaves}
    _require(len(by_id) == len(leaves), "duplicate installed leaf")
    _require(inventory.get("instance_count") == len(leaves), "inventory count mismatch")
    for row in leaves:
        _require(isinstance(row["instance_id"], str) and bool(row["instance_id"]), "empty leaf ID")
        _require(_number(row["volume_mm3"]) > 0, "nonpositive solid volume")
        _require(
            isinstance(row["solid_count"], int)
            and not isinstance(row["solid_count"], bool)
            and row["solid_count"] > 0,
            "positive integer solid count required",
        )
        _vector(row["zero_world_com_m"])
        _require("Invalid" not in row.get("native_state", []), "invalid native leaf state")
        _require(row.get("shape_valid") is True, "selected native shape validity unavailable")
    rows = membership["memberships"]
    members = {row["instance_id"]: row["motion_class"] for row in rows}
    _require(len(members) == len(rows), "duplicate membership leaf")
    _require(set(members) == set(by_id), "inventory/membership coverage differs")
    _require(set(members.values()) <= set(membership["motion_classes"]), "unknown motion class")
    _require(dict(Counter(members.values())) == membership["counts"], "motion class count mismatch")
    _require(
        inventory["native_source_revision"] == membership["native_source_revision"],
        "native source revision mismatch",
    )
    old = {row["instance_id"]: row for row in historical["mounted_bodies"]}
    _require(len(old) == len(historical["mounted_bodies"]), "duplicate historical leaf")
    _require(set(old) <= set(by_id), "historical retained leaf was removed")
    _require(all(row == by_id[key] for key, row in old.items()), "historical leaf changed")
    added = set(by_id) - set(old)
    _require(
        added
        == set(membership["required_instance_mass_overrides"])
        == set(membership["instance_mass_overrides"]),
        "added-leaf explicit mass scenario coverage differs",
    )
    for key in added:
        override = membership["instance_mass_overrides"][key]
        _require(_number(override["mass_kg"]) > 0, "positive added-leaf mass required")
        _require(
            isinstance(override.get("evidence"), str) and bool(override["evidence"].strip()),
            "added-leaf mass provenance required",
        )
    _require(
        len(by_id) == 518 and len(old) == 516 and len(added) == 2,
        "this review targets the frozen 518-leaf revision only",
    )
    return {
        "installed_leaf_count": len(by_id),
        "historical_leaves_preserved": len(old),
        "added_explicit_mass_leaves": len(added),
        "inventory_internal_coverage_only": True,
        "native_source_terminal_traversal_performed": False,
    }


def audit_mass_snapshot(snapshot: dict, inventory: dict, membership: dict) -> dict:
    """Reconcile each mass record to disjoint installed leaves and COM proxies."""
    leaves = {row["instance_id"]: row for row in inventory["mounted_bodies"]}
    bodies = snapshot["bodies"]
    _require(len(bodies) == 517, "frozen revision requires 517 mass records")
    used: set[str] = set()
    motor_masses = []
    totals = []
    moments = [[], [], []]
    for body in bodies:
        path = body["instance_path"]
        owned = {key for key in leaves if key == path or key.startswith(path + "/")}
        _require(bool(owned) and not (owned & used), "missing or duplicate mass leaf ownership")
        used.update(owned)
        mass = _number(body["mass_kg"])
        _require(mass > 0, "positive mass required")
        com = _vector(body["com_m"])
        assignment = body.get("mass_assignment", body)
        _require(assignment.get("geometry_leaf_count", 1) == len(owned), "mass leaf count mismatch")
        motion = {
            row["motion_class"] for row in membership["memberships"] if row["instance_id"] in owned
        }
        _require(len(motion) == 1, "purchased asset spans incompatible motion classes")
        # At the declared zero pose, grouped purchased geometry has a uniform
        # geometric-volume COM proxy. Native->ROS is (y,-x,z), exactly once.
        volume = math.fsum(leaves[key]["volume_mm3"] for key in owned)
        expected_native = tuple(
            math.fsum(
                leaves[key]["volume_mm3"] * leaves[key]["zero_world_com_m"][i] for key in owned
            )
            / volume
            for i in range(3)
        )
        expected_com = (expected_native[1], -expected_native[0], expected_native[2])
        _require(
            all(math.isclose(com[i], expected_com[i], rel_tol=0, abs_tol=1e-12) for i in range(3)),
            "zero-pose COM proxy/frame mismatch",
        )
        if assignment["category"].startswith("manufacturer_motor_mass_"):
            motor_masses.append(mass)
        totals.append(mass)
        for i in range(3):
            moments[i].append(mass * com[i])
    _require(used == set(leaves), "mass snapshot omits installed leaves")
    _require(len(motor_masses) == 7, "seven whole motor assets required")
    _require(
        math.isclose(math.fsum(motor_masses), 2.120, rel_tol=0, abs_tol=1e-12),
        "whole motor mass differs from 2.120 kg",
    )
    total = math.fsum(totals)
    return {
        "mass_record_count": len(bodies),
        "covered_geometry_leaves": len(used),
        "whole_motor_count": len(motor_masses),
        "whole_motor_mass_kg": math.fsum(motor_masses),
        "modeled_mass_kg": total,
        "independent_zero_com_m": [math.fsum(axis) / total for axis in moments],
        "physical_mass_validated": False,
    }


def audit_study(study: dict, inventory: dict, membership: dict) -> dict:
    """Check provenance and full-body wrench identities in every stored pose."""
    _require(study.get("schema_version") == 2, "study schema 2 required")
    _require(
        study["membership_canonical_sha256"] == canonical_sha256(membership),
        "stale study membership",
    )
    _require(
        study["membership_geometry_source_sha256"] == membership["source_geometry_sha256"],
        "study geometry source mismatch",
    )
    _require(
        study.get("full_wrist_arm_and_holding_torques_remain_null") is True,
        "full wrist totals must remain unresolved",
    )
    _require(
        study.get("pose_feasibility_or_collision_limits_validated") is False,
        "stored study cannot claim collision validation",
    )
    checked = 0
    cases = study["cases"]
    _require(bool(cases), "study requires cases")
    for case in cases:
        _require(
            case["mass_assignment_summary"]["input_inventory_canonical_sha256"]
            == canonical_sha256(inventory),
            "stale study inventory",
        )
        _require(case["modeled_mass_record_count"] == 517, "study mass record count mismatch")
        mass = _number(case["modeled_mass_kg"])
        _require(mass > 0, "positive study mass required")
        for pose in case["poses"].values():
            com = _vector(pose["modeled_center_of_mass_m"])
            for payload in pose["payload_cases"]:
                joints = payload["joints"]
                _require(len(joints) == 6, "six joint results required")
                for joint in joints[4:]:
                    _require(
                        joint["arm_gravity_torque_nm"] is None
                        and joint["required_ideal_holding_torque_nm"] is None,
                        "unresolved wrist result replaced by a numeric total",
                    )
                wrench = payload["gravity_wrench_about_frame_origin"]
                force = _vector(wrench["external_force_n"])
                support = _vector(wrench["ideal_support_force_n"])
                moment = _vector(wrench["external_moment_nm"])
                reaction = _vector(wrench["ideal_support_moment_nm"])
                _require(
                    all(
                        math.isclose(force[i] + support[i], 0, abs_tol=1e-11)
                        and math.isclose(moment[i] + reaction[i], 0, abs_tol=1e-11)
                        for i in range(3)
                    ),
                    "support wrench does not balance gravity",
                )
                pmass = _number(payload["payload_kg"])
                _require(pmass >= 0, "payload mass must be nonnegative")
                _require(
                    math.isclose(force[0], 0, abs_tol=1e-11)
                    and math.isclose(force[1], 0, abs_tol=1e-11)
                    and math.isclose(force[2], -(mass + pmass) * 9.80665, abs_tol=1e-10),
                    "gravity force disagrees with total mass",
                )
                _require(
                    math.isclose(moment[2], 0, abs_tol=1e-11), "gravity cannot create yaw moment"
                )
                if pmass == 0:
                    reference = _vector(wrench["reference_m"])
                    expected = (
                        -(com[1] - reference[1]) * mass * 9.80665,
                        (com[0] - reference[0]) * mass * 9.80665,
                        0,
                    )
                    _require(
                        all(math.isclose(moment[i], expected[i], abs_tol=1e-10) for i in range(3)),
                        "gravity moment disagrees with COM",
                    )
                checked += 1
    return {"stored_payload_pose_cases_checked": checked, "gravity_m_s2": 9.80665}


def _load(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"nonfinite JSON constant: {value}")

    with path.open("rb") as stream:
        raw = stream.read(16_777_217)
    _require(len(raw) <= 16_777_216, "review JSON exceeds 16 MiB")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_constant=invalid,
            parse_float=lambda value: _number(float(value)),
        )
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON encoding or nesting") from exc
    _require(isinstance(value, dict), "JSON object required")
    return value


def independent_potential_review(
    snapshot: dict, membership: dict, jaw_ledger: dict, loads: Any, *, cases_per_phase: int = 6
) -> dict:
    """Check all seven coordinate efforts with independent SE(3) point carry.

    Source masses and the declared jaw evaluator are inputs. This independent
    product-of-exponentials implementation does not call the load implementation
    to calculate potential; the load engine supplies the efforts under review.
    """
    from raftel_arm01.engineering.jaw_loads import (
        apply_jaw_overlay,
        carry_jaw_derivatives,
        jaw_gravity_torque_nm,
    )
    from raftel_arm01.kinematics.thor_jaw_bodies import jaw_body_states

    _require(
        type(cases_per_phase) is int and 1 <= cases_per_phase <= 100, "case bound must be 1..100"
    )
    identity = ((1.0, 0, 0, 0), (0, 1.0, 0, 0), (0, 0, 1.0, 0), (0, 0, 0, 1.0))

    def product(a, b):
        return tuple(
            tuple(math.fsum(a[i][k] * b[k][j] for k in range(4)) for j in range(4))
            for i in range(4)
        )

    def about(origin, axis, angle):
        x, y, z = axis
        c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
        rotation = (
            (c + x * x * t, x * y * t - z * s, x * z * t + y * s),
            (y * x * t + z * s, c + y * y * t, y * z * t - x * s),
            (z * x * t - y * s, z * y * t + x * s, c + z * z * t),
        )
        return tuple(
            (*rotation[i], origin[i] - math.fsum(rotation[i][j] * origin[j] for j in range(3)))
            for i in range(3)
        ) + (identity[3],)

    def point(transform, position):
        return tuple(
            math.fsum(transform[i][j] * position[j] for j in range(3)) + transform[i][3]
            for i in range(3)
        )

    def ros(value):
        x, y, z = value
        return y, -x, z

    bodies = snapshot["bodies"]
    masses = {body["id"]: body["mass_kg"] for body in bodies}
    active = {
        body["id"]: sum(
            body["id"] in joint["downstream_body_ids"] for joint in snapshot["joints"][:4]
        )
        for body in bodies
    }
    rng, h = random.Random(2026111107), 1e-6
    max_gradient_error, max_position_error, count = 0.0, 0.0, 0
    for phase_name, phase in membership["motion_scenarios"].items():
        # Read the source declarations separately from the implementation helper.
        raw = json.loads(json.dumps(membership["motion_classes"]))
        for name, changes in phase["motion_class_overrides"].items():
            raw[name].update(changes)
        classes = loads.wrist_motion_classes(membership, phase_name)

        def positions(values, raw_classes=raw):
            jaw_states = jaw_body_states(jaw_ledger, values[6])
            proximal = [identity]
            for index, joint in enumerate(snapshot["joints"][:4]):
                proximal.append(
                    product(
                        proximal[-1], about(joint["origin_m"], joint["axis_unit"], values[index])
                    )
                )
            wrists = {}
            for name, declaration in raw_classes.items():
                transform = identity
                for step in declaration["steps"]:
                    angle = step["q5_coefficient"] * values[4] + step["q6_coefficient"] * values[5]
                    transform = product(
                        transform, about(ros(step["origin_m"]), ros(step["axis_unit"]), angle)
                    )
                wrists[name] = transform
            transforms = {}
            result = {}
            for body in bodies:
                identifier = body["id"]
                key = active[identifier], body["wrist_motion_class"]
                if key not in transforms:
                    transforms[key] = product(proximal[key[0]], wrists[key[1]])
                position = (
                    ros(jaw_states[identifier].position_m)
                    if identifier in jaw_states
                    else body["com_m"]
                )
                result[identifier] = point(transforms[key], position)
            payload = point(
                product(proximal[4], wrists["roll_tool"]), snapshot["payload_position_m"]
            )
            return result, payload

        def potential(values):
            points, payload = positions(values)
            return 9.80665 * math.fsum(
                [masses[key] * value[2] for key, value in points.items()] + [0.2 * payload[2]]
            )

        for _ in range(cases_per_phase):
            values = [rng.uniform(-1.1, 1.1) for _ in range(6)] + [rng.uniform(0.05, 1.45)]
            overlay = apply_jaw_overlay(snapshot, jaw_ledger, values[6])
            _require(
                {b["id"]: b["mass_kg"] for b in overlay["bodies"]} == masses,
                "jaw overlay changed mass identities",
            )
            posed = loads.articulate_wrist_snapshot(overlay, tuple(values[:6]), classes)
            points, payload = positions(values)
            for body in posed["bodies"]:
                max_position_error = max(
                    max_position_error,
                    max(abs(body["com_m"][i] - points[body["id"]][i]) for i in range(3)),
                )
            max_position_error = max(
                max_position_error,
                max(abs(payload[i] - posed["payload_position_m"][i]) for i in range(3)),
            )
            report = loads.analyze(posed, payloads_kg=(0.2,))
            efforts = []
            for row in report["scenarios"][0]["joints"]:
                own = row["arm_gravity_torque_nm"]
                if own is None:
                    own = row["conditional_modeled_wrist_gravity_contribution_nm"]
                efforts.append(own + row["payload_gravity_torque_nm"])
            efforts.append(
                jaw_gravity_torque_nm(overlay, carry_jaw_derivatives(overlay, values[:6], classes))
            )
            for coordinate in range(7):
                before, after = list(values), list(values)
                before[coordinate] -= h
                after[coordinate] += h
                observed = -(potential(after) - potential(before)) / (2 * h)
                max_gradient_error = max(max_gradient_error, abs(efforts[coordinate] - observed))
                count += 1
    _require(max_position_error < 1e-12, "independent point transforms disagree")
    _require(max_gradient_error < 3e-8, "independent potential gradients disagree")
    return {
        "evidence_class": "independent_conditional_math_not_native_or_physical_validation",
        "seed": 2026111107,
        "poses_checked": count // 7,
        "coordinate_gradient_checks": count,
        "max_position_discrepancy_m": max_position_error,
        "max_gravity_effort_discrepancy_nm": max_gradient_error,
        "payload_kg": 0.2,
        "payload_jaw_motion": "fixed_to_roll_tool_not_grasp_contact_model",
    }


def review(root: Path, snapshot: dict | None = None) -> dict:
    cad = root / "hardware" / "cad"
    inventory_path = cad / "thor-mounted-geometry-v2.json"
    inventory = _load(inventory_path)
    membership = _load(cad / "thor-wrist-membership-v2.json")
    historical_path = cad / "thor-mounted-geometry.json"
    historical = _load(historical_path)
    _require(
        file_sha256(inventory_path) == membership["source_geometry_sha256"],
        "exact inventory file-byte SHA256 mismatch",
    )
    _require(
        file_sha256(historical_path)
        == inventory["completeness_correction"]["historical_inventory_sha256"],
        "exact historical file-byte SHA256 mismatch",
    )
    result = {
        "schema_version": 1,
        "evidence_class": "independent_cross_artifact_accounting_not_native_or_physical_validation",
        "coverage": audit_coverage(inventory, membership, historical),
        "study": audit_study(_load(cad / "thor-wrist-load-study-v2.json"), inventory, membership),
        "input_file_sha256": {
            path.name: file_sha256(path)
            for path in (
                inventory_path,
                historical_path,
                cad / "thor-wrist-membership-v2.json",
                cad / "thor-wrist-load-study-v2.json",
            )
        },
    }
    if snapshot is not None:
        result["mass_snapshot"] = audit_mass_snapshot(snapshot, inventory, membership)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--snapshot", type=Path, help="Optional externally generated zero-pose ledger"
    )
    parser.add_argument(
        "--build-snapshot",
        action="store_true",
        help="Use existing load builder, then independently check its accounting",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--math-checks",
        action="store_true",
        help="Independent seven-coordinate potential checks; implies --build-snapshot",
    )
    args = parser.parse_args()
    try:
        _require(
            not (args.snapshot and (args.build_snapshot or args.math_checks)),
            "choose one snapshot source",
        )
        snapshot = _load(args.snapshot) if args.snapshot else None
        if args.build_snapshot or args.math_checks:
            spec = importlib.util.spec_from_file_location(
                "_desktop_review_load_implementation", args.root / "tools" / "thor_load_analysis.py"
            )
            _require(
                spec is not None and spec.loader is not None, "load implementation unavailable"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            cad = args.root / "hardware" / "cad"
            inventory = _load(cad / "thor-mounted-geometry-v2.json")
            membership = _load(cad / "thor-wrist-membership-v2.json")
            snapshot = module.expand_mass_assignments(
                module.build_thor_snapshot(
                    inventory, instance_mass_overrides=membership["instance_mass_overrides"]
                ),
                membership,
            )
        result = review(args.root, snapshot)
        if args.math_checks:
            result["independent_potential_review"] = independent_potential_review(
                snapshot, membership, _load(cad / "thor-jaw-body-ledger.json"), module
            )
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
        else:
            print(text, end="")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
