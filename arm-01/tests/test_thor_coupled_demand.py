"""Independent constant-map derivative, extrema, power and T1 integration checks."""

import itertools
import json
import random
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from raftel_arm01.control.thor_coupled_demand import (
    CoupledDemandScenario,
    project_motion,
    project_rate_boxes,
)
from raftel_arm01.kinematics.thor_constraints import (
    ConstraintSet,
    JointBounds,
    JointConstraint,
    load_constraints,
)
from raftel_arm01.kinematics.thor_trajectory import TimedJointState, plan_quintic_path
from raftel_arm01.kinematics.thor_transmission import ElbowTransmission, WristDifferential


def constraints():
    velocities = (0.5, 0.2, 0.3, 0.4, 0.6, 0.7)
    accelerations = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
    return ConstraintSet(
        "synthetic-rate-study-v1",
        tuple(
            JointConstraint(
                f"joint_{i + 1}",
                None,
                JointBounds(-3, 3, velocities[i], accelerations[i], "synthetic rate box fixture"),
                None,
            )
            for i in range(6)
        ),
    )


def scenario(**updates):
    values = {
        "revision": "synthetic-transmission-study-v1",
        "evidence_class": "synthetic",
        "evidence": "explicit synthetic local constant-ratio fixture, not calibrated",
        "elbow": ElbowTransmission(0.01, 0.05, 5, 4, 1, -1),
        "wrist": WristDifferential(2, 1, -4, 3, "synthetic mechanism fixture"),
    }
    return CoupledDemandScenario(**(values | updates))


def state():
    return TimedJointState(
        0.5,
        (0.1, -0.2, 0.3, -0.4, 0.5, -0.6),
        (0.1, -0.1, 0.2, -0.2, 0.3, -0.4),
        (0.1, -0.2, 0.3, -0.4, 0.5, -0.6),
    )


def test_source_channels_and_conditional_rotors_remain_separate():
    output = project_motion(state(), constraints(), scenario=scenario())
    assert output.source_continuous.coordinate_names == ("A", "B", "C", "D", "X", "Y", "Z")
    assert output.source_continuous.velocities_rad_s == pytest.approx(
        (0.1, 0.1, 0.1, -0.2, -0.2, -1.1, -0.5)
    )
    assert output.conditional_elbow_rotors.velocities_rad_s == pytest.approx((-0.4, -0.4, -5.5))
    assert output.conditional_wrist_rotors.velocities_rad_s == pytest.approx((2.0, 3.3))
    assert "not_source" in output.conditional_elbow_rotors.coordinate_interpretation
    assert output.evidence_class == "conditional_offline_coupled_demand_not_actuator_capacity"
    assert not output.complete_actuator_capacity


def test_simultaneous_shoulder_elbow_and_wrist_rates_include_all_carrier_terms():
    source = state()
    changed = replace(source, velocities_rad_s=(0, 0.1, 0, 0, 0, 0))
    model = scenario()
    result = project_motion(changed, constraints(), scenario=model)
    # Source D remains zero; conditional remote elbow rotor moves with shoulder.
    assert result.source_continuous.velocities_rad_s[3] == 0
    assert result.conditional_elbow_rotors.velocities_rad_s[2] == pytest.approx(0.5)


def test_seeded_derivatives_match_perturbed_coordinates_and_rates():
    rng = random.Random(510)
    for _ in range(100):
        model = scenario(
            elbow=ElbowTransmission(
                0.01,
                rng.uniform(0.02, 0.08),
                rng.uniform(2, 8),
                4,
                rng.uniform(-1.5, 1.5),
                rng.choice((-1, 1)),
            ),
            wrist=WristDifferential(
                rng.uniform(0.5, 3),
                rng.choice((-1, 1)),
                rng.choice((-1, 1)) * rng.uniform(0.5, 5),
                rng.choice((-1, 1)) * rng.uniform(0.5, 5),
                "synthetic",
            ),
        )
        q = tuple(rng.uniform(-1, 1) for _ in range(6))
        qd = tuple(rng.uniform(-0.1, 0.1) for _ in range(6))
        qdd = tuple(rng.uniform(-0.1, 0.1) for _ in range(6))
        epsilon = 1e-5
        before = TimedJointState(
            0,
            tuple(q[i] - epsilon * qd[i] + epsilon**2 * qdd[i] / 2 for i in range(6)),
            tuple(qd[i] - epsilon * qdd[i] for i in range(6)),
            qdd,
        )
        middle = TimedJointState(epsilon, q, qd, qdd)
        after = TimedJointState(
            2 * epsilon,
            tuple(q[i] + epsilon * qd[i] + epsilon**2 * qdd[i] / 2 for i in range(6)),
            tuple(qd[i] + epsilon * qdd[i] for i in range(6)),
            qdd,
        )
        outputs = [
            project_motion(value, constraints(), scenario=model)
            for value in (before, middle, after)
        ]
        for field in ("source_continuous", "conditional_elbow_rotors", "conditional_wrist_rotors"):
            a, b, c = (getattr(result, field) for result in outputs)
            velocities = tuple(
                (v1 - v0) / (2 * epsilon)
                for v0, v1 in zip(a.coordinates_rad, c.coordinates_rad, strict=True)
            )
            accelerations = tuple(
                (v1 - v0) / (2 * epsilon)
                for v0, v1 in zip(a.velocities_rad_s, c.velocities_rad_s, strict=True)
            )
            assert b.velocities_rad_s == pytest.approx(velocities, abs=2e-8)
            assert b.accelerations_rad_s2 == pytest.approx(accelerations, abs=2e-8)


