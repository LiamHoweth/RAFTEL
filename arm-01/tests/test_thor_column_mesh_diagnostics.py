"""Analytic incidence/precision fixtures; no native process or actual STL needed."""

import copy
import hashlib
import json
import math
import runpy
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = runpy.run_path(str(Path(__file__).parents[1] / "tools/diagnose_thor_column_mesh.py"))


@pytest.fixture(autouse=True)
def tool_import_path(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "tools"))


def tetra_faces(offset=0):
    return [
        tuple(i + offset for i in face) for face in ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3))
    ]


def test_closed_tetrahedron_has_no_nonmanifold_incidence():
    points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    result = TOOLS["topology_snapshot"](points, tetra_faces())
    assert result["boundary_edge_count"] == 0
    assert result["nonmanifold_edge_count"] == 0
    assert result["used_index_count"] == result["exact_coordinate_count"] == 4


def test_two_closed_shells_touching_an_edge_have_four_incident_faces():
    points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (0, -1, 0), (0, 0, -1)]
    faces = tetra_faces() + [(0, 4, 1), (0, 1, 5), (1, 4, 5), (4, 0, 5)]
    result = TOOLS["topology_snapshot"](points, faces)
    assert result["boundary_edge_count"] == 0
    assert result["nonmanifold_edge_count"] == 1
    edge = result["nonmanifold_edges"][0]
    assert edge["length_mm"] == 1
    assert edge["incidence_count"] == 4
    assert len({row["facet_index_zero_based"] for row in edge["incident_facets"]}) == 4
    assert all(row["area_mm2"] == 0.5 for row in edge["incident_facets"])


def test_float32_can_merge_distinct_edges_without_erasing_nonzero_facets():
    points = [
        (8.6, 5, 17),
        (8.6, 5, 18),
        (9, 6, 17),
        (9, 5, 17),
        (8.6000001, 5, 17),
        (8.6000001, 5, 18),
        (8, 4, 17),
        (8, 5, 17),
    ]
    faces = tetra_faces() + tetra_faces(4)
    assert TOOLS["topology_snapshot"](points, faces)["nonmanifold_edge_count"] == 0
    rounded = [tuple(TOOLS["float32"](v) for v in point) for point in points]
    result = TOOLS["topology_snapshot"](rounded, faces)
    assert result["nonmanifold_edge_count"] == 1
    assert result["used_index_count"] == 8
    assert result["used_exact_coordinate_count"] == 6
    assert all(row["area_mm2"] > 0 for row in result["nonmanifold_edges"][0]["incident_facets"])


@pytest.mark.parametrize("value", [17.0, -17.0, 8.5, -8.5, 0.0, -0.0])
def test_float32_neighbors_are_ordered_and_exactly_representable(value):
    result = TOOLS["float32_neighborhood"](value)
    assert result["previous_binary32"] < value < result["next_binary32"]
    assert result["rounding_absolute_error"] == 0
    for key in ("previous_binary32", "next_binary32"):
        assert TOOLS["float32"](result[key]) == result[key]
    if abs(value) == 17:
        assert result["adjacent_spacing_max"] == 2**-19


@pytest.mark.parametrize("value", [math.nan, math.inf, True, "17", 10**1000, 1e300])
def test_invalid_or_unrepresentable_coordinate_rejects(value):
    with pytest.raises(ValueError):
        TOOLS["float32_neighborhood"](value)


@pytest.mark.parametrize("faces", [[(0, 1)], [(0, 1, 4)], [(0, True, 2)], [(0, -1, 2)]])
def test_malformed_faces_reject(faces):
    with pytest.raises(ValueError):
        TOOLS["topology_snapshot"]([(0, 0, 0), (1, 0, 0), (0, 1, 0)], faces)


def binary_tetrahedron():
    points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    raw = bytearray(b"synthetic incidence fixture".ljust(80, b"\0") + struct.pack("<I", 4))
    for face in tetra_faces():
        raw.extend(struct.pack("<12fH", 0, 0, 0, *(x for i in face for x in points[i]), 0))
    return bytes(raw)


def synthetic_bindings(monkeypatch):
    raw = binary_tetrahedron()
    sha = hashlib.sha256(raw).hexdigest()
    monkeypatch.setitem(TOOLS["build_report"].__globals__, "UPSTREAM_STL_SHA256", sha)
    capture = {
        "source_revision": TOOLS["SOURCE_REVISION"],
        "selections": [
            {
                "selection_id": "art4-transmission-column",
                "source_binding": {
                    "source_file": "freecad-src/Art4TransmissionColumn.fcstd",
                    "source_sha256": TOOLS["SOURCE_SHA256"],
                    "object_name": "Body",
                    "object_type": "PartDesign::Body",
                    "brep_entry": "PartShape1.brp",
                    "brep_sha256": TOOLS["BREP_SHA256"],
                },
                "draft_stl": {"sha256": sha, "vertex_count_before_STL_unindexing": 4},
                "coordinate_frame": "synthetic fixture frame",
                "cached_shape_properties": {"native_shape_valid": True},
            }
        ],
    }
    capture_raw = json.dumps(capture).encode()
    audit_raw = json.dumps(
        {"input_bindings": {"native_capture_raw_sha256": hashlib.sha256(capture_raw).hexdigest()}}
    ).encode()
    return raw, capture, capture_raw, audit_raw


