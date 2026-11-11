"""Declared transmission algebra; no physical calibration or command approval."""

import math
import random

import pytest

from raftel_arm01.kinematics.thor_drive import joints_to_drive
from raftel_arm01.kinematics.thor_transmission import ElbowTransmission, WristDifferential


def wrist(sign=1):
    return WristDifferential(2, sign, -2, 2, "explicit synthetic signed belt assumption")


def elbow(sign=1, carrier=1):
    return ElbowTransmission(0.02 / math.pi, 0.037, 5.18, 31.08, carrier, sign)


@pytest.mark.parametrize("sign", [-1, 1])
def test_common_axis_pure_fold_carries_both_side_shafts(sign):
    model = wrist(sign)
    assert model.side_angles(0.3, 0) == (0.3, 0.3)
    assert model.joint_angles(0.3, 0.3) == (0.3, 0)


@pytest.mark.parametrize("sign,y_side", [(-1, "negative_y"), (1, "positive_y")])
def test_opposed_source_algebra_requires_side_assignment(sign, y_side):
    model = wrist(sign)
    q5, q6 = 0.3, -0.2
    assert model.opposed_references(q5, q6, y_side) == pytest.approx(
        joints_to_drive((0, 0, 0, 0, q5, q6))[5:]
    )
    other_side = "positive_y" if y_side == "negative_y" else "negative_y"
    assert model.opposed_references(q5, q6, other_side) != pytest.approx(
        joints_to_drive((0, 0, 0, 0, q5, q6))[5:]
    )


@pytest.mark.parametrize("sign", [-1, 1])
def test_wrist_inverse_effort_and_virtual_work_randomized(sign):
    rng = random.Random(391)
    for _ in range(100):
        model = WristDifferential(
            rng.uniform(0.5, 4), sign, -rng.uniform(0.5, 3), rng.uniform(0.5, 3), "test"
        )
        q = tuple(rng.uniform(-2, 2) for _ in range(2))
        assert model.joint_angles(*model.side_angles(*q)) == pytest.approx(q)
        assert model.joints_from_rotors(*model.rotor_angles(*q)) == pytest.approx(q)
        efforts = tuple(rng.uniform(-1, 1) for _ in range(2))
        joints = model.joint_efforts(*efforts)
        assert model.rotor_efforts(*joints) == pytest.approx(efforts)
        velocity = tuple(rng.uniform(-2, 2) for _ in range(2))
        rotor_velocity = model.rotor_angles(*velocity)
        assert sum(a * b for a, b in zip(efforts, rotor_velocity, strict=True)) == pytest.approx(
            sum(a * b for a, b in zip(joints, velocity, strict=True)), abs=1e-12
        )


def test_wrist_finite_difference_motor_velocity_matches_effort_dual():
    model, q, h = wrist(), (0.2, -0.4), 1e-6
    rotor_effort = (0.3, -0.7)
    for index, effort in enumerate(model.joint_efforts(*rotor_effort)):
        plus, minus = list(q), list(q)
        plus[index] += h
        minus[index] -= h
        derivative = tuple(
            (a - b) / (2 * h)
            for a, b in zip(model.rotor_angles(*plus), model.rotor_angles(*minus), strict=True)
        )
        assert sum(a * b for a, b in zip(rotor_effort, derivative, strict=True)) == pytest.approx(
            effort, abs=1e-9
        )


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("carrier", [0, 1, -0.4])
def test_elbow_proxy_inverse_and_carrier_compensation(sign, carrier):
    model = elbow(sign, carrier)
    q2, q3 = 0.6, -0.3
    proxy = model.elbow_proxy_coordinate(q2, q3)
    assert proxy == pytest.approx(q3 + carrier * q2 / (sign * model.belt_ratio))
    assert model.relative_elbow_from_proxy(q2, proxy) == pytest.approx(q3)
    # A fixed normalized uncoupled drive coordinate does not hold q3 when c != 0.
    shift = model.relative_elbow_from_proxy(q2 + 0.2, proxy) - q3
    assert shift == pytest.approx(-carrier * 0.2 / (sign * model.belt_ratio))
    # Proxy is normalized output angle, not a source address or raw rotor angle.
    assert model.rotor_coordinates(q2, q3)[2] == pytest.approx(
        model.elbow_gearbox_ratio * sign * model.belt_ratio * proxy
    )


def test_elbow_proxy_example_illustrates_uncompensated_relative_error():
    model = elbow()
    error = model.relative_elbow_from_proxy(math.pi / 2, 0)
    assert math.degrees(error) == pytest.approx(-15.485345804105948)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "1", None])
def test_bad_runtime_values_rejected(bad):
    for operation in (
        lambda: wrist().side_angles(bad, 0),
        lambda: wrist().rotor_angles(0, bad),
        lambda: wrist().joint_angles(bad, 0),
        lambda: wrist().joint_efforts(0, bad),
        lambda: wrist().rotor_efforts(bad, 0),
        lambda: elbow().elbow_proxy_coordinate(bad, 0),
        lambda: elbow().relative_elbow_from_proxy(0, bad),
    ):
        with pytest.raises(ValueError, match="finite real"):
            operation()


def test_degenerate_or_unproven_declarations_rejected():
    for parameters in (
        (0, 1, 2, 2, "test"),
        (2, 0, 2, 2, "test"),
        (2, True, 2, 2, "test"),
        (2, 1, 0, 2, "test"),
        (2, 1, 2, 2, ""),
        (1e-300, 1, 1e-300, 2, "test"),
    ):
        with pytest.raises(ValueError):
            WristDifferential(*parameters)
    with pytest.raises(ValueError, match="y_side"):
        wrist().opposed_references(0, 0, "unknown")
    with pytest.raises(ValueError):
        ElbowTransmission(1, 1e-300, 1e-300, 1, 1, 1)


def test_overflow_is_rejected_and_valid_large_inverse_avoids_intermediate_sum():
    assert wrist().joint_angles(1e308, 1e308) == (1e308, 0)
    with pytest.raises(ValueError, match="finite real"):
        wrist().rotor_angles(1e308, 1e308)
    with pytest.raises(ValueError, match="finite real"):
        elbow().elbow_proxy_coordinate(1.7e308, 1.7e308)
