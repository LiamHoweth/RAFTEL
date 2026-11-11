"""Independent quantity, source/volume and drawing-coordinate acceptance checks."""

import copy
import importlib.util
import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fabrication = load_tool("thor_fabrication_assets")
loads = load_tool("thor_load_analysis")


@pytest.fixture
def inputs():
    inventory, interfaces, inspection = fabrication.load_manifest_inputs()
    return inventory, interfaces, inspection, loads.build_thor_snapshot(inventory)


def test_manifest_exactly_reconciles_existing_printed_assignments(inputs):
    result = fabrication.build_asset_manifest(*inputs)
    assert result["counts"] == {
        "installed_printed_leaves": 65,
        "unique_source_assets": 46,
        "export_geometry_variants": 47,
        "reflected_installed_leaves": 1,
    }
    assets = result["assets"]
    printed = [
        row
        for group in inputs[3]["bodies"]
        for row in group["mass_assignments"]
        if row["category"].startswith("printed_")
    ]
    assert {i["instance_id"] for a in assets for i in a["instances"]} == {
        row["instance_path"] for row in printed
    }
    assert sum(a["quantity"] for a in assets) == 65
    assert result["installed_printed_volume_mm3"] == pytest.approx(
        math.fsum(row["volume_mm3"] for row in printed), rel=1e-14
    )
    assert result["mass_overlay"]["printed_mass_kg"] == pytest.approx(
        math.fsum(row["mass_kg"] for row in printed), rel=1e-14
    )
    assert result["mass_overlay"]["slicer_infill_setting"] is None
    assert not any(result["qualification"].values())


def test_reflected_finger_is_a_distinct_export_variant_of_one_source_asset(inputs):
    result = fabrication.build_asset_manifest(*inputs)
    finger = next(a for a in result["assets"] if a["asset_id"] == "GripperFinger::Body")
    assert finger["quantity"] == 2
    assert {row["variant_id"] for row in finger["export_variants"]} == {"nominal", "reflected"}
    reflected = next(row for row in finger["instances"] if row["variant_id"] == "reflected")
    assert reflected["linked_object"] == fabrication.MIRRORED_REFERENCE
    assert reflected["source_to_installation_transform"] is None
    assert all(row["export_sha256"] is None for row in finger["export_variants"])


def test_manifest_keeps_art1_static_and_unrepaired_history_separate(inputs):
    result = fabrication.build_asset_manifest(*inputs)
    art1 = next(a for a in result["assets"] if a["asset_id"] == "Art1Body::Body")
    assert "unrepaired_original_history" in art1["history_status"]
    assert "validated_static_snapshot_separate" in art1["history_status"]
    assert "CC-BY-SA-4.0" == result["attribution"]["declared_repository_license"]
    assert all(
        a["orientation_and_inspection"]["actual_orientation_or_supports"] is None
        for a in result["assets"]
    )


@pytest.mark.parametrize(
    "bad",
    [
        "revision",
        "missing",
        "duplicate_leaf",
        "duplicate_mass",
        "hash",
        "volume",
        "envelope",
        "source_duplicate",
    ],
)
def test_changed_or_incomplete_source_evidence_fails(inputs, bad):
    inventory, interfaces, inspection, snapshot = copy.deepcopy(inputs)
    if bad == "revision":
        inspection["revision"] = "0" * 40
    elif bad == "missing":
        snapshot["bodies"][0]["mass_assignments"] = [
            row
            for row in snapshot["bodies"][0]["mass_assignments"]
            if row["category"].startswith("manufacturer_")
        ]
    elif bad == "duplicate_leaf":
        inventory["mounted_bodies"].append(inventory["mounted_bodies"][0])
    elif bad == "duplicate_mass":
        snapshot["bodies"][0]["mass_assignments"].append(
            snapshot["bodies"][0]["mass_assignments"][0]
        )
    elif bad == "hash":
        interfaces["printed_part_envelopes"]["source_shapes"][0]["source_sha256"] = "0" * 64
    elif bad == "volume":
        inventory["mounted_bodies"][0]["volume_mm3"] += 1
    elif bad == "envelope":
        interfaces["printed_part_envelopes"]["source_shapes"][0]["envelope_xyz_mm"][0] += 1
    else:
        interfaces["printed_part_envelopes"]["source_shapes"].append(
            interfaces["printed_part_envelopes"]["source_shapes"][0]
        )
    with pytest.raises(ValueError):
        fabrication.build_asset_manifest(inventory, interfaces, inspection, snapshot)


def test_tracked_manifest_and_drawing_reproduce_exactly(inputs):
    manifest = fabrication.build_asset_manifest(*inputs)
    tracked = ROOT / "hardware/cad/thor-printable-assets-v1.json"
    assert json.loads(tracked.read_text()) == manifest
    assert (ROOT / "hardware/drawings/thor-base-interface-v1.svg").read_text(encoding="utf-8") == (
        fabrication.base_interface_svg(inputs[1])
    )
    fabrication.validate_manifest_inputs(manifest)
    manifest["input_canonical_sha256"]["inventory"] = "0" * 64
    with pytest.raises(ValueError, match="stale"):
        fabrication.validate_manifest_inputs(manifest)


