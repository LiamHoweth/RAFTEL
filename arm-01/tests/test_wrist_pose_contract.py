"""Pinned-source declarations and independent simple geometric witnesses."""

import copy
import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location(
    "wrist_contract", ROOT / "tools/thor_wrist_pose_contract.py"
)
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)

# Source XML extracted from seven individually authenticated pinned documents.
# This immutable fixture permits CI without downloading upstream native CAD.
PINNED_DECLARATION = {
    "schema_version": 1,
    "source_revision": "286b081fe6f056d87c379b884781ef77ff6a0159",
    "source_sha256": {
        "Art56GearPlate.fcstd": "38ca5952d4e03e4009f94628d0c435153b980ea558a608fca9ac1c9aaf79d411",
        "Art56MotorCoverRing.fcstd": (
            "8d037cf7a3e63ee8f04b39be35836d35c5d6f330497c8df5a735cd05abd071fa"
        ),
        "Art56SmallGear.fcstd": "b737ce24c58bc5ffc3763fcd6cdcfdd425747565c2850054397f066ecd5a63a0",
        "Assembly.FCStd": "5ee729246229e7494466010ab68e2c2367ba4ec1361b7701df21c0f8b00c2c1b",
        "AssemblyArt4.FCStd": "9306c0461c1a979526c8f73554ddef8fa89b8880e613b42beed7ac19feb401da",
        "AssemblyArt56.FCStd": "a04836216dcae82eb033c15daba6e41dedb85b03f86ff21e56b77cdff835a473",
        "GripperBot.FCStd": "a65e68644312adee7381e3a640b2b827f9c2c3362bbe4a842ccee9fea969d176",
    },
    "bindings": [
        {
            "document": "Assembly.FCStd",
            "object": "AssemblyArt56",
            "parent_document": "AssemblyArt4.FCStd",
            "parent_link": "AssemblyArt4",
            "parent_datum": "LCS_Art56Fix",
            "attached_to": "AssemblyArt4#LCS_Art56Fix",
            "linked_file": "AssemblyArt56.FCStd",
            "linked_object": "Model",
            "saved_expression_engine": [
                [
                    "Placement",
                    "AssemblyArt4.Placement * "
                    "AssemblyArt4#LCS_Art56Fix.Placement * "
                    "AttachmentOffset * "
                    "AssemblyArt56#LCS_Art4Fix.Placement ^ -1",
                ]
            ],
            "saved_attachment_offset": {
                "position_mm": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.7071067811865476, 0.7071067811865476],
            },
            "saved_placement": {
                "position_mm": [-3.07e-14, -1.37e-14, 556.0],
                "quaternion_xyzw": [0.0, -1e-16, 0.7071067811865475, 0.7071067811865477],
            },
            "saved_parent_datum": {
                "position_mm": [0.0, 0.0, 111.5],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
            "coordinate": "q5",
            "coefficient": 1.0,
            "increment_side": "right",
            "increment_axis": [1, 0, 0],
        },
        {
            "document": "AssemblyArt56.FCStd",
            "object": "Art56GearPlate_Art56GearPlate",
            "parent_document": "Art56MotorCoverRing.fcstd",
            "parent_link": "Art56MotorCoverRing_Art56MotorCoverRing",
            "parent_datum": "LCS_BigGear",
            "attached_to": "Art56MotorCoverRing_Art56MotorCoverRing#LCS_BigGear",
            "linked_file": "Art56GearPlate.FCStd",
            "linked_object": "Body",
            "saved_expression_engine": [
                [
                    "Placement",
                    "Art56MotorCoverRing_Art56MotorCoverRing.Placement "
                    "* Art56MotorCoverRing#LCS_BigGear.Placement * "
                    "AttachmentOffset * "
                    "Art56GearPlate#LCS_Art56GearPlate.Placement ^ "
                    "-1",
                ]
            ],
            "saved_attachment_offset": {
                "position_mm": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.2588190451025199, -0.9659258262890686, -1e-16, 1e-16],
            },
            "saved_placement": {
                "position_mm": [-1.06e-14, 1.1e-15, 21.500000000000004],
                "quaternion_xyzw": [-0.8660254037844383, 0.5000000000000009, -2e-16, 1e-16],
            },
            "saved_parent_datum": {
                "position_mm": [0.0, -19.5, 0.0],
                "quaternion_xyzw": [0.5, -0.5, 0.5, 0.5],
            },
            "coordinate": "q6",
            "coefficient": 1.0,
            "increment_side": "left",
            "increment_axis": [0, 0, 1],
        },
        {
            "document": "AssemblyArt56.FCStd",
            "object": "Art56MotorCoverRing_Art56MotorCoverRing",
            "parent_document": "AssemblyArt56.FCStd",
            "parent_link": None,
            "parent_datum": "LCS_Origin",
            "attached_to": "Parent Assembly#LCS_Origin",
            "linked_file": "Art56MotorCoverRing.FCStd",
            "linked_object": "Body",
            "saved_expression_engine": [
                [
                    "Placement",
                    "LCS_Origin.Placement * AttachmentOffset * "
                    "Art56MotorCoverRing#LCS_Art56MotorCoverRing.Placement "
                    "^ -1",
                ]
            ],
            "saved_attachment_offset": {
                "position_mm": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.7071067811865476, 0.0, -0.7071067811865475],
            },
            "saved_placement": {
                "position_mm": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [
                    0.5,
                    -0.4999999999999998,
                    0.5000000000000001,
                    -0.5000000000000002,
                ],
            },
            "saved_parent_datum": {
                "position_mm": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
            "coordinate": None,
            "coefficient": 0.0,
            "increment_side": None,
            "increment_axis": None,
        },
        {
            "document": "AssemblyArt56.FCStd",
            "object": "GripperBot_GripperBot",
            "parent_document": "Art56GearPlate.fcstd",
            "parent_link": "Art56GearPlate_Art56GearPlate",
            "parent_datum": "LCS_Gripper",
            "attached_to": "Art56GearPlate_Art56GearPlate#LCS_Gripper",
            "linked_file": "GripperBot.FCStd",
            "linked_object": "Body",
            "saved_expression_engine": [
                [
                    "Placement",
                    "Art56GearPlate_Art56GearPlate.Placement * "
                    "Art56GearPlate#LCS_Gripper.Placement * "
                    "AttachmentOffset * "
                    "GripperBot#LCS_GripperBot.Placement ^ -1",
                ]
            ],
            "saved_attachment_offset": {
                "position_mm": [0.0, 0.0, 1.0],
                "quaternion_xyzw": [0.9848077530122079, -0.1736481776669317, -0.0, -2e-16],
            },
            "saved_placement": {
                "position_mm": [0.0466674302586318, -17.14993650574115, 56.499999999999986],
                "quaternion_xyzw": [
                    0.0009620666746153,
                    -0.7071061267078044,
                    -0.7071061267078046,
                    0.0009620666746153,
                ],
            },
            "saved_parent_datum": {
                "position_mm": [9.4e-15, -1.24e-14, -42.49999999999999],
                "quaternion_xyzw": [1.0, -1e-16, 1e-16, 1e-16],
            },
            "coordinate": None,
            "coefficient": 0.0,
            "increment_side": None,
            "increment_axis": None,
        },
    ],
    "coordinate_frame": "native_CAD_world_mm_at_zero_proximal_four_joints",
    "angle_units": "radians",
    "saved_zero_axes": {
        "fold": {"origin_mm": [0, 0, 556], "axis_unit": [0, 1, 0]},
        "plate_roll": {"origin_mm": [0, 0, 575.5], "axis_unit": [0, 0, 1]},
    },
    "declaration": "imposed_AttachmentOffset_increments_existing_source_expressions",
    "q5_membership": "all_AssemblyArt56_descendants",
    "q6_membership": "plate_and_attachment_descendants_only",
    "side_shafts_driven_for_q6": False,
    "differential_or_mesh_solved": False,
    "native_corroboration_in_this_contract": False,
    "physical_calibration_qualified": False,
}


