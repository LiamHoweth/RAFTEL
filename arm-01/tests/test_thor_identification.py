"""Synthetic identifiability, contradiction and conditional uncertainty checks."""

import json
import math
import random
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from raftel_arm01.control.thor_identification import (
    IdentificationPolicy,
    SyntheticElbowObservation,
    fit_elbow_model,
)


def policy(**overrides):
    values = {
        "minimum_axis_span_rad": 0.1,
        "max_output_residual_rad": 0.002,
        "max_direction_half_bias_rad": 0.001,
        "output_noise_floor_std_rad": 0.0001,
        "uncertainty_sigma_multiplier": 2.0,
        "output_scale_known": True,
    }
    values.update(overrides)
    return IdentificationPolicy(**values)


def grid(
    *,
    carrier=1.0,
    ratio=5.8,
    zero=0.12,
    seed=42,
    noise=0.0,
    quantum=0.0,
    hysteresis=0.0,
    scale=1.0,
):
    rng = random.Random(seed)
    samples = []
    for q2 in (-0.35, -0.1, 0.3, 0.55):
        for q3 in (-0.6, -0.2, 0.4):
            for direction in (-1, 1):
                output = (
                    zero
                    + carrier * q2
                    + ratio * q3
                    + hysteresis * direction
                    + rng.uniform(-noise, noise)
                ) * scale
                if quantum:
                    output = round(output / quantum) * quantum
                samples.append(SyntheticElbowObservation(q2, q3, output, direction))
    return samples


def test_known_synthetic_coefficients_recovered_with_nonzero_uncertainty_floor():
    result = fit_elbow_model(grid(), policy=policy())
    assert result.accepted_for_synthetic_model
    assert result.coefficients.zero_rad == pytest.approx(0.12, abs=1e-12)
    assert result.coefficients.carrier_coefficient == pytest.approx(1, abs=1e-12)
    assert result.coefficients.signed_ratio == pytest.approx(5.8, abs=1e-12)
    assert result.identified_ratio_sign == 1
    assert result.identified_ratio_magnitude == pytest.approx(5.8)
    assert result.paired_direction_pose_count == 12
    assert result.distinct_pose_count == 12
    assert result.sample_count == 24
    assert result.max_abs_residual_rad < 1e-14
    assert result.coefficient_standard_errors.signed_ratio > 0
    assert result.evidence_class == "synthetic_identification_not_physical_calibration"
    assert not result.commissioned


def test_seeded_unequal_input_scales_offsets_and_both_ratio_signs():
    rng = random.Random(908)
    for _ in range(40):
        carrier, ratio, zero = (
            rng.uniform(-2, 2),
            rng.choice((-1, 1)) * rng.uniform(1, 9),
            rng.uniform(-3, 3),
        )
        samples = [
            SyntheticElbowObservation(q2, q3, zero + carrier * q2 + ratio * q3, direction)
            for q2 in (-0.2, 0, 0.1)
            for q3 in (-2, 0, 3)
            for direction in (-1, 1)
        ]
        result = fit_elbow_model(samples, policy=policy())
        assert result.accepted_for_synthetic_model
        assert result.coefficients.carrier_coefficient == pytest.approx(carrier, abs=1e-12)
        assert result.coefficients.signed_ratio == pytest.approx(ratio, abs=1e-12)
        assert result.coefficients.zero_rad == pytest.approx(zero, abs=1e-12)
        assert result.identified_ratio_sign == (1 if ratio > 0 else -1)


def test_noise_and_quantization_are_exercised_without_claiming_iid_interval_coverage():
    result = fit_elbow_model(grid(ratio=-5.8, noise=0.00015, quantum=0.0002), policy=policy())
    assert result.accepted_for_synthetic_model
    assert result.identified_ratio_sign == -1
    assert result.coefficients.signed_ratio == pytest.approx(-5.8, abs=0.0003)
    assert result.coefficients.carrier_coefficient == pytest.approx(1, abs=0.0003)
    assert result.residual_rms_rad > 0
    assert "not_predictor_noise_quantization_or_hysteresis_coverage" in result.uncertainty_scope


