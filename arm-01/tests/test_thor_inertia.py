"""Independent analytical inertia identities; no robot inertia is inferred."""

import math
import random

import pytest

from raftel_arm01.engineering.inertia import (
    IDENTITY,
    MassProperties,
    aggregate_mass_properties,
    transform_mass_properties,
    uniform_box,
    uniform_cylinder,
    validate_centroidal_inertia,
    validate_rotation,
)


def flatten(matrix):
    return tuple(value for row in matrix for value in row)


def test_known_box_and_axial_cylinder_inertias():
    box = uniform_box(12, (1, 2, 3), frame="fixture", evidence="uniform analytic solid")
    assert flatten(box.centroidal_inertia_kg_m2) == pytest.approx((13, 0, 0, 0, 10, 0, 0, 0, 5))
    cylinder = uniform_cylinder(2, 3, 4, frame="fixture", evidence="uniform analytic solid")
    assert flatten(cylinder.centroidal_inertia_kg_m2) == pytest.approx(
        (43 / 6, 0, 0, 0, 43 / 6, 0, 0, 0, 9)
    )


def test_geometric_scaling_at_fixed_mass_and_fixed_density():
    baseline = uniform_box(2, (0.03, 0.06, 0.1), frame="m", evidence="fixture")
    for scale in (0.001, 0.1, 3, 1000):
        fixed_mass = uniform_box(
            2, tuple(scale * x for x in (0.03, 0.06, 0.1)), frame="m", evidence="fixture"
        )
        fixed_density = uniform_box(
            2 * scale**3,
            tuple(scale * x for x in (0.03, 0.06, 0.1)),
            frame="m",
            evidence="fixture",
        )
        assert flatten(fixed_mass.centroidal_inertia_kg_m2) == pytest.approx(
            tuple(x * scale**2 for x in flatten(baseline.centroidal_inertia_kg_m2)),
            rel=1e-12,
            abs=1e-30,
        )
        assert flatten(fixed_density.centroidal_inertia_kg_m2) == pytest.approx(
            tuple(x * scale**5 for x in flatten(baseline.centroidal_inertia_kg_m2)),
            rel=1e-12,
            abs=1e-30,
        )


def test_splitting_uniform_box_and_parallel_axis_recovers_original():
    whole = uniform_box(8, (2, 4, 6), frame="world", evidence="analytic whole")
    half = uniform_box(4, (1, 4, 6), frame="local", evidence="analytic half")
    parts = tuple(
        transform_mass_properties(
            half,
            IDENTITY,
            (x, 0, 0),
            target_frame="world",
            transform_evidence="known half-box COM",
        )
        for x in (-0.5, 0.5)
    )
    combined = aggregate_mass_properties(parts, evidence="partition identity")
    assert combined.mass_kg == whole.mass_kg
    assert combined.com_m == whole.com_m
    assert flatten(combined.centroidal_inertia_kg_m2) == pytest.approx(
        flatten(whole.centroidal_inertia_kg_m2)
    )


def test_point_cloud_independently_checks_products_of_inertia_and_covariance():
    rng = random.Random(9021)
    points = [tuple(rng.uniform(-1, 1) for _ in range(3)) for _ in range(20)]
    masses = [rng.uniform(0.1, 2) for _ in points]
    zero = ((0.0, 0.0, 0.0),) * 3
    bodies = tuple(
        MassProperties(mass, point, zero, "world", "explicit analytical point mass")
        for mass, point in zip(masses, points, strict=True)
    )
    combined = aggregate_mass_properties(bodies, evidence="point cloud independent sum")
    total = sum(masses)
    com = tuple(
        sum(m * p[i] for m, p in zip(masses, points, strict=True)) / total for i in range(3)
    )
    # A tensor quadratic form equals sum(m * |omega cross relative|^2).
    for _ in range(10):
        omega = tuple(rng.uniform(-2, 2) for _ in range(3))
        quadratic = sum(
            omega[i] * combined.centroidal_inertia_kg_m2[i][j] * omega[j]
            for i in range(3)
            for j in range(3)
        )
        expected = 0
        for mass, point in zip(masses, points, strict=True):
            r = tuple(point[i] - com[i] for i in range(3))
            cross = (
                omega[1] * r[2] - omega[2] * r[1],
                omega[2] * r[0] - omega[0] * r[2],
                omega[0] * r[1] - omega[1] * r[0],
            )
            expected += mass * sum(x * x for x in cross)
        assert quadratic == pytest.approx(expected, rel=1e-12)

    angle = 0.73
    rotation = (
        (math.cos(angle), -math.sin(angle), 0),
        (math.sin(angle), math.cos(angle), 0),
        (0, 0, 1),
    )
    transformed_then_summed = aggregate_mass_properties(
        tuple(
            transform_mass_properties(
                body,
                rotation,
                (0.2, -0.4, 0.7),
                target_frame="target",
                transform_evidence="fixture",
            )
            for body in bodies
        ),
        evidence="frame covariance",
    )
    summed_then_transformed = transform_mass_properties(
        combined, rotation, (0.2, -0.4, 0.7), target_frame="target", transform_evidence="fixture"
    )
    assert transformed_then_summed.com_m == pytest.approx(summed_then_transformed.com_m)
    assert flatten(transformed_then_summed.centroidal_inertia_kg_m2) == pytest.approx(
        flatten(summed_then_transformed.centroidal_inertia_kg_m2), rel=1e-12
    )


