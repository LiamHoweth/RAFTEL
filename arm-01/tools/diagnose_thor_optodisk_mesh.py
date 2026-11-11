"""Exact optodisk boundary diagnostics; no welding, CAD repair or print release.

The ordinary CLI is host-only. A separately authorized, isolated FreeCAD entry
point compares explicitly different cached-BRep tessellations in fresh shapes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import runpy
import shutil
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path, PurePosixPath, PureWindowsPath

FLAG = "RAFTEL_RUN_OPTODISK_MESH_DIAGNOSTIC"
CONFLICTING_FLAGS = (
    "RAFTEL_RUN_FREECAD_AUDIT",
    "RAFTEL_RUN_COLUMN_MESH_DIAGNOSTIC",
    "RAFTEL_RUN_THOR_SOLID_PROPERTIES",
)
SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
SOURCE_SHA256 = "c81e788792edea63c7e73a12b06dc8073668a6b899f8d46ea5c3d9d399de431c"
BREP_SHA256 = "a4a3586db66f88995c904ed5d8622122a38cb1046a086fdf53794f40dbfac5d1"
UPSTREAM_SHA256 = "a9056374be8f26e622a465a257b5ee80d13a48fdaa51d525ea2d4701618c9e9e"
MAX_BYTES = 100 * 1024**2
MAX_FACES = 1_000_000
MAX_PLANAR_LOOP_VERTICES = 128


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError("input outside bounded byte limit")
    return raw


def _no_conflicting_flags():
    if any(os.environ.get(name) == "1" for name in CONFLICTING_FLAGS):
        raise ValueError("conflicting native-helper opt-in must be cleared before imports")


def _helper(name):
    _no_conflicting_flags()
    return runpy.run_path(str(Path(__file__).with_name(name)))


def planar_boundary_crossings(cycle):
    """Exact rational predicates on supplied floats, bounded to small planar loops.

    This checks proper crossings of boundary segments only. It is not a full
    triangle self-intersection test, and does not treat contact as a proper cross.
    """
    if cycle is None or len(cycle) > MAX_PLANAR_LOOP_VERTICES:
        return {"tested": False, "reason": "no_graph_cycle_or_loop_exceeds_bound"}
    axis = next((i for i in range(3) if len({point[i] for point in cycle}) == 1), None)
    if axis is None:
        return {"tested": False, "reason": "not_exact_axis_aligned_planar"}
    axes = [i for i in range(3) if i != axis]
    xy = [tuple(Fraction(point[i]) for i in axes) for point in cycle]

    def cross(a, b):
        return a[0] * b[1] - a[1] * b[0]

    def minus(a, b):
        return a[0] - b[0], a[1] - b[1]

    result = []
    n = len(cycle)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            a, b, c, d = xy[i], xy[(i + 1) % n], xy[j], xy[(j + 1) % n]
            first, second, delta = minus(b, a), minus(d, c), minus(c, a)
            denominator = cross(first, second)
            if denominator == 0:
                continue
            t, u = cross(delta, second) / denominator, cross(delta, first) / denominator
            if 0 < t < 1 and 0 < u < 1:
                point = list(cycle[i])
                for k in axes:
                    point[k] = float(
                        Fraction(cycle[i][k])
                        + t * (Fraction(cycle[(i + 1) % n][k]) - Fraction(cycle[i][k]))
                    )
                result.append(
                    {
                        "cycle_edge_indices": [i, j],
                        "first_segment_parameter": float(t),
                        "second_segment_parameter": float(u),
                        "intersection_mm": point,
                    }
                )
    return {
        "tested": True,
        "constant_axis": axis,
        "proper_crossings": result,
        "predicates": "exact rational arithmetic on supplied finite float coordinates",
        "full_triangle_self_intersections_checked": False,
    }


def boundary_snapshot(points, faces):
    """Retain exact-coordinate boundary edges and graph cycles, never fill them."""
    column = _helper("diagnose_thor_column_mesh.py")
    topology = column["topology_snapshot"](points, faces)
    points = [column["_point"](point) for point in points]
    incidence = defaultdict(list)
    for face_index, face in enumerate(faces):
        triangle = tuple(points[index] for index in face)
        for a, b in zip(triangle, (*triangle[1:], triangle[0]), strict=True):
            incidence[tuple(sorted((a, b)))].append((face_index, triangle))
    rows = []
    neighbors = defaultdict(set)
    for edge, incident in sorted(incidence.items()):
        if len(incident) != 1:
            continue
        neighbors[edge[0]].add(edge[1])
        neighbors[edge[1]].add(edge[0])
        rows.append(
            {
                "endpoints_mm": edge,
                "length_mm": column["_finite"](math.dist(*edge)),
                "facet_index_zero_based": incident[0][0],
                "incident_triangle_mm": incident[0][1],
            }
        )
    unseen, components = set(neighbors), []
    while unseen:
        start = min(unseen)
        pending = [start]
        members = set()
        while pending:
            vertex = pending.pop()
            if vertex not in members:
                members.add(vertex)
                pending.extend(neighbors[vertex] - members)
        unseen -= members
        cycle = None
        if len(members) >= 3 and all(len(neighbors[p]) == 2 for p in members):
            cycle = [start]
            prior = None
            current = start
            while True:
                following = min(neighbors[current] - ({prior} if prior is not None else set()))
                if following == start:
                    break
                if following in cycle:
                    raise ValueError("boundary graph cycle traversal is inconsistent")
                cycle.append(following)
                prior, current = current, following
        component = {
            "vertices_mm": sorted(members),
            "graph_simple_cycle": cycle is not None,
            "ordered_cycle_mm": cycle,
            "vertex_degrees": [len(neighbors[p]) for p in sorted(members)],
            "axis_ranges_mm": [
                max(p[i] for p in members) - min(p[i] for p in members) for i in range(3)
            ],
        }
        if cycle is not None:
            origin = cycle[0]
            relative = [tuple(p[i] - origin[i] for i in range(3)) for p in cycle]
            terms = [[] for _ in range(3)]
            for a, b in zip(relative, (*relative[1:], relative[0]), strict=True):
                for i, value in enumerate(
                    (
                        a[1] * b[2] - a[2] * b[1],
                        a[2] * b[0] - a[0] * b[2],
                        a[0] * b[1] - a[1] * b[0],
                    )
                ):
                    terms[i].append(value / 2)
            vector = tuple(math.fsum(values) for values in terms)
            component["oriented_vector_area_mm2"] = vector
            component["vector_area_magnitude_mm2"] = math.hypot(*vector)
            component["area_is_not_a_validated_fill_or_surface_area"] = True
        component["planar_boundary_crossings"] = planar_boundary_crossings(cycle)
        components.append(component)
    return {
        "topology": topology,
        "boundary_edges": rows,
        "boundary_components": components,
        "boundary_edges_filled": False,
        "vertex_welding_performed": False,
    }


def stl_boundary(raw):
    import thor_slicer_plan as stl

    _, facets, _ = stl.parse_stl(raw)
    points, indices, faces = [], {}, []
    for _, triangle in facets:
        face = []
        for point in triangle:
            if point not in indices:
                indices[point] = len(points)
                points.append(point)
            face.append(indices[point])
        faces.append(face)
    return {
        "sha256": _sha(raw),
        "bytes": len(raw),
        "mesh_audit": stl.analyze_stl(raw),
        "boundary_diagnostic": boundary_snapshot(points, faces),
    }


def compare_stl_geometry(candidate, reference):
    """Compare exact discrete geometry, ignoring header/normals/triangle order.

    Triangle cyclic permutations preserve orientation; reversal does not. Both
    facet and vertex multiplicity remain visible. No proximity tolerance is used.
    """
    import thor_slicer_plan as stl

    def counters(raw):
        _, facets, _ = stl.parse_stl(raw)
        points = Counter(point for _, triangle in facets for point in triangle)
        triangles = Counter(
            min(
                triangle,
                (triangle[1], triangle[2], triangle[0]),
                (triangle[2], triangle[0], triangle[1]),
            )
            for _, triangle in facets
        )
        return points, triangles

    a_points, a_triangles = counters(candidate)
    b_points, b_triangles = counters(reference)
    return {
        "candidate_sha256": _sha(candidate),
        "reference_sha256": _sha(reference),
        "unindexed_vertex_multisets_exactly_equal": a_points == b_points,
        "oriented_cyclic_triangle_multisets_exactly_equal": a_triangles == b_triangles,
        "candidate_only_oriented_facets": sum((a_triangles - b_triangles).values()),
        "reference_only_oriented_facets": sum((b_triangles - a_triangles).values()),
        "normals_headers_triangle_order_ignored": True,
        "multiplicity_retained": True,
        "coordinate_tolerance_or_welding_used": False,
        "continuous_source_solid_equivalence_proven": False,
        "print_qualified": False,
    }


def validate_recorded_isolation(isolation):
    """Check recorded absolute path containment without relying on this host OS."""
    root = isolation.get("root")
    paths = isolation.get("actual_paths")
    if not isinstance(root, str) or not root:
        raise ValueError("native isolation needs its recorded absolute root")
    flavor = PureWindowsPath if PureWindowsPath(root).drive else PurePosixPath
    base = flavor(root)
    if not base.is_absolute() or any(
        part in {".", ".."} for part in root.replace("\\", "/").split("/")
    ):
        raise ValueError("native isolation root must be absolute and normalized")
    if not isinstance(paths, dict) or set(paths) != {
        "UserParameter",
        "SystemParameter",
        "UserHomePath",
        "UserAppData",
        "AppTempPath",
    }:
        raise ValueError("native isolation needs all five actual runtime paths")
    for value in paths.values():
        if (
            not isinstance(value, str)
            or not value
            or any(part in {".", ".."} for part in value.replace("\\", "/").split("/"))
        ):
            raise ValueError("native runtime path must be nonempty and normalized")
        path = flavor(value)
        if not path.is_absolute() or not path.is_relative_to(base):
            raise ValueError("native runtime path escaped the recorded isolation root")


def summarize_native(capture_raw, runner_raw, contract_raw, exports, upstream):
    """Validate supplied scope/bindings and recalculate all raw topology arrays."""
    from raftel_arm01.engineering.scenarios import _strict_json

    capture, runner, contract = (
        _strict_json(raw) for raw in (capture_raw, runner_raw, contract_raw)
    )
    if _sha(upstream) != UPSTREAM_SHA256:
        raise ValueError("native summary needs the exact pinned upstream STL bytes")
    expected = {
        "MeshPart_original": {
            "linear_deflection_mm": 0.1,
            "angular_deflection_rad": 0.2,
            "relative": False,
        },
        "Part_linear_only": {
            "linear_deflection_mm": 0.1,
            "angular_deflection_rad": None,
            "relative": False,
        },
        "MeshPart_refined": {
            "linear_deflection_mm": 0.025,
            "angular_deflection_rad": 0.1,
            "relative": False,
        },
    }
    if (
        type(capture.get("schema_version")) is not int
        or capture["schema_version"] != 1
        or capture.get("evidence_class")
        != "native_cached_optodisk_tessellation_diagnostic_not_repair"
        or capture.get("status") != "complete_diagnostic_not_repair"
        or capture.get("errors") != []
        or capture.get("source_brep_sha256_before") != BREP_SHA256
        or capture.get("source_brep_sha256_after") != BREP_SHA256
        or capture.get("source_unchanged") is not True
        or any(
            capture.get(key) is not False
            for key in (
                "document_opened_recomputed_or_saved",
                "mesh_repaired",
                "fabrication_release",
            )
        )
        or any(
            type(capture.get(key)) is not int or capture[key] != 0
            for key in ("open_document_count_before", "open_document_count_after")
        )
        or capture.get("runtime_isolation", {}).get("verified") is not True
        or capture.get("runtime_isolation", {}).get("requested") is not True
        or not isinstance(capture.get("freecad_version"), list)
        or capture["freecad_version"][:3] != ["1", "1", "4"]
        or capture["freecad_version"][-1:] != ["4fd3bf320d9566a27e60069fc8387448aaa3a094"]
        or capture.get("opencascade_version") != "7.8.1"
    ):
        raise ValueError("native optodisk capture did not establish declared diagnostic scope")
    column = _helper("diagnose_thor_column_mesh.py")
    if (
        type(contract.get("schema_version")) is not int
        or contract["schema_version"] != 1
        or contract.get("source_revision") != SOURCE_REVISION
        or contract.get("source_archive_sha256") != SOURCE_SHA256
        or contract.get("copied_brep_sha256") != BREP_SHA256
        or contract.get("executable_sha256") != column["RUNTIME_EXE_SHA256"]
        or contract.get("snapshot_sha256_before", {}).get("diagnose_thor_optodisk_mesh.py")
        != capture.get("capture_script_sha256")
        or not isinstance(contract.get("original_source_sha256_before"), dict)
        or len(contract["original_source_sha256_before"]) != 57
        or contract["original_source_sha256_before"].get("freecad-src/Art23Optodisk.fcstd")
        != SOURCE_SHA256
        or runner.get("native_report_sha256") != _sha(capture_raw)
        or runner.get("outcome") != "process_completed"
        or type(runner.get("returncode")) is not int
        or runner["returncode"] != 0
        or runner.get("audit_status") != capture["status"]
        or any(
            runner.get(key) is not True
            for key in (
                "native_process_launched",
                "original_sources_unchanged",
                "copied_brep_unchanged",
                "snapshots_unchanged",
                "launcher_snapshot_unchanged",
                "report_exists",
            )
        )
    ):
        raise ValueError("native optodisk source/worker/launcher evidence binding differs")
    validate_recorded_isolation(capture["runtime_isolation"])
    rows = capture.get("routes")
    if (
        not isinstance(rows, list)
        or len(rows) != 3
        or {row.get("route") for row in rows} != set(expected)
    ):
        raise ValueError("native optodisk comparison needs all three distinct declared routes")
    summaries = []
    for row in rows:
        if (
            row["settings"] != expected[row["route"]]
            or row.get("fresh_shape_per_route") is not True
        ):
            raise ValueError("native optodisk route settings/fresh-shape declaration differs")
        if row.get("mesh_repaired") is not False or row.get("print_qualified") is not False:
            raise ValueError("native optodisk route cannot claim repair or qualification")
        if type(row.get("native_shape_valid")) is not bool:
            raise ValueError("native optodisk shape validity must preserve a boolean observation")
        points, faces = row["points_mm"], row["faces"]
        raw = boundary_snapshot(points, faces)
        binary = boundary_snapshot([tuple(column["float32"](x) for x in p) for p in points], faces)
        for key, calculated in (("raw_topology", raw), ("binary32_topology", binary)):
            if json.dumps(calculated, sort_keys=True) != json.dumps(row.get(key), sort_keys=True):
                raise ValueError("native optodisk topology summary differs from retained arrays")
        descriptor = row["draft_stl"]
        filename = row["route"] + "_DRAFT_NOT_QUALIFIED.stl"
        if descriptor.get("filename") != filename or filename not in exports:
            raise ValueError("native optodisk export filename/availability differs")
        data = exports[filename]
        if descriptor.get("sha256") != _sha(data) or descriptor.get("bytes") != len(data):
            raise ValueError("native optodisk export byte binding differs")
        stl_data = stl_boundary(data)
        solid = _helper("probe_thor_solid_properties_freecad.py")
        expected_bytes = solid["binary_stl"](points, faces)
        correspondence = compare_stl_geometry(data, expected_bytes)
        if not correspondence["oriented_cyclic_triangle_multisets_exactly_equal"]:
            raise ValueError("native optodisk STL geometry differs from retained arrays")
        summaries.append(
            {
                "route": row["route"],
                "settings": row["settings"],
                "native_shape_valid": row["native_shape_valid"],
                "raw_topology": raw,
                "binary32_topology": binary,
                "draft_stl": descriptor,
                "stl_mesh_audit": stl_data["mesh_audit"],
                "upstream_discrete_geometry_comparison": compare_stl_geometry(data, upstream),
                "export_geometry_matches_retained_arrays": True,
                "export_bytes_reproduce_exactly_on_this_host": data == expected_bytes,
                "candidate_scope": (
                    "different tessellation diagnostic; not source-history repair, "
                    "surface fidelity or print qualification"
                ),
            }
        )
    return {
        "capture_raw_sha256": _sha(capture_raw),
        "runner_raw_sha256": _sha(runner_raw),
        "contract_raw_sha256": _sha(contract_raw),
        "executed_worker_sha256": capture["capture_script_sha256"],
        "runtime_isolation": capture["runtime_isolation"],
        "freecad_version": capture["freecad_version"],
        "opencascade_version": capture["opencascade_version"],
        "source_unchanged": True,
        "open_document_count_before": 0,
        "open_document_count_after": 0,
        "routes": summaries,
        "coherent_receipts_alone_authenticate_native_execution": False,
        "source_cause_proven": False,
        "mesh_repaired": False,
        "fabrication_release": False,
    }


def host_report(native_stl, upstream_stl, full_audit_raw, full_request_raw):
    from raftel_arm01.engineering.scenarios import _strict_json

    audit, request = _strict_json(full_audit_raw), _strict_json(full_request_raw)
    if (
        audit.get("source_revision") != SOURCE_REVISION
        or request.get("source_revision") != SOURCE_REVISION
    ):
        raise ValueError("full audit/request revision differs from pinned source")
    rows = [
        row
        for row in audit.get("selections", [])
        if row.get("installed_asset_id") == "Art23Optodisk::Body"
    ]
    selected = [
        row
        for row in request.get("selections", [])
        if row.get("source_file") == "freecad-src/Art23Optodisk.fcstd"
    ]
    if len(rows) != 1 or len(selected) != 1:
        raise ValueError("full evidence needs exactly one optodisk selection")
    row, selection = rows[0], selected[0]
    if any(
        selection.get(key) != value
        for key, value in {
            "source_sha256": SOURCE_SHA256,
            "brep_sha256": BREP_SHA256,
            "object_name": "Body",
            "object_type": "PartDesign::Body",
            "brep_entry": "PartShape.brp",
        }.items()
    ):
        raise ValueError("optodisk source/BRep/object pin differs")
    if any(
        row.get("source_binding", {}).get(key) != selection[key]
        for key in (
            "source_file",
            "source_sha256",
            "object_name",
            "object_type",
            "brep_entry",
            "brep_sha256",
        )
    ):
        raise ValueError("full audit source binding differs from the pinned request")
    if (
        row["native_export"]["sha256"] != _sha(native_stl)
        or _sha(upstream_stl) != UPSTREAM_SHA256
        or audit.get("full_request_raw_sha256") != _sha(full_request_raw)
        or row.get("selection_id") != selection.get("selection_id")
        or type(row.get("installed_quantity")) is not int
        or row["installed_quantity"] != 2
    ):
        raise ValueError("STL/request/quantity binding differs from full evidence")
    return {
        "schema_version": 1,
        "evidence_class": "host_optodisk_boundary_diagnostic_not_repair_or_qualification",
        "source_revision": SOURCE_REVISION,
        "source_binding": row["source_binding"],
        "full_audit_raw_sha256": _sha(full_audit_raw),
        "full_request_raw_sha256": _sha(full_request_raw),
        "installed_quantity": 2,
        "coordinate_frame": row["coordinate_frame"],
        "native_export": stl_boundary(native_stl),
        "preserved_upstream_stl": stl_boundary(upstream_stl),
        "geometry_equivalence_proven": False,
        "source_cause_proven": False,
        "mesh_repaired": False,
        "fabrication_release": False,
    }


def native_capture():
    if os.environ.get(FLAG) != "1":
        raise ValueError("native optodisk probe requires explicit opt-in")
    _no_conflicting_flags()
    root = Path(os.environ["RAFTEL_OPTODISK_RUN_DIR"]).resolve(strict=True)
    source = Path(os.environ["RAFTEL_OPTODISK_BREP"]).resolve(strict=True)
    output = Path(os.environ["RAFTEL_OPTODISK_REPORT"]).resolve()
    if not source.is_relative_to(root) or not output.is_relative_to(root):
        raise ValueError("copied source/report must stay in isolated run root")
    if output.exists() or output.suffix.lower() != ".json" or source == output:
        raise ValueError("native report must use a new distinct JSON path")
    if _sha(_read(source)) != BREP_SHA256:
        raise ValueError("cached optodisk BRep differs from the pinned source")
    if shutil.disk_usage(root).free < 50 * 1024**3:
        raise ValueError("native optodisk probe requires50GiB free")
    import FreeCAD as App
    import MeshPart
    import Part

    audit = _helper("audit_freecad_assembly.py")
    column = _helper("diagnose_thor_column_mesh.py")
    solid = _helper("probe_thor_solid_properties_freecad.py")
    isolation = audit["_runtime_isolation"](App, root)
    writer = audit["ReportWriter"](output)
    report = {
        "schema_version": 1,
        "evidence_class": "native_cached_optodisk_tessellation_diagnostic_not_repair",
        "status": "started",
        "source_brep_sha256_before": _sha(_read(source)),
        "capture_script_sha256": _sha(_read(Path(__file__))),
        "runtime_isolation": isolation,
        "freecad_version": list(App.Version()),
        "opencascade_version": Part.OCC_VERSION,
        "open_document_count_before": len(App.listDocuments()),
        "routes": [],
        "errors": [],
    }
    writer(report)
    meshroot = root / "draft-stl"
    meshroot.mkdir(exist_ok=False)
    try:
        for route, linear, angular in (
            ("MeshPart_original", 0.1, 0.2),
            ("Part_linear_only", 0.1, None),
            ("MeshPart_refined", 0.025, 0.1),
        ):
            shape = Part.Shape()
            shape.read(str(source))
            if angular is None:
                vertices, faces = shape.tessellate(linear)
            else:
                mesh = MeshPart.meshFromShape(
                    Shape=shape, LinearDeflection=linear, AngularDeflection=angular, Relative=False
                )
                vertices, faces = mesh.Topology
            points = [tuple(float(x) for x in p) for p in vertices]
            faces = [tuple(face) for face in faces]
            rounded = [tuple(column["float32"](x) for x in p) for p in points]
            binary = solid["binary_stl"](points, faces)
            filename = route + "_DRAFT_NOT_QUALIFIED.stl"
            with (meshroot / filename).open("xb") as stream:
                stream.write(binary)
            report["routes"].append(
                {
                    "route": route,
                    "settings": {
                        "linear_deflection_mm": linear,
                        "angular_deflection_rad": angular,
                        "relative": False,
                    },
                    "fresh_shape_per_route": True,
                    "native_shape_valid": shape.isValid(),
                    "raw_topology": boundary_snapshot(points, faces),
                    "binary32_topology": boundary_snapshot(rounded, faces),
                    "points_mm": points,
                    "faces": faces,
                    "draft_stl": {
                        "filename": filename,
                        "bytes": len(binary),
                        "sha256": _sha(binary),
                    },
                    "print_qualified": False,
                    "mesh_repaired": False,
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
    report["document_opened_recomputed_or_saved"] = False
    report["mesh_repaired"] = False
    report["fabrication_release"] = False
    if not report["source_unchanged"] or report["open_document_count_after"]:
        report["status"] = "failed_source_or_document_preservation"
    writer(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("native-stl", "upstream-stl", "full-audit", "full-request", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.suffix.lower() != ".json":
            raise ValueError("output must use a new JSON path")
        report = host_report(
            *[
                _read(path)
                for path in (args.native_stl, args.upstream_stl, args.full_audit, args.full_request)
            ]
        )
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Optodisk diagnostic failed: {error}", file=sys.stderr)
        return 2


if os.environ.get(FLAG) == "1":
    native_capture()
elif __name__ == "__main__":
    raise SystemExit(main())
