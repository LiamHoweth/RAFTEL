"""Check upstream-model kinematics without implying CAD or physical calibration."""

import math

import pytest

from raftel_arm01.kinematics.thor_model import (
    JOINT_LOCAL_AXES,
    VALIDATION_CLASS,
    chain,
    forward_kinematics,
)


def test_zero_pose_source_joint_origins_and_axes():
    frames, end = chain((0,) * 6)
    assert [f.origin_m[2] for f in frames] == pytest.approx(
        [0.099, 0.202, 0.362, 0.4515, 0.556, 0.5695]
    )
    assert all(f.origin_m[:2] == (0, 0) for f in frames)
    assert tuple(f.axis_unit for f in frames) == JOINT_LOCAL_AXES
    assert end[2][3] == pytest.approx(0.5695)
    assert "not_hardware_calibrated" in VALIDATION_CLASS


def test_tool_offsets_are_separate_from_link6():
    assert forward_kinematics((0,) * 6, "gripper_base")[2][3] == pytest.approx(0.6125)
    assert forward_kinematics((0,) * 6, "gripper_mid_point")[2][3] == pytest.approx(0.6875)


def test_shoulder_quarter_turn_matches_independent_planar_geometry():
    q = (0, math.pi / 2, 0, 0, 0, 0)
    pose = forward_kinematics(q)
    assert tuple(row[3] for row in pose[:3]) == pytest.approx((0, -0.3675, 0.202))
    frames, _ = chain(q)
    assert frames[2].origin_m == pytest.approx((0, -0.160, 0.202))
    assert frames[3].axis_unit == pytest.approx((0, -1, 0))


def test_base_yaw_rotates_folded_workspace_and_preserves_height():
    q = (math.pi / 2, math.pi / 2, 0, 0, 0, 0)
    pose = forward_kinematics(q)
    assert tuple(row[3] for row in pose[:3]) == pytest.approx((0.3675, 0, 0.202), abs=1e-12)


def test_wrist_roll_changes_orientation_not_source_midpoint_position():
    q = (0.3, -0.8, 0.4, 0.2, -0.6, 0)
    a = forward_kinematics(q, "gripper_mid_point")
    b = forward_kinematics((*q[:-1], 1.2), "gripper_mid_point")
    assert [a[i][3] for i in range(3)] == pytest.approx([b[i][3] for i in range(3)])
    assert a != b


def test_rotation_is_orthonormal_at_mixed_configuration():
    pose = forward_kinematics((0.4, -0.5, 0.6, -0.7, 0.8, -0.9))
    for i in range(3):
        for j in range(3):
            assert sum(pose[k][i] * pose[k][j] for k in range(3)) == pytest.approx(
                float(i == j), abs=1e-12
            )
    assert pose[3] == (0, 0, 0, 1)


@pytest.mark.parametrize(
    "angles",
    [
        (),
        (0,) * 5,
        (0,) * 7,
        (0, 0, 0, 0, 0, float("nan")),
        (0, 0, 0, 0, 0, float("inf")),
        (0, 0, 0, 0, 0, True),
        (0, 0, 0, 0, 0, "0"),
    ],
)
def test_invalid_angles(angles):
    with pytest.raises(ValueError):
        forward_kinematics(angles)


def test_invalid_target():
    with pytest.raises(ValueError, match="target"):
        forward_kinematics((0,) * 6, "tool_guess")
