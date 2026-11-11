#!/usr/bin/env python3
"""Synthetic elbow identification fixtures; no physical calibration or I/O."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import asdict
from pathlib import Path

from raftel_arm01.control.thor_identification import (
    COORDINATES,
    EVIDENCE_CLASS,
    IdentificationPolicy,
    SyntheticElbowObservation,
    fit_elbow_model,
)


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate synthetic input field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite synthetic input constant: {value}")


def _policy(**updates) -> IdentificationPolicy:
    values = {
        "minimum_axis_span_rad": 0.1,
        "max_output_residual_rad": 0.002,
        "max_direction_half_bias_rad": 0.001,
        "output_noise_floor_std_rad": 0.0001,
        "uncertainty_sigma_multiplier": 2,
        "output_scale_known": True,
    }
    return IdentificationPolicy(**(values | updates))


def _grid(
    *,
    seed: int,
    noise: float = 0,
    quantum: float = 0,
    hysteresis: float = 0,
    ratio: float = 5.8,
    output_scale: float = 1,
) -> list[SyntheticElbowObservation]:
    rng = random.Random(seed)
    result = []
    for q2 in (-0.35, -0.1, 0.3, 0.55):
        for q3 in (-0.6, -0.2, 0.4):
            for direction in (-1, 1):
                phi = (
                    0.12 + q2 + ratio * q3 + hysteresis * direction + rng.uniform(-noise, noise)
                ) * output_scale
                if quantum:
                    phi = round(phi / quantum) * quantum
                result.append(SyntheticElbowObservation(q2, q3, phi, direction))
    return result


def synthetic_study(seed: int) -> dict:
    """Bounded deterministic experiment with expected identifiable/rejected cases."""
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an integer within 0..2**32-1")
    collinear = [
        SyntheticElbowObservation(q, 2 * q, 0.12 + 12.6 * q, direction)
        for q in (-0.5, 0, 0.5)
        for direction in (-1, 1)
    ]
    wrapped = [
        SyntheticElbowObservation(
            item.q2_rad,
            item.q3_rad,
            (item.phi_rad + math.pi) % (2 * math.pi) - math.pi,
            item.approach_direction,
        )
        for item in _grid(seed=seed)
    ]
    cases = [
        ("known_positive_ratio", _grid(seed=seed), _policy(), True),
        ("known_negative_ratio", _grid(seed=seed, ratio=-5.8), _policy(), True),
        (
            "noisy_quantized_negative_ratio",
            _grid(seed=seed, ratio=-5.8, noise=0.00015, quantum=0.0002),
            _policy(),
            True,
        ),
        ("direction_hysteresis", _grid(seed=seed, hysteresis=0.01), _policy(), False),
        ("collinear_predictors", collinear, _policy(), False),
        (
            "unpaired_directions",
            [item for item in _grid(seed=seed) if item.approach_direction == 1],
            _policy(),
            False,
        ),
        (
            "unknown_output_scale",
            _grid(seed=seed, output_scale=2.5),
            _policy(output_scale_known=False),
            False,
        ),
        ("ambiguous_ratio_sign", _grid(seed=seed, ratio=1e-8), _policy(), False),
        ("wrapped_output_contradiction", wrapped, _policy(), False),
    ]
    outcomes = []
    for name, observations, policy, expected in cases:
        result = fit_elbow_model(observations, policy=policy)
        outcomes.append(
            {
                "case": name,
                "expected_synthetic_acceptance": expected,
                "expectation_met": result.accepted_for_synthetic_model == expected,
                "policy": asdict(policy),
                "result": asdict(result),
            }
        )
    return {
        "schema_version": 1,
        "evidence_class": EVIDENCE_CLASS,
        "coordinates": COORDINATES,
        "seed": seed,
        "generator": {
            "base_zero_rad": 0.12,
            "base_carrier_coefficient": 1,
            "base_ratio_magnitude": 5.8,
            "q2_grid_rad": [-0.35, -0.1, 0.3, 0.55],
            "q3_grid_rad": [-0.6, -0.2, 0.4],
            "approach_directions": [-1, 1],
            "noise_case_uniform_half_width_rad": 0.00015,
            "quantum_case_rad": 0.0002,
            "quantization_rule": "nearest_quantum_python_round_half_even",
            "hysteresis_case_half_bias_rad": 0.01,
            "output_scale_case_multiplier": 2.5,
        },
        "all_expected_outcomes_met": all(item["expectation_met"] for item in outcomes),
        "cases": outcomes,
        "physical_calibration_performed": False,
        "commissioned": False,
    }


def _load_synthetic_input(path: Path) -> dict:
    if path.stat().st_size > 1_048_576:
        raise ValueError("synthetic input exceeds one MiB")
    raw = path.read_bytes()
    document = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    required = {"schema_version", "evidence_class", "coordinates", "policy", "observations"}
    if not isinstance(document, dict) or set(document) != required:
        raise ValueError("synthetic document fields differ from the input contract")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("unsupported synthetic input schema")
    if document["evidence_class"] != EVIDENCE_CLASS or document["coordinates"] != COORDINATES:
        raise ValueError("only declared exact unwrapped synthetic coordinates are supported")
    if not isinstance(document["policy"], dict):
        raise ValueError("an explicit experiment policy object is required")
    policy = IdentificationPolicy(**document["policy"])
    records = document["observations"]
    if not isinstance(records, list) or not 1 <= len(records) <= 10_000:
        raise ValueError("observations must be a bounded nonempty list")
    fields = {"q2_rad", "q3_rad", "phi_rad", "approach_direction"}
    if any(not isinstance(item, dict) or set(item) != fields for item in records):
        raise ValueError("each synthetic observation needs exact angle and direction fields")
    observations = [SyntheticElbowObservation(**record) for record in records]
    result = fit_elbow_model(observations, policy=policy)
    return {
        "schema_version": 1,
        "evidence_class": EVIDENCE_CLASS,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "coordinates": COORDINATES,
        "policy": asdict(policy),
        "result": asdict(result),
        "physical_calibration_performed": False,
        "commissioned": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="synthetic generation seed")
    parser.add_argument("--input", type=Path, help="explicitly synthetic JSON experiment")
    parser.add_argument("--output", type=Path, help="new report path; existing evidence refused")
    args = parser.parse_args(argv)
    try:
        report = _load_synthetic_input(args.input) if args.input else synthetic_study(args.seed)
        encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            print(encoded, end="")
        else:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
    except (ValueError, TypeError, OSError, OverflowError) as error:
        print(f"synthetic identification: {error}", file=sys.stderr)
        return 2
    if report.get("all_expected_outcomes_met") is False:
        return 1
    if "result" in report and not report["result"]["accepted_for_synthetic_model"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
