"""Sparse declared drive-loss/radius/sharing sensitivity; no rated capacity.

Frozen gravity countertorques are paired with caller-declared instantaneous
rates. Each gearbox's output power determines its own direction of flow.
Zero-rate holding effort never receives a moving-efficiency multiplier.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath

import thor_elbow_loads as elbow

from raftel_arm01.engineering import scenarios
from raftel_arm01.engineering.scenarios import canonical_sha256, finite_number
from raftel_arm01.kinematics import thor_transmission
from raftel_arm01.kinematics.thor_transmission import ElbowTransmission

ROOT = Path(__file__).resolve().parents[1]
MAX_CASES = 256
MAX_FILE_BYTES = 16 * 1024**2
EVIDENCE = "conditional_analytical_drive_sensitivity"
UNITS = {"radius": "m", "effort": "N*m", "rate": "rad/s", "power": "W"}
SOURCE_REVISIONS = {
    "thor_cad": "286b081fe6f056d87c379b884781ef77ff6a0159",
    "thor_ros": "e11a56b5aa0d89f0b68a3ea7bd084eab4a050952",
}
SOURCE_UNITS = {"position": "m", "mass": "kg", "angle": "rad", "gravity": "m/s^2", "torque": "N*m"}


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise ValueError(name + " requires bounded nonempty text")
    return value


def _keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(name + " requires exactly " + str(sorted(expected)))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("expected lowercase SHA-256")
    return value


def read_json(path: Path) -> tuple[dict, bytes]:
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("drive-study input exceeds byte bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite JSON constant: " + value)

    def number(value):
        return finite_number(float(value))

    try:
        data = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=constant,
            parse_float=number,
        )
    except (RecursionError, UnicodeError) as error:
        raise ValueError("invalid UTF-8 or excessively nested JSON") from error
    if not isinstance(data, dict):
        raise ValueError("drive-study JSON root must be an object")
    return data, raw


def validate_request(value: dict) -> dict:
    _keys(
        value,
        {
            "schema_version",
            "revision",
            "evidence_class",
            "units",
            "source_load_study",
            "transmission",
            "reference_parameter_id",
            "parameter_points",
            "operating_points",
            "model_scope",
        },
        "drive sensitivity request",
    )
    try:
        data = copy.deepcopy(value)
    except RecursionError as error:
        raise ValueError("request exceeds bounded nesting") from error
    if (
        type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["evidence_class"] != EVIDENCE
        or data["units"] != UNITS
    ):
        raise ValueError("request requires schema 1, conditional evidence and explicit SI units")
    for name in ("revision", "model_scope", "reference_parameter_id"):
        _text(data[name], name)
    binding = data["source_load_study"]
    _keys(binding, {"path", "sha256", "canonical_sha256"}, "source binding")
    path = PurePosixPath(_text(binding["path"], "source path"))
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in binding["path"]
        or ":" in binding["path"]
        or path.suffix != ".json"
    ):
        raise ValueError("source path must be a relative project JSON path")
    _digest(binding["sha256"])
    _digest(binding["canonical_sha256"])
    transmission = data["transmission"]
    _keys(
        transmission,
        {
            "driver_radius_m",
            "elbow_gearbox_ratio",
            "shoulder_branch_ratio",
            "carrier_coupling",
            "belt_sign",
            "evidence",
        },
        "transmission",
    )
    _text(transmission["evidence"], "transmission evidence")
    for name in ("parameter_points", "operating_points"):
        if not isinstance(data[name], list) or not 1 <= len(data[name]) <= 64:
            raise ValueError(name + " requires 1..64 declared points")
    if len(data["parameter_points"]) * len(data["operating_points"]) > MAX_CASES:
        raise ValueError("declared sample product exceeds " + str(MAX_CASES))
    parameter_ids, parameter_values = set(), set()
    for point in data["parameter_points"]:
        _keys(
            point,
            {"id", "drum_radius_m", "gearbox_efficiencies", "shoulder_b_fraction", "evidence"},
            "parameter point",
        )
        identifier = _text(point["id"], "parameter id")
        _text(point["evidence"], "parameter evidence")
        if identifier in parameter_ids:
            raise ValueError("duplicate parameter point id")
        parameter_ids.add(identifier)
        point["drum_radius_m"] = finite_number(point["drum_radius_m"])
        point["shoulder_b_fraction"] = finite_number(point["shoulder_b_fraction"])
        if point["drum_radius_m"] <= 0 or not 0 <= point["shoulder_b_fraction"] <= 1:
            raise ValueError("radius must be positive and allocation in [0,1]")
        _keys(point["gearbox_efficiencies"], {"B", "C", "E"}, "gearbox efficiencies")
        for name, efficiency in point["gearbox_efficiencies"].items():
            efficiency = finite_number(efficiency)
            if not 0 < efficiency <= 1:
                raise ValueError("efficiency must lie in (0,1]")
            point["gearbox_efficiencies"][name] = efficiency
        key = canonical_sha256(
            {k: point[k] for k in ("drum_radius_m", "gearbox_efficiencies", "shoulder_b_fraction")}
        )
        if key in parameter_values:
            raise ValueError("duplicate parameter values")
        parameter_values.add(key)
        ElbowTransmission(
            **{k: v for k, v in transmission.items() if k != "evidence"},
            drum_radius_m=point["drum_radius_m"],
        )
    if data["reference_parameter_id"] not in parameter_ids:
        raise ValueError("reference parameter point is missing")
    operating_ids = set()
    for point in data["operating_points"]:
        _keys(point, {"id", "load_case", "joint_rates_rad_s", "evidence"}, "operating point")
        identifier = _text(point["id"], "operating id")
        _text(point["load_case"], "load case")
        _text(point["evidence"], "operating evidence")
        if identifier in operating_ids:
            raise ValueError("duplicate operating point id")
        operating_ids.add(identifier)
        rates = point["joint_rates_rad_s"]
        if not isinstance(rates, list) or len(rates) != 2:
            raise ValueError("q2/q3 require two explicit instantaneous rates")
        point["joint_rates_rad_s"] = [finite_number(rate) for rate in rates]
    return data


def _port(output_effort: float, output_rate: float, ratio: float, efficiency: float) -> dict:
    torque, speed, ratio, efficiency = map(
        finite_number, (output_effort, output_rate, ratio, efficiency)
    )
    if ratio <= 0 or not 0 < efficiency <= 1:
        raise ValueError("port ratio/efficiency is invalid")
    power = finite_number(torque * speed)
    input_rate = finite_number(ratio * speed)
    if speed != 0 and input_rate == 0:
        raise ValueError("nonzero output rate underflowed at the input shaft")
    if torque == 0:
        flow, input_effort, loss = "zero_transmitted_effort", 0.0, 0.0
    elif speed == 0:
        flow, input_effort, loss = "zero_rate_nonzero_effort_unknown_holding", None, 0.0
    else:
        if power == 0:
            raise ValueError("nonzero effort/rate product underflowed; flow cannot be inferred")
        flow = "motoring" if power > 0 else "backdriving"
        input_effort = elbow.signed_lossy_input_effort(torque, ratio, efficiency, flow)
        if input_effort == 0:
            raise ValueError("nonzero moving effort underflowed at the input shaft")
        loss = finite_number(
            power * ((1 / efficiency - 1) if flow == "motoring" else (efficiency - 1))
        )
    input_power = 0.0 if input_effort is None else finite_number(input_effort * input_rate)
    if power != 0 and input_power == 0:
        raise ValueError("nonzero moving power underflowed at the input shaft")
    if not math.isclose(input_power, power + loss, rel_tol=1e-11, abs_tol=0.0):
        raise ValueError("declared port failed its mechanical power identity")
    return {
        "output_effort_nm": torque,
        "output_rate_rad_s": speed,
        "input_rate_rad_s": input_rate,
        "gear_ratio": ratio,
        "declared_efficiency": efficiency,
        "power_flow": flow,
        "moving_efficiency_applied": flow in {"motoring", "backdriving"},
        "input_effort_nm": input_effort,
        "output_mechanical_power_w": power,
        "input_mechanical_power_w": input_power,
        "modeled_mechanical_loss_w": loss,
        "power_balance_residual_w": finite_number(input_power - power - loss),
        "holding_electrical_or_thermal_loss_w": None,
    }


def evaluate_operating_point(
    t2_nm: float,
    t3_nm: float,
    rates_rad_s: list[float],
    model: ElbowTransmission,
    share: float,
    efficiencies: dict,
) -> dict:
    """Three independent lossy gearboxes around the existing lossless carrier map."""
    if (
        not isinstance(model, ElbowTransmission)
        or not isinstance(rates_rad_s, (tuple, list))
        or len(rates_rad_s) != 2
    ):
        raise ValueError("existing elbow model and two declared rates required")
    t2, t3, q2dot, q3dot, share = map(finite_number, (t2_nm, t3_nm, *rates_rad_s, share))
    if not 0 <= share <= 1:
        raise ValueError("shoulder allocation must lie in [0,1]")
    _keys(efficiencies, {"B", "C", "E"}, "efficiencies")
    ideal = model.ideal_rotor_efforts(t2, t3, share)
    elbow_output = ideal["elbow_gearbox_output_nm"]
    shoulder_output = ideal["shoulder_branch_total_joint_nm"]
    if t3 != 0 and elbow_output == 0:
        raise ValueError("nonzero elbow demand underflowed at the output shaft")
    shoulder_b = finite_number(share * shoulder_output)
    shoulder_c = finite_number((1 - share) * shoulder_output)
    if shoulder_output != 0 and (
        (share != 0 and shoulder_b == 0) or (share != 1 and shoulder_c == 0)
    ):
        raise ValueError("nonzero allocated shoulder effort underflowed")
    phi_dot = finite_number(
        model.carrier_coupling * q2dot + model.belt_sign * model.belt_ratio * q3dot
    )
    ports = {
        "B": _port(
            shoulder_b,
            q2dot,
            model.shoulder_branch_ratio,
            efficiencies["B"],
        ),
        "C": _port(
            shoulder_c,
            q2dot,
            model.shoulder_branch_ratio,
            efficiencies["C"],
        ),
        "E": _port(elbow_output, phi_dot, model.elbow_gearbox_ratio, efficiencies["E"]),
    }
    joint_power = finite_number(t2 * q2dot + t3 * q3dot)
    out_power = finite_number(
        math.fsum(port["output_mechanical_power_w"] for port in ports.values())
    )
    input_power = finite_number(
        math.fsum(port["input_mechanical_power_w"] for port in ports.values())
    )
    loss = finite_number(math.fsum(port["modeled_mechanical_loss_w"] for port in ports.values()))
    scale = max(abs(joint_power), abs(out_power), abs(input_power), abs(loss))
    residual = finite_number(input_power - joint_power - loss)
    if (
        not math.isclose(joint_power, out_power, rel_tol=1e-11, abs_tol=1e-11 * scale)
        or abs(residual) > 1e-11 * scale
    ):
        raise ValueError("declared transmission failed its mechanical power identity")
    projected_rates = model.rotor_coordinates(q2dot, q3dot)
    if any(
        not math.isclose(ports[key]["input_rate_rad_s"], expected, rel_tol=1e-12, abs_tol=1e-12)
        for key, expected in zip(("B", "C", "E"), projected_rates, strict=True)
    ):
        raise ValueError("gearbox rates disagree with existing coupled coordinate map")
    return {
        "demanded_joint_countertorques_nm": [t2, t3],
        "declared_joint_rates_rad_s": [q2dot, q3dot],
        "lossless_reference_efforts": ideal,
        "ports": ports,
        "carrier_reaction_from_elbow_output_nm": finite_number(
            model.carrier_coupling * elbow_output
        ),
        "total_joint_mechanical_power_w": joint_power,
        "sum_output_port_power_w": out_power,
        "total_input_mechanical_power_w": input_power,
        "total_modeled_mechanical_loss_w": loss,
        "power_balance_residual_w": residual,
        "unknown_static_input_effort_ports": [
            name for name, port in ports.items() if port["input_effort_nm"] is None
        ],
        "complete_actuator_effort_or_capacity": None,
    }


def _summaries(cases: list[dict], request: dict) -> tuple[list[dict], list[dict]]:
    extrema = []
    for port in ("B", "C", "E"):
        known = [
            case for case in cases if case["result"]["ports"][port]["input_effort_nm"] is not None
        ]
        witness = (
            max(known, key=lambda case: abs(case["result"]["ports"][port]["input_effort_nm"]))
            if known
            else None
        )
        extrema.append(
            {
                "port": port,
                "known_modeled_effort_samples": len(known),
                "unknown_static_effort_samples": len(cases) - len(known),
                "sampled_max_absolute_modeled_input_effort_nm": None
                if witness is None
                else abs(witness["result"]["ports"][port]["input_effort_nm"]),
                "witness_case_id": None if witness is None else witness["case_id"],
                "witness": witness,
                "unknown_cases_bound_or_replaced_with_zero": False,
            }
        )
    reference = request["reference_parameter_id"]
    by_key = {
        (case["operating_point"]["id"], case["parameter_point"]["id"]): case for case in cases
    }
    reference_point = next(p for p in request["parameter_points"] if p["id"] == reference)
    contrasts = []
    axes = ("drum_radius_m", "gearbox_efficiencies", "shoulder_b_fraction")
    for parameter in request["parameter_points"]:
        changed = [axis for axis in axes if parameter[axis] != reference_point[axis]]
        if len(changed) != 1:
            continue
        for port in ("B", "C", "E"):
            comparisons, unknown = [], 0
            for operating in request["operating_points"]:
                base, candidate = (
                    by_key[(operating["id"], reference)],
                    by_key[(operating["id"], parameter["id"])],
                )
                a, b = (
                    row["result"]["ports"][port]["input_effort_nm"] for row in (base, candidate)
                )
                if a is None or b is None:
                    unknown += 1
                else:
                    comparisons.append((abs(b - a), base, candidate))
            if comparisons:
                spread, base, candidate = max(comparisons, key=lambda row: row[0])
                contrasts.append(
                    {
                        "varied_axis": changed[0],
                        "parameter_point_id": parameter["id"],
                        "port": port,
                        "maximum_sampled_absolute_effort_change_from_reference_nm": spread,
                        "comparisons_with_unknown_static_effort": unknown,
                        "reference_witness_case_id": base["case_id"],
                        "changed_witness_case_id": candidate["case_id"],
                    }
                )
    return extrema, contrasts


def build_report(request: dict, project_root: Path = ROOT) -> dict:
    data = validate_request(request)
    root = project_root.resolve()
    binding = data["source_load_study"]
    path = (root / binding["path"]).resolve()
    if not path.is_relative_to(root):
        raise ValueError("bound load study escaped project root")
    unresolved = root / binding["path"]
    if any(parent.is_symlink() for parent in (unresolved, *unresolved.parents) if parent != root):
        raise ValueError("bound load study may not traverse a symbolic link")
    source, raw = read_json(path)
    if _sha(raw) != binding["sha256"] or canonical_sha256(source) != binding["canonical_sha256"]:
        raise ValueError("bound load study bytes/content are stale")
    if (
        type(source.get("schema_version")) is not int
        or source["schema_version"] != 1
        or source.get("units") != SOURCE_UNITS
        or source.get("source_revisions") != SOURCE_REVISIONS
        or source.get("validation_class")
        != "hash_bound_conditional_gravity_study_not_physical_validation"
        or source.get("coordinate_frame") != "thor_ros_nominal_base_link_m"
        or source.get("actuator_or_fabrication_qualification") is not False
        or source.get("pose_feasibility_or_collision_limits_validated") is not False
        or source.get("native_recompute_performed") is not False
        or source.get("full_physical_wrist_holding_torques_remain_unknown") is not True
    ):
        raise ValueError("source must be the explicit nominal-frame conditional gravity study")
    mass = source.get("mass_conservation", {})
    if (
        any(
            type(mass.get(name)) is not int or mass[name] != expected
            for name, expected in (
                ("native_leaf_count", 518),
                ("mass_record_count", 517),
                ("motor_asset_count", 7),
            )
        )
        or finite_number(mass.get("motor_mass_kg")) != 2.120
        or finite_number(mass.get("modeled_mass_kg")) < mass["motor_mass_kg"]
    ):
        raise ValueError("source mass identity/whole-motor scope differs")
    _digest(mass.get("mass_record_identity_sha256"))
    source_cases = source.get("cases")
    if (
        not isinstance(source_cases, list)
        or type(source.get("case_count")) is not int
        or source["case_count"] != len(source_cases)
    ):
        raise ValueError("source case coverage is invalid")
    by_name = {case["name"]: case for case in source_cases}
    if len(by_name) != len(source_cases):
        raise ValueError("duplicate source load case")
    cases = []
    for operating, parameter in itertools.product(
        data["operating_points"], data["parameter_points"]
    ):
        if operating["load_case"] not in by_name:
            raise ValueError("requested source load case is missing")
        source_case = by_name[operating["load_case"]]
        joints = {row["joint"]: row for row in source_case["joints"]}
        if len(joints) != len(source_case["joints"]) or any(
            joints[name]["body_membership_resolved"] is not True for name in ("joint_2", "joint_3")
        ):
            raise ValueError("source shoulder/elbow efforts require resolved, unique rows")
        t2, t3 = (
            finite_number(joints[name]["required_ideal_holding_torque_nm"])
            for name in ("joint_2", "joint_3")
        )
        model = ElbowTransmission(
            **{k: v for k, v in data["transmission"].items() if k != "evidence"},
            drum_radius_m=parameter["drum_radius_m"],
        )
        cases.append(
            {
                "case_id": f"sample-{len(cases):03d}",
                "parameter_point": copy.deepcopy(parameter),
                "operating_point": copy.deepcopy(operating),
                "source_case_canonical_sha256": canonical_sha256(source_case),
                "result": evaluate_operating_point(
                    t2,
                    t3,
                    operating["joint_rates_rad_s"],
                    model,
                    parameter["shoulder_b_fraction"],
                    parameter["gearbox_efficiencies"],
                ),
            }
        )
    extrema, contrasts = _summaries(cases, data)
    code = {
        "tools/thor_drive_sensitivity_study.py": Path(__file__),
        "tools/thor_elbow_loads.py": Path(elbow.__file__),
        "src/raftel_arm01/kinematics/thor_transmission.py": Path(thor_transmission.__file__),
        "src/raftel_arm01/engineering/scenarios.py": Path(scenarios.__file__),
    }
    for relative, actual in code.items():
        if _sha(actual.read_bytes()) != _sha((root / relative).read_bytes()):
            raise ValueError("imported model differs from bound project source: " + relative)
    return {
        "schema_version": 1,
        "validation_class": EVIDENCE,
        "request": data,
        "request_canonical_sha256": canonical_sha256(data),
        "source_load_study": binding,
        "source_revisions": source["source_revisions"],
        "source_manifest_canonical_sha256": source["manifest_canonical_sha256"],
        "source_mass_ledger_summary": copy.deepcopy(mass),
        "mass_assignments_added_removed_or_reweighted": False,
        "code_sha256": {name: _sha(path.read_bytes()) for name, path in code.items()},
        "effort_semantics": (
            "Unchanged source required_ideal_holding_torque_nm countertorques used as "
            "instantaneous output demands; not gravity-applied torque or full dynamic demand."
        ),
        "sampling": {
            "method": "product of two caller-declared sparse point lists",
            "case_count": len(cases),
            "maximum_allowed_cases": MAX_CASES,
            "certified_extrema_or_uncertainty_bounds": False,
        },
        "sampled_effort_extrema": extrema,
        "matched_reference_contrasts": contrasts,
        "cases": cases,
        "source_or_study_rates_physically_qualified": False,
        "complete_capacity_margin": None,
        "static_holding_loss_model": None,
        "regenerative_electrical_hardware_qualified": False,
        "hardware_native_or_network_access": False,
        "fabrication_or_motion_released": False,
        "limitations": [
            "Per-port gearbox efficiencies are explicit moving-power assumptions; "
            "belt/carrier stage is lossless.",
            "Carrier shoulder reaction uses elbow output effort, never loss-scaled rotor effort.",
            "Zero-rate nonzero-effort input torques remain unknown; zero mechanical power "
            "says nothing about copper/thermal holding loss.",
            "No inertia, friction, start/stop, belt compliance/slip, cables, duty, motor curves "
            "or calibrated signs/scales are modeled.",
            "Shoulder allocation and effective pitch radius are declared samples, "
            "not measured or certified ranges.",
            "Witnesses describe only sampled partial mechanical demands; "
            "different extrema need not occur together.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        request, _ = read_json(args.request)
        report = build_report(request, args.project_root)
        text = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            print(text, end="")
        else:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
