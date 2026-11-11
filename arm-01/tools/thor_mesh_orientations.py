"""Unranked host-only geometric orientations of seven pinned native draft meshes.

This performs no slicing, mesh repair, support selection, stability assessment,
native CAD invocation or manufacturing qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path, PurePosixPath

import audit_thor_native_meshes as native
import thor_slicer_plan as stl

from raftel_arm01.engineering.scenarios import _strict_json, finite_number

ROOT = Path(__file__).resolve().parents[1]
PINNED_NATIVE_AUDIT_SHA256 = "74e82d136de667304e1ff5733b2c46aa450ca27210ef3762ca9fd10663d13379"
ELIGIBLE_IDS = frozenset(
    (
        "base-top",
        "base-bearing-fix",
        "common-bearing-fix",
        "art2-window",
        "art3-tensioner-body",
        "gripper-finger-nominal",
        "gripper-finger-reflected",
    )
)
# Column-vector convention: source point p -> R @ p + (0, 0, -minimum_z).
ROTATIONS = {
    "source_positive_z_up": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "source_negative_z_up": ((1, 0, 0), (0, -1, 0), (0, 0, -1)),
    "source_positive_x_up": ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
    "source_negative_x_up": ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
    "source_positive_y_up": ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    "source_negative_y_up": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
}


def proper_axis_rotation(matrix):
    """Validate an exact signed-permutation rotation; reflections are rejected."""
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        raise ValueError("rotation must be a three by three signed permutation")
    rows = tuple(stl._vector(row) for row in matrix)
    if any(value not in (-1, 0, 1) for row in rows for value in row):
        raise ValueError("rotation must have exact signed-permutation entries")
    if any(sum(value * value for value in row) != 1 for row in rows) or any(
        sum(rows[i][j] ** 2 for i in range(3)) != 1 for j in range(3)
    ):
        raise ValueError("rotation must be orthonormal")
    determinant = math.fsum(
        a * b for a, b in zip(rows[0], stl._cross(rows[1], rows[2]), strict=True)
    )
    if determinant != 1:
        raise ValueError("rotation must be proper, determinant +1")
    return rows


def rotate(matrix, point):
    return tuple(math.fsum(a * b for a, b in zip(row, point, strict=True)) for row in matrix)


def _geometry(triangles):
    points = [point for triangle in triangles for point in triangle]
    minimum = tuple(min(point[i] for point in points) for i in range(3))
    maximum = tuple(max(point[i] for point in points) for i in range(3))
    reference = tuple(a + (b - a) / 2 for a, b in zip(minimum, maximum, strict=True))
    areas, weights, centroids, normals = [], [], [], []
    for a, b, c in triangles:
        normal = stl._cross(stl._minus(b, a), stl._minus(c, a))
        norm = finite_number(math.hypot(*normal))
        if norm <= 0:
            raise ValueError("orientation requires nondegenerate triangles")
        ar, br, cr = (stl._minus(p, reference) for p in (a, b, c))
        weight = finite_number(
            math.fsum(x * y for x, y in zip(ar, stl._cross(br, cr), strict=True))
        )
        weights.append(weight)
        centroids.append(tuple(reference[i] + (ar[i] + br[i] + cr[i]) / 4 for i in range(3)))
        areas.append(norm / 2)
        normals.append(tuple(value / norm for value in normal))
    total_weight = finite_number(math.fsum(weights))
    if total_weight <= 0:
        raise ValueError("orientation requires positive signed winding volume")
    centroid = tuple(
        finite_number(
            math.fsum(w * c[i] for w, c in zip(weights, centroids, strict=True)) / total_weight
        )
        for i in range(3)
    )
    return minimum, maximum, areas, normals, total_weight / 6, centroid


def _hull_xy(points):
    """Exact monotone-chain hull of finite projected near-bed mesh vertices."""
    points = sorted(set((p[0], p[1]) for p in points))
    if len(points) <= 1:
        return points

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _inside_hull(point, hull):
    if len(hull) < 3:
        return None
    return all(
        (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]) >= 0
        for a, b in zip(hull, hull[1:] + hull[:1], strict=True)
    )


def measure_orientations(contents: bytes, *, native_volume_com_mm=None, bed_tolerance_mm=1e-5):
    """Measure six candidates, retaining the source mesh's actual handedness.

    Bed area is the sum of full triangle areas whose three grounded vertices
    have z <= numerical tolerance. Partial triangles are not clipped/integrated.
    Downward angle is atan2(-n_z, hypot(n_x,n_y)): wall 0deg, horizontal 90deg.
    Above-bed bins exclude complete near-bed triangles, not actual support needs.
    """
    tolerance = finite_number(bed_tolerance_mm)
    if not 0 < tolerance <= 0.1:
        raise ValueError("bed numerical tolerance must be positive and <= 0.1 mm")
    _, facets, _ = stl.parse_stl(contents)
    triangles = tuple(triangle for _, triangle in facets)
    original = _geometry(triangles)
    com = None if native_volume_com_mm is None else stl._vector(native_volume_com_mm)
    candidates = []
    for name, raw_rotation in ROTATIONS.items():
        matrix = proper_axis_rotation(raw_rotation)
        rotated = tuple(tuple(rotate(matrix, point) for point in face) for face in triangles)
        bottom = min(point[2] for face in rotated for point in face)
        translation = (0.0, 0.0, -bottom)
        transformed = tuple(tuple((p[0], p[1], p[2] - bottom) for p in face) for face in rotated)
        minimum, maximum, areas, normals, volume, mesh_com = _geometry(transformed)
        if not math.isclose(volume, original[4], rel_tol=1e-12, abs_tol=1e-9) or not math.isclose(
            math.fsum(areas), math.fsum(original[2]), rel_tol=1e-12, abs_tol=1e-9
        ):
            raise ValueError("proper rigid transform changed geometric invariants")
        at_bed = [all(p[2] <= tolerance for p in face) for face in transformed]
        near_bed_points = [p for face in transformed for p in face if p[2] <= tolerance]
        hull = _hull_xy(near_bed_points)
        downward_bins = [[] for _ in range(4)]
        downward_at_bed = []
        for area, normal, bed in zip(areas, normals, at_bed, strict=True):
            if normal[2] >= -1e-12:
                continue
            if bed:
                downward_at_bed.append(area)
                continue
            angle = math.degrees(math.atan2(-normal[2], math.hypot(normal[0], normal[1])))
            index = 0 if angle < 30 else 1 if angle < 45 else 2 if angle < 60 else 3
            downward_bins[index].append(area)
        transformed_com = None
        if com is not None:
            p = rotate(matrix, com)
            transformed_com = (p[0], p[1], p[2] - bottom)
        candidates.append(
            {
                "orientation_id": name,
                "source_to_study_rotation_rows": matrix,
                "rotation_determinant": 1,
                "translation_mm": translation,
                "bounds_mm": {"min": minimum, "max": maximum},
                "extent_xyz_mm": tuple(b - a for a, b in zip(minimum, maximum, strict=True)),
                "signed_winding_volume_mm3": volume,
                "surface_area_mm2": math.fsum(areas),
                "bed_full_triangle_area_mm2": math.fsum(
                    a for a, bed in zip(areas, at_bed, strict=True) if bed
                ),
                "bed_full_triangle_count": sum(at_bed),
                "near_bed_vertex_convex_hull_xy_mm": hull,
                "native_uniform_volume_com_mm": transformed_com,
                "native_com_projection_xy_mm": None
                if transformed_com is None
                else transformed_com[:2],
                "native_com_projection_in_vertex_hull": None
                if transformed_com is None
                else _inside_hull(transformed_com, hull),
                "mesh_winding_volume_centroid_mm": mesh_com,
                "native_minus_mesh_centroid_mm": None
                if transformed_com is None
                else tuple(a - b for a, b in zip(transformed_com, mesh_com, strict=True)),
                "downward_facing_full_bed_triangle_area_mm2": math.fsum(downward_at_bed),
                "above_bed_downward_facing_area_bins_mm2": {
                    label: math.fsum(values)
                    for label, values in zip(
                        (
                            "0_to_30_exclusive",
                            "30_to_45_exclusive",
                            "45_to_60_exclusive",
                            "60_to_90_inclusive",
                        ),
                        downward_bins,
                        strict=True,
                    )
                },
                "orientation_selected": False,
                "physical_stability_or_support_assessed": False,
            }
        )
    return candidates


def build_study(
    audit_contents: bytes,
    mesh_root: Path,
    *,
    expected_audit_sha256=PINNED_NATIVE_AUDIT_SHA256,
    bed_tolerance_mm=1e-5,
):
    """Bind exact audit bytes and source meshes before deriving measurements."""
    actual_hash = hashlib.sha256(audit_contents).hexdigest()
    if actual_hash != expected_audit_sha256:
        raise ValueError("native audit raw SHA256 differs from expected pin")
    audit = _strict_json(audit_contents)
    if (
        not isinstance(audit, dict)
        or type(audit.get("schema_version")) is not int
        or audit["schema_version"] != 1
        or audit.get("evidence_class") != native.HOST_CLASS
        or audit.get("source_revision") != stl.SOURCE_REVISION
    ):
        raise ValueError("unsupported native mesh audit identity")
    selections = audit.get("selections")
    if (
        not isinstance(selections, list)
        or len(selections) != 8
        or any(not isinstance(row, dict) for row in selections)
    ):
        raise ValueError("study requires the eight-row pinned audit")
    rows = [row for row in selections if row.get("draft_candidate") is True]
    if len(rows) != 7 or {row.get("selection_id") for row in rows} != ELIGIBLE_IDS:
        raise ValueError("study requires exactly seven eligible variant identities")
    excluded = [row for row in selections if row.get("draft_candidate") is not True]
    if (
        len(excluded) != 1
        or excluded[0].get("selection_id") != "art4-transmission-column"
        or excluded[0].get("draft_candidate") is not False
    ):
        raise ValueError("blocked column must remain excluded")
    results = []
    for row in rows:
        export = row["native_export"]
        filename = export["filename"]
        stl._safe_source_path(filename)
        if (
            not isinstance(filename, str)
            or PurePosixPath(filename).name != filename
            or "\\" in filename
            or not filename.endswith(".stl")
        ):
            raise ValueError("unsafe mesh filename")
        if (
            row.get("coordinate_frame") != native.FRAME
            or export.get("frame") != native.FRAME
            or export.get("units") != "mm"
        ):
            raise ValueError("mesh frame/unit contract differs")
        payload = stl._bounded_read(mesh_root / filename)
        if (
            hashlib.sha256(payload).hexdigest() != export["sha256"]
            or len(payload) != export["bytes"]
        ):
            raise ValueError("native mesh raw bytes differ from audit")
        mesh = stl.analyze_stl(payload)
        if (
            mesh["triangle_count"] != export["triangle_count"]
            or not mesh["topology"]["closed_consistently_oriented_two_manifold"]
            or mesh["topology"] != row["mesh"]["topology"]
            or mesh["algebraic_signed_volume_interpreted_mm3"] <= 0
        ):
            raise ValueError("eligible native mesh topology/count contract differs")
        results.append(
            {
                "selection_id": row["selection_id"],
                "installed_asset_id": row["installed_asset_id"],
                "geometry_variant": row["geometry_variant"],
                "source_binding": row["source_binding"],
                "native_export": export,
                "source_coordinate_frame": native.FRAME,
                "installed_frame_correspondence": None,
                "orientations": measure_orientations(
                    payload,
                    native_volume_com_mm=row["native_comparison"].get("native_raw_com_mm"),
                    bed_tolerance_mm=bed_tolerance_mm,
                ),
            }
        )
    return {
        "schema_version": 1,
        "evidence_class": (
            "host_unranked_axis_aligned_geometric_orientation_study_not_print_qualification"
        ),
        "source_revision": stl.SOURCE_REVISION,
        "native_mesh_audit_raw_sha256": actual_hash,
        "native_capture_bindings": audit["input_bindings"],
        "counts": {
            "eligible_variants": 7,
            "orientations_per_variant": 6,
            "orientation_measurements": 42,
            "excluded_variants": 1,
        },
        "excluded_selection_ids": ["art4-transmission-column"],
        "conventions": {
            "units": "mm, mm2, mm3",
            "transform": (
                "column vectors R @ source_point + (0,0,-minimum_rotated_z); "
                "proper signed permutation only; XY unchanged after rotation"
            ),
            "build_direction": "+Z",
            "bed_numerical_tolerance_mm": finite_number(bed_tolerance_mm),
            "bed_area": (
                "sum full triangles with all grounded vertices z<=numerical tolerance; "
                "no partial triangle clipping; not physical adhesion/contact tolerance"
            ),
            "near_bed_hull": (
                "convex hull of vertices z<=numerical tolerance; includes gaps; "
                "geometric containment is not stability or adhesion assessment"
            ),
            "com": (
                "native raw BRep geometric volume centroid transformed as a provisional "
                "uniform-volume COM; printed density, infill, material and installed frame unknown"
            ),
            "overhang_angle": (
                "outward winding-normal n, downward if n_z < -1e-12; "
                "angle=atan2(-n_z,hypot(n_x,n_y)), equivalent to asin(-n_z); "
                "from vertical wall0deg to downward horizontal90deg; full near-bed triangles "
                "excluded from above-bed bins"
            ),
            "numerical_invariants": (
                "signed winding volume and triangle area preserved within "
                "relative1e-12/absolute1e-9; no float32 rewrite"
            ),
        },
        "selections": results,
        "qualification": {
            key: False
            for key in (
                "orientation_selected",
                "support_strategy_selected",
                "slicer_import_or_process_validated",
                "physical_stability_assessed",
                "self_intersections_checked",
                "surface_fidelity_qualified",
                "strength_or_fit_qualified",
                "manufacturing_release",
            )
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        type=Path,
        default=ROOT / "hardware/print-planning/thor-native-mesh-audit-v1.json",
    )
    parser.add_argument("--mesh-root", type=Path, required=True)
    parser.add_argument("--bed-tolerance-mm", type=float, default=1e-5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("output must be new; existing evidence is preserved")
        result = build_study(
            stl._bounded_read(args.audit), args.mesh_root, bed_tolerance_mm=args.bed_tolerance_mm
        )
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print("Unranked geometric orientation study:", result["counts"])
        return 0
    except (ValueError, OSError, TypeError, KeyError, OverflowError) as error:
        print(f"Orientation study failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
