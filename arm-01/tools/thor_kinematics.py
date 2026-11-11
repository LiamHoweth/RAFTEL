"""Reproduce nominal frame/Jacobian/IK diagnostics without CAD or hardware.

Run from an installed ARM-01 environment. Output paths must be new so previous
reports are preserved. A pose input is an explicit base_link scenario, not a
measured TCP or a motion instruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

from raftel_arm01.kinematics.thor_constraints import (
    audit_source_constraints,
    load_constraints,
    validate_joint_state,
)
from raftel_arm01.kinematics.thor_frames import _unique_object, load_frame_graph
from raftel_arm01.kinematics.thor_ik import IKOptions, solve_pose_ik
from raftel_arm01.kinematics.thor_jacobian import singularity_diagnostic, spatial_jacobian
from raftel_arm01.kinematics.thor_model import SOURCE_PATH, SOURCE_REVISION, forward_kinematics

ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--joints", nargs=6, type=float, default=(0.4, -0.5, 0.6, -0.7, 0.8, -0.9), metavar="RAD"
    )
    result.add_argument(
        "--target", choices=("link_6", "gripper_base", "gripper_mid_point"), default="link_6"
    )
    result.add_argument(
        "--constraints", type=Path, default=ROOT / "config/thor-constraints-v1.json"
    )
    result.add_argument("--frames", type=Path, default=ROOT / "config/thor-frames-v1.json")
    result.add_argument("--characteristic-length-m", type=float, default=0.3)
    result.add_argument(
        "--source-xacro",
        type=Path,
        help="Optional pinned local xacro for byte/source limit audit; no network access",
    )
    result.add_argument(
        "--ik-pose",
        type=Path,
        help="JSON object {frame:base_link,target:<selected target>,pose_matrix_m:[[...]]}",
    )
    result.add_argument("--max-iterations", type=int, default=160)
    result.add_argument("--max-seconds", type=float, default=2)
    result.add_argument(
        "--output", type=Path, help="New JSON path only; existing evidence is never replaced"
    )
    return result


def build_report(args: argparse.Namespace) -> dict:
    constraints = load_constraints(args.constraints)
    frames = load_frame_graph(args.frames)
    violations = validate_joint_state(args.joints, constraints)
    if violations:
        raise ValueError("joints violate the declared study: " + "; ".join(violations))
    jacobian = spatial_jacobian(args.joints, args.target)
    report = {
        "schema_version": 1,
        "validation_class": "nominal_kinematic_analysis_not_physical_or_collision_validation",
        "frame": "base_link",
        "units": {
            "position": "m",
            "angle": "rad",
            "jacobian_rows": "linear_m_per_rad_then_angular_rad_per_rad",
        },
        "source_revision": SOURCE_REVISION,
        "source_path": SOURCE_PATH,
        "inputs": {
            "frames_sha256": hashlib.sha256(args.frames.read_bytes()).hexdigest(),
            "constraints_sha256": hashlib.sha256(args.constraints.read_bytes()).hexdigest(),
            "constraints_revision": constraints.revision,
        },
        "joints_rad": tuple(args.joints),
        "target": args.target,
        "base_link_from_target": forward_kinematics(args.joints, args.target),
        "spatial_geometric_jacobian": jacobian,
        "singularity": asdict(
            singularity_diagnostic(jacobian, characteristic_length_m=args.characteristic_length_m)
        ),
        "base_link_from_native_cad": frames.transform("base_link", "native_cad"),
        "unknown_frame_edges": [
            {"parent": record.parent, "child": record.child, "evidence": record.evidence}
            for record in frames.records
            if record.parent_from_child is None
        ],
        "source_limit_audit": None,
        "ik": None,
        "remaining_gates": [
            "No native nonzero-pose geometry comparison in this run",
            "Source scalar study bounds do not establish physical stops "
            "or coupled feasible regions",
            "No calibrated bench/camera/TCP transforms",
            "No collision screening, path/dynamic validation or hardware permission",
        ],
    }
    if args.source_xacro is not None:
        report["source_limit_audit"] = audit_source_constraints(args.source_xacro, constraints)
    if args.ik_pose is not None:
        contents = args.ik_pose.read_bytes()
        pose = json.loads(contents, object_pairs_hook=_unique_object)
        if (
            not isinstance(pose, dict)
            or set(pose) != {"frame", "target", "pose_matrix_m"}
            or pose["frame"] != "base_link"
            or pose["target"] != args.target
        ):
            raise ValueError(
                "IK pose must specify exactly frame=base_link, matching target and pose_matrix_m"
            )
        report["inputs"]["ik_pose_sha256"] = hashlib.sha256(contents).hexdigest()
        report["ik"] = asdict(
            solve_pose_ik(
                pose["pose_matrix_m"],
                args.joints,
                constraints,
                target=args.target,
                options=IKOptions(
                    max_iterations=args.max_iterations,
                    max_seconds=args.max_seconds,
                    characteristic_length_m=args.characteristic_length_m,
                ),
            )
        )
    return report


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
            print(f"Wrote nominal offline diagnostic: {args.output}")
        return 0
    except (ValueError, OSError, OverflowError) as error:
        print(f"Kinematic analysis failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
