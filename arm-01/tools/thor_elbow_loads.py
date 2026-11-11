"""Conditional remote-elbow transmission statics; no physical capacity claim.

Every geometric coordinate and carrier coefficient is explicit. This module
never turns the smooth drum's CAD body radius into a verified belt pitch radius,
uses holding torque as a running rating, or chooses physical shoulder sharing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict
from numbers import Real
from pathlib import Path

from raftel_arm01.kinematics.thor_transmission import ElbowTransmission


def finite(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("values must be finite real numbers")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("values must be finite real numbers") from error
    if not math.isfinite(result):
        raise ValueError("values must be finite real numbers")
    return result


def driver_pitch_radius_m(teeth: int, pitch_m: float) -> float:
    """Pitch-circle radius from a declared toothed pulley and belt pitch."""
    if type(teeth) is not int or teeth <= 0 or finite(pitch_m) <= 0:
        raise ValueError("teeth must be positive integer; belt pitch must be positive")
    return finite(teeth * pitch_m / (2 * math.pi))


def signed_lossy_input_effort(
    output_effort_nm: float, ratio: float, efficiency: float, flow: str
) -> float:
    """Conditional signed two-port effort conversion with explicit power direction.

    'motoring': input supplies output, input effort = output/(N*eta).
    'backdriving': output supplies input, input effort = eta*output/N.
    Static holding has zero power, so this efficiency model is not applicable
    without an independently justified friction/holding model.
    """
    torque, ratio, efficiency = finite(output_effort_nm), finite(ratio), finite(efficiency)
    if ratio <= 0 or not 0 < efficiency <= 1:
        raise ValueError("ratio must be positive and efficiency in (0,1]")
    if flow == "motoring":
        return finite(torque / ratio / efficiency)
    if flow == "backdriving":
        return finite(torque / ratio * efficiency)
    raise ValueError("flow must be motoring or backdriving; static flow is not inferred")


def belt_tension_difference(elbow_joint_nm: float, drum_pitch_radius_m: float) -> dict:
    """Ideal tangential resultant requirement, not a pretension/traction selection."""
    torque, radius = finite(elbow_joint_nm), finite(drum_pitch_radius_m)
    if radius <= 0:
        raise ValueError("drum pitch radius must be positive")
    difference = finite(torque / radius)
    return {
        "signed_tension_difference_n": difference,
        "magnitude_n": abs(difference),
        "symmetric_mid_tension_minimum_for_nonnegative_spans_n": abs(difference) / 2,
        "physical_pretension_or_traction_qualified": False,
        "span_convention": "T_plus minus T_minus, positive resultant produces positive q3 torque",
        "meaning": "Magnitude is tight minus slack; clamp, wrap and bearing forces unresolved",
    }


def baseline_joint_loads(
    study: dict, fraction: float, pose: str, payload_kg: float
) -> tuple[float, float]:
    """Read existing CAD-derived demand; do not substitute payload-only sizing."""
    fraction, payload_kg = finite(fraction), finite(payload_kg)
    cases = [c for c in study["cases"] if c["printed_whole_part_fraction"] == fraction]
    if len(cases) != 1:
        raise ValueError("exactly one matching material fraction is required")
    rows = [c for c in cases[0]["poses"][pose]["payload_cases"] if c["payload_kg"] == payload_kg]
    if len(rows) != 1:
        raise ValueError("exactly one matching payload case is required")
    values = {r["joint"]: r for r in rows[0]["joints"]}
    return tuple(
        finite(values[key]["required_ideal_holding_torque_nm"]) for key in ("joint_2", "joint_3")
    )


def conditional_report(
    study: dict,
    transmission: ElbowTransmission,
    shoulder_b_fraction: float,
    *,
    fraction: float,
    pose: str,
    payload_kg: float,
    geometry_evidence: str,
) -> dict:
    if not isinstance(geometry_evidence, str) or not geometry_evidence.strip():
        raise ValueError("geometry assumption/evidence source is required")
    t2, t3 = baseline_joint_loads(study, fraction, pose, payload_kg)
    return {
        "schema_version": 1,
        "validation_class": "conditional_transmission_analytical_model_not_hardware_qualification",
        "source_load_study_sha256": hashlib.sha256(
            json.dumps(study, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest(),
        "load_case": {"fraction": fraction, "pose": pose, "payload_kg": payload_kg},
        "input_holding_joint_nm": {"q2": t2, "q3": t3},
        "transmission_parameters": asdict(transmission),
        "geometry_evidence_or_assumptions": geometry_evidence,
        "ideal_efforts": transmission.ideal_rotor_efforts(t2, t3, shoulder_b_fraction),
        "belt_tension_requirement": belt_tension_difference(t3, transmission.drum_radius_m),
        "constant_effective_pitch_radius_physically_verified": False,
        "motor_capacity_or_safe_payload_qualified": False,
        "caveats": [
            "Radii, signs and carrier mapping are inputs; no calibrated motion instruction",
            "Static demands exclude motion, friction, acceleration, cables and thermal effects",
            "No physical shoulder load-sharing fraction is guaranteed",
            "No efficiency multiplier is applied to zero-power static holding",
            "Tension difference does not establish pretension, traction, clamp or bearing capacity",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load-study", required=True, type=Path)
    parser.add_argument("--drum-pitch-radius-mm", required=True, type=float)
    parser.add_argument("--driver-teeth", type=int, default=20)
    parser.add_argument("--belt-pitch-mm", type=float, default=2.0)
    parser.add_argument("--elbow-gearbox-ratio", type=float, default=5.18)
    parser.add_argument("--shoulder-branch-ratio", type=float, default=31.08)
    parser.add_argument("--carrier-coupling", required=True, type=float)
    parser.add_argument("--belt-sign", required=True, type=int, choices=(-1, 1))
    parser.add_argument("--shoulder-b-fraction", required=True, type=float)
    parser.add_argument("--geometry-evidence", required=True)
    parser.add_argument("--fraction", type=float, default=0.5)
    parser.add_argument("--pose", default="shoulder_horizontal")
    parser.add_argument("--payload-kg", type=float, default=0.2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        model = ElbowTransmission(
            driver_pitch_radius_m(args.driver_teeth, args.belt_pitch_mm / 1000),
            args.drum_pitch_radius_mm / 1000,
            args.elbow_gearbox_ratio,
            args.shoulder_branch_ratio,
            args.carrier_coupling,
            args.belt_sign,
        )
        result = conditional_report(
            json.loads(args.load_study.read_text()),
            model,
            args.shoulder_b_fraction,
            fraction=args.fraction,
            pose=args.pose,
            payload_kg=args.payload_kg,
            geometry_evidence=args.geometry_evidence,
        )
        content = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x") as stream:
                stream.write(content)
        else:
            print(content, end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
