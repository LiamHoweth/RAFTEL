"""Pure host checks of captured Art1 feature/frame return, without native claims.

Supplied numbers and identities are checked, never authenticated as a native run.
Metric agreement does not establish shape equivalence or attachment semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "return_diagnostics", Path(__file__).with_name("thor_art1_diagnostics.py")
)
diagnostics = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(diagnostics)

PHASES = (
    ("restored_cached", 1.7),
    ("nominal_forced", 1.7),
    ("radius_minus_0_01_mm", 1.69),
    ("radius_plus_0_01_mm", 1.71),
    ("restored_nominal_radius", 1.7),
)
THRESHOLDS = {
    **diagnostics.TOLERANCES,
    "area_mm2": 1e-6,
    "length_mm": 1e-9,
    "placement_matrix": 1e-12,
    "global_placement_matrix": 1e-12,
    "shape_placement_matrix": 1e-12,
    "raw_native_volume_mm3": 1e-6,
}


def _expressions(value: object) -> list:
    if not isinstance(value, list) or any(
        not isinstance(pair, list)
        or len(pair) != 2
        or any(not isinstance(v, str) or not v for v in pair)
        for pair in value
    ):
        raise ValueError("expressions must be path/expression string pairs")
    if len({pair[0] for pair in value}) != len(value):
        raise ValueError("duplicate expression paths")
    return sorted(value)


def source_expressions(member: dict) -> list | None:
    """Read saved XML expression pairs, preserving exact expressions and paths."""
    if "ExpressionEngine" not in member.get("saved_properties", {}):
        return None
    pairs = []

    def visit(node):
        if node.get("tag") == "Expression":
            attrs = node["attributes"]
            pairs.append([attrs["path"], attrs["expression"]])
        for child in node.get("children", []):
            visit(child)

    visit(member.get("saved_properties", {}).get("ExpressionEngine", {}))
    return _expressions(pairs)


def source_xml_ledger(path: Path, expected_sha256: str) -> dict:
    """Authenticate exact archive bytes before reading complete source identities."""
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("source archive bytes differ from expected SHA-256")
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("Document.xml")
    root = ET.fromstring(xml_bytes)
    types = {obj.get("name"): obj.get("type") for obj in root.findall("./Objects/Object")}
    objects = root.findall("./ObjectData/Object")
    if (
        not types
        or len(types) != len(objects)
        or {obj.get("name") for obj in objects} != set(types)
    ):
        raise ValueError("incomplete source XML object identity census")
    expressions = {}
    for obj in objects:
        expressions[obj.get("name")] = _expressions(
            [
                [node.get("path"), node.get("expression")]
                for node in obj.findall(
                    "./Properties/Property[@name='ExpressionEngine']/ExpressionEngine/Expression"
                )
            ]
        )
    return {
        "source_sha256": expected_sha256,
        "document_xml_sha256": hashlib.sha256(xml_bytes).hexdigest(),
        "types": types,
        "expressions": expressions,
    }


def _attachments(value: object) -> dict:
    result = {}
    for name, record in diagnostics._mapping(value, "attachment").items():
        canonical = "Support" if name == "AttachmentSupport" else name
        if canonical in result:
            raise ValueError("ambiguous attachment property aliases")
        if canonical in {"Support", "ExternalGeometry", "MirrorPlane"}:
            record = diagnostics._mapping(record, "attachment reference")
            allowed = {name, "AttachmentSupport"} if canonical == "Support" else {name}
            if record.get("current_property") not in allowed:
                raise ValueError("unrecognized attachment property alias")
            targets = record.get("targets")
            if not isinstance(targets, list) or any(
                not isinstance(t, dict)
                or set(t) != {"target", "selector"}
                or not isinstance(t["target"], str)
                or not t["target"]
                or not isinstance(t["selector"], str)
                for t in targets
            ):
                raise ValueError("invalid ordered attachment targets")
            result[canonical] = targets
        elif canonical == "AttachmentOffset":
            result[canonical] = diagnostics._rigid_matrix(record, "AttachmentOffset")
        else:
            result[canonical] = record
    return result


def _shape_metrics(shape: dict, label: str) -> tuple[dict, list[str]]:
    shape = diagnostics._mapping(shape, label)
    if type(shape.get("is_null")) is not bool or type(shape.get("valid")) is not bool:
        raise ValueError("shape requires explicit null/valid booleans")
    if shape["is_null"]:
        return {"is_null": True, "valid": shape["valid"]}, ["null_shape"]
    result = {"is_null": False, "valid": shape["valid"]}
    for field in ("solid_count", "face_count", "edge_count"):
        value = shape.get(field)
        if type(value) is not int or value < 0:
            raise ValueError(f"{label}.{field} must be a nonnegative integer")
        result[field] = value
    if type(shape.get("unbounded_construction_geometry")) is not bool:
        raise ValueError("unbounded construction flag required")
    if shape["unbounded_construction_geometry"]:
        return result, ["unbounded_construction_geometry"]
    unmeasured = []
    for field in (
        "volume_mm3",
        "raw_native_volume_mm3",
        "area_mm2",
        "length_mm",
        "bounds_mm",
        "center_of_mass_mm",
    ):
        value = shape.get(field)
        if value is None:
            if field not in {"volume_mm3", "center_of_mass_mm"} or result["solid_count"]:
                raise ValueError(f"{label}.{field} missing for bounded geometry")
            unmeasured.append(field)
            continue
        if field in {"bounds_mm", "center_of_mass_mm"}:
            value = diagnostics._vector(value, 6 if field == "bounds_mm" else 3, field)
            if field == "bounds_mm" and any(value[i] > value[i + 1] for i in (0, 2, 4)):
                raise ValueError("reversed shape bounds")
        else:
            value = diagnostics._number(value, field, nonnegative=field != "raw_native_volume_mm3")
        result[field] = value
    result["shape_placement_matrix"] = diagnostics._rigid_matrix(
        shape.get("shape_placement_matrix"), "shape placement"
    )
    return result, unmeasured


def _difference(first: object, second: object) -> float:
    if isinstance(first, list):
        return diagnostics._max_error(first, second)
    return abs(first - second)


def _circles(obj: dict) -> list[dict]:
    value = obj.get("sketch_circle_frames", [])
    if not isinstance(value, list):
        raise ValueError("sketch circle frames must be a list")
    result = []
    for circle in value:
        circle = diagnostics._mapping(circle, "sketch circle")
        measured = {
            field: diagnostics._vector(circle.get(field), 3, field)
            for field in ("center_in_sketch_mm", "center_in_document_mm", "axis_in_document")
        }
        if abs(sum(x * x for x in measured["axis_in_document"]) - 1) > 1e-12:
            raise ValueError("circle axis must be unit length")
        measured["radius_mm"] = diagnostics._number(
            circle.get("radius_mm"), "circle radius", nonnegative=True
        )
        result.append(measured)
    return result


def _constraint_checks(phase: dict, baseline: dict, expressions: dict, radius: float) -> list[str]:
    """Compare values independently of the worker's preserved-structure flag."""
    records = diagnostics._mapping(
        phase.get("affected_constraints_and_expressions"), "affected constraints"
    )
    baseline = diagnostics._mapping(baseline, "baseline affected constraints")
    expected_names = {
        name
        for name, pairs in expressions.items()
        if any("M3BoltBodyRadius" in expression for _, expression in pairs)
    }
    if set(records) != expected_names or set(baseline) != expected_names:
        return ["affected_constraint_census"]
    failures = []
    for name, record in records.items():
        record = diagnostics._mapping(record, "affected constraint record")
        diagnostics._mapping(baseline[name], "baseline affected constraint record")
        if _expressions(record.get("expressions")) != expressions[name]:
            failures.append(f"constraint_expressions:{name}")
        constraints, initial = record.get("constraints"), baseline[name].get("constraints")
        if (
            not isinstance(constraints, list)
            or not constraints
            or not isinstance(initial, list)
            or len(constraints) != len(initial)
        ):
            raise ValueError("nonempty complete affected constraints required")
        controlled = set()
        for path, expression in expressions[name]:
            if "M3BoltBodyRadius" in expression:
                match = re.fullmatch(r"Constraints\[(\d+)\]", path)
                if match is None:
                    raise ValueError("unsupported controlled constraint path")
                controlled.add(int(match[1]))
        if not controlled <= set(range(len(constraints))):
            raise ValueError("controlled constraint index absent")
        for index, (current, original) in enumerate(zip(constraints, initial, strict=True)):
            diagnostics._mapping(current, "constraint")
            diagnostics._mapping(original, "baseline constraint")
            value = diagnostics._number(current.get("Value"), "constraint Value")
            if {k: v for k, v in current.items() if k != "Value"} != {
                k: v for k, v in original.items() if k != "Value"
            }:
                failures.append(f"constraint_structure:{name}:{index}")
            if index in controlled:
                if abs(value - radius) >= 1e-12:
                    failures.append(f"controlled_constraint_value:{name}:{index}")
            elif value != diagnostics._number(original.get("Value"), "initial constraint Value"):
                failures.append(f"uncontrolled_constraint_value:{name}:{index}")
    return failures


