"""Synthetic geometry and strict source-binding tests; no slicer/CAD execution."""

import copy
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
for name in ("thor_slicer_plan", "audit_thor_native_meshes", "thor_mesh_orientations"):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
orientation = sys.modules["thor_mesh_orientations"]


def as_stl(triangles):
    lines = ["solid synthetic_geometric_fixture"]
    for triangle in triangles:
        lines.extend(("facet normal 0 0 0", "outer loop"))
        lines.extend("vertex " + " ".join(format(v, ".17g") for v in p) for p in triangle)
        lines.extend(("endloop", "endfacet"))
    return ("\n".join(lines + ["endsolid synthetic_geometric_fixture"]) + "\n").encode()


def box(*, offset=(0, 0, 0)):
    points = (
        (0, 0, 0),
        (2, 0, 0),
        (2, 3, 0),
        (0, 3, 0),
        (0, 0, 4),
        (2, 0, 4),
        (2, 3, 4),
        (0, 3, 4),
    )
    quads = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
    shifted = [tuple(p[i] + offset[i] for i in range(3)) for p in points]
    return as_stl(
        tuple(
            tuple(shifted[i] for i in face)
            for a, b, c, d in quads
            for face in ((a, b, c), (a, c, d))
        )
    )


def cylinder(n=64, radius=2, height=5):
    bottom = [
        (radius * math.cos(2 * math.pi * i / n), radius * math.sin(2 * math.pi * i / n), 0)
        for i in range(n)
    ]
    top = [(x, y, height) for x, y, _ in bottom]
    triangles = []
    for i in range(n):
        j = (i + 1) % n
        triangles.extend(
            (
                ((0, 0, 0), bottom[j], bottom[i]),
                ((0, 0, height), top[i], top[j]),
                (bottom[i], bottom[j], top[j]),
                (bottom[i], top[j], top[i]),
            )
        )
    return as_stl(triangles)


def test_box_volume_area_contact_com_and_grounding():
    rows = orientation.measure_orientations(box(), native_volume_com_mm=(1, 1.5, 2))
    assert len(rows) == 6
    for row, bed_area in zip(rows, (6, 6, 12, 12, 8, 8), strict=True):
        assert row["signed_winding_volume_mm3"] == pytest.approx(24)
        assert row["surface_area_mm2"] == pytest.approx(52)
        assert row["bed_full_triangle_area_mm2"] == pytest.approx(bed_area)
        assert row["downward_facing_full_bed_triangle_area_mm2"] == pytest.approx(bed_area)
        assert sum(row["above_bed_downward_facing_area_bins_mm2"].values()) == 0
        assert row["native_com_projection_in_vertex_hull"] is True
        assert row["native_minus_mesh_centroid_mm"] == pytest.approx((0, 0, 0))
        assert row["bounds_mm"]["min"][2] == 0
        assert row["translation_mm"][:2] == (0, 0)
        assert row["orientation_selected"] is False


def test_cylinder_caps_sides_volume_and_centroid():
    rows = orientation.measure_orientations(cylinder(), native_volume_com_mm=(0, 0, 2.5))
    cap = 64 / 2 * 4 * math.sin(2 * math.pi / 64)
    for row in rows:
        assert row["signed_winding_volume_mm3"] == pytest.approx(cap * 5, abs=1e-11)
        assert row["native_minus_mesh_centroid_mm"] == pytest.approx((0, 0, 0), abs=1e-14)
    assert rows[0]["bed_full_triangle_area_mm2"] == pytest.approx(cap)
    assert rows[1]["bed_full_triangle_area_mm2"] == pytest.approx(cap)
    assert rows[2]["bed_full_triangle_area_mm2"] == 0
    assert rows[2]["native_com_projection_in_vertex_hull"] is None
    assert sum(rows[2]["above_bed_downward_facing_area_bins_mm2"].values()) > 0


@pytest.mark.parametrize(
    "label,axis",
    (
        ("source_positive_z_up", (0, 0, 1)),
        ("source_negative_z_up", (0, 0, -1)),
        ("source_positive_x_up", (1, 0, 0)),
        ("source_negative_x_up", (-1, 0, 0)),
        ("source_positive_y_up", (0, 1, 0)),
        ("source_negative_y_up", (0, -1, 0)),
    ),
)
def test_rotation_maps_named_up_axis_to_build_up(label, axis):
    matrix = orientation.proper_axis_rotation(orientation.ROTATIONS[label])
    assert orientation.rotate(matrix, axis) == (0, 0, 1)


