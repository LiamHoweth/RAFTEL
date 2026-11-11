"""Bounded sweeps, reproducibility and independently recomputed witnesses."""

import copy
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from raftel_arm01.engineering.jaw_loads import (
    apply_jaw_overlay,
    carry_jaw_derivatives,
    jaw_gravity_torque_nm,
)
from raftel_arm01.engineering.scenarios import load_scenario_manifest, verify_scenario_inputs

ROOT = Path(__file__).parents[1]
for name in ("thor_load_analysis", "thor_scenario_analysis", "thor_sensitivity_study"):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
loads, study = sys.modules["thor_load_analysis"], sys.modules["thor_sensitivity_study"]


def manifest():
    return load_scenario_manifest(ROOT / "config/thor-scenario-v1.json")


def small_request():
    request = study.documented_reference_request(manifest())
    request["materials"] = request["materials"][:2]
    request["printed_fractions"]["values"] = [0.5, 1]
    request["poses"] = request["poses"][2:]
    request["jaws"] = request["jaws"][::2]
    request["payload_masses"]["values"] = [0, 0.2]
    request["payload_offsets_zero_m"]["values"] = [[0, 0, 0], [0, 0.05, 0]]
    return request


def exact_witness_holding(witness, manifest_data):
    """Rebuild each witness with a changed payload point; no cached-offset shortcut."""
    inputs = verify_scenario_inputs(manifest_data, ROOT)
    inventory, membership, jaw = (inputs[key] for key in ("inventory", "membership", "jaw_bodies"))
    offset = witness["payload_offset_zero_m"]
    payload_point = [offset[i] + [0, 0, 0.7025242557054092][i] for i in range(3)]
    material, fraction = witness["material"], witness["printed_fraction"]
    zero = loads.expand_mass_assignments(
        loads.build_thor_snapshot(
            inventory,
            printed_fraction=fraction,
            material=material["name"],
            material_density_kg_m3=material["density_kg_m3"],
            material_density_source=material["evidence"],
            payload_point_m=payload_point,
            instance_mass_overrides=manifest_data["belt_mass_overrides"],
        ),
        membership,
    )
    zero["wrist_conditional_gravity_closure"] = membership["conditional_gravity_closure"]
    jaw_case = witness["jaw"]
    overlay = apply_jaw_overlay(
        zero,
        jaw,
        jaw_case["closing_angle_rad"],
        mode="saved" if jaw_case["configuration"] == "saved_frozen" else "ideal",
    )
    angles = witness["pose"]["joint_angles_rad"]
    classes = loads.wrist_motion_classes(membership, manifest_data["wrist_motion_scenario"])
    posed = loads.articulate_wrist_snapshot(overlay, tuple(angles), classes)
    report = loads.analyze(posed, payloads_kg=(witness["payload_mass_kg"],))
    if witness["coordinate"] == "ideal_jaw_q":
        return -jaw_gravity_torque_nm(overlay, carry_jaw_derivatives(overlay, angles, classes))
    index = int(witness["coordinate"].removeprefix("joint_")) - 1
    row = report["scenarios"][0]["joints"][index]
    return (
        row["required_ideal_holding_torque_nm"]
        if row["required_ideal_holding_torque_nm"] is not None
        else row["conditional_modeled_holding_torque_nm"]
    )


