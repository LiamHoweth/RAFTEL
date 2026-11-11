"""Analytical columns checked against independent FK position/angular differences."""

import math
import random

import pytest

from raftel_arm01.kinematics.thor_frames import transform_point
from raftel_arm01.kinematics.thor_jacobian import (
    singularity_diagnostic,
    spatial_jacobian,
    symmetric_eigenvalues,
)
from raftel_arm01.kinematics.thor_model import forward_kinematics


@pytest.mark.parametrize("target", ["link_6", "gripper_base", "gripper_mid_point"])
def test_seeded_cartesian_and_angular_velocity_differences(target):
    rng = random.Random(396)
    h = 1e-6
    for _ in range(60):
        q = tuple(rng.uniform(-1.4, 1.4) for _ in range(6))
        offset = tuple(rng.uniform(-0.05, 0.05) for _ in range(3))
        jacobian = spatial_jacobian(q, target, point_offset_m=offset)
        pose = forward_kinematics(q, target)
        for column in range(6):
            plus = forward_kinematics(
                tuple(v + (h if i == column else 0) for i, v in enumerate(q)), target
            )
            minus = forward_kinematics(
                tuple(v - (h if i == column else 0) for i, v in enumerate(q)), target
            )
            p_plus, p_minus = transform_point(plus, offset), transform_point(minus, offset)
            numeric_linear = tuple((a - b) / (2 * h) for a, b in zip(p_plus, p_minus, strict=True))
            rdot_rt = tuple(
                tuple(
                    sum((plus[i][k] - minus[i][k]) / (2 * h) * pose[j][k] for k in range(3))
                    for j in range(3)
                )
                for i in range(3)
            )
            numeric_angular = (
                (rdot_rt[2][1] - rdot_rt[1][2]) / 2,
                (rdot_rt[0][2] - rdot_rt[2][0]) / 2,
                (rdot_rt[1][0] - rdot_rt[0][1]) / 2,
            )
            assert tuple(row[column] for row in jacobian[:3]) == pytest.approx(
                numeric_linear, abs=2e-10
            )
            assert tuple(row[column] for row in jacobian[3:]) == pytest.approx(
                numeric_angular, abs=3e-10
            )


def test_independent_zero_pose_planar_columns_and_singularity():
    j = spatial_jacobian((0,) * 6)
    assert tuple(row[1] for row in j) == pytest.approx((0, -0.3675, 0, 1, 0, 0))
    assert tuple(row[2] for row in j) == pytest.approx((0, -0.2075, 0, 1, 0, 0))
    assert tuple(row[4] for row in j) == pytest.approx((0, -0.0135, 0, 1, 0, 0))
    assert tuple(row[5] for row in j) == pytest.approx((0, 0, 0, 0, 0, 1))
    diagnostic = singularity_diagnostic(j, characteristic_length_m=0.3)
    assert diagnostic.numerical_rank == 3
    assert diagnostic.condition_number is None
    assert "not_physical" in diagnostic.validation_class


def test_offset_changes_last_roll_linear_velocity():
    j = spatial_jacobian((0,) * 6, point_offset_m=(0.02, 0, 0))
    assert tuple(row[5] for row in j) == pytest.approx((0, 0.02, 0, 0, 0, 1))


def test_full_rank_mixed_pose_and_known_singular_values():
    j = tuple(tuple(float(i == k) * (i + 1) for k in range(6)) for i in range(6))
    diagnostic = singularity_diagnostic(j, characteristic_length_m=1)
    assert diagnostic.singular_values == pytest.approx((6, 5, 4, 3, 2, 1))
    assert diagnostic.numerical_rank == 6
    assert diagnostic.condition_number == 6
    mixed = singularity_diagnostic(
        spatial_jacobian((0.4, -0.5, 0.6, -0.7, 0.8, -0.9)), characteristic_length_m=0.3
    )
    assert mixed.numerical_rank == 6
    assert 10 < mixed.condition_number < 30


def test_scale_covariance_of_dimensionless_diagnostic():
    j = spatial_jacobian((0.4, -0.5, 0.6, -0.7, 0.8, -0.9))
    scaled = tuple(tuple(v * 1000 if i < 3 else v for v in row) for i, row in enumerate(j))
    a = singularity_diagnostic(j, characteristic_length_m=0.3)
    b = singularity_diagnostic(scaled, characteristic_length_m=300)
    assert a.singular_values == pytest.approx(b.singular_values)
    assert a.condition_number == pytest.approx(b.condition_number)


def test_jacobi_solver_known_rotated_block_and_trace():
    value = (
        (2, 1, 0, 0, 0, 0),
        (1, 2, 0, 0, 0, 0),
        (0, 0, 0, 0, 0, 0),
        (0, 0, 0, 4, 0, 0),
        (0, 0, 0, 0, 5, 0),
        (0, 0, 0, 0, 0, 6),
    )
    assert symmetric_eigenvalues(value) == pytest.approx((6, 5, 4, 3, 1, 0))
    assert math.fsum(symmetric_eigenvalues(value)) == 19


@pytest.mark.parametrize(
    "kwargs",
    [
        {"characteristic_length_m": 0},
        {"characteristic_length_m": True},
        {"characteristic_length_m": float("nan")},
        {"characteristic_length_m": 0.3, "relative_rank_tolerance": 0},
        {"characteristic_length_m": 0.3, "relative_rank_tolerance": 1},
    ],
)
def test_invalid_scale_or_threshold(kwargs):
    with pytest.raises(ValueError):
        singularity_diagnostic(spatial_jacobian((0,) * 6), **kwargs)


def test_invalid_offsets_target_and_asymmetric_matrix():
    for offset in ((0, 0), (0, 0, float("inf")), (0, True, 0)):
        with pytest.raises(ValueError):
            spatial_jacobian((0,) * 6, point_offset_m=offset)
    with pytest.raises(ValueError, match="target"):
        spatial_jacobian((0,) * 6, "tcp_guess")
    matrix = [[float(i == j) for j in range(6)] for i in range(6)]
    matrix[0][1] = 1
    with pytest.raises(ValueError, match="symmetric"):
        symmetric_eigenvalues(matrix)
