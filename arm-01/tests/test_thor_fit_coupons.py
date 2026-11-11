"""Dimension-study geometry invariants; no real print or fit acceptance."""

import copy
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tool("thor_fabrication_assets")
planner = tool("thor_slicer_plan")
coupons = tool("thor_fit_coupons")


@pytest.fixture
def interfaces():
    return json.loads((ROOT / coupons.INPUTS["source_interfaces"]).read_bytes())


def test_source_linked_default_coupons_are_closed_distinct_dimension_studies():
    meshes, report = coupons.build_coupon_study()
    assert len(meshes) == len(report["coupons"]) == 3
    assert not report["manufacturing_release"]
    assert report["installed_asset_quantities_are_unchanged"]
    assert report["blocked_coupons"][0]["kind"] == "bearing_seat"
    assert report["blocked_coupons"][0]["nominal_dimension_or_allowance_mm"] is None
    assert report["mesh_units"] == "mm"
    worksheet = report["coupon_measurement_template"]
    assert worksheet["evidence_state"] == "unknown"
    assert worksheet["coupon_mass_is_not_installed_arm_mass"]
    assert all(
        value is None
        for key, value in worksheet.items()
        if key not in {"evidence_state", "coupon_mass_is_not_installed_arm_mass"}
    )
    assert [row["study_parameters"]["lower_bore_diameter_mm"] for row in report["coupons"]] == [
        5.9,
        6,
        6.1,
    ]
    assert len({hashlib.sha256(contents).hexdigest() for contents in meshes.values()}) == 3
    for row in report["coupons"]:
        contents = meshes[row["filename"]]
        assert contents[:80].startswith(b"RAFTEL DRAFT coupon mm;")
        assert hashlib.sha256(contents).hexdigest() == row["mesh_sha256"]
        assert row["source_dimensions"]["source_object"] == "BaseBot::Body002"
        assert row["source_dimensions"]["nominal_bore_diameter_mm"] == 6
        assert row["source_dimensions"]["nominal_relief_diameter_mm"] == 14
        assert row["source_dimensions"]["source_lower_bore_depth_mm"] == 5
        assert row["mesh"]["topology"]["closed_consistently_oriented_two_manifold"]
        assert row["mesh"]["connected_components_by_vertex"] == 1
        assert row["mesh"]["exact_vertex_count"] == 576
        assert row["mesh"]["triangle_count"] == 1152
        assert row["mesh"]["envelope_xyz_interpreted_mm"] == (22, 22, 10)
        assert not any(row["qualification"].values())


def test_nominal_dimension_reference_is_not_an_exact_source_part_and_faceting_is_explicit():
    _, report = coupons.build_coupon_study()
    nominal = report["coupons"][1]
    parameters = nominal["study_parameters"]
    assert parameters["source_nominal_dimension_reference"]
    assert parameters["outer_shape_and_upper_depth_are_coupon_assumptions"]
    assert "not_nominal_Thor_part_export" in nominal["evidence_class"]
    dimensions = nominal["digital_dimensional_checks"]
    assert dimensions["facets_are_inscribed_not_exact_circles"]
    assert dimensions["faceting_is_not_a_print_fit_allowance"]
    lower = dimensions["lower_bore_ring"]
    assert lower["minimum_across_flats_diameter_mm"] == pytest.approx(
        6 * math.cos(math.pi / 96), abs=2e-6
    )
    assert lower["minimum_across_flats_diameter_mm"] < 6
    assert lower["maximum_vertex_diameter_mm"] == pytest.approx(6, abs=2e-6)
    volume_circular = math.pi * (11**2 * 10 - 3**2 * 5 - 7**2 * 5)
    polygon_ratio = 96 * math.sin(2 * math.pi / 96) / (2 * math.pi)
    assert nominal["mesh"]["algebraic_signed_volume_interpreted_mm3"] == pytest.approx(
        volume_circular * polygon_ratio, rel=2e-6
    )