def compare_objects(before: dict, after: dict, order: list[str]) -> dict:
    """Keep every measured failure; no first-drift result establishes a cause."""
    rows = []
    failures, conflicts = [], []
    for name in order:
        first, second = before[name], after[name]
        errors, failed, unmeasured, baseline_gates = {}, [], [], []
        for field in ("placement_matrix", "global_placement_matrix"):
            if field in first or field in second:
                if field not in first or field not in second:
                    failed.append(field + ":missing")
                else:
                    error = _difference(first[field], second[field])
                    errors[field] = error
                    if error >= THRESHOLDS[field]:
                        failed.append(field)
        ac, bc = _circles(first), _circles(second)
        if len(ac) != len(bc):
            failed.append("sketch_circle_census")
        else:
            for index, (a, b) in enumerate(zip(ac, bc, strict=True)):
                for field in a:
                    error = _difference(a[field], b[field])
                    key = f"sketch_circle:{index}:{field}"
                    errors[key] = error
                    threshold = THRESHOLDS[
                        "hole_axis"
                        if field == "axis_in_document"
                        else "hole_radius_mm"
                        if field == "radius_mm"
                        else "hole_center_mm"
                    ]
                    if error >= threshold:
                        failed.append(key)
        if ("shape" in first) != ("shape" in second):
            failed.append("shape_presence")
        elif "shape" in first:
            a, ua = _shape_metrics(first["shape"], name)
            b, ub = _shape_metrics(second["shape"], name)
            unmeasured.extend(sorted(set(ua + ub)))
            for field in sorted(a.keys() | b.keys()):
                if field not in a or field not in b:
                    failed.append(field + ":measurement_availability_changed")
                elif field in THRESHOLDS:
                    error = _difference(a[field], b[field])
                    errors[field] = error
                    if error >= THRESHOLDS[field]:
                        failed.append(field)
                elif a[field] != b[field]:
                    failed.append(field)
            if not a.get("valid") or not b.get("valid") or a.get("is_null") or b.get("is_null"):
                baseline_gates.append("invalid_or_null_shape")
            for side, metrics in (("before", a), ("after", b)):
                if (
                    metrics.get("solid_count")
                    and "volume_mm3" in metrics
                    and "raw_native_volume_mm3" in metrics
                ):
                    error = abs(metrics["volume_mm3"] - metrics["raw_native_volume_mm3"])
                    if error >= THRESHOLDS["volume_mm3"]:
                        failed.append(f"{side}:raw_native_vs_solid_sum_volume")
                        conflicts.append(
                            {
                                "name": name,
                                "phase_side": side,
                                "kind": "raw_native_and_solid_sum_volume_disagree",
                                "absolute_error_mm3": error,
                            }
                        )
            boolean_fields = ("source_minus_candidate_mm3", "candidate_minus_source_mm3")
            if any(field in second["shape"] for field in boolean_fields):
                boolean_values = [
                    diagnostics._number(second["shape"].get(field), field, nonnegative=True)
                    for field in boolean_fields
                ]
                failed.extend(
                    field
                    for field, value in zip(boolean_fields, boolean_values, strict=True)
                    if value != 0
                )
                if boolean_values == [0, 0] and any(
                    field in failed for field in ("volume_mm3", "bounds_mm", "center_of_mass_mm")
                ):
                    conflicts.append(
                        {
                            "name": name,
                            "kind": "zero_Boolean_differences_disagree_with_other_metrics",
                        }
                    )
        rows.append(
            {
                "name": name,
                "max_absolute_errors": errors,
                "failed_checks": failed,
                "baseline_geometry_gates": baseline_gates,
                "unmeasured_fields": unmeasured,
            }
        )
        failures.extend(f"{name}:{field}" for field in failed)
    return {
        "objects": rows,
        "failures": failures,
        "metric_conflicts": conflicts,
        "first_changed_captured_feature": next(
            (r["name"] for r in rows if r["failed_checks"]), None
        ),
        "first_changed_frame": next(
            (
                r["name"]
                for r in rows
                if any(
                    k in r["failed_checks"] for k in ("placement_matrix", "global_placement_matrix")
                )
            ),
            None,
        ),
        "first_true_semantic_drift": None,
        "root_cause_established": False,
    }