def test_conditional_rotor_and_source_virtual_power_against_explicit_equations():
    rng = random.Random(915)
    model, motion = scenario(), state()
    result = project_motion(motion, constraints(), scenario=model)
    for _ in range(100):
        tb, tc, te, tm, tp = (rng.uniform(-2, 2) for _ in range(5))
        elbow, wrist = model.elbow, model.wrist
        rotor = sum(
            v * t
            for v, t in zip(
                result.conditional_elbow_rotors.velocities_rad_s, (tb, tc, te), strict=True
            )
        ) + sum(
            v * t
            for v, t in zip(result.conditional_wrist_rotors.velocities_rad_s, (tm, tp), strict=True)
        )
        qd = motion.velocities_rad_s
        joint = (
            qd[1]
            * (
                elbow.shoulder_branch_ratio * (tb + tc)
                + elbow.elbow_gearbox_ratio * elbow.carrier_coupling * te
            )
            + qd[2] * elbow.elbow_gearbox_ratio * elbow.belt_sign * elbow.belt_ratio * te
            + qd[4] * (wrist.negative_y_rotor_scale * tm + wrist.positive_y_rotor_scale * tp)
            + qd[5]
            * wrist.handedness
            * wrist.bevel_ratio
            * (wrist.negative_y_rotor_scale * tm - wrist.positive_y_rotor_scale * tp)
        )
        assert rotor == pytest.approx(joint, abs=1e-12)
        a, b, c, d, x, y, z = (rng.uniform(-2, 2) for _ in range(7))
        channel_power = sum(
            v * t
            for v, t in zip(
                result.source_continuous.velocities_rad_s, (a, b, c, d, x, y, z), strict=True
            )
        )
        source_joint_power = sum(
            v * t for v, t in zip(qd, (a, -b - c, -d, x, -y + z, 2 * y + 2 * z), strict=True)
        )
        assert channel_power == pytest.approx(source_joint_power, abs=1e-12)


def test_exact_linear_box_extrema_match_all_64_corners_and_have_witnesses():
    result = project_rate_boxes(constraints(), scenario=scenario())
    for field in ("source_continuous", "conditional_elbow_rotors", "conditional_wrist_rotors"):
        box = getattr(result, field)
        for limits, extrema in (
            (result.joint_velocity_abs_limits_rad_s, box.velocity_extrema_rad_s),
            (result.joint_acceleration_abs_limits_rad_s2, box.acceleration_extrema_rad_s2),
        ):
            corners = [
                tuple(sign * bound for sign, bound in zip(signs, limits, strict=True))
                for signs in itertools.product((-1, 1), repeat=6)
            ]
            for row, extremum in zip(box.constant_jacobian, extrema, strict=True):
                values = [
                    sum(a * b for a, b in zip(row, corner, strict=True)) for corner in corners
                ]
                assert extremum.minimum == pytest.approx(min(values))
                assert extremum.maximum == pytest.approx(max(values))
                assert sum(
                    a * b for a, b in zip(row, extremum.maximizing_joint_vector, strict=True)
                ) == pytest.approx(extremum.maximum)
                assert sum(
                    a * b for a, b in zip(row, extremum.minimizing_joint_vector, strict=True)
                ) == pytest.approx(extremum.minimum)
    assert not result.complete_actuator_capacity
    assert "different_rows_have_different_witness_states" in result.extrema_scope


def test_baseline_unknown_accelerations_rejects_both_projection_paths():
    root = Path(__file__).resolve().parents[1]
    baseline = load_constraints(root / "config/thor-constraints-v1.json")
    for action in (
        lambda: project_rate_boxes(baseline, scenario=scenario()),
        lambda: project_motion(state(), baseline, scenario=scenario()),
    ):
        with pytest.raises(ValueError, match="acceleration"):
            action()


def test_t1_path_samples_reuse_the_existing_contract_and_fit_declared_boxes():
    bounds, model = constraints(), scenario()
    path = plan_quintic_path(((0,) * 6, (0.2, -0.3, 0.4, -0.5, 0.6, -0.7)), bounds)
    boxes = project_rate_boxes(bounds, scenario=model)
    for sample in path.sample_uniform(0.2):
        demand = project_motion(sample, bounds, scenario=model)
        for field in ("source_continuous", "conditional_elbow_rotors", "conditional_wrist_rotors"):
            motion, box = getattr(demand, field), getattr(boxes, field)
            for value, interval in zip(
                motion.velocities_rad_s, box.velocity_extrema_rad_s, strict=True
            ):
                assert interval.minimum - 1e-12 <= value <= interval.maximum + 1e-12
            for value, interval in zip(
                motion.accelerations_rad_s2, box.acceleration_extrema_rad_s2, strict=True
            ):
                assert interval.minimum - 1e-12 <= value <= interval.maximum + 1e-12