def assert_close_json(actual, expected):
    if isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=2e-12, abs=2e-12)
    elif isinstance(expected, dict):
        assert set(actual) == set(expected)
        for key in expected:
            assert_close_json(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for first, last in zip(actual, expected, strict=True):
            assert_close_json(first, last)
    else:
        assert actual == expected


def test_complete_reference_grid_reproduces_with_honest_sampled_bounds():
    config = manifest()
    request = study.documented_reference_request(config)
    report = study.sensitivity_report(config, request, ROOT)
    saved = json.loads((ROOT / "hardware/cad/thor-sensitivity-study-v1.json").read_text())
    assert_close_json(report, saved)
    assert report["sampling"]["case_count"] == 1620
    assert not report["sampling"]["sampled_extrema_are_certified_worst_cases"]
    assert not report["pose_limits_collision_actuator_or_fabrication_qualification"]
    assert report["full_physical_wrist_holding_torques_remain_unknown"]
    assert not report["ideal_jaw_effort_is_servo_shaft_torque"]
    assert len(report["sampled_extrema"]) == 7
    rankings = report["ranked_missing_measurements_by_modeled_sensitivity"]
    assert len(rankings) == 5
    assert [row["maximum_sampled_conditional_holding_spread_nm"] for row in rankings] == sorted(
        (row["maximum_sampled_conditional_holding_spread_nm"] for row in rankings), reverse=True
    )
    # Recompute the seven reported witnesses through full changed-point snapshots.
    for row in report["sampled_extrema"]:
        value = exact_witness_holding(row["witness"], config)
        assert value == pytest.approx(row["witness"]["signed_conditional_holding_nm"], abs=1e-12)
        assert abs(value) == pytest.approx(
            row["sampled_max_absolute_conditional_holding_nm"], abs=1e-12
        )


def test_matched_parameter_ranking_has_recomputable_endpoints_and_no_other_changes():
    config = manifest()
    request = small_request()
    saved = copy.deepcopy(request)
    report = study.sensitivity_report(config, request, ROOT)
    assert request == saved
    assert report["sampling"]["case_count"] == 64
    for ranking in report["ranked_missing_measurements_by_modeled_sensitivity"]:
        low, high = ranking["low_witness"], ranking["high_witness"]
        low_parameters = {
            key: value
            for key, value in low.items()
            if key not in {ranking["varied_parameter"], "signed_conditional_holding_nm"}
        }
        high_parameters = {
            key: value
            for key, value in high.items()
            if key not in {ranking["varied_parameter"], "signed_conditional_holding_nm"}
        }
        assert low_parameters == high_parameters
        low_value = exact_witness_holding(low, config)
        high_value = exact_witness_holding(high, config)
        assert high_value - low_value == pytest.approx(
            ranking["maximum_sampled_conditional_holding_spread_nm"], abs=1e-12
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["units"].update(position="mm"),
        lambda data: data.update(schema_version=True),
        lambda data: data.update(evidence_class="physical"),
        lambda data: data["materials"][0].update(density_kg_m3=math.inf),
        lambda data: data["materials"][0].update(evidence=""),
        lambda data: data["printed_fractions"].update(values=[0]),
        lambda data: data["payload_masses"].update(values=[-1]),
        lambda data: data["payload_masses"].update(values=[0.2, 0.2]),
        lambda data: data["payload_offsets_zero_m"].update(values=[[0, 0, math.nan]]),
        lambda data: data["jaws"][0].update(closing_angle_rad=0),
        lambda data: data["jaws"][-1].update(closing_angle_rad=math.pi / 2),
        lambda data: data["poses"][0].update(joint_angles_rad=[0] * 5),
        lambda data: data["poses"].append(copy.deepcopy(data["poses"][0])),
        lambda data: data.update(physical_capacity_margin=1.0),
    ],
)
def test_ambiguous_nonfinite_or_unproven_sweep_inputs_fail(mutate):
    request = small_request()
    mutate(request)
    with pytest.raises(ValueError):
        study.validate_sweep_request(request)


def test_requested_case_count_is_bounded_before_analysis():
    request = small_request()
    original = request["poses"][0]
    request["poses"] = [
        {"name": f"explicit_{i}", "joint_angles_rad": original["joint_angles_rad"]}
        for i in range(200)
    ]
    with pytest.raises(ValueError, match="bounded maximum"):
        study.validate_sweep_request(request)


def test_sweep_report_rejects_stale_manifest_and_cli_requires_explicit_request(tmp_path):
    config = manifest()
    config["inputs"]["jaw_bodies"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="stale input hash"):
        study.sensitivity_report(config, small_request(), ROOT)
    command = [
        sys.executable,
        str(ROOT / "tools/thor_sensitivity_study.py"),
        str(ROOT / "config/thor-scenario-v1.json"),
    ]
    missing = subprocess.run(command, capture_output=True, text=True, check=False)
    assert missing.returncode != 0 and "required" in missing.stderr
    bad = tmp_path / "request.json"
    bad.write_text('{"schema_version":1,"schema_version":1}')
    ambiguous = subprocess.run(
        command + ["--request", str(bad)], capture_output=True, text=True, check=False
    )
    assert ambiguous.returncode != 0 and "duplicate JSON key" in ambiguous.stderr
