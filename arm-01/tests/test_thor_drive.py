"""Verify source-convention algebra; these tests do not validate a physical arm."""

import math
import random

import pytest

from raftel_arm01.kinematics.thor_drive import drive_to_joints, joints_to_drive


def test_zero_and_source_channel_order():
    assert joints_to_drive((0, 0, 0, 0, 0, 0)) == (0,) * 7
    assert joints_to_drive((1, 2, 3, 4, 5, 6)) == (1, -2, -2, -3, 4, 7, 17)
    assert drive_to_joints((1, -2, -2, -3, 4, 7, 17)) == (1, 2, 3, 4, 5, 6)


def test_pure_wrist_q5_is_opposite_channels():
    drives = joints_to_drive((0, 0, 0, 0, math.pi / 4, 0))
    assert drives[5:] == pytest.approx((-math.pi / 4, math.pi / 4))
    assert drive_to_joints(drives) == pytest.approx((0, 0, 0, 0, math.pi / 4, 0))


def test_pure_wrist_q6_is_equal_channels_at_source_scale():
    drives = joints_to_drive((0, 0, 0, 0, 0, math.pi / 4))
    assert drives[5:] == pytest.approx((math.pi / 2, math.pi / 2))
    assert drive_to_joints(drives) == pytest.approx((0, 0, 0, 0, 0, math.pi / 4))


def test_seeded_roundtrip_preserves_six_coordinates_without_degree_quantization():
    rng = random.Random(21)
    for _ in range(100):
        joints = tuple(rng.uniform(-math.pi, math.pi) for _ in range(6))
        assert drive_to_joints(joints_to_drive(joints)) == pytest.approx(joints, abs=1e-12)
    small = (0.00001, 0, 0, 0, 0, 0)
    assert drive_to_joints(joints_to_drive(small)) == small


def test_shoulder_mismatch_rejected_even_for_large_coordinates():
    with pytest.raises(ValueError, match="shoulder"):
        drive_to_joints((0, 0, 0.001, 0, 0, 0, 0))
    with pytest.raises(ValueError, match="shoulder"):
        drive_to_joints((0, 1e9, 1e9 + 0.01, 0, 0, 0, 0))


def test_shoulder_roundoff_tolerance_is_absolute_and_documented():
    assert drive_to_joints((0, 1, 1 + 1e-10, 0, 0, 0, 0)) == (0, -1, 0, 0, 0, 0)


@pytest.mark.parametrize("size", [0, 5, 7])
def test_joint_count_rejected(size):
    with pytest.raises(ValueError, match="exactly 6"):
        joints_to_drive([0] * size)


@pytest.mark.parametrize("size", [0, 6, 8])
def test_drive_count_rejected(size):
    with pytest.raises(ValueError, match="exactly 7"):
        drive_to_joints([0] * size)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "1", None, 1j])
def test_invalid_values_rejected_in_both_spaces(bad):
    with pytest.raises(ValueError, match="finite real"):
        joints_to_drive([0, 0, 0, 0, 0, bad])
    with pytest.raises(ValueError, match="finite real"):
        drive_to_joints([0, 0, 0, 0, 0, 0, bad])


def test_scalar_input_rejected_with_clear_error():
    with pytest.raises(ValueError, match="sequence"):
        joints_to_drive(1)
    with pytest.raises(ValueError, match="sequence"):
        drive_to_joints(None)


def test_finite_inputs_cannot_silently_create_infinite_output():
    with pytest.raises(ValueError, match="finite real"):
        joints_to_drive((0, 0, 0, 0, 1e308, 1e308))
    # Inverse divides first, so valid finite results avoid intermediate overflow.
    result = drive_to_joints((0, 0, 0, 0, 0, 1e308, 1e308))
    assert result[4] == 0
    assert result[5] == 5e307
