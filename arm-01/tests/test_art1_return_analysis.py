"""Meaningful analytic counterexamples; synthetic numbers are never native evidence."""

import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

PATH = Path(__file__).parents[1] / "tools/thor_art1_return_analysis.py"
SPEC = importlib.util.spec_from_file_location("tested_return_analysis", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def fixture():
    """Small declared source contract; intentionally invented geometry and identities."""
    expression = [["Constraints[0]", "Spreadsheet.M3BoltBodyRadius"]]
    members = []
    for name, kind in (
        ("Sketch004", "Sketcher::SketchObject"),
        ("Pad", "PartDesign::Pad"),
        ("LCS", "PartDesign::CoordinateSystem"),
    ):
        members.append({"name": name, "type": kind, "saved_properties": {}})
    members[0]["saved_properties"]["ExpressionEngine"] = {
        "tag": "ExpressionEngine",
        "children": [
            {
                "tag": "Expression",
                "attributes": {"path": expression[0][0], "expression": expression[0][1]},
            }
        ],
    }
    source = {
        "source_sha256": MODULE.diagnostics.SOURCE_SHA256,
        "ordered_body_members": [m["name"] for m in members],
        "members": members,
        "assembly_target_types": {
            "Body": "PartDesign::Body",
            "LCS": "PartDesign::CoordinateSystem",
        },
    }
    shape = {
        "is_null": False,
        "valid": True,
        "solid_count": 1,
        "face_count": 6,
        "edge_count": 12,
        "volume_mm3": 1000,
        "raw_native_volume_mm3": 1000,
        "area_mm2": 600,
        "length_mm": 120,
        "bounds_mm": [-5, 5, -5, 5, -5, 5],
        "center_of_mass_mm": [0, 0, 0],
        "unbounded_construction_geometry": False,
        "shape_placement_matrix": IDENTITY.copy(),
    }
    objects = {}
    for member in [
        *members,
        {"name": "Body", "type": "PartDesign::Body"},
        {"name": "Spreadsheet", "type": "Spreadsheet::Sheet"},
    ]:
        name = member["name"]
        objects[name] = {
            "name": name,
            "type_id": member["type"],
            "states": ["Up-to-date"],
            "placement_matrix": IDENTITY.copy(),
            "global_placement_matrix": IDENTITY.copy(),
            "expressions": copy.deepcopy(expression) if name == "Sketch004" else [],
            "attachment": {},
            "shape": copy.deepcopy(shape),
        }
    objects["Sketch004"]["attachment"] = {
        "Support": {
            "current_property": "AttachmentSupport",
            "targets": [{"target": "Pad", "selector": "Face1"}],
        }
    }
    phases = []
    for index, (label, radius) in enumerate(MODULE.PHASES):
        phases.append(
            {
                "phase": label,
                "radius_mm": radius,
                "cell_alias": "M3BoltBodyRadius",
                "cell_value": str(radius),
                "recompute_requested": index != 0,
                "sketch004_circle_radius_mm": radius,
                "objects": copy.deepcopy(objects),
                "affected_constraints_and_expressions": {
                    "Sketch004": {
                        "expressions": copy.deepcopy(expression),
                        "constraints": [
                            {"Type": "Radius", "Value": radius, "First": 0},
                            {"Type": "Distance", "Value": 7, "First": 1},
                        ],
                    }
                },
            }
        )
    capture = {
        "schema_version": 1,
        "evidence_class": "synthetic_Art1_parameter_return_fixture",
        "source_sha256": source["source_sha256"],
        "candidate_sha256": "a" * 64,
        "ordered_body_members": source["ordered_body_members"],
        "phases": phases,
        "status": "diagnostic_completed_not_migration_acceptance",
        "errors": [],
        "document_saved": False,
        "support_remapped": False,
        "all_inputs_snapshots_and_protected_bytes_unchanged": True,
        "owned_document_closed": True,
        "open_documents_after_cleanup": [],
    }
    return capture, source


def analyze(capture, source):
    return MODULE.analyze_return_trace(capture, source)


def test_matching_synthetic_trace_preserves_unknown_native_and_semantic_gates():
    result = analyze(*fixture())
    assert result["all_observed_numerical_and_identity_checks_passed"]
    assert not result["migration_accepted"]
    assert not result["native_capture_authenticated"]
    assert not result["semantic_reference_geometry_verified"]
    assert not result["thresholds_are_manufacturing_tolerances"]
    assert result["datum_targets_checked"] == ["LCS"]
    assert "full_surface_distance" in result["unmeasured_gates"]


def test_three_distinct_nominal_pairs_do_not_hide_return_failure():
    capture, source = fixture()
    capture["phases"][1]["objects"]["Body"]["shape"]["volume_mm3"] += 1e-7
    capture["phases"][4]["objects"]["Body"]["shape"]["volume_mm3"] -= 0.01772052329
    result = analyze(capture, source)
    comparisons = result["comparisons"]
    assert not comparisons["cached_to_forced"]["failures"]
    assert "Body:volume_mm3" in comparisons["forced_to_return"]["failures"]
    assert "Body:volume_mm3" in comparisons["cached_to_return"]["failures"]
    assert comparisons["cached_to_return"]["body_signed_volume_delta_mm3"] < 0
    assert not comparisons["forced_to_return"]["root_cause_established"]


def test_earliest_metric_difference_follows_body_order_and_frame_is_separate():
    capture, source = fixture()
    phase = capture["phases"][4]["objects"]
    phase["Pad"]["shape"]["area_mm2"] += 0.1
    phase["LCS"]["global_placement_matrix"][3] += 1e-5
    result = analyze(capture, source)["comparisons"]["forced_to_return"]
    assert result["first_changed_captured_feature"] == "Pad"
    assert result["first_changed_frame"] == "LCS"
    assert result["first_true_semantic_drift"] is None


def test_intended_perturbation_geometry_is_descriptive_and_not_nominal_gate():
    capture, source = fixture()
    capture["phases"][2]["objects"]["Pad"]["shape"]["volume_mm3"] += 20
    result = analyze(capture, source)
    assert result["all_observed_numerical_and_identity_checks_passed"]
    response = result["perturbation_responses"]["radius_minus_0_01_mm"]
    assert not response["nominal_equality_required"]
    assert "Pad:volume_mm3" in response["failures"]


def test_zero_booleans_do_not_override_another_metric_and_conflict_is_retained():
    capture, source = fixture()
    shape = capture["phases"][4]["objects"]["Body"]["shape"]
    shape.update(volume_mm3=1000.01, source_minus_candidate_mm3=0, candidate_minus_source_mm3=0)
    result = analyze(capture, source)["comparisons"]["forced_to_return"]
    assert "Body:volume_mm3" in result["failures"]
    assert any(c["kind"].startswith("zero_Boolean") for c in result["metric_conflicts"])


def test_raw_native_volume_remains_distinct_from_solid_sum():
    capture, source = fixture()
    capture["phases"][4]["objects"]["Body"]["shape"]["raw_native_volume_mm3"] *= -1
    result = analyze(capture, source)["comparisons"]["forced_to_return"]
    assert "Body:raw_native_volume_mm3" in result["failures"]
    assert "Body:volume_mm3" not in result["failures"]


@pytest.mark.parametrize(
    "field,value",
    [("volume_mm3", math.nan), ("raw_native_volume_mm3", True), ("bounds_mm", [1] * 5)],
)
def test_invalid_metrics_are_rejected(field, value):
    capture, source = fixture()
    capture["phases"][4]["objects"]["Body"]["shape"][field] = value
    with pytest.raises(ValueError):
        analyze(capture, source)


def test_metric_equal_to_existing_threshold_fails_strict_gate():
    capture, source = fixture()
    capture["phases"][4]["objects"]["Body"]["global_placement_matrix"][3] = 1e-12
    assert "forced_to_return:Body:global_placement_matrix" in analyze(capture, source)["failures"]


def test_unchanged_geometry_cannot_mask_source_expression_or_type_change():
    capture, source = fixture()
    obj = capture["phases"][3]["objects"]["Sketch004"]
    obj["expressions"][0][1] = "Spreadsheet.M3BoltHeadRadius"
    obj["type_id"] = "Part::Feature"
    failures = analyze(capture, source)["failures"]
    assert "radius_plus_0_01_mm:source_expressions:Sketch004" in failures
    assert "radius_plus_0_01_mm:type:Sketch004" in failures


def test_controlled_and_uncontrolled_constraint_values_checked_independently():
    capture, source = fixture()
    constraints = capture["phases"][2]["affected_constraints_and_expressions"]["Sketch004"][
        "constraints"
    ]
    constraints[0]["Value"] = 1.7
    constraints[1]["Value"] = 8
    failures = analyze(capture, source)["failures"]
    assert "radius_minus_0_01_mm:controlled_constraint_value:Sketch004:0" in failures
    assert "radius_minus_0_01_mm:uncontrolled_constraint_value:Sketch004:1" in failures


def test_selector_index_change_is_explicitly_unresolved_not_semantic_error():
    capture, source = fixture()
    capture["phases"][4]["objects"]["Sketch004"]["attachment"]["Support"]["targets"][0][
        "selector"
    ] = "Face2"
    result = analyze(capture, source)
    assert result["all_observed_numerical_and_identity_checks_passed"]
    assert len(result["literal_reference_changes"]) == 1
    assert not result["semantic_reference_geometry_verified"]


def test_changed_attachment_provider_fails_even_with_equal_geometry():
    capture, source = fixture()
    capture["phases"][4]["objects"]["Sketch004"]["attachment"]["Support"]["targets"][0][
        "target"
    ] = "Body"
    assert (
        "restored_nominal_radius:attachment_identity:Sketch004:Support"
        in analyze(capture, source)["failures"]
    )


def test_source_circle_frame_drift_rejects_equal_solid_metrics():
    capture, source = fixture()
    source["saved_circle_frames"] = [
        {
            "sketch": "Sketch004",
            "center_in_native_mm": [0, 0, 0],
            "normal_in_native": [0, 0, 1],
            "radius_mm": 1.7,
        }
    ]
    for phase in capture["phases"]:
        phase["objects"]["Sketch004"]["sketch_circle_frames"] = [
            {
                "center_in_sketch_mm": [0, 0, 0],
                "center_in_document_mm": [0, 0, 0],
                "axis_in_document": [0, 0, 1],
                "radius_mm": phase["radius_mm"],
            }
        ]
    capture["phases"][4]["objects"]["Sketch004"]["sketch_circle_frames"][0][
        "center_in_document_mm"
    ][0] = 0.001
    result = analyze(capture, source)
    assert "restored_nominal_radius:source_circle_center:Sketch004" in result["failures"]
    assert (
        "Sketch004:sketch_circle:0:center_in_document_mm"
        in result["comparisons"]["forced_to_return"]["failures"]
    )


def test_non_solid_centroid_and_volume_remain_unmeasured():
    capture, source = fixture()
    for phase in capture["phases"]:
        shape = phase["objects"]["Sketch004"]["shape"]
        shape.update(solid_count=0, volume_mm3=None, center_of_mass_mm=None)
    result = analyze(capture, source)
    assert result["all_observed_numerical_and_identity_checks_passed"]
    row = result["comparisons"]["forced_to_return"]["objects"][0]
    assert row["unmeasured_fields"] == ["center_of_mass_mm", "volume_mm3"]


def test_failed_preservation_and_cleanup_declarations_remain_gates():
    capture, source = fixture()
    capture["all_inputs_snapshots_and_protected_bytes_unchanged"] = False
    capture["owned_document_closed"] = False
    result = analyze(capture, source)
    assert "all_inputs_snapshots_and_protected_bytes_unchanged" in result["failures"]
    assert "owned_document_closed" in result["failures"]


@pytest.mark.parametrize("section", ["phase", "object", "constraint_record"])
def test_wrong_nested_record_types_reject_cleanly(section):
    capture, source = fixture()
    if section == "phase":
        capture["phases"][3] = None
    elif section == "object":
        capture["phases"][3]["objects"]["Pad"] = 3
    else:
        capture["phases"][3]["affected_constraints_and_expressions"]["Sketch004"] = False
    with pytest.raises(ValueError):
        analyze(capture, source)


@pytest.mark.parametrize("change", ["missing_phase", "missing_object", "reflection", "touched"])
def test_incomplete_or_invalid_capture_cannot_pass(change):
    capture, source = fixture()
    if change == "missing_phase":
        capture["phases"].pop()
    elif change == "missing_object":
        del capture["phases"][4]["objects"]["Pad"]
    elif change == "reflection":
        capture["phases"][4]["objects"]["LCS"]["placement_matrix"][0] = -1
    else:
        capture["phases"][4]["objects"]["Pad"]["states"] = ["Touched"]
        assert not analyze(capture, source)["all_observed_numerical_and_identity_checks_passed"]
        return
    with pytest.raises(ValueError):
        analyze(capture, source)


def test_cli_writes_failed_report_utf8_lf_and_never_overwrites(tmp_path):
    capture, source = fixture()
    capture["phases"][4]["objects"]["Body"]["shape"]["volume_mm3"] += 1
    paths = [tmp_path / n for n in ("capture.json", "source.json", "result.json")]
    for path, data in zip(paths, (capture, source), strict=False):
        path.write_text(json.dumps(data), encoding="utf-8")
    args = [str(paths[0]), "--source-contract", str(paths[1]), "--output", str(paths[2])]
    assert MODULE.main(args) == 1
    original = paths[2].read_bytes()
    assert b"\r\n" not in original
    assert MODULE.main(args) == 2
    assert paths[2].read_bytes() == original