def test_exact_source_declaration_and_operation_sides():
    contract.validate_contract(PINNED_DECLARATION)
    fold, roll, ring, gripper = PINNED_DECLARATION["bindings"]
    assert (fold["object"], fold["increment_side"], fold["increment_axis"]) == (
        "AssemblyArt56",
        "right",
        [1, 0, 0],
    )
    assert (roll["object"], roll["increment_side"], roll["increment_axis"]) == (
        contract.PLATE,
        "left",
        [0, 0, 1],
    )
    assert ring["coordinate"] is None and gripper["coordinate"] is None
    assert gripper["parent_link"] == contract.PLATE
    assert PINNED_DECLARATION["native_corroboration_in_this_contract"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("angle_units", "degrees"),
        ("coordinate_frame", "ROS_base_link_m"),
        ("side_shafts_driven_for_q6", True),
        ("differential_or_mesh_solved", True),
        ("native_corroboration_in_this_contract", True),
        ("physical_calibration_qualified", True),
    ],
)
def test_reject_changed_contract_claims_and_types(field, value):
    changed = copy.deepcopy(PINNED_DECLARATION)
    changed[field] = value
    with pytest.raises(ValueError, match="exact reviewed"):
        contract.validate_contract(changed)


@pytest.mark.parametrize("mutation", ["side", "axis", "expression", "pin", "offset", "extra"])
def test_reject_offset_handedness_stale_source_and_metadata_changes(mutation):
    changed = copy.deepcopy(PINNED_DECLARATION)
    if mutation == "side":
        changed["bindings"][1]["increment_side"] = "right"
    elif mutation == "axis":
        changed["bindings"][1]["increment_axis"] = [0, 0, -1]
    elif mutation == "expression":
        changed["bindings"][1]["saved_expression_engine"][0][1] = "Placement"
    elif mutation == "pin":
        changed["source_sha256"]["AssemblyArt56.FCStd"] = "0" * 64
    elif mutation == "offset":
        changed["bindings"][0]["saved_attachment_offset"]["position_mm"][2] = 1
    else:
        changed["unexpected"] = "field"
    with pytest.raises(ValueError):
        contract.validate_contract(changed)