def test_facet_normals_independently_point_out_of_material_at_all_six_surface_strips(interfaces):
    contents, _ = coupons.build_stepped_bore_coupon(interfaces, bore_diameter_offset_mm=0)
    _, facets, _ = planner.parse_stl(contents)
    for normal, triangle in facets:
        center = tuple(sum(point[i] for point in triangle) / 3 for i in range(3))
        zs = {point[2] for point in triangle}
        if len(zs) == 1:
            assert normal[2] < -0.99 if center[2] == 0 else normal[2] > 0.99
        else:
            radial_dot = normal[0] * center[0] + normal[1] * center[1]
            if math.hypot(center[0], center[1]) > 10:
                assert radial_dot > 0
            else:
                assert radial_dot < 0


@pytest.mark.parametrize("segments", [32, 64, 96, 128, 512])
def test_parametric_resolution_preserves_topology_envelope_and_volume(interfaces, segments):
    _, row = coupons.build_stepped_bore_coupon(
        interfaces,
        bore_diameter_offset_mm=0.1,
        segments=segments,
        outer_diameter_mm=24,
        upper_recess_depth_mm=4,
    )
    assert row["mesh"]["topology"]["closed_consistently_oriented_two_manifold"]
    assert row["mesh"]["envelope_xyz_interpreted_mm"] == (24, 24, 9)
    assert row["mesh"]["triangle_count"] == 12 * segments
    assert row["mesh"]["exact_vertex_count"] == 6 * segments


@pytest.mark.parametrize(
    "changes",
    [
        {"bore_diameter_offset_mm": math.nan},
        {"bore_diameter_offset_mm": math.inf},
        {"bore_diameter_offset_mm": True},
        {"bore_diameter_offset_mm": 1},
        {"bore_diameter_offset_mm": -1},
        {"segments": True},
        {"segments": 33},
        {"segments": 1024},
        {"outer_diameter_mm": 14},
        {"outer_diameter_mm": 15},
        {"outer_diameter_mm": 100},
        {"upper_recess_depth_mm": 0},
        {"upper_recess_depth_mm": math.inf},
    ],
)
def test_invalid_or_degenerate_study_parameters_fail(interfaces, changes):
    arguments = {"bore_diameter_offset_mm": 0, **changes}
    with pytest.raises(ValueError):
        coupons.build_stepped_bore_coupon(interfaces, **arguments)


@pytest.mark.parametrize("offsets", [(), (0.1,), (0, 0), tuple(i / 100 for i in range(10))])
def test_grid_requires_bounded_distinct_variants_and_nominal_reference(offsets):
    with pytest.raises(ValueError):
        coupons.build_coupon_study(offsets_mm=offsets)


def test_source_summary_cannot_drift_from_captured_faces(interfaces):
    bad = copy.deepcopy(interfaces)
    bad["base_mount_summary"]["through_hole_diameter_mm"] = 7
    with pytest.raises(ValueError, match="disagrees"):
        coupons.build_stepped_bore_coupon(bad, bore_diameter_offset_mm=0)


@pytest.mark.parametrize(
    "bad",
    [
        "bool_schema",
        "schema",
        "class",
        "source_file",
        "body",
        "hash",
        "frame",
        "relief_faces",
        "duplicate_face",
    ],
)
def test_source_receipt_cannot_claim_unsupported_schema_identity_or_face_ids(interfaces, bad):
    data = copy.deepcopy(interfaces)
    if bad == "bool_schema":
        data["schema_version"] = True
    elif bad == "schema":
        data["schema_version"] = 999
    elif bad == "class":
        data["validation_class"] = "fabricated_not_native"
    elif bad in {"source_file", "body", "frame", "hash"}:
        key = {"frame": "coordinate_frame", "hash": "source_sha256"}.get(bad, bad)
        data["base_interface"][key] = "FAKE"
    elif bad == "relief_faces":
        for face in data["base_interface"]["selected_cylindrical_faces"]:
            if face["face"] in {63, 64, 69, 70}:
                face["face"] += 100
    else:
        data["base_interface"]["selected_cylindrical_faces"][-1]["face"] = 63
    with pytest.raises(ValueError):
        coupons.build_stepped_bore_coupon(data, bore_diameter_offset_mm=0)