def analyze_return_trace(capture: dict, source_contract: dict, source: Path | None = None) -> dict:
    if type(capture.get("schema_version")) is not int or capture["schema_version"] != 1:
        raise ValueError("unsupported trace schema")
    if capture.get("evidence_class") not in {
        "native_copied_Art1_parameter_return_trace",
        "synthetic_Art1_parameter_return_fixture",
    }:
        raise ValueError("explicit trace evidence class required")
    if capture.get("source_sha256") != source_contract.get("source_sha256"):
        raise ValueError("source identity differs")
    diagnostics._digest(capture.get("candidate_sha256"), "candidate_sha256")
    members = {m["name"]: m for m in source_contract["members"]}
    order = source_contract["ordered_body_members"]
    if capture.get("ordered_body_members") != order or len(set(order)) != len(order) or not order:
        raise ValueError("Body feature order differs or is empty")
    phases = capture.get("phases")
    if (
        not isinstance(phases, list)
        or any(not isinstance(p, dict) for p in phases)
        or [p.get("phase") for p in phases] != [p[0] for p in PHASES]
    ):
        raise ValueError("complete ordered five-phase trace required")
    failures, phase_checks, literal_changes = [], [], []
    if (
        capture.get("status") != "diagnostic_completed_not_migration_acceptance"
        or capture.get("errors") != []
    ):
        failures.append("procedure_completion")
    for field, expected in (
        ("document_saved", False),
        ("support_remapped", False),
        ("all_inputs_snapshots_and_protected_bytes_unchanged", True),
        ("owned_document_closed", True),
    ):
        if capture.get(field) is not expected:
            failures.append(field)
    if capture.get("open_documents_after_cleanup") != []:
        failures.append("owned_document_cleanup")
    baseline = diagnostics._mapping(phases[0].get("objects"), "phase objects")
    for obj in baseline.values():
        diagnostics._mapping(obj, "baseline object")
    required = (
        set(members) | set(source_contract["assembly_target_types"]) | {"Body", "Spreadsheet"}
    )
    if not required <= baseline.keys():
        raise ValueError("missing source feature or assembly target object")
    known_expressions = {
        name: pairs
        for name, member in members.items()
        if (pairs := source_expressions(member)) is not None
    }
    ledger = source_xml_ledger(source, capture["source_sha256"]) if source is not None else None
    if ledger is not None:
        known_expressions = ledger["expressions"]
        if not set(ledger["types"]) <= baseline.keys():
            raise ValueError("source XML object missing from runtime")
    effective_expressions = {
        name: known_expressions.get(name, _expressions(obj.get("expressions")))
        for name, obj in baseline.items()
    }
    for index, (phase, (label, radius)) in enumerate(zip(phases, PHASES, strict=True)):
        objects = diagnostics._mapping(phase.get("objects"), "phase objects")
        if set(objects) != set(baseline):
            raise ValueError("runtime object census changed between phases")
        current_failures = []
        current_failures.extend(
            _constraint_checks(
                phase,
                phases[0].get("affected_constraints_and_expressions"),
                effective_expressions,
                radius,
            )
        )
        if phase.get("cell_alias") != "M3BoltBodyRadius":
            current_failures.append("cell_alias")
        # Native get() serializes the controlled cell as text; no other metric permits text.
        cell = phase.get("cell_value")
        if isinstance(cell, bool) or not isinstance(cell, (str, int, float)):
            raise ValueError("invalid controlled cell value")
        if abs(diagnostics._number(float(cell), "cell_value") - radius) >= 1e-12:
            current_failures.append("cell_value")
        for field in ("radius_mm", "sketch004_circle_radius_mm"):
            if abs(diagnostics._number(phase.get(field), field) - radius) >= 1e-12:
                current_failures.append(field)
        if phase.get("recompute_requested") is not (index != 0):
            current_failures.append("recompute_requested")
        for name, obj in objects.items():
            obj = diagnostics._mapping(obj, "phase object")
            if obj.get("name") != name or not isinstance(obj.get("type_id"), str):
                raise ValueError("object name/type identity missing")
            expected_type = members[name]["type"] if name in members else baseline[name]["type_id"]
            if ledger is not None:
                expected_type = ledger["types"].get(name, expected_type)
            if obj["type_id"] != expected_type:
                current_failures.append(f"type:{name}")
            if (
                name in source_contract["assembly_target_types"]
                and obj["type_id"] != source_contract["assembly_target_types"][name]
            ):
                current_failures.append(f"assembly_type:{name}")
            if obj.get("states") != ["Up-to-date"]:
                current_failures.append(f"own_state:{name}")
            for field in ("placement_matrix", "global_placement_matrix"):
                if field in obj:
                    diagnostics._rigid_matrix(obj[field], f"{name}:{field}")
                elif name in order or name == "Body":
                    current_failures.append(f"missing_frame:{name}:{field}")
            expressions = _expressions(obj.get("expressions"))
            expected = effective_expressions[name]
            if expressions != expected:
                kind = "source_expressions" if name in known_expressions else "temporal_expressions"
                current_failures.append(f"{kind}:{name}")
            circles = _circles(obj)
            for saved_circle in source_contract.get("saved_circle_frames", []):
                if saved_circle["sketch"] != name:
                    continue
                if len(circles) != 1:
                    current_failures.append(f"source_circle_census:{name}")
                    continue
                expected_radius = radius if name == "Sketch004" else saved_circle["radius_mm"]
                if (
                    _difference(
                        circles[0]["center_in_document_mm"], saved_circle["center_in_native_mm"]
                    )
                    >= THRESHOLDS["hole_center_mm"]
                ):
                    current_failures.append(f"source_circle_center:{name}")
                if (
                    _difference(circles[0]["axis_in_document"], saved_circle["normal_in_native"])
                    >= THRESHOLDS["hole_axis"]
                ):
                    current_failures.append(f"source_circle_axis:{name}")
                if abs(circles[0]["radius_mm"] - expected_radius) >= THRESHOLDS["hole_radius_mm"]:
                    current_failures.append(f"source_circle_radius:{name}")
            attachment = _attachments(obj.get("attachment"))
            initial_attachment = _attachments(baseline[name].get("attachment"))
            for prop in attachment.keys() | initial_attachment.keys():
                a, b = initial_attachment.get(prop), attachment.get(prop)
                if a == b:
                    continue
                if (
                    prop in {"Support", "ExternalGeometry", "MirrorPlane"}
                    and a is not None
                    and b is not None
                    and [v["target"] for v in a] == [v["target"] for v in b]
                ):
                    literal_changes.append(
                        {
                            "phase": label,
                            "owner": name,
                            "property": prop,
                            "before": a,
                            "after": b,
                            "semantic_meaning": "unresolved_without_geometric_descriptors",
                        }
                    )
                elif prop == "AttachmentOffset" and a is not None and b is not None:
                    if _difference(a, b) >= THRESHOLDS["datum_matrix"]:
                        current_failures.append(f"attachment_offset:{name}")
                else:
                    current_failures.append(f"attachment_identity:{name}:{prop}")
        failures.extend(f"{label}:{f}" for f in current_failures)
        observed = phase.get("recompute_result")
        if index == 0:
            recompute = "not_requested"
        elif observed is False:
            recompute = "requested_force_returned_zero_attempted_objects"
        elif observed is True:
            recompute = "requested_force_returned_nonzero_attempt_count_exact_count_lost"
        else:
            recompute = "requested_force_attempt_count_not_captured"
        phase_checks.append(
            {
                "phase": label,
                "failures": current_failures,
                "recompute_observation": recompute,
                "all_features_rebuilt_established": False,
            }
        )
    all_order = [*order, "Body", *sorted(set(baseline) - set(order) - {"Body"})]
    comparisons = {}
    for label, first, second in (
        ("cached_to_forced", 0, 1),
        ("forced_to_return", 1, 4),
        ("cached_to_return", 0, 4),
    ):
        comparison = compare_objects(phases[first]["objects"], phases[second]["objects"], all_order)
        comparison["body_signed_volume_delta_mm3"] = (
            phases[second]["objects"]["Body"]["shape"]["volume_mm3"]
            - phases[first]["objects"]["Body"]["shape"]["volume_mm3"]
        )
        comparisons[label] = comparison
        failures.extend(f"{label}:{f}" for f in comparison["failures"])
    datum_names = sorted(set(source_contract["assembly_target_types"]) - {"Body"})
    perturbations = {}
    for index in (2, 3):
        response = compare_objects(phases[1]["objects"], phases[index]["objects"], all_order)
        response["nominal_equality_required"] = False
        response["interpretation"] = (
            "Descriptive measured response to the declared radius edit; "
            "equality thresholds do not gate intended perturbation."
        )
        perturbations[phases[index]["phase"]] = response
    return {
        "schema_version": 1,
        "evidence_class": "host_analysis_of_supplied_Art1_return_trace",
        "input_evidence_class": capture["evidence_class"],
        "source_sha256": capture["source_sha256"],
        "candidate_sha256": capture["candidate_sha256"],
        "identity_census": {
            "runtime_objects": len(baseline),
            "ordered_body_members": len(order),
            "assembly_targets": len(source_contract["assembly_target_types"]),
            "source_expression_objects": sum(bool(pairs) for pairs in known_expressions.values()),
            "source_expression_pairs": sum(len(pairs) for pairs in known_expressions.values()),
        },
        "source_expression_coverage": {
            "authenticated_full_source_xml": ledger is not None,
            "document_xml_sha256": ledger["document_xml_sha256"] if ledger else None,
            "known_source_objects": sorted(known_expressions),
            "runtime_objects_with_only_temporal_expression_checks": sorted(
                set(baseline) - known_expressions.keys()
            ),
        },
        "thresholds": THRESHOLDS,
        "threshold_rule": "absolute_error_strictly_less_than_threshold",
        "thresholds_are_manufacturing_tolerances": False,
        "phase_checks": phase_checks,
        "comparisons": comparisons,
        "perturbation_responses": perturbations,
        "datum_targets_checked": datum_names,
        "literal_reference_changes": literal_changes,
        "failures": failures,
        "all_observed_numerical_and_identity_checks_passed": not failures,
        "unmeasured_gates": [
            "full_surface_distance",
            "bidirectional_Boolean_differences",
            "geometric_attachment_semantics",
            "native_capture_authentication",
            "complete_dependency_closure",
        ],
        "semantic_reference_geometry_verified": False,
        "native_capture_authenticated": False,
        "shape_equivalence_established": False,
        "migration_accepted": False,
        "manufacturing_released": False,
        "interpretation": (
            "Earliest captured change is an inspection lead, not a diagnosed cause. "
            "Perturbation phases are identity/control checks, not nominal geometry equality tests."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--source-contract", type=Path, required=True)
    parser.add_argument(
        "--source", type=Path, help="Exact source FCStd for complete XML identity checks"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = analyze_return_trace(
            diagnostics._load(args.capture), diagnostics._load(args.source_contract), args.source
        )
        result["capture_sha256"] = hashlib.sha256(args.capture.read_bytes()).hexdigest()
        result["source_contract_sha256"] = hashlib.sha256(
            args.source_contract.read_bytes()
        ).hexdigest()
        result["analysis_tool_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"return analysis rejected: {error}")
        return 2
    return 0 if result["all_observed_numerical_and_identity_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
