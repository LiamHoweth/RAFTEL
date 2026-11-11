"""Host-only audit of separately captured selected cached-BRep draft STLs.

The native worker and its primitive fixtures are input evidence. This tool runs
ordinary Python only, verifies input/export bindings, and evaluates STL topology
and numeric diagnostics independently of FreeCAD. It does not repair meshes,
solve installed frames, establish surface equivalence or qualify fabrication.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

import thor_slicer_plan as stl

from raftel_arm01.engineering.scenarios import _strict_json, canonical_sha256, finite_number

ROOT = Path(__file__).resolve().parents[1]
FRAME = "saved_BRep_storage_frame_as_read_mm; no extra XML/object/link placement applied"
CAPTURE_CLASS = (
    "native_selected_cached_BRep_geometric_properties_not_history_or_physical_validation"
)
HOST_CLASS = (
    "host_STL_audit_of_selected_native_cached_exports_not_surface_or_physical_qualification"
)
NATIVE_PLAN_CLASS = "selected_cached_native_mesh_audit_and_unreleased_draft_queue"


def _sha(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _digest(value) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError("native evidence binding needs a lowercase SHA256")
    return value


def validate_capture(report: dict, launch: dict, request: dict, request_sha256: str) -> dict:
    """Join the supplied run/launcher/request pins without authenticating a run."""
    _digest(request_sha256)
    _digest(report.get("capture_script_sha256"))
    _digest(launch.get("worker_snapshot_sha256"))
    if (
        type(report.get("schema_version")) is not int
        or report.get("schema_version") != 1
        or report.get("evidence_class") != CAPTURE_CLASS
        or report.get("audit_status") != "complete_selected_cached_geometry_only"
        or report.get("source_revision") != stl.SOURCE_REVISION
    ):
        raise ValueError("native capture is not the complete declared cached-shape scope")
    if (
        request.get("source_revision") != stl.SOURCE_REVISION
        or request.get("evidence_class") != "selected_saved_BRep_properties_request"
        or type(request.get("schema_version")) is not int
        or request["schema_version"] != 1
    ):
        raise ValueError("native request source/schema mismatch")
    if (
        report.get("request_sha256") != request_sha256
        or launch.get("request_snapshot_sha256") != request_sha256
        or canonical_sha256(report.get("request")) != canonical_sha256(request)
    ):
        raise ValueError("native/request snapshot binding is stale")
    if (
        launch.get("outcome") != "process_completed"
        or type(launch.get("returncode")) is not int
        or launch["returncode"] != 0
        or launch.get("audit_status") != report["audit_status"]
        or launch.get("errors") != []
        or report.get("errors") != []
    ):
        raise ValueError("native launcher/capture did not report completed execution")
    for field in (
        "native_process_launched",
        "original_source_bytes_unchanged",
        "worker_snapshot_unchanged",
        "request_snapshot_unchanged",
        "report_exists",
    ):
        if launch.get(field) is not True:
            raise ValueError(f"native launcher flag not established: {field}")
    for field in ("input_copy_bytes_unchanged", "runtime_isolated_paths_verified"):
        if report.get(field) is not True:
            raise ValueError(f"native capture flag not established: {field}")
    for field in (
        "document_opened_or_recomputed",
        "native_document_saved",
        "cross_asset_aggregation_performed",
    ):
        if report.get(field) is not False:
            raise ValueError("cached-only scope was not preserved")
    if (
        report.get("coordinate_frame") != FRAME
        or report.get("open_document_count_before") != 0
        or report.get("open_document_count_after") != 0
        or type(report.get("open_document_count_before")) is not int
        or type(report.get("open_document_count_after")) is not int
    ):
        raise ValueError("native frame/open-document contract differs")
    if report.get("capture_script_sha256") != launch.get("worker_snapshot_sha256"):
        raise ValueError("native worker snapshot binding differs")
    summary = report.get("primitive_fixtures", {}).get("summary", {})
    if (
        summary.get("verified") is not True
        or summary.get("case_count") != 9
        or type(summary.get("case_count")) is not int
    ):
        raise ValueError("nine native primitive/unit/frame fixtures are required")
    for field, maximum in (
        ("maximum_relative_volume_error", 1e-9),
        ("maximum_com_error_mm", 1e-8),
        ("maximum_relative_tensor_error", 1e-8),
    ):
        value = finite_number(summary[field])
        if not 0 <= value <= maximum:
            raise ValueError("native primitive fixture error exceeds declared numeric contract")
    selections = request.get("selections")
    if not isinstance(selections, list) or not 1 <= len(selections) <= 8:
        raise ValueError("request needs1..8 selected shapes")
    by_id = {row["selection_id"]: row for row in selections}
    source_pins = {}
    for selection in selections:
        path = stl._safe_source_path(selection["source_file"])
        entry = stl._safe_source_path(selection["brep_entry"])
        _digest(selection["source_sha256"])
        _digest(selection["brep_sha256"])
        if not path.startswith("freecad-src/") or not entry.lower().endswith(".brp"):
            raise ValueError("selected source/Shape entry identity is invalid")
        if path in source_pins and source_pins[path] != selection["source_sha256"]:
            raise ValueError("one source archive has conflicting pins")
        source_pins[path] = selection["source_sha256"]
    captures = report.get("selections")
    if (
        len(by_id) != len(selections)
        or not isinstance(captures, list)
        or len(captures) != len(selections)
        or {row["selection_id"] for row in captures} != set(by_id)
        or len({row["selection_id"] for row in captures}) != len(captures)
    ):
        raise ValueError("native selected identities are missing, extra or duplicated")
    if type(launch.get("selected_captures")) is not int or launch["selected_captures"] != len(
        captures
    ):
        raise ValueError("launcher selected count differs")
    expected = {row["source_file"]: row["source_sha256"] for row in selections}
    if (
        report.get("source_copy_sha256_before") != expected
        or report.get("source_copy_sha256_after") != expected
        or launch.get("original_source_sha256_after") != expected
    ):
        raise ValueError("native source-copy/original archive pins differ")
    return by_id


def _identity(row: dict) -> tuple[str, str, str]:
    source = row["source_binding"]
    reference = PurePosixPath(source["source_file"]).stem + "::" + source["object_name"]
    if source["object_type"] == "Part::Mirroring":
        if reference != "AssemblyArt56::Unnamed1_GripperFinger_mirrored":
            raise ValueError("unreconciled mirrored source identity")
        return reference, "GripperFinger::Body", "reflected"
    return reference, reference, "nominal"


def audit_exports(
    report: dict,
    launch: dict,
    request: dict,
    mesh_root: Path,
    upstream_plan: dict,
    *,
    request_sha256: str,
    native_capture_sha256: str,
    launch_sha256: str,
) -> dict:
    by_id = validate_capture(report, launch, request, request_sha256)
    _digest(native_capture_sha256)
    _digest(launch_sha256)
    if (
        upstream_plan.get("source_revision") != stl.SOURCE_REVISION
        or upstream_plan.get("evidence_class")
        != "pinned_upstream_STL_audit_and_unreleased_draft_queue"
    ):
        raise ValueError("preserved upstream mesh plan is required")
    parent_hash = canonical_sha256(upstream_plan)
    if any(
        selection.get("reference_capture", {})
        .get("input_canonical_sha256", {})
        .get("upstream_slicer_plan")
        != parent_hash
        for selection in by_id.values()
    ):
        raise ValueError("native request does not bind this preserved upstream plan")
    parent_groups = {
        (row["asset_id"], row["geometry_variant"]): row
        for row in upstream_plan["draft_plate_groups"]
    }
    upstream_meshes = {
        row["installed_asset_id"]: row
        for row in upstream_plan["mesh_audit"]
        if row.get("installed_asset_id") is not None
    }
    selections = []
    point_counts = {}
    resolved_root = mesh_root.resolve()
    for row in report["selections"]:
        selection = by_id[row["selection_id"]]
        expected = {
            key: selection[key]
            for key in (
                "source_file",
                "source_sha256",
                "object_name",
                "object_type",
                "brep_entry",
                "brep_sha256",
            )
        }
        expected["xml_placement_not_applied"] = selection["xml_placement"]
        if row.get("source_binding") != expected or row.get("coordinate_frame") != FRAME:
            raise ValueError("native selected source/frame binding differs from request")
        export = row.get("draft_stl")
        settings = selection["tessellation"]
        if (
            not isinstance(export, dict)
            or not isinstance(settings, dict)
            or export.get("units") != "mm"
            or export.get("frame") != FRAME
            or export.get("encoding") != "binary_STL"
            or export.get("tessellation") != settings
        ):
            raise ValueError("native STL units/frame/tessellation metadata mismatch")
        filename = stl._safe_source_path(export["filename"])
        if PurePosixPath(filename).name != filename or filename != settings["filename"]:
            raise ValueError("native export needs a safe request-bound basename")
        path = (mesh_root / filename).resolve()
        if not path.is_relative_to(resolved_root):
            raise ValueError("native STL path escapes export root")
        contents = stl._bounded_read(path)
        if (
            _sha(contents) != export["sha256"]
            or type(export.get("bytes")) is not int
            or len(contents) != export["bytes"]
        ):
            raise ValueError("native STL bytes/hash mismatch")
        mesh = stl.analyze_stl(contents)
        if (
            mesh["encoding"] != "binary"
            or type(export.get("triangle_count")) is not int
            or mesh["triangle_count"] != export["triangle_count"]
        ):
            raise ValueError("native STL facet count/encoding differs")
        metrics = row["cached_shape_properties"]
        if metrics.get("native_shape_valid") is not True:
            raise ValueError("native shape validity not established")
        volume = finite_number(metrics["aggregate"]["volume_mm3"])
        if volume <= 0:
            raise ValueError("native source volume must be positive")
        bounds = metrics["native_bounds_mm"]
        low = tuple(finite_number(bounds[axis + "Min"]) for axis in "XYZ")
        high = tuple(finite_number(bounds[axis + "Max"]) for axis in "XYZ")
        if any(a >= b for a, b in zip(low, high, strict=True)):
            raise ValueError("native source bounds are degenerate or inverted")
        tolerance = max(1e-5, 2e-7 * max(abs(value) for value in (*low, *high)))
        mesh_low = mesh["bounds_interpreted_mm"]["min"]
        mesh_high = mesh["bounds_interpreted_mm"]["max"]
        contained = all(
            mesh_low[i] >= low[i] - tolerance and mesh_high[i] <= high[i] + tolerance
            for i in range(3)
        )
        ratio = finite_number(mesh["absolute_signed_volume_interpreted_mm3"] / volume)
        com = metrics["aggregate"]["com_mm"]
        placement = metrics["raw_shape_placement_matrix_not_reapplied"]
        if (
            not isinstance(com, list)
            or len(com) != 3
            or not isinstance(placement, list)
            or len(placement) != 16
        ):
            raise ValueError("native COM/placement dimensions invalid")
        com = [finite_number(value) for value in com]
        placement = [finite_number(value) for value in placement]
        scale_consistent = 0.9 <= ratio <= 1.1
        reference, asset, variant = _identity(row)
        parent = parent_groups.get((asset, variant))
        if parent is None:
            raise ValueError("native selection lacks its installed asset/variant quantity")
        topology = mesh["topology"]["closed_consistently_oriented_two_manifold"]
        positive = mesh["algebraic_signed_volume_interpreted_mm3"] > 0
        reasons = []
        if not topology:
            reasons.append("exact_vertex_topology_or_winding_failure")
        if not positive:
            reasons.append("nonpositive_winding_integral")
        if not contained:
            reasons.append("mesh_bounds_outside_native_bounds_at_float32_tolerance")
        if not scale_consistent:
            reasons.append("gross_unit_or_scale_sanity_failure")
        source = upstream_meshes.get(asset) if variant == "nominal" else None
        comparison = (
            None
            if source is None
            else {
                "upstream_source_path": source["source_path"],
                "upstream_sha256": source["sha256"],
                "upstream_topology": source["mesh"]["topology"],
                "upstream_triangle_count": source["mesh"]["triangle_count"],
                "native_export_triangle_count": mesh["triangle_count"],
                "extent_delta_from_upstream_xyz_mm": [
                    a - b
                    for a, b in zip(
                        mesh["envelope_xyz_interpreted_mm"],
                        source["mesh"]["envelope_xyz_interpreted_mm"],
                        strict=True,
                    )
                ],
                "signed_volume_proxy_delta_from_upstream_mm3": mesh[
                    "algebraic_signed_volume_interpreted_mm3"
                ]
                - source["mesh"]["algebraic_signed_volume_interpreted_mm3"],
                "geometry_equivalence_or_common_native_to_STL_transform_established": False,
            }
        )
        selections.append(
            {
                "selection_id": row["selection_id"],
                "source_reference": reference,
                "installed_asset_id": asset,
                "geometry_variant": variant,
                "installed_quantity": parent["repeat_plate_count"],
                "source_binding": row["source_binding"],
                "coordinate_frame": FRAME,
                "native_export": export,
                "mesh": mesh,
                "native_comparison": {
                    "native_bounds_mm": bounds,
                    "native_volume_mm3": volume,
                    "native_raw_com_mm": com,
                    "native_raw_shape_placement_matrix_not_reapplied": placement,
                    "mesh_bound_delta_min_mm": [a - b for a, b in zip(mesh_low, low, strict=True)],
                    "mesh_bound_delta_max_mm": [
                        a - b for a, b in zip(mesh_high, high, strict=True)
                    ],
                    "inside_native_bounds_at_float32_serialization_tolerance": contained,
                    "float32_bound_comparison_tolerance_mm": tolerance,
                    "relative_winding_volume_proxy_delta": ratio - 1,
                    "coarse_unit_scale_sanity_band": [0.9, 1.1],
                    "scale_screen_is_not_surface_or_manufacturing_tolerance": True,
                    "bidirectional_surface_distance_mm": None,
                    "native_mesh_surface_equivalence_established": False,
                },
                "upstream_comparison": comparison,
                "draft_candidate": not reasons,
                "blockers": reasons,
                "installed_frame_correspondence": None,
                "qualification": {
                    "self_intersections_checked": False,
                    "surface_fidelity_qualified": False,
                    "printed_strength_or_fit": False,
                    "manufacturing_release": False,
                },
            }
        )
        _, facets, _ = stl.parse_stl(contents)
        point_counts[row["selection_id"]] = Counter(
            point for _, triangle in facets for point in triangle
        )
    mirror = None
    if {"gripper-finger-nominal", "gripper-finger-reflected"} <= set(point_counts):
        reflected = Counter(
            {
                (-x, y, z): count
                for (x, y, z), count in point_counts["gripper-finger-nominal"].items()
            }
        )
        mirror = {
            "test": "exact_unindexed_float32_vertex_multiset_X_reflection",
            "matches": reflected == point_counts["gripper-finger-reflected"],
            "native_saved_variant_not_new_reflection_operation": True,
            "installed_link_transform_established": False,
            "surface_equivalence_from_point_cloud_alone": False,
        }
    return {
        "schema_version": 1,
        "evidence_class": HOST_CLASS,
        "source_revision": stl.SOURCE_REVISION,
        "audit_mode": "ordinary_Python_host_only_no_native_process_or_mesh_repair",
        "input_bindings": {
            "native_capture_raw_sha256": native_capture_sha256,
            "launcher_raw_sha256": launch_sha256,
            "request_raw_sha256": request_sha256,
            "upstream_plan_canonical_sha256": canonical_sha256(upstream_plan),
        },
        "native_run_context": {
            "capture_script_sha256": report["capture_script_sha256"],
            "runner_declared_executable_sha256": report.get("runner_declared_executable_sha256"),
            "full_runtime_bundle_verified_by_worker": report.get(
                "full_runtime_bundle_verified_by_worker"
            ),
            "freecad_version": report["freecad_version"],
            "opencascade_version": report.get("opencascade_version"),
            "fixture_summary": report["primitive_fixtures"]["summary"],
            "originals_and_copies_unchanged": True,
            "document_opened_recomputed_or_saved": False,
            "source_execution_authentication_boundary": report.get(
                "source_authentication_boundary"
            ),
        },
        "counts": {
            "selected_exports": len(selections),
            "candidate_geometry_variants": sum(row["draft_candidate"] for row in selections),
            "blocked_geometry_variants": sum(not row["draft_candidate"] for row in selections),
            "candidate_installed_instances": sum(
                row["installed_quantity"] for row in selections if row["draft_candidate"]
            ),
            "blocked_installed_instances": sum(
                row["installed_quantity"] for row in selections if not row["draft_candidate"]
            ),
        },
        "selections": selections,
        "finger_vertex_reflection_check": mirror,
        "qualification": {
            "whole_assembly_or_history_rebuilt": False,
            "native_to_installed_frames_complete": False,
            "mesh_self_intersections_checked": False,
            "bidirectional_surface_fidelity_checked": False,
            "slicer_import_verified": False,
            "physical_fit_strength_or_print_qualified": False,
            "manufacturing_release": False,
        },
    }


def native_draft_plan(audit: dict, upstream_plan: dict) -> dict:
    """Separate native-cached queue; it never mutates the upstream source plan."""
    if audit.get("evidence_class") != HOST_CLASS or audit["input_bindings"][
        "upstream_plan_canonical_sha256"
    ] != canonical_sha256(upstream_plan):
        raise ValueError("native audit does not bind this preserved upstream plan")
    groups = []
    meshes = []
    parent_groups = {
        (row["asset_id"], row["geometry_variant"]): row
        for row in upstream_plan["draft_plate_groups"]
    }
    for row in audit["selections"]:
        if not row["draft_candidate"]:
            continue
        if (
            row["geometry_variant"] == "reflected"
            and (audit.get("finger_vertex_reflection_check") or {}).get("matches") is not True
        ):
            continue
        parent = parent_groups[(row["installed_asset_id"], row["geometry_variant"])]
        binding = {
            "native_capture_raw_sha256": audit["input_bindings"]["native_capture_raw_sha256"],
            "native_launcher_raw_sha256": audit["input_bindings"]["launcher_raw_sha256"],
            "request_raw_sha256": audit["input_bindings"]["request_raw_sha256"],
            "native_mesh_audit_canonical_sha256": canonical_sha256(audit),
            "selection_id": row["selection_id"],
            "source_binding": row["source_binding"],
            "coordinate_frame": row["coordinate_frame"],
            "tessellation": row["native_export"]["tessellation"],
            "native_to_installed_transform": None,
            "surface_equivalence_qualified": False,
        }
        meshes.append(
            {
                "source_path": row["native_export"]["filename"],
                "source_url": f"{stl.SOURCE_REPOSITORY}/blob/{stl.SOURCE_REVISION}/"
                f"{row['source_binding']['source_file']}",
                "git_blob_sha1": None,
                "sha256": row["native_export"]["sha256"],
                "installed_asset_id": row["installed_asset_id"],
                "geometry_variant": row["geometry_variant"],
                "mesh": copy.deepcopy(row["mesh"]),
                "mesh_origin": "selected_saved_BRep_native_tessellation",
                "native_export_binding": binding,
            }
        )
        group = copy.deepcopy(parent)
        group.update(
            plate_group_id="native-cached-" + row["selection_id"],
            stage="native_cached_mesh_audited_waiting_orientation_and_surface_review",
            source_mesh_path=row["native_export"]["filename"],
            source_mesh_sha256=row["native_export"]["sha256"],
            mesh_kind="selected_saved_BRep_native_tessellation_not_pinned_upstream_STL",
            draft_placement_proposal=stl.centered_draft_placement(
                row["mesh"], upstream_plan["installed_profile"]
            ),
            unresolved_gates=[
                "native_to_installed_frame_not_recovered",
                "self_intersection_and_surface_distance_unverified",
                "orientation_support_fit_and_strength_unqualified",
            ],
        )
        groups.append(group)
    license_row = next(
        row for row in upstream_plan["mesh_audit"] if row["source_path"] == "LICENSE"
    )
    meshes.append(copy.deepcopy(license_row))
    return {
        "schema_version": 1,
        "evidence_class": NATIVE_PLAN_CLASS,
        "source_revision": stl.SOURCE_REVISION,
        "mesh_origin": "selected_saved_BRep_native_tessellation",
        "parent_upstream_plan_canonical_sha256": canonical_sha256(upstream_plan),
        "native_mesh_audit_canonical_sha256": canonical_sha256(audit),
        "input_canonical_sha256": copy.deepcopy(upstream_plan["input_canonical_sha256"]),
        "installed_profile": copy.deepcopy(upstream_plan["installed_profile"]),
        "draft_plate_groups": groups,
        "mesh_audit": meshes,
        "attribution": copy.deepcopy(upstream_plan["attribution"]),
        "qualification": copy.deepcopy(audit["qualification"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--mesh-root", type=Path, required=True)
    parser.add_argument(
        "--request",
        type=Path,
        default=ROOT / "hardware/print-planning/thor-native-export-inputs-v1.json",
    )
    parser.add_argument(
        "--upstream-plan",
        type=Path,
        default=ROOT / "hardware/print-planning/thor-draft-plan-v1.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--draft-plan", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = (args.capture, args.launcher, args.request, args.upstream_plan)
        raw = [stl._bounded_read(path) for path in paths]
        capture, launcher, request, parent = map(_strict_json, raw)
        if args.output.exists() or (
            args.draft_plan is not None
            and (args.draft_plan.exists() or args.draft_plan.resolve() == args.output.resolve())
        ):
            raise ValueError("output evidence paths must be new and distinct")
        audit = audit_exports(
            capture,
            launcher,
            request,
            args.mesh_root,
            parent,
            request_sha256=_sha(raw[2]),
            native_capture_sha256=_sha(raw[0]),
            launch_sha256=_sha(raw[1]),
        )
        queue = None if args.draft_plan is None else native_draft_plan(audit, parent)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(audit, indent=2, allow_nan=False) + "\n")
        if queue is not None:
            with args.draft_plan.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(queue, indent=2, allow_nan=False) + "\n")
        print("Audited selected native cached STLs on ordinary host:", audit["counts"])
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        print(f"Native mesh host audit failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
