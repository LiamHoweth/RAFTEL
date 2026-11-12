"""Conditional uniform-solid inertia of authenticated installed printed copies."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from dataclasses import asdict
from pathlib import Path, PureWindowsPath

from raftel_arm01.engineering.inertia import (
    MassProperties,
    aggregate_mass_properties,
    transform_mass_properties,
)

FRAME = "native master assembly saved-zero Cartesian frame, metres"


def absolute_windows_path(value):
    if (
        not isinstance(value, str)
        or not value
        or any(part == ".." for part in value.replace("/", "\\").split("\\"))
    ):
        raise ValueError("native paths must be absolute without traversal")
    path = PureWindowsPath(value)
    if not path.is_absolute():
        raise ValueError("native paths must be absolute without traversal")
    return path


def digest(value):
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def strict_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("evidence must be a regular file without symlink")
    with path.open("rb") as stream:
        raw = stream.read(16777217)
    if len(raw) > 16777216:
        raise ValueError("evidence exceeds 16 MiB bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate evidence field")
            result[key] = value
        return result

    def finite(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite evidence number")
        return parsed

    def reject(value):
        raise ValueError("nonfinite evidence constant")

    result = json.loads(
        raw.decode("utf-8"), object_pairs_hook=unique, parse_float=finite, parse_constant=reject
    )
    if not isinstance(result, dict):
        raise ValueError("evidence root must be object")
    return raw, result


def validate_capture(capture):
    """One canonical gate shared by pure aggregation and the file builder."""
    if type(capture.get("schema_version")) is not int or capture["schema_version"] != 1:
        raise ValueError("unsupported typed native capture schema")
    if capture.get("evidence_class") != "native_cached_printed_tensor_frame_authentication":
        raise ValueError("unsupported native evidence class")
    for key, expected in {
        "source_assembly_recomputed": False,
        "synthetic_coordinate_fixture_recomputed": True,
        "cad_saved": False,
        "source_copy_bytes_unchanged": True,
        "preexisting_documents_preserved": True,
        "physical_inertia": None,
        "whole_arm_inertia": None,
        "native_geometric_integration_uncertainty_quantified": False,
    }.items():
        if capture.get(key) is not expected:
            raise ValueError("native scope or preservation gate failed: " + key)
    for key, expected in {
        "open_document_count_before": 0,
        "open_document_count_after": 0,
        "installed_leaf_count": 518,
    }.items():
        if type(capture.get(key)) is not int or capture[key] != expected:
            raise ValueError("native document/identity count gate failed")
    if capture.get("errors") != [] or type(capture.get("errors")) is not list:
        raise ValueError("native capture errors are present")
    if capture.get("status") not in {
        "complete_frame_authentication",
        "partial_frame_authentication",
    }:
        raise ValueError("native status not accepted")
    if type(capture.get("complete_65_printed_coverage")) is not bool:
        raise ValueError("typed complete coverage flag required")
    count = sum(row.get("status") == "authenticated" for row in capture["instances"])
    if (
        type(capture.get("authenticated_instance_count")) is not int
        or capture["authenticated_instance_count"] != count
    ):
        raise ValueError("authenticated instance count does not reproduce")
    if capture["complete_65_printed_coverage"] != (count == 65):
        raise ValueError("complete coverage summary does not reproduce")
    if (capture["status"] == "complete_frame_authentication") != capture[
        "complete_65_printed_coverage"
    ]:
        raise ValueError("native status and coverage disagree")
    for prefix in ("source_copy", "original_copy"):
        before, after = capture[prefix + "_sha256_before"], capture[prefix + "_sha256_after"]
        if not isinstance(before, dict) or len(before) != 57 or before != after:
            raise ValueError("native before/after archive ledgers disagree")
        if any(
            not isinstance(value, str)
            or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
            for value in before.values()
        ):
            raise ValueError("invalid native archive digest")
    runtime = capture["runtime_isolation"]
    if runtime.get("requested") is not True or runtime.get("verified") is not True:
        raise ValueError("native isolation was not verified")
    keys = {"UserParameter", "SystemParameter", "UserHomePath", "UserAppData", "AppTempPath"}
    actual, expected = runtime["actual_paths"], capture["expected_runtime_paths"]
    if set(actual) != keys or set(expected) != keys:
        raise ValueError("all five runtime paths required")
    run_root = absolute_windows_path(runtime["root"])
    for key in keys:
        if absolute_windows_path(actual[key]) != absolute_windows_path(
            expected[key]
        ) or not absolute_windows_path(actual[key]).is_relative_to(run_root):
            raise ValueError("native runtime path escaped or differs")
    documents = capture["loaded_document_sources"]
    if len(documents) != 53 or len({row["document"] for row in documents}) != 53:
        raise ValueError("53 distinct private restored documents required")
    for row in documents:
        path = absolute_windows_path(row["path"])
        if (
            path.parent != run_root / "source"
            or capture["source_copy_sha256_before"].get(path.name) != row["sha256"]
        ):
            raise ValueError("restored source path/hash not authenticated")
    fixture = capture["synthetic_coordinate_fixture"]
    expected_bounds = {
        "direct_child": [[96, 30, 0], [100, 32, 6]],
        "link_false": [[96, 20, 0], [100, 22, 6]],
        "link_true": [[100, 30, 0], [106, 32, 4]],
        "group_link_false": [[96, 30, 0], [100, 32, 6]],
        "group_link_true": [[60, 30, 0], [66, 32, 4]],
    }
    if (
        fixture.get("passed") is not True
        or len(fixture["cases"]) != 5
        or {row["name"] for row in fixture["cases"]} != set(expected_bounds)
    ):
        raise ValueError("native coordinate fixture coverage failed")
    probe = frame_module()
    for row in fixture["cases"]:
        target = expected_bounds[row["name"]]
        for line in row["expected_world_bounds_mm"]:
            for value in line:
                probe.finite(value)
        if row["expected_world_bounds_mm"] != target:
            raise ValueError("native fixture expectation changed")
        observed = row["observed_world_optimal_bounds_mm"]
        if len(observed) != 2 or any(len(line) != 3 for line in observed):
            raise ValueError("native fixture dimensions changed")
        residual = max(
            abs(probe.finite(observed[i][j]) - target[i][j]) for i in range(2) for j in range(3)
        )
        if residual > 1e-6 or residual != probe.finite(row["maximum_extremum_error_mm"]):
            raise ValueError("native fixture check does not reproduce")
    if (
        capture.get("freecad_version", [])[:3] != ["1", "1", "4"]
        or capture.get("opencascade_version") != "7.8.1"
    ):
        raise ValueError("unsupported native runtime version")
    states = capture["final_state_counts"]
    if any(type(value) is not int or value < 0 for value in states.values()) or any(
        states.get(key, 0) for key in ("Invalid", "Error")
    ):
        raise ValueError("native final states contain invalid/error objects")


def frame_module():
    path = Path(__file__).with_name("probe_thor_printed_tensor_frames.py")
    spec = importlib.util.spec_from_file_location("printed_frame_math", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def study(capture, registry, density_kg_m3=1240.0):
    """Validate full printed coverage before aggregating a declared solid model.

    The caller supplies retained native evidence, not arbitrary geometric input
    promoted to physical measurement. The CLI binds all retained input bytes.
    """
    if (
        isinstance(density_kg_m3, bool)
        or not isinstance(density_kg_m3, (int, float))
        or not math.isfinite(density_kg_m3)
        or density_kg_m3 <= 0
    ):
        raise ValueError("declare a positive finite uniform-solid density")
    validate_capture(capture)
    probe = frame_module()
    expected = {
        identifier: row["selection_id"]
        for row in registry["variants"]
        for identifier in row["installed_instance_ids"]
    }
    if (
        len(registry["variants"]) != 47
        or len({row["selection_id"] for row in registry["variants"]}) != 47
        or len(expected) != 65
        or sum(len(row["installed_instance_ids"]) for row in registry["variants"]) != 65
        or sum(row["quantity_required"] for row in registry["variants"]) != 65
    ):
        raise ValueError("expected complete unique 47-variant/65-instance registry")
    variants = {row["selection_id"]: row for row in capture["variants"]}
    if len(capture["variants"]) != 47 or len(variants) != 47:
        raise ValueError("native source variants must be unique")
    rows = capture["instances"]
    identities = [row["instance_id"] for row in rows]
    if len(set(identities)) != len(identities) or set(identities) != set(expected):
        raise ValueError("printed instance identity coverage changed")
    if set(variants) != {row["selection_id"] for row in registry["variants"]}:
        raise ValueError("printed geometry variant coverage changed")
    base = {
        "schema_version": 1,
        "evidence_class": "conditional_uniform_solid_printed_subset_inertia_not_physical_prints",
        "status": "blocked_incomplete_frames",
        "coordinate_frame": FRAME,
        "reference_uniform_density_kg_m3": density_kg_m3,
        "density_evidence": (
            "caller-declared uniform-solid reference assumption; "
            "not measured filament or installed print density"
        ),
        "uniform_solid_model_is_slicer_infill": False,
        "geometry_variants": len(variants),
        "printed_instance_count": len(rows),
        "authenticated_instance_count": sum(row["status"] == "authenticated" for row in rows),
        "physical_printed_subset_inertia": None,
        "nonuniform_printed_subset_inertia": None,
        "purchased_internal_inertia": None,
        "whole_arm_inertia": None,
        "default_native_geometric_integration_error_bound": None,
        "continuous_surface_deviation_certified": False,
        "feature_history_rebuild_accepted": False,
        "fabrication_release": False,
        "components": [],
        "reference_uniform_solid_aggregate": None,
        "unresolved_instance_ids": sorted(
            row["instance_id"] for row in rows if row["status"] != "authenticated"
        ),
    }
    if not capture.get("complete_65_printed_coverage") or base["unresolved_instance_ids"]:
        return base
    if (
        capture["status"] != "complete_frame_authentication"
        or capture["errors"]
        or not capture["source_copy_bytes_unchanged"]
    ):
        raise ValueError("native capture did not complete preservation/measurement gates")
    components = []
    groups = {}
    for row in rows:
        if row["selection_id"] != expected[row["instance_id"]]:
            raise ValueError("installed instance bound to wrong source variant")
        variant = variants[row["selection_id"]]
        matrix = row["source_raw_to_master_mm"]
        probe.validate_rigid(matrix)
        derived = probe.product(row["ancestor_transform_mm"], row["source_raw_to_installed_raw_mm"])
        if matrix != derived:
            raise ValueError("world transform does not follow recorded ancestor chain")
        raw_delta = probe.product(
            row["installed_raw_placement_mm"],
            probe.inverse_rigid(variant["source_raw_placement_mm"]),
        )
        if raw_delta != row["source_raw_to_installed_raw_mm"]:
            raise ValueError("source/installed own placement delta changed")
        marker_result = probe.marker_check(
            variant["source_vertices_mm"], row["installed_vertices_mm"], raw_delta
        )
        recorded = row["marker_check"]
        if (
            type(recorded["all_ordered_vertices_checked"]) is not int
            or not isinstance(recorded["noncollinear_witness_indices"], list)
            or any(type(value) is not int for value in recorded["noncollinear_witness_indices"])
        ):
            raise ValueError("typed marker counts and witness indices required")
        float_keys = {"witness_cross_product_norm_mm2", "maximum_marker_error_mm"}
        if set(marker_result) != set(recorded) or any(
            not math.isclose(probe.finite(recorded[key]), value, rel_tol=1e-12, abs_tol=1e-15)
            if key in float_keys
            else recorded[key] != value
            for key, value in marker_result.items()
        ):
            raise ValueError("recorded marker check does not reproduce")
        geo = variant["cached_shape_properties"]["aggregate"]
        if len(geo["com_m"]) != 3 or [probe.finite(value) for value in geo["com_m"]] != [
            probe.finite(value) * 1e-3 for value in geo["com_mm"]
        ]:
            raise ValueError("geometric COM SI conversion changed")
        if geo["centroidal_geometric_inertia_m5"] != [
            [value * 1e-15 for value in line] for line in geo["centroidal_geometric_inertia_mm5"]
        ]:
            raise ValueError("geometric inertia SI conversion changed")
        probe.metric_check(geo, row["installed_raw_metrics"]["aggregate"], raw_delta)
        volume = geo["volume_m3"]
        if volume != geo["volume_mm3"] * 1e-9:
            raise ValueError("geometric volume SI conversion changed")
        tensor = [
            [value * density_kg_m3 for value in line]
            for line in geo["centroidal_geometric_inertia_m5"]
        ]
        source = MassProperties(
            volume * density_kg_m3,
            tuple(geo["com_m"]),
            tensor,
            row["selection_id"] + " raw BRep storage frame",
            "hash-pinned cached native geometric tensor times declared uniform-solid density",
        )
        installed = transform_mass_properties(
            source,
            [line[:3] for line in matrix[:3]],
            [matrix[i][3] / 1000 for i in range(3)],
            target_frame=FRAME,
            transform_evidence="native ordered vertices and actual placement-chain authentication",
        )
        components.append(installed)
        groups.setdefault(row["root_subassembly"], []).append(installed)
        base["components"].append(
            {
                "instance_id": row["instance_id"],
                "selection_id": row["selection_id"],
                "root_subassembly": row["root_subassembly"],
                "volume_m3": volume,
                "uniform_solid_mass_properties": asdict(installed),
            }
        )
    aggregate = aggregate_mass_properties(
        components,
        evidence=(
            "all 65 distinct installed printed copies; uniform-solid reference only; "
            "default native GProps uncertainty unquantified"
        ),
    )
    base.update(
        status="complete_conditional_printed_subset_only",
        installed_printed_volume_m3=math.fsum(item["volume_m3"] for item in base["components"]),
        reference_uniform_solid_aggregate=asdict(aggregate),
        subassembly_uniform_solid_aggregates={
            name: asdict(
                aggregate_mass_properties(
                    items, evidence="same conditional uniform-solid reference subset"
                )
            )
            for name, items in sorted(groups.items())
        },
    )
    return base


def build(project_root, capture_path, density_kg_m3=1240.0):
    root = Path(project_root).resolve()
    raw, capture = strict_json(capture_path)
    validate_capture(capture)
    paths = {
        "inspection.json": "cad/thor-baseline-inspection.json",
        "inventory.json": "cad/thor-mounted-geometry-v2.json",
        "mounted.json": "cad/thor-native-mounted-bounds-v1.json",
        "full-request.json": "print-planning/thor-full-print-export-inputs-v1.json",
        "full-native.json": "print-planning/thor-full-print-export-native-v1.json",
    }
    paths.update(
        {
            f"batch-{i:02}.json": (
                f"print-planning/thor-full-print-export-rawcapture-batch-{i:02}-v1.json"
            )
            for i in range(1, 7)
        }
    )
    if set(capture["input_sha256"]) != set(paths):
        raise ValueError("native evidence input binding set changed")
    inputs = {}
    for name, relative in paths.items():
        data, parsed = strict_json(root / "hardware" / relative)
        if hashlib.sha256(data).hexdigest() != capture["input_sha256"][name]:
            raise ValueError("stale native evidence input: " + name)
        inputs[name] = parsed
    original_pins = {
        Path(row["path"]).name: row["sha256"] for row in inputs["inspection.json"]["files"]
    }
    compatible_pins = dict(original_pins)
    compatible_pins["Art1Body.fcstd"] = (
        "142d754d3551352ffd2338d940cc3edecb9d272b2401f70aea9f89fea164c140"
    )
    if (
        capture["source_copy_sha256_before"] != compatible_pins
        or capture["original_copy_sha256_before"] != original_pins
    ):
        raise ValueError("native copy ledgers differ from authoritative source pins")
    publication = capture["publication_provenance"]
    native = dict(capture)
    native.pop("publication_provenance")
    native_raw = (json.dumps(native, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if hashlib.sha256(native_raw).hexdigest() != publication["actual_raw_capture_sha256"]:
        raise ValueError("published native fields differ from retained raw capture digest")
    receipt = publication["actual_launch_result"]
    if type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1:
        raise ValueError("unsupported typed actual launcher schema")
    if (
        not digest(receipt.get("request_sha256"))
        or not digest(publication.get("actual_launch_contract_sha256"))
        or receipt.get("contract_sha256") != publication["actual_launch_contract_sha256"]
    ):
        raise ValueError("actual launcher request/contract digest bindings disagree")
    if (
        type(receipt.get("timeout_s")) is not int
        or not 1 <= receipt["timeout_s"] <= 480
        or frame_module().finite(receipt["elapsed_seconds"]) > receipt["timeout_s"]
    ):
        raise ValueError("actual launcher timeout bounds invalid")
    if (
        frame_module().finite(receipt["elapsed_seconds"]) <= 0
        or type(receipt.get("free_bytes_after")) is not int
        or receipt["free_bytes_after"] < 50 * 1024**3
    ):
        raise ValueError("actual launcher duration/reserve gate failed")
    for key in (
        "native_process_launched",
        "original_source_unchanged",
        "originals_freecad-src_copies_unchanged",
        "compatible_source_unchanged",
        "source_copies_unchanged",
        "addons_unchanged",
        "all_snapshots_unchanged",
    ):
        if receipt.get(key) is not True:
            raise ValueError("actual launcher preservation gate failed")
    if (
        type(receipt.get("returncode")) is not int
        or receipt["returncode"] != 0
        or receipt["outcome"] != "process_completed"
        or receipt["status"] != capture["status"]
        or receipt["errors"] != []
    ):
        raise ValueError("actual native process receipt not successful")
    if (
        receipt.get("complete_65_printed_coverage") is not capture["complete_65_printed_coverage"]
        or type(receipt.get("authenticated_instance_count")) is not int
        or receipt["authenticated_instance_count"] != capture["authenticated_instance_count"]
    ):
        raise ValueError("actual launcher coverage summary disagrees")
    if (
        receipt["report_sha256"] != publication["actual_raw_capture_sha256"]
        or receipt["worker_sha256"] != capture["worker_sha256"]
        or receipt["executable_sha256"]
        != "1692e54224b48989974e8b91d3ac7a38d1d502d3db4dee1d4cf79ba91356e42d"
    ):
        raise ValueError("actual launcher code/runtime/report bindings disagree")
    if (
        publication["original_source_sha256_before"] != original_pins
        or receipt["original_source_sha256_after"] != original_pins
        or publication["compatible_source_sha256_before"] != compatible_pins
        or receipt["compatible_source_sha256_after"] != compatible_pins
    ):
        raise ValueError("actual parent source ledgers disagree")
    worker = root / "tools/probe_thor_printed_tensor_frames.py"
    if hashlib.sha256(worker.read_bytes()).hexdigest() != capture["worker_sha256"]:
        raise ValueError("current native worker differs from captured snapshot")
    prior = {
        row["selection_id"]: row
        for name, data in inputs.items()
        if name.startswith("batch-")
        for row in data["selections"]
    }
    for row in capture["variants"]:
        reference = prior[row["selection_id"]]
        if (
            row["cached_shape_properties"] != reference["cached_shape_properties"]
            or row["source_binding"] != reference["source_binding"]
        ):
            raise ValueError("new source geometry differs from pinned full47 native capture")
    mounted = {row["instance_id"]: row for row in inputs["mounted.json"]["instances"]}
    probe = frame_module()
    variants = {row["selection_id"]: row for row in capture["variants"]}
    for row in capture["instances"]:
        if row["status"] != "authenticated":
            continue
        reference = mounted[row["instance_id"]]
        if row["ancestor_transform_mm"] != reference["ancestor_transform_mm"]:
            raise ValueError("native ancestor chain differs from pinned mounted evidence")
        geo = variants[row["selection_id"]]["cached_shape_properties"]["aggregate"]
        world_com = [v / 1000 for v in probe.point(row["source_raw_to_master_mm"], geo["com_mm"])]
        if math.dist(world_com, reference["native_world_com_m"]) > 1e-9:
            raise ValueError("world COM differs from pinned mounted evidence")
    result = study(capture, inputs["full-native.json"], density_kg_m3)
    result["native_capture_sha256"] = hashlib.sha256(raw).hexdigest()
    result["native_capture_input_sha256"] = capture["input_sha256"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--uniform-solid-density-kg-m3", type=float, default=1240.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.project_root, args.capture, args.uniform_solid_density_kg_m3)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
