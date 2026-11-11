"""Worker-only cached Art1 metric experiment; no documents, recompute or saves.

The coordinator owns runtime/process isolation and snapshot retention. Boundary
samples and tessellation convergence are diagnostics, never a Hausdorff bound
or a migration/fabrication acceptance test.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import runpy
import shutil
import time
from collections import Counter
from pathlib import Path

FLAG = "RAFTEL_RUN_THOR_METRIC_SEMANTICS"
LEVELS = ((0.5, 0.4), (0.1, 0.2), (0.02, 0.1))
MAX_TRIANGLES = 500_000
MAX_SAMPLES = 96
PINNED = {
    "source": (
        "8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a",
        "PartShape.brp",
        "d0ed3dcd293f814b6db11e0e29a22e89a6aa4fe6c8d9f8e5c08e508baec2b9db",
    ),
    "candidate": (
        "6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd",
        "Body.Shape.brp",
        "190d3f1560664eea784ae7edabed8442768d7c65ce4a8c040e1b9f3f5529016c",
    ),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_metric_selections(selections):
    if {r["selection_id"] for r in selections} != set(PINNED) or len(selections) != 2:
        raise ValueError("exactly the pinned source and UNACCEPTED candidate Body are required")
    for row in selections:
        if (row["source_sha256"], row["brep_entry"], row["brep_sha256"]) != PINNED[
            row["selection_id"]
        ]:
            raise ValueError("metric source/candidate pins differ")
        if (
            row["object_name"] != "Body"
            or row["uniform_density"] is not None
            or row["tessellation"] is not None
        ):
            raise ValueError("metric request must remain cached Body geometry only")
    return selections


def mesh_summary(points, faces):
    """Oriented tetrahedral integral in mm³; no topology or surface proof."""
    if not points or not faces or len(faces) > MAX_TRIANGLES:
        raise ValueError("bounded nonempty tessellation required")
    if any(len(p) != 3 or any(not math.isfinite(v) for v in p) for p in points):
        raise ValueError("nonfinite or malformed tessellation vertices")
    terms = []
    for face in faces:
        if len(face) != 3 or any(type(i) is not int or not 0 <= i < len(points) for i in face):
            raise ValueError("invalid tessellation triangle index")
        a, b, c = (points[i] for i in face)
        terms.append(
            (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                + a[1] * (b[2] * c[0] - b[0] * c[2])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            )
            / 6
        )
    return {
        "vertex_count": len(points),
        "triangle_count": len(faces),
        "oriented_triangle_integral_mm3": math.fsum(terms),
        "bounds_mm": [f(p[i] for p in points) for i in range(3) for f in (min, max)],
        "closed_manifold_or_self_intersection_proven": False,
    }


def sample_points(points):
    """Deterministic extrema plus evenly indexed vertices, at most 96 points."""
    unique = sorted(set(tuple(p) for p in points))
    if not unique:
        raise ValueError("surface sampling requires vertices")
    chosen = {min(unique, key=lambda p: p[i]) for i in range(3)}
    chosen.update(max(unique, key=lambda p: p[i]) for i in range(3))
    slots = MAX_SAMPLES - len(chosen)
    chosen.update(unique[round(i * (len(unique) - 1) / max(1, slots - 1))] for i in range(slots))
    return sorted(chosen)


def directed_samples(Part, points, target):
    # Face compounds deliberately avoid solid-interior distance=0 semantics.
    boundary = Part.makeCompound(target.Faces)
    if boundary.Solids:
        raise ValueError("distance target must be boundary faces, never a solid")
    rows = []
    for point in sample_points(points):
        distance, pairs, _ = Part.Vertex(*point).distToShape(boundary, 1e-7)
        if not math.isfinite(distance) or distance < 0 or not pairs:
            raise ValueError("native boundary distance returned no finite solution")
        rows.append({"point_mm": point, "distance_to_target_boundary_mm": distance})
    return {
        "sample_count": len(rows),
        "maximum_sampled_distance_mm": max(r["distance_to_target_boundary_mm"] for r in rows),
        "samples": rows,
        "true_maximum_or_Hausdorff_distance_proven": False,
        "sampling_scope": (
            "deterministic subset of tessellation vertices; no continuous surface bound"
        ),
    }


def _paths():
    if os.environ.get(FLAG) != "1":
        raise ValueError("metric worker requires explicit opt-in")
    if os.environ.get("RAFTEL_RUN_THOR_SOLID_PROPERTIES") == "1":
        raise ValueError("nested solid worker execution must be disabled")
    root = Path(os.environ["RAFTEL_METRIC_RUN_DIR"]).resolve(strict=True)
    request = Path(os.environ["RAFTEL_METRIC_REQUEST"]).resolve(strict=True)
    sources = Path(os.environ["RAFTEL_METRIC_SOURCE_ROOT"]).resolve(strict=True)
    output = Path(os.environ["RAFTEL_METRIC_REPORT"]).resolve()
    paths = {
        "UserParameter": root / "user.cfg",
        "SystemParameter": root / "system.cfg",
        "UserHomePath": Path(os.environ["FREECAD_USER_HOME"]).resolve(strict=True),
        "UserAppData": Path(os.environ["FREECAD_USER_DATA"]).resolve(strict=True),
        "AppTempPath": Path(os.environ["FREECAD_USER_TEMP"]).resolve(strict=True),
    }
    if (
        not root.is_dir()
        or not sources.is_dir()
        or any(not p.is_relative_to(root) for p in (request, sources, output, *paths.values()))
        or output.exists()
        or output.suffix != ".json"
        or output.is_relative_to(sources)
        or request == output
        or os.environ.get("PYTHONNOUSERSITE") != "1"
        or any(not paths[k].is_dir() for k in ("UserHomePath", "UserAppData", "AppTempPath"))
        or shutil.disk_usage(root).free < 50 * 1024**3 + 128 * 1024**2
    ):
        raise ValueError("fresh isolated metric run, configuration and 50 GiB reserve required")
    return root, request, sources, output, paths


def native_capture():
    root, request_path, source_root, output, paths = _paths()
    helper_path = Path(__file__).with_name("probe_thor_solid_properties_freecad.py")
    helper = runpy.run_path(str(helper_path))
    request = helper["validate_request"](
        json.loads(
            request_path.read_text(encoding="utf-8"), object_pairs_hook=helper["_unique_object"]
        )
    )
    selections = validate_metric_selections(request["selections"])
    verified = []
    for row in selections:
        verified.append((row, *helper["read_selected_brep"](source_root, row)))
    report = {
        "schema_version": 1,
        "evidence_class": "native_cached_metric_semantics_diagnostic_only",
        "audit_status": "starting",
        "request_sha256": sha(request_path),
        "capture_script_sha256": sha(Path(__file__)),
        "helper_sha256": sha(helper_path),
        "declared_executable_sha256": os.environ.get("RAFTEL_METRIC_EXECUTABLE_SHA256"),
        "migration_accepted": False,
        "candidate_accepted": False,
        "native_document_saved": False,
        "document_opened_or_recomputed": False,
        "full_runtime_bundle_independently_verified_by_worker": False,
        "coordinate_frame": "saved_BRep_storage_frame_mm; no additional placements applied",
        "selections": {},
        "mesh_convergence": [],
        "errors": [],
    }

    created = False
    checkpoint_index = 0
    checkpoint_sha = None

    def checkpoint():
        # Only this fresh run's report is updated; old captures are never opened for writing.
        nonlocal created, checkpoint_index, checkpoint_sha
        contents = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if not created:
            with output.open("xb") as stream:
                stream.write(contents)
        else:
            if sha(output) != checkpoint_sha:
                raise ValueError("own checkpoint changed externally; refusing replacement")
            checkpoint_index += 1
            temporary = root / f"metric-checkpoint-{checkpoint_index:04d}.json.tmp"
            with temporary.open("xb") as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, output)
        created = True
        checkpoint_sha = hashlib.sha256(contents).hexdigest()

    checkpoint()

    started = time.monotonic()
    try:
        import FreeCAD as App
        import MeshPart
        import Part

        report["open_document_count_before"] = len(App.listDocuments())
        if report["open_document_count_before"]:
            raise ValueError("metric worker requires zero open CAD documents")
        actual = {key: App.ConfigGet(key) for key in paths}
        report["actual_runtime_paths"] = actual
        if any(Path(actual[k]).resolve() != p for k, p in paths.items()):
            raise ValueError("runtime parameters/data paths differ from isolated run")
        report.update(freecad_version=list(App.Version()), opencascade_version=Part.OCC_VERSION)
        shapes = {}
        for row, raw, binding in verified:
            brep = root / (row["selection_id"] + ".brep")
            with brep.open("xb") as stream:
                stream.write(raw)
            shape = Part.Shape()
            shape.read(str(brep))
            shapes[row["selection_id"]] = shape
            bounds = shape.optimalBoundingBox(False, False)
            report["selections"][row["selection_id"]] = {
                "source_binding": binding,
                "properties": helper["_native_metrics"](shape),
                "optimal_unmeshed_bounds_mm": [getattr(bounds, k) for k in helper["BOUNDS"]],
                "stored_subshape_tolerance_mm": {
                    "minimum": shape.getTolerance(-1),
                    "average": shape.getTolerance(0),
                    "maximum": shape.getTolerance(1),
                },
                "face_surface_type_counts": dict(
                    Counter(type(f.Surface).__name__ for f in shape.Faces)
                ),
            }
        # Negative control: overlapping solids have zero global minimum distance,
        # while translated boundaries have a nonzero maximum sampled distance.
        box = Part.makeBox(2, 3, 4)
        moved = box.copy(True, False)
        moved.translate(App.Vector(0.25, 0, 0))
        vertices = [(v.Point.x, v.Point.y, v.Point.z) for v in box.Vertexes]
        control = directed_samples(Part, vertices, moved)
        report["translated_box_control"] = {
            "minimum_solid_distance_mm": box.distToShape(moved)[0],
            **control,
            "expected_sample_maximum_mm": 0.25,
        }
        if (
            abs(control["maximum_sampled_distance_mm"] - 0.25) > 1e-7
            or abs(report["translated_box_control"]["minimum_solid_distance_mm"]) > 1e-7
        ):
            raise ValueError("boundary distance negative control failed")
        interior = (1.0, 1.5, 2.0)
        boundary_distance = directed_samples(Part, [interior], moved)["maximum_sampled_distance_mm"]
        # Nearest face of translated box [0.25,2.25] x [0,3] x [0,4].
        expected_distance = min(1.0 - 0.25, 2.25 - 1.0, 1.5, 3 - 1.5, 2.0, 4 - 2.0)
        report["interior_box_control"] = {
            "point_mm": interior,
            "minimum_solid_distance_mm": Part.Vertex(*interior).distToShape(moved)[0],
            "distance_to_boundary_faces_mm": boundary_distance,
            "closed_form_nearest_face_distance_mm": expected_distance,
        }
        if (
            abs(boundary_distance - expected_distance) > 1e-7
            or abs(report["interior_box_control"]["minimum_solid_distance_mm"]) > 1e-7
        ):
            raise ValueError("interior point distance-to-boundary control failed")
        for name, other in (("source", "candidate"), ("candidate", "source")):
            cut = shapes[name].cut(shapes[other])
            report[name + "_minus_" + other] = {
                "is_null": cut.isNull(),
                "solid_count": len(cut.Solids),
                "face_count": len(cut.Faces),
                "edge_count": len(cut.Edges),
                "volume_mm3": None if cut.isNull() else cut.Volume,
            }
        for deflection, angular in LEVELS:
            level = {
                "linear_deflection_mm": deflection,
                "angular_deflection_rad": angular,
                "relative": False,
                "shapes": {},
            }
            report["mesh_convergence"].append(level)
            for name in shapes:
                if time.monotonic() - started > 240:
                    raise ValueError("bounded worker time exhausted before next tessellation")
                # A fresh raw import per level avoids shared triangulation caches.
                fresh = Part.Shape()
                fresh.read(str(root / (name + ".brep")))
                before_mesh = helper["_native_metrics"](fresh)
                mesh = MeshPart.meshFromShape(
                    Shape=fresh,
                    LinearDeflection=deflection,
                    AngularDeflection=angular,
                    Relative=False,
                )
                points, faces = mesh.Topology
                coordinates = [(p.x, p.y, p.z) for p in points]
                summary = mesh_summary(coordinates, faces)
                summary["native_metrics_before_meshing"] = before_mesh
                summary["native_metrics_after_meshing"] = helper["_native_metrics"](fresh)
                target = shapes["candidate" if name == "source" else "source"]
                summary["directed_boundary_samples"] = directed_samples(Part, coordinates, target)
                level["shapes"][name] = summary
                checkpoint()
        report["audit_status"] = "complete_diagnostic_not_equivalence"
        report["open_document_count_after"] = len(App.listDocuments())
        if report["open_document_count_after"]:
            raise ValueError("metric worker unexpectedly opened a CAD document")
    except Exception as error:
        report["audit_status"] = "failed_metric_diagnostic"
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
    report["input_copy_sha256_after"] = {
        r["selection_id"]: sha(source_root / r["source_file"]) for r in selections
    }
    report["input_copy_bytes_unchanged"] = all(
        report["input_copy_sha256_after"][r["selection_id"]] == r["source_sha256"]
        for r in selections
    )
    if not report["input_copy_bytes_unchanged"]:
        report["audit_status"] = "failed_input_copy_changed"
    report["capture_script_sha256_after"] = sha(Path(__file__))
    report["helper_sha256_after"] = sha(helper_path)
    report["request_sha256_after"] = sha(request_path)
    report["retained_inputs_unchanged"] = all(
        report[k] == report[k + "_after"]
        for k in ("capture_script_sha256", "helper_sha256", "request_sha256")
    )
    if not report["retained_inputs_unchanged"]:
        report["audit_status"] = "failed_retained_input_changed"
    report["elapsed_seconds"] = time.monotonic() - started
    checkpoint()
    print("RAFTEL_METRIC_REPORT", report["audit_status"], str(output))
    return report


if __name__ == "__main__" or os.environ.get(FLAG) == "1":
    native_capture()
