"""Prepare all printed cached-BRep descriptors and bounded worker batches.

Read-only ZIP/XML preparation: no FreeCAD import, history rebuild, geometry
repair, source save, physical inertia or fabrication release. The original Art1
archive is required; no unaccepted diagnostic candidate can replace it.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

import prepare_thor_native_export_inputs as selected

from raftel_arm01.engineering.scenarios import _strict_json, canonical_sha256

ROOT = Path(__file__).resolve().parents[1]
COUNTS = {
    "installed_printed_leaves": 65,
    "unique_source_assets": 46,
    "export_geometry_variants": 47,
    "reflected_installed_leaves": 1,
}
ORIGINAL_ARCHIVES = 57
BATCH_LIMIT = 8
ART1_SHA256 = "8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a"
REFLECTED_REFERENCE = "AssemblyArt56::Unnamed1_GripperFinger_mirrored"


def source_files(inspection):
    if type(inspection.get("schema_version")) is not int or inspection["schema_version"] != 1:
        raise ValueError("unsupported source inspection schema")
    if inspection.get("revision") != selected.SOURCE_REVISION:
        raise ValueError("source inspection revision differs from pinned Thor")
    rows = inspection["files"]
    if len(rows) != ORIGINAL_ARCHIVES or inspection.get("source_file_count") != ORIGINAL_ARCHIVES:
        raise ValueError("complete 57-archive source inspection required")
    result = {}
    for row in rows:
        raw = selected._safe_path(row["path"])
        name = raw if raw.startswith("freecad-src/") else "freecad-src/" + raw
        if name.casefold() in result:
            raise ValueError("ambiguous source inspection archive path")
        selected.xml_audit._digest(row["sha256"], "archive SHA256")
        result[name.casefold()] = {"source_file": name, "sha256": row["sha256"]}
    return result


def verify_archives(source_root, files):
    """Verify every original archive, including ten not selected for printing."""
    result = {}
    for row in files.values():
        path = (source_root / row["source_file"]).resolve()
        if not path.is_relative_to(source_root.resolve()):
            raise ValueError("source archive escapes supplied root")
        actual = selected._sha(selected._read(path))
        if actual != row["sha256"]:
            raise ValueError("original archive differs from source inspection pin")
        result[row["source_file"]] = actual
    return result


def registry_rows(manifest, inventory, files):
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("unsupported printable manifest schema")
    if (
        manifest.get("source_revision") != selected.SOURCE_REVISION
        or inventory.get("native_source_revision") != selected.SOURCE_REVISION
    ):
        raise ValueError("manifest/inventory revisions must identify pinned Thor")
    if (
        manifest.get("counts") != COUNTS
        or any(type(manifest["counts"].get(k)) is not int for k in COUNTS)
        or len(manifest["assets"]) != COUNTS["unique_source_assets"]
    ):
        raise ValueError("full 46-asset/47-variant/65-instance manifest required")
    if manifest["input_canonical_sha256"]["inventory"] != canonical_sha256(inventory):
        raise ValueError("manifest inventory canonical pin differs")
    mounted = {r["instance_id"]: r for r in inventory["mounted_bodies"]}
    if len(mounted) != len(inventory["mounted_bodies"]):
        raise ValueError("duplicate mounted instance identity")
    assets, instances, rows = set(), set(), []
    for asset in sorted(manifest["assets"], key=lambda a: a["asset_id"]):
        identity = asset["asset_id"]
        if identity in assets or asset["source_object"] != identity:
            raise ValueError("duplicate or inconsistent source asset identity")
        assets.add(identity)
        document, separator, obj = identity.partition("::")
        if not separator or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", obj) is None:
            raise ValueError("asset must identify one safe document/object")
        if Path(asset["source_file"]).stem != document:
            raise ValueError("asset document and source filename disagree")
        source = files.get(asset["source_file"].casefold())
        if (
            source is None
            or source["source_file"] != asset["source_file"]
            or source["sha256"] != asset["source_sha256"]
        ):
            raise ValueError("asset/source inspection archive pins disagree")
        if identity == "Art1Body::Body" and asset["source_sha256"] != ART1_SHA256:
            raise ValueError("Art1 must remain the original pinned cached Body")
        variants = {v["variant_id"]: v for v in asset["export_variants"]}
        if len(variants) != len(asset["export_variants"]) or not set(variants) <= {
            "nominal",
            "reflected",
        }:
            raise ValueError("unknown or duplicate geometry variant")
        if type(asset["quantity"]) is not int or asset["quantity"] != len(asset["instances"]):
            raise ValueError("asset quantity differs from installed instances")
        if sum(v["quantity"] for v in variants.values()) != asset["quantity"]:
            raise ValueError("variant quantities do not reconcile asset quantity")
        for variant_id, variant in sorted(variants.items()):
            members = sorted(
                [r for r in asset["instances"] if r["variant_id"] == variant_id],
                key=lambda r: r["instance_id"],
            )
            quantity = variant["quantity"]
            if type(quantity) is not int or quantity < 1 or len(members) != quantity:
                raise ValueError("variant quantity differs from installed membership")
            source_file, object_name = asset["source_file"], obj
            reference = identity
            if variant_id == "reflected":
                if identity != "GripperFinger::Body" or quantity != 1:
                    raise ValueError("only the actual saved reflected finger is supported")
                reference = REFLECTED_REFERENCE
                source_file = files["freecad-src/assemblyart56.fcstd"]["source_file"]
                object_name = reference.partition("::")[2]
            for member in members:
                name = member["instance_id"]
                preserved = mounted.get(name)
                operation = (
                    "source_shape" if variant_id == "nominal" else "saved_assembly_reflection"
                )
                if (
                    name in instances
                    or member["linked_object"] != reference
                    or member["geometry_operation"] != operation
                    or preserved is None
                    or preserved["linked_object"] != reference
                    or preserved["volume_mm3"] != member["volume_mm3"]
                    or preserved["zero_world_com_m"] != member["zero_world_com_m"]
                ):
                    raise ValueError("installed identity/variant/source correspondence disagrees")
                instances.add(name)
            rows.append(
                dict(
                    asset_id=identity,
                    geometry_variant=variant_id,
                    quantity_required=quantity,
                    source_file=source_file,
                    object_name=object_name,
                    source_sha256=files[source_file.casefold()]["sha256"],
                    members=members,
                    source_asset_canonical_sha256=canonical_sha256(asset),
                    history_status=asset["history_status"],
                )
            )
    if (
        len(rows) != 47
        or len(instances) != 65
        or sum(r["geometry_variant"] == "reflected" for r in rows) != 1
    ):
        raise ValueError("complete unique 47-variant/65-instance reconciliation failed")
    return rows


def build_request(manifest, inspection, inventory, source_root):
    files = source_files(inspection)
    if manifest["input_canonical_sha256"]["source_inspection"] != canonical_sha256(inspection):
        raise ValueError("manifest source inspection canonical pin differs")
    registry = registry_rows(manifest, inventory, files)
    before = verify_archives(source_root, files)
    pins = {
        name: canonical_sha256(value)
        for name, value in (
            ("printable_asset_manifest", manifest),
            ("source_inspection", inspection),
            ("mounted_inventory", inventory),
        )
    }
    registry_hash = canonical_sha256(registry)
    selections = []
    for index, row in enumerate(registry, 1):
        metadata = selected.inspect_selection(
            source_root, row["source_file"], row["source_sha256"], row["object_name"]
        )
        expected_type = (
            "Part::Mirroring" if row["geometry_variant"] == "reflected" else "PartDesign::Body"
        )
        if metadata["object_type"] != expected_type:
            raise ValueError("saved final-shape type differs from declared geometry variant")
        identifier = (
            f"print-{index:02d}-{Path(row['source_file']).stem.lower()}-"
            f"{row['object_name'].lower()}-{row['geometry_variant']}"
        )
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", identifier) is None:
            raise ValueError("selection identifier is not safe or exceeds worker limit")
        context_hash = canonical_sha256(metadata["saved_context"])
        selections.append(
            dict(
                selection_id=identifier,
                source_file=row["source_file"],
                source_sha256=row["source_sha256"],
                object_name=row["object_name"],
                object_type=metadata["object_type"],
                brep_entry=metadata["brep_entry"],
                brep_sha256=metadata["brep_sha256"],
                xml_placement=metadata["xml_placement"],
                selection_evidence=(
                    "Read-only original-archive saved Shape descriptor; "
                    "no history rebuild/native geometry validity or print qualification"
                ),
                uniform_density=None,
                tessellation=dict(
                    linear_deflection_mm=0.1,
                    angular_deflection_rad=0.2,
                    relative=False,
                    filename=identifier + "-cached-native-draft.stl",
                ),
                reference_capture=dict(
                    evidence_class="full_print_registry_host_preparation_not_native_export",
                    input_canonical_sha256=pins,
                    canonical_variant_registry_sha256=registry_hash,
                    counts=copy.deepcopy(COUNTS),
                    original_archive_count_verified=57,
                    original_archive_set_canonical_sha256=canonical_sha256(before),
                    original_archive_bytes_verified_before_after=True,
                    asset_id=row["asset_id"],
                    geometry_variant=row["geometry_variant"],
                    quantity_required=row["quantity_required"],
                    source_asset_canonical_sha256=row["source_asset_canonical_sha256"],
                    installed_instances=[
                        dict(
                            instance_id=m["instance_id"],
                            linked_object=m["linked_object"],
                            variant_id=m["variant_id"],
                            geometry_operation=m["geometry_operation"],
                            preserved_installed_volume_mm3=m["volume_mm3"],
                            preserved_installed_COM_m=m["zero_world_com_m"],
                            installed_coordinate_frame=inventory["coordinate_frame"],
                            source_to_installed_transform=None,
                        )
                        for m in row["members"]
                    ],
                    installed_instance_set_canonical_sha256=canonical_sha256(
                        [m["instance_id"] for m in row["members"]]
                    ),
                    history_status=row["history_status"],
                    frame_policy=selected.FRAME_POLICY,
                    archive_bytes=metadata["source_archive_bytes"],
                    archive_shape_entry_bytes=metadata["brep_bytes"],
                    document_xml_sha256=metadata["document_xml_sha256"],
                    raw_xml_placement_attributes=metadata["raw_xml_placement_attributes"],
                    saved_xml_context=metadata["saved_context"],
                    saved_xml_context_canonical_sha256=context_hash,
                    upstream_attribution=manifest["attribution"],
                    worker_batch_limit=8,
                    qualification=dict(
                        native_cached_BRep_validated=False,
                        feature_history_rebuilt=False,
                        exact_Art1_migration_accepted=False,
                        mesh_topology_or_fidelity_accepted=False,
                        mounted_transform_recovered=False,
                        physical_mass_or_inertia_known=False,
                        manufacturing_released=False,
                    ),
                ),
                upstream_stl_reference=None,
            )
        )
    if verify_archives(source_root, files) != before:
        raise ValueError("original archive bytes changed during descriptor preparation")
    return dict(
        schema_version=1,
        source_revision=selected.SOURCE_REVISION,
        evidence_class="selected_saved_BRep_properties_request",
        selections=selections,
    )


def worker_batches(request):
    rows = request["selections"]
    if (
        len(rows) != 47
        or len({r["selection_id"] for r in rows}) != 47
        or len({(r["source_file"], r["object_name"]) for r in rows}) != 47
    ):
        raise ValueError("batching requires the complete 47-variant registry")
    return [
        {
            **copy.deepcopy(request),
            "selections": copy.deepcopy(request["selections"][i : i + BATCH_LIMIT]),
        }
        for i in range(0, 47, BATCH_LIMIT)
    ]


def main(argv=None):
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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-directory", type=Path)
    args = parser.parse_args(argv)
    try:
        inputs = (args.manifest, args.source_inspection, args.inventory)
        if args.output.exists() or (
            args.batch_directory is not None and args.batch_directory.exists()
        ):
            raise ValueError("existing request or batch evidence paths are never overwritten")
        output = args.output.resolve()
        if output.is_relative_to(args.source_root.resolve()) or output in {
            p.resolve() for p in inputs
        }:
            raise ValueError("request output must remain outside source/input paths")
        if args.batch_directory is not None and (
            args.batch_directory.resolve().is_relative_to(args.source_root.resolve())
            or output.is_relative_to(args.batch_directory.resolve())
        ):
            raise ValueError("batch evidence must be separate from source and full request")
        request = build_request(
            *(_strict_json(selected._read(p)) for p in inputs), args.source_root
        )
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(request, indent=2, allow_nan=False) + "\n")
        if args.batch_directory is not None:
            args.batch_directory.mkdir(exist_ok=False)
            for index, batch in enumerate(worker_batches(request), 1):
                with (args.batch_directory / f"batch-{index:02d}.json").open(
                    "x", encoding="utf-8", newline="\n"
                ) as stream:
                    stream.write(json.dumps(batch, indent=2, allow_nan=False) + "\n")
        print(
            "Prepared 47 cached geometry variants / 65 instances; "
            "current native worker needs six serialized batches; no native process launched"
        )
        return 0
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        selected.zipfile.BadZipFile,
        selected.ET.ParseError,
    ) as error:
        print(f"Full print descriptor preparation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
