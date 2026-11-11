"""Analytic exact-boundary fixtures and native opt-in guards; no native launch."""

import copy
import hashlib
import json
import runpy
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = runpy.run_path(str(Path(__file__).parents[1] / "tools/diagnose_thor_optodisk_mesh.py"))


@pytest.fixture(autouse=True)
def tool_path(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "tools"))


def square():
    return [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(0, 1, 2), (0, 2, 3)]


def tetra():
    return [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)], [
        (0, 2, 1),
        (0, 1, 3),
        (1, 2, 3),
        (2, 0, 3),
    ]


def binary_fixture():
    points, faces = square()
    raw = bytearray(b"synthetic boundary fixture".ljust(80, b"\0") + struct.pack("<I", len(faces)))
    for face in faces:
        raw.extend(struct.pack("<12fH", 0, 0, 1, *(x for i in face for x in points[i]), 0))
    return bytes(raw)


def test_square_has_one_four_edge_cycle_and_unit_projected_area():
    report = TOOLS["boundary_snapshot"](*square())
    assert len(report["boundary_edges"]) == 4
    component = report["boundary_components"][0]
    assert component["graph_simple_cycle"] is True
    assert component["vertex_degrees"] == [2, 2, 2, 2]
    assert component["axis_ranges_mm"] == [1, 1, 0]
    assert component["vector_area_magnitude_mm2"] == 1
    assert report["boundary_edges_filled"] is False


def test_closed_tetra_has_no_boundary():
    report = TOOLS["boundary_snapshot"](*tetra())
    assert report["boundary_edges"] == []
    assert report["boundary_components"] == []


def test_planar_bow_tie_has_an_exact_proper_boundary_crossing():
    loop = [(0.0, 0.0, 5.0), (1.0, 1.0, 5.0), (0.0, 1.0, 5.0), (1.0, 0.0, 5.0)]
    result = TOOLS["planar_boundary_crossings"](loop)
    assert result["tested"] is True
    assert result["proper_crossings"] == [
        {
            "cycle_edge_indices": [0, 2],
            "first_segment_parameter": 0.5,
            "second_segment_parameter": 0.5,
            "intersection_mm": [0.5, 0.5, 5.0],
        }
    ]
    assert result["full_triangle_self_intersections_checked"] is False


def test_square_has_no_proper_crossings_and_contact_is_not_a_proper_cross():
    points, _ = square()
    assert TOOLS["planar_boundary_crossings"](points)["proper_crossings"] == []
    touch = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.5, 0.0, 0.0)]
    assert TOOLS["planar_boundary_crossings"](touch)["proper_crossings"] == []


def test_nonplanar_or_large_cycle_is_explicitly_unchecked():
    for loop in (None, [(0, 0, 0)] * 129, [(0, 0, 0), (1, 1, 0), (0, 1, 1), (1, 0, 1)]):
        assert TOOLS["planar_boundary_crossings"](loop)["tested"] is False


def test_disconnected_boundary_cycles_are_retained_separately():
    points, faces = square()
    more = [(x + 3, y, z) for x, y, z in points]
    result = TOOLS["boundary_snapshot"](
        points + more, faces + [tuple(i + 4 for i in f) for f in faces]
    )
    assert len(result["boundary_components"]) == 2
    assert all(c["vector_area_magnitude_mm2"] == 1 for c in result["boundary_components"])


def test_branching_boundary_is_not_presented_as_one_simple_cycle():
    points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)]
    report = TOOLS["boundary_snapshot"](points, [(0, 1, 2), (0, 3, 4)])
    assert len(report["boundary_components"]) == 1
    assert report["boundary_components"][0]["graph_simple_cycle"] is False
    assert report["boundary_components"][0]["ordered_cycle_mm"] is None


def test_unindexed_stl_reuses_existing_topology_audit():
    result = TOOLS["stl_boundary"](binary_fixture())
    assert result["mesh_audit"]["topology"]["boundary_edges"] == 4
    assert len(result["boundary_diagnostic"]["boundary_edges"]) == 4


