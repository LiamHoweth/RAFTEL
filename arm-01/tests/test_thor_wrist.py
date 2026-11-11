"""Independent analytical and finite-difference COM/virtual-work checks."""

import math
import random

import pytest

from raftel_arm01.kinematics.thor_wrist import (
    MotionStep,
    WristPointState,
    gravity_generalized_torque_nm,
    point_state,
)


def step(origin=(0, 0, 0), axis=(0, 1, 0), a=1, b=0):
    return MotionStep(origin, axis, a, b, "explicit synthetic mechanism fixture")


def test_fixed_point_has_zero_generalized_moment():
    state = point_state((0.1, 0.2, 0.3), 0.4, -0.8, ())
    assert state.position_m == (0.1, 0.2, 0.3)
    assert state.dq5_m_rad == (0, 0, 0)
    assert state.dq6_m_rad == (0, 0, 0)
    assert gravity_generalized_torque_nm(state, 2) == (0, 0)


def test_fold_known_quarter_turn_and_gravity_moment():
    state = point_state((0, 0, 0.2), math.pi / 2, 0, (step(),))
    assert state.position_m == pytest.approx((0.2, 0, 0), abs=1e-15)
    assert state.dq5_m_rad == pytest.approx((0, 0, -0.2), abs=1e-15)
    assert gravity_generalized_torque_nm(state, 0.5) == pytest.approx((0.980665, 0))


def test_roll_axis_is_carried_by_fold_not_left_in_world():
    steps = (step(), step(axis=(0, 0, 1), a=0, b=1))
    state = point_state((0.1, 0, 0.2), math.pi / 2, math.pi / 2, steps)
    # R_y(pi/2) R_z(pi/2) p = (.2, .1, 0).
    assert state.position_m == pytest.approx((0.2, 0.1, 0), abs=1e-15)
    assert state.dq5_m_rad == pytest.approx((0, 0, -0.2), abs=1e-15)
    assert state.dq6_m_rad == pytest.approx((0, 0, 0.1), abs=1e-15)


def test_rotor_phase_does_not_move_axis_centered_com():
    # Coupled angle coefficients in a fixture are explicit, not Thor calibration.
    steps = (step(origin=(0.03, 0.04, 0.05), a=-1, b=2),)
    state = point_state((0.03, 0.2, 0.05), 0.8, -0.7, steps)
    assert state.position_m == pytest.approx((0.03, 0.2, 0.05))
    assert state.dq5_m_rad == pytest.approx((0, 0, 0))
    assert state.dq6_m_rad == pytest.approx((0, 0, 0))


def test_rotor_off_axis_com_carries_both_generalized_coordinates():
    state = point_state((0, 0, 0.1), 0.3, -0.2, (step(a=-1, b=2),))
    assert state.dq6_m_rad == pytest.approx(tuple(-2 * v for v in state.dq5_m_rad))
    assert gravity_generalized_torque_nm(state, 1)[1] == pytest.approx(
        -2 * gravity_generalized_torque_nm(state, 1)[0]
    )


def test_general_chains_match_centered_difference_at_nonzero_angles():
    steps = (
        step(origin=(0.03, -0.02, 0.1), axis=(0, 1, 0), a=1, b=0.2),
        step(origin=(0.01, 0.04, 0.3), axis=(0, 0, 1), a=-0.5, b=2),
    )
    rng = random.Random(16)
    h = 1e-6
    for _ in range(50):
        q5, q6 = rng.uniform(-1, 1), rng.uniform(-1, 1)
        point = (rng.random() * 0.2, rng.random() * 0.2, 0.4)
        state = point_state(point, q5, q6, steps)
        for index, derivative in enumerate((state.dq5_m_rad, state.dq6_m_rad)):
            plus = point_state(
                point, q5 + (h if index == 0 else 0), q6 + (h if index == 1 else 0), steps
            )
            minus = point_state(
                point, q5 - (h if index == 0 else 0), q6 - (h if index == 1 else 0), steps
            )
            finite_difference = tuple(
                (a - b) / (2 * h) for a, b in zip(plus.position_m, minus.position_m, strict=True)
            )
            assert derivative == pytest.approx(finite_difference, abs=1e-9)


