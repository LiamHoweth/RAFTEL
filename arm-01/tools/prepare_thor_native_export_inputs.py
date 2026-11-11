"""Prepare hash-pinned selected saved-BRep requests without running FreeCAD.

Archives, XML and exact cached Shape entries are read only. Own XML placement,
saved BRep coordinates and installed/world capture coordinates remain separate.
No geometry validity, inertia, native tessellation or fabrication claim follows
from preparing this request. The coordinated native worker owns those checks.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

import thor_art1_diagnostics as xml_audit

from raftel_arm01.engineering.scenarios import _strict_json, canonical_sha256

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
SOURCE_REPOSITORY = "https://github.com/AngelLM/Thor"
MAX_ARCHIVE_BYTES = 50_000_000
MAX_UNCOMPRESSED_BYTES = 150_000_000
TARGETS = (
    ("base-top", "BaseTop::Body", "freecad-src/BaseTop.fcstd", "Body"),
    ("base-bearing-fix", "BaseBearingFix::Body", "freecad-src/BaseBearingFix.fcstd", "Body"),
    ("common-bearing-fix", "CommonBearingFix::Body", "freecad-src/CommonBearingFix.fcstd", "Body"),
    ("art2-window", "Art2BodyAWindow::Body", "freecad-src/Art2BodyAWindow.fcstd", "Body"),
    (
        "art3-tensioner-body",
        "Art3TensionerBody::Body",
        "freecad-src/Art3TensionerBody.fcstd",
        "Body",
    ),
    (
        "art4-transmission-column",
        "Art4TransmissionColumn::Body",
        "freecad-src/Art4TransmissionColumn.fcstd",
        "Body",
    ),
    ("gripper-finger-nominal", "GripperFinger::Body", "freecad-src/GripperFinger.FCStd", "Body"),
    (
        "gripper-finger-reflected",
        "AssemblyArt56::Unnamed1_GripperFinger_mirrored",
        "freecad-src/AssemblyArt56.FCStd",
        "Unnamed1_GripperFinger_mirrored",
    ),
)
FRAME_POLICY = (
    "Raw saved BRep coordinates as stored in the selected archive entry. "
    "Apply no XML/object/ancestor/link placement while reading. Native worker must "
    "record the actual Shape.Placement and compare it separately with XML placement. "
    "No source-to-installed transform is inferred from bounds, COM or identity own placement."
)


def _sha(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _read(path: Path) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(MAX_ARCHIVE_BYTES + 1)
    if not data or len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("input size is empty or outside the bounded archive/JSON limit")
    return data


def _safe_path(raw: str) -> str:
    if not isinstance(raw, str) or "\\" in raw or ":" in raw:
        raise ValueError("source/entry paths require normalized relative POSIX names")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in raw.split("/")):
        raise ValueError("source/entry paths require normalized relative POSIX names")
    return path.as_posix()


def _placement(node: ET.Element) -> tuple[dict | None, dict | None]:
    prop = xml_audit._property(node, "Placement")
    value = None if prop is None else prop.find("PropertyPlacement")
    if value is None:
        return None, None
    values = xml_audit._placement(node)
    return {"position_mm": values[:3], "quaternion_xyzw": values[3:]}, dict(
        sorted(value.attrib.items())
    )


def _context(document: ET.Element, node: ET.Element, kinds: dict) -> dict:
    """Retain saved context as metadata, without solving link/attachment graphs."""
    saved = {}
    for name in (
        "Placement",
        "AttachmentOffset",
        "MapMode",
        "AttachedTo",
        "Support",
        "Source",
        "LinkedObject",
        "LinkPlacement",
        "LinkTransform",
        "Base",
        "Normal",
        "Tip",
        "Group",
        "ExpressionEngine",
    ):
        prop = xml_audit._property(node, name)
        if prop is not None:
            saved[name] = xml_audit._xml_value(prop)
    parents = []
    links = []
    name = node.get("name")
    for candidate in document.findall("./ObjectData/Object"):
        members = [
            link.get("value")
            for link in candidate.findall('./Properties/Property[@name="Group"]/LinkList/Link')
        ]
        if name in members:
            placement, raw = _placement(candidate)
            parents.append(
                {
                    "name": candidate.get("name"),
                    "type": kinds.get(candidate.get("name")),
                    "xml_placement": placement,
                    "raw_xml_placement_attributes": raw,
                    "group_members": members,
                }
            )
    source = xml_audit._property(node, "Source")
    source_link = None if source is None else source.find("Link")
    if source_link is not None:
        linked = document.find(f'./ObjectData/Object[@name="{source_link.get("value")}"]')
        if linked is None:
            raise ValueError("saved mirror Source object is missing")
        props = {
            prop.get("name"): xml_audit._xml_value(prop)
            for prop in linked.findall("./Properties/Property")
            if prop.get("name")
            in {"Placement", "LinkPlacement", "LinkedObject", "LinkTransform", "ExpressionEngine"}
        }
        links.append(
            {
                "name": linked.get("name"),
                "type": kinds.get(linked.get("name")),
                "saved_properties": props,
            }
        )
    return {
        "object_saved_properties": saved,
        "direct_containing_groups": parents,
        "saved_Source_link_context": links,
        "context_interpretation": "saved XML only; no attachment evaluation, "
        "external-document execution or mounted transform recovery",
    }


def inspect_selection(
    source_root: Path, source_file: str, expected_sha256: str, object_name: str
) -> dict:
    source_file = _safe_path(source_file)
    xml_audit._digest(expected_sha256, "source archive SHA256")
    if (
        not isinstance(object_name, str)
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", object_name) is None
    ):
        raise ValueError("selected object needs a safe FreeCAD internal name")
    path = (source_root / source_file).resolve()
    if not path.is_relative_to(source_root.resolve()):
        raise ValueError("source archive escapes the supplied root")
    contents = _read(path)
    if _sha(contents) != expected_sha256:
        raise ValueError(f"pinned source archive SHA256 mismatch: {source_file}")
    with zipfile.ZipFile(io.BytesIO(contents)) as archive:
        entries = archive.infolist()
        if len({entry.filename for entry in entries}) != len(entries):
            raise ValueError("duplicate ZIP archive member")
        if (
            any(entry.flag_bits & 1 for entry in entries)
            or sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_BYTES
        ):
            raise ValueError("encrypted/oversized native archive")
        xml = archive.read("Document.xml")
        if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
            raise ValueError("DTD/entities are not permitted")
        document = ET.fromstring(xml)
        definitions = document.findall("./Objects/Object")
        kinds = {item.get("name"): item.get("type") for item in definitions}
        if len(kinds) != len(definitions):
            raise ValueError("duplicate XML object definition")
        matches = document.findall(f'./ObjectData/Object[@name="{object_name}"]')
        if len(matches) != 1:
            raise ValueError("selected XML object is missing or duplicated")
        node = matches[0]
        if kinds.get(object_name) not in {"PartDesign::Body", "Part::Mirroring"}:
            raise ValueError("selected object is not a declared final Body/mirrored Shape")
        prop = xml_audit._property(node, "Shape")
        parts = [] if prop is None else prop.findall("Part")
        if len(parts) != 1:
            raise ValueError("selected object needs one exact cached Shape entry")
        entry = _safe_path(parts[0].get("file"))
        brep = archive.read(entry)
        if not brep:
            raise ValueError("selected cached BRep is empty")
        placement, raw = _placement(node)
        context = _context(document, node, kinds)
    return {
        "object_type": kinds[object_name],
        "brep_entry": entry,
        "brep_sha256": _sha(brep),
        "brep_bytes": len(brep),
        "xml_placement": placement,
        "raw_xml_placement_attributes": raw,
        "source_archive_bytes": len(contents),
        "document_xml_sha256": _sha(xml),
        "saved_context": context,
    }


def build_request(
    manifest: dict, inspection: dict, inventory: dict, slicer_plan: dict, source_root: Path
) -> dict:
    if (
        manifest.get("source_revision") != SOURCE_REVISION
        or inspection.get("revision") != SOURCE_REVISION
        or inventory.get("native_source_revision") != SOURCE_REVISION
        or slicer_plan.get("source_revision") != SOURCE_REVISION
    ):
        raise ValueError("source/capture revisions do not identify the same pinned Thor baseline")
    assets = {asset["asset_id"]: asset for asset in manifest["assets"]}
    if len(assets) != len(manifest["assets"]):
        raise ValueError("duplicate asset identity")
    files = {row["path"].split("/")[-1].casefold(): row for row in inspection["files"]}
    if len(files) != len(inspection["files"]):
        raise ValueError("ambiguous source inspection filename")
    pins = {
        name: canonical_sha256(data)
        for name, data in (
            ("printable_asset_manifest", manifest),
            ("source_inspection", inspection),
            ("mounted_inventory", inventory),
            ("upstream_slicer_plan", slicer_plan),
        )
    }
    selections = []
    for selection_id, reference, source_file, object_name in TARGETS:
        asset = assets.get(reference)
        source = files.get(source_file.split("/")[-1].casefold())
        if source is None:
            raise ValueError("selected archive lacks the preserved source inspection pin")
        if asset is not None and (
            asset["source_sha256"] != source["sha256"] or asset["source_file"] != source_file
        ):
            raise ValueError("asset and source inspection pins disagree")
        metadata = inspect_selection(source_root, source_file, source["sha256"], object_name)
        mounted = [
            {
                "instance_id": row["instance_id"],
                "volume_mm3": row["volume_mm3"],
                "zero_world_com_m": row["zero_world_com_m"],
                "frame": inventory["coordinate_frame"],
                "source_to_installed_transform": None,
            }
            for row in inventory["mounted_bodies"]
            if row.get("linked_object") == reference
        ]
        if not mounted:
            raise ValueError("selected source has no preserved installed counterpart")
        capture = {
            "frame_policy": FRAME_POLICY,
            "input_canonical_sha256": pins,
            "archive_shape_entry_bytes": metadata["brep_bytes"],
            "archive_bytes": metadata["source_archive_bytes"],
            "document_xml_sha256": metadata["document_xml_sha256"],
            "raw_xml_placement_attributes": metadata["raw_xml_placement_attributes"],
            "saved_xml_context": metadata["saved_context"],
            "preserved_raw_source_shape_reference": None
            if asset is None
            else {
                "frame": asset["source_geometry_frame"],
                "bounds_mm": asset["source_bounds_mm"],
                "volume_mm3": asset["source_volume_mm3"],
                "center_of_mass_mm": None,
                "center_of_mass_status": "no_matching_raw-source_COM_field_"
                "in_these_preserved_captures",
            },
            "preserved_installed_references": mounted,
            "installed_COM_is_not_raw_source_COM": True,
            "frame_invariant_volume_reference_mm3": asset["source_volume_mm3"]
            if asset is not None
            else mounted[0]["volume_mm3"],
            "volume_reference_scope": "Volume is invariant under rigid transforms/reflection; "
            "this reference does not recover a placement",
            "mirrored_source_frame_correspondence": None
            if asset is not None
            else "actual saved mirrored BRep selected; its full source-to-installed "
            "frame relationship remains unverified",
        }
        rows = [
            row for row in slicer_plan["mesh_audit"] if row.get("installed_asset_id") == reference
        ]
        upstream = (
            None
            if not rows
            else {
                "source_path": rows[0]["source_path"],
                "sha256": rows[0]["sha256"],
                "git_blob_sha1": rows[0]["git_blob_sha1"],
                "mesh_kind": "pinned_upstream_STL_not_this_native_BRep_export",
                "mesh_comparison": rows[0]["comparison"],
                "native_to_STL_transform": None,
            }
        )
        selections.append(
            {
                "selection_id": selection_id,
                "source_file": source_file,
                "source_sha256": source["sha256"],
                "object_name": object_name,
                "object_type": metadata["object_type"],
                "brep_entry": metadata["brep_entry"],
                "brep_sha256": metadata["brep_sha256"],
                "xml_placement": metadata["xml_placement"],
                "selection_evidence": "Exact nonempty saved Shape entry selected from pinned "
                "original archive by read-only ZIP/XML inspection; "
                "no native validity or feature-history rebuild claim",
                "uniform_density": None,
                "tessellation": {
                    "linear_deflection_mm": 0.1,
                    "angular_deflection_rad": 0.2,
                    "relative": False,
                    "filename": selection_id + "-cached-native-draft.stl",
                },
                "reference_capture": capture,
                "upstream_stl_reference": upstream,
            }
        )
    if not 1 <= len(selections) <= 8 or len({row["selection_id"] for row in selections}) != len(
        selections
    ):
        raise ValueError("selection request must contain1..8 unique entries")
    return {
        "schema_version": 1,
        "source_revision": SOURCE_REVISION,
        "evidence_class": "selected_saved_BRep_properties_request",
        "selections": selections,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "hardware/cad/thor-printable-assets-v1.json"
    )
    parser.add_argument(
        "--source-inspection",
        type=Path,
        default=ROOT / "hardware/cad/thor-baseline-inspection.json",
    )
    parser.add_argument(
        "--inventory", type=Path, default=ROOT / "hardware/cad/thor-mounted-geometry-v2.json"
    )
    parser.add_argument(
        "--slicer-plan", type=Path, default=ROOT / "hardware/print-planning/thor-draft-plan-v1.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request = build_request(
            *(
                _strict_json(_read(path))
                for path in (
                    args.manifest,
                    args.source_inspection,
                    args.inventory,
                    args.slicer_plan,
                )
            ),
            args.source_root,
        )
        encoded = json.dumps(request, indent=2, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
        print(f"Prepared selected saved-BRep request without native execution: {args.output}")
        return 0
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, ET.ParseError) as error:
        print(f"Native export input preparation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
