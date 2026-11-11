"""Saved-zero numerical mounted AABB pairs; no physical collision clearance.

The pinned native capture supplies already-converted metre coordinates. No
additional object placement, source rescaling, articulation or native process
is performed. All numerical proxy enclosure statuses remain unknown.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

from raftel_arm01.engineering.scenarios import _strict_json, canonical_sha256
from raftel_arm01.kinematics.thor_collision import AABB, intersect_boxes
from raftel_arm01.kinematics.thor_frames import IDENTITY, finite, rigid_transform

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_PATH = "hardware/cad/thor-native-mounted-bounds-v1.json"
INVENTORY_PATH = "hardware/cad/thor-mounted-geometry-v2.json"
PINNED_CAPTURE_SHA256 = "d223ce7cb2bb9813b24640be2dc783b1054381624061b23951cf71e9bf067fe4"
SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
FRAME = "native master document saved-zero frame; complete Model ancestor chain; metres"
POLICY = {
    "schema_version": 1,
    "study_mode": "saved_zero_numerical_AABB_diagnostics_not_physical_collision_screening",
    "selected_bounds_field": "world_optimal_bounds_m",
    "native_api": "optimalBoundingBox(False, True)",
    "native_api_interpretation": "triangulation disabled; shape-tolerance expansion enabled",
    "comparison_bounds_field": "world_default_bounds_m",
    "coordinate_units": "m",
    "placement_application": "none; capture already supplies world bounds in metres",
    "enclosure_status": "unknown",
    "pair_scope": "all unordered pairs of the exact 518 source identities",
    "numerical_tolerance_m": 1e-12,
    "candidate_retention": "every selected-metric overlap/contact; every default-only candidate",
    "pair_exclusions": [],
    "automatic_adjacency_exclusions": False,
    "separated_witness_limit": 16,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _bounds(value) -> AABB:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("bounds require [minimum_xyz, maximum_xyz] in metres")
    return AABB(value[0], value[1])


def validate_inputs(
    capture_raw: bytes, inventory_raw: bytes, *, expected_capture_sha256=PINNED_CAPTURE_SHA256
) -> tuple[dict, list[dict]]:
    if _sha(capture_raw) != expected_capture_sha256:
        raise ValueError("mounted capture raw SHA256 differs from frozen input pin")
    capture, inventory = _strict_json(capture_raw), _strict_json(inventory_raw)
    if not isinstance(capture, dict) or not isinstance(inventory, dict):
        raise ValueError("source inputs must be JSON objects")
    if (
        type(capture.get("schema_version")) is not int
        or capture["schema_version"] != 1
        or capture.get("evidence_class") != "native_saved_zero_installed_shape_bounds"
        or capture.get("status") != "complete_numerical_bounds_capture"
        or capture.get("cad_revision") != SOURCE_REVISION
        or capture.get("frame") != FRAME
    ):
        raise ValueError("unsupported mounted capture schema, source, scope or coordinate units")
    if (
        type(inventory.get("inventory_revision")) is not int
        or inventory["inventory_revision"] != 2
        or inventory.get("native_source_revision") != SOURCE_REVISION
        or inventory.get("coordinate_frame") != "native Assembly::Model zero-pose frame, metres"
        or inventory.get("validation_class")
        != "restored_cached_geometry_with_explicit_grouping_assumptions"
        or capture.get("inventory_sha256") != _sha(inventory_raw)
    ):
        raise ValueError("inventory semantic contract or raw SHA256 binding differs")
    for name in (
        "shape_history_rebuilt",
        "cad_saved",
        "physical_enclosure_verified",
        "collision_clearance_accepted",
        "fabrication_release",
    ):
        if capture.get(name) is not False:
            raise ValueError("capture qualification/no-rebuild contract differs")
    for name in (
        "complete_identity_coverage",
        "source_copy_bytes_unchanged",
        "preexisting_documents_preserved",
        "all_enclosure_verified_flags_false",
    ):
        if capture.get(name) is not True:
            raise ValueError("capture completeness/preservation contract differs")
    for name in (
        "errors",
        "walker_errors",
        "missing_object_records",
        "missing_instance_ids",
        "unexpected_instance_ids",
    ):
        if capture.get(name) != []:
            raise ValueError("source capture contains errors or identity gaps")
    for name, expected in (
        ("observed_instance_count", 518),
        ("expected_instance_count", 518),
        ("captured_bounds_count", 518),
        ("bounds_gap_count", 0),
    ):
        if type(capture.get(name)) is not int or capture[name] != expected:
            raise ValueError("capture count contract differs")
    scope = capture.get("native_scope")
    if (
        not isinstance(scope, dict)
        or scope.get("saved_zero_only") is not True
        or any(
            scope.get(k) is not False
            for k in (
                "history_recompute_requested",
                "changed_recompute_requested",
                "forced_recompute_requested",
            )
        )
    ):
        raise ValueError("saved-zero/no-recompute contract differs")
    if capture.get("final_state_counts") != {"Up-to-date": 1147, "Touched": 1854}:
        raise ValueError("source cached object-state contract differs")
    fixture = capture.get("synthetic_coordinate_fixture")
    fixture_names = {
        "direct_child",
        "link_false",
        "link_true",
        "group_link_false",
        "group_link_true",
    }
    if (
        not isinstance(fixture, dict)
        or fixture.get("passed") is not True
        or len(fixture.get("cases", [])) != 5
        or {row.get("name") for row in fixture["cases"]} != fixture_names
    ):
        raise ValueError("five native coordinate fixture cases are required")
    tolerance = finite(fixture.get("tolerance_mm"))
    if not 0 < tolerance <= 2e-6 or any(
        not 0 <= finite(row.get("maximum_extremum_error_mm")) <= tolerance
        for row in fixture["cases"]
    ):
        raise ValueError("native coordinate fixtures exceed their numerical policy")
    model = capture.get("master_model_saved_placement", {})
    if rigid_transform(model.get("matrix")) != IDENTITY:
        raise ValueError("this study requires the captured identity master Model placement")
    leaves, rows = inventory.get("mounted_bodies"), capture.get("instances")
    if (
        not isinstance(leaves, list)
        or not isinstance(rows, list)
        or len(leaves) != 518
        or len(rows) != 518
        or inventory.get("instance_count") != 518
        or any(not isinstance(row, dict) for row in (*leaves, *rows))
    ):
        raise ValueError("both sources must contain exactly 518 instance records")
    if any(
        not isinstance(row.get(key), str) or not row[key].strip()
        for row in (*leaves, *rows)
        for key in ("instance_id", "object_reference", "root_subassembly")
    ):
        raise ValueError("instance source identifiers must be nonempty strings")
    known = {row.get("instance_id"): row for row in leaves}
    observed = {row.get("instance_id"): row for row in rows}
    if (
        len(known) != 518
        or len(observed) != 518
        or set(known) != set(observed)
        or any(not isinstance(key, str) or not key for key in known)
    ):
        raise ValueError("exact source instance identity coverage differs")
    for name, row in observed.items():
        if any(
            row.get(key) != known[name].get(key) for key in ("object_reference", "root_subassembly")
        ):
            raise ValueError("instance source object/root binding differs")
        if (
            row.get("status") != "captured_numerical_bounds"
            or row.get("enclosure_verified") is not False
            or row.get("raw_shape_placement_unchanged") is not True
        ):
            raise ValueError("instance numerical-only status/preservation differs")
        _bounds(row.get("world_optimal_bounds_m"))
        _bounds(row.get("world_default_bounds_m"))
    return capture, [observed[name] for name in sorted(observed)]


def interval_gaps(left: AABB, right: AABB) -> tuple[float, ...]:
    """Three exact-coordinate interval gaps in shared world XYZ, in metres."""
    return tuple(
        finite(max(right.minimum_m[i] - left.maximum_m[i], left.minimum_m[i] - right.maximum_m[i]))
        for i in range(3)
    )


def derive_pairs(rows: list[dict], *, policy=POLICY) -> dict:
    """Broad phase over every pair; SAT confirmation only on retained candidates."""
    if policy != POLICY or any(type(policy[key]) is not type(POLICY[key]) for key in POLICY):
        raise ValueError("unsupported numerical metric/pair/exclusion policy")
    tolerance = policy["numerical_tolerance_m"]
    optimal = [_bounds(row["world_optimal_bounds_m"]) for row in rows]
    default = [_bounds(row["world_default_bounds_m"]) for row in rows]
    proxies = [
        bounds.proxy(
            row["instance_id"],
            FRAME,
            "Pinned saved-zero numerical optimal bounds; source enclosure unknown",
        )
        for bounds, row in zip(optimal, rows, strict=True)
    ]
    counts = Counter(
        {
            key: 0
            for key in (
                "total_pairs",
                "optimal_overlap_or_contact",
                "default_overlap_or_contact",
                "both_metrics_candidate",
                "optimal_only_candidate",
                "default_only_candidate",
                "neither_metric_candidate",
                "sat_confirmation_disagreements",
            )
        }
    )
    candidates, default_only, separated_witnesses = [], [], []
    groups = Counter()
    for left, right in combinations(range(len(rows)), 2):
        gaps = interval_gaps(optimal[left], optimal[right])
        dgaps = interval_gaps(default[left], default[right])
        maximum, dmaximum = max(gaps), max(dgaps)
        selected, other = maximum <= tolerance, dmaximum <= tolerance
        counts["total_pairs"] += 1
        counts["optimal_overlap_or_contact"] += selected
        counts["default_overlap_or_contact"] += other
        counts["both_metrics_candidate"] += selected and other
        counts["optimal_only_candidate"] += selected and not other
        counts["default_only_candidate"] += other and not selected
        counts["neither_metric_candidate"] += not selected and not other
        record = {
            "left_index": left,
            "right_index": right,
            "optimal_axis_gaps_m": gaps,
            "default_axis_gaps_m": dgaps,
        }
        if selected:
            sat = intersect_boxes(proxies[left], proxies[right], numerical_tolerance_m=tolerance)
            counts["sat_confirmation_disagreements"] += sat.relation != "proxy_overlap_or_contact"
            record.update(
                optimal_contact_classification="within_numerical_tolerance"
                if maximum >= -tolerance
                else "interior_overlap",
                default_metric_candidate=other,
                sat_confirmation_relation=sat.relation,
                sat_maximum_axis_gap_m=sat.maximum_axis_gap_m,
            )
            candidates.append(record)
            groups[
                tuple(sorted((rows[left]["root_subassembly"], rows[right]["root_subassembly"])))
            ] += 1
        elif other:
            default_only.append(record)
        if not selected:
            separated_witnesses.append((maximum, record))
            separated_witnesses.sort(
                key=lambda pair: (pair[0], pair[1]["left_index"], pair[1]["right_index"])
            )
            del separated_witnesses[policy["separated_witness_limit"] :]
    return {
        "counts": dict(counts),
        "optimal_overlap_candidates": candidates,
        "default_only_candidates": default_only,
        "nearest_separated_numerical_witnesses": [row for _, row in separated_witnesses],
        "candidate_subassembly_pair_counts": [
            {"subassemblies": list(key), "candidate_count": count}
            for key, count in sorted(groups.items())
        ],
        "candidate_pair_exclusions": [],
        "intended_contact_audit_complete": False,
    }


def build_study(
    capture_raw: bytes,
    inventory_raw: bytes,
    *,
    expected_capture_sha256=PINNED_CAPTURE_SHA256,
    policy=POLICY,
) -> dict:
    capture, rows = validate_inputs(
        capture_raw, inventory_raw, expected_capture_sha256=expected_capture_sha256
    )
    pairs = derive_pairs(rows, policy=policy)
    differences = []
    registry = []
    for index, row in enumerate(rows):
        delta = tuple(
            tuple(finite(a - b) for a, b in zip(p, q, strict=True))
            for p, q in zip(
                row["world_default_bounds_m"], row["world_optimal_bounds_m"], strict=True
            )
        )
        differences.extend(abs(value) for point in delta for value in point)
        registry.append(
            {
                "index": index,
                "instance_id": row["instance_id"],
                "object_reference": row["object_reference"],
                "root_subassembly": row["root_subassembly"],
                "optimal_bounds_m": row["world_optimal_bounds_m"],
                "default_bounds_m": row["world_default_bounds_m"],
                "default_minus_optimal_extrema_m": delta,
                "enclosure_status": "unknown",
            }
        )
    implementation = ROOT / "src/raftel_arm01/kinematics/thor_collision.py"
    return {
        "schema_version": 1,
        "evidence_class": (
            "saved_zero_mounted_numerical_AABB_pairs_not_physical_collision_screening"
        ),
        "source_revision": SOURCE_REVISION,
        "input_bindings": {
            "mounted_bounds": {"path": CAPTURE_PATH, "raw_sha256": _sha(capture_raw)},
            "mounted_inventory": {"path": INVENTORY_PATH, "raw_sha256": _sha(inventory_raw)},
            "box_math_implementation": {
                "path": "src/raftel_arm01/kinematics/thor_collision.py",
                "raw_sha256": _sha(implementation.read_bytes()),
            },
        },
        "policy": copy.deepcopy(policy),
        "policy_canonical_sha256": canonical_sha256(policy),
        "coordinate_contract": {
            "frame": FRAME,
            "units": "m",
            "native_mm_to_m_conversion": (
                "already performed once by captured worker; "
                "no further scaling or placements applied"
            ),
        },
        "native_scope": {
            "source_capture_raw_evidence": capture["raw_evidence"],
            "shape_history_rebuilt": False,
            "saved_zero_only": True,
            "final_state_counts": capture["final_state_counts"],
            "source_copy_bytes_unchanged": True,
            "original_source_count": capture["original_source_count"],
            "addon_source_count": capture["addon_source_count"],
        },
        "proxy_coverage": {
            "installed_identities": len(registry),
            "numerical_AABB_proxies": len(registry),
            "verified_geometry_enclosures": 0,
            "nonzero_pose_bindings": 0,
            "obstacle_or_held_object_models": 0,
            "full_physical_scene_coverage": False,
        },
        "bounds_comparison": {
            "maximum_absolute_default_vs_optimal_extremum_difference_m": max(differences),
            "metric_choice_establishes_enclosure_or_clearance": False,
        },
        "proxy_registry": registry,
        "pair_diagnostics": pairs,
        "interpretation": {
            "overlap_candidate": (
                "numerical boxes overlap/contact; physical collision and intended contact unknown"
            ),
            "omitted_pair": "no selected numerical proxy overlap at saved zero; not physical clear",
            "default_only_candidate": (
                "default numerical boxes overlap/contact while selected optimal numerical "
                "boxes separate; no metric is accepted as physical enclosure proof"
            ),
            "gap": "signed interval projection gap only; not exact geometric or physical clearance",
        },
        "physical_collision_free": None,
        "swept_path_clearance": None,
        "qualification": {
            key: False
            for key in (
                "source_or_physical_enclosure_verified",
                "intended_contacts_resolved",
                "nonzero_rigid_articulation_verified",
                "physical_collision_clearance",
                "hardware_motion_authorized",
                "manufacturing_release",
            )
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, default=ROOT / CAPTURE_PATH)
    parser.add_argument("--inventory", type=Path, default=ROOT / INVENTORY_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("output must be new; existing evidence is preserved")
        raw = []
        for path in (args.capture, args.inventory):
            with path.open("rb") as handle:
                contents = handle.read(20 * 1024 * 1024 + 1)
            if len(contents) > 20 * 1024 * 1024:
                raise ValueError("input exceeds bounded capture size")
            raw.append(contents)
        result = build_study(*raw)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print("Saved-zero numerical AABB pairs:", result["pair_diagnostics"]["counts"])
        return 0
    except (ValueError, OSError, TypeError, KeyError, OverflowError) as error:
        print(f"Mounted numerical proxy study failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
