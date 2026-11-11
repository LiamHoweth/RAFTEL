"""Check source metadata math and strict expression handling without CAD/network."""

import json
import math
import runpy
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

TOOLS = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "extract_thor_geometry.py"))


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("0.160", 0.160),
        ("${PI / 2}", math.pi / 2),
        ("-${PI / 2}", -math.pi / 2),
        ("-2.967", -2.967),
        ("1 + 2 * 3", 7),
    ],
)
def test_only_explicit_numeric_arithmetic(expression, expected):
    assert TOOLS["number"](expression, math.pi) == pytest.approx(expected)


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('whoami')",
        "PI.__class__",
        "2**100",
        "1/0",
        "nan",
        "True",
    ],
)
def test_unsafe_or_unsupported_expressions_rejected(expression):
    with pytest.raises(ValueError):
        TOOLS["number"](expression, math.pi)


def test_quaternion_transform_matches_independent_half_turn():
    frame = {
        "position_m": [0, -0.068, 0.202],
        "quaternion_xyzw": [0, math.sqrt(0.5), math.sqrt(0.5), 0],
    }
    point = TOOLS["transform_point"](frame, [0, 0.160, 0.068])
    assert point == pytest.approx((0, 0, 0.362), abs=1e-12)


def native_object(name, position=(0, 0, 0), quaternion=(0, 0, 0, 1)):
    obj = ET.Element("Object", name=name)
    properties = ET.SubElement(obj, "Properties")
    prop = ET.SubElement(properties, "Property", name="Placement")
    attrs = dict(
        zip(
            ("Px", "Py", "Pz", "Q0", "Q1", "Q2", "Q3"),
            map(str, (*position, *quaternion)),
            strict=True,
        )
    )
    ET.SubElement(prop, "PropertyPlacement", **attrs)
    return obj


def save_native(directory, name, objects):
    root = ET.Element("Document")
    data = ET.SubElement(root, "ObjectData")
    data.extend(objects)
    with zipfile.ZipFile(directory / f"{name}.FCStd", "w") as archive:
        archive.writestr("Document.xml", ET.tostring(root))


def test_selected_assembly_members_not_all_prototypes(tmp_path):
    model = native_object("Model")
    group = ET.SubElement(model.find("Properties"), "Property", name="Group")
    links = ET.SubElement(group, "LinkList")
    objects = [model, native_object("UninstalledPrototype", (900, 900, 900))]
    for name, selected in TOOLS["SELECTED_LCS"].items():
        ET.SubElement(links, "Link", value=name)
        objects.append(native_object(name))
        save_native(tmp_path, name, [native_object(label) for label in selected])
    save_native(tmp_path, "Assembly", objects)
    result = TOOLS["extract"](tmp_path)
    assert len(result["installed_master_subassemblies"]) == 6
    assert not any(
        i["name"] == "UninstalledPrototype" for i in result["installed_master_subassemblies"]
    )
    assert not result["cad_axis_directions_calibrated"]
    assert not result["mass_or_load_properties_extracted"]
    assert not result["selected_files_match_pinned_inventory"]
    assert result["upstream_nominal_model"] is None
    json.dumps(result, allow_nan=False)


def test_nonunit_placement_quaternion_rejected():
    with pytest.raises(ValueError, match="unit"):
        TOOLS["placement"](native_object("bad", quaternion=(0, 0, 0, 2)))


def test_nonfinite_position_rejected():
    with pytest.raises(ValueError, match="nonfinite"):
        TOOLS["placement"](native_object("bad", position=(0, float("nan"), 0)))