@pytest.mark.parametrize(
    "matrix",
    (
        ((-1, 0, 0), (0, 1, 0), (0, 0, 1)),
        ((1, 0, 0), (1, 0, 0), (0, 0, 1)),
        ((1, 0), (0, 1)),
        ((True, 0, 0), (0, 1, 0), (0, 0, 1)),
        ((float("nan"), 0, 0), (0, 1, 0), (0, 0, 1)),
    ),
)
def test_bad_rotations_are_rejected(matrix):
    with pytest.raises((ValueError, TypeError)):
        orientation.proper_axis_rotation(matrix)


def test_translation_only_grounds_z_without_xy_recentering():
    rows = orientation.measure_orientations(box(offset=(10, 20, -30)))
    assert rows[0]["translation_mm"] == (0, 0, 30)
    assert rows[0]["bounds_mm"] == {"min": (10, 20, 0), "max": (12, 23, 4)}
    assert rows[0]["native_uniform_volume_com_mm"] is None
    assert rows[0]["mesh_winding_volume_centroid_mm"] == (11, 21.5, 2)


def test_bed_tolerance_is_numerical_not_partial_triangle_area():
    triangle = ((0, 0, 0), (1, 0, 1e-4), (0, 1, 0))
    # A grounded vertex alone does not give an entire triangle its area at the bed.
    tetra = as_stl(
        (
            triangle,
            ((0, 0, 0), (0, 0, -1), (1, 0, 1e-4)),
            ((0, 0, 0), (0, 1, 0), (0, 0, -1)),
            ((1, 0, 1e-4), (0, 0, -1), (0, 1, 0)),
        )
    )
    rows = orientation.measure_orientations(tetra)
    assert rows[0]["bed_full_triangle_area_mm2"] == 0


def test_known_downward_sloped_face_uses_angle_from_vertical_wall():
    points = ((0, 0, 0), (2, 0, 0), (0, 2, 0), (0, 0, 2))
    faces = ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))
    payload = as_stl(tuple(tuple(points[i] for i in face) for face in faces))
    rows = orientation.measure_orientations(payload)
    bins = rows[1]["above_bed_downward_facing_area_bins_mm2"]
    # After source -Z goes up, original +++ normal faces down at asin(1/sqrt(3)).
    assert bins["30_to_45_exclusive"] == pytest.approx(2 * math.sqrt(3))
    assert sum(bins.values()) == pytest.approx(2 * math.sqrt(3))
    assert rows[1]["downward_facing_full_bed_triangle_area_mm2"] == 0


def test_exact_45_degree_face_belongs_to_45_to_60_bin():
    points = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 1, 1))
    faces = ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))
    payload = as_stl(tuple(tuple(points[i] for i in face) for face in faces))
    rows = orientation.measure_orientations(payload)
    bins = rows[5]["above_bed_downward_facing_area_bins_mm2"]
    # Source +X+Y normal becomes +X-Z with source -Y up: an exact 45deg face.
    assert bins["45_to_60_exclusive"] == pytest.approx(math.sqrt(2) / 2)
    assert bins["30_to_45_exclusive"] == 0


def test_mesh_centroid_and_volume_are_translation_invariant():
    baseline = orientation.measure_orientations(box())
    shifted = orientation.measure_orientations(box(offset=(1e6, -2e6, 3e6)))
    for first, second in zip(baseline, shifted, strict=True):
        assert first["signed_winding_volume_mm3"] == second["signed_winding_volume_mm3"]
        assert first["surface_area_mm2"] == second["surface_area_mm2"]
        assert (
            second["mesh_winding_volume_centroid_mm"][2]
            == first["mesh_winding_volume_centroid_mm"][2]
        )


@pytest.mark.parametrize("bad", (0, -1, True, float("nan"), 0.10001))
def test_invalid_bed_tolerances_rejected(bad):
    with pytest.raises(ValueError):
        orientation.measure_orientations(box(), bed_tolerance_mm=bad)


