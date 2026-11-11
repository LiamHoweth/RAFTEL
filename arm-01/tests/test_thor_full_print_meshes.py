"""Portable actual-metadata joins plus synthetic STL guard counterexamples.

The real47payloads remain local .work evidence. These tests do not claim CI
replays native CAD or downloads/repairs/prints any geometry.
"""

import copy
import importlib
import json
import math
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
audit = importlib.import_module("audit_thor_full_print_meshes")


@pytest.fixture(scope="module")
def evidence():
    _, documents, request_raw, raw_batches = audit.load_evidence()
    return documents, request_raw, raw_batches


def validate(documents, request_raw, raw_batches):
    return audit.validate_full_metadata(
        documents["aggregate"],
        request_raw,
        raw_batches,
        documents["manifest"],
        documents["inventory"],
        documents["inspection"],
    )


def test_actual_six_batch_metadata_is_complete_separate_and_geometry_only(evidence):
    documents, raw, batches = evidence
    joined = validate(documents, raw, batches)
    assert len(joined["by_id"]) == len(joined["captured"]) == len(joined["variants"]) == 47
    assert {row["batch"]["batch_index"] for row in joined["contexts"].values()} == set(range(1, 7))
    ids = [
        member["instance_id"]
        for selection in joined["by_id"].values()
        for member in selection["reference_capture"]["installed_instances"]
    ]
    assert len(ids) == len(set(ids)) == 65
    assert sum(row["draft_stl"]["triangle_count"] for row in joined["captured"].values()) == 325810
    assert all(
        context["capture"]["full_runtime_bundle_verified_by_worker"] is False
        for context in joined["contexts"].values()
    )


@pytest.mark.parametrize(
    "bad",
    [
        "missing_batch",
        "duplicate_batch",
        "swapped_batch",
        "missing_variant",
        "duplicate_variant",
        "changed_instance",
        "wrong_quantity",
        "count_bool",
        "qualified",
        "missing_qualification",
        "opened_document",
        "runtime_claim",
        "preservation_claim",
        "aggregate_com",
        "raw_capture_bytes",
        "raw_runner_bytes",
        "unsafe_request_path",
        "unsafe_batch_path",
        "unsafe_export_path",
        "earlier_eight_count",
    ],
)
def test_incomplete_corrupt_or_contradictory_aggregate_is_rejected(evidence, bad):
    original, raw, original_batches = evidence
    documents, batches = copy.deepcopy(original), dict(original_batches)
    aggregate = documents["aggregate"]
    if bad == "missing_batch":
        aggregate["batches"].pop()
    elif bad == "duplicate_batch":
        aggregate["batches"][-1] = copy.deepcopy(aggregate["batches"][0])
    elif bad == "swapped_batch":
        batches[1], batches[2] = batches[2], batches[1]
    elif bad == "missing_variant":
        aggregate["variants"].pop()
    elif bad == "duplicate_variant":
        aggregate["variants"][-1] = copy.deepcopy(aggregate["variants"][0])
    elif bad == "changed_instance":
        aggregate["variants"][0]["installed_instance_ids"][0] = "invented installed leaf"
    elif bad == "wrong_quantity":
        aggregate["variants"][0]["quantity_required"] += 1
    elif bad == "count_bool":
        aggregate["counts"]["source_assets"] = True
    elif bad == "qualified":
        aggregate["qualification"]["manufacturing_released"] = True
    elif bad == "missing_qualification":
        aggregate["qualification"] = {}
    elif bad == "opened_document":
        aggregate["preservation"]["document_opened_or_recomputed"] = True
    elif bad == "runtime_claim":
        aggregate["runtime"]["complete_runtime_and_OS_library_bundle_verified_by_worker"] = True
    elif bad == "preservation_claim":
        aggregate["preservation"]["all57_originals_verified_before_after_each_batch"] = False
    elif bad == "aggregate_com":
        aggregate["variants"][0]["com_mm"][0] += 1
    elif bad == "raw_capture_bytes":
        batches[1] = (batches[1][0] + b" ", batches[1][1])
    elif bad == "raw_runner_bytes":
        batches[1] = (batches[1][0], batches[1][1] + b" ")
    elif bad == "unsafe_request_path":
        aggregate["full_request_path"] = "../../outside/request.json"
    elif bad == "unsafe_batch_path":
        aggregate["batches"][0]["raw_capture_path"] = "../../outside/capture.json"
    elif bad == "unsafe_export_path":
        aggregate["variants"][0]["draft_stl"]["local_path"] = "../../outside/mesh.stl"
    else:
        aggregate["earlier_eight_repeatability"]["matched_selection_count"] = 999
    with pytest.raises(ValueError):
        validate(documents, raw, batches)


def mutate_pair(documents, batches, action):
    capture, runner = map(audit._strict_json, batches[1])
    action(capture, runner)
    cap_raw = (json.dumps(capture, allow_nan=True) + "\n").encode()
    runner["report_sha256"] = audit.sha(cap_raw)
    runner_raw = (json.dumps(runner) + "\n").encode()
    batch = documents["aggregate"]["batches"][0]
    batch["raw_capture_sha256"], batch["raw_runner_sha256"] = (
        audit.sha(cap_raw),
        audit.sha(runner_raw),
    )
    batches[1] = cap_raw, runner_raw