def test_native_instancing_preserves_reused_parts_and_excludes_body_history():
    identity = [[float(i == j) for j in range(4)] for i in range(4)]

    def matrix(x, y, z):
        m = [row[:] for row in identity]
        for i, value in enumerate((x, y, z)):
            m[i][3] = value
        return {"matrix": m}

    objects = [
        {"name": "Model", "type": "App::Part", "group_members": ["Assembly::AssemblyArt1"]},
        {
            "name": "AssemblyArt1",
            "type": "App::Link",
            "link_transform": False,
            "link_placement": matrix(0, 0, 79),
            "linked_object_direct": "Parts::Model",
        },
    ]
    parts = [
        {"name": "Model", "type": "App::Part", "group_members": ["Parts::Motor1", "Parts::Motor2"]},
        {
            "name": "Motor1",
            "type": "App::Link",
            "link_transform": False,
            "link_placement": matrix(10, 0, 0),
            "linked_object_direct": "Parts::Prototype",
        },
        {
            "name": "Motor2",
            "type": "App::Link",
            "link_transform": False,
            "link_placement": matrix(-10, 0, 0),
            "linked_object_direct": "Parts::Prototype",
        },
        {"name": "Prototype", "type": "App::Part", "group_members": ["Parts::Body"]},
        {
            "name": "Body",
            "type": "PartDesign::Body",
            "group_members": ["Parts::History"],
            "volume_mm3": 8,
            "solid_count": 1,
            "shape_center_of_mass_mm": [1, 1, 1],
        },
        {
            "name": "History",
            "type": "PartDesign::Feature",
            "volume_mm3": 999,
            "solid_count": 1,
            "shape_center_of_mass_mm": [999, 999, 999],
        },
    ]
    report = {
        "restore_completed": True,
        "master_document": "Assembly",
        "status": "completed",
        "documents": [
            {"name": "Assembly", "objects": objects},
            {"name": "Parts", "objects": parts},
        ],
    }
    result = TOOLS["installed_leaf_instances"](report)
    assert result["instance_count"] == 2
    assert [i["zero_world_com_m"] for i in result["mounted_bodies"]] == [
        [0.011, 0.001, 0.080],
        [-0.009, 0.001, 0.080],
    ]
    assert sum(i["volume_mm3"] for i in result["mounted_bodies"]) == 16
    assert not result["missing_object_records"] and not result["errors"]


def test_native_partial_restore_rejected_and_missing_geometry_reported():
    with pytest.raises(ValueError, match="completed"):
        TOOLS["installed_leaf_instances"]({"restore_completed": False})
    report = {
        "restore_completed": True,
        "master_document": "Assembly",
        "documents": [
            {
                "name": "Assembly",
                "objects": [
                    {
                        "name": "Model",
                        "type": "App::Part",
                        "group_members": ["Assembly::Missing", "Assembly::Part"],
                    },
                    {"name": "Part", "type": "Part::Feature", "shape_error": "bad geometry"},
                ],
            }
        ],
    }
    result = TOOLS["installed_leaf_instances"](report)
    assert result["missing_object_records"] == ["Assembly::Missing"]
    assert result["errors"][0]["reason"] == "bad geometry"


def terminal_report(*leaves):
    return {
        "restore_completed": True,
        "master_document": "Assembly",
        "documents": [
            {
                "name": "Assembly",
                "objects": [
                    {
                        "name": "Model",
                        "type": "App::Part",
                        "group_members": [f"Assembly::{leaf['name']}" for leaf in leaves],
                    },
                    *leaves,
                ],
            }
        ],
    }


def test_directly_installed_partdesign_pad_missing_inventory_fails_closed():
    # A terminal Pad in an App::Part is physical even without a Body wrapper.
    report = terminal_report(
        {"name": "Belt", "type": "PartDesign::Pad"},
        {"name": "LCS_Belt", "type": "PartDesign::CoordinateSystem"},
        {"name": "HoleAxis", "type": "PartDesign::Line"},
        {"name": "Sketch", "type": "Sketcher::SketchObject"},
    )
    result = TOOLS["installed_leaf_instances"](report)
    assert result["instance_count"] == 0
    assert result["errors"] == [
        {
            "reference": "Assembly::Belt",
            "instance_path": "Assembly::Model/Assembly::Belt",
            "reason": "physical leaf lacks native shape inventory",
        }
    ]
    assert result["terminal_type_counts"]["PartDesign::Pad"] == 1
    assert result["nonphysical_terminal_type_counts"] == {
        "PartDesign::CoordinateSystem": 1,
        "PartDesign::Line": 1,
        "Sketcher::SketchObject": 1,
    }


def test_directly_installed_pad_is_retained_without_traversing_its_sketch():
    result = TOOLS["installed_leaf_instances"](
        terminal_report(
            {
                "name": "Belt",
                "type": "PartDesign::Pad",
                "out_list": ["Assembly::Sketch"],
                "volume_mm3": 2,
                "solid_count": 1,
                "shape_center_of_mass_mm": [1, 2, 3],
                "shape_valid": True,
            }
        )
    )
    assert result["instance_count"] == 1
    assert result["mounted_bodies"][0]["zero_world_com_m"] == [0.001, 0.002, 0.003]
    assert not result["errors"] and not result["missing_object_records"]


