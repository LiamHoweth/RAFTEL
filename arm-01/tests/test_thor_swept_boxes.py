"""Synthetic swept proxies and independent exact-rational interval witnesses."""

import importlib.util
import json
import math
import random
from fractions import Fraction
from pathlib import Path

import pytest

from raftel_arm01.kinematics.thor_collision import BoxProxy, intersect_boxes
from raftel_arm01.kinematics.thor_frames import IDENTITY
from raftel_arm01.kinematics.thor_swept_boxes import (
    LINEAR_TRANSLATION_ASSUMPTION,
    sweep_against_static_boxes,
    sweep_linear_translation,
)

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "thor_swept_box_study", ROOT / "tools/thor_swept_box_study.py"
)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def box(name, center=(0, 0, 0), half=(0.25,) * 3, *, frame="fixture", rotation=IDENTITY):
    transform = tuple((*rotation[i][:3], center[i]) for i in range(3)) + (IDENTITY[3],)
    return BoxProxy(
        name, frame, half, transform, "Explicit synthetic box fixture", "synthetic_exact_box"
    )


def sweep(start, end, obstacle, **kwargs):
    return sweep_linear_translation(
        start,
        end,
        obstacle,
        assumption=LINEAR_TRANSLATION_ASSUMPTION,
        motion_evidence="Explicit synthetic linear path declaration",
        **kwargs,
    )


def rational_interval(start, end, half, obstacle_center, obstacle_half, padding=0):
    """Independent exact inequality clipping, with floats treated as exact dyadics."""
    entry, leave = Fraction(0), Fraction(1)
    for s, e, h, c, fixed_half in zip(
        start, end, half, obstacle_center, obstacle_half, strict=True
    ):
        s, e, h, c, fixed_half, pad = map(Fraction, (s, e, h, c, fixed_half, padding))
        lower, upper = c - fixed_half - h - pad, c + fixed_half + h + pad
        velocity = e - s
        if velocity == 0:
            if not lower <= s <= upper:
                return None
        else:
            roots = ((lower - s) / velocity, (upper - s) / velocity)
            entry, leave = max(entry, min(roots)), min(leave, max(roots))
            if entry > leave:
                return None
    return entry, leave


def test_separated_endpoints_miss_midpath_overlap():
    start, end = box("moving", (-2, 0, 0)), box("moving", (2, 0, 0))
    fixed = box("obstacle", half=(0.5,) * 3)
    assert all(
        intersect_boxes(value, fixed).relation == "no_proxy_overlap" for value in (start, end)
    )
    result = sweep(start, end, fixed)
    assert result.overlap_parameter_interval == (5 / 16, 11 / 16)
    assert result.relation == "proxy_overlap_or_contact_during_declared_linear_sweep"
    assert result.physical_collision_free is None
    assert result.robot_path_clearance is None


@pytest.mark.parametrize(
    "center,expected", (((0, 0, 0), (0, 1)), ((2, 0, 0), None), ((0.75, 0, 0), (0, 1)))
)
def test_stationary_inside_outside_and_tangent(center, expected):
    result = sweep(box("moving", center), box("moving", center), box("obstacle", half=(0.5,) * 3))
    assert result.overlap_parameter_interval == expected


def test_start_inside_end_contact_and_singleton_point_crossing():
    fixed = box("obstacle", half=(0.5,) * 3)
    assert sweep(box("m"), box("m", (2, 0, 0)), fixed).overlap_parameter_interval == (0, 3 / 8)
    assert sweep(
        box("m", (-2, 0, 0)), box("m", (-0.75, 0, 0)), fixed
    ).overlap_parameter_interval == (1, 1)
    point = box("point", half=(0, 0, 0))
    assert sweep(
        box("m", (-1, 0, 0), (0, 0, 0)), box("m", (1, 0, 0), (0, 0, 0)), point
    ).overlap_parameter_interval == (0.5, 0.5)


def test_face_grazing_is_retained_for_an_entire_closed_interval():
    result = sweep(
        box("m", (-2, 0.75, 0)), box("m", (2, 0.75, 0)), box("obstacle", half=(0.5,) * 3)
    )
    assert result.overlap_parameter_interval == (5 / 16, 11 / 16)
    assert result.axis_parameter_intervals[1] == (0, 1)


