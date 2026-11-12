"""Authenticate saved-BRep printed tensor frames against native installed copies.

Cached geometry only: no recompute, CAD save, material measurement or release.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path

FLAG = "RAFTEL_RUN_THOR_PRINTED_TENSOR_FRAMES"


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("expected finite nonboolean number")
    return float(value)


def contained_file(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError("input must be a regular contained file without symlink")
    return path


def strict_request(path):
    with path.open("rb") as stream:
        raw = stream.read(1048577)
    if len(raw) > 1048576:
        raise ValueError("request exceeds byte bound")

    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("duplicate request key")
            data[key] = value
        return data

    def reject(value):
        raise ValueError("nonfinite request value")

    data = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique,
        parse_float=lambda value: finite(float(value)),
        parse_constant=reject,
    )
    if not isinstance(data, dict):
        raise ValueError("request root must be object")
    return data


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, digest, name):
    if sha(path) != digest:
        raise ValueError("snapshot hash mismatch")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def product(a, b):
    return [[math.fsum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def inverse_rigid(a):
    validate_rigid(a)
    r = [[a[j][i] for j in range(3)] for i in range(3)]
    return [r[i] + [-math.fsum(r[i][j] * a[j][3] for j in range(3))] for i in range(3)] + [
        [0, 0, 0, 1]
    ]


def validate_rigid(a):
    if (
        len(a) != 4
        or any(len(row) != 4 for row in a)
        or any(not math.isfinite(finite(x)) for row in a for x in row)
    ):
        raise ValueError("expected finite rigid 4x4 matrix")
    if any(abs(a[3][j] - float(j == 3)) > 1e-12 for j in range(4)):
        raise ValueError("invalid homogeneous row")
    r = [row[:3] for row in a[:3]]
    determinant = sum(
        r[0][j] * (r[1][(j + 1) % 3] * r[2][(j + 2) % 3] - r[1][(j + 2) % 3] * r[2][(j + 1) % 3])
        for j in range(3)
    )
    if abs(determinant - 1) > 1e-10 or any(
        abs(sum(r[i][k] * r[j][k] for k in range(3)) - float(i == j)) > 1e-10
        for i in range(3)
        for j in range(3)
    ):
        raise ValueError("matrix must contain proper rotation")


def point(a, p):
    return [math.fsum(a[i][j] * p[j] for j in range(3)) + a[i][3] for i in range(3)]


def marker_check(source, installed, matrix, tolerance_mm=1e-7):
    validate_rigid(matrix)
    if finite(tolerance_mm) <= 0:
        raise ValueError("marker tolerance must be positive finite")
    if len(source) != len(installed) or len(source) < 3 or len(source) > 100000:
        raise ValueError("ordered vertex coverage mismatch or bound")
    if any(len(p) != 3 or any(not math.isfinite(finite(v)) for v in p) for p in source + installed):
        raise ValueError("invalid vertex")
    origin = source[0]
    distant = max(range(1, len(source)), key=lambda i: math.dist(origin, source[i]))
    v = [source[distant][i] - origin[i] for i in range(3)]

    def area(index):
        w = [source[index][i] - origin[i] for i in range(3)]
        return math.hypot(
            *(v[(i + 1) % 3] * w[(i + 2) % 3] - v[(i + 2) % 3] * w[(i + 1) % 3] for i in range(3))
        )

    third = max(range(len(source)), key=area)
    if area(third) <= 1e-10:
        raise ValueError("markers do not span a plane")
    maximum = max(math.dist(point(matrix, a), b) for a, b in zip(source, installed, strict=True))
    if maximum > tolerance_mm:
        raise ValueError(f"ordered native markers disagree: {maximum} mm")
    return {
        "all_ordered_vertices_checked": len(source),
        "noncollinear_witness_indices": [0, distant, third],
        "witness_cross_product_norm_mm2": area(third),
        "maximum_marker_error_mm": maximum,
        "acceptance_tolerance_mm": tolerance_mm,
    }


def metric_check(source, installed, matrix):
    validate_rigid(matrix)
    for metrics in (source, installed):
        if finite(metrics["volume_mm3"]) <= 0:
            raise ValueError("positive finite native volume required")
        if len(metrics["com_mm"]) != 3 or len(metrics["centroidal_geometric_inertia_mm5"]) != 3:
            raise ValueError("native metric dimensions changed")
        for value in metrics["com_mm"]:
            finite(value)
        for row in metrics["centroidal_geometric_inertia_mm5"]:
            if len(row) != 3:
                raise ValueError("native tensor dimensions changed")
            for value in row:
                finite(value)
    rotation = [row[:3] for row in matrix[:3]]
    volume_error = abs(source["volume_mm3"] - installed["volume_mm3"]) / source["volume_mm3"]
    com_error = math.dist(point(matrix, source["com_mm"]), installed["com_mm"])
    tensor = source["centroidal_geometric_inertia_mm5"]
    predicted = [
        [
            math.fsum(
                rotation[i][a] * tensor[a][b] * rotation[j][b] for a in range(3) for b in range(3)
            )
            for j in range(3)
        ]
        for i in range(3)
    ]
    scale = max(abs(x) for row in predicted for x in row)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("native geometric tensor must have positive finite scale")
    tensor_error = (
        max(
            abs(predicted[i][j] - installed["centroidal_geometric_inertia_mm5"][i][j])
            for i in range(3)
            for j in range(3)
        )
        / scale
    )
    if (
        any(not math.isfinite(v) for v in (volume_error, com_error, tensor_error))
        or volume_error > 1e-9
        or com_error > 1e-7
        or tensor_error > 1e-8
    ):
        raise ValueError(
            "native volume/COM/tensor covariance disagreement; "
            f"relative_V={volume_error}, COM_mm={com_error}, relative_J={tensor_error}; "
            "default numerical GProps are not certified frame-covariant integrals"
        )
    return {
        "relative_volume_error": volume_error,
        "com_error_mm": com_error,
        "relative_tensor_covariance_error": tensor_error,
    }


def capture():
    if os.environ.get(FLAG) != "1":
        raise ValueError("explicit printed tensor capture opt-in required")
    if any(
        os.environ.get(key) == "1"
        for key in (
            "RAFTEL_RUN_FREECAD_AUDIT",
            "RAFTEL_RUN_THOR_MOUNTED_BOUNDS",
            "RAFTEL_RUN_THOR_SOLID_PROPERTIES",
        )
    ):
        raise ValueError("conflicting capture entry flag")
    raw_root = Path(os.environ["RAFTEL_PRINTED_TENSOR_ROOT"])
    root = raw_root.resolve()
    if raw_root.is_symlink() or not root.is_dir():
        raise ValueError("capture root must be regular task directory")
    request = strict_request(contained_file(root, "request.json"))
    if (
        set(request)
        != {
            "schema_version",
            "worker_sha256",
            "scripts",
            "inputs",
            "addon_roots",
            "expected_runtime_paths",
        }
        or type(request["schema_version"]) is not int
        or request["schema_version"] != 1
    ):
        raise ValueError("unsupported native request schema")
    if set(request["scripts"]) != {"mounted.py", "audit.py", "extractor.py", "solid.py"}:
        raise ValueError("unsupported helper snapshot set")
    for name in request["scripts"]:
        contained_file(root, "scripts/" + name)
    for name in request["inputs"]:
        if "/" in name or "\\" in name or ":" in name:
            raise ValueError("input basename required")
        contained_file(root, "inputs/" + name)
    if sha(__file__) != request["worker_sha256"]:
        raise ValueError("worker snapshot changed")
    if Path(__file__).resolve() != root / "scripts/worker.py":
        raise ValueError("executed worker must be the private retained snapshot")
    scripts = request["scripts"]
    mounted = load(root / "scripts/mounted.py", scripts["mounted.py"], "printed_mounted")
    mounted.require_disk_reserve(root)
    helper = load(root / "scripts/audit.py", scripts["audit.py"], "printed_audit")
    extractor = load(root / "scripts/extractor.py", scripts["extractor.py"], "printed_extractor")
    solid = load(root / "scripts/solid.py", scripts["solid.py"], "printed_solid")
    inputs = {
        name: mounted.strict_json(root / "inputs" / name, digest)
        for name, digest in request["inputs"].items()
    }
    sources, expected_ids = mounted.pinned_inputs(
        root / "inputs/inspection.json", root / "inputs/inventory.json"
    )
    before = mounted.verify_files(root / "source", sources)
    original_expected = {
        Path(row["path"]).name: row["sha256"] for row in inputs["inspection.json"]["files"]
    }
    originals_before = mounted.verify_files(root / "originals/freecad-src", original_expected)
    variants = inputs["full-native.json"]["variants"]
    descriptors = {row["selection_id"]: row for row in inputs["full-request.json"]["selections"]}
    prior_metrics = {
        row["selection_id"]: row["cached_shape_properties"]
        for name, data in inputs.items()
        if name.startswith("batch-")
        for row in data["selections"]
    }
    wanted = {instance: row for row in variants for instance in row["installed_instance_ids"]}
    if (
        len(variants) != 47
        or len(wanted) != 65
        or len(descriptors) != 47
        or len(prior_metrics) != 47
    ):
        raise ValueError("expected 47 variants and 65 unique installed prints")
    if sum(len(row["installed_instance_ids"]) for row in variants) != 65:
        raise ValueError("installed printed identities must be unique")
    if any(len(row["installed_instance_ids"]) != row["quantity_required"] for row in variants):
        raise ValueError("printed variant quantities disagree")
    writer = helper.ReportWriter(root / "probe.json")
    report = {
        "schema_version": 1,
        "status": "starting",
        "evidence_class": "native_cached_printed_tensor_frame_authentication",
        "worker_sha256": request["worker_sha256"],
        "input_sha256": request["inputs"],
        "script_sha256": scripts,
        "source_copy_sha256_before": before,
        "original_copy_sha256_before": originals_before,
        "errors": [],
        "variants": [],
        "instances": [],
        "source_assembly_recomputed": False,
        "synthetic_coordinate_fixture_recomputed": True,
        "cad_saved": False,
        "physical_inertia": None,
        "whole_arm_inertia": None,
        "native_geometric_integration_uncertainty_quantified": False,
    }
    App = None
    previous = None
    try:
        import FreeCAD as App
        import Part

        previous = set(App.listDocuments())
        report["runtime_isolation"] = helper._runtime_isolation(App, root)
        expected_paths = request["expected_runtime_paths"]
        actual_paths = report["runtime_isolation"]["actual_paths"]
        if set(expected_paths) != set(actual_paths):
            raise ValueError("expected all five dedicated runtime paths")
        if any(
            Path(actual_paths[k]).resolve() != Path(v).resolve() for k, v in expected_paths.items()
        ):
            raise ValueError("actual runtime path differs from dedicated expected path")
        report["expected_runtime_paths"] = expected_paths
        report["open_document_count_before"] = len(previous)
        report["freecad_version"] = list(App.Version())
        report["opencascade_version"] = Part.OCC_VERSION
        origins = {}
        for name, (kind, digest) in mounted.MODULE_PINS.items():
            path = Path(importlib.import_module(name).__file__).resolve()
            if (
                not path.is_relative_to(Path(request["addon_roots"][kind]).resolve())
                or sha(path) != digest
            ):
                raise ValueError("addon origin/pin mismatch")
            origins[name] = {"path": str(path), "sha256": digest}
        report["addon_module_origins"] = origins
        report["synthetic_coordinate_fixture"] = mounted.native_fixture(App, Part, helper)
        master = App.openDocument(str(root / "source/Assembly.FCStd"))
        report["loaded_document_sources"] = []
        for document in App.listDocuments().values():
            path = Path(document.FileName).resolve()
            if (
                not path.is_relative_to(root / "source")
                or path.name not in sources
                or sha(path) != sources[path.name]
            ):
                raise ValueError("restored external document escaped pinned private source copy")
            report["loaded_document_sources"].append(
                {"document": document.Name, "path": str(path), "sha256": sha(path)}
            )
        metadata = {"restore_completed": True, "master_document": master.Name, "documents": []}
        objects = {}
        for document in App.listDocuments().values():
            records = []
            for obj in document.Objects:
                objects[helper._reference(obj)] = obj
                row = helper._object_metadata(obj)
                if helper._is_terminal(obj):
                    helper._shape_metadata(obj, row, False)
                records.append(row)
            metadata["documents"].append({"name": document.Name, "objects": records})
        inventory = extractor.installed_leaf_instances(metadata)
        leaves = {row["instance_id"]: row for row in inventory["mounted_bodies"]}
        if (
            set(leaves) != expected_ids
            or inventory["errors"]
            or inventory["missing_object_records"]
        ):
            raise ValueError("518 leaf identity coverage changed")
        report["installed_leaf_count"] = len(leaves)
        mounted_reference = {row["instance_id"]: row for row in inputs["mounted.json"]["instances"]}
        for variant in variants:
            descriptor = descriptors[variant["selection_id"]]
            raw, binding = solid.read_selected_brep(root / "originals", descriptor)
            brep = root / (variant["selection_id"] + ".brep")
            with brep.open("xb") as stream:
                stream.write(raw)
            source = Part.Shape()
            source.read(str(brep))
            metrics = solid._native_metrics(source)
            if metrics != prior_metrics[variant["selection_id"]]:
                raise ValueError("source native metrics differ from preserved full47 capture")
            source_matrix = helper._placement(source.Placement)["matrix"]
            source_vertices = [list(v.Point) for v in source.Vertexes]
            source_counts = [
                len(getattr(source, attr)) for attr in ("Vertexes", "Edges", "Faces", "Solids")
            ]
            variant_record = {
                "selection_id": variant["selection_id"],
                "asset_id": variant["asset_id"],
                "geometry_variant": variant["geometry_variant"],
                "source_binding": binding,
                "source_raw_placement_mm": source_matrix,
                "source_vertices_mm": source_vertices,
                "topology_counts_vertices_edges_faces_solids": source_counts,
                "cached_shape_properties": metrics,
            }
            report["variants"].append(variant_record)
            for instance_id in variant["installed_instance_ids"]:
                leaf = leaves[instance_id]
                row = {
                    "instance_id": instance_id,
                    "selection_id": variant["selection_id"],
                    "root_subassembly": leaf["root_subassembly"],
                    "status": "unverified",
                }
                try:
                    obj = objects[leaf["object_reference"]]
                    objmeta = helper._object_metadata(obj)
                    source_reference = (
                        Path(descriptor["source_file"]).stem + "::" + descriptor["object_name"]
                    )
                    if (
                        leaf["object_reference"] != source_reference
                        and objmeta.get("linked_object_direct") != source_reference
                    ):
                        raise ValueError(
                            "installed object/link does not identify selected source asset"
                        )
                    installed = obj.Shape
                    installed_matrix = helper._placement(installed.Placement)["matrix"]
                    raw_transform = product(installed_matrix, inverse_rigid(source_matrix))
                    world_transform = product(leaf["ancestor_transform_mm"], raw_transform)
                    validate_rigid(world_transform)
                    counts = [
                        len(getattr(installed, attr))
                        for attr in ("Vertexes", "Edges", "Faces", "Solids")
                    ]
                    if counts != source_counts:
                        raise ValueError("native topology counts changed")
                    vertices = [list(v.Point) for v in installed.Vertexes]
                    markers = marker_check(source_vertices, vertices, raw_transform)
                    native_metrics = solid._native_metrics(installed)
                    row.update(
                        object_reference=leaf["object_reference"],
                        object_metadata=objmeta,
                        ancestor_transform_mm=leaf["ancestor_transform_mm"],
                        installed_raw_placement_mm=installed_matrix,
                        source_raw_to_installed_raw_mm=raw_transform,
                        source_raw_to_master_mm=world_transform,
                        installed_vertices_mm=vertices,
                        marker_check=markers,
                        installed_raw_metrics=native_metrics,
                    )
                    covariance = metric_check(
                        metrics["aggregate"], native_metrics["aggregate"], raw_transform
                    )
                    if (
                        leaf["ancestor_transform_mm"]
                        != mounted_reference[instance_id]["ancestor_transform_mm"]
                    ):
                        raise ValueError("actual ancestors differ from pinned mounted capture")
                    world_com = [
                        v / 1000 for v in point(world_transform, metrics["aggregate"]["com_mm"])
                    ]
                    world_com_error = math.dist(
                        world_com, mounted_reference[instance_id]["native_world_com_m"]
                    )
                    if world_com_error > 1e-9:
                        raise ValueError("world COM differs from prior mounted capture")
                    row.update(
                        status="authenticated",
                        object_reference=leaf["object_reference"],
                        object_metadata=objmeta,
                        ancestor_transform_mm=leaf["ancestor_transform_mm"],
                        installed_raw_placement_mm=installed_matrix,
                        source_raw_to_installed_raw_mm=raw_transform,
                        source_raw_to_master_mm=world_transform,
                        installed_vertices_mm=vertices,
                        marker_check=markers,
                        metric_crosscheck=covariance,
                        installed_raw_metrics=native_metrics,
                        prior_mounted_world_com_error_m=world_com_error,
                    )
                except Exception as error:
                    row["error"] = {"type": type(error).__name__, "message": str(error)}
                report["instances"].append(row)
            writer(report)
        count = sum(row["status"] == "authenticated" for row in report["instances"])
        report["authenticated_instance_count"] = count
        report["complete_65_printed_coverage"] = count == 65 and {
            row["instance_id"] for row in report["instances"]
        } == set(wanted)
        report["status"] = (
            "complete_frame_authentication"
            if report["complete_65_printed_coverage"]
            else "partial_frame_authentication"
        )
        report["final_state_counts"] = {}
        for document in App.listDocuments().values():
            for obj in document.Objects:
                for token in obj.State:
                    report["final_state_counts"][token] = (
                        report["final_state_counts"].get(token, 0) + 1
                    )
    except Exception as error:
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
        report["status"] = "failed_frame_authentication"
    finally:
        if App is not None and previous is not None:
            report["preexisting_documents_preserved"] = (
                mounted.close_created_documents(App, previous) == previous
            )
            report["open_document_count_after"] = len(App.listDocuments())
        try:
            report["source_copy_sha256_after"] = mounted.verify_files(root / "source", sources)
            report["original_copy_sha256_after"] = mounted.verify_files(
                root / "originals/freecad-src", original_expected
            )
            report["source_copy_bytes_unchanged"] = (
                before == report["source_copy_sha256_after"]
                and originals_before == report["original_copy_sha256_after"]
            )
        except (ValueError, OSError) as error:
            report["source_copy_bytes_unchanged"] = False
            report["errors"].append({"type": type(error).__name__, "message": str(error)})
        if (
            not report["source_copy_bytes_unchanged"]
            or not report.get("preexisting_documents_preserved", False)
            or report.get("open_document_count_after") != 0
        ):
            report["status"] = "failed_preservation_guard"
            report["complete_65_printed_coverage"] = False
        report["free_bytes_after_capture"] = mounted.require_disk_reserve(root)
        writer(report)
    return report


if __name__ == "__main__" or os.environ.get(FLAG) == "1":
    capture()