def fixture_audit(tmp_path):
    payload = box()
    filename = "synthetic.stl"
    (tmp_path / filename).write_bytes(payload)
    row = {
        "draft_candidate": True,
        "installed_asset_id": "synthetic",
        "geometry_variant": "nominal",
        "source_binding": {"synthetic": True},
        "coordinate_frame": orientation.native.FRAME,
        "native_export": {
            "filename": filename,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "units": "mm",
            "frame": orientation.native.FRAME,
            "triangle_count": 12,
        },
        "mesh": orientation.stl.analyze_stl(payload),
        "native_comparison": {"native_raw_com_mm": (1, 1.5, 2)},
    }
    rows = [
        dict(copy.deepcopy(row), selection_id=name) for name in sorted(orientation.ELIGIBLE_IDS)
    ]
    rows.append({"selection_id": "art4-transmission-column", "draft_candidate": False})
    return {
        "schema_version": 1,
        "evidence_class": orientation.native.HOST_CLASS,
        "source_revision": orientation.stl.SOURCE_REVISION,
        "selections": rows,
        "input_bindings": {"synthetic": True},
    }


def build_fixture(value, tmp_path):
    raw = json.dumps(value).encode()
    return orientation.build_study(
        raw, tmp_path, expected_audit_sha256=hashlib.sha256(raw).hexdigest()
    )


def test_study_exact_variants_and_all_qualification_false(tmp_path):
    report = build_fixture(fixture_audit(tmp_path), tmp_path)
    assert report["counts"]["orientation_measurements"] == 42
    assert {row["selection_id"] for row in report["selections"]} == orientation.ELIGIBLE_IDS
    assert not any(report["qualification"].values())


@pytest.mark.parametrize(
    "mutation",
    (
        "bool_schema",
        "wrong_frame",
        "wrong_units",
        "stale_mesh",
        "unsafe_path",
        "windows_drive_path",
        "blocked_enabled",
        "blocked_not_bool",
        "duplicate_identity",
        "topology",
    ),
)
def test_input_binding_failures(tmp_path, mutation):
    value = fixture_audit(tmp_path)
    row = value["selections"][0]
    if mutation == "bool_schema":
        value["schema_version"] = True
    elif mutation == "wrong_frame":
        row["coordinate_frame"] = "installed"
    elif mutation == "wrong_units":
        row["native_export"]["units"] = "m"
    elif mutation == "stale_mesh":
        row["native_export"]["sha256"] = "0" * 64
    elif mutation == "unsafe_path":
        row["native_export"]["filename"] = "../synthetic.stl"
    elif mutation == "windows_drive_path":
        row["native_export"]["filename"] = "C:synthetic.stl"
    elif mutation == "blocked_enabled":
        value["selections"][-1]["draft_candidate"] = True
    elif mutation == "blocked_not_bool":
        value["selections"][-1]["draft_candidate"] = 0
    elif mutation == "duplicate_identity":
        row["selection_id"] = value["selections"][1]["selection_id"]
    elif mutation == "topology":
        row["mesh"]["topology"]["boundary_edges"] = 3
    with pytest.raises(ValueError):
        build_fixture(value, tmp_path)


def test_stale_audit_and_existing_output_preserved(tmp_path):
    with pytest.raises(ValueError, match="SHA256"):
        orientation.build_study(b"{}", tmp_path)
    output = tmp_path / "existing.json"
    output.write_bytes(b"preserved")
    assert orientation.main(["--mesh-root", str(tmp_path), "--output", str(output)]) == 2
    assert output.read_bytes() == b"preserved"


def test_checked_report_and_actual_fingers_are_distinct():
    audit_raw = (ROOT / "hardware/print-planning/thor-native-mesh-audit-v1.json").read_bytes()
    assert hashlib.sha256(audit_raw).hexdigest() == orientation.PINNED_NATIVE_AUDIT_SHA256
    report = json.loads(
        (ROOT / "hardware/print-planning/thor-mesh-orientation-study-v1.json").read_bytes()
    )
    assert report["native_mesh_audit_raw_sha256"] == orientation.PINNED_NATIVE_AUDIT_SHA256
    rows = {row["selection_id"]: row for row in report["selections"]}
    nominal, reflected = (rows["gripper-finger-" + name] for name in ("nominal", "reflected"))
    assert nominal["native_export"]["sha256"] != reflected["native_export"]["sha256"]
    assert nominal["source_binding"] != reflected["source_binding"]
    assert nominal["orientations"][0]["native_com_projection_xy_mm"][0] > 0
    assert reflected["orientations"][0]["native_com_projection_xy_mm"][0] < 0
    assert len(rows) == 7
