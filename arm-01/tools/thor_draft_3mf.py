"""Compose mesh-only standard 3MF drafts for local slicer inspection.

This is a generic 3MF Core package, not an Anycubic-native project, sliced
toolpath or fabrication release. Closed upstream meshes and separately audited
cached-BRep native exports retain distinct origins. No geometry repair, reflection,
machine G-code, printer/cloud access or process configuration is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import thor_slicer_plan as planner

from raftel_arm01.engineering.scenarios import _strict_json, canonical_sha256, finite_number

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
MODEL_RELATIONSHIP = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
MODEL_CONTENT_TYPE = "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"
VENDOR_NAMESPACE = "urn:raftel:arm01:draft-planning:v1"
PARTS = frozenset({"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"})
SPEC_REFERENCE = {
    "project": "3MF Consortium Core Specification",
    "version": "1.4.0",
    "revision": "997b385e06f3181cf9aae0c578e0b45ccd48ccb2",
    "path": "3MF Core Specification.md",
    "sha256": "4db7a7a13e7f757c6afc1a9ad731b56d8d068b1a766025692ff757d0f7f16940",
    "url": "https://github.com/3MFConsortium/spec_core/blob/997b385e06f3181cf9aae0c578e0b45ccd48ccb2/3MF%20Core%20Specification.md",
    "checked_sections": [
        "3.3 matrices",
        "3.4 model/metadata",
        "4.1 meshes",
        "Appendix C content types/relationships",
    ],
}


def _xml_bytes(element: ET.Element) -> bytes:
    ET.indent(element, space="  ")
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def _indexed_mesh(contents: bytes):
    _, facets, _ = planner.parse_stl(contents)
    by_point = {}
    points = []
    faces = []
    for _, triangle in facets:
        face = []
        for point in triangle:
            if point not in by_point:
                by_point[point] = len(points)
                points.append(point)
            face.append(by_point[point])
        faces.append(tuple(face))
    return tuple(points), tuple(faces)


def _mesh_audit_matches(current, recorded) -> bool:
    """Exact structure/discrete facts with 1e-12 derived-float roundoff only.

    Raw STL bytes and packaged vertices/indices are checked separately and
    exactly. This numerical comparison is not a mesh or manufacturing tolerance.
    JSON lists and in-memory tuples carry the same diagnostic sequence here.
    """
    if isinstance(recorded, dict):
        return (
            isinstance(current, dict)
            and current.keys() == recorded.keys()
            and all(_mesh_audit_matches(current[key], value) for key, value in recorded.items())
        )
    if isinstance(recorded, (list, tuple)):
        return (
            isinstance(current, (list, tuple))
            and len(current) == len(recorded)
            and all(_mesh_audit_matches(a, b) for a, b in zip(current, recorded, strict=True))
        )
    if isinstance(recorded, float):
        return (
            type(current) is float
            and math.isfinite(current)
            and math.isfinite(recorded)
            and math.isclose(current, recorded, rel_tol=1e-12, abs_tol=1e-12)
        )
    return type(current) is type(recorded) and current == recorded


NATIVE_PLAN_CLASS = "selected_cached_native_mesh_audit_and_unreleased_draft_queue"
NATIVE_MESH_ORIGIN = "selected_saved_BRep_native_tessellation"


def _native_origin(plan: dict) -> bool:
    return (
        plan.get("evidence_class") == NATIVE_PLAN_CLASS
        and plan.get("mesh_origin") == NATIVE_MESH_ORIGIN
    )


def _validate_native_binding(plan: dict, row: dict, asset_id: str, variant: str) -> None:
    binding = row.get("native_export_binding")
    if (
        not isinstance(binding, dict)
        or row.get("mesh_origin") != NATIVE_MESH_ORIGIN
        or row.get("geometry_variant") != variant
        or row.get("git_blob_sha1") is not None
    ):
        raise ValueError("native cached export origin/variant binding is missing")
    for key in (
        "native_capture_raw_sha256",
        "native_launcher_raw_sha256",
        "request_raw_sha256",
        "native_mesh_audit_canonical_sha256",
    ):
        value = binding.get(key)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise ValueError("native export requires complete capture/audit hashes")
    if (
        binding["native_mesh_audit_canonical_sha256"]
        != plan.get("native_mesh_audit_canonical_sha256")
        or binding.get("native_to_installed_transform") is not None
        or binding.get("surface_equivalence_qualified") is not False
        or binding.get("coordinate_frame")
        != "saved_BRep_storage_frame_as_read_mm; no extra XML/object/link placement applied"
    ):
        raise ValueError("native export frame/audit scope differs")
    source = binding["source_binding"]
    reference = Path(source["source_file"]).stem + "::" + source["object_name"]
    if variant == "reflected":
        if (
            reference != "AssemblyArt56::Unnamed1_GripperFinger_mirrored"
            or source["object_type"] != "Part::Mirroring"
            or asset_id != "GripperFinger::Body"
        ):
            raise ValueError("native reflected variant needs its actual saved mirrored BRep")
    elif reference != asset_id or source["object_type"] != "PartDesign::Body":
        raise ValueError("native source Body identity differs from installed asset")


def _draft_inputs(plan: dict, asset_id: str, copy_index: int, variant: str = "nominal"):
    if (
        not isinstance(plan, dict)
        or type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
        or plan.get("source_revision") != planner.SOURCE_REVISION
    ):
        raise ValueError("draft package requires the pinned source mesh plan")
    native = _native_origin(plan)
    if not native and (
        plan.get("evidence_class") != "pinned_upstream_STL_audit_and_unreleased_draft_queue"
        or "mesh_origin" in plan
    ):
        raise ValueError(
            "mesh origin must be explicit upstream or separately audited native cached"
        )
    if (
        not isinstance(variant, str)
        or variant not in {"nominal", "reflected"}
        or (not native and variant != "nominal")
    ):
        raise ValueError("a reflected variant requires a separately audited native cached export")
    matches = [
        group
        for group in plan["draft_plate_groups"]
        if group["asset_id"] == asset_id and group["geometry_variant"] == variant
    ]
    if len(matches) != 1:
        raise ValueError("exactly one requested geometry-variant group must match the asset")
    group = matches[0]
    if type(copy_index) is not int or not 1 <= copy_index <= group["repeat_plate_count"]:
        raise ValueError("copy index must be inside the declared nominal quantity")
    expected_stage = (
        "native_cached_mesh_audited_waiting_orientation_and_surface_review"
        if native
        else "source_mesh_audited_waiting_profile_orientation_and_fidelity_review"
    )
    if group["stage"] != expected_stage:
        raise ValueError("plate group is blocked; no package is created")
    if group["source_mesh_path"] is None or asset_id.startswith("Art1Body::"):
        raise ValueError("missing reflected geometry or unresolved Art1 exact-solid gate")
    profile = plan["installed_profile"]
    if (
        not isinstance(profile, dict)
        or profile.get("candidate_inner_rectangle_mm") != [[3, 0], [423, 420]]
        or profile.get("conservative_height_mm") != 500
    ):
        raise ValueError("hash-bound installed profile draft scenario is required")
    if not isinstance(plan["input_canonical_sha256"].get("installed_profile_audit"), str):
        raise ValueError("profile audit provenance is missing")
    mesh_rows = [
        row for row in plan["mesh_audit"] if row["source_path"] == group["source_mesh_path"]
    ]
    if len(mesh_rows) != 1 or mesh_rows[0]["installed_asset_id"] != asset_id:
        raise ValueError("mesh source identity is ambiguous")
    row = mesh_rows[0]
    if native:
        _validate_native_binding(plan, row, asset_id, variant)
    elif (
        "native_export_binding" in row
        or not isinstance(row.get("git_blob_sha1"), str)
        or len(row["git_blob_sha1"]) != 40
        or not row["source_path"].startswith("stl/")
    ):
        raise ValueError("upstream mesh provenance cannot be substituted with a native export")
    if row["mesh"]["topology"]["closed_consistently_oriented_two_manifold"] is not True:
        raise ValueError("mesh topology is blocked")
    proposal = planner.centered_draft_placement(row["mesh"], profile)
    if (
        canonical_sha256(proposal) != canonical_sha256(group["draft_placement_proposal"])
        or proposal["aabb_fit_in_provisional_inner_rectangle"] is not True
    ):
        raise ValueError("draft placement is stale, inconsistent or outside the profile scenario")
    license_rows = [record for record in plan["mesh_audit"] if record["source_path"] == "LICENSE"]
    if len(license_rows) != 1:
        raise ValueError("upstream license provenance is missing")
    return group, row, profile, proposal, license_rows[0]


def build_draft_3mf(
    plan: dict,
    asset_id: str,
    source_mesh: bytes,
    license_bytes: bytes,
    *,
    copy_index: int = 1,
    variant: str = "nominal",
) -> tuple[bytes, dict]:
    """Transcribe one nominal copy with an identity rotation and draft translation.

    Source binary-float vertex values and facet order/winding are preserved
    exactly through 17-digit decimal coordinates. The build has one item;
    repeated required copies receive separate one-part draft files.
    """
    group, row, profile, proposal, license_row = _draft_inputs(plan, asset_id, copy_index, variant)
    if (
        hashlib.sha256(source_mesh).hexdigest() != row["sha256"]
        or hashlib.sha256(license_bytes).hexdigest() != license_row["sha256"]
    ):
        raise ValueError("source mesh or license bytes changed after audit")
    mesh = planner.analyze_stl(source_mesh)
    if (
        mesh["topology"]["closed_consistently_oriented_two_manifold"] is not True
        or mesh["algebraic_signed_volume_interpreted_mm3"] <= 0
    ):
        raise ValueError("a closed, positive-winding source mesh is required; no automatic repair")
    if not _mesh_audit_matches(mesh, row["mesh"]):
        raise ValueError("mesh audit no longer matches the current parser result")
    points, faces = _indexed_mesh(source_mesh)
    title = (
        f"DRAFT_unqualified_{asset_id.split('::')[0]}_"
        f"{copy_index:02d}-of-{group['repeat_plate_count']:02d}"
    )
    native = _native_origin(plan)
    if native:
        title = (
            f"DRAFT_unqualified_NATIVE_CACHED_{asset_id.split('::')[0]}_{variant}_"
            f"{copy_index:02d}-of-{group['repeat_plate_count']:02d}"
        )
    provenance = {
        "evidence_class": "generic_mesh_only_3MF_draft_not_Anycubic_native_project_"
        "or_fabrication_release",
        "source_revision": planner.SOURCE_REVISION,
        "format_reference": SPEC_REFERENCE,
        "source_mesh_path": row["source_path"],
        "source_mesh_sha256": row["sha256"],
        "source_git_blob_sha1": row["git_blob_sha1"],
        "asset_id": asset_id,
        "geometry_variant": variant,
        "copy_index": copy_index,
        "nominal_quantity_required": group["repeat_plate_count"],
        "build_item_quantity": 1,
        "plan_canonical_sha256": canonical_sha256(plan),
        "profile_audit_canonical_sha256": plan["input_canonical_sha256"]["installed_profile_audit"],
        "profile_scenario": profile,
        "placement_proposal": proposal,
        "attribution": plan["attribution"],
        "upstream_license_sha256": license_row["sha256"],
        "modifications": "Source mesh transcribed without repairing/welding/reflecting geometry; "
        "separate identity-rotation build translation only",
        "qualification": {
            "native_geometry_equivalence": False,
            "self_intersections_checked": False,
            "selected_orientation_or_supports_qualified": False,
            "actual_nozzle_or_filament_confirmed": False,
            "Anycubic_GUI_import_observed": False,
            "sliced_or_Gcode_generated": False,
            "printer_or_cloud_contact": False,
            "manufacturing_release": False,
        },
    }
    if native:
        provenance.pop("nominal_quantity_required")
        provenance.update(
            mesh_origin=NATIVE_MESH_ORIGIN,
            variant_quantity_required=group["repeat_plate_count"],
            native_export_binding=row["native_export_binding"],
        )
    model = ET.Element(
        "model",
        {
            "unit": "millimeter",
            "{http://www.w3.org/XML/1998/namespace}lang": "en-US",
            "xmlns": CORE,
            "xmlns:raftel": VENDOR_NAMESPACE,
        },
    )
    metadata = {
        "Title": title,
        "Designer": "AngelLM and Thor contributors; RAFTEL draft planning transcription",
        "Application": "RAFTEL offline mesh-only draft composer",
        "Description": "DRAFT: source Z-up candidate, saved software profile scenario only. "
        "No native-solid equivalence, strength, process or fabrication release.",
        "LicenseTerms": license_bytes.decode("utf-8") + "\nSource: " + row["source_url"],
        "raftel:Provenance": json.dumps(
            provenance, sort_keys=True, separators=(",", ":"), allow_nan=False
        ),
    }
    for name, value in metadata.items():
        ET.SubElement(model, "metadata", {"name": name, "preserve": "true"}).text = value
    resources = ET.SubElement(model, "resources")
    obj = ET.SubElement(
        resources,
        "object",
        {
            "id": "1",
            "type": "model",
            "name": title,
            "partnumber": f"{asset_id}:{variant}:{copy_index}",
        },
    )
    mesh_element = ET.SubElement(obj, "mesh")
    vertices = ET.SubElement(mesh_element, "vertices")
    for point in points:
        ET.SubElement(
            vertices,
            "vertex",
            {
                name: format(value, ".17g")
                for name, value in zip(("x", "y", "z"), point, strict=True)
            },
        )
    triangles = ET.SubElement(mesh_element, "triangles")
    for face in faces:
        ET.SubElement(
            triangles,
            "triangle",
            {name: str(value) for name, value in zip(("v1", "v2", "v3"), face, strict=True)},
        )
    build = ET.SubElement(model, "build")
    translation = proposal["translation_mm"]
    transform = "1 0 0 0 1 0 0 0 1 " + " ".join(format(value, ".17g") for value in translation)
    ET.SubElement(
        build,
        "item",
        {
            "objectid": "1",
            "transform": transform,
            "partnumber": f"{asset_id}:{variant}:{copy_index}",
        },
    )
    content = ET.Element("Types", {"xmlns": CONTENT_TYPES})
    ET.SubElement(
        content,
        "Default",
        {
            "Extension": "rels",
            "ContentType": "application/vnd.openxmlformats-package.relationships+xml",
        },
    )
    ET.SubElement(content, "Default", {"Extension": "model", "ContentType": MODEL_CONTENT_TYPE})
    relationships = ET.Element("Relationships", {"xmlns": RELATIONSHIPS})
    ET.SubElement(
        relationships,
        "Relationship",
        {"Id": "rel0", "Type": MODEL_RELATIONSHIP, "Target": "/3D/3dmodel.model"},
    )
    parts = {
        "[Content_Types].xml": _xml_bytes(content),
        "_rels/.rels": _xml_bytes(relationships),
        "3D/3dmodel.model": _xml_bytes(model),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, value in parts.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, value)
    payload = buffer.getvalue()
    receipt = inspect_draft_3mf(
        payload, source_mesh, plan, asset_id, copy_index=copy_index, variant=variant
    )
    receipt["title"] = title
    return payload, receipt


def inspect_draft_3mf(
    payload: bytes,
    source_mesh: bytes,
    plan: dict,
    asset_id: str,
    *,
    copy_index: int = 1,
    variant: str = "nominal",
) -> dict:
    """Round-trip the generated Core subset; this is not slicer compatibility QA."""
    group, row, profile, proposal, license_row = _draft_inputs(plan, asset_id, copy_index, variant)
    if not isinstance(payload, bytes) or len(payload) > planner.MAX_MESH_BYTES:
        raise ValueError("3MF archive exceeds the bounded input size")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        if (
            len(entries) != 3
            or {info.filename for info in entries} != PARTS
            or sum(info.file_size for info in entries) > planner.MAX_MESH_BYTES
            or any(
                info.flag_bits & 1
                or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                for info in entries
            )
        ):
            raise ValueError("unexpected, encrypted or oversized 3MF package parts")
        parts = {info.filename: archive.read(info) for info in entries}
    if any(
        b"<!DOCTYPE" in value.upper() or b"<!ENTITY" in value.upper() for value in parts.values()
    ):
        raise ValueError("DTD/entity declarations are not allowed")
    content = ET.fromstring(parts["[Content_Types].xml"])
    content_types = {item.get("Extension"): item.get("ContentType") for item in content}
    if (
        content.tag != f"{{{CONTENT_TYPES}}}Types"
        or content_types.get("model") != MODEL_CONTENT_TYPE
    ):
        raise ValueError("invalid 3MF content types")
    relationships = ET.fromstring(parts["_rels/.rels"])
    if (
        relationships.tag != f"{{{RELATIONSHIPS}}}Relationships"
        or len(relationships) != 1
        or relationships[0].get("Type") != MODEL_RELATIONSHIP
        or relationships[0].get("Target") != "/3D/3dmodel.model"
        or relationships[0].get("TargetMode") is not None
    ):
        raise ValueError("invalid or external 3MF start relationship")
    model = ET.fromstring(parts["3D/3dmodel.model"])
    if model.tag != f"{{{CORE}}}model" or model.get("unit") != "millimeter":
        raise ValueError("3MF unit must be millimeter")
    metadata_elements = model.findall(f"{{{CORE}}}metadata")
    metadata = {item.get("name"): item.text for item in metadata_elements}
    if (
        len(metadata) != len(metadata_elements)
        or set(metadata)
        != {"Title", "Designer", "Application", "Description", "LicenseTerms", "raftel:Provenance"}
        or not metadata["Title"].startswith("DRAFT_unqualified_")
    ):
        raise ValueError("3MF draft metadata is missing, duplicated or unlabeled")
    namespaces = dict(
        (prefix, uri)
        for _, (prefix, uri) in ET.iterparse(
            io.BytesIO(parts["3D/3dmodel.model"]), events=("start-ns",)
        )
    )
    if namespaces.get("raftel") != VENDOR_NAMESPACE:
        raise ValueError("custom metadata QName namespace is missing")
    license_text, separator, license_url = metadata["LicenseTerms"].rpartition("\nSource: ")
    if (
        not separator
        or license_url != row["source_url"]
        or hashlib.sha256(license_text.encode("utf-8")).hexdigest() != license_row["sha256"]
    ):
        raise ValueError("upstream license text or attribution was changed")
    provenance = _strict_json(metadata["raftel:Provenance"])
    if (
        provenance["source_mesh_sha256"] != hashlib.sha256(source_mesh).hexdigest()
        or provenance["source_mesh_sha256"] != row["sha256"]
        or provenance.get("asset_id") != asset_id
        or provenance["plan_canonical_sha256"] != canonical_sha256(plan)
        or provenance["geometry_variant"] != variant
        or provenance["copy_index"] != copy_index
        or provenance["build_item_quantity"] != 1
        or provenance.get("upstream_license_sha256") != license_row["sha256"]
        or provenance.get("qualification")
        != {
            "native_geometry_equivalence": False,
            "self_intersections_checked": False,
            "selected_orientation_or_supports_qualified": False,
            "actual_nozzle_or_filament_confirmed": False,
            "Anycubic_GUI_import_observed": False,
            "sliced_or_Gcode_generated": False,
            "printer_or_cloud_contact": False,
            "manufacturing_release": False,
        }
    ):
        raise ValueError("3MF provenance/quantity binding changed")
    native = _native_origin(plan)
    if native and (
        provenance.get("mesh_origin") != NATIVE_MESH_ORIGIN
        or canonical_sha256(provenance.get("native_export_binding"))
        != canonical_sha256(row["native_export_binding"])
        or provenance.get("variant_quantity_required") != group["repeat_plate_count"]
        or "nominal_quantity_required" in provenance
    ):
        raise ValueError("native 3MF provenance/variant quantity binding changed")
    objects = model.findall(f"{{{CORE}}}resources/{{{CORE}}}object")
    items = model.findall(f"{{{CORE}}}build/{{{CORE}}}item")
    if (
        len(objects) != 1
        or objects[0].get("id") != "1"
        or len(items) != 1
        or items[0].get("objectid") != "1"
    ):
        raise ValueError("draft must contain one nominal object and one build item")
    if [child.tag for child in objects[0]] != [f"{{{CORE}}}mesh"] or [
        child.tag for child in objects[0][0]
    ] != [f"{{{CORE}}}vertices", f"{{{CORE}}}triangles"]:
        raise ValueError("unexpected geometry outside the supported mesh-only Core subset")
    points = tuple(
        tuple(finite_number(float(vertex.get(axis))) for axis in ("x", "y", "z"))
        for vertex in objects[0].findall(f"{{{CORE}}}mesh/{{{CORE}}}vertices/{{{CORE}}}vertex")
    )
    faces = tuple(
        tuple(int(triangle.get(axis)) for axis in ("v1", "v2", "v3"))
        for triangle in objects[0].findall(f"{{{CORE}}}mesh/{{{CORE}}}triangles/{{{CORE}}}triangle")
    )
    if (
        not points
        or not faces
        or any(index < 0 or index >= len(points) for face in faces for index in face)
    ):
        raise ValueError("3MF triangle vertex index is out of range")
    original_points, original_faces = _indexed_mesh(source_mesh)
    if points != original_points or faces != original_faces:
        raise ValueError("3MF mesh vertices/winding differ from the exact audited source")
    transform = tuple(
        finite_number(float(value)) for value in items[0].get("transform", "").split()
    )
    if (
        len(transform) != 12
        or transform[:9] != (1, 0, 0, 0, 1, 0, 0, 0, 1)
        or transform[9:] != tuple(proposal["translation_mm"])
    ):
        raise ValueError("3MF build transform differs from the draft translation")
    translated = tuple(tuple(point[i] + transform[9 + i] for i in range(3)) for point in points)
    lo = tuple(min(point[i] for point in translated) for i in range(3))
    hi = tuple(max(point[i] for point in translated) for i in range(3))
    bedlo, bedhi = profile["candidate_inner_rectangle_mm"]
    if (
        any(lo[i] < bedlo[i] - 1e-9 or hi[i] > bedhi[i] + 1e-9 for i in range(2))
        or lo[2] < -1e-9
        or hi[2] > profile["conservative_height_mm"] + 1e-9
    ):
        raise ValueError("3MF transformed bounds exceed the provisional profile scenario")
    receipt = {
        "schema_version": 1,
        "evidence_class": "standard_3MF_structural_roundtrip_not_slicer_"
        "or_manufacturing_validation",
        "package_sha256": hashlib.sha256(payload).hexdigest(),
        "source_mesh_sha256": row["sha256"],
        "asset_id": asset_id,
        "geometry_variant": variant,
        "copy_index": copy_index,
        "nominal_quantity_required": group["repeat_plate_count"],
        "build_item_quantity": 1,
        "vertex_count": len(points),
        "triangle_count": len(faces),
        "units": "millimeter",
        "format_reference": SPEC_REFERENCE,
        "exact_mesh_vertex_index_winding_roundtrip": True,
        "transformed_bounds_mm": {"min": lo, "max": hi},
        "profile_audit_canonical_sha256": plan["input_canonical_sha256"]["installed_profile_audit"],
        "Anycubic_import_observed": False,
        "sliced": False,
        "manufacturing_release": False,
    }
    if native:
        receipt.pop("nominal_quantity_required")
        receipt.update(
            mesh_origin=NATIVE_MESH_ORIGIN,
            variant_quantity_required=group["repeat_plate_count"],
            native_export_binding=row["native_export_binding"],
        )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--upstream-root", "--mesh-root", dest="upstream_root", type=Path, required=True
    )
    parser.add_argument(
        "--license-file",
        type=Path,
        help="Explicit pinned upstream license file for a separate native mesh root",
    )
    parser.add_argument("--asset", required=True)
    parser.add_argument("--copy-index", type=int, default=1)
    parser.add_argument("--variant", choices=("nominal", "reflected"), default="nominal")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = _strict_json(planner._bounded_read(args.plan))
        group, _, _, _, _ = _draft_inputs(plan, args.asset, args.copy_index, args.variant)
        source = (
            args.upstream_root / planner._safe_source_path(group["source_mesh_path"])
        ).resolve()
        root = args.upstream_root.resolve()
        if not source.is_relative_to(root):
            raise ValueError("source mesh escapes its root")
        if args.output.suffix.lower() != ".3mf":
            raise ValueError("draft output must use .3mf extension")
        if args.receipt is not None and args.output.resolve() == args.receipt.resolve():
            raise ValueError("3MF output and JSON receipt must use distinct paths")
        if args.output.exists() or (args.receipt is not None and args.receipt.exists()):
            raise ValueError("existing evidence paths are never overwritten")
        license_path = (
            (args.upstream_root / "LICENSE").resolve()
            if args.license_file is None
            else args.license_file.resolve()
        )
        if args.license_file is None and not license_path.is_relative_to(root):
            raise ValueError("source license escapes its root")
        payload, receipt = build_draft_3mf(
            plan,
            args.asset,
            planner._bounded_read(source),
            planner._bounded_read(license_path),
            copy_index=args.copy_index,
            variant=args.variant,
        )
        with args.output.open("xb") as handle:
            handle.write(payload)
        if args.receipt is not None:
            with args.receipt.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
        print(f"Created generic DRAFT mesh-only 3MF for local inspection: {args.output}")
        return 0
    except (
        ValueError,
        OSError,
        OverflowError,
        KeyError,
        TypeError,
        ET.ParseError,
        zipfile.BadZipFile,
    ) as error:
        print(f"Draft 3MF composition failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
