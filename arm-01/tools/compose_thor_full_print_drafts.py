"""Compose full-registry generic 3MF drafts through the unchanged native composer.

The new queue retains each actual batch's raw capture/runner/request hashes.
It does not relabel the full host audit as the older selected-eight audit or
weaken the existing Art1/source/geometry checks. No slicer/device is invoked.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import audit_thor_full_print_meshes as full
import thor_draft_3mf as composer

from raftel_arm01.engineering.evidence_files import write_new_evidence
from raftel_arm01.engineering.scenarios import _strict_json, canonical_sha256

ROOT = full.ROOT
AUDIT_PATH = ROOT / "hardware/print-planning/thor-full-print-mesh-audit-v1.json"
PARENT_PATH = ROOT / "hardware/print-planning/thor-draft-plan-v1.json"


def full_native_draft_plan(audit: dict, parent: dict, joined: dict) -> dict:
    """Build a genuine native-cache queue with per-selection actual batch pins."""
    full._require(
        type(audit.get("schema_version")) is int
        and audit["schema_version"] == 1
        and audit.get("evidence_class") == full.HOST_CLASS
        and audit.get("source_revision") == full.stl.SOURCE_REVISION
        and audit.get("native_aggregate_canonical_sha256") == canonical_sha256(joined["aggregate"])
        and audit.get("full_request_raw_sha256") == joined["request_raw_sha256"],
        "full mesh audit source/aggregate/request binding differs",
    )
    full._require(
        type(parent.get("schema_version")) is int
        and parent["schema_version"] == 1
        and parent.get("evidence_class") == "pinned_upstream_STL_audit_and_unreleased_draft_queue"
        and parent.get("source_revision") == full.stl.SOURCE_REVISION,
        "preserved upstream quantity/profile plan required",
    )
    reference = next(iter(joined["by_id"].values()))["reference_capture"]
    full._require(
        parent["input_canonical_sha256"]["printable_asset_manifest"]
        == reference["input_canonical_sha256"]["printable_asset_manifest"],
        "upstream profile/quantity plan binds a different printable manifest",
    )
    full._false_contract(
        audit["qualification"],
        (
            "whole_assembly_or_history_rebuilt",
            "native_to_installed_frames_complete",
            "mesh_self_intersections_checked",
            "bidirectional_surface_fidelity_checked",
            "slicer_import_verified",
            "physical_fit_strength_or_print_qualified",
            "manufacturing_release",
        ),
    )
    rows = {row["selection_id"]: row for row in audit["selections"]}
    full._require(
        len(rows) == len(audit["selections"]) == 47 and set(rows) == set(joined["by_id"]),
        "full host audit selection coverage differs",
    )
    parents = {
        (row["asset_id"], row["geometry_variant"]): row for row in parent["draft_plate_groups"]
    }
    full._require(
        len(parents) == len(parent["draft_plate_groups"]) == 47,
        "upstream plan variant identities duplicate or omit",
    )
    groups, meshes, blocked = [], [], []
    audit_hash = canonical_sha256(audit)
    for identifier, selection in joined["by_id"].items():
        row = rows[identifier]
        native, variant = joined["captured"][identifier], joined["variants"][identifier]
        context, batch = selection["reference_capture"], joined["contexts"][identifier]["batch"]
        full._false_contract(
            row["qualification"],
            (
                "self_intersections_checked",
                "surface_fidelity_qualified",
                "printed_strength_or_fit",
                "manufacturing_release",
            ),
        )
        expected_bindings = {
            key: batch[key]
            for key in (
                "raw_capture_sha256",
                "raw_runner_sha256",
                "request_sha256",
                "worker_sha256",
                "launcher_snapshot_sha256",
            )
        }
        identity = context["asset_id"], context["geometry_variant"]
        full._require(
            row["installed_asset_id"] == identity[0]
            and row["geometry_variant"] == identity[1]
            and row["source_binding"] == native["source_binding"]
            and row["native_export"] == variant["draft_stl"]
            and row["actual_batch_bindings"] == expected_bindings
            and row["batch_index"] == batch["batch_index"]
            and row["installed_instance_ids"] == variant["installed_instance_ids"]
            and type(row["installed_quantity"]) is int
            and row["installed_quantity"] == context["quantity_required"]
            and row["coordinate_frame"] == full.selected_audit.FRAME,
            "full queue row source/frame/quantity/actual batch pins differ",
        )
        parent_group = parents.get(identity)
        full._require(
            parent_group is not None
            and parent_group["repeat_plate_count"] == context["quantity_required"]
            and type(parent_group["repeat_plate_count"]) is int,
            "upstream group quantity differs from installed full registry",
        )
        reasons = list(row["blockers"])
        full._require(
            type(row["draft_candidate"]) is bool and row["draft_candidate"] == (not reasons),
            "host mesh candidate/blocker fields contradict",
        )
        if identity[0] == "Art1Body::Body":
            reasons.append("existing_composer_Art1_history_exact_solid_gate_remains_unaccepted")
        if (
            identity[1] == "reflected"
            and audit["finger_vertex_reflection_check"]["matches"] is not True
        ):
            reasons.append("saved_finger_reflection_correspondence_unverified")
        if reasons:
            blocked.append(
                {
                    "selection_id": identifier,
                    "asset_id": identity[0],
                    "geometry_variant": identity[1],
                    "quantity": context["quantity_required"],
                    "blockers": reasons,
                }
            )
            continue
        binding = {
            "native_capture_raw_sha256": batch["raw_capture_sha256"],
            "native_launcher_raw_sha256": batch["raw_runner_sha256"],
            "request_raw_sha256": batch["request_sha256"],
            "native_mesh_audit_canonical_sha256": audit_hash,
            "selection_id": identifier,
            "actual_batch_index": batch["batch_index"],
            "actual_launcher_contract": "full-print batch runner result; preserved raw schema",
            "full_native_aggregate_canonical_sha256": canonical_sha256(joined["aggregate"]),
            "source_binding": copy.deepcopy(row["source_binding"]),
            "coordinate_frame": row["coordinate_frame"],
            "tessellation": copy.deepcopy(row["native_export"]["tessellation"]),
            "native_to_installed_transform": None,
            "surface_equivalence_qualified": False,
        }
        meshes.append(
            {
                "source_path": row["native_export"]["filename"],
                "source_url": f"{full.stl.SOURCE_REPOSITORY}/blob/{full.stl.SOURCE_REVISION}/"
                f"{row['source_binding']['source_file']}",
                "git_blob_sha1": None,
                "sha256": row["native_export"]["sha256"],
                "installed_asset_id": identity[0],
                "geometry_variant": identity[1],
                "mesh": copy.deepcopy(row["mesh"]),
                "mesh_origin": composer.NATIVE_MESH_ORIGIN,
                "native_export_binding": binding,
            }
        )
        group = copy.deepcopy(parent_group)
        group.update(
            plate_group_id="full-native-cached-" + identifier,
            stage="native_cached_mesh_audited_waiting_orientation_and_surface_review",
            source_mesh_path=row["native_export"]["filename"],
            source_mesh_sha256=row["native_export"]["sha256"],
            mesh_kind="selected_saved_BRep_native_tessellation_not_pinned_upstream_STL",
            draft_placement_proposal=full.stl.centered_draft_placement(
                row["mesh"], parent["installed_profile"]
            ),
            unresolved_gates=[
                "native_to_installed_frame_not_recovered",
                "self_intersection_and_surface_distance_unverified",
                "orientation_support_fit_and_strength_unqualified",
            ],
        )
        groups.append(group)
    counts = audit["counts"]
    full._require(
        all(type(value) is int for value in counts.values())
        and counts
        == {
            "audited_geometry_variants": 47,
            "represented_installed_instances": 65,
            "candidate_geometry_variants": sum(row["draft_candidate"] for row in rows.values()),
            "blocked_geometry_variants": sum(not row["draft_candidate"] for row in rows.values()),
            "candidate_installed_instances": sum(
                row["installed_quantity"] for row in rows.values() if row["draft_candidate"]
            ),
            "blocked_installed_instances": sum(
                row["installed_quantity"] for row in rows.values() if not row["draft_candidate"]
            ),
            "total_triangles": sum(row["native_export"]["triangle_count"] for row in rows.values()),
        },
        "full host audit counts contradict its bound selections",
    )
    license_rows = [row for row in parent["mesh_audit"] if row["source_path"] == "LICENSE"]
    full._require(len(license_rows) == 1, "preserved upstream license binding missing/ambiguous")
    meshes.append(copy.deepcopy(license_rows[0]))
    plan = {
        "schema_version": 1,
        "evidence_class": composer.NATIVE_PLAN_CLASS,
        "source_revision": full.stl.SOURCE_REVISION,
        "mesh_origin": composer.NATIVE_MESH_ORIGIN,
        "registry_scope": "full47 registry; per-selection actual batch pins; "
        "historical plans unchanged",
        "parent_upstream_plan_canonical_sha256": canonical_sha256(parent),
        "native_mesh_audit_canonical_sha256": audit_hash,
        "input_canonical_sha256": copy.deepcopy(parent["input_canonical_sha256"]),
        "installed_profile": copy.deepcopy(parent["installed_profile"]),
        "draft_plate_groups": groups,
        "mesh_audit": meshes,
        "blocked_groups": blocked,
        "counts": {
            "full_registry_variants": 47,
            "full_registry_installed_instances": 65,
            "host_mesh_candidates": sum(row["draft_candidate"] for row in rows.values()),
            "composer_candidate_variants": len(groups),
            "composer_candidate_instances": sum(row["repeat_plate_count"] for row in groups),
            "composer_blocked_variants": len(blocked),
            "composer_blocked_instances": sum(row["quantity"] for row in blocked),
        },
        "attribution": copy.deepcopy(parent["attribution"]),
        "qualification": copy.deepcopy(audit["qualification"]),
    }
    # Validate the complete in-memory queue before a caller can create any
    # directory or publish a queue-only success. Reuse the unchanged composer
    # gate rather than maintaining a weaker parallel topology/source policy.
    for group in groups:
        composer._draft_inputs(
            plan, group["asset_id"], group["repeat_plate_count"], group["geometry_variant"]
        )
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="new separate draft directory"
    )
    parser.add_argument(
        "--license-file", type=Path, default=ROOT.parent / ".work/print-planning/upstream/LICENSE"
    )
    parser.add_argument(
        "--queue-only", action="store_true", help="write plan without reading local mesh payloads"
    )
    parser.add_argument(
        "--max-projects", type=int, help="optional bounded preview subset; receipt remains partial"
    )
    args = parser.parse_args(argv)
    try:
        destination = args.output_dir.resolve()
        full._require(
            not destination.exists() and not args.output_dir.is_symlink(),
            "draft output directory must be new",
        )
        joined, _, _, _ = full.load_evidence()
        audit = _strict_json(full.stl._bounded_read(AUDIT_PATH))
        parent = _strict_json(full.stl._bounded_read(PARENT_PATH))
        plan = full_native_draft_plan(audit, parent, joined)
        if args.max_projects is not None:
            full._require(
                1 <= args.max_projects <= plan["counts"]["composer_candidate_instances"],
                "max-projects outside queue bounds",
            )
        license_bytes = None if args.queue_only else full.stl._bounded_read(args.license_file)
        if license_bytes is not None:
            license_row = next(row for row in plan["mesh_audit"] if row["source_path"] == "LICENSE")
            full._require(
                full.sha(license_bytes) == license_row["sha256"],
                "license bytes differ from preserved source pin",
            )
        destination.mkdir(parents=True, exist_ok=False)
        write_new_evidence(
            [(destination / "draft-queue.json", json.dumps(plan, indent=2, allow_nan=False) + "\n")]
        )
        receipts = []
        if not args.queue_only:
            by_identity = {
                (row["installed_asset_id"], row["geometry_variant"]): row
                for row in audit["selections"]
            }
            for group in plan["draft_plate_groups"]:
                row = by_identity[(group["asset_id"], group["geometry_variant"])]
                contents = full.stl._bounded_read(
                    full._relative(ROOT.parent, row["native_export"]["local_path"])
                )
                for index in range(1, group["repeat_plate_count"] + 1):
                    if args.max_projects is not None and len(receipts) >= args.max_projects:
                        break
                    payload, receipt = composer.build_draft_3mf(
                        plan,
                        group["asset_id"],
                        contents,
                        license_bytes,
                        copy_index=index,
                        variant=group["geometry_variant"],
                    )
                    filename = f"DRAFT_full_native_{row['selection_id']}_"
                    filename += f"{index:02d}-of-{group['repeat_plate_count']:02d}.3mf"
                    with (destination / filename).open("xb") as stream:
                        stream.write(payload)
                    receipts.append(
                        {"filename": filename, "actual_batch_index": row["batch_index"], **receipt}
                    )
                if args.max_projects is not None and len(receipts) >= args.max_projects:
                    break
        receipt = {
            "schema_version": 1,
            "evidence_class": "generic_full_native_cached_one_part_3MF_drafts_"
            "not_sliced_or_import_verified",
            "plan_canonical_sha256": canonical_sha256(plan),
            "queue_only": args.queue_only,
            "requested_project_count": plan["counts"]["composer_candidate_instances"],
            "created_project_count": len(receipts),
            "complete_queue_export": not args.queue_only
            and len(receipts) == plan["counts"]["composer_candidate_instances"],
            "projects": receipts,
            "Anycubic_GUI_import_observed": False,
            "sliced_or_Gcode_generated": False,
            "printer_or_cloud_contact": False,
            "manufacturing_release": False,
        }
        write_new_evidence(
            [(destination / "receipt.json", json.dumps(receipt, indent=2, allow_nan=False) + "\n")]
        )
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "queue": plan["counts"],
                "created_project_count": len(receipts),
                "complete_queue_export": receipt["complete_queue_export"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