def evidence(monkeypatch):
    raw = binary_fixture()
    sha = hashlib.sha256(raw).hexdigest()
    monkeypatch.setitem(TOOLS["host_report"].__globals__, "UPSTREAM_SHA256", sha)
    selection = {
        "selection_id": "synthetic-optodisk",
        "source_file": "freecad-src/Art23Optodisk.fcstd",
        "source_sha256": TOOLS["SOURCE_SHA256"],
        "brep_sha256": TOOLS["BREP_SHA256"],
        "object_name": "Body",
        "object_type": "PartDesign::Body",
        "brep_entry": "PartShape.brp",
    }
    request = {"source_revision": TOOLS["SOURCE_REVISION"], "selections": [selection]}
    request_raw = json.dumps(request).encode()
    row = {
        "selection_id": "synthetic-optodisk",
        "installed_asset_id": "Art23Optodisk::Body",
        "source_binding": copy.deepcopy(selection),
        "installed_quantity": 2,
        "native_export": {"sha256": sha},
        "coordinate_frame": "synthetic saved BRep frame",
    }
    audit = {
        "source_revision": TOOLS["SOURCE_REVISION"],
        "full_request_raw_sha256": hashlib.sha256(request_raw).hexdigest(),
        "selections": [row],
    }
    return raw, request_raw, audit


def test_host_report_keeps_boundaries_and_release_unknown(monkeypatch):
    raw, request_raw, audit = evidence(monkeypatch)
    report = TOOLS["host_report"](raw, raw, json.dumps(audit).encode(), request_raw)
    assert report["installed_quantity"] == 2
    assert report["fabrication_release"] is False
    assert report["geometry_equivalence_proven"] is False
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize(
    "change", ["bytes", "request", "quantity", "quantity_bool", "source", "duplicate"]
)
def test_stale_pins_and_quantity_substitution_reject(monkeypatch, change):
    raw, request_raw, audit = evidence(monkeypatch)
    native = raw
    if change == "bytes":
        native += b"changed"
    elif change == "request":
        audit["full_request_raw_sha256"] = "a" * 64
    elif change == "quantity":
        audit["selections"][0]["installed_quantity"] = 3
    elif change == "quantity_bool":
        audit["selections"][0]["installed_quantity"] = True
    elif change == "source":
        audit["selections"][0]["source_binding"]["brep_sha256"] = "a" * 64
    else:
        audit["selections"].append(copy.deepcopy(audit["selections"][0]))
    with pytest.raises(ValueError):
        TOOLS["host_report"](native, raw, json.dumps(audit).encode(), request_raw)


def test_native_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv(TOOLS["FLAG"], raising=False)
    with pytest.raises(ValueError, match="explicit opt-in"):
        TOOLS["native_capture"]()


@pytest.mark.parametrize("flag", TOOLS["CONFLICTING_FLAGS"])
def test_conflicting_native_helper_flags_reject_before_paths_or_imports(monkeypatch, flag):
    monkeypatch.setenv(TOOLS["FLAG"], "1")
    monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match="conflicting"):
        TOOLS["native_capture"]()


