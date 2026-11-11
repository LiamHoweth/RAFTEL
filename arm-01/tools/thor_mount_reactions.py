"""Offline full-wrench interface reaction study with explicit allocation assumptions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from raftel_arm01.engineering.evidence_files import write_new_evidence
from raftel_arm01.engineering.mount_reactions import (
    ReactionChannel,
    SingularSupportLayout,
    Wrench,
    solve_reactions,
    transform_wrench,
)
from raftel_arm01.kinematics.thor_frames import load_frame_graph

ROOT = Path(__file__).resolve().parents[1]
FRAME = "native_cad_source_zero_scenario"
INPUTS = {
    "frames": "config/thor-frames-v1.json",
    "interfaces": "hardware/cad/thor-fabrication-interfaces.json",
    "gravity_study": "hardware/cad/thor-wrist-load-study-v2.json",
}


def _read(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError(f"duplicate JSON key: {name}")
            result[name] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def case_input(case: dict) -> tuple[Wrench, tuple[ReactionChannel, ...], dict]:
    """Parse explicit SI inputs; unknown frames and constraint choices are not filled in."""
    if not isinstance(case, dict) or type(case.get("schema_version")) is not int:
        raise ValueError("mount case must be a revisioned JSON object")
    if case["schema_version"] != 1 or case.get("evidence_class") != "conditional_mount_input":
        raise ValueError("unsupported mount input schema or evidence class")
    if case.get("units") != {"force": "N", "moment": "N*m", "length": "m"}:
        raise ValueError("mount case must declare SI units")
    if not isinstance(case.get("channels"), list):
        raise ValueError("mount case channels must be a list")
    try:
        wrench = Wrench(**case["wrench"])
        channels = tuple(ReactionChannel(**channel) for channel in case["channels"])
    except (TypeError, KeyError) as error:
        raise ValueError("incomplete or unexpected wrench/channel input fields") from error
    options = case.get("allocation")
    if not isinstance(options, dict) or options.get("method") != "minimum_weighted_force_norm":
        raise ValueError("explicit minimum weighted-force-norm allocation assumption required")
    if set(options) != {"method", "evidence", "characteristic_length_m"}:
        raise ValueError("allocation must supply method, evidence and characteristic length")
    return (
        wrench,
        channels,
        {
            "allocation_evidence": options["evidence"],
            "characteristic_length_m": options["characteristic_length_m"],
        },
    )


def analyze_case(case: dict) -> dict:
    wrench, channels, options = case_input(case)
    return solve_reactions(wrench, channels, **options)


def _channels(points_m: list[tuple[float, float, float]], prefix: str, *, normal_only=False):
    result = []
    directions = ((0, 0, 1),) if normal_only else ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    axes = ("z",) if normal_only else ("x", "y", "z")
    for index, (x, y, z) in enumerate(points_m):
        transform = ((1, 0, 0, x), (0, 1, 0, y), (0, 0, 1, z), (0, 0, 0, 1))
        for axis, direction in zip(axes, directions, strict=True):
            result.append(
                ReactionChannel(
                    f"{prefix}-{index}-{axis}",
                    transform,
                    direction,
                    1,
                    "bilateral",
                    FRAME,
                    "Assumed point-force component; actual contact/preload/stiffness unmeasured",
                )
            )
    return tuple(result)


def build_study(root: Path = ROOT) -> dict:
    data = {role: _read(root / path) for role, path in INPUTS.items()}
    interfaces = data["interfaces"]
    source_holes = [
        (*[coordinate / 1000 for coordinate in point], 0.0)
        for point in interfaces["base_mount_summary"]["hole_centers_xy_mm"]
    ]
    outer = interfaces["proposed_adapter"]["candidate_outer_bounds_mm"]
    # The 25 mm inset is a study coordinate choice, not a selected clamp pad.
    inset_mm = 25
    corners = [
        ((outer["x_min"] + inset_mm) / 1000, (outer["y_min"] + inset_mm) / 1000, 0),
        ((outer["x_max"] - inset_mm) / 1000, (outer["y_min"] + inset_mm) / 1000, 0),
        ((outer["x_max"] - inset_mm) / 1000, (outer["y_max"] - inset_mm) / 1000, 0),
        ((outer["x_min"] + inset_mm) / 1000, (outer["y_max"] - inset_mm) / 1000, 0),
    ]
    layouts = {
        "source_bore_points_three_bilateral_components_each": _channels(source_holes, "bore"),
        "proposed_blank_corner_points_three_bilateral_components_each": _channels(
            corners, "corner"
        ),
    }
    matched = [
        case
        for case in data["gravity_study"]["cases"]
        if case["material_reference"]["family"] == "PLA"
        and case["printed_effective_whole_part_solid_fraction"] == 0.5
        and case["scenario_name"] == "bevel_sign_positive"
    ]
    if len(matched) != 1:
        raise ValueError("expected one preserved PLA half-solid positive-phase case")
    frozen_case = matched[0]
    graph = load_frame_graph(root / INPUTS["frames"])
    native_from_nominal = graph.transform("native_cad", "base_link")
    cases = []
    for pose_name in ("upright", "shoulder_horizontal"):
        pose = frozen_case["poses"][pose_name]
        payloads = [case for case in pose["payload_cases"] if case["payload_kg"] == 0.2]
        if len(payloads) != 1:
            raise ValueError("missing frozen 0.2 kg gravity case")
        raw = payloads[0]["gravity_wrench_about_frame_origin"]
        nominal = Wrench(
            raw["external_force_n"], raw["external_moment_nm"], raw["reference_m"], "base_link"
        )
        external = transform_wrench(nominal, native_from_nominal, FRAME)
        for name, channels in layouts.items():
            result = solve_reactions(
                external,
                channels,
                characteristic_length_m=0.1,
                allocation_evidence="Equal weights minimize force norm; not measured stiffness",
            )
            cases.append(
                {
                    "name": f"{pose_name}_payload_0.2kg_{name}",
                    "joint_angles_rad": pose["joint_angles_rad"],
                    "payload_kg": 0.2,
                    "load_source": "preserved v2 frozen-jaw gravity study; not physical evidence",
                    "result": result,
                }
            )
    synthetic = Wrench((12, -7, -60), (3, -4, 1.2), (0, 0, 0), FRAME)
    for name, channels in layouts.items():
        cases.append(
            {
                "name": f"synthetic_full_wrench_{name}",
                "evidence_class": "synthetic_wrench_fixture_not_a_physical_load_case",
                "result": solve_reactions(
                    synthetic,
                    channels,
                    characteristic_length_m=0.1,
                    allocation_evidence="Equal diagnostic weights; arbitrary synthetic full wrench",
                ),
            }
        )
    rejected = []
    incomplete_layouts = {
        "four_normal_only_corner_points": _channels(corners, "normal", normal_only=True),
        "two_fully_constrained_point_contacts": _channels([corners[0], corners[2]], "two-point"),
    }
    for name, channels in incomplete_layouts.items():
        try:
            solve_reactions(
                synthetic,
                channels,
                characteristic_length_m=0.1,
                allocation_evidence="Deliberately incomplete support fixture",
            )
        except SingularSupportLayout as error:
            rejected.append({"name": name, "diagnostic": error.diagnostic})
        else:
            raise ValueError("deliberately incomplete support layout was unexpectedly accepted")
    return {
        "schema_version": 1,
        "evidence_class": "conditional_rigid_interface_study_not_mount_or_fabrication_release",
        "input_sha256": {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in INPUTS.values()
        },
        "source_revision": interfaces["source_revision"],
        "frame_registration": {
            "frame": FRAME,
            "native_from_nominal": native_from_nominal,
            "status": "conditional_source_zero_frame_scenario_not_bench_calibration",
            "assumption": (
                "BaseBot LCS_Bot identity is treated as coincident with native assembly zero. "
                "Source hole dimensions are preserved; no measured bench registration is supplied."
            ),
            "physical_bench_transform": None,
        },
        "layouts": {
            "source_bore_points_m": source_holes,
            "proposed_blank_corner_points_m": corners,
            "proposed_corner_inset_mm": inset_mm,
            "all_three_component_contacts_are_assumed": True,
            "contacts_or_preload_verified": False,
            "proposed_blank_dimensions_mm": interfaces["proposed_adapter"][
                "candidate_outer_dimensions_mm"
            ],
            "plate_thickness_m": None,
        },
        "cases": cases,
        "rejected_incomplete_support_models": rejected,
        "remaining_gates": [
            "Bench dimensions, plate grade/thickness and real clamp contact locations/areas",
            "Preload, contact availability, friction, slip, pullout and desk crushing",
            "Plate bending, fastener bearing/strength, printed-base creep and gravity restraint",
            "Actual mass/COM, dynamic/cable forces and measured source-to-bench registration",
        ],
        "qualification": {
            "physical_mount_feasibility_established": False,
            "manufacturing_release": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--case-file", type=Path, help="explicit SI wrench/support case; otherwise frozen study"
    )
    args = parser.parse_args(argv)
    try:
        result = analyze_case(_read(args.case_file)) if args.case_file else build_study()
        write_new_evidence(
            [(args.output, json.dumps(result, indent=2, allow_nan=False) + "\n")],
            protected_inputs=(
                [args.case_file] if args.case_file else [ROOT / path for path in INPUTS.values()]
            ),
        )
    except SingularSupportLayout as error:
        parser.exit(2, json.dumps(error.diagnostic, allow_nan=False) + "\n")
    except (OSError, TypeError, KeyError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"evidence_class": result["evidence_class"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