@pytest.mark.parametrize(
    "bad",
    [
        "duplicate_interface_key",
        "profile_array",
        "profile_bool_schema",
        "profile_class",
        "profile_machine",
        "profile_selection_hash",
        "profile_null_fields",
        "profile_selector_mismatch",
    ],
)
def test_study_strict_json_and_saved_profile_binding_fail_closed(tmp_path, bad):
    data = {}
    for role, path in coupons.INPUTS.items():
        content = (ROOT / path).read_bytes()
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        data[role] = json.loads(content)
    if bad == "duplicate_interface_key":
        target = tmp_path / coupons.INPUTS["source_interfaces"]
        target.write_bytes(
            target.read_bytes().replace(
                b'"schema_version": 1', b'"schema_version": 999, "schema_version": 1', 1
            )
        )
    else:
        profile = data["saved_profile_audit"]
        if bad == "profile_array":
            profile = []
        elif bad == "profile_bool_schema":
            profile["schema_version"] = True
        elif bad == "profile_class":
            profile["validation_class"] = "fabricated_not_a_profile"
        elif bad == "profile_machine":
            profile["profiles"]["machine"]["selected_name"] = "unverified machine"
        elif bad == "profile_null_fields":
            profile["saved_selection"]["profile_fields"] = None
            profile["saved_selection"]["profile_fields_canonical_sha256"] = (
                coupons.canonical_sha256(None)
            )
        elif bad == "profile_selector_mismatch":
            profile["saved_selection"]["profile_fields"]["process"] = "unverified selector"
            profile["saved_selection"]["profile_fields_canonical_sha256"] = (
                coupons.canonical_sha256(profile["saved_selection"]["profile_fields"])
            )
        else:
            profile["saved_selection"]["profile_fields_canonical_sha256"] = "0" * 64
        (tmp_path / coupons.INPUTS["saved_profile_audit"]).write_text(json.dumps(profile))
    with pytest.raises(ValueError):
        coupons.build_coupon_study(tmp_path)


def test_tracked_recipe_reproduces_hashes_and_numerical_mesh_diagnostics():
    _, report = coupons.build_coupon_study()
    tracked = json.loads((ROOT / "hardware/print-planning/thor-fit-coupons-v1.json").read_bytes())
    # Reuse the existing draft audit comparator: hashes/discrete fields remain
    # exact, derived floating diagnostics allow 1e-12 numerical roundoff only.
    draft = tool("thor_draft_3mf")
    assert draft._mesh_audit_matches(report, tracked)


def test_cli_exclusive_drafts_and_receipt_preserve_existing_evidence(tmp_path):
    directory, report = tmp_path / "new-coupons", tmp_path / "new-receipt.json"
    command = [
        sys.executable,
        str(ROOT / "tools/thor_fit_coupons.py"),
        "--output-dir",
        str(directory),
        "--report",
        str(report),
    ]
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert report.read_bytes() == (directory / "receipt.json").read_bytes()
    assert b"\r\n" not in report.read_bytes()
    receipt = json.loads(report.read_bytes())
    for row in receipt["coupons"]:
        assert (
            hashlib.sha256((directory / row["filename"]).read_bytes()).hexdigest()
            == row["mesh_sha256"]
        )
    original = report.read_bytes()
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode != 0 and "must be new" in run.stderr
    assert report.read_bytes() == original
    another = tmp_path / "second-new-directory"
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/thor_fit_coupons.py"),
            "--output-dir",
            str(another),
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "new path" in run.stderr
    assert not another.exists()
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/thor_fit_coupons.py"),
            "--output-dir",
            str(another),
            "--report",
            str(another / "receipt.json"),
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "outside" in run.stderr
    assert not another.exists()