def test_source_contract_rejects_bytes_before_parsing(tmp_path):
    (tmp_path / next(iter(contract.PINNED))).write_bytes(b"different input")
    with pytest.raises(ValueError, match="pinned wrist input"):
        contract.source_contract(tmp_path)


def test_observed_zero_marker_stays_zero_and_fold_follows_positive_native_y():
    p = [10.0, 20.0, 600.0]
    assert contract.expected_marker(p, 0.0, 0.0) == pytest.approx(p)
    # Quarter fold about +Y: X becomes negative Z, positive Z becomes X.
    assert contract.expected_marker([10, 20, 600], math.pi / 2, 0) == pytest.approx([44, 20, 546])


def test_positive_roll_and_fold_only_membership():
    assert contract.expected_marker([10, 0, 600], 0, math.pi / 2) == pytest.approx([0, 10, 600])
    assert contract.expected_marker([10, 0, 600], 0, math.pi / 2, roll=False) == pytest.approx(
        [10, 0, 600]
    )


def test_combined_rotations_carry_roll_axis_and_use_distinct_fold_origin():
    # R_y(pi/2) R_z(pi/2) applied relative to the fold origin.
    assert contract.expected_marker([10, 20, 600], math.pi / 2, math.pi / 2) == pytest.approx(
        [44, 10, 576]
    )
    # Any point on the roll axis is invariant to q6, even after fold.
    a = contract.expected_marker([0, 0, 575.5], 0.2, 0.15)
    b = contract.expected_marker([0, 0, 575.5], 0.2, 0.0)
    assert a == pytest.approx(b, abs=1e-12)


@pytest.mark.parametrize(
    "point,q5,q6,roll",
    [
        ([1, 2], 0, 0, True),
        ([True, 0, 0], 0, 0, True),
        ([1, 2, float("nan")], 0, 0, True),
        ([1, 2, 3], True, 0, True),
        ([1, 2, 3], 0, float("inf"), True),
        ([1, 2, 3], 0, 0, 1),
    ],
)
def test_invalid_marker_inputs_fail_closed(point, q5, q6, roll):
    with pytest.raises(ValueError):
        contract.expected_marker(point, q5, q6, roll=roll)
