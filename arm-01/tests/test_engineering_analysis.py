"""Analytical invariants, not assertions of physical actuator suitability."""

import importlib.util
import math
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "engineering_analysis", Path(__file__).parents[1] / "tools" / "engineering_analysis.py"
)
analysis = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = analysis
_SPEC.loader.exec_module(analysis)


def test_payload_only_known_moment():
    load = analysis.PointLoad("payload", 0.2, 0.35)
    assert analysis.static_torque_nm((load,)) == pytest.approx(0.6864655)


def test_proximal_mass_does_not_load_elbow():
    loads = (
        analysis.PointLoad("proximal", 20, 0.1),
        analysis.PointLoad("distal", 0.2, 0.4),
    )
    assert analysis.static_torque_nm(loads, 0.18) == pytest.approx(0.4314926)


def test_model_includes_more_than_payload():
    loads = analysis.proposed_loads()
    payload_only = analysis.static_torque_nm((loads[-1],))
    assert analysis.static_torque_nm(loads) > 2 * payload_only
    assert len([load for load in loads if "servo" in load.name]) == 5


def test_shorter_geometry_reduces_moment_proportionally():
    full = analysis.static_torque_nm(analysis.proposed_loads())
    short = analysis.static_torque_nm(analysis.proposed_loads(length_scale=0.75))
    assert short == pytest.approx(full * 0.75)


def test_floor_bound_matches_pythagoras_and_rejects_too_high_mount():
    radius = analysis.floor_outer_radius_m(0.4, 0.325, 0.025)
    assert radius == pytest.approx(math.sqrt(0.4**2 - 0.3**2))
    assert analysis.floor_outer_radius_m(0.4, 0.5) is None
    assert analysis.floor_outer_radius_m(0.4, 0.425) == pytest.approx(0)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_mass_rejected(value):
    with pytest.raises(ValueError):
        analysis.PointLoad("bad", value, 0.1)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_geometry_rejected(value):
    with pytest.raises(ValueError):
        analysis.proposed_loads(length_scale=value)
    with pytest.raises(ValueError):
        analysis.floor_outer_radius_m(0.4, value)


def test_report_explicitly_disclaims_hardware_validation():
    report = analysis.report()
    assert report["validation_class"] == "preliminary_analytical_estimate_not_hardware_or_ik"
    assert len(report["static_scenarios"]) == 6
    assert all(
        not case["chassis_and_joint_limits_checked"] for case in report["floor_outer_bounds"]
    )