def test_unknown_inertia_propagates_without_erasing_mass_or_com():
    purchased = MassProperties(
        0.38, (0, 0, 0), None, "world", "known mass, unknown internal inertia"
    )
    printed = uniform_box(0.02, (0.01, 0.02, 0.03), frame="world", evidence="uniform scenario only")
    result = aggregate_mass_properties((purchased, printed), evidence="partial inertia model")
    assert result.mass_kg == pytest.approx(0.40)
    assert result.centroidal_inertia_kg_m2 is None
    assert (
        transform_mass_properties(
            result, IDENTITY, (1, 2, 3), target_frame="other", transform_evidence="known transform"
        ).centroidal_inertia_kg_m2
        is None
    )


@pytest.mark.parametrize(
    "bad",
    [
        ((-1, 0, 0), (0, 1, 0), (0, 0, 1)),
        ((1, 0, 0), (0, 1, 0), (0, 0, 3)),
        ((1, 0.1, 0), (0, 1, 0), (0, 0, 1)),
        ((1, 2, 0), (2, 1, 0), (0, 0, 1)),
        ((1, 0, 0), (0, math.nan, 0), (0, 0, 1)),
    ],
)
def test_nonphysical_or_nonfinite_tensors_rejected_at_all_si_scales(bad):
    for scale in (1, 1e-18, 1e18):
        with pytest.raises(ValueError):
            validate_centroidal_inertia(tuple(tuple(x * scale for x in row) for row in bad))


@pytest.mark.parametrize("epsilon", [1e-7, 1e-6])
def test_near_rank_deficient_triangle_violation_cannot_hide_in_small_minors(epsilon):
    tensor = ((1, -epsilon, 0), (-epsilon, 1, 0), (0, 0, 0))
    rotation = (
        (1 / math.sqrt(2), -1 / math.sqrt(2), 0),
        (1 / math.sqrt(6), 1 / math.sqrt(6), -2 / math.sqrt(6)),
        (1 / math.sqrt(3), 1 / math.sqrt(3), 1 / math.sqrt(3)),
    )
    rotated = tuple(
        tuple(
            math.fsum(
                rotation[i][a] * tensor[a][b] * rotation[j][b] for a in range(3) for b in range(3)
            )
            for j in range(3)
        )
        for i in range(3)
    )
    for scale in (1e-24, 1, 1e24):
        for candidate in (tensor, rotated):
            with pytest.raises(ValueError, match="triangle"):
                validate_centroidal_inertia(
                    tuple(tuple(x * scale for x in row) for row in candidate)
                )
        valid = ((scale, 0, 0), (0, scale, 0), (0, 0, 0))
        assert validate_centroidal_inertia(valid) == valid


def test_finite_large_valid_tensor_does_not_overflow_half_trace():
    tensor = ((1.7e308, 0, 0), (0, 1.7e308, 0), (0, 0, 1.7e308))
    assert validate_centroidal_inertia(tensor) == tensor


def test_subnormal_tensor_checks_preserve_sign_and_triangle_constraints():
    tiny = math.ulp(0.0)
    valid = ((tiny, 0, 0), (0, tiny, 0), (0, 0, tiny))
    assert validate_centroidal_inertia(valid) == valid
    with pytest.raises(ValueError, match="positive semidefinite"):
        validate_centroidal_inertia(((-tiny, 0, 0), (0, -tiny, 0), (0, 0, -tiny)))
    with pytest.raises(ValueError, match="triangle"):
        validate_centroidal_inertia(((tiny, 0, 0), (0, tiny, 0), (0, 0, 3 * tiny)))


@pytest.mark.parametrize(
    "bad", [((1, 0, 0), (0, 1, 0), (0, 0, -1)), ((2, 0, 0), (0, 1, 0), (0, 0, 1))]
)
def test_reflection_and_scaling_are_not_rotations(bad):
    with pytest.raises(ValueError):
        validate_rotation(bad)


def test_mixed_frames_and_empty_aggregation_rejected():
    body = uniform_box(1, (1, 1, 1), frame="one", evidence="fixture")
    other = uniform_box(1, (1, 1, 1), frame="two", evidence="fixture")
    with pytest.raises(ValueError, match="same frame"):
        aggregate_mass_properties((body, other), evidence="fixture")
    with pytest.raises(ValueError, match="at least one"):
        aggregate_mass_properties((), evidence="fixture")


@pytest.mark.parametrize("mass", [0, -1, True, "1", math.inf, math.nan])
def test_invalid_mass_cannot_become_an_inertia(mass):
    with pytest.raises(ValueError):
        uniform_box(mass, (1, 1, 1), frame="fixture", evidence="fixture")