def native_paths(tmp_path, monkeypatch):
    source = tmp_path / "source.brep"
    source.write_bytes(b"synthetic BRep guard fixture")
    output = tmp_path / "new.json"
    monkeypatch.setenv(TOOLS["FLAG"], "1")
    monkeypatch.setenv("RAFTEL_OPTODISK_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("RAFTEL_OPTODISK_BREP", str(source))
    monkeypatch.setenv("RAFTEL_OPTODISK_REPORT", str(output))
    return source, output


def test_native_existing_output_is_preserved(tmp_path, monkeypatch):
    _, output = native_paths(tmp_path, monkeypatch)
    output.write_bytes(b"existing")
    with pytest.raises(ValueError, match="new distinct"):
        TOOLS["native_capture"]()
    assert output.read_bytes() == b"existing"


def test_native_wrong_brep_rejects_before_imports(tmp_path, monkeypatch):
    _, output = native_paths(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="pinned"):
        TOOLS["native_capture"]()
    assert not output.exists()


def test_native_disk_reserve_rejects_before_imports(tmp_path, monkeypatch):
    source, output = native_paths(tmp_path, monkeypatch)
    monkeypatch.setitem(
        TOOLS["native_capture"].__globals__,
        "BREP_SHA256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        TOOLS["native_capture"].__globals__["shutil"],
        "disk_usage",
        lambda _: SimpleNamespace(free=49 * 1024**3),
    )
    with pytest.raises(ValueError, match="50GiB"):
        TOOLS["native_capture"]()
    assert not output.exists()


def test_discrete_mesh_comparison_retains_orientation_and_multiplicity():
    raw = binary_fixture()
    cyclic = bytearray(raw)
    for offset in range(84, len(raw), 50):
        record = list(struct.unpack_from("<12fH", raw, offset))
        a, b, c = record[3:6], record[6:9], record[9:12]
        struct.pack_into("<12fH", cyclic, offset, *record[:3], *b, *c, *a, record[12])
    result = TOOLS["compare_stl_geometry"](bytes(cyclic), raw)
    assert result["oriented_cyclic_triangle_multisets_exactly_equal"] is True
    assert result["unindexed_vertex_multisets_exactly_equal"] is True
    reversed_raw = bytearray(raw)
    record = list(struct.unpack_from("<12fH", raw, 84))
    a, b, c = record[3:6], record[6:9], record[9:12]
    struct.pack_into("<12fH", reversed_raw, 84, *record[:3], *a, *c, *b, record[12])
    result = TOOLS["compare_stl_geometry"](bytes(reversed_raw), raw)
    assert result["oriented_cyclic_triangle_multisets_exactly_equal"] is False
    assert result["unindexed_vertex_multisets_exactly_equal"] is True
    assert result["candidate_only_oriented_facets"] == 1


def test_discrete_comparison_ignores_headers_and_stored_normals_only():
    raw = binary_fixture()
    altered = bytearray(raw)
    altered[:80] = b"different header".ljust(80, b"\0")
    struct.pack_into("<3f", altered, 84, 1, 0, 0)
    assert (
        TOOLS["compare_stl_geometry"](bytes(altered), raw)[
            "oriented_cyclic_triangle_multisets_exactly_equal"
        ]
        is True
    )
    altered[96:100] = struct.pack("<f", 0.125)
    assert (
        TOOLS["compare_stl_geometry"](bytes(altered), raw)[
            "oriented_cyclic_triangle_multisets_exactly_equal"
        ]
        is False
    )


def native_receipts(monkeypatch):
    points, faces = square()
    topology = TOOLS["boundary_snapshot"](points, faces)
    capture = {
        "schema_version": 1,
        "evidence_class": "native_cached_optodisk_tessellation_diagnostic_not_repair",
        "status": "complete_diagnostic_not_repair",
        "errors": [],
        "source_brep_sha256_before": TOOLS["BREP_SHA256"],
        "source_brep_sha256_after": TOOLS["BREP_SHA256"],
        "source_unchanged": True,
        "capture_script_sha256": "f" * 64,
        "document_opened_recomputed_or_saved": False,
        "mesh_repaired": False,
        "fabrication_release": False,
        "open_document_count_before": 0,
        "open_document_count_after": 0,
        "runtime_isolation": {
            "requested": True,
            "verified": True,
            "root": "/synthetic/run",
            "actual_paths": {
                name: "/synthetic/run/" + name
                for name in (
                    "UserParameter",
                    "SystemParameter",
                    "UserHomePath",
                    "UserAppData",
                    "AppTempPath",
                )
            },
        },
        "freecad_version": [
            "1",
            "1",
            "4",
            "synthetic host fixture",
            "4fd3bf320d9566a27e60069fc8387448aaa3a094",
        ],
        "opencascade_version": "7.8.1",
        "routes": [],
    }
    exports = {}
    raw = binary_fixture()
    monkeypatch.setitem(
        TOOLS["summarize_native"].__globals__, "UPSTREAM_SHA256", hashlib.sha256(raw).hexdigest()
    )
    for route, linear, angular in (
        ("MeshPart_original", 0.1, 0.2),
        ("Part_linear_only", 0.1, None),
        ("MeshPart_refined", 0.025, 0.1),
    ):
        filename = route + "_DRAFT_NOT_QUALIFIED.stl"
        exports[filename] = raw
        capture["routes"].append(
            {
                "route": route,
                "settings": {
                    "linear_deflection_mm": linear,
                    "angular_deflection_rad": angular,
                    "relative": False,
                },
                "fresh_shape_per_route": True,
                "mesh_repaired": False,
                "print_qualified": False,
                "native_shape_valid": True,
                "points_mm": points,
                "faces": faces,
                "raw_topology": topology,
                "binary32_topology": topology,
                "draft_stl": {
                    "filename": filename,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                },
            }
        )
    original = {f"synthetic-{i}": "a" * 64 for i in range(56)}
    original["freecad-src/Art23Optodisk.fcstd"] = TOOLS["SOURCE_SHA256"]
    contract = {
        "schema_version": 1,
        "source_revision": TOOLS["SOURCE_REVISION"],
        "source_archive_sha256": TOOLS["SOURCE_SHA256"],
        "copied_brep_sha256": TOOLS["BREP_SHA256"],
        "executable_sha256": TOOLS["_helper"]("diagnose_thor_column_mesh.py")["RUNTIME_EXE_SHA256"],
        "snapshot_sha256_before": {"diagnose_thor_optodisk_mesh.py": "f" * 64},
        "original_source_sha256_before": original,
    }
    runner = {
        "outcome": "process_completed",
        "returncode": 0,
        "audit_status": capture["status"],
        **{
            key: True
            for key in (
                "native_process_launched",
                "original_sources_unchanged",
                "copied_brep_unchanged",
                "snapshots_unchanged",
                "launcher_snapshot_unchanged",
                "report_exists",
            )
        },
    }
    return capture, runner, contract, exports, raw


def serialized_native(capture, runner, contract, exports, upstream):
    raw = json.dumps(capture).encode()
    runner = dict(runner, native_report_sha256=hashlib.sha256(raw).hexdigest())
    return raw, json.dumps(runner).encode(), json.dumps(contract).encode(), exports, upstream


def test_native_summary_recalculates_scope_arrays_and_discrete_correspondence(monkeypatch):
    summary = TOOLS["summarize_native"](*serialized_native(*native_receipts(monkeypatch)))
    assert len(summary["routes"]) == 3
    assert summary["coherent_receipts_alone_authenticate_native_execution"] is False
    assert summary["fabrication_release"] is False
    assert all(r["export_geometry_matches_retained_arrays"] for r in summary["routes"])


@pytest.mark.parametrize(
    "change",
    [
        "repair",
        "release",
        "docs_bool",
        "version",
        "paths",
        "runner",
        "exe",
        "arrays",
        "topology",
        "settings",
        "route_repair",
        "stl",
    ],
)
def test_native_summary_rejects_coherent_hash_scope_or_array_substitution(change, monkeypatch):
    capture, runner, contract, exports, upstream = native_receipts(monkeypatch)
    if change == "repair":
        capture["mesh_repaired"] = True
    elif change == "release":
        capture["fabrication_release"] = True
    elif change == "docs_bool":
        capture["open_document_count_before"] = False
    elif change == "version":
        capture["freecad_version"] = ["different"]
    elif change == "paths":
        capture["runtime_isolation"]["actual_paths"] = {}
    elif change == "runner":
        runner["snapshots_unchanged"] = False
    elif change == "exe":
        contract["executable_sha256"] = "a" * 64
    elif change == "arrays":
        capture["routes"][0]["points_mm"][0] = (0.125, 0, 0)
    elif change == "topology":
        capture["routes"][0]["raw_topology"] = {}
    elif change == "settings":
        capture["routes"][0]["settings"]["linear_deflection_mm"] = 0.5
    elif change == "route_repair":
        capture["routes"][0]["print_qualified"] = True
    else:
        name = capture["routes"][0]["draft_stl"]["filename"]
        data = bytearray(exports[name])
        struct.pack_into("<f", data, 96, 0.125)
        exports[name] = bytes(data)
        capture["routes"][0]["draft_stl"]["sha256"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(ValueError):
        TOOLS["summarize_native"](*serialized_native(capture, runner, contract, exports, upstream))


@pytest.mark.parametrize(
    "change",
    ["outside_windows", "relative", "dotdot", "root_relative", "requested_false", "upstream_bytes"],
)
def test_native_summary_rejects_escape_or_upstream_substitution(change, monkeypatch):
    capture, runner, contract, exports, upstream = native_receipts(monkeypatch)
    isolation = capture["runtime_isolation"]
    if change == "outside_windows":
        isolation["root"] = r"C:\task\run"
        isolation["actual_paths"] = {
            name: r"C:\task\run" + "\\" + name
            for name in (
                "UserParameter",
                "SystemParameter",
                "UserHomePath",
                "UserAppData",
                "AppTempPath",
            )
        }
        isolation["actual_paths"]["UserParameter"] = r"C:\outside\foreign.cfg"
    elif change == "relative":
        isolation["actual_paths"]["UserParameter"] = "foreign.cfg"
    elif change == "dotdot":
        isolation["actual_paths"]["UserParameter"] = "/synthetic/run/../foreign.cfg"
    elif change == "root_relative":
        isolation["root"] = "synthetic/run"
    elif change == "requested_false":
        isolation["requested"] = False
    else:
        altered = bytearray(upstream)
        altered[0] = ord("X")
        upstream = bytes(altered)
    with pytest.raises(ValueError):
        TOOLS["summarize_native"](*serialized_native(capture, runner, contract, exports, upstream))


def test_recorded_windows_paths_are_checked_independently_of_host_platform():
    isolation = {
        "root": r"C:\Task\Run",
        "actual_paths": {
            name: r"c:\task\run" + "\\" + name
            for name in (
                "UserParameter",
                "SystemParameter",
                "UserHomePath",
                "UserAppData",
                "AppTempPath",
            )
        },
    }
    TOOLS["validate_recorded_isolation"](isolation)
