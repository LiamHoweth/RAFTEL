"""Pinned source expression regression, separate from continuous Thor algebra."""

import json
import math
from pathlib import Path

import pytest

from raftel_arm01.control.thor_source_conversion import (
    ROS_REVISION,
    ROS_SOURCE_SHA256,
    read_fly_report,
    read_grbl_report,
    source_angles,
    source_write,
)
from raftel_arm01.kinematics.thor_drive import joints_to_drive

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/thor-controller-conversion.json").read_text()
)


def test_pinned_reference_is_host_cpp_not_ros_or_physical_test():
    assert FIXTURE["source_revision"] == ROS_REVISION
    assert FIXTURE["source_sha256"] == ROS_SOURCE_SHA256
    assert FIXTURE["evidence_class"] == "host_cpp_expression_fixture_not_ros_runtime_or_hardware"


@pytest.mark.parametrize("case", FIXTURE["cases"])
def test_cpp_generated_boundary_expression_fixtures(case):
    assert source_angles(case["joints_rad"]) == tuple(case["angles_deg"])


def test_offset_before_cast_is_not_simplified_continuous_map():
    joints = (-math.pi / 1800,) * 7  # -0.1 degree
    assert source_angles(joints) == (-1, 1, 1, 0, 0, 0, 179)
    assert math.degrees(joints_to_drive(joints[:6])[0]) == pytest.approx(-0.1)
    # Wrist source truncates each joint first: int(-.9)+2*int(.9)=0,
    # whereas int(-.9+2*.9) would be zero but the opposite shaft would be 2.
    wrist = (0, 0, 0, 0, math.radians(0.9), math.radians(0.9), 0)
    assert source_angles(wrist)[4:6] == (0, 0)
    assert tuple(math.degrees(v) for v in joints_to_drive(wrist[:6])[5:]) == pytest.approx(
        (0.9, 2.7)
    )


def test_initial_zero_write_only_gripper_and_then_suppresses():
    first = source_write((0,) * 7, board="thor_pcb")
    assert first.diagnostic_lines == ("M3 S255\r\n",)
    assert (
        source_write(
            (0,) * 7, board="thor_pcb", previous_angles_deg=first.angles_deg
        ).diagnostic_lines
        == ()
    )
    assert first.evidence_class == "offline_source_conversion_not_physical_state"


def test_source_board_axis_order_and_gripper_integer_division():
    joints = FIXTURE["cases"][7]["joints_rad"]
    pcb = source_write(joints, board="thor_pcb")
    fly = source_write(joints, board="fly")
    assert pcb.diagnostic_lines == ("G0 A12 B34 C34 D-44 X-55 Y0 Z0\r\n", "M3 S222\r\n")
    assert fly.diagnostic_lines == ("G0 X12 Y34 Z-44 U-55 V0 W0\r\n", "M280 P0 S157\r\n")
    assert "G90" not in "".join(pcb.diagnostic_lines)


def test_gripper_only_change_preserves_arm_suppression():
    prior = source_write((0,) * 7, board="fly").angles_deg
    changed = source_write((0, 0, 0, 0, 0, 0, 0.1), board="fly", previous_angles_deg=prior)
    assert changed.diagnostic_lines == ("M280 P0 S185\r\n",)


def test_complete_grbl_readback_uses_c_and_reports_b_c_disagreement():
    readback = read_grbl_report(
        "<Idle,MPos:10,20,30,40,50,60,80,WPos:10,20,30,40,50,60,80>",
        commanded_gripper_deg=150,
    )
    assert tuple(math.degrees(v) for v in readback.joints_rad) == pytest.approx(
        (10, -30, -40, 50, 10, 35, -30)
    )
    assert readback.duplicate_shoulder_agrees is False
    assert readback.gripper_state_origin == "last_command_not_sensor"


def test_complete_fly_branch_has_no_duplicate_shoulder_and_overwrites_pos_gripper():
    readback = read_fly_report(
        '{"status":"I","pos":[10,30,40,50,60,80,999],"homed":[0,0,0]}',
        commanded_gripper_deg=150,
    )
    assert tuple(math.degrees(v) for v in readback.joints_rad) == pytest.approx(
        (10, -30, -40, 50, 10, 35, -30)
    )
    assert readback.duplicate_shoulder_agrees is None
    assert readback.reported_channels_deg[-1] == 999


@pytest.mark.parametrize(
    "report",
    [
        "<Idle,MPos:1,2,3,WPos:1,2,3>",
        "<Idle,MPos:1,2,3,4,5,6,7>",
        "<Idle,MPos:1,2,3,4,5,6,nan,WPos:0>",
        "<Idle,MPos:1,2,3,4,5,6,x,WPos:0>",
    ],
)
def test_grbl_partial_or_malformed_reports_fail_atomically(report):
    with pytest.raises(ValueError):
        read_grbl_report(report, commanded_gripper_deg=180)


@pytest.mark.parametrize(
    "report",
    [
        '{"pos":[1,2,3,4,5,6],"status":"I"}',
        '{"status":"I","pos":[1,2,3]}',
        '{"status":"I","pos":[1,2,3,4,5,true]}',
        '{"status":"I","pos":[1,2,3,4,5,NaN]}',
        '{"status":',
    ],
)
def test_fly_strict_source_prefix_complete_finite_input(report):
    with pytest.raises(ValueError):
        read_fly_report(report, commanded_gripper_deg=180)


@pytest.mark.parametrize("bad", [math.nan, math.inf, True, "1", None, 1e308])
def test_undefined_source_inputs_rejected(bad):
    with pytest.raises(ValueError):
        source_angles((bad, 0, 0, 0, 0, 0, 0))


def test_source_api_rejects_unsupported_board_prior_state_and_wrong_shape():
    with pytest.raises(ValueError, match="board"):
        source_write((0,) * 7, board="unknown")
    with pytest.raises(ValueError, match="integers"):
        source_write((0,) * 7, board="fly", previous_angles_deg=(0.0,) * 7)
    with pytest.raises(ValueError, match="seven|7"):
        source_angles((0,) * 6)
    with pytest.raises(ValueError, match="32-bit"):
        source_write((0,) * 7, board="fly", previous_angles_deg=(2**32,) * 7)


@pytest.mark.parametrize("bad", [True, 180.0, -(2**31) - 1, 2**31])
def test_readback_requires_defined_int32_command_state(bad):
    with pytest.raises(ValueError):
        read_fly_report('{"status":"I","pos":[0,0,0,0,0,0]}', commanded_gripper_deg=bad)
