"""Reconcile preserved source captures into a draft printable-asset manifest.

This tool reads JSON only. It exports no solids, meshes or machine instructions.
Installed quantities are checked against the existing load overlay rather than
inventing a second classification of purchased and printed components.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

from raftel_arm01.engineering.evidence_files import write_new_evidence

ROOT = Path(__file__).resolve().parents[1]
MIRRORED_REFERENCE = "AssemblyArt56::Unnamed1_GripperFinger_mirrored"
FINGER_REFERENCE = "GripperFinger::Body"
INPUT_PATHS = {
    "inventory": "hardware/cad/thor-mounted-geometry-v2.json",
    "interfaces": "hardware/cad/thor-fabrication-interfaces.json",
    "source_inspection": "hardware/cad/thor-baseline-inspection.json",
}


def _number(value: Any, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a finite number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("expected a finite number") from error
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError("expected a positive finite number" if positive else "nonfinite number")
    return result


def _hash(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("expected a lowercase SHA-256")
    return value


def canonical_sha256(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _orientation_candidates(source: str) -> dict:
    """Inspection prompts, not selected print settings or inferred face normals."""
    name = source.split("::", 1)[0]
    if "Gear" in name or "Pulley" in name or "Optodisk" in name:
        feature = "teeth, hub bore, shaft engagement and radial runout"
        risk = "hub splitting across layers and unsupported tooth/overhang surfaces"
    elif "Bearing" in name or "Tensioner" in name:
        feature = "bearing seat, retention lip, bolt bore and tensioner contact"
        risk = "layer separation around press/bolt loading and trapped seat supports"
    elif name.startswith("Gripper"):
        feature = "jaw pivots, finger contact face and socket/radial retention where present"
        risk = "pivot-boss splitting, jaw bending across layers and inaccessible socket supports"
    elif any(term in name for term in ("Cover", "Fan", "Window", "Box")):
        feature = "thin walls, screw bosses, cable openings and fan/tool access"
        risk = "thin-wall warping, screw-boss splitting and supports trapped in openings"
    else:
        feature = "load-bearing bosses, joint/shaft interfaces and fastener access"
        risk = "tension normal to layers, unsupported bosses and inaccessible internal supports"
    return {
        "status": "inspection_candidates_not_selected_process",
        "primary": "Compare source +Z up after identifying an actual stable bed-contact face",
        "alternative": "Compare source +X up; fixture/support feasibility must be inspected",
        "inspect_features": feature,
        "layer_and_support_risks": risk,
        "actual_orientation_or_supports": None,
        "required_acceptance_source": None,
    }


def build_asset_manifest(
    inventory: dict, interfaces: dict, source_inspection: dict, mass_snapshot: dict
) -> dict:
    """Bind 65 installed print assignments to 46 preserved source assets.

    The reflected finger is a second export variant of one source asset. A
    reflected mesh must never be represented as another copy of the nominal
    geometry. Exact reflection/placement remains a required native export gate.
    """
    revision = interfaces.get("source_revision")
    if (
        not isinstance(revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
        or inventory.get("native_source_revision") != revision
        or source_inspection.get("revision") != revision
        or interfaces.get("printed_part_envelopes", {}).get("source_revision") != revision
    ):
        raise ValueError("source revision mismatch")
    if inventory.get("errors") or inventory.get("missing_object_records"):
        raise ValueError("inventory has unresolved geometry")
    leaves = inventory.get("mounted_bodies", [])
    by_id = {leaf["instance_id"]: leaf for leaf in leaves}
    if len(by_id) != len(leaves) or inventory.get("instance_count") != len(leaves):
        raise ValueError("duplicate or inconsistent inventory instances")
    sources = interfaces["printed_part_envelopes"]["source_shapes"]
    by_source = {row["source_reference"]: row for row in sources}
    if len(by_source) != len(sources):
        raise ValueError("duplicate source shape")
    files = {row["path"].split("/")[-1].casefold(): row for row in source_inspection["files"]}
    if len(files) != len(source_inspection["files"]):
        raise ValueError("ambiguous source file names")
    assignments = [
        row
        for group in mass_snapshot.get("bodies", [])
        for row in group.get("mass_assignments", [])
    ]
    printed = [row for row in assignments if row.get("category", "").startswith("printed_")]
    mass_summary = mass_snapshot.get("mass_assignment_summary", {})
    if (
        mass_summary.get("printed_PLA_density_kg_m3") != 1240
        or mass_summary.get("printed_effective_whole_part_solid_fraction") != 0.5
    ):
        raise ValueError("manifest requires the declared baseline PLA half-solid mass overlay")
    assigned_ids = [row["instance_path"] for row in assignments]
    if len(assigned_ids) != len(set(assigned_ids)):
        raise ValueError("duplicate mass assignment")
    if not printed:
        raise ValueError("no printed mass assignments")
    expected_count = interfaces["printed_part_envelopes"]["printed_installed_leaf_count"]
    if len(printed) != expected_count:
        raise ValueError("printed assignment count differs from source capture")
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in printed:
        leaf = by_id.get(row["instance_path"])
        if leaf is None:
            raise ValueError("printed mass assignment absent from inventory")
        linked = leaf.get("linked_object")
        reflected = linked == MIRRORED_REFERENCE
        source = FINGER_REFERENCE if reflected else linked
        if source not in by_source:
            raise ValueError("printed leaf has no source-envelope disposition")
        source_row = by_source[source]
        volume = _number(leaf["volume_mm3"], positive=True)
        if not math.isclose(
            volume, _number(source_row["volume_mm3"], positive=True), rel_tol=1e-10, abs_tol=1e-5
        ) or not math.isclose(volume, row["volume_mm3"], rel_tol=1e-12, abs_tol=1e-8):
            raise ValueError("installed/source/mass volume mismatch")
        if not math.isclose(
            _number(row["mass_kg"], positive=True),
            volume * 1e-9 * 1240 * 0.5,
            rel_tol=1e-12,
            abs_tol=1e-14,
        ):
            raise ValueError("printed mass differs from declared baseline scenario")
        com = leaf["zero_world_com_m"]
        if not isinstance(com, list) or len(com) != 3:
            raise ValueError("invalid installed COM")
        groups[source].append(
            {
                "instance_id": leaf["instance_id"],
                "linked_object": linked,
                "variant_id": "reflected" if reflected else "nominal",
                "geometry_operation": "saved_assembly_reflection" if reflected else "source_shape",
                "volume_mm3": volume,
                "zero_world_com_m": [_number(v) for v in com],
                "installation_frame": inventory["coordinate_frame"],
                "source_to_installation_transform": None,
                "transform_status": "not_recovered_by_this_JSON_only_tool",
                "baseline_PLA_half_solid_mass_kg": _number(row["mass_kg"], positive=True),
            }
        )
    if set(groups) != set(by_source):
        raise ValueError("uninstalled source shape or missing printed source assignment")
    assets = []
    for source, instances in sorted(groups.items()):
        row = by_source[source]
        file_row = files.get(row["file"].casefold())
        if file_row is None or _hash(row["source_sha256"]) != file_row["sha256"]:
            raise ValueError("source file hash differs from pinned source inspection")
        if row.get("valid_cached_shape") is not True:
            raise ValueError("invalid source shape")
        envelope = [_number(value, positive=True) for value in row["envelope_xyz_mm"]]
        if len(envelope) != 3:
            raise ValueError("invalid source envelope")
        bounds = row["bounds_mm"]
        for axis, length in zip("XYZ", envelope, strict=True):
            actual = _number(bounds[f"{axis}Max"]) - _number(bounds[f"{axis}Min"])
            if not math.isclose(actual, length, rel_tol=1e-10, abs_tol=1e-7):
                raise ValueError("source envelope differs from bounds")
        variants = []
        for variant in sorted({instance["variant_id"] for instance in instances}):
            members = [instance for instance in instances if instance["variant_id"] == variant]
            variants.append(
                {
                    "variant_id": variant,
                    "quantity": len(members),
                    "export_status": "not_exported",
                    "export_sha256": None,
                    "mesh_units": None,
                    "export_frame": (
                        "native source raw Shape coordinates, mm; own placement already applied"
                        if variant == "nominal"
                        else "saved reflected final solid; exact frame/plane needs native capture"
                    ),
                    "required_geometry_operation": (
                        "source_final_solid"
                        if variant == "nominal"
                        else "saved_reflected_final_solid_not_duplicate_nominal_mesh"
                    ),
                }
            )
        assets.append(
            {
                "asset_id": source,
                "source_file": "freecad-src/" + row["file"],
                "source_object": source,
                "source_sha256": row["source_sha256"],
                "source_url": f"https://github.com/AngelLM/Thor/blob/{revision}/freecad-src/{row['file']}",
                "source_geometry_frame": "native source raw Shape coordinates, mm",
                "source_bounds_mm": bounds,
                "source_envelope_xyz_mm": envelope,
                "source_volume_mm3": row["volume_mm3"],
                "quantity": len(instances),
                "installed_volume_mm3": math.fsum(v["volume_mm3"] for v in instances),
                "instances": sorted(instances, key=lambda value: value["instance_id"]),
                "export_variants": variants,
                "orientation_and_inspection": _orientation_candidates(source),
                "history_status": (
                    "unrepaired_original_history; validated_static_snapshot_separate; "
                    "export_only_exact_accepted_final_solid_after_hash_and_native_check"
                    if source == "Art1Body::Body"
                    else "cached_final_shape; not_rebuilt_by_this_tool"
                ),
            }
        )
    return {
        "schema_version": 1,
        "evidence_class": "source_capture_reconciliation_not_export_or_manufacturing_release",
        "source_revision": revision,
        "input_canonical_sha256": {
            "inventory": canonical_sha256(inventory),
            "interfaces": canonical_sha256(interfaces),
            "source_inspection": canonical_sha256(source_inspection),
        },
        "mass_overlay": {
            "method": "existing thor_load_analysis.build_thor_snapshot default PLA scenario",
            "printed_density_kg_m3": 1240,
            "effective_whole_part_solid_fraction": 0.5,
            "slicer_infill_setting": None,
            "measured_mass": False,
            "printed_mass_kg": math.fsum(row["mass_kg"] for row in printed),
        },
        "counts": {
            "installed_printed_leaves": len(printed),
            "unique_source_assets": len(assets),
            "export_geometry_variants": sum(len(a["export_variants"]) for a in assets),
            "reflected_installed_leaves": sum(
                v["variant_id"] == "reflected" for a in assets for v in a["instances"]
            ),
        },
        "installed_printed_volume_mm3": math.fsum(row["volume_mm3"] for row in printed),
        "assets": assets,
        "attribution": {
            "creator": "AngelLM and Thor contributors",
            "project": "Thor",
            "repository": "https://github.com/AngelLM/Thor",
            "declared_repository_license": "CC-BY-SA-4.0",
            "license_url": f"https://github.com/AngelLM/Thor/blob/{revision}/LICENSE",
            "obligations": [
                "Retain creator, source, revision and license link with derivatives/exports",
                "Identify modifications/reflections and preserve applicable ShareAlike obligations",
                "Embedded document metadata conflict remains an attribution review gate",
                "No RAFTEL company-wide license is selected by this manifest",
            ],
        },
        "qualification": {
            "native_export_performed": False,
            "mesh_dimensions_or_manifoldness_validated": False,
            "source_to_installation_transforms_complete": False,
            "sliced": False,
            "physical_mass_or_fit_verified": False,
            "manufacturing_release": False,
        },
    }


def load_manifest_inputs(root: Path = ROOT) -> tuple[dict, dict, dict]:
    return tuple(
        json.loads((root / path).read_text(encoding="utf-8")) for path in INPUT_PATHS.values()
    )


def validate_manifest_inputs(manifest: dict, root: Path = ROOT) -> None:
    """Reject stale report inputs before a manifest is reused for measurements."""
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
    ):
        raise ValueError("unsupported printable manifest schema")
    for role, path in INPUT_PATHS.items():
        data = json.loads((root / path).read_text(encoding="utf-8"))
        if manifest.get("input_canonical_sha256", {}).get(role) != canonical_sha256(data):
            raise ValueError(f"stale printable manifest input: {role}")


def base_interface_svg(interfaces: dict) -> str:
    """Dimensioned source/proposal drawing with machine-readable source coordinates.

    The base rectangle is its bounding envelope, not a fabricated outline. SVG
    coordinates use a reflected y drawing axis so source +Y points upward.
    """
    base = interfaces["base_interface"]
    summary = interfaces["base_mount_summary"]
    proposal = interfaces["proposed_adapter"]
    centers = summary["hole_centers_xy_mm"]
    if len(centers) != 4 or summary.get("recess_top_is_nonplanar") is not True:
        raise ValueError("expected pinned asymmetric base interface capture")
    bore = _number(summary["through_hole_diameter_mm"], positive=True)
    recess = _number(summary["recess_diameter_mm"], positive=True)
    bore_z = [_number(value) for value in summary["through_hole_z_interval_mm"]]
    recess_start = _number(summary["recess_z_start_mm"])
    radius = _number(summary["radius_of_hole_centers_mm"], positive=True)
    if len(bore_z) != 2 or bore_z[0] >= bore_z[1]:
        raise ValueError("invalid bore interval")
    faces = {face["face"]: face for face in base["selected_cylindrical_faces"]}
    for center, face_index in zip(centers, (6, 9, 11, 13), strict=True):
        face = faces.get(face_index)
        if (
            face is None
            or not all(
                math.isclose(_number(a), _number(b), abs_tol=1e-6)
                for a, b in zip(center, face["center_mm"][:2], strict=True)
            )
            or not math.isclose(2 * _number(face["radius_mm"]), bore, abs_tol=1e-8)
            or not math.isclose(math.hypot(*center), radius, abs_tol=1e-6)
            or not math.isclose(face["bounds_mm"]["ZMin"], bore_z[0], abs_tol=1e-6)
            or not math.isclose(face["bounds_mm"]["ZMax"], bore_z[1], abs_tol=1e-6)
        ):
            raise ValueError("source hole table disagrees with saved cylindrical faces")
        reliefs = [
            row
            for row in faces.values()
            if math.isclose(2 * _number(row["radius_mm"]), recess, abs_tol=1e-8)
            and all(
                math.isclose(a, b, abs_tol=1e-6)
                for a, b in zip(center, row["center_mm"][:2], strict=True)
            )
        ]
        if len(reliefs) != 1 or not math.isclose(
            reliefs[0]["bounds_mm"]["ZMin"], recess_start, abs_tol=1e-6
        ):
            raise ValueError("source relief table disagrees with saved cylindrical faces")
    bounds = base["bounds_mm"]
    outer = proposal["candidate_outer_bounds_mm"]
    x0, x1, y0, y1 = (_number(outer[k]) for k in ("x_min", "x_max", "y_min", "y_max"))
    width, height = x1 - x0, y1 - y0
    if width <= 0 or height <= 0:
        raise ValueError("invalid proposed adapter envelope")
    envelope = [bounds[f"{axis}Max"] - bounds[f"{axis}Min"] for axis in "XYZ"]
    source_label = escape("BaseBot::" + base["body"])
    metadata = {
        "evidence_class": "source_dimensions_and_proposed_blank_not_manufacturing_drawing",
        "source_revision": interfaces["source_revision"],
        "interface_capture_canonical_sha256": canonical_sha256(interfaces),
        "source_file": base["source_file"],
        "source_sha256": _hash(base["source_sha256"]),
        "source_object": "BaseBot::" + base["body"],
        "frame": "BaseBot source mm; drawing x=source x, drawing y=-source y",
        "hole_centers_xy_mm": centers,
        "datum_LCS_Bot_matrix_row_major": next(
            row["placement_matrix"] for row in base["datums"] if row["name"] == "LCS_Bot"
        ),
        "proposed_blank_dimensions_mm": [width, height],
        "actual_bench_extrinsics_or_plate_thickness": None,
    }
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" '
        'viewBox="0 0 720 540" role="img" aria-labelledby="title description">',
        '<title id="title">Thor source base interface and proposed adapter blank</title>',
        '<desc id="description">Asymmetric four-hole source pattern, bounding envelope and '
        "separate dashed proposed blank. Dimensions in millimetres. No fabrication release.</desc>",
        "<metadata>" + escape(json.dumps(metadata, sort_keys=True)) + "</metadata>",
        '<rect width="720" height="540" fill="white"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#15212b;font-size:10px}"
        ".dim{stroke:#526170;stroke-width:.7;fill:none}.proposal{stroke:#276ac2;"
        "stroke-dasharray:5 3;stroke-width:1.4;fill:none}.source{stroke:#15212b;"
        "stroke-width:1;fill:none}.recess{stroke:#167a59;stroke-width:.8;fill:none}</style>",
        '<text x="24" y="26" style="font-size:18px;font-weight:bold">Thor base interface</text>',
        '<text x="24" y="43">SOURCE DIMENSIONS + STUDY PROPOSAL · all dimensions mm</text>',
        '<text x="24" y="59" fill="#a33">NO MANUFACTURING RELEASE · not to scale on screen</text>',
        '<g transform="translate(185 270)">',
        f'<rect id="proposed-blank" class="proposal" x="{x0}" y="{-y1}" '
        f'width="{width}" height="{height}"/>',
        f'<rect id="source-envelope" class="source" stroke-dasharray="2 2" '
        f'x="{bounds["XMin"]}" y="{-bounds["YMax"]}" '
        f'width="{bounds["XMax"] - bounds["XMin"]}" '
        f'height="{bounds["YMax"] - bounds["YMin"]}"/>',
    ]
    for label, (x, y), face in zip("ABCD", centers, (6, 9, 11, 13), strict=True):
        lines.extend(
            [
                f'<circle id="hole-{label}" class="source" cx="{x}" cy="{-y}" '
                f'r="{bore / 2}" data-source-x-mm="{x}" data-source-y-mm="{y}" '
                f'data-source-face="{face}"/>',
                f'<circle class="recess" cx="{x}" cy="{-y}" r="{recess / 2}"/>',
                f'<path class="dim" d="M {x - 10} {-y} H {x + 10} M {x} {-y - 10} V {-y + 10}"/>',
                f'<text x="{x + 11}" y="{-y - 8}" style="font-weight:bold">{label}</text>',
            ]
        )
    lines += [
        '<path class="dim" d="M 0 12 V -25 M -12 0 H 25"/>',
        '<text x="27" y="4">+X</text><text x="3" y="-28">+Y</text>',
        '<text x="-28" y="20">LCS_Bot</text>',
        f'<path class="dim" d="M {x0} {y1 + 15} H {x1} '
        f'M {x0} {y1 + 10} V {y1 + 20} M {x1} {y1 + 10} V {y1 + 20}"/>',
        f'<text x="{(x0 + x1) / 2 - 52}" y="{y1 + 29}">{width:g} proposed blank</text>',
        f'<path class="dim" d="M {x0 - 15} {-y1} V {-y0} '
        f'M {x0 - 20} {-y1} H {x0 - 10} M {x0 - 20} {-y0} H {x0 - 10}"/>',
        f'<text x="{x0 - 25}" y="18" transform="rotate(-90 {x0 - 25} 18)">'
        f"{height:g} proposed blank</text>",
        "</g>",
        '<text x="412" y="98" style="font-size:13px;font-weight:bold">'
        f"SOURCE: {source_label}</text>",
        f'<text x="412" y="116">Four Ø{bore:g} bores, source z={bore_z[0]:g} '
        f"to {bore_z[1]:g}</text>",
        f'<text x="412" y="132">Ø{recess:g} relief starts at z={recess_start:g}</text>',
        '<text x="412" y="148">Relief top is nonplanar; depth is not uniform</text>',
        '<text x="412" y="172">Hole    X             Y</text>',
    ]
    for index, (label, (x, y)) in enumerate(zip("ABCD", centers, strict=True)):
        lines.extend(
            [
                f'<text x="412" y="{188 + index * 16}">{label}</text>',
                f'<text x="440" y="{188 + index * 16}">{x:.6f}</text>',
                f'<text x="520" y="{188 + index * 16}">{y:.6f}</text>',
            ]
        )
    lines += [
        f'<text x="412" y="270">All centers lie on R{radius:g}</text>',
        '<text x="412" y="286">Asymmetric pattern; not a square</text>',
        '<text x="412" y="310">Dotted rectangle: source bounding envelope</text>',
        f'<text x="412" y="326">{envelope[0]:.6f} × {envelope[1]:.6f} × {envelope[2]:g}</text>',
        f'<text x="412" y="350" fill="#276ac2">BLUE DASHED: proposed '
        f"{width:g} × {height:g} blank</text>",
        '<text x="412" y="366">Thickness / finished clearance / clamp pads:</text>',
        '<text x="412" y="382">UNSELECTED. Requires bench + wrench data.</text>',
        '<text x="24" y="474">Frame: BaseBot source; LCS_Bot identity. '
        "Bench transform unmeasured.</text>",
        '<text x="24" y="490">Trace: thor-fabrication-interfaces.json · '
        "cylinder faces 6/9/11/13; relief faces 63/64/69/70.</text>",
        '<text x="24" y="506">AngelLM / Thor contributors · CC-BY-SA-4.0 · '
        "preserved source; annotations and blank proposal added.</text>",
        f'<text x="24" y="522">Pinned source {escape(interfaces["source_revision"])} · '
        "no slicing, fit or load qualification.</text>",
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def saved_tool_mating_frames(interfaces: dict) -> dict:
    """Compose the saved mating expression in SI using the shared frame math.

    FreeCAD's serialized Q0/Q1/Q2/Q3 are x/y/z/w. These are saved source
    transforms, never a measured TCP or a solution to the jaw linkage.
    """
    from raftel_arm01.kinematics.thor_frames import compose, inverse, rigid_transform

    def datum(section: str, name: str):
        matches = [row for row in interfaces[section]["datums"] if row["name"] == name]
        if len(matches) != 1:
            raise ValueError("missing or ambiguous source datum")
        flat = matches[0]["placement_matrix"]
        if not isinstance(flat, list) or len(flat) != 16:
            raise ValueError("source datum must have 16 row-major components")
        matrix = [[_number(value) for value in flat[i : i + 4]] for i in range(0, 16, 4)]
        for index in range(3):
            matrix[index][3] /= 1000
        return rigid_transform(matrix)

    source = interfaces["tool_interface_summary"]["saved_gripper_attachment"]
    expression = source["placement_expression"]["expression"]
    expected = (
        "Art56GearPlate_Art56GearPlate.Placement * Art56GearPlate#LCS_Gripper.Placement * "
        "AttachmentOffset * GripperBot#LCS_GripperBot.Placement ^ -1"
    )
    if expression != expected:
        raise ValueError("saved mating expression changed; review transform semantics first")
    offset = source["AttachmentOffset"]
    x, y, z, w = (_number(float(offset[f"Q{index}"])) for index in range(4))
    if not math.isclose(x * x + y * y + z * z + w * w, 1.0, abs_tol=1e-10):
        raise ValueError("source attachment quaternion is not unit length")
    translation = [_number(float(offset[f"P{axis}"])) / 1000 for axis in "xyz"]
    attachment = rigid_transform(
        (
            (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), translation[0]),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), translation[1]),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), translation[2]),
            (0, 0, 0, 1),
        )
    )
    plate_from_mate = datum("tool_plate_interface", "LCS_Gripper")
    gripper_from_mate = datum("gripper_socket_interface", "LCS_GripperBot")
    plate_from_gripper = compose(compose(plate_from_mate, attachment), inverse(gripper_from_mate))
    return {
        "evidence_class": "saved_source_mating_expression_not_calibrated_tool_transform",
        "transform_direction": "parent_from_child; translation in metres",
        "plate_source_from_LCS_Gripper": plate_from_mate,
        "attachment_offset": attachment,
        "gripper_source_from_LCS_GripperBot": gripper_from_mate,
        "plate_source_from_gripper_source": plate_from_gripper,
        "saved_expression": expression,
        "physical_TCP": None,
    }


def tool_interface_svg(interfaces: dict) -> str:
    """Source dimensional schematics; diameter comparison is not a mating overlay."""
    summary = interfaces["tool_interface_summary"]
    plate = interfaces["tool_plate_interface"]
    socket = interfaces["gripper_socket_interface"]
    frames = saved_tool_mating_frames(interfaces)
    male_diameter = _number(summary["plate_male_diameter_mm"], positive=True)
    socket_diameter = _number(summary["gripper_socket_diameter_mm"], positive=True)
    hole_diameter = _number(summary["plate_radial_hole_diameter_mm"], positive=True)
    start, end = [_number(v) for v in summary["plate_male_axial_interval_source_z_mm"]]
    plane = _number(summary["plate_radial_hole_axial_plane_source_z_mm"])
    from_end = _number(summary["plate_radial_hole_plane_from_end_mm"], positive=True)
    if not start < plane < end or not math.isclose(plane - start, from_end, abs_tol=1e-8):
        raise ValueError("radial-hole plane differs from source axial interval")
    male = next(row for row in plate["selected_cylindrical_faces"] if row["face"] == 157)
    socket_face = next(row for row in socket["selected_cylindrical_faces"] if row["face"] == 46)
    if not math.isclose(2 * male["radius_mm"], male_diameter, abs_tol=1e-8) or not math.isclose(
        2 * socket_face["radius_mm"], socket_diameter, abs_tol=1e-8
    ):
        raise ValueError("source interface summary differs from native cylinder capture")
    if not all(
        math.isclose(male["bounds_mm"][key], value, abs_tol=1e-6)
        for key, value in (("ZMin", start), ("ZMax", end))
    ):
        raise ValueError("source male axial interval differs from native cylinder capture")
    directions = summary["plate_radial_hole_lines"]["axis_directions"]
    if len(directions) != 3:
        raise ValueError("expected three radial source hole axes")
    for direction in directions:
        if len(direction) != 3 or not math.isclose(math.hypot(*direction), 1, abs_tol=1e-10):
            raise ValueError("radial hole direction must be unit length")
        if abs(direction[2]) > 1e-10:
            raise ValueError("radial hole axis must lie in plate XY plane")
    if any(
        not math.isclose(sum(a * b for a, b in zip(left, right, strict=True)), -0.5, abs_tol=1e-10)
        for i, left in enumerate(directions)
        for right in directions[i + 1 :]
    ):
        raise ValueError("radial source holes are not spaced 120 degrees")
    metadata = {
        "evidence_class": "source_dimensions_and_saved_frame_table_not_manufacturing_release",
        "source_revision": interfaces["source_revision"],
        "interface_capture_canonical_sha256": canonical_sha256(interfaces),
        "source_files": {
            plate["source_file"]: _hash(plate["source_sha256"]),
            socket["source_file"]: _hash(socket["source_sha256"]),
            summary["saved_assembly_source"]: _hash(summary["saved_assembly_sha256"]),
        },
        "radial_hole_axis_directions": directions,
        "radial_hole_source_z_mm": plane,
        "saved_mating_frames": frames,
    }
    radius = male_diameter / 2
    attachment = frames["attachment_offset"]
    tilt_degrees = math.degrees(
        math.acos(max(-1, min(1, (sum(attachment[i][i] for i in range(3)) - 1) / 2)))
    )
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1000" '
        'viewBox="0 0 720 600" role="img" aria-labelledby="title description">',
        '<title id="title">Thor source socket and radial retention interface</title>',
        '<desc id="description">Source dimensional schematics and saved frame table. '
        "Separate diameters are compared without implying a physical fit. "
        "No fabrication release.</desc>",
        "<metadata>" + escape(json.dumps(metadata, sort_keys=True)) + "</metadata>",
        '<rect width="720" height="600" fill="white"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#15212b;font-size:10px}"
        ".source{stroke:#15212b;stroke-width:1;fill:none}"
        ".dim{stroke:#526170;stroke-width:.7;fill:none}"
        ".axis{stroke:#ac3f24;stroke-width:.8;stroke-dasharray:4 2;fill:none}"
        ".comparison{stroke:#167a59;stroke-width:.8;stroke-dasharray:3 2;fill:none}</style>",
        '<text x="24" y="28" style="font-size:18px;font-weight:bold">Thor tool interface</text>',
        '<text x="24" y="46">SOURCE DIMENSIONS + SAVED MATING FRAMES · '
        "all drawing dimensions mm</text>",
        '<text x="24" y="64">NO MANUFACTURING RELEASE · '
        "dimensions schematic, not to screen scale</text>",
        '<text x="24" y="93" style="font-size:12px;font-weight:bold">'
        "Plate XY diameter comparison</text>",
        '<text x="24" y="109">Dashed socket circle compares sizes; not an assembled overlay</text>',
        '<g transform="translate(140 195) scale(4 -4)">',
        f'<circle id="male-diameter" class="source" cx="0" cy="0" r="{radius}"/>',
        f'<circle id="socket-diameter-comparison" class="comparison" cx="0" cy="0" '
        f'r="{socket_diameter / 2}"/>',
    ]
    for index, (x, y, _) in enumerate(directions):
        lines.append(
            f'<path id="radial-axis-{index}" class="axis" '
            f'd="M {-x * (radius + 3)} {-y * (radius + 3)} '
            f'L {x * (radius + 3)} {y * (radius + 3)}" '
            f'data-source-direction="{x},{y},0"/>'
        )
    lines += [
        "</g>",
        f'<text x="24" y="283">Male Ø{male_diameter:g}; socket Ø{socket_diameter:g}; '
        f"nominal diameter difference {socket_diameter - male_diameter:g}</text>",
        f'<text x="24" y="300">Three Ø{hole_diameter:g} radial axis lines at 120°; '
        "not an axial bolt circle</text>",
        '<text x="372" y="93" style="font-size:12px;font-weight:bold">'
        "Plate source axial section envelope</text>",
        '<text x="372" y="109">Horizontal = source Z; vertical = source X</text>',
        '<g transform="translate(600 195) scale(4)">',
        f'<rect id="male-axial-envelope" class="source" x="{start}" y="{-radius}" '
        f'width="{end - start}" height="{male_diameter}"/>',
        f'<path id="radial-hole-plane" class="axis" d="M {plane} {-radius - 3} V {radius + 3}"/>',
        f'<path class="dim" d="M {start} {radius + 3} H {plane} '
        f'M {start} {radius + 1} V {radius + 5} M {plane} {radius + 1} V {radius + 5}"/>',
        "</g>",
        f'<text x="372" y="283">Source z={start:g} to {end:g}; radial plane z={plane:g}</text>',
        f'<text x="372" y="300">Hole plane {from_end:g} from gripper-side end</text>',
        '<text x="24" y="326">The bottom + top gripper halves jointly form the socket. '
        "CAD diameter difference is not measured fit.</text>",
        '<text x="24" y="344">Saved mating: LCS_Gripper × AttachmentOffset × '
        "inverse(LCS_GripperBot)</text>",
        f'<text x="24" y="361">Offset includes {attachment[2][3] * 1000:+g} mm in '
        f"mating-local Z and {tilt_degrees:g}° tilt. "
        "Keep the full transform; axis alignment alone is insufficient.</text>",
        '<text x="24" y="388" style="font-size:12px;font-weight:bold">'
        "Plate source ← gripper source (row-major; translation in metres)</text>",
    ]
    for index, row in enumerate(frames["plate_source_from_gripper_source"]):
        text = "    ".join(f"{value: .9f}" for value in row)
        lines.append(
            f'<text x="40" y="{408 + index * 17}" style="font-family:monospace" '
            f'xml:space="preserve">{text}</text>'
        )
    lines += [
        '<text x="24" y="488">Trace: Art56GearPlate Face157 / radial faces159,161,162; '
        "GripperBot Face46; saved AssemblyArt56 attachment.</text>",
        '<text x="24" y="506">Full source datums and transforms are embedded in SVG metadata. '
        "Physical TCP, retention, fit and jaw closure remain unverified.</text>",
        '<text x="24" y="532">AngelLM / Thor contributors · CC-BY-SA-4.0 · '
        "preserved geometry; dimensional annotations added.</text>",
        f'<text x="24" y="550">Pinned source {escape(interfaces["source_revision"])}</text>',
        '<text x="24" y="568">This report composes saved rigid transforms only; '
        "it does not rebuild native CAD or solve a linkage.</text>",
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new manifest path")
    parser.add_argument("--svg", type=Path, help="optional dimensioned source/proposal SVG")
    parser.add_argument("--tool-svg", type=Path, help="optional source tool-interface SVG")
    parser.add_argument(
        "--measurement-template", type=Path, help="optional blank per-instance form"
    )
    parser.add_argument(
        "--validate-records", type=Path, help="validate a fabrication-record import"
    )
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "hardware/cad/thor-printable-assets-v1.json"
    )
    args = parser.parse_args(argv)
    try:
        if args.validate_records:
            from raftel_arm01.engineering.fabrication_records import validate_fabrication_records

            if args.svg or args.tool_svg or args.measurement_template:
                raise ValueError("record validation cannot generate drawings or templates")
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            validate_manifest_inputs(manifest)
            result = validate_fabrication_records(
                json.loads(args.validate_records.read_text(encoding="utf-8")), manifest
            )
            write_new_evidence(
                [(args.output, json.dumps(result, indent=2, allow_nan=False) + "\n")],
                protected_inputs=[
                    args.manifest,
                    args.validate_records,
                    *[ROOT / path for path in INPUT_PATHS.values()],
                ],
            )
            print(json.dumps({key: value for key, value in result.items() if key != "records"}))
            return 0
        # Existing tooling owns classification and purchased-asset grouping.
        from thor_load_analysis import build_thor_snapshot

        inventory, interfaces, inspection = load_manifest_inputs()
        manifest = build_asset_manifest(
            inventory, interfaces, inspection, build_thor_snapshot(inventory)
        )
        outputs = [(args.output, json.dumps(manifest, indent=2, allow_nan=False) + "\n")]
        if args.svg:
            outputs.append((args.svg, base_interface_svg(interfaces)))
        if args.tool_svg:
            outputs.append((args.tool_svg, tool_interface_svg(interfaces)))
        if args.measurement_template:
            from raftel_arm01.engineering.fabrication_records import measurement_template

            outputs.append(
                (
                    args.measurement_template,
                    json.dumps(measurement_template(manifest), indent=2, allow_nan=False) + "\n",
                )
            )
        # Validate every requested artifact before writing any output.
        write_new_evidence(outputs, protected_inputs=[ROOT / path for path in INPUT_PATHS.values()])
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"evidence_class": manifest["evidence_class"], "counts": manifest["counts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
