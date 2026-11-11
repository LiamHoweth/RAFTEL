"""Offline scalar joint-path study from caller-explicit rate assumptions.

No source acceleration limit is invented. A separate rate-study JSON file is
required, with synthetic/assumed provenance. Output is a new diagnostic report,
never controller commands or a physical path-clearance claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

from raftel_arm01.kinematics.thor_constraints import ConstraintSet, load_constraints
from raftel_arm01.kinematics.thor_frames import _unique_object
from raftel_arm01.kinematics.thor_model import SOURCE_REVISION, _angles
from raftel_arm01.kinematics.thor_trajectory import plan_quintic_path

ROOT = Path(__file__).resolve().parents[1]


def load_rate_study(path: Path, baseline: ConstraintSet) -> tuple[ConstraintSet, dict]:
    data = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
    required = {
        "schema_version",
        "revision",
        "units",
        "evidence_class",
        "evidence",
        "velocity_limits_rad_s",
        "acceleration_limits_rad_s2",
    }
    if (
        not isinstance(data, dict)
        or set(data) != required
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["units"] != {"velocity": "rad/s", "acceleration": "rad/s^2"}
    ):
        raise ValueError(
            "rate study requires the documented schema1 fields and rad/s,rad/s^2 units"
        )
    if not isinstance(data["evidence_class"], str) or data["evidence_class"] not in {
        "synthetic",
        "assumed",
    }:
        raise ValueError("offline rate study evidence_class must be synthetic or assumed")
    if not isinstance(data["evidence"], str) or not data["evidence"].strip():
        raise ValueError("rate study requires explicit evidence")
    velocity, acceleration = (
        _angles(data["velocity_limits_rad_s"]),
        _angles(data["acceleration_limits_rad_s2"]),
    )
    bounds = baseline.bounds("study")
    evidence = (
        f"{data['evidence_class']}: {data['evidence']}; "
        "numerical study only, no physical limit qualification"
    )
    updated = ConstraintSet(
        data["revision"],
        tuple(
            replace(
                joint,
                study=replace(
                    bound,
                    max_velocity_rad_s=v,
                    max_acceleration_rad_s2=a,
                    evidence=evidence + f"; position evidence: {bound.evidence}",
                ),
            )
            for joint, bound, v, a in zip(
                baseline.joints, bounds, velocity, acceleration, strict=True
            )
        ),
    )
    return updated, data


def load_waypoints(path: Path | None) -> tuple[tuple[float, ...], ...]:
    if path is None:
        return ((0.0,) * 6, (0.2, -0.3, 0.4, -0.5, 0.6, -0.7), (0.1, -0.2, 0.3, -0.4, 0.5, -0.6))
    data = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
    expected = {"schema_version", "model_source_revision", "joint_order", "units", "waypoints_rad"}
    if (
        not isinstance(data, dict)
        or set(data) != expected
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["model_source_revision"] != SOURCE_REVISION
        or data["joint_order"] != [f"joint_{i}" for i in range(1, 7)]
        or data["units"] != "rad"
    ):
        raise ValueError(
            "waypoints need schema1, matching source revision, joint_1..6 order and rad units"
        )
    values = data["waypoints_rad"]
    if not isinstance(values, list) or not 2 <= len(values) <= 1000:
        raise ValueError("waypoint file needs2..1000 waypoints")
    return tuple(_angles(value) for value in values)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--rate-study",
        type=Path,
        required=True,
        help="Explicit synthetic/assumed six-axis velocity and acceleration JSON",
    )
    result.add_argument(
        "--constraints", type=Path, default=ROOT / "config/thor-constraints-v1.json"
    )
    result.add_argument(
        "--waypoints",
        type=Path,
        help="Optional revisioned nominal joint waypoint JSON; "
        "otherwise uses labeled example points",
    )
    result.add_argument("--sample-period-s", type=float, default=0.1)
    result.add_argument("--max-samples", type=int, default=10000)
    result.add_argument("--max-total-duration-s", type=float, default=300)
    result.add_argument("--output", type=Path, help="New JSON path; existing evidence is preserved")
    return result


def build_report(args: argparse.Namespace) -> dict:
    baseline = load_constraints(args.constraints)
    constraints, rate_study = load_rate_study(args.rate_study, baseline)
    waypoints = load_waypoints(args.waypoints)
    path = plan_quintic_path(waypoints, constraints, max_total_duration_s=args.max_total_duration_s)
    samples = path.sample_uniform(args.sample_period_s, max_samples=args.max_samples)
    return {
        "schema_version": 1,
        "validation_class": path.validation_class,
        "model_source_revision": SOURCE_REVISION,
        "joint_order": [f"joint_{i}" for i in range(1, 7)],
        "units": {"time": "s", "position": "rad", "velocity": "rad/s", "acceleration": "rad/s^2"},
        "inputs": {
            "constraints_sha256": hashlib.sha256(args.constraints.read_bytes()).hexdigest(),
            "rate_study_sha256": hashlib.sha256(args.rate_study.read_bytes()).hexdigest(),
            "waypoints_sha256": None
            if args.waypoints is None
            else hashlib.sha256(args.waypoints.read_bytes()).hexdigest(),
            "waypoint_kind": "explicit_numerical_example"
            if args.waypoints is None
            else "caller_supplied_nominal_joint_coordinates",
        },
        "rate_study": rate_study,
        "constraints_revision": constraints.revision,
        "waypoints_rad": waypoints,
        "duration_s": path.duration_s,
        "segments": [
            {
                "start_rad": segment.start_rad,
                "end_rad": segment.end_rad,
                "duration_s": segment.duration_s,
                "analytic_peak_abs_velocity_rad_s": segment.peak_rates()[0],
                "analytic_peak_abs_acceleration_rad_s2": segment.peak_rates()[1],
            }
            for segment in path.segments
        ],
        "sample_period_s": args.sample_period_s,
        "samples": [asdict(sample) for sample in samples],
        "remaining_gates": [
            "No source or calibrated acceleration capability established",
            "No coupled shaft/cable/collision or intersample clearance analysis",
            "No dynamics/actuator capacity or hardware backend",
            "Rest at each waypoint; jerk discontinuities are not constrained",
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
            with args.output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
            print(f"Wrote offline scalar trajectory study: {args.output}")
        return 0
    except (ValueError, OSError, OverflowError) as error:
        print(f"Trajectory study failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
