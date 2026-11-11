"""Generate independent dimension-study STL coupons, never nominal Thor part exports.

The stepped bore reuses captured BaseBot diameters/lower-bore depth. Its outer
wall and upper recess depth are explicit coupon-design assumptions. No native
solid extraction, slicer action, printer access or fabrication release occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import thor_fabrication_assets as fabrication
import thor_slicer_plan as mesh_tools

from raftel_arm01.engineering.evidence_files import write_new_evidence
from raftel_arm01.engineering.scenarios import _strict_json, canonical_sha256, finite_number

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "source_interfaces": "hardware/cad/thor-fabrication-interfaces.json",
    "saved_profile_audit": "hardware/print-planning/local-profile-audit.json",
}
DEFAULT_OFFSETS_MM = (-0.1, 0.0, 0.1)
BASEBOT_SHA256 = "c637feec821a886c80c8622cf316de02c05f06d90ff49af9df9b0a0cdff00e5a"


def _source_dimensions(interfaces: dict) -> dict:
    if (
        not isinstance(interfaces, dict)
        or type(interfaces.get("schema_version")) is not int
        or interfaces["schema_version"] != 1
        or interfaces.get("validation_class")
        != (
            "native cached dimensions and proposed fabrication acceptance gate; "
            "not manufacturing release"
        )
        or interfaces.get("source_revision") != mesh_tools.SOURCE_REVISION
        or interfaces.get("sources_unchanged") is not True
    ):
        raise ValueError(
            "coupon dimensions require the supported pinned native-capture schema/class"
        )
    base = interfaces.get("base_interface")
    if not isinstance(base, dict) or any(
        base.get(key) != value
        for key, value in (
            ("source_file", "BaseBot.fcstd"),
            ("body", "Body002"),
            ("source_sha256", BASEBOT_SHA256),
            ("coordinate_frame", "source document cached Body coordinates in mm"),
        )
    ):
        raise ValueError("coupon source must be the pinned BaseBot file, Body002, hash and frame")
    faces = base.get("selected_cylindrical_faces")
    expected_faces = {6, 9, 11, 13, 63, 64, 69, 70}
    if (
        not isinstance(faces, list)
        or len(faces) != len(expected_faces)
        or any(not isinstance(face, dict) or type(face.get("face")) is not int for face in faces)
        or {face["face"] for face in faces} != expected_faces
    ):
        raise ValueError("coupon requires the exact referenced BaseBot bore and relief face IDs")
    # Reuse the existing source-face/summary crosschecks. This creates text in
    # memory only; it does not touch the existing drawing or source evidence.
    fabrication.base_interface_svg(interfaces)
    summary = interfaces["base_mount_summary"]
    low, high = summary["through_hole_z_interval_mm"]
    return {
        "source_revision": interfaces["source_revision"],
        "source_file": "freecad-src/" + base["source_file"],
        "source_sha256": base["source_sha256"],
        "source_object": "BaseBot::" + base["body"],
        "source_bore_faces": [6, 9, 11, 13],
        "source_relief_faces": [63, 64, 69, 70],
        "nominal_bore_diameter_mm": summary["through_hole_diameter_mm"],
        "nominal_relief_diameter_mm": summary["recess_diameter_mm"],
        "source_lower_bore_depth_mm": high - low,
        "original_relief_top_is_nonplanar": True,
        "coupon_is_independent_of_original_outer_shape": True,
    }


def _stl(points: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> bytes:
    # Quantize shared vertices once; exact repeated STL vertices retain a
    # coherent indexed topology after unindexing. No repair/weld is applied.
    quantized = [struct.unpack("<3f", struct.pack("<3f", *point)) for point in points]
    result = bytearray(
        b"RAFTEL DRAFT coupon mm; AngelLM/Thor CC-BY-SA-4.0 dimensions; NOT source part".ljust(
            80, b" "
        )
    )
    result.extend(struct.pack("<I", len(faces)))
    for face in faces:
        triangle = tuple(quantized[index] for index in face)
        a, b, c = triangle
        normal = (
            (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
            (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
            (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]),
        )
        length = math.hypot(*normal)
        if length == 0:
            raise ValueError("coupon parameter combination produces a degenerate triangle")
        result.extend(
            struct.pack(
                "<12fH",
                *(value / length for value in normal),
                *(value for point in triangle for value in point),
                0,
            )
        )
    return bytes(result)


def _clearance_ring_dimensions(contents: bytes, *, z_mm: float, upper_radius_mm: float) -> dict:
    _, facets, _ = mesh_tools.parse_stl(contents)
    points = sorted(
        {
            point
            for _, triangle in facets
            for point in triangle
            if point[2] == z_mm and math.hypot(point[0], point[1]) < upper_radius_mm
        },
        key=lambda point: math.atan2(point[1], point[0]),
    )
    if len(points) < 4:
        raise ValueError("cannot recover coupon inner ring from exported STL")
    across_flats = []
    for first, second in zip(points, points[1:] + points[:1], strict=True):
        length = math.hypot(second[0] - first[0], second[1] - first[1])
        across_flats.append(2 * abs(first[0] * second[1] - first[1] * second[0]) / length)
    radii = [math.hypot(point[0], point[1]) for point in points]
    return {
        "ring_vertex_count": len(points),
        "minimum_across_flats_diameter_mm": min(across_flats),
        "minimum_vertex_diameter_mm": 2 * min(radii),
        "maximum_vertex_diameter_mm": 2 * max(radii),
    }


def build_stepped_bore_coupon(
    interfaces: dict,
    *,
    bore_diameter_offset_mm: float,
    outer_diameter_mm: float = 22.0,
    upper_recess_depth_mm: float = 5.0,
    segments: int = 96,
) -> tuple[bytes, dict]:
    """Closed annular stepped cylinder, independent of Thor's final source solid.

    The diameter offset changes only the lower bore. It is a study parameter,
    never a selected shrink/fit allowance. The source relief stays unchanged.
    Coordinates round to a declared 1e-6 mm grid before binary-float STL output.
    """
    source = _source_dimensions(interfaces)
    offset = finite_number(bore_diameter_offset_mm)
    outer = finite_number(outer_diameter_mm)
    upper_depth = finite_number(upper_recess_depth_mm)
    if not -0.5 <= offset <= 0.5:
        raise ValueError("coupon study offset must be inside the explicit +/-0.5 mm study bound")
    if type(segments) is not int or not 32 <= segments <= 512 or segments % 4:
        raise ValueError("segments must be a multiple of four in [32,512]")
    if not 0 < upper_depth <= 20:
        raise ValueError("upper recess study depth must be in (0,20] mm")
    bore = source["nominal_bore_diameter_mm"] + offset
    relief = source["nominal_relief_diameter_mm"]
    lower_depth = source["source_lower_bore_depth_mm"]
    height = lower_depth + upper_depth
    if not 0 < bore < relief < outer <= 60 or outer - relief < 2:
        raise ValueError(
            "coupon needs ordered bore/relief/outer diameters and >=1 mm radial outer wall"
        )
    if not 0 < lower_depth < height:
        raise ValueError("source lower bore depth is invalid")
    rings = [
        (outer / 2, 0),
        (outer / 2, height),
        (bore / 2, 0),
        (bore / 2, lower_depth),
        (relief / 2, lower_depth),
        (relief / 2, height),
    ]
    points = [
        (
            round(radius * math.cos(2 * math.pi * i / segments), 6),
            round(radius * math.sin(2 * math.pi * i / segments), 6),
            z,
        )
        for radius, z in rings
        for i in range(segments)
    ]
    faces = []

    def strip(first_ring: int, second_ring: int, *, reverse: bool = False):
        for index in range(segments):
            following = (index + 1) % segments
            a, b = first_ring * segments + index, first_ring * segments + following
            c, d = second_ring * segments + following, second_ring * segments + index
            triangles = ((a, b, c), (a, c, d))
            faces.extend(tuple(reversed(face)) if reverse else face for face in triangles)

    strip(0, 1)  # outer wall points outward
    strip(0, 2, reverse=True)  # underside annulus points down
    strip(2, 3, reverse=True)  # lower cavity wall points inward
    strip(3, 4, reverse=True)  # step ledge points up
    strip(4, 5, reverse=True)  # upper cavity wall points inward
    strip(5, 1, reverse=True)  # upper annulus points up
    contents = _stl(points, faces)
    audit = mesh_tools.analyze_stl(contents)
    if (
        audit["topology"]["closed_consistently_oriented_two_manifold"] is not True
        or audit["connected_components_by_vertex"] != 1
        or audit["algebraic_signed_volume_interpreted_mm3"] <= 0
    ):
        raise ValueError("generated coupon failed closed, oriented, single-component STL checks")
    polygon_factor = segments * math.sin(2 * math.pi / segments) / 2
    expected_volume = polygon_factor * (
        outer**2 / 4 * height - bore**2 / 4 * lower_depth - relief**2 / 4 * upper_depth
    )
    measured_volume = audit["algebraic_signed_volume_interpreted_mm3"]
    if not math.isclose(measured_volume, expected_volume, rel_tol=2e-6, abs_tol=1e-5):
        raise ValueError("exported coupon volume disagrees with independent polygon-prism formula")
    if not all(
        math.isclose(actual, expected, abs_tol=2e-6)
        for actual, expected in zip(
            audit["envelope_xyz_interpreted_mm"], (outer, outer, height), strict=True
        )
    ):
        raise ValueError("exported coupon envelope differs from explicit dimensions")
    lower_ring = _clearance_ring_dimensions(contents, z_mm=0, upper_radius_mm=(bore + outer) / 4)
    # z=height contains the relief + outer rings only.
    quantized_height = struct.unpack("<f", struct.pack("<f", height))[0]
    upper_ring = _clearance_ring_dimensions(
        contents, z_mm=quantized_height, upper_radius_mm=(relief + outer) / 4
    )
    if lower_ring["ring_vertex_count"] != segments or upper_ring["ring_vertex_count"] != segments:
        raise ValueError("exported coupon ring coverage differs")
    return contents, {
        "evidence_class": "independent_parametric_dimension_study_not_nominal_Thor_part_export",
        "source_dimensions": source,
        "study_parameters": {
            "bore_diameter_offset_mm": offset,
            "offset_is_diametral_not_radial": True,
            "source_nominal_dimension_reference": offset == 0,
            "lower_bore_diameter_mm": bore,
            "upper_relief_diameter_mm": relief,
            "lower_bore_depth_mm": lower_depth,
            "outer_diameter_mm": outer,
            "upper_recess_depth_mm": upper_depth,
            "total_height_mm": height,
            "outer_shape_and_upper_depth_are_coupon_assumptions": True,
            "segments": segments,
            "pre_STL_vertex_rounding_grid_mm": 1e-6,
        },
        "mesh_sha256": hashlib.sha256(contents).hexdigest(),
        "mesh_bytes": len(contents),
        "mesh": audit,
        "digital_dimensional_checks": {
            "expected_faceted_polygon_volume_mm3": expected_volume,
            "mesh_volume_difference_mm3": measured_volume - expected_volume,
            "lower_bore_ring": lower_ring,
            "upper_relief_ring": upper_ring,
            "facets_are_inscribed_not_exact_circles": True,
            "faceting_is_not_a_print_fit_allowance": True,
        },
        "qualification": {
            "native_source_solid_equivalence": False,
            "general_self_intersection_scan_performed": False,
            "actual_printer_nozzle_filament_or_shrinkage_verified": False,
            "fit_or_retention_acceptance": False,
            "sliced_or_Gcode_generated": False,
            "Anycubic_GUI_import_observed": False,
            "manufacturing_release": False,
        },
    }


def build_coupon_study(root: Path = ROOT, *, offsets_mm=DEFAULT_OFFSETS_MM, segments=96):
    interfaces = _strict_json((root / INPUTS["source_interfaces"]).read_bytes())
    profile = _strict_json((root / INPUTS["saved_profile_audit"]).read_bytes())
    if (
        not isinstance(profile, dict)
        or type(profile.get("schema_version")) is not int
        or profile["schema_version"] != 1
        or profile.get("validation_class")
        != (
            "read_only_installed_software_and_saved_profile_metadata_not_physical_printer_"
            "or_print_qualification"
        )
    ):
        raise ValueError(
            "coupon profile context requires the supported saved-software audit schema/class"
        )
    selection = profile.get("saved_selection")
    if (
        not isinstance(selection, dict)
        or not isinstance(selection.get("profile_fields"), dict)
        or selection.get("is_live_gui_state") is not False
        or selection.get("is_physical_hardware_confirmation") is not False
        or selection.get("profile_fields_canonical_sha256")
        != canonical_sha256(selection.get("profile_fields"))
    ):
        raise ValueError("coupon saved-profile selection contract differs")
    profiles = profile.get("profiles")
    if not isinstance(profiles, dict) or any(
        not isinstance(profiles.get(role), dict)
        or not isinstance(profiles[role].get("selected_name"), str)
        or not profiles[role]["selected_name"].strip()
        or selection["profile_fields"].get(role) != profiles[role]["selected_name"]
        for role in ("machine", "process", "filament")
    ):
        raise ValueError("saved profile selectors must match their audited profile identities")
    # Reuse the installed-profile identity/hash/outline validation. The returned
    # software scenario is not used as a selected coupon process or physical fit.
    try:
        mesh_tools.installed_profile_scenario(profile)
    except (KeyError, TypeError) as error:
        raise ValueError("coupon saved-profile selection is incomplete") from error
    offsets = sorted(finite_number(value) for value in offsets_mm)
    if not 1 <= len(offsets) <= 9 or len(offsets) != len(set(offsets)) or 0 not in offsets:
        raise ValueError(
            "supply 1..9 distinct offsets including the zero nominal-dimension reference"
        )
    meshes, receipts = {}, []
    for index, offset in enumerate(offsets, 1):
        contents, receipt = build_stepped_bore_coupon(
            interfaces, bore_diameter_offset_mm=offset, segments=segments
        )
        filename = f"DRAFT_dimension_study_bolt_coupon_{index:02d}.stl"
        meshes[filename] = contents
        receipts.append({"filename": filename, **receipt})
    report = {
        "schema_version": 1,
        "evidence_class": "source_linked_coupon_dimension_study_not_print_or_fabrication_release",
        "input_canonical_sha256": {
            INPUTS["source_interfaces"]: canonical_sha256(interfaces),
            INPUTS["saved_profile_audit"]: canonical_sha256(profile),
        },
        "source_revision": interfaces["source_revision"],
        "design_kind": "independent_stepped_annular_test_piece_not_extracted_Thor_geometry",
        "mesh_units": "mm",
        "mesh_frame": "coupon_local; lower annulus at z=0; concentric bore along +Z",
        "local_pose_is_only_an_orientation_candidate": True,
        "installed_asset_quantities_are_unchanged": True,
        "existing_native_and_upstream_STL_drafts_are_separate": True,
        "saved_profile_context": {
            "evidence_class": "saved_software_selection_only_not_physical_machine_confirmation",
            "profile_used_for_slicing": False,
            "nozzle_material_support_or_process_settings_selected_here": False,
        },
        "coupon_measurement_template": {
            "evidence_state": "unknown",
            "specimen_id": None,
            "coupon_filename": None,
            "coupon_mesh_sha256": None,
            "actual_profile_and_filament_evidence": None,
            "instrument_id": None,
            "instrument_resolution_m": None,
            "measured_lower_bore_xy_m": None,
            "measured_relief_xy_m": None,
            "cleaned_coupon_mass_kg": None,
            "fit_target_part_or_drawing": None,
            "required_fit_interval_m": None,
            "requirement_source": None,
            "acceptance": None,
            "coupon_mass_is_not_installed_arm_mass": True,
        },
        "coupons": receipts,
        "blocked_coupons": [
            {
                "kind": "bearing_seat",
                "reason": "No selected bearing-seat face/fit capture in the bound interface data; "
                "exact bearing variant/drawing and required fit are not inferred from axis lines",
                "nominal_dimension_or_allowance_mm": None,
            }
        ],
        "attribution": {
            "dimension_source": "AngelLM and Thor contributors; BaseBot cached native face capture",
            "repository": mesh_tools.SOURCE_REPOSITORY,
            "revision": interfaces["source_revision"],
            "license": "CC-BY-SA-4.0",
            "license_url": f"{mesh_tools.SOURCE_REPOSITORY}/blob/"
            f"{interfaces['source_revision']}/LICENSE",
            "modifications": "Independent coupon outer wall and upper depth; explicit bore "
            "diameter study variants and faceted mesh generation",
        },
        "manufacturing_release": False,
    }
    return meshes, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="new coupon STL directory")
    parser.add_argument("--report", type=Path, help="optional new external receipt path")
    parser.add_argument("--bore-offset-mm", type=float, action="append")
    parser.add_argument("--segments", type=int, default=96)
    args = parser.parse_args(argv)
    try:
        output = args.output_dir.resolve()
        if output.exists() or args.output_dir.is_symlink():
            raise ValueError("coupon output directory must be new; existing evidence is preserved")
        if args.report and (args.report.exists() or args.report.is_symlink()):
            raise ValueError("coupon report must use a new path")
        if args.report and (
            args.report.resolve() == output or output in args.report.resolve().parents
        ):
            raise ValueError("external receipt must be outside the new mesh directory")
        meshes, report = build_coupon_study(
            offsets_mm=DEFAULT_OFFSETS_MM if args.bore_offset_mm is None else args.bore_offset_mm,
            segments=args.segments,
        )
        output.mkdir(parents=True, exist_ok=False)
        for filename, contents in meshes.items():
            with (output / filename).open("xb") as stream:
                stream.write(contents)
        report_text = json.dumps(report, indent=2, allow_nan=False) + "\n"
        readme = (
            "DRAFT DIMENSION STUDY ONLY - NO FABRICATION RELEASE\n"
            "STL coordinates are millimetres; the file format itself encodes no unit.\n"
            "These independent coupons are not extracted nominal Thor parts.\n"
            "Captured BaseBot diameters/lower-bore depth are source-linked; outer wall,\n"
            "upper recess depth and diameter variants are unqualified study parameters.\n"
            "Read receipt.json for each filename, offset, digital dimensions and hashes.\n"
            "Keep receipt.json with these files. Do not replace original CAD/part meshes.\n"
            "No slicer import, print settings, measured fit or printer start was performed.\n"
            "Dimension source: AngelLM and Thor contributors, CC-BY-SA-4.0.\n"
            f"Source: {mesh_tools.SOURCE_REPOSITORY}/tree/{mesh_tools.SOURCE_REVISION}\n"
            f"License: {report['attribution']['license_url']}\n"
        )
        protected = [ROOT / path for path in INPUTS.values()]
        reports = [(output / "receipt.json", report_text), (output / "README_DRAFT.txt", readme)]
        if args.report:
            reports.append((args.report, report_text))
        write_new_evidence(reports, protected_inputs=protected)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "coupon_count": len(meshes),
                "mesh_directory": str(output),
                "manufacturing_release": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