@pytest.mark.parametrize(
    "bad",
    [
        "source_pin",
        "body",
        "frame",
        "copied_archive",
        "original_archive",
        "worker_pin",
        "request_snapshot",
        "physical_inertia",
        "nonfinite_tensor",
        "subnormal_tensor",
        "non_PSD_tensor",
        "SI_tensor",
        "opened_doc",
        "fixture",
        "false_source_auth",
        "retained_snapshot",
        "duplicate_selection",
        "unisolated_paths",
        "export_qualification",
    ],
)
def test_rehashed_raw_pair_still_rejects_semantic_context_corruption(evidence, bad):
    original, raw, original_batches = evidence
    documents, batches = copy.deepcopy(original), dict(original_batches)

    def action(capture, runner):
        row = capture["selections"][0]
        properties = row["cached_shape_properties"]
        if bad == "source_pin":
            row["source_binding"]["source_sha256"] = "0" * 64
        elif bad == "body":
            row["source_binding"]["object_name"] = "unaccepted_candidate"
        elif bad == "frame":
            row["coordinate_frame"] = "double_transformed_installed_frame"
        elif bad == "copied_archive":
            name = next(iter(runner["input_copy_sha256_before"]))
            runner["input_copy_sha256_before"][name] = "0" * 64
            runner["input_copy_sha256_after"][name] = "0" * 64
        elif bad == "original_archive":
            name = next(iter(runner["original57_sha256_before"]))
            runner["original57_sha256_before"][name] = "0" * 64
            runner["original57_sha256_after"][name] = "0" * 64
        elif bad == "worker_pin":
            capture["capture_script_sha256"] = "0" * 64
        elif bad == "request_snapshot":
            capture["request"]["selections"][0]["source_sha256"] = "0" * 64
        elif bad == "physical_inertia":
            row["physical_or_purchased_internal_or_nonuniform_print_inertia_kg_m2"] = [
                [1, 0, 0],
                [0, 1, 0],
                [0, 0, 1],
            ]
        elif bad == "nonfinite_tensor":
            properties["aggregate"]["centroidal_geometric_inertia_mm5"][0][0] = math.nan
        elif bad == "subnormal_tensor":
            properties["solids"][0]["centroidal_geometric_inertia_mm5"] = [
                [1e-320, 0, 0],
                [0, 1e-320, 0],
                [0, 0, 1e-320],
            ]
            properties["aggregate"]["centroidal_geometric_inertia_mm5"] = [
                [1e-320, 0, 0],
                [0, 1e-320, 0],
                [0, 0, 1e-320],
            ]
            properties["aggregate"]["centroidal_geometric_inertia_m5"] = [
                [0, 0, 0],
                [0, 0, 0],
                [0, 0, 0],
            ]
        elif bad == "non_PSD_tensor":
            properties["solids"][0]["centroidal_geometric_inertia_mm5"][0][0] = -1
        elif bad == "SI_tensor":
            properties["aggregate"]["centroidal_geometric_inertia_m5"][0][0] *= 1000
        elif bad == "opened_doc":
            capture["open_document_count_after"] = 1
        elif bad == "fixture":
            capture["primitive_fixtures"]["records"]["box"]["aggregate"]["volume_mm3"] *= 2
        elif bad == "false_source_auth":
            capture["declared_revision_not_independently_authenticated_by_worker"] = False
        elif bad == "retained_snapshot":
            name = next(iter(runner["retained_sha256_before"]))
            runner["retained_sha256_before"][name] = "0" * 64
            runner["retained_sha256_after"][name] = "0" * 64
        elif bad == "unisolated_paths":
            for key in capture["expected_isolated_paths"]:
                capture["expected_isolated_paths"][key] = (
                    r"C:\Users\howet\AppData\Roaming\unisolated.cfg"
                )
                capture["actual_runtime_paths"][key] = (
                    r"C:\Users\howet\AppData\Roaming\unisolated.cfg"
                )
            documents["aggregate"]["batches"][0]["actual_runtime_paths"] = copy.deepcopy(
                capture["actual_runtime_paths"]
            )
        elif bad == "export_qualification":
            row["draft_stl"]["print_or_fit_qualification"] = True
            documents["aggregate"]["variants"][0]["draft_stl"]["print_or_fit_qualification"] = True
        else:
            capture["selections"][-1] = copy.deepcopy(capture["selections"][0])

    mutate_pair(documents, batches, action)
    with pytest.raises(ValueError):
        validate(documents, raw, batches)


def tetrahedron(*, open_face=False, reverse=False, normal_mode="valid"):
    points = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
    if open_face:
        faces.pop()
    if reverse:
        faces = [tuple(reversed(face)) for face in faces]
    payload = bytearray(
        b"explicitly synthetic unit test fixture".ljust(80, b" ") + struct.pack("<I", len(faces))
    )
    for face in faces:
        a, b, c = [points[i] for i in face]
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        normal = tuple(value / math.hypot(*n) for value in n)
        if normal_mode == "zero":
            normal = (0, 0, 0)
        if normal_mode == "opposed":
            normal = tuple(-value for value in normal)
        payload.extend(struct.pack("<12fH", *normal, *(x for i in face for x in points[i]), 0))
    return bytes(payload)


