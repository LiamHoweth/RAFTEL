"""Analytic offline path derivatives, bounds and continuity, without motion."""

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
from raftel_arm01.kinematics.thor_trajectory import (
    PEAK_QUINTIC_ACCELERATION,
    PEAK_QUINTIC_VELOCITY,
    QuinticSegment,
    TimedJointPath,
    TimedJointState,
    plan_quintic_path,
)

ROOT = Path(__file__).parents[1]


@pytest.fixture
def study():
    baseline = load_constraints(ROOT / "config/thor-constraints-v1.json")
    return ConstraintSet(
        "synthetic-rate-study-v1",
        tuple(
            replace(
                joint,
                study=replace(
                    joint.study,
                    max_velocity_rad_s=0.1,
                    max_acceleration_rad_s2=0.2,
                    evidence="Synthetic numerical fixture: .1rad/s and .2rad/s2; "
                    "not physical limits",
                ),
            )
            for joint in baseline.joints
        ),
    )


def test_baseline_unknown_acceleration_fails_instead_of_guessing():
    baseline = load_constraints(ROOT / "config/thor-constraints-v1.json")
    with pytest.raises(ValueError, match="explicit study velocity and acceleration"):
        plan_quintic_path(((0,) * 6, (0.1,) * 6), baseline)


def test_closed_form_endpoints_midpoint_and_derivative_extrema():
    segment = QuinticSegment((0,) * 6, (1, 0, -2, 0, 0, 0), 2)
    start, end = segment.sample(0), segment.sample(2)
    assert start.joints_rad == (0,) * 6
    assert end.joints_rad == (1, 0, -2, 0, 0, 0)
    assert start.velocities_rad_s == end.velocities_rad_s == (0,) * 6
    assert start.accelerations_rad_s2 == end.accelerations_rad_s2 == (0,) * 6
    middle = segment.sample(1)
    assert middle.joints_rad == (0.5, 0, -1, 0, 0, 0)
    assert middle.velocities_rad_s == (
        PEAK_QUINTIC_VELOCITY / 2,
        0,
        -PEAK_QUINTIC_VELOCITY,
        0,
        0,
        0,
    )
    assert middle.accelerations_rad_s2 == (0,) * 6
    a, b = segment.peak_rates()
    assert a == (PEAK_QUINTIC_VELOCITY / 2, 0, PEAK_QUINTIC_VELOCITY, 0, 0, 0)
    assert b == (PEAK_QUINTIC_ACCELERATION / 4, 0, PEAK_QUINTIC_ACCELERATION / 2, 0, 0, 0)
    for u in ((3 - math.sqrt(3)) / 6, (3 + math.sqrt(3)) / 6):
        at = segment.sample(2 * u)
        assert abs(at.accelerations_rad_s2[0]) == pytest.approx(b[0])


def test_analytic_derivatives_match_central_differences():
    rng = random.Random(673)
    for _ in range(100):
        start = tuple(rng.uniform(-1, 1) for _ in range(6))
        end = tuple(rng.uniform(-1, 1) for _ in range(6))
        duration = rng.uniform(0.5, 20)
        segment = QuinticSegment(start, end, duration)
        time = duration * rng.uniform(0.05, 0.95)
        h = duration * 1e-5
        a, b, c = segment.sample(time - h), segment.sample(time), segment.sample(time + h)
        numeric_velocity = tuple(
            (z - x) / (2 * h) for x, z in zip(a.joints_rad, c.joints_rad, strict=True)
        )
        numeric_acceleration = tuple(
            (z - x) / (2 * h) for x, z in zip(a.velocities_rad_s, c.velocities_rad_s, strict=True)
        )
        assert b.velocities_rad_s == pytest.approx(numeric_velocity, abs=3e-9)
        assert b.accelerations_rad_s2 == pytest.approx(numeric_acceleration, abs=5e-8)


def test_duration_is_computed_from_both_velocity_and_acceleration(study):
    target = (0.8, 0, 0, 0, 0, 0)
    path = plan_quintic_path(((0,) * 6, target), study)
    expected = max(
        PEAK_QUINTIC_VELOCITY * 0.8 / 0.1, math.sqrt(PEAK_QUINTIC_ACCELERATION * 0.8 / 0.2)
    )
    assert path.duration_s == pytest.approx(expected)
    rates = path.segments[0].peak_rates()
    assert max(rates[0]) <= 0.1 * (1 + 1e-12)
    assert max(rates[1]) <= 0.2 * (1 + 1e-12)
    small = plan_quintic_path(((0,) * 6, (0.001, 0, 0, 0, 0, 0)), study)
    expected = math.sqrt(PEAK_QUINTIC_ACCELERATION * 0.001 / 0.2)
    assert small.duration_s == pytest.approx(expected)


