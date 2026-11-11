"""Generic mesh-only 3MF roundtrips, not Anycubic import or print acceptance."""

import copy
import hashlib
import importlib.util
import io
import json
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
if "thor_slicer_plan" not in sys.modules:
    SPEC = importlib.util.spec_from_file_location(
        "thor_slicer_plan", ROOT / "tools/thor_slicer_plan.py"
    )
    planner = importlib.util.module_from_spec(SPEC)
    sys.modules[SPEC.name] = planner
    SPEC.loader.exec_module(planner)
else:
    planner = sys.modules["thor_slicer_plan"]
SPEC = importlib.util.spec_from_file_location("thor_draft_3mf", ROOT / "tools/thor_draft_3mf.py")
draft = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = draft
SPEC.loader.exec_module(draft)


def tetrahedron():
    points = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    faces = ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))
    return (
        b"synthetic-float-fixture".ljust(80, b" ")
        + struct.pack("<I", 4)
        + b"".join(
            struct.pack("<12fH", 0.0, 0.0, 0.0, *(x for vertex in face for x in points[vertex]), 0)
            for face in faces
        )
    )


@pytest.fixture
def inputs():
    # This is a small package-format fixture, not an upstream geometry claim.
    source = tetrahedron()
    license_bytes = b"Synthetic license text fixture\n"
    profile = draft.planner.installed_profile_scenario(
        json.loads((ROOT / "hardware/print-planning/local-profile-audit.json").read_bytes())
    )
    mesh = planner.analyze_stl(source)
    asset = "CommonBearingFix::Body"
    row = {
        "source_path": "stl/CommonBearingFix.stl",
        "source_url": f"{planner.SOURCE_REPOSITORY}/blob/{planner.SOURCE_REVISION}/"
        "stl/CommonBearingFix.stl",
        "git_blob_sha1": hashlib.sha1(
            b"blob " + str(len(source)).encode() + b"\0" + source
        ).hexdigest(),
        "sha256": hashlib.sha256(source).hexdigest(),
        "installed_asset_id": asset,
        "mesh": mesh,
    }
    plan = {
        "schema_version": 1,
        "evidence_class": "pinned_upstream_STL_audit_and_unreleased_draft_queue",
        "source_revision": planner.SOURCE_REVISION,
        "input_canonical_sha256": {"installed_profile_audit": "1" * 64},
        "installed_profile": profile,
        "mesh_audit": [
            row,
            {"source_path": "LICENSE", "sha256": hashlib.sha256(license_bytes).hexdigest()},
        ],
        "attribution": {
            "creator": "Synthetic geometry test fixture; production artifact retains "
            "AngelLM/Thor attribution",
            "declared_repository_license": "CC-BY-SA-4.0",
        },
        "draft_plate_groups": [
            {
                "asset_id": asset,
                "geometry_variant": "nominal",
                "repeat_plate_count": 4,
                "stage": "source_mesh_audited_waiting_profile_orientation_and_fidelity_review",
                "source_mesh_path": row["source_path"],
                "draft_placement_proposal": planner.centered_draft_placement(mesh, profile),
            }
        ],
    }
    return plan, asset, source, license_bytes


def rewrite_package(payload, mutate):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    mutate(parts)
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in parts.items():
            archive.writestr(name, contents)
    return target.getvalue()


def change_model(parts, mutate):
    model = ET.fromstring(parts["3D/3dmodel.model"])
    mutate(model)
    # QName-valued metadata needs this declaration even after ET reserialization.
    model.set("xmlns:raftel", draft.VENDOR_NAMESPACE)
    parts["3D/3dmodel.model"] = ET.tostring(model, encoding="utf-8", xml_declaration=True)