def test_svg_overlay_preserves_asymmetric_source_coordinates_and_transform(inputs):
    xml = ET.fromstring(fabrication.base_interface_svg(inputs[1]))
    namespace = {"s": "http://www.w3.org/2000/svg"}
    circles = [row for row in xml.findall(".//s:circle", namespace) if row.get("id")]
    assert len(circles) == 4
    for circle, (x, y) in zip(
        circles,
        [(0, 86), (86 * math.cos(math.pi / 6), 43), (0, -86), (86 * math.cos(math.pi / 6), -43)],
        strict=True,
    ):
        assert float(circle.get("cx")) == pytest.approx(x)
        assert float(circle.get("cy")) == pytest.approx(-y)
        assert float(circle.get("r")) == 3
        assert math.hypot(x, y) == pytest.approx(86)
    metadata = json.loads(xml.find("s:metadata", namespace).text)
    assert metadata["source_object"] == "BaseBot::Body002"
    assert metadata["proposed_blank_dimensions_mm"] == [300, 320]
    assert metadata["datum_LCS_Bot_matrix_row_major"] == [
        1,
        0,
        0,
        0,
        0,
        1,
        0,
        0,
        0,
        0,
        1,
        0,
        0,
        0,
        0,
        1,
    ]
    assert metadata["actual_bench_extrinsics_or_plate_thickness"] is None


def test_svg_rejects_summary_that_disagrees_with_cylindrical_face(inputs):
    interfaces = copy.deepcopy(inputs[1])
    interfaces["base_mount_summary"]["hole_centers_xy_mm"][0][0] += 2
    with pytest.raises(ValueError, match="disagrees"):
        fabrication.base_interface_svg(interfaces)


def test_svg_visible_dimensions_follow_proposal_and_capture_changes(inputs):
    interfaces = copy.deepcopy(inputs[1])
    interfaces["proposed_adapter"]["candidate_outer_bounds_mm"]["x_max"] += 20
    interfaces["proposed_adapter"]["candidate_outer_bounds_mm"]["y_max"] += 10
    xml = ET.fromstring(fabrication.base_interface_svg(interfaces))
    texts = " ".join(xml.itertext())
    assert "320 × 330 blank" in texts
    assert "300 × 320 blank" not in texts


def test_saved_tool_mating_composition_matches_independent_point_chain(inputs):
    from raftel_arm01.kinematics.thor_frames import transform_point

    extract = load_tool("extract_thor_geometry")
    interfaces = inputs[1]
    result = fabrication.saved_tool_mating_frames(interfaces)
    plate = next(
        row["placement_matrix"]
        for row in interfaces["tool_plate_interface"]["datums"]
        if row["name"] == "LCS_Gripper"
    )
    gripper = next(
        row["placement_matrix"]
        for row in interfaces["gripper_socket_interface"]["datums"]
        if row["name"] == "LCS_GripperBot"
    )
    offset = interfaces["tool_interface_summary"]["saved_gripper_attachment"]["AttachmentOffset"]
    frame = {
        "position_m": [float(offset[f"P{axis}"]) / 1000 for axis in "xyz"],
        "quaternion_xyzw": [float(offset[f"Q{axis}"]) for axis in range(4)],
    }
    points = [(0, 0, 0), (0.02, -0.01, 0.04), (0, 0, 0.01715), (0, 0.0085, 0.01715)]
    for point in points:
        # Independent point-wise inverse gripper datum, existing saved-quaternion
        # evaluator, then direct source plate datum. No compose/inverse helpers.
        relative = [point[i] - gripper[4 * i + 3] / 1000 for i in range(3)]
        in_mate = [sum(gripper[4 * j + i] * relative[j] for j in range(3)) for i in range(3)]
        in_offset = extract.transform_point(frame, in_mate)
        expected = [
            sum(plate[4 * i + j] * in_offset[j] for j in range(3)) + plate[4 * i + 3] / 1000
            for i in range(3)
        ]
        actual = transform_point(result["plate_source_from_gripper_source"], point)
        assert actual == pytest.approx(expected, abs=1e-14)
    # Saved socket center and axis line map to the male axis; this does not
    # establish fit or axial retention. Saved mating origin includes the offset.
    composed = result["plate_source_from_gripper_source"]
    assert transform_point(composed, (0, 0, 0.01715)) == pytest.approx((0, 0, -0.035), abs=1e-14)
    assert transform_point(composed, (0, 0.0085, 0.01715)) == pytest.approx(
        (0, 0, -0.0435), abs=1e-14
    )
    assert result["physical_TCP"] is None


