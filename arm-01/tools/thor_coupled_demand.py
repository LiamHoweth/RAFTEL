#!/usr/bin/env python3
"""Partial coupled demand from explicit offline rate/transmission scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

from thor_trajectory_study import load_rate_study, load_waypoints

from raftel_arm01.control.thor_coupled_demand import (
    EVIDENCE_CLASS,
    CoupledDemandScenario,
    project_motion,
    project_rate_boxes,
)
from raftel_arm01.kinematics.thor_constraints import load_constraints
from raftel_arm01.kinematics.thor_frames import _unique_object
from raftel_arm01.kinematics.thor_model import SOURCE_REVISION
from raftel_arm01.kinematics.thor_trajectory import plan_quintic_path
from raftel_arm01.kinematics.thor_transmission import ElbowTransmission, WristDifferential

ROOT = Path(__file__).resolve().parents[1]


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite transmission study constant: {value}")


def load_transmission_study(path: Path) -> tuple[CoupledDemandScenario, dict]:
    if path.stat().st_size > 1_048_576:
        raise ValueError("transmission study exceeds one MiB")
    data = json.loads(
        path.read_bytes(), object_pairs_hook=_unique_object, parse_constant=_reject_constant
    )
    expected = {"schema_version", "revision", "evidence_class", "evidence", "elbow", "wrist"}
    if (
        not isinstance(data, dict)
        or set(data) != expected
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
    ):
        raise ValueError("transmission study requires exact schema1 fields")
    elbow_fields = {
        "driver_radius_m",
        "drum_radius_m",
        "elbow_gearbox_ratio",
        "shoulder_branch_ratio",
        "carrier_coupling",
        "belt_sign",
    }
    wrist_fields = {"bevel_ratio", "handedness", "negative_y_rotor_scale", "positive_y_rotor_scale"}
    if not isinstance(data["elbow"], dict) or set(data["elbow"]) != elbow_fields:
        raise ValueError("elbow scenario requires all declared radii, ratios and signs")
    if not isinstance(data["wrist"], dict) or set(data["wrist"]) != wrist_fields:
        raise ValueError("wrist scenario requires all declared ratios and signed scales")
    if not isinstance(data["evidence"], str) or not data["evidence"].strip():
        raise ValueError("transmission study requires explicit provenance")
    model = CoupledDemandScenario(
        data["revision"],
        data["evidence_class"],
        data["evidence"],
        ElbowTransmission(**data["elbow"]),
        WristDifferential(**data["wrist"], evidence=data["evidence"]),
    )
    return model, data


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--rate-study", type=Path, required=True, help="T1 explicit rate study JSON"
    )
    result.add_argument(
        "--transmission-study",
        type=Path,
        required=True,
        help="Explicit assumed/synthetic constant-ratio transmission JSON",
    )
    result.add_argument(
        "--constraints", type=Path, default=ROOT / "config/thor-constraints-v1.json"
    )
    result.add_argument("--waypoints", type=Path, help="T1 revisioned nominal joint waypoints")
    result.add_argument("--sample-period-s", type=float, default=0.2)
    result.add_argument("--max-samples", type=int, default=10000)
    result.add_argument("--max-total-duration-s", type=float, default=300)
    result.add_argument(
        "--box-only", action="store_true", help="Rate boxes only, no sampled T1 path"
    )
    result.add_argument("--output", type=Path, help="New report path; existing evidence preserved")
    return result


def build_report(args: argparse.Namespace) -> dict:
    baseline = load_constraints(args.constraints)
    constraints, rate_study = load_rate_study(args.rate_study, baseline)
    model, transmission_study = load_transmission_study(args.transmission_study)
    boxes = project_rate_boxes(constraints, scenario=model)
    trajectory = None
    if not args.box_only:
        waypoints = load_waypoints(args.waypoints)
        path = plan_quintic_path(
            waypoints, constraints, max_total_duration_s=args.max_total_duration_s
        )
        samples = path.sample_uniform(args.sample_period_s, max_samples=args.max_samples)
        trajectory = {
            "duration_s": path.duration_s,
            "constraint_revision": path.constraint_revision,
            "sample_period_s": args.sample_period_s,
            "waypoints_rad": waypoints,
            "sampled_demands": [
                asdict(project_motion(sample, constraints, scenario=model)) for sample in samples
            ],
            "scope": "sampled_partial_coupled_demand_not_exact_path_clearance_or_load_extrema",
        }
    return {
        "schema_version": 1,
        "evidence_class": EVIDENCE_CLASS,
        "model_source_revision": SOURCE_REVISION,
        "inputs": {
            "constraints_sha256": hashlib.sha256(args.constraints.read_bytes()).hexdigest(),
            "rate_study_sha256": hashlib.sha256(args.rate_study.read_bytes()).hexdigest(),
            "transmission_study_sha256": hashlib.sha256(
                args.transmission_study.read_bytes()
            ).hexdigest(),
            "waypoints_sha256": None
            if args.waypoints is None or args.box_only
            else hashlib.sha256(args.waypoints.read_bytes()).hexdigest(),
            "waypoint_kind": "not_evaluated"
            if args.box_only
            else "explicit_numerical_example"
            if args.waypoints is None
            else "caller_supplied_nominal_joint_coordinates",
        },
        "rate_study": rate_study,
        "transmission_study": transmission_study,
        "rate_boxes": asdict(boxes),
        "trajectory": trajectory,
        "complete_capacity_margin": None,
        "remaining_gates": [
            "No calibrated source-channel to physical-shaft map",
            "Joint1/joint4/gripper physical transmission demands not modeled",
            "No inertial/friction/loss/duty demand or matching motor capacity curves",
            "Constant local pitch-radius/routing assumptions may change with mechanism",
            "No coupled cable/collision/calibrated shaft-limit or physical validation",
            "Independent rate-box maxima have separate witness states",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = build_report(args)
        encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            sys.stdout.write(encoded)
        else:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
    except (OSError, ValueError, TypeError, OverflowError) as error:
        print(f"Coupled demand study failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
