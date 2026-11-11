"""Nominal local FK-to-IK-to-FK and bounded failure fixtures."""

import json
import math
import random
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from raftel_arm01.kinematics.thor_constraints import (
    ConstraintSet,
    load_constraints,
    validate_joint_state,
)
from raftel_arm01.kinematics.thor_frames import IDENTITY, transform_point
from raftel_arm01.kinematics.thor_ik import IKOptions, rotation_error, solve_pose_ik
from raftel_arm01.kinematics.thor_jacobian import spatial_jacobian
from raftel_arm01.kinematics.thor_model import forward_kinematics

ROOT = Path(__file__).parents[1]


@pytest.fixture
def constraints():
    return load_constraints(ROOT / "config/thor-constraints-v1.json")


def axis_angle_pose(axis, angle):
    x, y, z = axis
    c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0),
        (0, 0, 0, 1),
    )


@pytest.mark.parametrize(
    "angle", [0, 1e-12, 0.3, math.pi - 1e-8, math.pi, math.pi + 1e-8, 2 * math.pi - 0.2]
)
@pytest.mark.parametrize("axis", [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1 / math.sqrt(3),) * 3])
def test_so3_log_small_and_half_turns(axis, angle):
    actual = rotation_error(axis_angle_pose(axis, angle), IDENTITY)
    expected = angle if angle <= math.pi else angle - 2 * math.pi
    assert math.hypot(*actual) == pytest.approx(abs(expected), abs=1e-9)
    if abs(angle - math.pi) > 1e-10:
        assert actual == pytest.approx(tuple(component * expected for component in axis), abs=1e-9)


@pytest.mark.parametrize("target", ["link_6", "gripper_base", "gripper_mid_point"])
def test_seeded_nearby_pose_round_trips(constraints, target):
    rng = random.Random(2026)
    options = IKOptions(max_seconds=5)
    for _ in range(45):
        q = tuple(rng.uniform(-1.3, 1.3) for _ in range(6))
        desired = forward_kinematics(q, target)
        seed = tuple(v + rng.uniform(-0.08, 0.08) for v in q)
        result = solve_pose_ik(desired, seed, constraints, target=target, options=options)
        assert result.converged, result
        assert result.reason == "converged"
        assert result.iterations <= options.max_iterations
        assert not validate_joint_state(result.joints_rad, constraints)
        actual = forward_kinematics(result.joints_rad, target)
        assert (
            math.hypot(*(desired[i][3] - actual[i][3] for i in range(3)))
            <= options.position_tolerance_m
        )
        assert math.hypot(*rotation_error(desired, actual)) <= options.orientation_tolerance_rad
        assert "not_collision_or_hardware" in result.validation_class


def test_seeded_zero_pose_and_mixed_pose_from_singular_seed(constraints):
    for q, seed in [
        ((0,) * 6, (0.01,) * 6),
        ((0.2, -0.6, 0.8, -0.3, 0.5, 0.4), (0,) * 6),
        ((0, 1.570796326795, 0, 0, 0, 0), (0, 1.5, 0.01, 0.01, 0.01, 0.01)),
    ]:
        result = solve_pose_ik(forward_kinematics(q), seed, constraints)
        assert result.converged, result
        assert not validate_joint_state(result.joints_rad, constraints)


def test_already_solved_pose_uses_no_iteration(constraints):
    q = (0.2, -0.3, 0.4, -0.5, 0.6, -0.7)
    result = solve_pose_ik(forward_kinematics(q), q, constraints)
    assert result.converged and result.iterations == 0
    assert result.joints_rad == q


def test_unreachable_rejection_and_inside_bound_local_stall(constraints):
    desired = tuple((*row[:3], 10 if i == 0 else row[3]) for i, row in enumerate(IDENTITY))
    result = solve_pose_ik(desired, (0,) * 6, constraints)
    assert not result.converged and result.reason == "outside_nominal_reach_bound"
    assert result.iterations == 0
    # A zero first-order direction at the straight seed is a local failure,
    # despite being inside the triangle-inequality radius bound.
    desired = ((1, 0, 0, 0.001), (0, 1, 0, 0), (0, 0, 1, 0.56), (0, 0, 0, 1))
    result = solve_pose_ik(desired, (0,) * 6, constraints)
    assert not result.converged and result.reason == "stalled"


def test_iteration_and_time_bounds(constraints, monkeypatch):
    target = forward_kinematics((0.2, -0.6, 0.8, -0.3, 0.5, 0.4))
    result = solve_pose_ik(target, (0,) * 6, constraints, options=IKOptions(max_iterations=1))
    assert not result.converged and result.reason == "iteration_limit"
    assert result.iterations == 1
    clock = iter((0, 3))
    monkeypatch.setattr("raftel_arm01.kinematics.thor_ik.time.monotonic", lambda: next(clock))
    result = solve_pose_ik(target, (0,) * 6, constraints)
    assert not result.converged and result.reason == "time_limit"