def test_tool_drawing_reproduces_source_dimensions_and_frame_metadata(inputs):
    svg = fabrication.tool_interface_svg(inputs[1])
    xml = ET.fromstring(svg)
    ns = {"s": "http://www.w3.org/2000/svg"}
    by_id = {row.get("id"): row for row in xml.iter() if row.get("id")}
    assert float(by_id["male-diameter"].get("r")) == 15
    assert float(by_id["socket-diameter-comparison"].get("r")) == 15.5
    assert float(by_id["male-axial-envelope"].get("x")) == -42.5
    assert float(by_id["male-axial-envelope"].get("width")) == 37.5
    metadata = json.loads(xml.find("s:metadata", ns).text)
    assert metadata["radial_hole_source_z_mm"] == -38
    assert metadata["saved_mating_frames"]["physical_TCP"] is None
    assert (ROOT / "hardware/drawings/thor-tool-interface-v1.svg").read_text(
        encoding="utf-8"
    ) == svg


@pytest.mark.parametrize("bad", ["quaternion", "expression", "datum", "hole_plane", "diameter"])
def test_tool_drawing_rejects_changed_or_inconsistent_mating_evidence(inputs, bad):
    interfaces = copy.deepcopy(inputs[1])
    if bad == "quaternion":
        interfaces["tool_interface_summary"]["saved_gripper_attachment"]["AttachmentOffset"][
            "Q0"
        ] = "2"
    elif bad == "expression":
        interfaces["tool_interface_summary"]["saved_gripper_attachment"]["placement_expression"][
            "expression"
        ] = "AttachmentOffset"
    elif bad == "datum":
        interfaces["tool_plate_interface"]["datums"] = []
    elif bad == "hole_plane":
        interfaces["tool_interface_summary"]["plate_radial_hole_axial_plane_source_z_mm"] = -37
    else:
        interfaces["tool_interface_summary"]["plate_male_diameter_mm"] = 32
    with pytest.raises(ValueError):
        fabrication.tool_interface_svg(interfaces)


def test_installed_tool_generates_manifest_and_negative_record_import(tmp_path):
    output = tmp_path / "manifest.json"
    command = [sys.executable, str(ROOT / "tools/thor_fabrication_assets.py")]
    run = subprocess.run(command + ["--output", str(output)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert b"\r\n" not in output.read_bytes()
    assert json.loads(output.read_text())["counts"]["installed_printed_leaves"] == 65
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    run = subprocess.run(
        command + ["--validate-records", str(bad), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "schema" in run.stderr


def test_cli_preflights_all_outputs_before_creating_or_truncating_any(tmp_path):
    command = [sys.executable, str(ROOT / "tools/thor_fabrication_assets.py")]
    output, existing = tmp_path / "new.json", tmp_path / "historical.svg"
    existing.write_bytes(b"preserved historical bytes\n")
    run = subprocess.run(
        command + ["--output", str(output), "--svg", str(existing)], capture_output=True, text=True
    )
    assert run.returncode != 0 and "already exists" in run.stderr
    assert not output.exists()
    assert existing.read_bytes() == b"preserved historical bytes\n"
    alias = output.parent / "." / output.name
    run = subprocess.run(
        command + ["--output", str(output), "--svg", str(alias)], capture_output=True, text=True
    )
    assert run.returncode != 0 and "distinct" in run.stderr
    assert not output.exists()


def test_record_validation_cannot_replace_its_input(tmp_path):
    command = [sys.executable, str(ROOT / "tools/thor_fabrication_assets.py")]
    original_manifest = (ROOT / "hardware/cad/thor-printable-assets-v1.json").read_bytes()
    original_template = (ROOT / "hardware/measurements/thor-fabrication-template.json").read_bytes()
    manifest, template = tmp_path / "manifest.json", tmp_path / "template.json"
    manifest.write_bytes(original_manifest)
    template.write_bytes(original_template)
    run = subprocess.run(
        command
        + [
            "--validate-records",
            str(template),
            "--manifest",
            str(manifest),
            "--output",
            str(template),
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "cannot replace an input" in run.stderr
    assert template.read_bytes() == original_template
    assert manifest.read_bytes() == original_manifest


def test_shared_exclusive_writer_handles_lf_unicode_and_creation_race(tmp_path, monkeypatch):
    from raftel_arm01.engineering.evidence_files import write_new_evidence

    output = tmp_path / "new.txt"
    write_new_evidence([(output, "µ\nsource\n")])
    assert output.read_bytes() == "µ\nsource\n".encode()
    with pytest.raises(ValueError, match="already exists"):
        write_new_evidence([(output, "replacement")])
    # Emulate an entry appearing after the exists preflight. Exclusive open
    # remains the authoritative guard and preserves the old bytes.
    monkeypatch.setattr(Path, "exists", lambda self: False)
    with pytest.raises(FileExistsError):
        write_new_evidence([(output, "replacement")])
    assert output.read_bytes() == "µ\nsource\n".encode()