@pytest.mark.parametrize("field", ["joints_rad", "velocities_rad_s", "accelerations_rad_s2"])
def test_study_position_rate_violations_reject(field):
    value = replace(state(), **{field: (10,) * 6})
    with pytest.raises(ValueError, match="violates"):
        project_motion(value, constraints(), scenario=scenario())


def test_scenario_requires_explicit_assumed_or_synthetic_mechanism_provenance():
    for update in (
        {"evidence": ""},
        {"revision": ""},
        {"evidence_class": "physical"},
        {"elbow": None},
    ):
        with pytest.raises(ValueError):
            scenario(**update)
    with pytest.raises(ValueError, match="TimedJointState"):
        project_motion(None, constraints(), scenario=scenario())


def test_overflow_in_box_projection_is_rejected():
    model = scenario(wrist=WristDifferential(1e308, 1, 1, 1, "extreme synthetic fixture"))
    # Unit-basis coefficients are finite, but combining the 6th input with this
    # deliberately huge study bound would overflow; it must not report infinity.
    bounds = constraints()
    updated = replace(
        bounds.joints[5], study=replace(bounds.joints[5].study, max_velocity_rad_s=10)
    )
    bounds = replace(bounds, joints=bounds.joints[:5] + (updated,))
    with pytest.raises(ValueError, match="finite"):
        project_rate_boxes(bounds, scenario=model)


def cli_inputs(tmp_path):
    rate_path, model_path = tmp_path / "rates.json", tmp_path / "mechanism.json"
    rate = {
        "schema_version": 1,
        "revision": "test-synthetic-rate-study",
        "units": {"velocity": "rad/s", "acceleration": "rad/s^2"},
        "evidence_class": "synthetic",
        "evidence": "test-only numerical scenario, not qualified hardware rates",
        "velocity_limits_rad_s": [0.1] * 6,
        "acceleration_limits_rad_s2": [0.2] * 6,
    }
    mechanism = {
        "schema_version": 1,
        "revision": "test-synthetic-transmissions",
        "evidence_class": "synthetic",
        "evidence": "test-only constant mechanism fixture",
        "elbow": {
            "driver_radius_m": 0.01,
            "drum_radius_m": 0.05,
            "elbow_gearbox_ratio": 5,
            "shoulder_branch_ratio": 4,
            "carrier_coupling": 1,
            "belt_sign": -1,
        },
        "wrist": {
            "bevel_ratio": 2,
            "handedness": 1,
            "negative_y_rotor_scale": -4,
            "positive_y_rotor_scale": 3,
        },
    }
    rate_path.write_text(json.dumps(rate))
    model_path.write_text(json.dumps(mechanism))
    return rate_path, model_path


def test_cli_reuses_t1_rate_input_and_reports_partial_demands_and_input_hashes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    rate_path, model_path = cli_inputs(tmp_path)
    command = [
        sys.executable,
        str(root / "tools/thor_coupled_demand.py"),
        "--rate-study",
        str(rate_path),
        "--transmission-study",
        str(model_path),
    ]
    output = subprocess.run(command, capture_output=True, text=True, check=True)
    report = json.loads(output.stdout)
    assert report["complete_capacity_margin"] is None
    assert report["rate_boxes"]["complete_actuator_capacity"] is False
    assert report["trajectory"]["sampled_demands"]
    assert report["transmission_study"]["evidence_class"] == "synthetic"
    assert len(report["inputs"]["transmission_study_sha256"]) == 64
    repeated = subprocess.run(command, capture_output=True, text=True, check=True)
    assert repeated.stdout == output.stdout
    box_only = subprocess.run(command + ["--box-only"], capture_output=True, text=True, check=True)
    assert json.loads(box_only.stdout)["trajectory"] is None


def test_cli_missing_unknown_or_physical_scenario_fields_fail_and_preserve_evidence(tmp_path):
    root = Path(__file__).resolve().parents[1]
    rate_path, model_path = cli_inputs(tmp_path)
    command = [
        sys.executable,
        str(root / "tools/thor_coupled_demand.py"),
        "--rate-study",
        str(rate_path),
        "--transmission-study",
        str(model_path),
    ]
    original = model_path.read_text()
    for field, value in (("evidence_class", "physical"), ("elbow", {}), ("wrist", None)):
        document = json.loads(original)
        document[field] = value
        model_path.write_text(json.dumps(document))
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 2
        assert not result.stdout
    model_path.write_text(original)
    output = tmp_path / "existing.json"
    output.write_text("prior evidence")
    result = subprocess.run(command + ["--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 2
    assert output.read_text() == "prior evidence"
    rates = json.loads(rate_path.read_text())
    rates["acceleration_limits_rad_s2"] = [None] * 6
    rate_path.write_text(json.dumps(rates))
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert not result.stdout