def test_generic_core_roundtrip_exact_geometry_units_transform_and_quantity(inputs):
    plan, asset, source, license_bytes = inputs
    payload, receipt = draft.build_draft_3mf(plan, asset, source, license_bytes, copy_index=2)
    assert receipt["units"] == "millimeter"
    assert receipt["vertex_count"] == 4 and receipt["triangle_count"] == 4
    assert receipt["copy_index"] == 2 and receipt["nominal_quantity_required"] == 4
    assert receipt["build_item_quantity"] == 1
    assert receipt["transformed_bounds_mm"] == {"min": (212.5, 209.5, 0), "max": (213.5, 210.5, 1)}
    assert receipt["exact_mesh_vertex_index_winding_roundtrip"]
    assert not receipt["Anycubic_import_observed"] and not receipt["manufacturing_release"]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == draft.PARTS
        assert not any(name.lower().endswith((".gcode", ".bgcode")) for name in archive.namelist())
        assert b"DRAFT_unqualified_" in archive.read("3D/3dmodel.model")


def test_reproducible_package_and_copy_quantity_failure(inputs):
    plan, asset, source, license_bytes = inputs
    first, _ = draft.build_draft_3mf(plan, asset, source, license_bytes)
    second, _ = draft.build_draft_3mf(plan, asset, source, license_bytes)
    assert first == second
    for index in (0, 5, True):
        with pytest.raises(ValueError, match="copy index"):
            draft.build_draft_3mf(plan, asset, source, license_bytes, copy_index=index)


@pytest.mark.parametrize(
    "kind", ["topology", "missing_profile", "stale_placement", "Art1", "missing_reflection"]
)
def test_blocked_sources_and_unverified_profile_or_placement_reject(inputs, kind):
    plan, asset, source, license_bytes = inputs
    bad = copy.deepcopy(plan)
    if kind == "topology":
        bad["draft_plate_groups"][0]["stage"] = "blocked_source_mesh_topology"
    elif kind == "missing_profile":
        bad["installed_profile"] = None
    elif kind == "stale_placement":
        bad["draft_plate_groups"][0]["draft_placement_proposal"]["translation_mm"][0] = 0
    elif kind == "Art1":
        asset = "Art1Body::Body"
        bad["draft_plate_groups"][0]["asset_id"] = asset
    else:
        bad["draft_plate_groups"][0]["source_mesh_path"] = None
    with pytest.raises(ValueError):
        draft.build_draft_3mf(bad, asset, source, license_bytes)


@pytest.mark.parametrize(
    "field,value", [("unit", "inch"), ("transform", "1 0 0 0 1 0 0 0 1 0 0 0")]
)
def test_wrong_units_or_build_transform_are_detected(inputs, field, value):
    plan, asset, source, license_bytes = inputs
    payload, _ = draft.build_draft_3mf(plan, asset, source, license_bytes)

    def mutate(model):
        target = (
            model if field == "unit" else model.find(f"{{{draft.CORE}}}build/{{{draft.CORE}}}item")
        )
        target.set(field, value)

    changed = rewrite_package(payload, lambda parts: change_model(parts, mutate))
    with pytest.raises(ValueError):
        draft.inspect_draft_3mf(changed, source, plan, asset)


def test_triangle_indices_winding_and_license_removal_detected(inputs):
    plan, asset, source, license_bytes = inputs
    payload, _ = draft.build_draft_3mf(plan, asset, source, license_bytes)

    def triangle(model):
        model.find(f".//{{{draft.CORE}}}triangle").set("v1", "9")

    def license_change(model):
        next(
            item
            for item in model.findall(f"{{{draft.CORE}}}metadata")
            if item.get("name") == "LicenseTerms"
        ).text = "removed license"

    for mutate in (triangle, license_change):
        changed = rewrite_package(payload, lambda parts, mutate=mutate: change_model(parts, mutate))
        with pytest.raises(ValueError):
            draft.inspect_draft_3mf(changed, source, plan, asset)
    with pytest.raises(ValueError, match="bytes changed"):
        draft.build_draft_3mf(plan, asset, source + b"changed", license_bytes)


