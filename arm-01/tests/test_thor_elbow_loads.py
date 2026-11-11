"""Virtual-work and conditional-demand checks, never physical qualification."""

import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "thor_elbow_loads", Path(__file__).parents[1] / "tools" / "thor_elbow_loads.py"
)
loads = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = loads
_SPEC.loader.exec_module(loads)


def model(sign=1, coupling=1):
    return loads.ElbowTransmission(0.01, 0.05, 5, 30, coupling, sign)


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("coupling", [-0.4, 0, 1])
def test_virtual_work_with_random_rates_and_rotor_efforts(sign, coupling):
    transmission = model(sign, coupling)
    rng = random.Random(1968)
    for _ in range(40):
        qdot = [rng.uniform(-3, 3) for _ in range(2)]
        rotor_torque = [rng.uniform(-2, 2) for _ in range(3)]
        rotor_rate = transmission.rotor_coordinates(*qdot)
        joint_torque = transmission.joint_efforts(*rotor_torque)
        joint_power = sum(t * v for t, v in zip(joint_torque, qdot, strict=True))
        rotor_power = sum(t * v for t, v in zip(rotor_torque, rotor_rate, strict=True))
        assert rotor_power == pytest.approx(joint_power, abs=1e-12)


@pytest.mark.parametrize("sign", [-1, 1])
def test_coordinate_inverse_and_finite_difference_carrier_derivative(sign):
    transmission = model(sign)
    assert transmission.joint_coordinates(
        *transmission.rotor_coordinates(0.7, -0.3)
    ) == pytest.approx((0.7, -0.3))
    before = transmission.rotor_coordinates(0.7, -0.3)
    after = transmission.rotor_coordinates(0.700001, -0.3)
    assert [(a - b) / 1e-6 for a, b in zip(after, before, strict=True)] == pytest.approx(
        (30, 30, 5)
    )
    with pytest.raises(ValueError, match="agree"):
        transmission.joint_coordinates(1, 2, 3)


def test_known_carrier_reaction_and_shoulder_redundancy():
    # q3 torque 10 at 5:1 belt requires 2 at elbow output; that also supports
    # 2 of the requested shoulder torque 8. Remaining 6 is carried by B/C.
    transmission = model()
    efforts = transmission.ideal_rotor_efforts(8, 10, 0.25)
    assert efforts["elbow_gearbox_output_nm"] == pytest.approx(2)
    assert efforts["rotor_E_nm"] == pytest.approx(0.4)
    assert efforts["rotor_B_nm"] == pytest.approx(0.05)
    assert efforts["rotor_C_nm"] == pytest.approx(0.15)
    assert transmission.joint_efforts(*(efforts[f"rotor_{axis}_nm"] for axis in "BCE")) == (8, 10)
    assert not efforts["physical_load_sharing_verified"]
    independent = model(coupling=0).ideal_rotor_efforts(8, 10, 0.25)
    assert independent["shoulder_branch_total_joint_nm"] == 8
    # Complete loss of contribution from either shoulder is an explicit scenario.
    for share in (0, 1):
        e = transmission.ideal_rotor_efforts(8, 10, share)
        assert max(e["rotor_B_nm"], e["rotor_C_nm"]) == pytest.approx(0.2)


def test_tangential_tension_requirement_has_no_pretension_or_capacity_claim():
    tension = loads.belt_tension_difference(-2, 0.04)
    assert tension["signed_tension_difference_n"] == -50
    assert tension["symmetric_mid_tension_minimum_for_nonnegative_spans_n"] == 25
    assert not tension["physical_pretension_or_traction_qualified"]


def test_power_direction_efficiency_is_not_static_friction():
    # A 10:1 transmission at 0.8 efficiency, output 4 Nm, 2 rad/s.
    motoring = loads.signed_lossy_input_effort(4, 10, 0.8, "motoring")
    backdrive = loads.signed_lossy_input_effort(4, 10, 0.8, "backdriving")
    assert motoring * 20 * 0.8 == pytest.approx(4 * 2)
    assert backdrive * 20 == pytest.approx(4 * 2 * 0.8)
    assert loads.signed_lossy_input_effort(-4, 10, 0.8, "motoring") == -motoring
    with pytest.raises(ValueError, match="static"):
        loads.signed_lossy_input_effort(4, 10, 0.8, "static")


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), "2", None])
def test_reject_nonfinite_or_non_numeric_inputs(bad):
    with pytest.raises(ValueError):
        model().rotor_coordinates(bad, 0)
    with pytest.raises(ValueError):
        loads.ElbowTransmission(bad, 0.05, 5, 30, 1, 1)
    with pytest.raises(ValueError):
        model().ideal_rotor_efforts(1, 2, bad)


@pytest.mark.parametrize("bad", [0, -1])
def test_positive_geometry_and_ratio_required(bad):
    with pytest.raises(ValueError):
        loads.ElbowTransmission(0.01, bad, 5, 30, 1, 1)
    with pytest.raises(ValueError):
        loads.signed_lossy_input_effort(1, bad, 0.8, "motoring")


def test_sign_share_and_overflow_guards():
    for bad_sign in (True, 0, 1.0, 2):
        with pytest.raises(ValueError):
            loads.ElbowTransmission(0.01, 0.05, 5, 30, 1, bad_sign)
    for share in (-0.1, 1.1):
        with pytest.raises(ValueError):
            model().ideal_rotor_efforts(1, 2, share)
    with pytest.raises(ValueError):
        model().rotor_coordinates(1e308, 1e308)
    assert loads.driver_pitch_radius_m(20, 0.002) == pytest.approx(0.02 / math.pi)


def test_committed_cad_baseline_and_report_provenance():
    study = json.loads(
        (Path(__file__).parents[1] / "hardware/cad/thor-load-study.json").read_text()
    )
    q2, q3 = loads.baseline_joint_loads(study, 0.5, "shoulder_horizontal", 0.2)
    assert q2 == pytest.approx(-5.827992891670454)
    assert q3 == pytest.approx(-2.3423243748226543)
    report = loads.conditional_report(
        study,
        model(),
        0.3,
        fraction=0.5,
        pose="shoulder_horizontal",
        payload_kg=0.2,
        geometry_evidence="Test fixture geometry, not measured Thor pitch radius",
    )
    assert len(report["source_load_study_sha256"]) == 64
    assert not report["motor_capacity_or_safe_payload_qualified"]
    assert not report["constant_effective_pitch_radius_physically_verified"]
    with pytest.raises(ValueError):
        loads.baseline_joint_loads(study, 0.51, "shoulder_horizontal", 0.2)
    with pytest.raises(ValueError):
        loads.conditional_report(
            study,
            model(),
            0.3,
            fraction=0.5,
            pose="shoulder_horizontal",
            payload_kg=0.2,
            geometry_evidence="",
        )


def test_underflowing_belt_ratio_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        loads.ElbowTransmission(1e308, 1e-308, 5, 30, 1, 1)


def test_cli_rejects_existing_output_without_changing_it(tmp_path, monkeypatch, capsys):
    output = tmp_path / "existing.json"
    output.write_text("preserve")
    source = Path(__file__).parents[1] / "hardware/cad/thor-load-study.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "thor_elbow_loads",
            "--load-study",
            str(source),
            "--drum-pitch-radius-mm",
            "37",
            "--carrier-coupling",
            "1",
            "--belt-sign",
            "1",
            "--shoulder-b-fraction",
            "0.5",
            "--geometry-evidence",
            "test assumption",
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as error:
        loads.main()
    assert error.value.code == 2
    assert output.read_text() == "preserve"
    assert "File exists" in capsys.readouterr().err