def mesh_fixture(contents):
    selection = {
        "tessellation": {
            "filename": "fixture.stl",
            "linear_deflection_mm": 0.1,
            "angular_deflection_rad": 0.2,
            "relative": False,
        }
    }
    row = {
        "upstream_STL_is_not_this_native_export": True,
        "draft_stl": {
            "filename": "fixture.stl",
            "units": "mm",
            "frame": audit.selected_audit.FRAME,
            "encoding": "binary_STL",
            "tessellation": selection["tessellation"],
            "sha256": audit.sha(contents),
            "bytes": len(contents),
            "triangle_count": struct.unpack_from("<I", contents, 80)[0],
            "vertex_count_before_STL_unindexing": 4,
            "mesh_manifoldness_or_winding_independently_verified": False,
            "mesh_self_intersections_checked": False,
            "print_or_fit_qualification": False,
        },
        "cached_shape_properties": {
            "aggregate": {"volume_mm3": 1 / 6},
            "native_bounds_mm": {"XMin": 0, "YMin": 0, "ZMin": 0, "XMax": 1, "YMax": 1, "ZMax": 1},
        },
    }
    return row, selection


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("valid", None),
        ("open", "exact_vertex_topology_or_winding_failure"),
        ("reversed", "nonpositive_winding_integral"),
        ("zero", "stored_facet_normal_zero_or_opposed_to_winding"),
        ("opposed", "stored_facet_normal_zero_or_opposed_to_winding"),
        ("scale", "gross_unit_or_scale_sanity_failure"),
        ("bounds", "mesh_bounds_outside_native_bounds_at_float32_tolerance"),
    ],
)
def test_synthetic_mesh_guard_reports_truthful_blockers(kind, expected):
    contents = tetrahedron(
        open_face=kind == "open",
        reverse=kind == "reversed",
        normal_mode=kind if kind in {"zero", "opposed"} else "valid",
    )
    row, selection = mesh_fixture(contents)
    if kind == "scale":
        row["cached_shape_properties"]["aggregate"]["volume_mm3"] *= 1000
    if kind == "bounds":
        row["cached_shape_properties"]["native_bounds_mm"]["XMax"] = 0.5
    result = audit.audit_one_mesh(contents, row, selection)
    assert result["draft_candidate"] == (expected is None)
    if expected:
        assert expected in result["blockers"]


def test_mesh_hash_and_unit_metadata_corruption_rejects_before_eligibility():
    contents = tetrahedron()
    row, selection = mesh_fixture(contents)
    with pytest.raises(ValueError, match="byte/hash"):
        audit.audit_one_mesh(contents + b" ", row, selection)
    row["draft_stl"]["units"] = "m"
    with pytest.raises(ValueError, match="units/frame"):
        audit.audit_one_mesh(contents, row, selection)


def test_tracked_host_audit_preserves_two_topology_blocks_and65_quantities():
    data = json.loads(
        (ROOT / "hardware/print-planning/thor-full-print-mesh-audit-v1.json").read_bytes()
    )
    assert data["evidence_class"] == audit.HOST_CLASS
    assert data["counts"] == {
        "audited_geometry_variants": 47,
        "represented_installed_instances": 65,
        "candidate_geometry_variants": 45,
        "blocked_geometry_variants": 2,
        "candidate_installed_instances": 62,
        "blocked_installed_instances": 3,
        "total_triangles": 325810,
    }
    blocked = {
        row["installed_asset_id"]: row for row in data["selections"] if not row["draft_candidate"]
    }
    assert blocked["Art23Optodisk::Body"]["mesh"]["topology"]["boundary_edges"] == 4
    assert blocked["Art4TransmissionColumn::Body"]["mesh"]["topology"]["nonmanifold_edges"] == 3
    assert data["finger_vertex_reflection_check"]["matches"]
    assert not any(data["qualification"].values())


def test_metadata_only_cli_is_portable_and_preserves_existing_output(tmp_path):
    output = tmp_path / "new.json"
    command = [
        sys.executable,
        str(ROOT / "tools/audit_thor_full_print_meshes.py"),
        "--metadata-only",
        "--output",
        str(output),
    ]
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    content = output.read_bytes()
    assert b"\r\n" not in content and json.loads(content)["mesh_payloads_audited"] is False
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode != 0 and output.read_bytes() == content


def test_direct_metadata_scope_does_not_claim_unprovided_historical_repeatability(evidence):
    documents, raw, batches = evidence
    joined = validate(documents, raw, batches)
    assert joined["earlier_eight_repeatability_verified"] is False
    with pytest.raises(ValueError, match="historical eight"):
        audit.audit_full_meshes(joined, ROOT.parent)
    complete, _, _, _ = audit.load_evidence()
    assert complete["earlier_eight_repeatability_verified"] is True