def test_disjoint_axis_parameter_intervals_do_not_form_a_false_hit():
    # X reaches the obstacle early; Y reaches it later, with no shared u.
    result = sweep(box("m", (0, -4, 0)), box("m", (4, 0, 0)), box("obstacle", half=(0.25,) * 3))
    assert all(interval is not None for interval in result.axis_parameter_intervals)
    assert result.overlap_parameter_interval is None


def test_reversing_endpoints_reverses_entry_and_exit_parameters():
    start, end, fixed = box("m", (-3, 0, 0)), box("m", (1, 0, 0)), box("o", half=(0.5,) * 3)
    interval = sweep(start, end, fixed).overlap_parameter_interval
    reverse = sweep(end, start, fixed).overlap_parameter_interval
    assert interval == (9 / 16, 15 / 16)
    assert reverse == (1 - interval[1], 1 - interval[0])


def test_exact_signed_permutation_fixed_orientation_maps_half_widths():
    rz90 = ((0, -1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
    start = box("m", (-2, 0, 0), (0.125, 0.25, 0.5), rotation=rz90)
    end = box("m", (2, 0, 0), (0.125, 0.25, 0.5), rotation=rz90)
    fixed = box("o", half=(0.5,) * 3, rotation=rz90)
    assert sweep(start, end, fixed).overlap_parameter_interval == (5 / 16, 11 / 16)


def test_numerical_padding_is_explicit_dilation_not_physical_margin():
    start, end, fixed = box("m", (-2, 0.875, 0)), box("m", (2, 0.875, 0)), box("o", half=(0.5,) * 3)
    assert sweep(start, end, fixed).overlap_parameter_interval is None
    result = sweep(start, end, fixed, numerical_tolerance_m=0.125)
    assert result.overlap_parameter_interval == (9 / 32, 23 / 32)
    assert result.physical_collision_free is None


def test_randomized_exact_fraction_oracle():
    rng = random.Random(78123)
    for _ in range(750):
        start = tuple(rng.randint(-20, 20) / 4 for _ in range(3))
        end = start if rng.random() < 0.15 else tuple(rng.randint(-20, 20) / 4 for _ in range(3))
        half = tuple(rng.randint(0, 8) / 4 for _ in range(3))
        center = tuple(rng.randint(-12, 12) / 4 for _ in range(3))
        fixed_half = tuple(rng.randint(0, 8) / 4 for _ in range(3))
        padding = rng.choice((0, 0.125))
        expected = rational_interval(start, end, half, center, fixed_half, padding)
        result = sweep(
            box("m", start, half),
            box("m", end, half),
            box("o", center, fixed_half),
            numerical_tolerance_m=padding,
        )
        if expected is None:
            assert result.overlap_parameter_interval is None
        else:
            assert result.overlap_parameter_interval == pytest.approx(
                tuple(map(float, expected)), rel=1e-12, abs=1e-12
            )


@pytest.mark.parametrize(
    "case",
    (
        "frame",
        "identity",
        "obstacle_frame",
        "obstacle_identity",
        "resize",
        "rotate_end",
        "rotate_start",
        "rotate_obstacle",
        "assumption",
        "evidence",
    ),
)
def test_unsupported_inputs_reject_instead_of_silently_broadening_scope(case):
    start, end, fixed = box("m", (-2, 0, 0)), box("m", (2, 0, 0)), box("o")
    rz90 = ((0, -1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
    angle = 0.1
    rotated = (
        (math.cos(angle), -math.sin(angle), 0, 0),
        (math.sin(angle), math.cos(angle), 0, 0),
        (0, 0, 1, 0),
        (0, 0, 0, 1),
    )
    assumption, evidence = LINEAR_TRANSLATION_ASSUMPTION, "Declared fixture"
    if case == "frame":
        end = box("m", (2, 0, 0), frame="other")
    elif case == "identity":
        end = box("different", (2, 0, 0))
    elif case == "obstacle_frame":
        fixed = box("o", frame="other")
    elif case == "obstacle_identity":
        fixed = box("m")
    elif case == "resize":
        end = box("m", (2, 0, 0), half=(1, 1, 1))
    elif case == "rotate_end":
        end = box("m", (2, 0, 0), rotation=rz90)
    elif case == "rotate_start":
        start = box("m", (-2, 0, 0), rotation=rotated)
    elif case == "rotate_obstacle":
        fixed = box("o", rotation=rotated)
    elif case == "assumption":
        assumption = "interpolate_joint_endpoints"
    elif case == "evidence":
        evidence = ""
    with pytest.raises(ValueError):
        sweep_linear_translation(start, end, fixed, assumption=assumption, motion_evidence=evidence)


@pytest.mark.parametrize("bad", (-1, True, float("nan"), float("inf")))
def test_invalid_numerical_policy(bad):
    with pytest.raises(ValueError):
        sweep(box("m"), box("m"), box("o"), numerical_tolerance_m=bad)


@pytest.mark.parametrize(
    "case", ("delta_overflow", "radius_overflow", "lost_positive_width", "parameter_underflow")
)
def test_unrepresentable_geometry_or_parameter_rejects_cleanly(case):
    start, end, fixed = box("m"), box("m"), box("o")
    if case == "delta_overflow":
        start, end = box("m", (-1e308, 0, 0), (0, 0, 0)), box("m", (1e308, 0, 0), (0, 0, 0))
    elif case == "radius_overflow":
        fixed = box("o", (1e308, 0, 0), (1e308, 1, 1))
    elif case == "lost_positive_width":
        start = box("m", (1, 0, 0), (1e-300,) * 3)
        end = box("m", (2, 0, 0), (1e-300,) * 3)
    elif case == "parameter_underflow":
        start, end = box("m", (0, 0, 0), (0, 0, 0)), box("m", (1e308, 0, 0), (0, 0, 0))
        fixed = box("o", (1e-300, 0, 0), (0, 0, 0))
    with pytest.raises(ValueError):
        sweep(start, end, fixed)


def test_bounded_obstacle_collection_and_all_results_preserved():
    start, end = box("m", (-2, 0, 0)), box("m", (2, 0, 0))
    fixed = (box("one"), box("two", (0, 3, 0)))
    kwargs = {"assumption": LINEAR_TRANSLATION_ASSUMPTION, "motion_evidence": "Synthetic fixture"}
    result = sweep_against_static_boxes(start, end, fixed, **kwargs)
    assert len(result) == 2
    assert result[0].overlap_parameter_interval is not None
    assert result[1].overlap_parameter_interval is None
    assert sweep_against_static_boxes(start, end, (), **kwargs) == ()
    with pytest.raises(ValueError):
        sweep_against_static_boxes(start, end, fixed, max_obstacles=1, **kwargs)
    with pytest.raises(ValueError):
        sweep_against_static_boxes(start, end, (fixed[0], fixed[0]), **kwargs)
    with pytest.raises(ValueError):
        sweep_against_static_boxes(start, end, (), max_obstacles=True, **kwargs)
    with pytest.raises(ValueError):
        sweep_against_static_boxes(
            box("m", (1, 0, 0), (1e-300,) * 3),
            box("m", (2, 0, 0), (1e-300,) * 3),
            (),
            **kwargs,
        )


def test_tracked_synthetic_report_reproduction_and_physical_gates():
    report = json.loads(json.dumps(study.build_study()))
    assert report == json.loads((ROOT / "hardware/cad/thor-swept-box-study-v1.json").read_bytes())
    assert report["case_count"] == 7
    witness = report["cases"][0]
    assert witness["endpoint_proxy_relations"] == ["no_proxy_overlap"] * 2
    assert witness["sweep_result"]["overlap_parameter_interval"] == [5 / 16, 11 / 16]
    assert report["actual_robot_sweep_cases"] == []
    assert report["robot_swept_clearance"] is None
    assert report["physical_collision_free"] is None
    assert not any(report["qualification"].values())


def test_existing_output_is_preserved(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_bytes(b"preserved")
    assert study.main(["--output", str(path)]) == 2
    assert path.read_bytes() == b"preserved"
