"""Check declared multi-pose jaw capture predicates without operating CAD/hardware.

A passing supplied capture is not authentication of a native run, contact
validation, physical calibration, or a manufacturing release. Synthetic inputs
remain synthetic in every output. All dimensions use GripperBot-local SI axes.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from thor_jaw_reconciliation import PINNED, read_evidence_json

from raftel_arm01.kinematics.thor_gripper import IdealThorGripper
from raftel_arm01.kinematics.thor_jaw_bodies import SOURCE_REVISION, canonical_sha256

ROOT = Path(__file__).resolve().parents[1]
FRAME = "GripperBot source Body local XYZ, metres"
POINTS = (
    "driven_pivot_m",
    "auxiliary_pivot_m",
    "driven_tip_m",
    "auxiliary_tip_m",
    "finger_driven_hole_m",
    "finger_auxiliary_hole_m",
)
AXES = ("driven_base", "auxiliary_base", "finger_driven", "finger_auxiliary")


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected finite SI number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("expected finite SI number") from error
    if not math.isfinite(result):
        raise ValueError("expected finite SI number")
    return result


def _vector(value: object) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("expected three finite SI coordinates")
    return tuple(_number(v) for v in value)


def _unit(value: object) -> tuple[float, float, float]:
    result = _vector(value)
    if not math.isclose(math.hypot(*result), 1, rel_tol=0, abs_tol=1e-9):
        raise ValueError("capture axis/normal must be a unit vector")
    return result


def _digest(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("expected lowercase SHA-256 digest")
    return value


def repair_specification(ledger: dict) -> dict:
    """Create numerical acceptance targets, never physical travel/fit ratings."""
    return {
        "schema_version": 1,
        "validation_class": "proposed_native_jaw_capture_predicates",
        "source_revision": SOURCE_REVISION,
        "original_source_sha256": dict(PINNED),
        "jaw_body_ledger_canonical_sha256": canonical_sha256(ledger),
        "coordinate_frame": FRAME,
        "configuration": "ideal_derived_candidate",
        "required_q_rad": [0, math.pi / 6, math.pi / 3],
        "numeric_targets": {
            "position_m": 1e-6,
            "loop_axis_distance_m": 1e-6,
            "link_length_m": 1e-6,
            "normal_or_axis_vector_error": 1e-8,
            "phase_rad": 1e-7,
            "aperture_m": 1e-6,
        },
        "target_basis": (
            "Numerical reproduction targets for the declared ideal model, chosen for "
            "diagnosis; these are not manufactured fit, clearance or safety tolerances."
        ),
        "required_capture_fields": {
            "per_side_points": list(POINTS),
            "per_side_axis_units": list(AXES),
            "contact_plane": ["point_m", "normal_unit"],
        },
        "rebuild_procedure": [
            "Use copied source files and isolated preferences; verify original hashes first/last.",
            "Repair active pivot support and driven phase by semantic geometry, not edge index.",
            "Retain explicit old-to-new references and every altered source dimension.",
            "Force selected-feature rebuild, save/reopen derived copies and recapture each pose.",
            "Record runtime/version, candidate hashes and measured axes/points/planes per pose.",
            "Inspect whole jaw/wrist gear interference and fixed-pin stacks in a separate gate.",
        ],
        "native_verification_complete": False,
        "contact_qualified": False,
        "retention_qualified": False,
        "usable_opening_m": None,
        "physical_calibration_qualified": False,
        "fabrication_released": False,
    }


def _validate_specification(spec: dict) -> dict:
    if (
        not isinstance(spec, dict)
        or type(spec.get("schema_version")) is not int
        or spec["schema_version"] != 1
    ):
        raise ValueError("unsupported jaw repair specification")
    if (
        spec.get("source_revision") != SOURCE_REVISION
        or spec.get("original_source_sha256") != PINNED
    ):
        raise ValueError("jaw repair specification source differs")
    if (
        spec.get("coordinate_frame") != FRAME
        or spec.get("configuration") != "ideal_derived_candidate"
    ):
        raise ValueError("jaw repair specification frame/configuration differs")
    _digest(spec.get("jaw_body_ledger_canonical_sha256"))
    for field in (
        "native_verification_complete",
        "contact_qualified",
        "retention_qualified",
        "physical_calibration_qualified",
        "fabrication_released",
    ):
        if spec.get(field) is not False:
            raise ValueError("repair specification cannot release native/physical acceptance")
    if spec.get("usable_opening_m") is not None:
        raise ValueError("usable physical opening remains unknown")
    required = spec.get("required_q_rad")
    if not isinstance(required, list) or not 3 <= len(required) <= 16:
        raise ValueError("specification needs three to sixteen distinct study poses")
    values = [_number(q) for q in required]
    if len(set(values)) != len(values):
        raise ValueError("duplicate required jaw pose")
    for q in values:
        IdealThorGripper().state(q)
    targets = spec.get("numeric_targets")
    if not isinstance(targets, dict):
        raise ValueError("missing numerical capture targets")
    for key in (
        "position_m",
        "loop_axis_distance_m",
        "link_length_m",
        "normal_or_axis_vector_error",
        "phase_rad",
        "aperture_m",
    ):
        if not 0 < _number(targets.get(key)) <= 1e-3:
            raise ValueError("capture numerical target must be positive and bounded")
    return targets


def evaluate_capture(spec: dict, capture: dict) -> dict:
    """Evaluate measured declarations; retain evidence class and unknown gates."""
    targets = _validate_specification(spec)
    if (
        not isinstance(capture, dict)
        or type(capture.get("schema_version")) is not int
        or capture["schema_version"] != 1
    ):
        raise ValueError("unsupported jaw capture schema")
    evidence = capture.get("evidence_class")
    if evidence not in ("native_selected_geometry", "synthetic_fixture"):
        raise ValueError("jaw capture needs an explicit supported evidence class")
    if (
        capture.get("coordinate_frame") != FRAME
        or capture.get("source_revision") != SOURCE_REVISION
    ):
        raise ValueError("jaw capture frame/source revision differs")
    if capture.get("original_source_sha256") != PINNED:
        raise ValueError("jaw capture original source hashes differ")
    if capture.get("jaw_body_ledger_canonical_sha256") != spec["jaw_body_ledger_canonical_sha256"]:
        raise ValueError("jaw capture refers to a stale ideal body ledger")
    configuration = capture.get("configuration")
    if configuration not in ("saved_original", "ideal_derived_candidate"):
        raise ValueError("unsupported jaw capture configuration")
    provenance = capture.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("capture provenance is required")
    if evidence == "native_selected_geometry":
        for key in ("generator", "runtime_name", "runtime_version"):
            if not isinstance(provenance.get(key), str) or not provenance[key].strip():
                raise ValueError("native capture needs generator/runtime/version")
        candidates = provenance.get("candidate_document_sha256")
        if not isinstance(candidates, dict) or not candidates:
            raise ValueError("native capture needs candidate document hashes")
        for name, digest in candidates.items():
            if (
                not isinstance(name, str)
                or not name
                or name in (".", "..")
                or any(separator in name for separator in ("/", "\\"))
                or Path(name).name != name
            ):
                raise ValueError("candidate hash keys must be document basenames")
            _digest(digest)
        if provenance.get("recompute_mode") not in ("none", "force_selected_feature_rebuild"):
            raise ValueError("native recompute mode must be explicit")
        if type(provenance.get("save_reopen_verified")) is not bool:
            raise ValueError("save/reopen evidence must be explicit")
    poses = capture.get("poses")
    if not isinstance(poses, list) or not poses or len(poses) > 32:
        raise ValueError("jaw capture needs one to thirty-two poses")
    q_values = []
    results = []
    for pose in poses:
        if not isinstance(pose, dict):
            raise ValueError("invalid jaw pose capture")
        q = pose.get("q_rad")
        if configuration == "saved_original":
            if q is not None or len(poses) != 1:
                raise ValueError("saved source has one unsolved pose and no common closing q")
        else:
            q = _number(q)
            IdealThorGripper().state(q)
            if any(abs(q - old) < 1e-9 for old in q_values):
                raise ValueError("duplicate jaw capture pose")
            q_values.append(q)
        sides = pose.get("sides")
        if not isinstance(sides, dict) or set(sides) != {"left", "right"}:
            raise ValueError("jaw capture needs both sides")
        checks = []
        phases = {}
        contacts = {}

        def record(name: str, residual: float, limit: float, checks: list = checks) -> None:
            residual = _number(residual)
            checks.append(
                {
                    "predicate": name,
                    "residual": residual,
                    "limit": limit,
                    "passed": residual <= limit,
                }
            )

        model = IdealThorGripper().state(q) if q is not None else None
        for side_index, (label, side) in enumerate((("left", -1), ("right", 1))):
            raw = sides[label]
            if not isinstance(raw, dict):
                raise ValueError("invalid side capture")
            points = {key: _vector(raw.get(key)) for key in POINTS}
            axis_units = raw.get("axis_units")
            if not isinstance(axis_units, dict) or set(axis_units) != set(AXES):
                raise ValueError("capture needs all four pivot-axis directions")
            for name, value in axis_units.items():
                unit = _unit(value)
                record(
                    f"{label}.{name}.jaw_plane_axis",
                    math.hypot(unit[0], unit[1]),
                    targets["normal_or_axis_vector_error"],
                )
            for kind in ("driven", "auxiliary"):
                pivot, tip = points[kind + "_pivot_m"], points[kind + "_tip_m"]
                hole = points["finger_" + kind + "_hole_m"]
                # All checked rotation-axis lines are normal to the jaw plane;
                # axial separation along those same lines is not a closure error.
                record(
                    f"{label}.{kind}.loop_axis_distance_m",
                    math.dist(tip[:2], hole[:2]),
                    targets["loop_axis_distance_m"],
                )
                record(
                    f"{label}.{kind}.link_length_m",
                    abs(math.dist(pivot[:2], tip[:2]) - 0.035),
                    targets["link_length_m"],
                )
                expected_pivot = (
                    side * (0.0145 if kind == "driven" else 0.006),
                    0.0325 if kind == "driven" else 0.051,
                )
                record(
                    f"{label}.{kind}.base_pivot_xy_m",
                    math.dist(pivot[:2], expected_pivot),
                    targets["position_m"],
                )
                if model is not None:
                    endpoint = (
                        model.driven_endpoints_m
                        if kind == "driven"
                        else model.auxiliary_endpoints_m
                    )[side_index]
                    record(
                        f"{label}.{kind}.ideal_endpoint_xy_m",
                        math.dist(tip[:2], endpoint),
                        targets["position_m"],
                    )
            a, b = points["finger_driven_hole_m"], points["finger_auxiliary_hole_m"]
            delta = (b[0] - a[0], b[1] - a[1])
            record(
                f"{label}.finger_pivot_delta_m",
                math.dist(delta, (-side * 0.0085, 0.0185)),
                targets["position_m"],
            )
            pivot, tip = points["driven_pivot_m"], points["driven_tip_m"]
            phase = math.atan2(tip[1] - pivot[1], side * (tip[0] - pivot[0]))
            phases[label] = phase
            if q is not None:
                record(f"{label}.closing_phase_rad", abs(phase - q), targets["phase_rad"])
            plane = raw.get("contact_plane")
            if not isinstance(plane, dict):
                raise ValueError("contact plane observation is required")
            point, normal = _vector(plane.get("point_m")), _unit(plane.get("normal_unit"))
            record(
                f"{label}.finger_normal_direction",
                math.dist(normal, (-side, 0, 0)),
                targets["normal_or_axis_vector_error"],
            )
            contacts[label] = (point, normal)
        record(
            "equal_opposite_link_phase_rad",
            abs(phases["left"] - phases["right"]),
            targets["phase_rad"],
        )
        left_point, left_normal = contacts["left"]
        right_point, right_normal = contacts["right"]
        record(
            "contact_normals_opposed",
            math.hypot(*(left_normal[i] + right_normal[i] for i in range(3))),
            targets["normal_or_axis_vector_error"],
        )
        gap = math.fsum((right_point[i] - left_point[i]) * left_normal[i] for i in range(3))
        if model is not None:
            record("conditional_ideal_aperture_m", abs(gap - model.gap_m), targets["aperture_m"])
        results.append(
            {
                "q_rad": q,
                "configuration": configuration,
                "measured_plane_separation_m": gap,
                "conditional_ideal_aperture_m": model.gap_m if model else None,
                "declared_geometric_predicates_passed": all(c["passed"] for c in checks),
                "checks": checks,
            }
        )
    missing = [
        q for q in spec["required_q_rad"] if not any(abs(q - actual) < 1e-9 for actual in q_values)
    ]
    metadata_complete = (
        evidence == "native_selected_geometry"
        and provenance.get("recompute_mode") == "force_selected_feature_rebuild"
        and provenance.get("save_reopen_verified") is True
    )
    return {
        "schema_version": 1,
        "validation_class": "offline_supplied_jaw_capture_predicate_check",
        "input_evidence_class": evidence,
        "configuration": configuration,
        "specification_canonical_sha256": canonical_sha256(spec),
        "capture_canonical_sha256": canonical_sha256(capture),
        "missing_required_q_rad": missing,
        "declared_geometric_predicates_passed": (
            configuration == "ideal_derived_candidate"
            and not missing
            and all(p["declared_geometric_predicates_passed"] for p in results)
        ),
        "native_rebuild_metadata_complete": metadata_complete,
        "native_verification_complete": False,
        "native_verification_note": (
            "Supplied metadata/coordinates are not authentication of native execution."
        ),
        "contact_qualified": False,
        "retention_qualified": False,
        "usable_opening_m": None,
        "physical_calibration_qualified": False,
        "fabrication_released": False,
        "poses": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--specification",
        type=Path,
        default=ROOT / "hardware/cad/thor-jaw-repair-specification.json",
    )
    parser.add_argument(
        "--ledger", type=Path, default=ROOT / "hardware/cad/thor-jaw-body-ledger.json"
    )
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("jaw acceptance report must use a new output path")
        spec = read_evidence_json(args.specification)
        ledger = read_evidence_json(args.ledger)
        if spec.get("jaw_body_ledger_canonical_sha256") != canonical_sha256(ledger):
            raise ValueError("jaw repair specification has a stale body ledger")
        capture = read_evidence_json(args.capture)
        report = evaluate_capture(spec, capture)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in (
                        "input_evidence_class",
                        "declared_geometric_predicates_passed",
                        "native_verification_complete",
                        "contact_qualified",
                        "retention_qualified",
                    )
                },
                indent=2,
            )
        )
        return 0 if report["declared_geometric_predicates_passed"] else 1
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