def test_limit_projection_never_escapes_study_box(constraints):
    narrow = ConstraintSet(
        "narrow-synthetic-box",
        tuple(
            replace(joint, study=replace(joint.study, lower_rad=-0.01, upper_rad=0.01))
            for joint in constraints.joints
        ),
    )
    target = forward_kinematics((0, 0.5, 0, 0, 0, 0))
    result = solve_pose_ik(target, (0,) * 6, narrow)
    assert not result.converged
    assert result.reason in {"stalled_at_limits", "iteration_limit"}
    assert not validate_joint_state(result.joints_rad, narrow)
    assert any(abs(value) == pytest.approx(0.01) for value in result.joints_rad)


def test_differential_virtual_work_against_independent_pose_difference():
    rng = random.Random(733)
    h = 1e-6
    for _ in range(60):
        q = tuple(rng.uniform(-1.3, 1.3) for _ in range(6))
        velocity = tuple(rng.uniform(-0.8, 0.8) for _ in range(6))
        wrench = tuple(rng.uniform(-4, 4) for _ in range(6))
        offset = (0.02, -0.01, 0.03)
        j = spatial_jacobian(q, "gripper_mid_point", point_offset_m=offset)
        efforts = tuple(sum(j[i][k] * wrench[i] for i in range(6)) for k in range(6))
        plus = forward_kinematics(
            tuple(a + h * b for a, b in zip(q, velocity, strict=True)), "gripper_mid_point"
        )
        minus = forward_kinematics(
            tuple(a - h * b for a, b in zip(q, velocity, strict=True)), "gripper_mid_point"
        )
        pplus, pminus = transform_point(plus, offset), transform_point(minus, offset)
        twist = tuple((a - b) / (2 * h) for a, b in zip(pplus, pminus, strict=True)) + tuple(
            v / (2 * h) for v in rotation_error(plus, minus)
        )
        assert sum(a * b for a, b in zip(efforts, velocity, strict=True)) == pytest.approx(
            sum(a * b for a, b in zip(wrench, twist, strict=True)), abs=3e-9
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"max_iterations": 0},
        {"max_iterations": True},
        {"max_seconds": 0},
        {"max_seconds": 31},
        {"damping": 0},
        {"damping": float("nan")},
        {"position_tolerance_m": True},
        {"line_search_steps": 21},
        {"max_joint_step_rad": 4},
    ],
)
def test_invalid_solver_options(changes):
    with pytest.raises(ValueError):
        IKOptions(**changes)


def test_invalid_seed_target_and_constraint_family(constraints):
    target = forward_kinematics((0,) * 6)
    with pytest.raises(ValueError, match="seed violates"):
        solve_pose_ik(target, (3.5, 0, 0, 0, 0, 0), constraints)
    with pytest.raises(ValueError, match="source or study"):
        solve_pose_ik(target, (0,) * 6, constraints, family="calibrated")
    with pytest.raises(ValueError, match="target"):
        solve_pose_ik(target, (0,) * 6, constraints, target="physical_tcp")
    bad = (*target[:3], (0, 0, 0, 0))
    with pytest.raises(ValueError, match="homogeneous"):
        solve_pose_ik(bad, (0,) * 6, constraints)


@pytest.mark.parametrize(
    "changes",
    [{"damping": 1e308}, {"characteristic_length_m": 1e-308}, {"max_joint_step_rad": 1e-20}],
)
def test_numeric_scaling_extremes_reject(changes):
    with pytest.raises(ValueError):
        IKOptions(**changes)


def cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "tools/thor_kinematics.py"), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_offline_cli_deterministic_report_and_preserved_output(tmp_path):
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    for path in (first, second):
        result = cli("--output", path)
        assert result.returncode == 0, result.stderr
    assert first.read_bytes() == second.read_bytes()
    report = json.loads(first.read_text())
    assert report["frame"] == "base_link"
    assert report["source_limit_audit"] is None
    assert len(report["unknown_frame_edges"]) == 5
    before = first.read_bytes()
    result = cli("--output", first)
    assert result.returncode == 2
    assert first.read_bytes() == before


def test_offline_cli_pose_ik_and_wrong_frame_rejection(tmp_path):
    pose = tmp_path / "pose.json"
    content = {
        "frame": "base_link",
        "target": "link_6",
        "pose_matrix_m": forward_kinematics((0.2, -0.6, 0.8, -0.3, 0.5, 0.4)),
    }
    pose.write_text(json.dumps(content), encoding="utf-8")
    result = cli("--joints", 0, 0, 0, 0, 0, 0, "--ik-pose", pose)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["ik"]["converged"]
    assert report["ik"]["constraint_family"] == "study"
    content["frame"] = "arm_base"
    pose.write_text(json.dumps(content), encoding="utf-8")
    result = cli("--ik-pose", pose)
    assert result.returncode == 2
    assert "frame=base_link" in result.stderr


def test_offline_cli_negative_joint_and_stale_source(tmp_path):
    result = cli("--joints", 0, 0, 0, 0, 0, "nan")
    assert result.returncode == 2
    source = tmp_path / "not-pinned.xacro"
    source.write_text("not pinned source", encoding="utf-8")
    result = cli("--source-xacro", source)
    assert result.returncode == 2 and "SHA256" in result.stderr