def test_bidirectional_repeated_poses_expose_hysteresis_instead_of_hiding_carrier_bias():
    result = fit_elbow_model(
        grid(hysteresis=0.01),
        policy=policy(max_output_residual_rad=0.02),
    )
    assert not result.accepted_for_synthetic_model
    assert "direction_dependent_bias_exceeds_declared_fixture_gate" in result.reasons
    assert result.mean_paired_direction_half_bias_rad == pytest.approx(0.01)
    assert result.coefficients.carrier_coefficient == pytest.approx(1)


def test_unpaired_direction_bias_cannot_be_claimed_assessed():
    samples = [sample for sample in grid() if sample.approach_direction == 1]
    result = fit_elbow_model(samples, policy=policy())
    assert not result.accepted_for_synthetic_model
    assert result.paired_direction_pose_count == 0
    assert result.mean_paired_direction_half_bias_rad is None
    assert "direction_bias_unassessed_requires_three_paired_poses" in result.reasons


def test_collinear_and_single_axis_excitation_reject_ratio_carrier_separation():
    collinear = [
        SyntheticElbowObservation(q, 2 * q, 0.1 + 4 * q, direction)
        for q in (-0.5, 0, 0.5)
        for direction in (-1, 1)
    ]
    result = fit_elbow_model(collinear, policy=policy())
    assert not result.accepted_for_synthetic_model
    assert result.coefficients is None
    assert "rank_deficient_or_ill_conditioned_design_matrix" in result.reasons
    one_axis = [replace(item, q3_rad=0) for item in collinear]
    result = fit_elbow_model(one_axis, policy=policy())
    assert not result.accepted_for_synthetic_model
    assert "insufficient_independent_axis_excitation" in result.reasons
    assert "rank_deficient_design_matrix" in result.reasons


def test_repeated_identical_poses_do_not_add_excitation():
    observations = [SyntheticElbowObservation(0.5, 0.3, 0.2, 1)] * 100
    result = fit_elbow_model(observations, policy=policy())
    assert not result.accepted_for_synthetic_model
    assert result.distinct_pose_count == 1
    assert result.coefficients is None


def test_unknown_output_scale_keeps_physical_parameters_unidentifiable():
    result = fit_elbow_model(grid(scale=2.5), policy=policy(output_scale_known=False))
    assert not result.accepted_for_synthetic_model
    assert "unknown_output_scale_conflates_carrier_ratio_and_scale" in result.reasons
    assert result.coefficients.carrier_coefficient == pytest.approx(2.5)
    assert result.coefficients.signed_ratio == pytest.approx(14.5)
    assert result.identified_ratio_magnitude is None
    assert result.identified_ratio_sign is None


def test_tiny_or_zero_ratio_has_ambiguous_sign_under_declared_noise():
    result = fit_elbow_model(grid(ratio=1e-8), policy=policy())
    assert not result.accepted_for_synthetic_model
    assert result.identified_ratio_sign is None
    assert result.identified_ratio_magnitude is None
    assert "ratio_sign_ambiguous_under_declared_noise_model" in result.reasons


def test_contradictory_and_wrapped_observations_fail_residual_gate():
    samples = grid()
    samples[0] = replace(samples[0], phi_rad=samples[0].phi_rad + 0.1)
    result = fit_elbow_model(samples, policy=policy())
    assert not result.accepted_for_synthetic_model
    assert "residuals_contradict_declared_linear_fixture_model" in result.reasons
    wrapped = [
        replace(item, phi_rad=(item.phi_rad + math.pi) % (2 * math.pi) - math.pi) for item in grid()
    ]
    result = fit_elbow_model(wrapped, policy=policy())
    assert not result.accepted_for_synthetic_model
    assert "residuals_contradict_declared_linear_fixture_model" in result.reasons


def test_covariance_satisfies_independent_normal_information_identity():
    observations = grid()
    configuration = policy()
    result = fit_elbow_model(observations, policy=configuration)
    rows = [(1, item.q2_rad, item.q3_rad) for item in observations]
    xtx = [[sum(row[i] * row[j] for row in rows) for j in range(3)] for i in range(3)]
    covariance = result.coefficient_covariance
    variance = configuration.output_noise_floor_std_rad**2
    for i in range(3):
        for j in range(3):
            product = sum(xtx[i][k] * covariance[k][j] for k in range(3))
            assert product == pytest.approx(variance if i == j else 0, abs=1e-20)


