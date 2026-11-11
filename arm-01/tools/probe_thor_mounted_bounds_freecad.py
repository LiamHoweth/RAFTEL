"""Capture copied saved-zero installed shape bounds in an isolated FreeCAD process.

This is a native numerical bounding/coordinate diagnostic, not collision
clearance, a conservative physical envelope or procedural-history acceptance.
The existing installed-leaf walker owns identity and ancestor traversal.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import itertools
import json
import math
import os
import shutil
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

FLAG = "RAFTEL_RUN_THOR_MOUNTED_BOUNDS"
CAD_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
INSPECTION_SHA256 = "f76f1e2e1dc4c9f58b938a748502f89f20064dd373014c37ab1f06ba01412631"
INVENTORY_SHA256 = "64dbcf86439afffd11f63181259cba048008a3bedf103997603a24d23b49fa3e"
STATIC_ART1_SHA256 = "142d754d3551352ffd2338d940cc3edecb9d272b2401f70aea9f89fea164c140"
AUDIT_HELPER_SHA256 = "224c6b45aa7d32aaee54d5de7b17f5446b6df865c6870fe5de5fdd9bd2c58c10"
EXTRACTOR_SHA256 = "be4ecc712bc385fec2c6678f10c20148283687b7f387bf88e2f33ec1657018e3"
MIN_FREE_BYTES = 50 * 1024**3 + 128 * 1024**2
MODULE_PINS = {
    "FastenersCmd": (
        "fasteners",
        "89f3ef5d38bee30fed839168741c004e1a86cf88dc9310883a0b69e1f83d0abf",
    ),
    "freecad.gears.features": (
        "gears",
        "f4281f0b56e7f5f514b4f185ae8bd5718e34f82902680c63e0ecfbf9a3d45eb7",
    ),
    "pygears.involute_tooth": (
        "gears",
        "e0f71a5023da057bff5aa6f2443e6bd993e4bb911dbf045e6017aab9d109b6ce",
    ),
    "pygears.bevel_tooth": (
        "gears",
        "0785043da40bac5fb8ade84c1736015eae53dad775a29e6adb754c721fa1244e",
    ),
}
FIXTURE_EXPECTED_MM = {
    "direct_child": [[96, 30, 0], [100, 32, 6]],
    "link_false": [[96, 20, 0], [100, 22, 6]],
    "link_true": [[100, 30, 0], [106, 32, 4]],
    "group_link_false": [[96, 30, 0], [100, 32, 6]],
    "group_link_true": [[60, 30, 0], [66, 32, 4]],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_disk_reserve(root: Path) -> int:
    free = shutil.disk_usage(root).free
    if free < MIN_FREE_BYTES:
        raise ValueError("native capture requires the 50 GiB reserve plus scratch budget")
    return free


def strict_json(path: Path, expected_sha256: str | None = None) -> dict:
    raw = path.read_bytes()
    if len(raw) > 8_388_608:
        raise ValueError("JSON input exceeds byte bound")
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("pinned JSON bytes changed")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite JSON number")
        return parsed

    def invalid(value):
        raise ValueError("nonfinite JSON constant")

    value = json.loads(raw, object_pairs_hook=unique, parse_float=number, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("file name must be a relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("file name must be a relative POSIX path")
    return value


def pinned_inputs(inspection_path: Path, inventory_path: Path) -> tuple[dict, set[str]]:
    inspection = strict_json(inspection_path, INSPECTION_SHA256)
    inventory = strict_json(inventory_path, INVENTORY_SHA256)
    sources = {Path(row["path"]).name: row["sha256"] for row in inspection["files"]}
    if len(sources) != 57 or inspection["revision"] != CAD_REVISION:
        raise ValueError("unsupported source inspection")
    sources["Art1Body.fcstd"] = STATIC_ART1_SHA256
    identifiers = {row["instance_id"] for row in inventory["mounted_bodies"]}
    if len(identifiers) != 518 or inventory["instance_count"] != 518:
        raise ValueError("unsupported installed inventory")
    return sources, identifiers


def verify_files(root: Path, expected: dict) -> dict:
    actual = {}
    for name, digest in expected.items():
        name = safe_relative(name)
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("source path escaped its root")
        actual[name] = sha(path)
        if actual[name] != digest:
            raise ValueError(f"source bytes changed: {name}")
    return actual


def bounds_values(box) -> list[list[float]]:
    result = [[box.XMin, box.YMin, box.ZMin], [box.XMax, box.YMax, box.ZMax]]
    if any(not math.isfinite(v) for row in result for v in row) or any(
        result[0][i] > result[1][i] for i in range(3)
    ):
        raise ValueError("bounds must be finite ordered extrema")
    return result


def bound_corners(bounds) -> list[list[float]]:
    if len(bounds) != 2 or any(len(row) != 3 for row in bounds):
        raise ValueError("expected two 3D extrema")
    if any(not math.isfinite(v) for row in bounds for v in row) or any(
        bounds[0][i] > bounds[1][i] for i in range(3)
    ):
        raise ValueError("bounds must be finite ordered extrema")
    return [list(point) for point in itertools.product(*zip(bounds[0], bounds[1], strict=True))]


def corner_bounds(points) -> list[list[float]]:
    if not points or any(len(row) != 3 or any(not math.isfinite(v) for v in row) for row in points):
        raise ValueError("expected finite 3D points")
    return [
        [min(p[i] for p in points) for i in range(3)],
        [max(p[i] for p in points) for i in range(3)],
    ]


def placed_copy(shape, ancestor_matrix, App):
    """Premultiply ancestors only: the raw Shape already includes own Placement."""
    copied = shape.copy()
    matrix = App.Matrix(*[value for row in ancestor_matrix for value in row])
    copied.Placement = App.Placement(matrix).multiply(shape.Placement)
    return copied


def close_created_documents(App, previous: set[str]) -> set[str]:
    for name in set(App.listDocuments()) - previous:
        App.closeDocument(name)
    return set(App.listDocuments())


def native_fixture(App, Part, helper) -> dict:
    previous = set(App.listDocuments())
    document = App.newDocument("RAFTELMountedBoundsFixture")
    try:
        model = document.addObject("App::Part", "Model")
        model.Placement.Base = App.Vector(100, 0, 0)
        parent = document.addObject("App::Part", "Parent")
        model.addObject(parent)
        parent.Placement = App.Placement(
            App.Vector(0, 20, 0), App.Rotation(App.Vector(0, 0, 1), 90)
        )
        child = document.addObject("Part::Feature", "Child")
        child.Shape = Part.makeBox(2, 4, 6)
        child.Placement.Base = App.Vector(10, 0, 0)
        parent.addObject(child)
        source = document.addObject("Part::Feature", "Source")
        source.Shape = Part.makeBox(2, 4, 6)
        source.Placement = App.Placement(
            App.Vector(10, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90)
        )
        group_source = document.addObject("App::Part", "GroupSource")
        group_source.Placement = App.Placement(
            App.Vector(0, 40, 0), App.Rotation(App.Vector(1, 0, 0), 90)
        )
        group_child = document.addObject("Part::Feature", "GroupChild")
        group_child.Shape = Part.makeBox(2, 4, 6)
        group_child.Placement.Base = App.Vector(10, 0, 0)
        group_source.addObject(group_child)
        targets = [("direct_child", child, model.Placement.multiply(parent.Placement))]
        for group, target in ((False, source), (True, group_source)):
            for flag in (False, True):
                name = ("group_link_" if group else "link_") + str(flag).lower()
                link = document.addObject("App::Link", name)
                link.setLink(target)
                link.LinkTransform = flag
                link.LinkPlacement = App.Placement(
                    App.Vector(0, 20, 0), App.Rotation(App.Vector(0, 0, 1), 90)
                )
                model.addObject(link)
                targets.append((name, link, model.Placement))
        document.recompute()
        records = []
        for name, obj, ancestors in targets:
            raw = obj.Shape
            world = placed_copy(raw, helper._placement(ancestors)["matrix"], App)
            bounds = bounds_values(world.optimalBoundingBox(False, True))
            expected = FIXTURE_EXPECTED_MM[name]
            residual = max(abs(bounds[i][j] - expected[i][j]) for i in range(2) for j in range(3))
            records.append(
                {
                    "name": name,
                    "expected_world_bounds_mm": expected,
                    "observed_world_optimal_bounds_mm": bounds,
                    "maximum_extremum_error_mm": residual,
                    "raw_shape_placement": helper._placement(raw.Placement),
                    "ancestor_transform_mm": helper._placement(ancestors)["matrix"],
                }
            )
            if residual > 2e-6:
                raise ValueError(f"synthetic installed-shape bounds contract failed: {name}")
        return {
            "passed": True,
            "cases": records,
            "tolerance_mm": 2e-6,
            "tolerance_interpretation": "numerical fixture policy, not manufacturing tolerance",
        }
    finally:
        close_created_documents(App, previous)


def load_snapshot(path: Path, expected: str, name: str):
    if sha(path) != expected:
        raise ValueError("helper snapshot bytes changed")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_capture() -> dict:
    if os.environ.get(FLAG) != "1":
        raise ValueError("native capture requires explicit opt-in")
    if os.environ.get("RAFTEL_RUN_FREECAD_AUDIT") == "1":
        raise ValueError("generic audit flag must be unset when importing its helper")
    root = Path(os.environ["RAFTEL_MOUNTED_BOUNDS_RUN_ROOT"]).resolve()
    free_before = require_disk_reserve(root)
    request = strict_json(root / "request.json")
    if (
        set(request)
        != {
            "schema_version",
            "evidence_class",
            "cad_revision",
            "helper_sha256",
            "extractor_sha256",
            "worker_sha256",
            "addon_roots",
        }
        or request["schema_version"] != 1
        or type(request["schema_version"]) is not int
        or request["evidence_class"] != "native_saved_zero_mounted_bounds_request"
        or request["cad_revision"] != CAD_REVISION
    ):
        raise ValueError("unsupported mounted bounds request")
    if sha(Path(__file__)) != request["worker_sha256"]:
        raise ValueError("executed worker bytes changed")
    if (
        request["helper_sha256"] != AUDIT_HELPER_SHA256
        or request["extractor_sha256"] != EXTRACTOR_SHA256
    ):
        raise ValueError("unsupported helper/extractor revision")
    helper = load_snapshot(
        root / "scripts/audit_freecad_assembly.py",
        request["helper_sha256"],
        "mounted_bounds_audit_helper",
    )
    extractor = load_snapshot(
        root / "scripts/extract_thor_geometry.py",
        request["extractor_sha256"],
        "mounted_bounds_extractor",
    )
    sources, expected_ids = pinned_inputs(
        root / "inputs/inspection.json", root / "inputs/inventory.json"
    )
    source_root = root / "source"
    before = verify_files(source_root, sources)
    writer = helper.ReportWriter(root / "probe.json")
    report = {
        "schema_version": 1,
        "evidence_class": "native_saved_zero_installed_shape_bounds",
        "status": "starting",
        "cad_revision": CAD_REVISION,
        "inspection_sha256": INSPECTION_SHA256,
        "inventory_sha256": INVENTORY_SHA256,
        "worker_sha256": request["worker_sha256"],
        "free_bytes_before_capture": free_before,
        "helper_sha256": request["helper_sha256"],
        "extractor_sha256": request["extractor_sha256"],
        "source_copy_sha256_before": before,
        "errors": [],
        "instances": [],
        "frame": "native master document saved-zero frame; complete Model ancestor chain; metres",
        "shape_history_rebuilt": False,
        "cad_saved": False,
        "physical_enclosure_verified": False,
        "collision_clearance_accepted": False,
        "fabrication_release": False,
    }
    App = None
    previous = None
    try:
        import FreeCAD as App
        import Part

        previous = set(App.listDocuments())
        report["runtime_isolation"] = helper._runtime_isolation(App, root)
        report["open_document_count_before"] = len(previous)
        report["freecad_version"] = list(App.Version())
        origins = {}
        if set(request["addon_roots"]) != {"fasteners", "gears"}:
            raise ValueError("expected two pinned addon roots")
        for name, (kind, digest) in MODULE_PINS.items():
            module = importlib.import_module(name)
            path = Path(module.__file__).resolve()
            if (
                not path.is_relative_to(Path(request["addon_roots"][kind]).resolve())
                or sha(path) != digest
            ):
                raise ValueError(f"addon origin/pin mismatch: {name}")
            origins[name] = {"path": str(path), "sha256": digest}
        report["addon_module_origins"] = origins
        report["synthetic_coordinate_fixture"] = native_fixture(App, Part, helper)
        writer(report)
        master = App.openDocument(str(source_root / "Assembly.FCStd"))
        report["master_model_saved_placement"] = helper._placement(
            master.getObject("Model").Placement
        )
        metadata = {
            "restore_completed": True,
            "master_document": master.Name,
            "status": "restored_cached",
            "shape_validation_requested": False,
            "documents": [],
        }
        objects = {}
        for document in list(App.listDocuments().values()):
            records = []
            for obj in document.Objects:
                reference = helper._reference(obj)
                objects[reference] = obj
                record = helper._object_metadata(obj)
                if helper._is_terminal(obj):
                    helper._shape_metadata(obj, record, False)
                records.append(record)
            metadata["documents"].append({"name": document.Name, "objects": records})
            report["metadata_document_count"] = len(metadata["documents"])
            writer(report)
        inventory = extractor.installed_leaf_instances(metadata)
        ids = {row["instance_id"] for row in inventory["mounted_bodies"]}
        report["walker_errors"] = inventory["errors"]
        report["missing_object_records"] = inventory["missing_object_records"]
        report["observed_instance_count"] = len(ids)
        report["expected_instance_count"] = len(expected_ids)
        report["missing_instance_ids"] = sorted(expected_ids - ids)
        report["unexpected_instance_ids"] = sorted(ids - expected_ids)
        report["complete_identity_coverage"] = (
            ids == expected_ids
            and not inventory["errors"]
            and not inventory["missing_object_records"]
        )
        if not report["complete_identity_coverage"]:
            raise ValueError("native leaf identity coverage differs from the pinned inventory")
        for leaf in inventory["mounted_bodies"]:
            obj = objects[leaf["object_reference"]]
            row = {
                key: leaf[key]
                for key in (
                    "instance_id",
                    "object_reference",
                    "root_subassembly",
                    "native_state",
                    "ancestor_transform_mm",
                    "zero_world_com_m",
                    "geometry_derivation",
                )
            }
            row["enclosure_verified"] = False
            try:
                raw = obj.Shape
                if raw.isNull():
                    raise ValueError("leaf raw Shape is null")
                raw_before = helper._placement(raw.Placement)
                world = placed_copy(raw, leaf["ancestor_transform_mm"], App)
                raw_optimal = bounds_values(raw.optimalBoundingBox(False, True))
                transformed_box = corner_bounds(
                    [
                        extractor._point(leaf["ancestor_transform_mm"], point)
                        for point in bound_corners(raw_optimal)
                    ]
                )
                world_info = {}
                helper._shape_metadata(SimpleNamespace(Shape=world), world_info, False)
                world_com = [value / 1000 for value in world_info["shape_center_of_mass_mm"]]
                com_error = math.dist(world_com, leaf["zero_world_com_m"])
                row.update(
                    {
                        "raw_shape_placement": raw_before,
                        "object_metadata": helper._object_metadata(obj),
                        "copied_world_shape_placement": helper._placement(world.Placement),
                        "raw_default_bounds_mm": bounds_values(raw.BoundBox),
                        "raw_optimal_bounds_mm": raw_optimal,
                        "transformed_raw_optimal_box_aabb_m": transformed_box,
                        "world_default_bounds_m": [
                            [v / 1000 for v in point] for point in bounds_values(world.BoundBox)
                        ],
                        "world_optimal_bounds_m": [
                            [v / 1000 for v in point]
                            for point in bounds_values(world.optimalBoundingBox(False, True))
                        ],
                        "native_world_com_m": world_com,
                        "world_com_crosscheck_error_m": com_error,
                        "raw_shape_placement_unchanged": raw_before
                        == helper._placement(obj.Shape.Placement),
                        "status": "captured_numerical_bounds",
                    }
                )
                if com_error > 1e-9 or not row["raw_shape_placement_unchanged"]:
                    raise ValueError("copied native shape frame/immutability crosscheck failed")
            except Exception as error:
                row["status"] = "bounds_unavailable"
                row["error"] = {"type": type(error).__name__, "message": str(error)}
            report["instances"].append(row)
            if len(report["instances"]) % 16 == 0:
                writer(report)
        report["captured_bounds_count"] = sum(
            row["status"] == "captured_numerical_bounds" for row in report["instances"]
        )
        report["bounds_gap_count"] = len(report["instances"]) - report["captured_bounds_count"]
        report["final_state_counts"] = {}
        for document in App.listDocuments().values():
            for obj in document.Objects:
                for token in obj.State:
                    report["final_state_counts"][token] = (
                        report["final_state_counts"].get(token, 0) + 1
                    )
        report["status"] = (
            "complete_numerical_bounds_capture"
            if not report["bounds_gap_count"]
            else "complete_bounds_capture_with_gaps"
        )
    except Exception as error:
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
        report["status"] = "failed_bounds_capture"
    finally:
        if App is not None and previous is not None:
            report["preexisting_documents_preserved"] = (
                close_created_documents(App, previous) == previous
            )
            report["open_document_count_after"] = len(App.listDocuments())
        try:
            after = verify_files(source_root, sources)
            report["source_copy_sha256_after"] = after
            report["source_copy_bytes_unchanged"] = after == before
        except (OSError, ValueError) as error:
            report["source_copy_bytes_unchanged"] = False
            report["errors"].append({"type": type(error).__name__, "message": str(error)})
        if (
            not report["source_copy_bytes_unchanged"]
            or report.get("preexisting_documents_preserved", True) is not True
        ):
            report["status"] = "failed_preservation_guard"
        writer(report)
    return report


if __name__ == "__main__" or os.environ.get(FLAG) == "1":
    native_capture()