def test_extra_parts_and_external_relationship_reject(inputs):
    plan, asset, source, license_bytes = inputs
    payload, _ = draft.build_draft_3mf(plan, asset, source, license_bytes)
    changed = rewrite_package(
        payload, lambda parts: parts.update({"machine.gcode": b"not a permitted part"})
    )
    with pytest.raises(ValueError, match="package parts"):
        draft.inspect_draft_3mf(changed, source, plan, asset)

    def external(parts):
        relationships = ET.fromstring(parts["_rels/.rels"])
        relationships[0].set("TargetMode", "External")
        parts["_rels/.rels"] = ET.tostring(relationships)

    changed = rewrite_package(payload, external)
    with pytest.raises(ValueError, match="external"):
        draft.inspect_draft_3mf(changed, source, plan, asset)


def test_cli_preserves_existing_artifact_and_lf_receipt(inputs, tmp_path):
    plan, asset, source, license_bytes = inputs
    source_root = tmp_path / "upstream"
    (source_root / "stl").mkdir(parents=True)
    (source_root / "stl/CommonBearingFix.stl").write_bytes(source)
    (source_root / "LICENSE").write_bytes(license_bytes)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8", newline="\n")
    output = tmp_path / "DRAFT.3mf"
    receipt = tmp_path / "receipt.json"
    args = [
        "--plan",
        str(plan_path),
        "--upstream-root",
        str(source_root),
        "--asset",
        asset,
        "--output",
        str(output),
        "--receipt",
        str(receipt),
    ]
    assert draft.main(args) == 0
    original = output.read_bytes()
    assert b"\r\n" not in receipt.read_bytes()
    assert draft.main(args) == 2
    assert output.read_bytes() == original


