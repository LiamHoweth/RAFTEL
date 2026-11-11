"""Geometric checks of the explicit ideal branch, not physical validation."""

import math
import random

import pytest

from raftel_arm01.kinematics.thor_gripper import IdealThorGripper


def test_nominal_source_dimensions_and_gap_examples():
    model = IdealThorGripper()
    assert model.state(0).gap_m == pytest.approx(0.070)
    assert model.state(math.pi / 3).gap_m == pytest.approx(0.035)
    assert model.state(0).finger_translation_m == ((0, 0), (0, 0))


def test_both_link_lengths_and_constant_finger_pivot_vectors():
    model = IdealThorGripper()
    for q in (0, 0.2, 0.7, 1.2):
        state = model.state(q)
        for i, side in enumerate((-1, 1)):
            a, b = state.driven_endpoints_m[i], state.auxiliary_endpoints_m[i]
            assert math.hypot(a[0] - side * 0.0145, a[1] - 0.0325) == pytest.approx(0.035)
            assert math.hypot(b[0] - side * 0.006, b[1] - 0.051) == pytest.approx(0.035)
            assert (b[0] - a[0], b[1] - a[1]) == pytest.approx((-side * 0.0085, 0.0185))
            # Nonzero cross product excludes the collinear toggle on this branch.
            cross = (b[0] - a[0]) * (a[1] - 0.0325) - (b[1] - a[1]) * (a[0] - side * 0.0145)
            assert abs(cross) > 1e-6


def test_jacobians_match_finite_differences_and_gap_virtual_work():
    model, rng, epsilon = IdealThorGripper(), random.Random(25), 1e-6
    for _ in range(30):
        q = rng.uniform(0.01, 1.5)
        state, plus, minus = model.state(q), model.state(q + epsilon), model.state(q - epsilon)
        assert state.gap_derivative_m_rad == pytest.approx(
            (plus.gap_m - minus.gap_m) / (2 * epsilon), abs=1e-10
        )
        for side in (0, 1):
            assert state.finger_translation_derivative_m_rad[side] == pytest.approx(
                tuple(
                    (plus.finger_translation_m[side][i] - minus.finger_translation_m[side][i])
                    / (2 * epsilon)
                    for i in (0, 1)
                ),
                abs=1e-10,
            )
        # Conjugate gap force times dg/dq equals the sum of opposing point-force work.
        force = 3.0
        assert force * state.gap_derivative_m_rad == pytest.approx(
            force
            * (
                state.finger_translation_derivative_m_rad[1][0]
                - state.finger_translation_derivative_m_rad[0][0]
            )
        )


@pytest.mark.parametrize("bad", [-0.1, math.pi / 2, math.pi, math.nan, math.inf, True, "0"])
def test_invalid_or_outside_study_angles_rejected(bad):
    with pytest.raises(ValueError):
        IdealThorGripper().state(bad)


@pytest.mark.parametrize(
    "override",
    [
        {"link_length_m": 0},
        {"link_length_m": math.inf},
        {"driven_half_spacing_m": 0.005},
        {"auxiliary_base_y_m": 0.030},
        {"contact_offset_from_driven_tip_m": 0.020},
    ],
)
def test_degenerate_or_unsupported_geometry_rejected(override):
    with pytest.raises(ValueError):
        IdealThorGripper(**override)


def test_finite_inputs_with_overflowing_result_are_rejected():
    with pytest.raises(ValueError, match="finite"):
        IdealThorGripper(link_length_m=1e308).state(0)
