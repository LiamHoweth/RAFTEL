"""Reproduce explicitly synthetic linear swept-box witnesses, never robot paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

from raftel_arm01.kinematics.thor_collision import BoxProxy, intersect_boxes
from raftel_arm01.kinematics.thor_frames import IDENTITY
from raftel_arm01.kinematics.thor_swept_boxes import (
    LINEAR_TRANSLATION_ASSUMPTION,
    sweep_linear_translation,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture_box(name, center, half) -> BoxProxy:
    transform = tuple((*IDENTITY[i][:3], center[i]) for i in range(3)) + (IDENTITY[3],)
    return BoxProxy(
        name,
        "synthetic_world_m",
        half,
        transform,
        "Explicit synthetic study box; not Thor or workstation geometry",
        "synthetic_exact_box",
    )


def build_study() -> dict:
    obstacle = fixture_box("synthetic_static_obstacle", (0, 0, 0), (0.5, 0.5, 0.5))
    definitions = (
        (
            "endpoints_separate_midpath_overlap",
            (-2, 0, 0),
            (2, 0, 0),
            (0.25,) * 3,
            obstacle,
            (5 / 16, 11 / 16),
        ),
        ("stationary_separated", (-2, 0, 0), (-2, 0, 0), (0.25,) * 3, obstacle, None),
        ("stationary_inside", (0, 0, 0), (0, 0, 0), (0.25,) * 3, obstacle, (0, 1)),
        (
            "grazing_face_contact",
            (-2, 0.75, 0),
            (2, 0.75, 0),
            (0.25,) * 3,
            obstacle,
            (5 / 16, 11 / 16),
        ),
        ("start_inside_then_exit", (0, 0, 0), (2, 0, 0), (0.25,) * 3, obstacle, (0, 3 / 8)),
        ("endpoint_only_contact", (-2, 0, 0), (-0.75, 0, 0), (0.25,) * 3, obstacle, (1, 1)),
        (
            "zero_width_point_crossing",
            (-1, 0, 0),
            (1, 0, 0),
            (0, 0, 0),
            fixture_box("synthetic_static_point", (0, 0, 0), (0, 0, 0)),
            (0.5, 0.5),
        ),
    )
    cases = []
    for name, start_point, end_point, half, fixed, expected in definitions:
        start, end = (
            fixture_box("synthetic_moving_box", point, half) for point in (start_point, end_point)
        )
        result = sweep_linear_translation(
            start,
            end,
            fixed,
            assumption=LINEAR_TRANSLATION_ASSUMPTION,
            motion_evidence=(
                "Declared constant-orientation linear centre path for this synthetic fixture only"
            ),
            numerical_tolerance_m=0,
        )
        if result.overlap_parameter_interval != expected:
            raise ValueError("synthetic closed-form witness disagrees")
        cases.append(
            {
                "case_id": name,
                "moving_start": asdict(start),
                "moving_end": asdict(end),
                "static_obstacle": asdict(fixed),
                "endpoint_proxy_relations": [
                    intersect_boxes(value, fixed, numerical_tolerance_m=0).relation
                    for value in (start, end)
                ],
                "hand_computed_overlap_interval": expected,
                "sweep_result": asdict(result),
            }
        )
    paths = (
        "src/raftel_arm01/kinematics/thor_collision.py",
        "src/raftel_arm01/kinematics/thor_swept_boxes.py",
    )
    return {
        "schema_version": 1,
        "evidence_class": (
            "synthetic_fixed_orientation_linear_AABB_sweeps_not_robot_path_validation"
        ),
        "input_bindings": [
            {"path": path, "raw_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
            for path in paths
        ],
        "assumption": LINEAR_TRANSLATION_ASSUMPTION,
        "parameter": (
            "dimensionless u in [0,1]; centre(u)=(1-u)*start+u*end; "
            "no joint interpolation or trajectory timing inferred"
        ),
        "numerical_policy": {
            "padding_m": 0.0,
            "contact": "closed intervals; singleton tangency retained",
            "arithmetic": (
                "floating-point analytic slabs, not certified interval arithmetic; "
                "unrepresentable width/crossing calculations reject"
            ),
        },
        "case_count": len(cases),
        "cases": cases,
        "robot_binding_gates": [
            (
                "Saved-zero mounted bounds provide one cached numerical scene, "
                "not nonzero full-body transforms or enclosures."
            ),
            (
                "Joint quintics do not imply linearly translating fixed-orientation body boxes; "
                "joint rotation/curved motion is rejected by this API assumption contract."
            ),
            (
                "Source/physical enclosure margins, full obstacle/held-object coverage, "
                "intended contacts and real path timing remain unverified."
            ),
        ],
        "actual_robot_sweep_cases": [],
        "robot_swept_clearance": None,
        "physical_collision_free": None,
        "qualification": {
            key: False
            for key in (
                "complete_T2_gate",
                "robot_dynamic_binding",
                "source_enclosure_verified",
                "joint_path_collision_screened",
                "physical_clearance",
                "hardware_motion_authorized",
                "manufacturing_release",
            )
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("output must be new; existing evidence is preserved")
        result = build_study()
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(
            "Synthetic swept-box cases:",
            result["case_count"],
            "; robot swept clearance remains null",
        )
        return 0
    except (ValueError, OSError, TypeError, KeyError, OverflowError) as error:
        print(f"Synthetic swept-box study failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