def test_host_report_preserves_scope_and_finite_exact_geometry(monkeypatch):
    raw, _, capture_raw, audit_raw = synthetic_bindings(monkeypatch)
    report = TOOLS["build_report"](raw, raw, capture_raw, audit_raw)
    assert report["interpretation"]["fabrication_release"] is False
    assert report["interpretation"]["mesh_repaired"] is False
    assert report["interpretation"]["four_triangles_per_defect_edge_is_observed"] is False
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize(
    "change", ["native_bytes", "capture_binding", "source_brep", "source_object", "upstream_bytes"]
)
def test_stale_geometry_or_evidence_pins_reject(monkeypatch, change):
    raw, capture, capture_raw, audit_raw = synthetic_bindings(monkeypatch)
    native_raw, upstream_raw = raw, raw
    if change == "native_bytes":
        native_raw = raw + b"changed"
    elif change == "capture_binding":
        audit_raw = b'{"input_bindings":{"native_capture_raw_sha256":"stale"}}'
    elif change in {"source_brep", "source_object"}:
        capture = copy.deepcopy(capture)
        key = "brep_sha256" if change == "source_brep" else "object_name"
        capture["selections"][0]["source_binding"][key] = "changed"
        capture_raw = json.dumps(capture).encode()
    else:
        upstream_raw = raw + b"changed"
    with pytest.raises(ValueError):
        TOOLS["build_report"](native_raw, upstream_raw, capture_raw, audit_raw)


def test_native_capture_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv(TOOLS["FLAG"], raising=False)
    with pytest.raises(ValueError, match="explicit opt-in"):
        TOOLS["native_capture"]()


def test_conflicting_helper_opt_in_rejects_before_import_or_file_access(monkeypatch):
    monkeypatch.setenv(TOOLS["FLAG"], "1")
    monkeypatch.setenv("RAFTEL_RUN_FREECAD_AUDIT", "1")
    with pytest.raises(ValueError, match="conflicting assembly-audit"):
        TOOLS["native_capture"]()


