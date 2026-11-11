"""Inspect exact column-mesh defects without welding, repair or print qualification.

The normal CLI is host-only. An explicitly opted-in, separately coordinated
FreeCAD entry point can inspect topology before final binary STL serialization.
Neither mode saves/recomputes CAD or communicates with a slicer or printer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import runpy
import shutil
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

FLAG = "RAFTEL_RUN_COLUMN_MESH_DIAGNOSTIC"
SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
SOURCE_SHA256 = "f31295eaaf973347c73779e69ca33f095656b1e7bc4511eac5ce879aaaddbb2c"
BREP_SHA256 = "95cc8bc005dead7f10f6c613c38b3b37176188d33fdaf23a09af4a7a693ad038"
RUNTIME_EXE_SHA256 = "1692e54224b48989974e8b91d3ac7a38d1d502d3db4dee1d4cf79ba91356e42d"
UPSTREAM_STL_SHA256 = "f62c1a9b123f354d3796c7610339678e283a51ea651351c7138fde3e8268530e"
MAX_POINTS = 1_000_000
MAX_FACES = 1_000_000
MAX_INPUT_BYTES = 100 * 1024**2


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("coordinates must be finite real numbers")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("coordinates must be finite real numbers") from error
    if not math.isfinite(result):
        raise ValueError("coordinates must be finite real numbers")
    return result


def _point(value):
    if not isinstance(value, list | tuple) or len(value) != 3:
        raise ValueError("a point needs exactly three coordinates")
    return tuple(_finite(x) for x in value)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path):
    with Path(path).open("rb") as stream:
        contents = stream.read(MAX_INPUT_BYTES + 1)
    if not 1 <= len(contents) <= MAX_INPUT_BYTES:
        raise ValueError("input is empty or exceeds the bounded byte limit")
    return contents


def float32(value):
    try:
        return _finite(struct.unpack("<f", struct.pack("<f", _finite(value)))[0])
    except (OverflowError, struct.error) as error:
        raise ValueError("coordinate is outside finite binary32 range") from error


def float32_neighborhood(value):
    """Adjacent representable values, not an asserted geometric error bound."""
    value = _finite(value)
    rounded = float32(value)
    bits = struct.unpack("<I", struct.pack("<f", rounded))[0]
    if rounded == 0:
        previous, following = -(2.0**-149), 2.0**-149
    else:
        neighbors = []
        for candidate in (bits - 1, bits + 1):
            result = struct.unpack("<f", struct.pack("<I", candidate))[0]
            neighbors.append(result if math.isfinite(result) else None)
        previous, following = neighbors if rounded > 0 else neighbors[::-1]
    return {
        "value": value,
        "rounded_binary32": rounded,
        "rounding_absolute_error": abs(value - rounded),
        "previous_binary32": previous,
        "next_binary32": following,
        "adjacent_spacing_max": max(
            abs(rounded - neighbor) for neighbor in (previous, following) if neighbor is not None
        ),
    }


def topology_snapshot(points, faces):
    """Count exact-coordinate incidences before any optional serialization.

    Face indices and duplicates are retained. Coordinate-equivalent source
    vertices are identified for diagnostics only; no repaired mesh is emitted.
    """
    if not 1 <= len(points) <= MAX_POINTS or not 1 <= len(faces) <= MAX_FACES:
        raise ValueError("point/triangle count outside diagnostic bounds")
    points = tuple(_point(point) for point in points)
    checked_faces = []
    incidence = defaultdict(list)
    duplicates = Counter()
    used = set()
    for face_index, face in enumerate(faces):
        if (
            not isinstance(face, list | tuple)
            or len(face) != 3
            or any(type(index) is not int or not 0 <= index < len(points) for index in face)
        ):
            raise ValueError("triangles require three in-range integer indices")
        used.update(face)
        triangle = tuple(points[index] for index in face)
        checked_faces.append(triangle)
        duplicates[tuple(sorted(triangle))] += 1
        for a, b in zip(triangle, (*triangle[1:], triangle[0]), strict=True):
            edge = tuple(sorted((a, b)))
            incidence[edge].append((face_index, 1 if a < b else -1))
    defects = []
    for edge, rows in sorted(incidence.items()):
        if len(rows) <= 2 and edge[0] != edge[1]:
            continue
        facets = []
        for face_index, direction in rows:
            triangle = checked_faces[face_index]
            a, b, c = triangle
            u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            cross = (
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            )
            magnitude = _finite(math.hypot(*(_finite(x) for x in cross)))
            facets.append(
                {
                    "facet_index_zero_based": face_index,
                    "triangle_mm": triangle,
                    "edge_direction_relative_to_sorted_endpoints": direction,
                    "area_mm2": magnitude / 2,
                    "geometric_unit_normal": tuple(x / magnitude for x in cross)
                    if magnitude
                    else None,
                }
            )
        defects.append(
            {
                "endpoints_mm": edge,
                "length_mm": _finite(math.dist(*edge)),
                "incidence_count": len(rows),
                "incident_facets": facets,
            }
        )
    defect_vertices = sorted({point for edge in defects for point in edge["endpoints_mm"]})
    return {
        "indexed_point_count": len(points),
        "used_index_count": len(used),
        "exact_coordinate_count": len(set(points)),
        "used_exact_coordinate_count": len({points[i] for i in used}),
        "triangle_count": len(faces),
        "boundary_edge_count": sum(len(rows) == 1 for rows in incidence.values()),
        "nonmanifold_edge_count": len(defects),
        "duplicate_facet_count": sum(count - 1 for count in duplicates.values()),
        "nonmanifold_edges": defects,
        "defect_vertices_mm": defect_vertices,
        "defect_chain_total_length_mm": math.fsum(edge["length_mm"] for edge in defects),
        "source_geometry_changed": False,
        "self_intersections_checked": False,
    }


def analyze_bytes(contents):
    import thor_slicer_plan as stl

    encoding, facets, _ = stl.parse_stl(contents)
    indices = {}
    points, faces = [], []
    for _, triangle in facets:
        face = []
        for point in triangle:
            if point not in indices:
                indices[point] = len(points)
                points.append(point)
            face.append(indices[point])
        faces.append(face)
    return {
        "sha256": _sha(contents),
        "bytes": len(contents),
        "encoding": encoding,
        "existing_parser_audit": stl.analyze_stl(contents),
        "incidence_diagnostic": topology_snapshot(points, faces),
    }


def summarize_native_precision(capture_raw, launch_raw, contract_raw):
    """Join retained receipts and independently recalculate the recorded arrays.

    This checks supplied evidence coherence, not independent authentication of
    an executable invocation. Retained logs and independent review are separate.
    """
    from raftel_arm01.engineering.scenarios import _strict_json

    capture, launch, contract = (
        _strict_json(raw) for raw in (capture_raw, launch_raw, contract_raw)
    )
    if (
        type(capture.get("schema_version")) is not int
        or capture["schema_version"] != 1
        or capture.get("evidence_class")
        != "native_cached_BRep_mesh_precision_diagnostic_not_repair"
        or capture.get("status") != "complete_diagnostic_not_repair"
        or capture.get("errors") != []
        or capture.get("source_brep_sha256_before") != BREP_SHA256
        or capture.get("source_brep_sha256_after") != BREP_SHA256
        or capture.get("source_unchanged") is not True
        or any(
            type(capture.get(key)) is not int or capture[key] != 0
            for key in ("open_document_count_before", "open_document_count_after")
        )
        or capture.get("runtime_isolation", {}).get("verified") is not True
        or capture.get("document_opened_recomputed_or_saved") is not False
        or capture.get("mesh_repaired") is not False
        or capture.get("fabrication_release") is not False
        or not isinstance(capture.get("freecad_version"), list)
        or capture["freecad_version"][:3] != ["1", "1", "4"]
        or capture["freecad_version"][-1:] != ["4fd3bf320d9566a27e60069fc8387448aaa3a094"]
        or capture.get("opencascade_version") != "7.8.1"
    ):
        raise ValueError("native precision capture did not establish its declared scope")
    if (
        launch.get("native_process_launched") is not True
        or launch.get("outcome") != "process_completed"
        or type(launch.get("returncode")) is not int
        or launch["returncode"] != 0
        or launch.get("audit_status") != capture["status"]
        or launch.get("native_report_sha256") != _sha(capture_raw)
        or any(
            launch.get(key) is not True
            for key in (
                "original_sources_unchanged",
                "copied_brep_unchanged",
                "snapshots_unchanged",
                "launcher_snapshot_unchanged",
                "report_exists",
            )
        )
    ):
        raise ValueError("native precision launcher did not preserve completed evidence")
    if (
        type(contract.get("schema_version")) is not int
        or contract["schema_version"] != 1
        or contract.get("source_revision") != SOURCE_REVISION
        or contract.get("executable_sha256") != RUNTIME_EXE_SHA256
        or contract.get("source_archive_sha256") != SOURCE_SHA256
        or contract.get("copied_brep_sha256") != BREP_SHA256
        or contract.get("snapshot_sha256_before", {}).get("diagnose_thor_column_mesh.py")
        != capture.get("capture_script_sha256")
    ):
        raise ValueError("native precision contract/source/worker binding differs")
    originals = contract.get("original_source_sha256_before")
    if (
        not isinstance(originals, dict)
        or len(originals) != 57
        or originals.get("freecad-src/Art4TransmissionColumn.fcstd") != SOURCE_SHA256
    ):
        raise ValueError("native precision contract needs the57-source preservation ledger")
    paths = capture["runtime_isolation"].get("actual_paths")
    if (
        not isinstance(paths, dict)
        or set(paths)
        != {"UserParameter", "SystemParameter", "UserHomePath", "UserAppData", "AppTempPath"}
        or any(not isinstance(value, str) or not value for value in paths.values())
    ):
        raise ValueError("native precision capture needs all five actual runtime paths")
    summaries = []
    routes = capture.get("routes")
    if (
        not isinstance(routes, list)
        or {row.get("route") for row in routes}
        != {"MeshPart_same_settings", "Part_tessellate_linear_only"}
        or len(routes) != 2
    ):
        raise ValueError("native precision capture needs both distinct declared routes")
    for row in routes:
        points, faces = row["points_mm"], row["faces"]
        raw = topology_snapshot(points, faces)
        rounded = topology_snapshot([tuple(float32(x) for x in point) for point in points], faces)
        for key, calculated in (("raw_topology", raw), ("binary32_rounded_topology", rounded)):
            if json.dumps(calculated, sort_keys=True) != json.dumps(row.get(key), sort_keys=True):
                raise ValueError("native precision topology summary differs from retained arrays")
        already = sum(x == float32(x) for point in points for x in point)
        if (
            type(row.get("coordinate_count")) is not int
            or type(row.get("coordinates_already_binary32_count")) is not int
            or row["coordinate_count"] != len(points) * 3
            or row.get("coordinates_already_binary32_count") != already
        ):
            raise ValueError("native precision coordinate counts differ from retained arrays")
        summaries.append(
            {
                "route": row["route"],
                "settings_comparability": row["settings_comparability"],
                "native_shape_valid": row["native_shape_valid"],
                "coordinate_count": len(points) * 3,
                "coordinates_already_binary32_count": already,
                "raw_topology": {
                    key: value for key, value in raw.items() if key != "nonmanifold_edges"
                },
                "binary32_rounded_topology": {
                    key: value for key, value in rounded.items() if key != "nonmanifold_edges"
                },
            }
        )
    return {
        "capture_raw_sha256": _sha(capture_raw),
        "launcher_raw_sha256": _sha(launch_raw),
        "contract_raw_sha256": _sha(contract_raw),
        "executed_capture_script_sha256": capture["capture_script_sha256"],
        "runtime_isolation": capture["runtime_isolation"],
        "freecad_version": capture["freecad_version"],
        "opencascade_version": capture["opencascade_version"],
        "open_document_count_before": 0,
        "open_document_count_after": 0,
        "source_unchanged": True,
        "original_57_source_files_unchanged_reported_by_launcher": True,
        "routes": summaries,
        "coherent_receipts_alone_authenticate_native_execution": False,
        "underlying_defect_cause_proven": False,
        "mesh_repaired": False,
        "fabrication_release": False,
    }


def build_report(native_mesh, upstream_mesh, capture_raw, audit_raw, native_raw_evidence=None):
    from raftel_arm01.engineering.scenarios import _strict_json

    capture, audit = _strict_json(capture_raw), _strict_json(audit_raw)
    if capture.get("source_revision") != SOURCE_REVISION:
        raise ValueError("capture revision differs from pinned column source")
    selections = [
        x
        for x in capture.get("selections", [])
        if x.get("selection_id") == "art4-transmission-column"
    ]
    if len(selections) != 1:
        raise ValueError("capture needs exactly one declared column selection")
    selection = selections[0]
    binding = selection["source_binding"]
    if (
        binding.get("source_sha256") != SOURCE_SHA256
        or binding.get("brep_sha256") != BREP_SHA256
        or binding.get("source_file") != "freecad-src/Art4TransmissionColumn.fcstd"
        or binding.get("object_name") != "Body"
        or binding.get("object_type") != "PartDesign::Body"
        or binding.get("brep_entry") != "PartShape1.brp"
    ):
        raise ValueError("column source/BRep binding differs from pinned bytes")
    if selection["draft_stl"]["sha256"] != _sha(native_mesh):
        raise ValueError("native STL bytes differ from capture binding")
    if audit.get("input_bindings", {}).get("native_capture_raw_sha256") != _sha(capture_raw):
        raise ValueError("host audit does not bind this capture's exact bytes")
    if _sha(upstream_mesh) != UPSTREAM_STL_SHA256:
        raise ValueError("upstream STL bytes differ from the preserved source pin")
    native = analyze_bytes(native_mesh)
    vertices = native["incidence_diagnostic"]["defect_vertices_mm"]
    result = {
        "schema_version": 1,
        "evidence_class": (
            "host_exact_mesh_incidence_diagnostics_not_repair_or_fabrication_qualification"
        ),
        "source_revision": SOURCE_REVISION,
        "input_bindings": {
            "capture_raw_sha256": _sha(capture_raw),
            "host_audit_raw_sha256": _sha(audit_raw),
        },
        "source_binding": binding,
        "coordinate_frame": selection["coordinate_frame"],
        "native_capture_reported_shape_properties": selection["cached_shape_properties"],
        "native_stl": native,
        "preserved_upstream_stl": analyze_bytes(upstream_mesh),
        "defect_coordinate_binary32_neighborhoods": [
            {"vertex_mm": point, "coordinates": [float32_neighborhood(value) for value in point]}
            for point in vertices
        ],
        "pre_final_serialization_vertex_count_reported_by_capture": selection["draft_stl"][
            "vertex_count_before_STL_unindexing"
        ],
        "native_precision_probe": None
        if native_raw_evidence is None
        else summarize_native_precision(*native_raw_evidence),
        "interpretation": {
            "four_triangles_per_defect_edge_is_observed": bool(
                native["incidence_diagnostic"]["nonmanifold_edges"]
            )
            and all(
                edge["incidence_count"] == 4
                for edge in native["incidence_diagnostic"]["nonmanifold_edges"]
            ),
            "origin_of_defect_proven": False,
            "original_native_topology_cannot_be_recovered_from_STL_alone": True,
            "equal_point_counts_do_not_exclude_earlier_quantization": True,
            "mesh_repaired": False,
            "native_solid_equivalence_proven": False,
            "print_or_fit_qualification": False,
            "fabrication_release": False,
        },
    }
    return result


def native_capture():
    """Guarded cached-BRep comparison; coordinator supplies fresh isolated paths."""
    if os.environ.get(FLAG) != "1":
        raise ValueError("native precision capture requires explicit opt-in")
    if os.environ.get("RAFTEL_RUN_FREECAD_AUDIT") == "1":
        raise ValueError("conflicting assembly-audit opt-in must be cleared before this probe")
    root = Path(os.environ["RAFTEL_COLUMN_RUN_DIR"]).resolve(strict=True)
    source = Path(os.environ["RAFTEL_COLUMN_BREP"]).resolve(strict=True)
    output = Path(os.environ["RAFTEL_COLUMN_REPORT"]).resolve()
    if not root.is_dir() or not source.is_relative_to(root) or not output.is_relative_to(root):
        raise ValueError("copied BRep/report must stay inside the fresh isolated run")
    if output == source or output.exists() or output.suffix.lower() != ".json":
        raise ValueError("native report requires a new distinct JSON path")
    if _sha(_read(source)) != BREP_SHA256:
        raise ValueError("native precision capture requires the pinned column BRep")
    if shutil.disk_usage(root).free < 50 * 1024**3:
        raise ValueError("native precision capture requires the 50 GiB disk reserve")
    import FreeCAD as App
    import MeshPart
    import Part

    helper = runpy.run_path(str(Path(__file__).with_name("audit_freecad_assembly.py")))
    isolation = helper["_runtime_isolation"](App, root)
    writer = helper["ReportWriter"](output)
    report = {
        "schema_version": 1,
        "evidence_class": "native_cached_BRep_mesh_precision_diagnostic_not_repair",
        "status": "started",
        "runtime_isolation": isolation,
        "freecad_version": list(App.Version()),
        "opencascade_version": Part.OCC_VERSION,
        "source_brep_sha256_before": _sha(_read(source)),
        "capture_script_sha256": _sha(_read(Path(__file__))),
        "open_document_count_before": len(App.listDocuments()),
        "routes": [],
        "errors": [],
    }
    writer(report)
    try:
        for route in ("MeshPart_same_settings", "Part_tessellate_linear_only"):
            shape = Part.Shape()
            shape.read(str(source))
            if route == "MeshPart_same_settings":
                mesh = MeshPart.meshFromShape(
                    Shape=shape, LinearDeflection=0.1, AngularDeflection=0.2, Relative=False
                )
                vertices, faces = mesh.Topology
            else:
                vertices, faces = shape.tessellate(0.1)
            vertices = [tuple(float(x) for x in point) for point in vertices]
            faces = [tuple(face) for face in faces]
            rounded = [tuple(float32(x) for x in point) for point in vertices]
            report["routes"].append(
                {
                    "route": route,
                    "settings_comparability": "same requested settings as Run03"
                    if route == "MeshPart_same_settings"
                    else "linear deflection0.1 only; angular/default meshing behavior differs",
                    "native_shape_valid": shape.isValid(),
                    "raw_topology": topology_snapshot(vertices, faces),
                    "binary32_rounded_topology": topology_snapshot(rounded, faces),
                    "coordinates_already_binary32_count": sum(
                        x == float32(x) for point in vertices for x in point
                    ),
                    "coordinate_count": len(vertices) * 3,
                    "points_mm": vertices,
                    "faces": faces,
                }
            )
            writer(report)
        report["status"] = "complete_diagnostic_not_repair"
    except Exception as error:
        report["status"] = "failed_diagnostic"
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
    report["source_brep_sha256_after"] = _sha(_read(source))
    report["source_unchanged"] = (
        report["source_brep_sha256_after"] == report["source_brep_sha256_before"]
    )
    report["open_document_count_after"] = len(App.listDocuments())
    if not report["source_unchanged"] or report["open_document_count_after"]:
        report["status"] = "failed_source_preservation_or_document_isolation"
    report["document_opened_recomputed_or_saved"] = False
    report["mesh_repaired"] = False
    report["fabrication_release"] = False
    writer(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-mesh", type=Path, required=True)
    parser.add_argument("--upstream-mesh", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--host-audit", type=Path, required=True)
    parser.add_argument("--native-precision-report", type=Path)
    parser.add_argument("--native-precision-launcher", type=Path)
    parser.add_argument("--native-precision-contract", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        native_paths = (
            args.native_precision_report,
            args.native_precision_launcher,
            args.native_precision_contract,
        )
        if any(path is not None for path in native_paths) and not all(
            path is not None for path in native_paths
        ):
            raise ValueError("supply all three optional native precision evidence paths together")
        if args.output.suffix.lower() != ".json" or args.output.exists():
            raise ValueError("output requires a new JSON path")
        if args.output.resolve() in {
            p.resolve()
            for p in (args.native_mesh, args.upstream_mesh, args.capture, args.host_audit)
        }:
            raise ValueError("output must not alias any input")
        report = build_report(
            *[
                _read(path)
                for path in (args.native_mesh, args.upstream_mesh, args.capture, args.host_audit)
            ],
            native_raw_evidence=None
            if native_paths[0] is None
            else tuple(_read(path) for path in native_paths),
        )
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Column mesh diagnostic failed: {error}", file=sys.stderr)
        return 2


if os.environ.get(FLAG) == "1":
    native_capture()
elif __name__ == "__main__":
    raise SystemExit(main())