def test_unknown_terminal_and_nonvariables_python_object_are_not_silently_dropped():
    result = TOOLS["installed_leaf_instances"](
        terminal_report(
            {"name": "Variables", "type": "App::FeaturePython"},
            {"name": "CustomGeometry", "type": "App::FeaturePython"},
            {"name": "NewType", "type": "Custom::PotentialSolid"},
        )
    )
    assert {row["reference"] for row in result["errors"]} == {
        "Assembly::CustomGeometry",
        "Assembly::NewType",
    }
    assert result["nonphysical_terminal_type_counts"] == {"App::FeaturePython": 1}


def test_v2_inventory_preserves_prior_geometry_and_adds_both_native_belt_instances():
    import hashlib

    directory = Path(__file__).parents[1] / "hardware" / "cad"
    historical_path = directory / "thor-mounted-geometry.json"
    historical = json.loads(historical_path.read_text())
    corrected = json.loads((directory / "thor-mounted-geometry-v2.json").read_text())
    assert corrected["mounted_bodies"][:516] == historical["mounted_bodies"]
    assert corrected["instance_count"] == len(corrected["mounted_bodies"]) == 518
    assert len({row["instance_id"] for row in corrected["mounted_bodies"]}) == 518
    assert not corrected["errors"] and not corrected["missing_object_records"]
    added = corrected["mounted_bodies"][516:]
    assert {row["instance_id"] for row in added} == {
        "Assembly::Model/Assembly::AssemblyArt4/AssemblyArt4::Belt_GT2_208mm/AssemblyArt4::Pad046",
        "Assembly::Model/Assembly::AssemblyArt4/AssemblyArt4::Belt_GT2_208mm001/AssemblyArt4::Pad046",
    }
    native_path = directory / "thor-wrist-belt-native-validation.json"
    native = json.loads(native_path.read_text())
    assert native["status"] == "complete" and native["restore_completed"]
    assert native["audit_mode"] == "none" and not native["saved_source_changes"]
    shape = native["documents"][0]["objects"][0]
    assert shape["shape_valid"] and not shape["shape_null"] and shape["solid_count"] == 1
    for belt in added:
        assert belt["object_type"] == "PartDesign::Pad"
        assert belt["volume_mm3"] == shape["volume_mm3"]
        assert belt["solid_count"] == shape["solid_count"]
        assert belt["shape_valid"] and belt["native_state"] == ["Touched"]
    provenance = corrected["completeness_correction"]
    assert (
        provenance["historical_inventory_sha256"]
        == hashlib.sha256(historical_path.read_bytes()).hexdigest()
    )
    assert (
        provenance["new_shape_validation_report_sha256"]
        == hashlib.sha256(native_path.read_bytes()).hexdigest()
    )


def test_source_leaf_fallback_removes_or_retains_source_placement():
    def frame(x, y, z):
        return {"matrix": [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]}

    target = {
        "placement": frame(10, 0, 0),
        "volume_mm3": 8,
        "solid_count": 1,
        "shape_center_of_mass_mm": [11, 1, 1],
    }
    link = {
        "link_placement": frame(0, 20, 0),
        "link_transform": False,
        "shape_error": "no generic centroid property",
    }
    derived = TOOLS["_derived_link_geometry"](link, target)
    assert derived["shape_center_of_mass_mm"] == pytest.approx([1, 21, 1])
    assert derived["volume_mm3"] == 8 and "shape_error" not in derived
    link["link_transform"] = True
    assert TOOLS["_derived_link_geometry"](link, target)[
        "shape_center_of_mass_mm"
    ] == pytest.approx([11, 21, 1])