def test_observation_hash_is_deterministic_and_changes_with_content():
    observations = grid()
    first = fit_elbow_model(observations, policy=policy())
    assert (
        first.observations_sha256
        == fit_elbow_model(observations, policy=policy()).observations_sha256
    )
    observations[0] = replace(observations[0], phi_rad=observations[0].phi_rad + 0.00001)
    assert (
        first.observations_sha256
        != fit_elbow_model(observations, policy=policy()).observations_sha256
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"q2_rad": float("nan")},
        {"q3_rad": True},
        {"phi_rad": 1e308},
        {"approach_direction": 0},
        {"approach_direction": 1.0},
    ],
)
def test_bad_observations_reject_before_fit(kwargs):
    values = {"q2_rad": 0, "q3_rad": 0, "phi_rad": 0, "approach_direction": 1}
    values.update(kwargs)
    with pytest.raises(ValueError):
        SyntheticElbowObservation(**values)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"minimum_axis_span_rad": 0},
        {"output_noise_floor_std_rad": 0},
        {"output_noise_floor_std_rad": 1e-300},
        {"max_output_residual_rad": -1},
        {"uncertainty_sigma_multiplier": 0.5},
        {"output_scale_known": "unknown"},
    ],
)
def test_policy_requires_explicit_finite_bounded_experiment_gates(kwargs):
    with pytest.raises(ValueError):
        policy(**kwargs)


def test_bounded_and_typed_observation_input_required():
    for values in ([], [object()], grid() * 500, None):
        with pytest.raises(ValueError):
            fit_elbow_model(values, policy=policy())


def test_installed_cli_study_is_deterministic_and_declares_rejected_cases():
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, str(root / "tools/thor_identification_study.py"), "--seed", "42"]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    second = subprocess.run(command, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    report = json.loads(first.stdout)
    assert report["all_expected_outcomes_met"]
    assert len(report["cases"]) == 9
    assert not report["physical_calibration_performed"]
    assert sum(case["result"]["accepted_for_synthetic_model"] for case in report["cases"]) == 3


def test_cli_synthetic_input_hash_and_rejection_status(tmp_path):
    root = Path(__file__).resolve().parents[1]
    tool = root / "tools/thor_identification_study.py"
    path = tmp_path / "synthetic.json"
    document = {
        "schema_version": 1,
        "evidence_class": "synthetic_identification_not_physical_calibration",
        "coordinates": "exact_unwrapped_relative_joint_and_output_radians",
        "policy": asdict(policy()),
        "observations": [asdict(item) for item in grid()],
    }
    path.write_text(json.dumps(document))
    command = [sys.executable, str(tool), "--input", str(path)]
    good = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(good.stdout)["result"]["accepted_for_synthetic_model"]
    document["policy"]["output_scale_known"] = False
    path.write_text(json.dumps(document))
    rejected = subprocess.run(command, capture_output=True, text=True)
    assert rejected.returncode == 1
    assert "unknown_output_scale" in json.loads(rejected.stdout)["result"]["reasons"][0]
    document["evidence_class"] = "physical_calibration"
    path.write_text(json.dumps(document))
    physical = subprocess.run(command, capture_output=True, text=True)
    assert physical.returncode == 2
    assert not physical.stdout


def test_cli_negative_schema_preserves_existing_evidence(tmp_path):
    root = Path(__file__).resolve().parents[1]
    tool = root / "tools/thor_identification_study.py"
    existing = tmp_path / "existing.json"
    existing.write_text("prior evidence")
    result = subprocess.run(
        [sys.executable, str(tool), "--output", str(existing)], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert existing.read_text() == "prior evidence"
    bad = tmp_path / "bad.json"
    for raw in ('{"schema_version":1,"schema_version":1}', '{"value":NaN}', "[]"):
        bad.write_text(raw)
        result = subprocess.run(
            [sys.executable, str(tool), "--input", str(bad)], capture_output=True, text=True
        )
        assert result.returncode == 2
        assert not result.stdout


def test_measurement_worksheet_contains_no_fabricated_measurements():
    path = Path(__file__).resolve().parents[1] / "config/thor-identification-worksheet.json"
    worksheet = json.loads(path.read_text())
    assert not worksheet["physical_execution_performed"]
    assert worksheet["commissioning_status"] == "not_commissioned"
    assert all(value is None for value in worksheet["observation_template"].values())
    assert all(value is None for value in worksheet["preconditions"].values())
