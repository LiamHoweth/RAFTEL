"""Declared drive power, source binding and unknown-effort regression checks."""

import copy
import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location(
    "thor_drive_sensitivity_study", ROOT / "tools" / "thor_drive_sensitivity_study.py"
)
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


@pytest.fixture
def study_request():
    return study.read_json(ROOT / "config" / "thor-drive-sensitivity-v1.json")[0]


def model(sign=1, coupling=1):
    return study.ElbowTransmission(1, 2, 4, 2, coupling, sign)


def test_mixed_direction_hand_calculated_port_power_and_reaction():
    result = study.evaluate_operating_point(
        3, 4, [1, -1], model(), 0.25, {"B": 0.5, "C": 0.75, "E": 0.8}
    )
    ports = result["ports"]
    assert [ports[p]["power_flow"] for p in ("B", "C", "E")] == [
        "motoring",
        "motoring",
        "backdriving",
    ]
    assert [ports[p]["input_mechanical_power_w"] for p in ("B", "C", "E")] == (
        pytest.approx([0.5, 1, -1.6])
    )
    assert result["total_joint_mechanical_power_w"] == -1
    assert result["total_input_mechanical_power_w"] == pytest.approx(-0.1)
    assert result["total_modeled_mechanical_loss_w"] == pytest.approx(0.9)
    assert result["carrier_reaction_from_elbow_output_nm"] == 2
    assert ports["E"]["input_effort_nm"] == 0.4


def test_joint_power_cancellation_still_dissipates():
    result = study.evaluate_operating_point(
        3, 4, [1, -0.75], model(), 0.5, {"B": 0.8, "C": 0.8, "E": 0.8}
    )
    assert result["total_joint_mechanical_power_w"] == 0
    assert result["total_modeled_mechanical_loss_w"] == pytest.approx(0.45)
    assert result["total_input_mechanical_power_w"] == pytest.approx(0.45)


def test_zero_elbow_port_rate_has_unknown_effort_even_with_moving_joints():
    result = study.evaluate_operating_point(
        3, 4, [1, -0.5], model(), 0.25, {"B": 0.8, "C": 0.8, "E": 0.8}
    )
    assert result["unknown_static_input_effort_ports"] == ["E"]
    assert result["ports"]["E"]["input_effort_nm"] is None
    assert result["ports"]["E"]["input_mechanical_power_w"] == 0
    assert result["ports"]["E"]["holding_electrical_or_thermal_loss_w"] is None


def test_static_nonzero_effort_is_not_efficiency_divided():
    result = study.evaluate_operating_point(
        3, 4, [0, 0], model(), 0.5, {"B": 0.01, "C": 0.01, "E": 0.01}
    )
    assert result["unknown_static_input_effort_ports"] == ["B", "C", "E"]
    assert result["total_modeled_mechanical_loss_w"] == 0
    assert result["complete_actuator_effort_or_capacity"] is None


@pytest.mark.parametrize("share", [0, 1])
def test_allocation_endpoints_are_zero_effort_not_unknown(share):
    result = study.evaluate_operating_point(
        3, 4, [0, 0], model(), share, {"B": 0.8, "C": 0.8, "E": 0.8}
    )
    inactive = "B" if share == 0 else "C"
    assert result["ports"][inactive]["input_effort_nm"] == 0
    assert result["ports"][inactive]["power_flow"] == "zero_transmitted_effort"


@pytest.mark.parametrize("sign", [-1, 1])
def test_random_signed_virtual_work_and_nonnegative_losses(sign):
    rng = random.Random(503)
    for _ in range(100):
        t2, t3, q2, q3 = [rng.uniform(-10, 10) for _ in range(4)]
        coupling = rng.uniform(-2, 2)
        result = study.evaluate_operating_point(
            t2,
            t3,
            [q2, q3],
            model(sign, coupling),
            rng.random(),
            {p: rng.uniform(0.1, 1) for p in ("B", "C", "E")},
        )
        assert result["sum_output_port_power_w"] == pytest.approx(t2 * q2 + t3 * q3)
        assert all(port["modeled_mechanical_loss_w"] >= 0 for port in result["ports"].values())
        assert result["total_input_mechanical_power_w"] == pytest.approx(
            result["total_joint_mechanical_power_w"] + result["total_modeled_mechanical_loss_w"]
        )


@pytest.mark.parametrize(
    "args",
    [
        (1e-100, 1e-100, 1e-224, 1),
        (1e-200, -1e100, 1e100, 1e-100),
        (1e-200, 1e-200, 1, 1),
    ],
)
def test_underflow_cannot_be_promoted_to_known_zero(args):
    with pytest.raises(ValueError):
        study._port(*args)