def test_editor_group_alias_does_not_duplicate_a_physical_leaf():
    report = {
        "restore_completed": True,
        "master_document": "Assembly",
        "documents": [
            {
                "name": "Assembly",
                "objects": [
                    {
                        "name": "Model",
                        "type": "App::Part",
                        "group_members": ["Assembly::Leaf", "Assembly::EditorGroup"],
                    },
                    {
                        "name": "EditorGroup",
                        "type": "App::DocumentObjectGroup",
                        "group_members": ["Assembly::Leaf"],
                    },
                    {
                        "name": "Leaf",
                        "type": "Part::Feature",
                        "volume_mm3": 8,
                        "solid_count": 1,
                        "shape_center_of_mass_mm": [1, 1, 1],
                    },
                ],
            }
        ],
    }
    result = TOOLS["installed_leaf_instances"](report)
    assert result["instance_count"] == 1


def test_hidden_mirror_and_array_sources_are_not_additional_installed_parts():
    report = {
        "restore_completed": True,
        "master_document": "Assembly",
        "documents": [
            {
                "name": "Assembly",
                "objects": [
                    {
                        "name": "Model",
                        "type": "App::Part",
                        "group_members": [
                            "Assembly::Source",
                            "Assembly::Mirror",
                            "Assembly::Sphere",
                            "Assembly::Array",
                        ],
                    },
                    {
                        "name": "Source",
                        "type": "Part::Feature",
                        "visibility": False,
                        "volume_mm3": 8,
                        "solid_count": 1,
                        "shape_center_of_mass_mm": [1, 1, 1],
                    },
                    {
                        "name": "Mirror",
                        "type": "Part::Mirroring",
                        "visibility": True,
                        "out_list": ["Assembly::Source"],
                        "volume_mm3": 8,
                        "solid_count": 1,
                        "shape_center_of_mass_mm": [-1, 1, 1],
                    },
                    {
                        "name": "Sphere",
                        "type": "Part::Sphere",
                        "visibility": False,
                        "volume_mm3": 1,
                        "solid_count": 1,
                        "shape_center_of_mass_mm": [10, 0, 0],
                    },
                    {
                        "name": "Array",
                        "type": "Part::FeaturePython",
                        "visibility": True,
                        "out_list": ["Assembly::Sphere"],
                        "volume_mm3": 10,
                        "solid_count": 10,
                        "shape_center_of_mass_mm": [0, 0, 0],
                    },
                ],
            }
        ],
    }
    result = TOOLS["installed_leaf_instances"](report)
    assert result["instance_count"] == 2
    assert sum(i["volume_mm3"] for i in result["mounted_bodies"]) == 18
    assert {i["source"] for i in result["excluded_construction_sources"]} == {
        "Assembly::Source",
        "Assembly::Sphere",
    }


def test_native_report_merge_checks_identity_and_preserves_unfiltered_metadata():
    base = {
        "assembly_filename": "Assembly.FCStd",
        "master_document": "Assembly",
        "freecad_version": ["1", "1", "4"],
        "restore_completed": True,
        "documents": [
            {
                "name": "Assembly",
                "objects": [
                    {"name": "Model", "type": "App::Part"},
                    {"name": "Leaf", "type": "Part::Feature"},
                ],
            }
        ],
    }
    shapes = {
        "assembly_filename": "Assembly.FCStd",
        "master_document": "Assembly",
        "freecad_version": ["1", "1", "4"],
        "restore_completed": True,
        "status": "complete",
        "documents": [
            {
                "name": "Assembly",
                "objects": [{"name": "Leaf", "type": "Part::Feature", "volume_mm3": 8}],
            }
        ],
    }
    result = TOOLS["merge_native_reports"](base, shapes)
    assert result["documents"][0]["objects"][0]["name"] == "Model"
    assert result["documents"][0]["objects"][1]["volume_mm3"] == 8
    assert "volume_mm3" not in base["documents"][0]["objects"][1]
    shapes["master_document"] = "Other"
    with pytest.raises(ValueError, match="mismatch"):
        TOOLS["merge_native_reports"](base, shapes)


def test_axis_probe_refuses_cad_overwrite_before_importing_runtime(tmp_path, monkeypatch):
    probe = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "probe_thor_axes_freecad.py"))
    source = tmp_path / "Assembly.FCStd"
    source.write_bytes(b"protected source")
    monkeypatch.setenv("RAFTEL_THOR_AXIS_SOURCE", str(source))
    monkeypatch.setenv("RAFTEL_THOR_AXIS_REPORT", str(source))
    with pytest.raises(ValueError, match="new JSON"):
        probe["main"]()
    assert source.read_bytes() == b"protected source"