def native_paths(tmp_path, monkeypatch):
    source = tmp_path / "column.brep"
    source.write_bytes(b"synthetic copied BRep guard fixture, never native geometry")
    output = tmp_path / "new-report.json"
    monkeypatch.setenv(TOOLS["FLAG"], "1")
    monkeypatch.setenv("RAFTEL_COLUMN_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("RAFTEL_COLUMN_BREP", str(source))
    monkeypatch.setenv("RAFTEL_COLUMN_REPORT", str(output))
    return source, output


def test_native_existing_report_is_preserved_before_runtime_import(tmp_path, monkeypatch):
    _, output = native_paths(tmp_path, monkeypatch)
    output.write_bytes(b"existing evidence")
    with pytest.raises(ValueError, match="new distinct"):
        TOOLS["native_capture"]()
    assert output.read_bytes() == b"existing evidence"


def test_native_wrong_brep_rejects_before_runtime_import(tmp_path, monkeypatch):
    _, output = native_paths(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="pinned column BRep"):
        TOOLS["native_capture"]()
    assert not output.exists()


@pytest.mark.parametrize("escape", ["source", "output"])
def test_native_input_or_report_escape_rejects(tmp_path, monkeypatch, escape):
    root = tmp_path / "run"
    root.mkdir()
    source, _ = native_paths(root, monkeypatch)
    outside = tmp_path / "outside.brep"
    outside.write_bytes(source.read_bytes())
    if escape == "source":
        monkeypatch.setenv("RAFTEL_COLUMN_BREP", str(outside))
    else:
        monkeypatch.setenv("RAFTEL_COLUMN_REPORT", str(tmp_path / "outside.json"))
    with pytest.raises(ValueError, match="stay inside"):
        TOOLS["native_capture"]()


def test_native_reserve_guard_is_retained(tmp_path, monkeypatch):
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
    with pytest.raises(ValueError, match="50 GiB"):
        TOOLS["native_capture"]()
    assert not output.exists()


def test_native_actual_configuration_escape_rejects_before_shape_import(tmp_path, monkeypatch):
    source, output = native_paths(tmp_path, monkeypatch)
    monkeypatch.setitem(
        TOOLS["native_capture"].__globals__,
        "BREP_SHA256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        TOOLS["native_capture"].__globals__["shutil"],
        "disk_usage",
        lambda _: SimpleNamespace(free=64 * 1024**3),
    )
    monkeypatch.setitem(
        sys.modules,
        "FreeCAD",
        SimpleNamespace(
            ConfigGet=lambda _: str(tmp_path.parent / "outside"), listDocuments=lambda: {}
        ),
    )
    for name in ("MeshPart", "Part"):
        monkeypatch.setitem(sys.modules, name, SimpleNamespace())
    with pytest.raises(ValueError, match="escaped"):
        TOOLS["native_capture"]()
    assert not output.exists()


def native_receipt_fixture():
    points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    faces = tetra_faces()
    topology = TOOLS["topology_snapshot"](points, faces)
    capture = {
        "schema_version": 1,
        "evidence_class": "native_cached_BRep_mesh_precision_diagnostic_not_repair",
        "status": "complete_diagnostic_not_repair",
        "errors": [],
        "source_brep_sha256_before": TOOLS["BREP_SHA256"],
        "source_brep_sha256_after": TOOLS["BREP_SHA256"],
        "source_unchanged": True,
        "capture_script_sha256": "f" * 64,
        "open_document_count_before": 0,
        "open_document_count_after": 0,
        "runtime_isolation": {
            "verified": True,
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
        "document_opened_recomputed_or_saved": False,
        "mesh_repaired": False,
        "fabrication_release": False,
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
    for name in ("MeshPart_same_settings", "Part_tessellate_linear_only"):
        capture["routes"].append(
            {
                "route": name,
                "points_mm": points,
                "faces": faces,
                "raw_topology": topology,
                "binary32_rounded_topology": topology,
                "coordinate_count": 12,
                "coordinates_already_binary32_count": 12,
                "settings_comparability": "synthetic host fixture, not an actual native run",
                "native_shape_valid": True,
            }
        )
    launch = {
        "native_process_launched": True,
        "outcome": "process_completed",
        "returncode": 0,
        "audit_status": capture["status"],
        "original_sources_unchanged": True,
        "copied_brep_unchanged": True,
        "snapshots_unchanged": True,
        "launcher_snapshot_unchanged": True,
        "report_exists": True,
    }
    originals = {f"synthetic-{i}": "a" * 64 for i in range(56)}
    originals["freecad-src/Art4TransmissionColumn.fcstd"] = TOOLS["SOURCE_SHA256"]
    contract = {
        "schema_version": 1,
        "source_revision": TOOLS["SOURCE_REVISION"],
        "source_archive_sha256": TOOLS["SOURCE_SHA256"],
        "copied_brep_sha256": TOOLS["BREP_SHA256"],
        "executable_sha256": TOOLS["RUNTIME_EXE_SHA256"],
        "snapshot_sha256_before": {"diagnose_thor_column_mesh.py": "f" * 64},
        "original_source_sha256_before": originals,
    }
    return capture, launch, contract


def serialize_native_fixture(capture, launch, contract):
    raw = json.dumps(capture).encode()
    launch = dict(launch, native_report_sha256=hashlib.sha256(raw).hexdigest())
    return raw, json.dumps(launch).encode(), json.dumps(contract).encode()


def test_native_receipt_summary_recalculates_arrays_without_authentication_claim():
    report = TOOLS["summarize_native_precision"](
        *serialize_native_fixture(*native_receipt_fixture())
    )
    assert report["coherent_receipts_alone_authenticate_native_execution"] is False
    assert report["mesh_repaired"] is False
    assert report["fabrication_release"] is False
    assert len(report["routes"]) == 2


@pytest.mark.parametrize(
    "key,value",
    [
        ("mesh_repaired", True),
        ("mesh_repaired", None),
        ("fabrication_release", True),
        ("fabrication_release", None),
        ("schema_version", True),
        ("evidence_class", "different"),
        ("open_document_count_before", False),
        ("open_document_count_after", 1),
        ("source_brep_sha256_after", "a" * 64),
        ("freecad_version", ["different"]),
        ("opencascade_version", "different"),
    ],
)
def test_native_summary_rejects_scope_changes_even_with_consistent_capture_hash(key, value):
    capture, launch, contract = native_receipt_fixture()
    capture[key] = value
    with pytest.raises(ValueError):
        TOOLS["summarize_native_precision"](*serialize_native_fixture(capture, launch, contract))


@pytest.mark.parametrize(
    "change",
    [
        "arrays",
        "summary",
        "count_bool",
        "source_ledger",
        "exe",
        "worker",
        "launcher",
        "hash",
        "paths",
    ],
)
def test_native_summary_rejects_tampered_arrays_and_evidence_bindings(change):
    capture, launch, contract = native_receipt_fixture()
    if change == "arrays":
        capture["routes"][0]["points_mm"][0] = (0.1, 0.0, 0.0)
    elif change == "summary":
        capture["routes"][0]["raw_topology"] = dict(
            capture["routes"][0]["raw_topology"], boundary_edge_count=4
        )
    elif change == "count_bool":
        capture["routes"][0]["coordinate_count"] = True
    elif change == "source_ledger":
        contract["original_source_sha256_before"] = {}
    elif change == "exe":
        contract["executable_sha256"] = "a" * 64
    elif change == "worker":
        capture["capture_script_sha256"] = "a" * 64
    elif change == "launcher":
        launch["copied_brep_unchanged"] = False
    elif change == "paths":
        capture["runtime_isolation"]["actual_paths"] = {}
    serialized = list(serialize_native_fixture(capture, launch, contract))
    if change == "hash":
        altered = json.loads(serialized[1])
        altered["native_report_sha256"] = "a" * 64
        serialized[1] = json.dumps(altered).encode()
    with pytest.raises(ValueError):
        TOOLS["summarize_native_precision"](*serialized)