def test_gravity_matches_negative_potential_gradient_and_virtual_work():
    steps = (step(origin=(0, 0, 0.1)), step(origin=(0, 0, 0.3), axis=(0, 0, 1), a=0, b=1))
    point, mass, q5, q6 = (0.1, -0.05, 0.4), 0.23, 0.7, -0.4
    h = 1e-6
    state = point_state(point, q5, q6, steps)
    torques = gravity_generalized_torque_nm(state, mass)
    for index in (0, 1):
        plus = point_state(
            point, q5 + (h if index == 0 else 0), q6 + (h if index == 1 else 0), steps
        )
        minus = point_state(
            point, q5 - (h if index == 0 else 0), q6 - (h if index == 1 else 0), steps
        )
        negative_potential_gradient = (
            -mass * 9.80665 * (plus.position_m[2] - minus.position_m[2]) / (2 * h)
        )
        assert torques[index] == pytest.approx(negative_potential_gradient, abs=1e-9)
    qdot = (0.3, -0.8)
    com_z_velocity = state.dq5_m_rad[2] * qdot[0] + state.dq6_m_rad[2] * qdot[1]
    assert sum(a * b for a, b in zip(torques, qdot, strict=True)) == pytest.approx(
        -mass * 9.80665 * com_z_velocity
    )


def test_rigid_frame_change_carries_points_axes_jacobians_and_gravity():
    # Independent R_x(pi/2) plus a translation changes the expression frame.
    def rotate(vector):
        x, y, z = vector
        return (x, -z, y)

    def transform(point):
        return tuple(a + b for a, b in zip(rotate(point), (0.3, -0.2, 0.1), strict=True))

    steps = (
        step(origin=(0, 0, 0.556)),
        step(origin=(0, 0, 0.5775), axis=(0, 0, 1), a=0, b=1),
    )
    transformed_steps = tuple(
        step(transform(s.origin_m), rotate(s.axis_unit), s.q5_coefficient, s.q6_coefficient)
        for s in steps
    )
    original = point_state((0.04, -0.02, 0.63), 0.7, -0.4, steps)
    transformed = point_state(transform((0.04, -0.02, 0.63)), 0.7, -0.4, transformed_steps)
    assert transformed.position_m == pytest.approx(transform(original.position_m), abs=1e-15)
    assert transformed.dq5_m_rad == pytest.approx(rotate(original.dq5_m_rad), abs=1e-15)
    assert transformed.dq6_m_rad == pytest.approx(rotate(original.dq6_m_rad), abs=1e-15)
    assert gravity_generalized_torque_nm(transformed, 0.2, rotate((0, 0, -9.80665))) == (
        pytest.approx(gravity_generalized_torque_nm(original, 0.2), abs=1e-15)
    )


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "1", None])
def test_nonfinite_or_nonnumeric_angles_rejected(bad):
    with pytest.raises(ValueError, match="finite"):
        point_state((0, 0, 0), bad, 0, ())


@pytest.mark.parametrize("axis", [(0, 0, 0), (0, 2, 0), (1, 1, 0)])
def test_nonunit_axes_rejected(axis):
    with pytest.raises(ValueError, match="unit"):
        step(axis=axis)


def test_evidence_required_and_input_lists_normalized_immutably():
    with pytest.raises(ValueError, match="evidence"):
        MotionStep((0, 0, 0), (0, 1, 0), 1, 0, " ")
    origin = [0, 0, 0]
    declaration = MotionStep(origin, [0, 1, 0], 1, 0, "fixture")
    origin[0] = 5
    assert declaration.origin_m == (0, 0, 0)


def test_invalid_mass_gravity_or_motion_declarations_fail():
    state = point_state((0, 0, 1), 0, 0, ())
    for mass in (-1, math.nan, True):
        with pytest.raises(ValueError):
            gravity_generalized_torque_nm(state, mass)
    with pytest.raises(ValueError):
        point_state((0, 0, 0), 0, 0, ["not a step"])
    with pytest.raises(ValueError):
        gravity_generalized_torque_nm(WristPointState((0, 0, 0), (math.nan, 0, 0), (0, 0, 0)), 1)


def test_declared_angle_overflow_does_not_silently_create_nan():
    with pytest.raises(ValueError, match="finite"):
        point_state((0, 0, 0.1), 1e308, 1e308, (step(a=2, b=2),))