def test_cli_receipt_output_alias_fails_before_creating_any_artifact(inputs, tmp_path):
    plan, asset, source, license_bytes = inputs
    source_root = tmp_path / "upstream"
    (source_root / "stl").mkdir(parents=True)
    (source_root / "stl/CommonBearingFix.stl").write_bytes(source)
    (source_root / "LICENSE").write_bytes(license_bytes)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8", newline="\n")
    output = tmp_path / "DRAFT.3mf"
    assert (
        draft.main(
            [
                "--plan",
                str(plan_path),
                "--upstream-root",
                str(source_root),
                "--asset",
                asset,
                "--output",
                str(output),
                "--receipt",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()


def test_derived_mesh_diagnostic_roundoff_only_is_tolerated(inputs):
    plan, asset, source, license_bytes = inputs
    rounded = copy.deepcopy(plan)
    rounded["mesh_audit"][0]["mesh"]["surface_area_interpreted_mm2"] += 1e-13
    _, receipt = draft.build_draft_3mf(rounded, asset, source, license_bytes)
    assert receipt["exact_mesh_vertex_index_winding_roundtrip"]
    changed = copy.deepcopy(plan)
    changed["mesh_audit"][0]["mesh"]["surface_area_interpreted_mm2"] += 1e-3
    with pytest.raises(ValueError, match="audit no longer matches"):
        draft.build_draft_3mf(changed, asset, source, license_bytes)

    changed = copy.deepcopy(plan)
    changed["mesh_audit"][0]["mesh"]["triangle_count"] += 1
    with pytest.raises(ValueError, match="audit no longer matches"):
        draft.build_draft_3mf(changed, asset, source, license_bytes)


def native_inputs(inputs, *, reflected=False):
    plan, asset, source, license_bytes = copy.deepcopy(inputs)
    plan.update(
        evidence_class=draft.NATIVE_PLAN_CLASS,
        mesh_origin=draft.NATIVE_MESH_ORIGIN,
        native_mesh_audit_canonical_sha256="7" * 64,
    )
    row = plan["mesh_audit"][0]
    group = plan["draft_plate_groups"][0]
    variant = "reflected" if reflected else "nominal"
    if reflected:
        asset = "GripperFinger::Body"
        row["installed_asset_id"] = asset
        group.update(asset_id=asset, geometry_variant=variant, repeat_plate_count=1)
    binding = {
        "native_capture_raw_sha256": "1" * 64,
        "native_launcher_raw_sha256": "2" * 64,
        "request_raw_sha256": "3" * 64,
        "native_mesh_audit_canonical_sha256": "7" * 64,
        "selection_id": "synthetic-native-fixture",
        "source_binding": {
            "source_file": "freecad-src/AssemblyArt56.FCStd"
            if reflected
            else "freecad-src/CommonBearingFix.fcstd",
            "object_name": "Unnamed1_GripperFinger_mirrored" if reflected else "Body",
            "object_type": "Part::Mirroring" if reflected else "PartDesign::Body",
            "source_sha256": "4" * 64,
            "brep_entry": "PartShape52.brp" if reflected else "PartShape.brp",
            "brep_sha256": "5" * 64,
        },
        "coordinate_frame": "saved_BRep_storage_frame_as_read_mm; "
        "no extra XML/object/link placement applied",
        "tessellation": {
            "linear_deflection_mm": 0.1,
            "angular_deflection_rad": 0.2,
            "relative": False,
        },
        "native_to_installed_transform": None,
        "surface_equivalence_qualified": False,
    }
    row.update(
        mesh_origin=draft.NATIVE_MESH_ORIGIN,
        geometry_variant=variant,
        git_blob_sha1=None,
        native_export_binding=binding,
    )
    group["stage"] = "native_cached_mesh_audited_waiting_orientation_and_surface_review"
    return plan, asset, source, license_bytes, variant


@pytest.mark.parametrize("reflected", [False, True])
def test_native_cached_origin_and_actual_saved_variant_are_preserved(inputs, reflected):
    plan, asset, source, license_bytes, variant = native_inputs(inputs, reflected=reflected)
    payload, receipt = draft.build_draft_3mf(plan, asset, source, license_bytes, variant=variant)
    assert receipt["mesh_origin"] == draft.NATIVE_MESH_ORIGIN
    assert receipt["geometry_variant"] == variant
    assert receipt["variant_quantity_required"] == (1 if reflected else 4)
    assert "nominal_quantity_required" not in receipt
    assert "NATIVE_CACHED" in receipt["title"]
    assert receipt["exact_mesh_vertex_index_winding_roundtrip"]
    assert receipt["native_export_binding"]["source_binding"]["brep_entry"] == (
        "PartShape52.brp" if reflected else "PartShape.brp"
    )
    assert not receipt["manufacturing_release"]
    assert (
        draft.inspect_draft_3mf(payload, source, plan, asset, variant=variant)["mesh_origin"]
        == draft.NATIVE_MESH_ORIGIN
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_capture_raw_sha256", None),
        ("native_mesh_audit_canonical_sha256", "0" * 64),
        ("native_to_installed_transform", [1] * 16),
        ("surface_equivalence_qualified", True),
    ],
)
def test_native_cached_missing_or_inflated_binding_rejects(inputs, field, value):
    plan, asset, source, license_bytes, variant = native_inputs(inputs)
    plan["mesh_audit"][0]["native_export_binding"][field] = value
    with pytest.raises(ValueError):
        draft.build_draft_3mf(plan, asset, source, license_bytes, variant=variant)


def test_native_export_cannot_be_silently_relabeled_upstream(inputs):
    plan, asset, source, license_bytes, variant = native_inputs(inputs)
    plan.pop("mesh_origin")
    plan["evidence_class"] = "pinned_upstream_STL_audit_and_unreleased_draft_queue"
    plan["draft_plate_groups"][0]["stage"] = (
        "source_mesh_audited_waiting_profile_orientation_and_fidelity_review"
    )
    with pytest.raises(ValueError, match="cannot be substituted"):
        draft.build_draft_3mf(plan, asset, source, license_bytes, variant=variant)