def test_c2_path_boundary_and_uniform_endpoint(study):
    waypoints = ((0,) * 6, (0.1, -0.2, 0.3, -0.4, 0.5, -0.6), (-0.2, 0.1, 0, 0.2, -0.1, 0.3))
    path = plan_quintic_path(waypoints, study)
    boundary = path.segments[0].duration_s
    at = path.sample(boundary)
    assert at.joints_rad == waypoints[1]
    assert at.velocities_rad_s == at.accelerations_rad_s2 == (0,) * 6
    left, right = path.sample(boundary - 1e-6), path.sample(boundary + 1e-6)
    assert left.joints_rad == pytest.approx(right.joints_rad, abs=1e-12)
    assert left.velocities_rad_s == pytest.approx(right.velocities_rad_s, abs=1e-12)
    assert left.accelerations_rad_s2 == pytest.approx(right.accelerations_rad_s2, abs=1e-6)
    sampled = path.sample_uniform(0.1)
    assert sampled[0].time_s == 0
    assert sampled[-1].time_s == path.duration_s
    assert sampled[-1].joints_rad == waypoints[-1]
    assert all(b.time_s > a.time_s for a, b in zip(sampled, sampled[1:], strict=False))
    assert "not_collision_dynamics_or_hardware" in path.validation_class


def test_seeded_whole_path_scalar_bounds(study):
    rng = random.Random(125)
    for _ in range(25):
        waypoints = tuple(tuple(rng.uniform(-1.4, 1.4) for _ in range(6)) for _ in range(4))
        path = plan_quintic_path(waypoints, study)
        for sample in path.sample_uniform(0.5):
            assert not validate_joint_state(
                sample.joints_rad,
                study,
                velocities_rad_s=sample.velocities_rad_s,
                accelerations_rad_s2=sample.accelerations_rad_s2,
            )


def test_dense_samples_do_not_exceed_analytic_maxima():
    segment = QuinticSegment(
        (-0.2, 0.3, 0.4, -0.5, 0.6, -0.7), (0.7, -0.6, 0.5, -0.4, 0.3, -0.2), 1.7
    )
    velocities, accelerations = segment.peak_rates()
    for i in range(1001):
        sample = segment.sample(segment.duration_s * i / 1000)
        assert all(
            abs(v) <= limit * (1 + 1e-12)
            for v, limit in zip(sample.velocities_rad_s, velocities, strict=True)
        )
        assert all(
            abs(a) <= limit * (1 + 1e-12)
            for a, limit in zip(sample.accelerations_rad_s2, accelerations, strict=True)
        )


def test_endpoint_position_roundoff_and_stationary_segments(study):
    low = tuple(bound.lower_rad for bound in study.bounds())
    high = tuple(bound.upper_rad for bound in study.bounds())
    path = plan_quintic_path((low, high, high), study)
    first = path.segments[0]
    for t in (
        0,
        math.nextafter(0, 1),
        first.duration_s / 2,
        math.nextafter(first.duration_s, 0),
        first.duration_s,
    ):
        assert not validate_joint_state(first.sample(t).joints_rad, study)
    stationary = path.segments[1]
    assert stationary.duration_s == pytest.approx(0.01)
    assert stationary.peak_rates() == ((0,) * 6, (0,) * 6)
    assert stationary.sample(0.005).joints_rad == high


def test_requested_duration_rate_violation_and_duration_budget(study):
    waypoints = ((0,) * 6, (0.1,) * 6)
    with pytest.raises(ValueError, match="analytic velocity or acceleration"):
        plan_quintic_path(waypoints, study, segment_durations_s=(0.1,))
    with pytest.raises(ValueError, match="duration budget"):
        plan_quintic_path(waypoints, study, max_total_duration_s=0.5)
    with pytest.raises(ValueError, match="one requested duration"):
        plan_quintic_path(waypoints, study, segment_durations_s=())
    with pytest.raises(ValueError, match="below minimum"):
        plan_quintic_path(waypoints, study, segment_durations_s=(0,))
    with pytest.raises(ValueError, match="position limits"):
        plan_quintic_path(((0,) * 6, (4, 0, 0, 0, 0, 0)), study)


@pytest.mark.parametrize("time", [-0.1, float("nan"), float("inf"), True, 10])
def test_invalid_segment_sample_time(time):
    with pytest.raises(ValueError):
        QuinticSegment((0,) * 6, (0.1,) * 6, 1).sample(time)


