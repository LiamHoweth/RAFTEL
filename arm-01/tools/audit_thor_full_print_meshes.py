"""Join six original native batches and audit all printed cached-BRep STL variants.

Raw captures/runners keep their actual schemas and hashes. This ordinary-Python
tool never launches native CAD, repairs meshes, infers installed frames or grants
print qualification. Metadata-only checking works without local native assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path, PureWindowsPath

import audit_thor_native_meshes as selected_audit
import prepare_thor_full_print_exports as preparation
import probe_thor_solid_properties_freecad as worker
import thor_slicer_plan as stl

from raftel_arm01.engineering.evidence_files import write_new_evidence
from raftel_arm01.engineering.inertia import validate_centroidal_inertia
from raftel_arm01.engineering.scenarios import _strict_json, canonical_sha256, finite_number
from raftel_arm01.kinematics.thor_frames import rigid_transform

ROOT = Path(__file__).resolve().parents[1]
AGGREGATE_CLASS = "all_printed_cached_BRep_native_exports_not_history_or_manufacturing_validation"
HOST_CLASS = "full47_cached_native_STL_host_audit_not_surface_or_print_qualification"
INPUTS = {
    "aggregate": "hardware/print-planning/thor-full-print-export-native-v1.json",
    "request": "hardware/print-planning/thor-full-print-export-inputs-v1.json",
    "manifest": "hardware/cad/thor-printable-assets-v1.json",
    "inventory": "hardware/cad/thor-mounted-geometry-v2.json",
    "inspection": "hardware/cad/thor-baseline-inspection.json",
}
SOURCE_KEYS = (
    "source_file",
    "source_sha256",
    "object_name",
    "object_type",
    "brep_entry",
    "brep_sha256",
)
AGGREGATE_QUALIFICATION = (
    "feature_history_rebuilt",
    "Art1_exact_migration_accepted",
    "all_53_reference_meanings_verified",
    "surface_equivalence_qualified",
    "mesh_topology_or_self_intersections_qualified",
    "orientation_or_supports_selected",
    "Anycubic_import_observed",
    "physical_fit_strength_or_capacity_qualified",
    "manufacturing_released",
)
REFERENCE_QUALIFICATION = (
    "native_cached_BRep_validated",
    "feature_history_rebuilt",
    "exact_Art1_migration_accepted",
    "mesh_topology_or_fidelity_accepted",
    "mounted_transform_recovered",
    "physical_mass_or_inertia_known",
    "manufacturing_released",
)


def sha(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _false_fields(data: dict, fields) -> None:
    _require(isinstance(data, dict), "qualification/scope must be an object")
    for field in fields:
        _require(data.get(field) is False, f"unqualified scope flag contradicted: {field}")


def _false_contract(data: dict, fields) -> None:
    _require(
        isinstance(data, dict) and set(data) == set(fields), "qualification contract fields differ"
    )
    _false_fields(data, fields)


def _relative(repo: Path, raw: str) -> Path:
    relative = stl._safe_source_path(raw)
    result = (repo / relative).resolve()
    _require(result.is_relative_to(repo.resolve()), "evidence path escapes repository")
    return result


def _archive_pins(mapping: dict) -> dict:
    _require(isinstance(mapping, dict), "archive preservation map must be an object")
    result = {}
    for raw, digest in mapping.items():
        _require(isinstance(raw, str), "archive preservation path must be text")
        text = raw.replace("\\", "/")
        prefix, separator, name = text.rpartition("/freecad-src/")
        _require(
            bool(separator) and bool(prefix) and "/" not in name, "archive path identity differs"
        )
        key = "freecad-src/" + name
        _require(key not in result, "duplicate archive identity in preservation map")
        result[key] = selected_audit._digest(digest)
    return result


def _scaled(actual, source, factor: float) -> None:
    actual, source = finite_number(actual), finite_number(source)
    expected = source * factor
    _require(
        math.isfinite(expected) and not (source != 0 and expected == 0),
        "geometric unit conversion overflow/underflow",
    )
    _require(
        math.isclose(actual, expected, rel_tol=1e-10, abs_tol=0),
        "geometric mm/SI conversion differs",
    )


def validate_export_contract(row: dict, selection: dict) -> None:
    exported = row["draft_stl"]
    _require(
        isinstance(exported, dict) and row.get("upstream_STL_is_not_this_native_export") is True,
        "native STL origin must remain distinct from upstream meshes",
    )
    _false_fields(
        exported,
        (
            "mesh_manifoldness_or_winding_independently_verified",
            "mesh_self_intersections_checked",
            "print_or_fit_qualification",
        ),
    )
    _require(
        exported.get("units") == "mm"
        and exported.get("frame") == selected_audit.FRAME
        and exported.get("encoding") == "binary_STL"
        and exported.get("tessellation") == selection["tessellation"]
        and exported.get("filename") == selection["tessellation"]["filename"],
        "native STL units/frame/tessellation contract differs",
    )
    _require(
        type(exported.get("triangle_count")) is int
        and 1 <= exported["triangle_count"] <= stl.MAX_TRIANGLES
        and type(exported.get("bytes")) is int
        and exported["bytes"] == 84 + 50 * exported["triangle_count"]
        and type(exported.get("vertex_count_before_STL_unindexing")) is int
        and exported["vertex_count_before_STL_unindexing"] > 0,
        "native binary STL count/size contract differs",
    )
    selected_audit._digest(exported.get("sha256"))


def validate_isolated_paths(capture: dict, batch: dict) -> None:
    tails = {
        "UserParameter": "user.cfg",
        "SystemParameter": "system.cfg",
        "UserHomePath": "user-home",
        "UserAppData": "user-data",
        "AppTempPath": "user-temp",
    }
    expected, actual = capture["expected_isolated_paths"], capture["actual_runtime_paths"]
    _require(set(expected) == set(actual) == set(tails), "native isolation path set differs")
    local = stl._safe_source_path(batch["local_run_directory"]).casefold()
    roots, distinct = set(), set()
    for key, tail in tails.items():
        pair = []
        for raw in (expected[key], actual[key]):
            _require(
                isinstance(raw, str) and PureWindowsPath(raw).is_absolute(),
                "captured Windows isolation path must be absolute",
            )
            path = raw.replace("\\", "/").rstrip("/")
            _require(
                not any(part in {".", ".."} for part in path.split("/")),
                "isolation paths cannot contain traversal aliases",
            )
            pair.append(path.casefold())
        _require(
            pair[0] == pair[1] and pair[0].endswith("/" + local + "/" + tail),
            "native isolation path is outside its actual batch directory",
        )
        roots.add(pair[0][: -len(tail) - 1])
        distinct.add(pair[0])
    _require(
        len(roots) == 1 and len(distinct) == 5,
        "five distinct isolated paths must share one batch root",
    )


def validate_geometric_properties(metrics: dict) -> None:
    _require(metrics.get("native_shape_valid") is True, "native cached shape is invalid")
    _require(
        metrics.get("full_self_intersection_analysis_performed") is False,
        "native metadata claims unsupported self-intersection qualification",
    )
    aggregate = metrics["aggregate"]
    solids = metrics["solids"]
    _require(isinstance(solids, list) and bool(solids), "native solids are missing")
    _require(
        type(aggregate.get("solid_count")) is int and aggregate["solid_count"] == len(solids),
        "native solid count differs",
    )
    for index, solid in enumerate(solids):
        _require(
            type(solid.get("solid_index")) is int and solid["solid_index"] == index,
            "native solid indices differ",
        )
        _require(
            solid.get("native_valid") is True and solid.get("native_closed_flag") is True,
            "native solid is not valid/closed",
        )
        _require(finite_number(solid["volume_mm3"]) > 0, "solid volume must be positive")
        _require(len(solid["com_mm"]) == 3, "solid COM dimensions differ")
        tuple(finite_number(value) for value in solid["com_mm"])
        validate_centroidal_inertia(solid["centroidal_geometric_inertia_mm5"])
    rebuilt = worker.aggregate_geometric_solids(solids)
    for name in ("volume_mm3", "com_mm", "centroidal_geometric_inertia_mm5"):
        _numeric_close(aggregate[name], rebuilt[name])
    _require(finite_number(aggregate["volume_mm3"]) > 0, "aggregate volume must be positive")
    _scaled(aggregate["volume_m3"], aggregate["volume_mm3"], 1e-9)
    _require(
        len(aggregate["com_mm"]) == len(aggregate["com_m"]) == 3, "aggregate COM dimensions differ"
    )
    for actual, source in zip(aggregate["com_m"], aggregate["com_mm"], strict=True):
        _scaled(actual, source, 1e-3)
    mm5 = validate_centroidal_inertia(aggregate["centroidal_geometric_inertia_mm5"])
    m5 = validate_centroidal_inertia(aggregate["centroidal_geometric_inertia_m5"])
    for i in range(3):
        for j in range(3):
            _scaled(m5[i][j], mm5[i][j], 1e-15)
    _false_fields(aggregate, ("inter_solid_overlap_check_performed",))
    _require(
        aggregate.get("member_sum_is_union_volume_proven") is (len(solids) == 1)
        and aggregate.get("aggregation_scope") == rebuilt["aggregation_scope"],
        "per-BRep geometric aggregation scope differs",
    )
    flat = metrics["raw_shape_placement_matrix_not_reapplied"]
    _require(isinstance(flat, list) and len(flat) == 16, "raw Shape placement must be 4x4")
    matrix = [[finite_number(value) for value in flat[i : i + 4]] for i in range(0, 16, 4)]
    for i in range(3):
        matrix[i][3] /= 1000
    rigid_transform(matrix)
    bounds = metrics["native_bounds_mm"]
    for axis in "XYZ":
        _require(
            finite_number(bounds[axis + "Min"]) < finite_number(bounds[axis + "Max"]),
            "native bounds are inverted/degenerate",
        )


def _numeric_close(actual, expected) -> None:
    if isinstance(expected, (list, tuple)):
        _require(
            isinstance(actual, (list, tuple)) and len(actual) == len(expected),
            "geometric dimensions differ",
        )
        for first, second in zip(actual, expected, strict=True):
            _numeric_close(first, second)
    else:
        first, second = finite_number(actual), finite_number(expected)
        _require(
            math.isclose(first, second, rel_tol=1e-11, abs_tol=0),
            "native geometric aggregate differs from component arithmetic",
        )


def validate_registry(request: dict, manifest: dict, inventory: dict, inspection: dict) -> dict:
    _require(
        manifest.get("evidence_class")
        == "source_capture_reconciliation_not_export_or_manufacturing_release",
        "unsupported printable manifest evidence class",
    )
    _require(
        inventory.get("validation_class")
        == "restored_cached_geometry_with_explicit_grouping_assumptions"
        and type(inventory.get("instance_count")) is int
        and inventory["instance_count"] == 518
        and inventory.get("errors") == []
        and inventory.get("missing_object_records") == [],
        "unsupported or incomplete mounted inventory",
    )
    _require(
        type(request.get("schema_version")) is int
        and request["schema_version"] == 1
        and request.get("source_revision") == stl.SOURCE_REVISION
        and request.get("evidence_class") == "selected_saved_BRep_properties_request",
        "unsupported full request schema/source",
    )
    files = preparation.source_files(inspection)
    registry = preparation.registry_rows(manifest, inventory, files)
    _require(len(request["selections"]) == 47, "full request requires all47 variants")
    selections = {row["selection_id"]: row for row in request["selections"]}
    _require(len(selections) == 47, "duplicate full request selection")
    registry_hash = canonical_sha256(registry)
    inputs = {
        "printable_asset_manifest": canonical_sha256(manifest),
        "source_inspection": canonical_sha256(inspection),
        "mounted_inventory": canonical_sha256(inventory),
    }
    original_pins = {row["source_file"]: row["sha256"] for row in files.values()}
    all_instances = set()
    for selection, expected in zip(request["selections"], registry, strict=True):
        context = selection["reference_capture"]
        _require(
            context.get("evidence_class")
            == "full_print_registry_host_preparation_not_native_export"
            and context.get("input_canonical_sha256") == inputs
            and context.get("canonical_variant_registry_sha256") == registry_hash
            and context.get("counts") == preparation.COUNTS
            and all(type(value) is int for value in context["counts"].values()),
            "full registry reference capture is stale or unsupported",
        )
        for key in (
            "asset_id",
            "geometry_variant",
            "quantity_required",
            "source_asset_canonical_sha256",
            "history_status",
        ):
            _require(context.get(key) == expected[key], "full registry identity/quantity differs")
        for key in ("source_file", "source_sha256", "object_name"):
            _require(selection.get(key) == expected[key], "selected source pin/object differs")
        _require(
            selection.get("object_type")
            == (
                "Part::Mirroring"
                if expected["geometry_variant"] == "reflected"
                else "PartDesign::Body"
            ),
            "source type differs from saved variant",
        )
        _require(
            selection.get("uniform_density") is None
            and selection.get("upstream_stl_reference") is None,
            "full export must retain geometry-only native scope",
        )
        _require(
            context.get("original_archive_count_verified") == 57
            and type(context["original_archive_count_verified"]) is int
            and context.get("original_archive_bytes_verified_before_after") is True
            and context.get("original_archive_set_canonical_sha256")
            == canonical_sha256(original_pins),
            "original archive preparation pin differs",
        )
        _require(
            context.get("saved_xml_context_canonical_sha256")
            == canonical_sha256(context["saved_xml_context"]),
            "saved XML context hash differs",
        )
        _false_contract(context["qualification"], REFERENCE_QUALIFICATION)
        _require(
            context.get("frame_policy") == preparation.selected.FRAME_POLICY,
            "full registry frame policy differs",
        )
        members = context["installed_instances"]
        _require(
            type(context.get("quantity_required")) is int
            and context["quantity_required"] == len(members),
            "variant quantity/instance count differs",
        )
        expected_members = expected["members"]
        for member, preserved in zip(members, expected_members, strict=True):
            wanted = {
                "instance_id": preserved["instance_id"],
                "linked_object": preserved["linked_object"],
                "variant_id": preserved["variant_id"],
                "geometry_operation": preserved["geometry_operation"],
                "preserved_installed_volume_mm3": preserved["volume_mm3"],
                "preserved_installed_COM_m": preserved["zero_world_com_m"],
                "installed_coordinate_frame": inventory["coordinate_frame"],
                "source_to_installed_transform": None,
            }
            _require(
                member == wanted and member["instance_id"] not in all_instances,
                "installed leaf identity/geometry/frame differs or duplicates",
            )
            all_instances.add(member["instance_id"])
        _require(
            context.get("installed_instance_set_canonical_sha256")
            == canonical_sha256([member["instance_id"] for member in members]),
            "installed instance-set hash differs",
        )
    _require(len(all_instances) == 65, "full registry must cover65unique installed instances")
    # The original worker schema remains bounded to actual native batches.
    for batch in preparation.worker_batches(request):
        worker.validate_request(batch)
    return selections


def validate_full_metadata(
    aggregate, request_raw, raw_batches, manifest, inventory, inspection, *, earlier_capture=None
):
    """Check actual full-runner schema, six raw pairs and exact47/65 registry joins."""
    request = _strict_json(request_raw)
    by_id = validate_registry(request, manifest, inventory, inspection)
    _require(
        aggregate.get("full_request_path") == "arm-01/" + INPUTS["request"],
        "aggregate full-request provenance path differs",
    )
    _require(
        type(aggregate.get("schema_version")) is int
        and aggregate["schema_version"] == 1
        and aggregate.get("evidence_class") == AGGREGATE_CLASS
        and aggregate.get("audit_status") == "complete_six_batches_47_cached_geometry_variants_only"
        and aggregate.get("source_revision") == stl.SOURCE_REVISION
        and aggregate.get("full_request_sha256") == sha(request_raw),
        "unsupported or stale full native aggregate",
    )
    _false_fields(
        aggregate,
        ("source_to_installed_transforms_inferred", "cross_asset_inertia_aggregation_performed"),
    )
    _require(
        aggregate.get("density_or_physical_inertia") is None, "physical inertia must remain unknown"
    )
    _false_contract(aggregate["qualification"], AGGREGATE_QUALIFICATION)
    _require(
        aggregate.get("coordinate_frame")
        == (
            "separate per-source saved BRep storage coordinates in mm; "
            "no extra XML/link placements applied"
        )
        and aggregate["runtime"].get("complete_runtime_and_OS_library_bundle_verified_by_worker")
        is False,
        "aggregate frame/runtime authentication scope differs",
    )
    preservation = aggregate["preservation"]
    stl._safe_source_path(preservation["original_eight_selection_capture_path"])
    _false_fields(preservation, ("document_opened_or_recomputed", "native_document_saved"))
    for name in (
        "all57_originals_verified_before_after_each_batch",
        "all_input_copies_unchanged",
        "all_retained_worker_request_launcher_snapshots_unchanged",
        "original_eight_selection_capture_preserved",
    ):
        _require(preservation.get(name) is True, "aggregate preservation claim differs")
    _require(
        len(aggregate["batches"]) == 6 and set(raw_batches) == set(range(1, 7)),
        "exactly six actual native batches required",
    )
    sources = {row["path"]: row["sha256"] for row in inspection["files"]}
    expected_batches = preparation.worker_batches(request)
    captured, contexts, observed_batches = {}, {}, set()
    for batch in aggregate["batches"]:
        index = batch["batch_index"]
        _require(
            type(index) is int and 1 <= index <= 6 and index not in observed_batches,
            "duplicate/invalid native batch index",
        )
        observed_batches.add(index)
        for key in ("raw_capture_path", "raw_runner_path", "local_run_directory"):
            stl._safe_source_path(batch[key])
        capture_raw, runner_raw = raw_batches[index]
        _require(
            sha(capture_raw) == batch["raw_capture_sha256"]
            and sha(runner_raw) == batch["raw_runner_sha256"],
            "raw capture/runner bytes differ from aggregate",
        )
        capture, runner = _strict_json(capture_raw), _strict_json(runner_raw)
        actual_request = capture["request"]
        _require(
            canonical_sha256(actual_request) == canonical_sha256(expected_batches[index - 1]),
            "actual native batch request is missing/swapped/stale",
        )
        expected_ids = [row["selection_id"] for row in actual_request["selections"]]
        _require(
            batch["selection_ids"] == expected_ids
            and batch["selection_count"] == len(expected_ids)
            and type(batch["selection_count"]) is int,
            "aggregate native batch coverage differs",
        )
        _require(
            type(runner.get("schema_version")) is int
            and runner["schema_version"] == 1
            and runner.get("batch_index") == index
            and type(runner["batch_index"]) is int
            and runner.get("outcome") == "process_completed"
            and type(runner.get("returncode")) is int
            and runner["returncode"] == 0
            and runner.get("selection_count") == len(expected_ids)
            and type(runner["selection_count"]) is int,
            "actual native runner did not complete its batch",
        )
        for field in (
            "process_launched",
            "original57_sha256_unchanged",
            "input_copy_sha256_unchanged",
            "retained_sha256_unchanged",
            "launcher_snapshot_unchanged",
            "capture_completed",
        ):
            _require(
                runner.get(field) is True, "native runner preservation/completion flag is absent"
            )
        _false_fields(runner, ("migration_accepted", "manufacturing_released"))
        _require(
            runner.get("report_sha256") == sha(capture_raw)
            and runner.get("full_request_sha256") == sha(request_raw)
            and runner.get("launch_contract_sha256") == batch["launch_contract_sha256"]
            and runner.get("launcher_snapshot_sha256") == batch["launcher_snapshot_sha256"]
            and runner.get("executable_sha256") == aggregate["runtime"]["executable_sha256"],
            "actual native runner raw/snapshot/executable pins differ",
        )
        _require(
            all(
                batch[key] == runner[key]
                for key in ("started_utc", "finished_utc", "elapsed_seconds")
            )
            and finite_number(runner["elapsed_seconds"]) >= 0,
            "aggregate/runner timing metadata differs",
        )
        _require(
            type(capture.get("schema_version")) is int
            and capture["schema_version"] == 1
            and capture.get("evidence_class") == selected_audit.CAPTURE_CLASS
            and capture.get("audit_status") == "complete_selected_cached_geometry_only"
            and capture.get("source_revision") == stl.SOURCE_REVISION
            and runner.get("audit_status") == capture["audit_status"]
            and capture.get("errors") == [],
            "native capture scope/status differs",
        )
        _require(
            capture.get("request_sha256") == batch["request_sha256"]
            and capture.get("capture_script_sha256")
            == batch["worker_sha256"]
            == aggregate["runtime"]["worker_sha256"]
            and capture.get("runner_declared_executable_sha256")
            == aggregate["runtime"]["executable_sha256"],
            "native worker/request/runtime pins differ",
        )
        _false_fields(
            capture,
            (
                "document_opened_or_recomputed",
                "native_document_saved",
                "cross_asset_aggregation_performed",
            ),
        )
        _require(
            capture.get("input_copy_bytes_unchanged") is True
            and capture.get("runtime_isolated_paths_verified") is True
            and capture.get("coordinate_frame") == selected_audit.FRAME
            and capture.get("full_runtime_bundle_verified_by_worker") is False
            and capture.get("declared_revision_not_independently_authenticated_by_worker") is True,
            "native isolation/frame/authentication scope differs",
        )
        for field in ("open_document_count_before", "open_document_count_after"):
            _require(
                type(capture.get(field)) is int and capture[field] == 0,
                "native capture opened a document",
            )
        validate_isolated_paths(capture, batch)
        summary = worker.verify_fixture_records(capture["primitive_fixtures"]["records"])
        recorded = capture["primitive_fixtures"]["summary"]
        _require(
            recorded == batch["primitive_fixture_summary"]
            and recorded.get("verified") is True
            and type(recorded.get("case_count")) is int
            and recorded["case_count"] == 9
            and recorded.get("contract") == summary["contract"],
            "native fixture summary scope differs",
        )
        for name in (
            "maximum_relative_volume_error",
            "maximum_com_error_mm",
            "maximum_relative_tensor_error",
        ):
            _require(
                math.isclose(
                    finite_number(recorded[name]), summary[name], rel_tol=1e-9, abs_tol=1e-14
                ),
                "native fixture records/summary differ beyond arithmetic roundoff",
            )
        _require(
            batch["actual_runtime_paths"] == capture["actual_runtime_paths"]
            and batch["open_documents_before"] == capture["open_document_count_before"]
            and batch["open_documents_after"] == capture["open_document_count_after"],
            "aggregate runtime path/document facts differ",
        )
        _require(
            capture["freecad_version"] == aggregate["runtime"]["freecad_version"]
            and capture["opencascade_version"] == aggregate["runtime"]["opencascade_version"],
            "native runtime version differs",
        )
        _require(
            runner["original57_sha256_before"] == runner["original57_sha256_after"]
            and _archive_pins(runner["original57_sha256_before"]) == sources,
            "all57 original archive preservation pins differ",
        )
        expected_sources = {
            row["source_file"]: row["source_sha256"] for row in actual_request["selections"]
        }
        _require(
            runner["input_copy_sha256_before"] == runner["input_copy_sha256_after"]
            and _archive_pins(runner["input_copy_sha256_before"]) == expected_sources
            and capture["source_copy_sha256_before"]
            == capture["source_copy_sha256_after"]
            == expected_sources,
            "native input-copy source pins differ",
        )
        retained = runner["retained_sha256_before"]
        _require(
            retained == runner["retained_sha256_after"] and len(retained) == 2,
            "retained worker/request snapshots differ",
        )
        tails = {
            raw.replace("\\", "/").rsplit("/", 1)[-1]: value for raw, value in retained.items()
        }
        _require(
            tails
            == {
                "request.json": batch["request_sha256"],
                "probe_thor_solid_properties_freecad.py": batch["worker_sha256"],
            },
            "retained worker/request snapshot pins differ",
        )
        rows = capture["selections"]
        _require(
            len(rows) == len(expected_ids)
            and {row["selection_id"] for row in rows} == set(expected_ids)
            and len({row["selection_id"] for row in rows}) == len(rows),
            "native capture selection set differs",
        )
        for row in rows:
            identifier = row["selection_id"]
            selection = by_id[identifier]
            _require(identifier not in captured, "native selection appears in multiple batches")
            wanted = {key: selection[key] for key in SOURCE_KEYS}
            wanted["xml_placement_not_applied"] = selection["xml_placement"]
            _require(
                row.get("source_binding") == wanted
                and row.get("coordinate_frame") == selected_audit.FRAME
                and row.get("coordinate_frame_id")
                == f"saved-brep:{selection['source_file']}::"
                f"{selection['object_name']}@{selection['brep_sha256']}",
                "native selected source/frame identity differs",
            )
            _require(
                row.get("uniform_density_scenario") is None
                and row.get("physical_or_purchased_internal_or_nonuniform_print_inertia_kg_m2")
                is None,
                "physical/nonuniform inertia must remain unknown",
            )
            validate_geometric_properties(row["cached_shape_properties"])
            validate_export_contract(row, selection)
            captured[identifier] = row
            contexts[identifier] = {"batch": batch, "runner": runner, "capture": capture}
    _require(set(captured) == set(by_id), "native batches omit or add a full-request selection")
    variants = {row["selection_id"]: row for row in aggregate["variants"]}
    _require(
        len(variants) == 47 and len(aggregate["variants"]) == 47 and set(variants) == set(by_id),
        "aggregate variant set differs",
    )
    triangles = 0
    for identifier, row in captured.items():
        variant, selection = variants[identifier], by_id[identifier]
        context = selection["reference_capture"]
        _require(
            variant["batch_index"] == contexts[identifier]["batch"]["batch_index"]
            and variant["asset_id"] == context["asset_id"]
            and variant["geometry_variant"] == context["geometry_variant"]
            and type(variant["quantity_required"]) is int
            and variant["quantity_required"] == context["quantity_required"]
            and variant["installed_instance_ids"]
            == [member["instance_id"] for member in context["installed_instances"]]
            and variant["source_binding"] == row["source_binding"]
            and variant["coordinate_frame"] == row["coordinate_frame"]
            and variant["native_cached_shape_valid"] is True
            and variant["density_or_physical_inertia"] is None,
            "aggregate variant source/quantity/installed/frame facts differ",
        )
        _numeric_close(
            variant["volume_mm3"], row["cached_shape_properties"]["aggregate"]["volume_mm3"]
        )
        _numeric_close(variant["com_mm"], row["cached_shape_properties"]["aggregate"]["com_mm"])
        exported = dict(variant["draft_stl"])
        local = exported.pop("local_path")
        stl._safe_source_path(local)
        _require(
            exported == row["draft_stl"]
            and local
            == contexts[identifier]["batch"]["local_run_directory"]
            + "/draft-stl/"
            + exported["filename"],
            "aggregate native STL export/path differs",
        )
        triangles += exported["triangle_count"]
    counts = aggregate["counts"]
    _require(
        all(type(value) is int for value in counts.values())
        and counts
        == {
            "original_archives_preserved": 57,
            "source_assets": 46,
            "captured_geometry_variants": 47,
            "represented_installed_instances": 65,
            "native_batches": 6,
            "unique_primitive_fixture_cases": 9,
            "primitive_fixture_executions": 54,
            "draft_stl_files": 47,
            "total_draft_stl_triangles": triangles,
        },
        "full native aggregate counts differ",
    )
    measured_volume = math.fsum(
        captured[key]["cached_shape_properties"]["aggregate"]["volume_mm3"]
        * by_id[key]["reference_capture"]["quantity_required"]
        for key in by_id
    )
    preserved_volume = math.fsum(
        member["preserved_installed_volume_mm3"]
        for selection in by_id.values()
        for member in selection["reference_capture"]["installed_instances"]
    )
    comparison = aggregate["geometric_volume_reconciliation"]
    _numeric_close(comparison["quantity_weighted_component_volume_mm3"], measured_volume)
    _numeric_close(comparison["preserved_installed_component_volume_mm3"], preserved_volume)
    _require(
        math.isclose(
            finite_number(comparison["difference_mm3"]),
            measured_volume - preserved_volume,
            rel_tol=1e-10,
            abs_tol=1e-8,
        ),
        "aggregate component-volume difference differs",
    )
    _numeric_close(
        aggregate["process_elapsed_seconds_sum"],
        math.fsum(batch["elapsed_seconds"] for batch in aggregate["batches"]),
    )
    targets = {(source.casefold(), name) for _, _, source, name in preparation.selected.TARGETS}
    expected_eight = [
        key
        for key, selection in by_id.items()
        if (selection["source_file"].casefold(), selection["object_name"]) in targets
    ]
    repeat = aggregate["earlier_eight_repeatability"]
    _require(
        type(repeat.get("matched_selection_count")) is int
        and repeat["matched_selection_count"] == 8
        and len(expected_eight) == 8
        and repeat.get("matched_current_selection_ids") == expected_eight
        and repeat.get("exact_source_bindings_properties_and_STL_sha256") is True,
        "earlier-eight repeatability identity/count summary differs",
    )
    if earlier_capture is not None:
        _require(
            earlier_capture.get("evidence_class") == selected_audit.CAPTURE_CLASS
            and earlier_capture.get("source_revision") == stl.SOURCE_REVISION,
            "historical eight capture scope differs",
        )
        old = {
            (row["source_binding"]["source_file"], row["source_binding"]["object_name"]): row
            for row in earlier_capture["selections"]
        }
        _require(
            len(old) == len(earlier_capture["selections"]) == 8,
            "historical eight identity count differs",
        )
        for key in expected_eight:
            current = captured[key]
            previous = old.get(
                (current["source_binding"]["source_file"], current["source_binding"]["object_name"])
            )
            _require(
                previous is not None
                and previous["source_binding"] == current["source_binding"]
                and previous["cached_shape_properties"] == current["cached_shape_properties"]
                and previous["draft_stl"]["sha256"] == current["draft_stl"]["sha256"],
                "historical/native component repeatability facts differ",
            )
    return {
        "aggregate": aggregate,
        "request": request,
        "request_raw_sha256": sha(request_raw),
        "by_id": by_id,
        "captured": captured,
        "contexts": contexts,
        "variants": variants,
        "metadata_class": "six_actual_native_batch_raw_pin_and_registry_consistency_checks_only",
        "earlier_eight_repeatability_verified": earlier_capture is not None,
    }


def load_evidence(root: Path = ROOT):
    documents = {
        name: _strict_json(stl._bounded_read(root / path)) for name, path in INPUTS.items()
    }
    request_raw = stl._bounded_read(root / INPUTS["request"])
    original_capture = documents["aggregate"]["preservation"]
    original_raw = stl._bounded_read(
        _relative(root.parent, original_capture["original_eight_selection_capture_path"])
    )
    _require(
        sha(original_raw) == original_capture["original_eight_selection_capture_sha256"],
        "original eight-selection historical capture changed",
    )
    raw_batches = {}
    for batch in documents["aggregate"]["batches"]:
        index = batch["batch_index"]
        _require(index not in raw_batches, "duplicate raw batch index")
        raw_batches[index] = tuple(
            stl._bounded_read(_relative(root.parent, batch[key]))
            for key in ("raw_capture_path", "raw_runner_path")
        )
    joined = validate_full_metadata(
        documents["aggregate"],
        request_raw,
        raw_batches,
        documents["manifest"],
        documents["inventory"],
        documents["inspection"],
        earlier_capture=_strict_json(original_raw),
    )
    return joined, documents, request_raw, raw_batches


def audit_one_mesh(contents: bytes, row: dict, selection: dict) -> dict:
    """Validate byte binding, then screen topology/normals/bounds and gross scale."""
    validate_export_contract(row, selection)
    exported = row["draft_stl"]
    _require(
        exported["units"] == "mm"
        and exported["frame"] == selected_audit.FRAME
        and exported["encoding"] == "binary_STL"
        and exported["tessellation"] == selection["tessellation"]
        and exported["filename"] == selection["tessellation"]["filename"],
        "native STL metadata differs",
    )
    _require(
        type(exported["bytes"]) is int
        and len(contents) == exported["bytes"]
        and sha(contents) == exported["sha256"],
        "native STL byte/hash binding differs",
    )
    mesh = stl.analyze_stl(contents)
    _require(
        mesh["encoding"] == "binary"
        and type(exported["triangle_count"]) is int
        and mesh["triangle_count"] == exported["triangle_count"],
        "native STL facet encoding/count differs",
    )
    metrics = row["cached_shape_properties"]
    bounds, volume = metrics["native_bounds_mm"], finite_number(metrics["aggregate"]["volume_mm3"])
    _require(volume > 0, "native source volume must be positive")
    low, high = (
        [finite_number(bounds[axis + suffix]) for axis in "XYZ"] for suffix in ("Min", "Max")
    )
    tolerance = max(1e-5, 2e-7 * max(abs(value) for value in (*low, *high)))
    mesh_low, mesh_high = (mesh["bounds_interpreted_mm"][name] for name in ("min", "max"))
    contained = all(
        mesh_low[i] >= low[i] - tolerance and mesh_high[i] <= high[i] + tolerance for i in range(3)
    )
    ratio = finite_number(mesh["absolute_signed_volume_interpreted_mm3"] / volume)
    blockers = []
    if mesh["topology"]["closed_consistently_oriented_two_manifold"] is not True:
        blockers.append("exact_vertex_topology_or_winding_failure")
    if mesh["algebraic_signed_volume_interpreted_mm3"] <= 0:
        blockers.append("nonpositive_winding_integral")
    if any(mesh["stored_normal_warnings"].values()):
        blockers.append("stored_facet_normal_zero_or_opposed_to_winding")
    if not contained:
        blockers.append("mesh_bounds_outside_native_bounds_at_float32_tolerance")
    if not 0.9 <= ratio <= 1.1:
        blockers.append("gross_unit_or_scale_sanity_failure")
    return {
        "mesh": mesh,
        "draft_candidate": not blockers,
        "blockers": blockers,
        "native_comparison": {
            "native_bounds_mm": bounds,
            "native_volume_mm3": volume,
            "inside_native_bounds_at_float32_tolerance": contained,
            "float32_bound_tolerance_mm": tolerance,
            "winding_volume_ratio": ratio,
            "gross_unit_scale_band": [0.9, 1.1],
            "band_is_not_a_surface_or_fit_tolerance": True,
        },
    }


def audit_full_meshes(joined: dict, repo_root: Path) -> dict:
    _require(
        joined.get("earlier_eight_repeatability_verified") is True,
        "full payload audit requires the separately verified historical eight capture",
    )
    selections = []
    finger_points = {}
    for identifier, selection in joined["by_id"].items():
        row, variant = joined["captured"][identifier], joined["variants"][identifier]
        contents = stl._bounded_read(_relative(repo_root, variant["draft_stl"]["local_path"]))
        audited = audit_one_mesh(contents, row, selection)
        batch = joined["contexts"][identifier]["batch"]
        context = selection["reference_capture"]
        selections.append(
            {
                "selection_id": identifier,
                "batch_index": batch["batch_index"],
                "installed_asset_id": context["asset_id"],
                "geometry_variant": context["geometry_variant"],
                "installed_quantity": context["quantity_required"],
                "installed_instance_ids": variant["installed_instance_ids"],
                "source_binding": row["source_binding"],
                "coordinate_frame": selected_audit.FRAME,
                "native_export": variant["draft_stl"],
                "actual_batch_bindings": {
                    key: batch[key]
                    for key in (
                        "raw_capture_sha256",
                        "raw_runner_sha256",
                        "request_sha256",
                        "worker_sha256",
                        "launcher_snapshot_sha256",
                    )
                },
                **audited,
                "installed_frame_correspondence": None,
                "qualification": {
                    "self_intersections_checked": False,
                    "surface_fidelity_qualified": False,
                    "printed_strength_or_fit": False,
                    "manufacturing_release": False,
                },
            }
        )
        if context["asset_id"] == "GripperFinger::Body":
            _, facets, _ = stl.parse_stl(contents)
            finger_points[context["geometry_variant"]] = Counter(
                point for _, triangle in facets for point in triangle
            )
    reflection = {(-x, y, z): count for (x, y, z), count in finger_points["nominal"].items()}
    reflection_matches = Counter(reflection) == finger_points["reflected"]
    for row in selections:
        if row["geometry_variant"] == "reflected" and not reflection_matches:
            row["blockers"].append("saved_finger_vertex_reflection_not_corresponding")
            row["draft_candidate"] = False
    return {
        "schema_version": 1,
        "evidence_class": HOST_CLASS,
        "source_revision": stl.SOURCE_REVISION,
        "native_aggregate_canonical_sha256": canonical_sha256(joined["aggregate"]),
        "full_request_raw_sha256": joined["request_raw_sha256"],
        "audit_mode": "ordinary_Python_host_only_no_native_process_or_mesh_repair",
        "counts": {
            "audited_geometry_variants": len(selections),
            "represented_installed_instances": 65,
            "candidate_geometry_variants": sum(row["draft_candidate"] for row in selections),
            "blocked_geometry_variants": sum(not row["draft_candidate"] for row in selections),
            "candidate_installed_instances": sum(
                row["installed_quantity"] for row in selections if row["draft_candidate"]
            ),
            "blocked_installed_instances": sum(
                row["installed_quantity"] for row in selections if not row["draft_candidate"]
            ),
            "total_triangles": sum(row["mesh"]["triangle_count"] for row in selections),
        },
        "selections": selections,
        "finger_vertex_reflection_check": {
            "test": "exact_unindexed_float32_vertex_multiset_X_reflection",
            "matches": reflection_matches,
            "native_saved_variant_not_new_reflection_operation": True,
            "installed_link_transform_established": False,
            "surface_equivalence_from_point_cloud_alone": False,
        },
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True, help="new output evidence path")
    args = parser.parse_args(argv)
    try:
        joined, documents, _, _ = load_evidence()
        result = (
            {
                "schema_version": 1,
                "evidence_class": joined["metadata_class"],
                "source_revision": stl.SOURCE_REVISION,
                "counts": documents["aggregate"]["counts"],
                "mesh_payloads_audited": False,
                "manufacturing_release": False,
            }
            if args.metadata_only
            else audit_full_meshes(joined, ROOT.parent)
        )
        write_new_evidence(
            [(args.output, json.dumps(result, indent=2, allow_nan=False) + "\n")],
            protected_inputs=[ROOT / path for path in INPUTS.values()],
        )
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        parser.error(str(error))
    print(json.dumps(result["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
