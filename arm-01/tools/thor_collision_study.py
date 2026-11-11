"""Audit collision-proxy binding gaps and retain explicitly synthetic witnesses.

No source robot proxy, obstacle, enclosure or moving-body transform is invented.
This host-only fallback does not invoke CAD, a slicer or any hardware backend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from raftel_arm01.engineering.scenarios import _strict_json
from raftel_arm01.kinematics import thor_model
from raftel_arm01.kinematics.thor_collision import (
    AABB,
    PairExclusion,
    intersect_boxes,
    screen_proxies,
    transform_proxy,
)
from raftel_arm01.kinematics.thor_frames import load_frame_graph
from raftel_arm01.kinematics.thor_wrist import MotionStep

ROOT = Path(__file__).resolve().parents[1]
CAD_SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
INPUTS = {
    "mounted_inventory": "hardware/cad/thor-mounted-geometry-v2.json",
    "wrist_membership": "hardware/cad/thor-wrist-membership-v2.json",
    "frame_manifest": "config/thor-frames-v1.json",
    "metric_semantics_source_audit": "hardware/cad/thor-native-metric-semantics.json",
    "nominal_model_implementation": "src/raftel_arm01/kinematics/thor_model.py",
    "frame_implementation": "src/raftel_arm01/kinematics/thor_frames.py",
    "wrist_motion_implementation": "src/raftel_arm01/kinematics/thor_wrist.py",
    "proxy_implementation": "src/raftel_arm01/kinematics/thor_collision.py",
}


def synthetic_witnesses() -> dict:
    """Deliberate fixture dimensions; none derives from Thor or a real bench."""
    a = AABB((-0.01, -0.01, -0.01), (0.01, 0.01, 0.01)).proxy(
        "synthetic_box_a",
        "synthetic_world",
        "Declared 20mm cube test fixture",
        enclosure_status="synthetic_exact_box",
    )
    b = AABB((0.01, -0.01, -0.01), (0.03, 0.01, 0.01)).proxy(
        "synthetic_box_b",
        "synthetic_world",
        "Declared face-tangent cube fixture",
        enclosure_status="synthetic_exact_box",
    )
    obstacle = AABB((0.07, -0.01, -0.01), (0.09, 0.01, 0.01)).proxy(
        "synthetic_obstacle",
        "synthetic_world",
        "Invented fixture obstacle, not a workstation measurement",
        enclosure_status="synthetic_exact_box",
    )
    scene = screen_proxies(
        (a, b, obstacle),
        (
            PairExclusion(
                a.proxy_id,
                b.proxy_id,
                "Deliberate face-contact fixture only",
                "Explicit synthetic policy example; not a Thor bearing/gear contact decision",
            ),
        ),
    )
    # This demonstrates reuse of nominal FK, without binding any real body to it.
    local = AABB((-0.005, -0.005, -0.005), (0.005, 0.005, 0.005)).proxy(
        "synthetic_target_cube",
        "synthetic_local",
        "Arbitrary 10mm cube at nominal source link_6; no robot enclosure",
        enclosure_status="synthetic_exact_box",
    )
    pose = (0.3, -0.2, 0.4, 0.1, 0.0, 0.0)
    target = transform_proxy(local, thor_model.forward_kinematics(pose), "base_link")
    return {
        "fixture_geometry_not_source_derived": True,
        "scene": scene,
        "nominal_fk_transform_example": {
            "joint_angles_rad": pose,
            "proxy": asdict(target),
            "aabb_m": asdict(target.aabb()),
            "real_body_frame_binding": None,
            "physical_or_source_robot_collision_result": None,
        },
        "tangent_pair": asdict(intersect_boxes(a, b)),
        "separated_pair": asdict(intersect_boxes(a, obstacle)),
    }


def build_study(root: Path = ROOT) -> dict:
    raw = {}
    for role, relative in INPUTS.items():
        contents = (root / relative).read_bytes()
        if not 0 < len(contents) <= 20 * 1024 * 1024:
            raise ValueError("source input exceeds bounded audit size")
        raw[role] = contents
    inventory = _strict_json(raw["mounted_inventory"])
    membership = _strict_json(raw["wrist_membership"])
    if (
        not isinstance(inventory, dict)
        or type(inventory.get("inventory_revision")) is not int
        or inventory["inventory_revision"] != 2
        or inventory.get("native_source_revision") != CAD_SOURCE_REVISION
        or inventory.get("coordinate_frame") != "native Assembly::Model zero-pose frame, metres"
        or inventory.get("validation_class")
        != "restored_cached_geometry_with_explicit_grouping_assumptions"
        or inventory.get("native_fixture_frame_rule")
        != "Raw Shape centroid includes own placement, excludes ancestor AppParts"
    ):
        raise ValueError("unsupported inventory revision, source, frame or evidence class")
    if (
        not isinstance(membership, dict)
        or type(membership.get("schema_version")) is not int
        or membership["schema_version"] != 2
        or membership.get("native_source_revision") != CAD_SOURCE_REVISION
        or membership.get("coordinate_frame") != "native_CAD_world_m"
        or membership.get("validation_class")
        != (
            "revised installed membership and conditional gravity-only closure; "
            "not physical or conjugate gear articulation validation"
        )
    ):
        raise ValueError("unsupported membership revision, source, frame or evidence class")
    leaves = inventory.get("mounted_bodies")
    if not isinstance(leaves, list) or len(leaves) != 518 or inventory.get("instance_count") != 518:
        raise ValueError("expected the 518-leaf inventory revision")
    if any(not isinstance(row, dict) for row in leaves):
        raise ValueError("mounted leaves must be object records")
    ids = [row.get("instance_id") for row in leaves]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("mounted identities must be unique nonempty strings")
    inventory_hash = hashlib.sha256(raw["mounted_inventory"]).hexdigest()
    if membership.get("source_geometry_sha256") != inventory_hash:
        raise ValueError("wrist membership inventory raw hash mismatch")
    assignments = membership.get("memberships")
    if (
        not isinstance(assignments, list)
        or len(assignments) != len(ids)
        or any(not isinstance(row, dict) for row in assignments)
        or {r.get("instance_id") for r in assignments} != set(ids)
    ):
        raise ValueError("wrist memberships must cover the same 518 identities")
    classes = membership["motion_classes"]
    if not isinstance(classes, dict) or any(not isinstance(row, dict) for row in classes.values()):
        raise ValueError("motion classes must be object records")
    counts = Counter(row["motion_class"] for row in assignments)
    if set(counts) - set(classes) or dict(counts) != membership["counts"]:
        raise ValueError("motion class declarations/counts differ")
    for value in classes.values():
        if not isinstance(value.get("evidence"), str) or not value["evidence"].strip():
            raise ValueError("motion classes require source evidence")
        tuple(MotionStep(**step) for step in value["steps"])
    graph = load_frame_graph(root / INPUTS["frame_manifest"])
    return {
        "schema_version": 1,
        "evidence_class": "collision_proxy_mathematics_and_source_binding_gap_audit_only",
        "source_revision": inventory["native_source_revision"],
        "input_bindings": {
            role: {"path": INPUTS[role], "raw_sha256": hashlib.sha256(contents).hexdigest()}
            for role, contents in raw.items()
        },
        "source_coverage": {
            "installed_leaf_count": len(leaves),
            "wrist_motion_class_counts": dict(sorted(counts.items())),
            "inventory_coordinate_frame": inventory["coordinate_frame"],
            "inventory_record_fields": sorted(set().union(*(row.keys() for row in leaves))),
            "mounted_full_shape_proxy_bindings_verified": 0,
            "robot_geometry_proxies_constructed": 0,
            "source_geometry_enclosure_verified": False,
            "source_boxes_assumed_conservative": False,
            "robot_pair_exclusions": [],
            "robot_intended_contact_exclusion_audit_complete": False,
            "automatic_adjacent_joint_exclusions": False,
            "nonzero_robot_collision_witnesses": [],
            "unknown_static_frames": [
                {"parent": record.parent, "child": record.child, "evidence": record.evidence}
                for record in graph.records
                if record.parent_from_child is None
            ],
        },
        "binding_gates": [
            (
                "Acquire per-installed-leaf full-shape geometry and a traceable "
                "source-to-installed transform ledger; COM and volume do not determine "
                "orientation or shape."
            ),
            (
                "Prove the numerical proxy encloses the intended solid in its declared frame, "
                "including geometry/tessellation/serialization error allowances; saved "
                "BoundBox/mesh extrema are not accepted enclosure proof here."
            ),
            (
                "Audit every moving body's rigid ownership at zero and nonzero poses; "
                "COM-only bearing classes and circulating belts cannot silently become "
                "rigid body transforms."
            ),
            (
                "Reconcile wrist/jaw/rotor articulation and identify intended contact pairs "
                "with exact IDs, reasons and native evidence; adjacency is not a blanket exclusion."
            ),
            (
                "Measure and bind bench, bins, tool, held objects, wiring and other obstacles "
                "to the same expression frame; unavailable geometry remains missing."
            ),
            (
                "After discrete pose screening, add swept/intersample checks and validated "
                "physical margins; endpoint results do not establish an entire path."
            ),
        ],
        "source_motion_boundary": {
            "motion_steps_valid_as_declared_COM_model": True,
            "full_shape_rigid_articulation_proved_by_COM_model": False,
            "unresolved_membership_evidence": membership["unresolved"],
            "nominal_model_source_revision": thor_model.SOURCE_REVISION,
            "nominal_model_path": thor_model.SOURCE_PATH,
        },
        "synthetic_witnesses": synthetic_witnesses(),
        "qualification": {
            key: False
            for key in (
                "conservative_robot_enclosure",
                "complete_geometry_coverage",
                "physical_collision_clearance",
                "swept_path_clearance",
                "hardware_motion_authorized",
                "manufacturing_release",
            )
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("output must be new; existing evidence is preserved")
        report = build_study()
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print("Collision proxy source bindings remain unverified; synthetic witnesses retained")
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        print(f"Collision study failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