def test_invalid_path_continuity_sampling_and_numeric_inputs(study):
    a = QuinticSegment((0,) * 6, (0.1,) * 6, 1)
    b = QuinticSegment((0.2,) * 6, (0,) * 6, 1)
    with pytest.raises(ValueError, match="exact waypoint"):
        TimedJointPath((a, b), "fixture", ("fixture",) * 6)
    path = plan_quintic_path(((0,) * 6, (0.1,) * 6), study)
    for time in (-1, path.duration_s + 1, float("nan")):
        with pytest.raises(ValueError):
            path.sample(time)
    with pytest.raises(ValueError, match="sample budget"):
        path.sample_uniform(1e-9, max_samples=10)
    with pytest.raises(ValueError):
        path.sample_uniform(0)
    for duration in (0, -1, True, float("inf"), 1e-308):
        with pytest.raises(ValueError):
            QuinticSegment((0,) * 6, (1,) * 6, duration)
    with pytest.raises(ValueError):
        TimedJointState(0, (0,) * 6, (True,) * 6, (0,) * 6)
    with pytest.raises(ValueError):
        plan_quintic_path(((0,) * 6,), study)


def test_many_segment_timeline_and_unresolvable_duration_rejection():
    stationary = QuinticSegment((0,) * 6, (0,) * 6, 0.1)
    path = TimedJointPath((stationary,) * 999, "timeline-fixture", ("synthetic fixture",) * 6)
    for i in range(1, 999):
        boundary = math.fsum([0.1] * i)
        assert path.sample(boundary).joints_rad == (0,) * 6
    assert path.sample(math.nextafter(path.duration_s, 0)).joints_rad == (0,) * 6
    with pytest.raises(ValueError, match="cannot be resolved"):
        TimedJointPath(
            (QuinticSegment((0,) * 6, (0,) * 6, 1e100), stationary),
            "invalid-timeline",
            ("fixture",) * 6,
        )


def test_uniform_sampling_keeps_start_when_time_ratio_underflows():
    segment = QuinticSegment((0,) * 6, (0,) * 6, 1e-300)
    path = TimedJointPath((segment,), "tiny-duration-fixture", ("explicit synthetic fixture",) * 6)
    samples = path.sample_uniform(1e308)
    assert [sample.time_s for sample in samples] == [0, 1e-300]


def test_uniform_sampling_has_one_endpoint_when_ratio_rounds_up():
    duration = 14.449699625914022
    period = 0.23305967138571002
    segment = QuinticSegment((0,) * 6, (0,) * 6, duration)
    path = TimedJointPath((segment,), "rounded-ratio-fixture", ("explicit synthetic fixture",) * 6)
    samples = path.sample_uniform(period)
    assert samples[0].time_s == 0
    assert samples[-1].time_s == duration
    assert all(a.time_s < b.time_s for a, b in zip(samples, samples[1:], strict=False))
    assert sum(sample.time_s == duration for sample in samples) == 1


def rate_study_fixture():
    return {
        "schema_version": 1,
        "revision": "synthetic-cli-study-v1",
        "units": {"velocity": "rad/s", "acceleration": "rad/s^2"},
        "evidence_class": "synthetic",
        "evidence": "Numerical test fixture; no physical speed or acceleration qualification",
        "velocity_limits_rad_s": [0.1] * 6,
        "acceleration_limits_rad_s2": [0.2] * 6,
    }


def trajectory_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "tools/thor_trajectory_study.py"), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_trajectory_cli_explicit_rate_study_reproduction_and_evidence_preservation(tmp_path):
    rates = tmp_path / "rates.json"
    rates.write_text(json.dumps(rate_study_fixture()), encoding="utf-8")
    first, second = tmp_path / "one.json", tmp_path / "two.json"
    for output in (first, second):
        result = trajectory_cli("--rate-study", rates, "--output", output)
        assert result.returncode == 0, result.stderr
    assert first.read_bytes() == second.read_bytes()
    report = json.loads(first.read_text())
    assert report["rate_study"]["evidence_class"] == "synthetic"
    assert len(report["segments"]) == 2
    assert report["samples"][-1]["time_s"] == report["duration_s"]
    before = first.read_bytes()
    result = trajectory_cli("--rate-study", rates, "--output", first)
    assert result.returncode == 2
    assert first.read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("units", {"velocity": "deg/s", "acceleration": "rad/s^2"}),
        ("evidence_class", "physical"),
        ("evidence", ""),
        ("acceleration_limits_rad_s2", [None] * 6),
        ("velocity_limits_rad_s", [0] * 6),
    ],
)
def test_trajectory_cli_invalid_study_rejects(tmp_path, field, value):
    data = rate_study_fixture()
    data[field] = value
    rates = tmp_path / "bad-rates.json"
    rates.write_text(json.dumps(data), encoding="utf-8")
    result = trajectory_cli("--rate-study", rates)
    assert result.returncode == 2


def test_trajectory_cli_required_rates_and_sample_budget(tmp_path):
    assert trajectory_cli().returncode == 2
    rates = tmp_path / "rates.json"
    rates.write_text(json.dumps(rate_study_fixture()), encoding="utf-8")
    result = trajectory_cli(
        "--rate-study", rates, "--sample-period-s", 0.000001, "--max-samples", 10
    )
    assert result.returncode == 2 and "sample budget" in result.stderr
