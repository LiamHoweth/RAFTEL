"""Host provenance/topology guards on explicitly synthetic capture fixtures."""

import copy
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
for name in ("thor_slicer_plan", "audit_thor_native_meshes"):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
audit = sys.modules["audit_thor_native_meshes"]


def tetrahedron(*, open_face=False, scale=1.0):
    points = ((0.0, 0.0, 0.0), (scale, 0.0, 0.0), (0.0, scale, 0.0), (0.0, 0.0, scale))
    faces = ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))
    if open_face:
        faces = faces[:-1]
    return (
        b"Synthetic unit fixture, not actual native execution".ljust(80, b" ")
        + struct.pack("<I", len(faces))
        + b"".join(
            struct.pack(
                "<12fH", 0.0, 0.0, 0.0, *(value for index in face for value in points[index]), 0
            )
            for face in faces
        )
    )


@pytest.fixture
def capture(tmp_path):
    parent = json.loads((ROOT / "hardware/print-planning/thor-draft-plan-v1.json").read_bytes())
    source = {
        "source_file": "freecad-src/BaseTop.fcstd",
        "source_sha256": "1" * 64,
        "object_name": "Body",
        "object_type": "PartDesign::Body",
        "brep_entry": "PartShape.brp",
        "brep_sha256": "2" * 64,
    }
    placement = {"position_mm": [0.0, 0.0, 0.0], "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]}
    settings = {
        "linear_deflection_mm": 0.1,
        "angular_deflection_rad": 0.2,
        "relative": False,
        "filename": "base-top-fixture.stl",
    }
    selection = {
        "selection_id": "base-top",
        **source,
        "xml_placement": placement,
        "uniform_density": None,
        "tessellation": settings,
        "reference_capture": {
            "input_canonical_sha256": {"upstream_slicer_plan": audit.canonical_sha256(parent)}
        },
    }
    request = {
        "schema_version": 1,
        "evidence_class": "selected_saved_BRep_properties_request",
        "source_revision": audit.stl.SOURCE_REVISION,
        "selections": [selection],
    }
    request_raw = (json.dumps(request, indent=2) + "\n").encode()
    request_hash = hashlib.sha256(request_raw).hexdigest()
    mesh = tetrahedron()
    (tmp_path / settings["filename"]).write_bytes(mesh)
    export = {
        "filename": settings["filename"],
        "sha256": hashlib.sha256(mesh).hexdigest(),
        "bytes": len(mesh),
        "units": "mm",
        "frame": audit.FRAME,
        "encoding": "binary_STL",
        "triangle_count": 4,
        "tessellation": settings,
    }
    native = {
        "schema_version": 1,
        "evidence_class": audit.CAPTURE_CLASS,
        "audit_status": "complete_selected_cached_geometry_only",
        "source_revision": audit.stl.SOURCE_REVISION,
        "request_sha256": request_hash,
        "request": request,
        "capture_script_sha256": "3" * 64,
        "coordinate_frame": audit.FRAME,
        "cross_asset_aggregation_performed": False,
        "document_opened_or_recomputed": False,
        "native_document_saved": False,
        "source_copy_sha256_before": {source["source_file"]: source["source_sha256"]},
        "source_copy_sha256_after": {source["source_file"]: source["source_sha256"]},
        "input_copy_bytes_unchanged": True,
        "runtime_isolated_paths_verified": True,
        "open_document_count_before": 0,
        "open_document_count_after": 0,
        "errors": [],
        "freecad_version": ["synthetic_fixture_not_runtime"],
        "primitive_fixtures": {
            "summary": {
                "verified": True,
                "case_count": 9,
                "maximum_relative_volume_error": 0.0,
                "maximum_com_error_mm": 0.0,
                "maximum_relative_tensor_error": 0.0,
            }
        },
        "selections": [
            {
                "selection_id": "base-top",
                "source_binding": {**source, "xml_placement_not_applied": placement},
                "coordinate_frame": audit.FRAME,
                "cached_shape_properties": {
                    "native_shape_valid": True,
                    "aggregate": {"volume_mm3": 1 / 6, "com_mm": [0.25] * 3},
                    "native_bounds_mm": {
                        "XMin": 0.0,
                        "XMax": 1.0,
                        "YMin": 0.0,
                        "YMax": 1.0,
                        "ZMin": 0.0,
                        "ZMax": 1.0,
                    },
                    "raw_shape_placement_matrix_not_reapplied": [
                        float(i == j) for i in range(4) for j in range(4)
                    ],
                },
                "draft_stl": export,
            }
        ],
    }
    launch = {
        "native_process_launched": True,
        "request_snapshot_sha256": request_hash,
        "worker_snapshot_sha256": "3" * 64,
        "outcome": "process_completed",
        "returncode": 0,
        "audit_status": native["audit_status"],
        "errors": [],
        "original_source_bytes_unchanged": True,
        "worker_snapshot_unchanged": True,
        "request_snapshot_unchanged": True,
        "report_exists": True,
        "selected_captures": 1,
        "original_source_sha256_after": native["source_copy_sha256_before"],
    }
    return native, launch, request, parent, tmp_path, request_hash


def evaluate(fixture):
    native, launch, request, parent, root, request_hash = fixture
    return audit.audit_exports(
        native,
        launch,
        request,
        root,
        parent,
        request_sha256=request_hash,
        native_capture_sha256="4" * 64,
        launch_sha256="5" * 64,
    )


def test_host_audit_retains_native_scope_quantities_and_no_physical_claim(capture):
    result = evaluate(capture)
    assert result["counts"] == {
        "selected_exports": 1,
        "candidate_geometry_variants": 1,
        "blocked_geometry_variants": 0,
        "candidate_installed_instances": 1,
        "blocked_installed_instances": 0,
    }
    row = result["selections"][0]
    assert row["mesh"]["topology"]["closed_consistently_oriented_two_manifold"]
    assert row["native_comparison"]["relative_winding_volume_proxy_delta"] == pytest.approx(0)
    assert row["installed_frame_correspondence"] is None
    assert not any(result["qualification"].values())
    queue = audit.native_draft_plan(result, capture[3])
    assert queue["mesh_origin"] == "selected_saved_BRep_native_tessellation"
    assert len(queue["draft_plate_groups"]) == 1
    assert queue["mesh_audit"][0]["git_blob_sha1"] is None
    assert (
        queue["mesh_audit"][0]["native_export_binding"]["source_binding"]["brep_sha256"] == "2" * 64
    )
    assert capture[3]["evidence_class"] == "pinned_upstream_STL_audit_and_unreleased_draft_queue"


@pytest.mark.parametrize(
    "case",
    [
        "missing_fixture",
        "worker_pin",
        "returncode_bool",
        "recomputed",
        "request_pin",
        "source_pin",
        "schema_bool",
        "frame",
    ],
)
def test_incomplete_stale_or_wrong_scope_native_captures_reject(capture, case):
    bad = copy.deepcopy(capture)
    native, launch, *_ = bad
    if case == "missing_fixture":
        native["primitive_fixtures"]["summary"]["verified"] = False
    elif case == "worker_pin":
        launch["worker_snapshot_sha256"] = "0" * 64
    elif case == "returncode_bool":
        launch["returncode"] = False
    elif case == "recomputed":
        native["document_opened_or_recomputed"] = True
    elif case == "request_pin":
        native["request_sha256"] = "0" * 64
    elif case == "source_pin":
        native["selections"][0]["source_binding"]["brep_sha256"] = "0" * 64
    elif case == "schema_bool":
        native["schema_version"] = True
    else:
        native["coordinate_frame"] = "installed_world"
    with pytest.raises(ValueError):
        evaluate(bad)


def test_export_hash_units_path_and_source_plan_binding_reject(capture):
    for field, value in [("sha256", "0" * 64), ("units", "m"), ("filename", "../outside.stl")]:
        bad = copy.deepcopy(capture)
        bad[0]["selections"][0]["draft_stl"][field] = value
        with pytest.raises(ValueError):
            evaluate(bad)
    bad = copy.deepcopy(capture)
    bad[3]["draft_plate_groups"][0]["repeat_plate_count"] += 1
    with pytest.raises(ValueError, match="does not bind"):
        evaluate(bad)


def test_topology_and_scale_failures_are_blocked_diagnostics_not_repaired(capture):
    for contents in (tetrahedron(open_face=True), tetrahedron(scale=1000)):
        bad = copy.deepcopy(capture)
        native = bad[0]
        root = bad[4]
        row = native["selections"][0]["draft_stl"]
        (root / row["filename"]).write_bytes(contents)
        row.update(
            sha256=hashlib.sha256(contents).hexdigest(),
            bytes=len(contents),
            triangle_count=struct.unpack_from("<I", contents, 80)[0],
        )
        result = evaluate(bad)
        assert result["counts"]["blocked_geometry_variants"] == 1
        assert not result["selections"][0]["draft_candidate"]
        queue = audit.native_draft_plan(result, bad[3])
        assert queue["draft_plate_groups"] == []
        assert not any(result["qualification"].values())


def test_cli_emits_new_lf_audit_and_queue_and_preserves_evidence(capture, tmp_path):
    native, launch, request, parent, mesh_root, _ = capture
    files = []
    for name, value in [
        ("capture", native),
        ("launcher", launch),
        ("request", request),
        ("parent", parent),
    ]:
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
        files.append(path)
    output = tmp_path / "audit.json"
    queue = tmp_path / "queue.json"
    args = [
        "--capture",
        str(files[0]),
        "--launcher",
        str(files[1]),
        "--request",
        str(files[2]),
        "--upstream-plan",
        str(files[3]),
        "--mesh-root",
        str(mesh_root),
        "--output",
        str(output),
        "--draft-plan",
        str(queue),
    ]
    assert audit.main(args) == 0
    saved = output.read_bytes()
    assert b"\r\n" not in saved
    assert audit.main(args) == 2
    assert output.read_bytes() == saved


def test_missing_joint_worker_hashes_do_not_count_as_a_match(capture):
    bad = copy.deepcopy(capture)
    bad[0]["capture_script_sha256"] = None
    bad[1]["worker_snapshot_sha256"] = None
    with pytest.raises(ValueError, match="SHA256"):
        evaluate(bad)