def test_full_bound_study_preserves_sources_and_unknown_counts(study_request):
    before = copy.deepcopy(study_request)
    report = study.build_report(study_request)
    assert study_request == before
    assert report["sampling"]["case_count"] == 63
    assert report["source_mass_ledger_summary"]["modeled_mass_kg"] == 5.6547224855756
    assert report["source_mass_ledger_summary"]["motor_mass_kg"] == 2.120
    assert report["mass_assignments_added_removed_or_reweighted"] is False
    assert report["complete_capacity_margin"] is None
    for extreme in report["sampled_effort_extrema"]:
        assert (
            extreme["known_modeled_effort_samples"] + extreme["unknown_static_effort_samples"] == 63
        )
        assert extreme["unknown_static_effort_samples"] > 0
        assert extreme["witness"]["case_id"] == extreme["witness_case_id"]
    for row in report["cases"]:
        assert row["result"]["demanded_joint_countertorques_nm"] == pytest.approx(
            [-5.843128346682769, -2.3498756418312166]
        )
    assert {r["varied_axis"] for r in report["matched_reference_contrasts"]} == {
        "drum_radius_m",
        "gearbox_efficiencies",
        "shoulder_b_fraction",
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(schema_version=True),
        lambda r: r["units"].update(radius="mm"),
        lambda r: r["source_load_study"].update(path="C:/data.json"),
        lambda r: r["source_load_study"].update(path="../data.json"),
        lambda r: r["parameter_points"][0].update(drum_radius_m=0),
        lambda r: r["parameter_points"][0].update(shoulder_b_fraction=1.1),
        lambda r: r["parameter_points"][0]["gearbox_efficiencies"].update(B=0),
        lambda r: r["operating_points"][0].update(joint_rates_rad_s=[True, 0]),
        lambda r: r["parameter_points"].append(copy.deepcopy(r["parameter_points"][0])),
        lambda r: r["operating_points"].append(copy.deepcopy(r["operating_points"][0])),
        lambda r: r.update(extra="unknown"),
    ],
)
def test_study_request_rejects_ambiguous_or_invalid_values(study_request, mutate):
    mutate(study_request)
    with pytest.raises(ValueError):
        study.validate_request(study_request)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(schema_version=True),
        lambda r: r["units"].update(torque="N*mm"),
        lambda r: r["source_revisions"].update(thor_cad="0" * 40),
        lambda r: r.update(actuator_or_fabrication_qualification=True),
        lambda r: r.update(pose_feasibility_or_collision_limits_validated=True),
        lambda r: r.update(native_recompute_performed=True),
        lambda r: r.update(full_physical_wrist_holding_torques_remain_unknown=False),
        lambda r: r["mass_conservation"].update(motor_asset_count=True),
        lambda r: r["mass_conservation"].update(modeled_mass_kg=1),
        lambda r: r["mass_conservation"].update(mass_record_identity_sha256="not-a-hash"),
    ],
)
def test_semantics_rejected_even_with_coherent_rebound_hashes(study_request, tmp_path, mutate):
    source, _ = study.read_json(ROOT / study_request["source_load_study"]["path"])
    mutate(source)
    raw = (json.dumps(source, allow_nan=False) + "\n").encode()
    path = tmp_path / "source.json"
    path.write_bytes(raw)
    study_request["source_load_study"] = {
        "path": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_sha256": study.canonical_sha256(source),
    }
    with pytest.raises(ValueError):
        study.build_report(study_request, tmp_path)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b"[]"])
def test_strict_json_rejects_duplicate_nonfinite_and_nonobject(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        study.read_json(path)


def test_stale_binding_and_missing_source_fail(study_request):
    study_request["source_load_study"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="stale"):
        study.build_report(study_request)


@pytest.mark.parametrize("rates", [[1e300, 0], [0, 0]])
def test_branch_underflow_is_not_hidden_by_power_or_static_unknown_policy(rates):
    with pytest.raises(ValueError):
        study.evaluate_operating_point(
            5e-324,
            0,
            rates,
            study.ElbowTransmission(1, 2, 1, 1, 0, 1),
            0.5,
            {"B": 1, "C": 1, "E": 1},
        )


def test_elbow_output_underflow_is_rejected_when_static():
    with pytest.raises(ValueError, match="elbow demand underflowed"):
        study.evaluate_operating_point(
            0,
            5e-324,
            [0, 0],
            study.ElbowTransmission(1, 2, 1, 1, 0, 1),
            0.5,
            {"B": 1, "C": 1, "E": 1},
        )


def test_nested_malformed_input_has_clean_cli_error(study_request, tmp_path, capsys):
    nested = 0
    for _ in range(600):
        nested = [nested]
    study_request["model_scope"] = nested
    path = tmp_path / "nested.json"
    path.write_text(json.dumps(study_request), encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit) as error:
        study.main([str(path)])
    assert error.value.code == 2
    assert "Traceback" not in capsys.readouterr().err


def test_cli_lf_no_overwrite_and_exact_reproduction(tmp_path, study_request):
    target = tmp_path / "new.json"
    assert (
        study.main(
            [str(ROOT / "config" / "thor-drive-sensitivity-v1.json"), "--output", str(target)]
        )
        == 0
    )
    raw = target.read_bytes()
    assert b"\r" not in raw
    assert json.loads(raw) == study.build_report(study_request)
    with pytest.raises(SystemExit) as error:
        study.main(
            [str(ROOT / "config" / "thor-drive-sensitivity-v1.json"), "--output", str(target)]
        )
    assert error.value.code == 2
    assert target.read_bytes() == raw


def test_existing_report_reproduces_exactly_if_present(study_request):
    path = ROOT / "hardware" / "cad" / "thor-drive-sensitivity-study-v1.json"
    if not path.exists():
        pytest.skip("candidate report not generated yet")
    expected = (
        json.dumps(study.build_report(study_request), indent=2, allow_nan=False) + "\n"
    ).encode()
    assert path.read_bytes() == expected
