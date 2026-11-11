"""Capture checks reject missing cuts, stale geometry and incomplete evidence."""

import copy
import hashlib
import json
import math
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
TOOLS = runpy.run_path(str(ROOT / "tools" / "thor_art1_diagnostics.py"))
SOURCE_CONTRACT = json.loads(
    (ROOT / "hardware" / "cad" / "thor-art1-desktop-source-fingerprint.json").read_text()
)
HISTORY_PATH = ROOT / "hardware" / "cad" / "thor-art1-migration-evidence.json"
STAGES = TOOLS["STAGES"]


def complete_capture():
    """Deliberately synthetic dimensions, never a claim of native CAD success."""
    shape = {
        "valid": True,
        "solid_count": 1,
        "volume_mm3": 1000.0,
        "bounds_mm": [-5, 5, -5, 5, -5, 5],
        "center_of_mass_mm": [0, 0, 0],
        "source_minus_candidate_mm3": 0,
        "candidate_minus_source_mm3": 0,
        "surface_distance_mm": 0,
    }
    source_members = {member["name"]: member for member in SOURCE_CONTRACT["members"]}
    holes = {}
    for name, sketch in (("body_bolt", "Sketch004"), ("head_recess", "Sketch005")):
        circle = next(c for c in SOURCE_CONTRACT["saved_circle_frames"] if c["sketch"] == sketch)
        hole = {
            "center_mm": circle["center_in_native_mm"],
            "axis": circle["normal_in_native"],
            "radius_mm": circle["radius_mm"],
            "depth_mm": 13,
        }
        holes[name] = {stage: copy.deepcopy(hole) for stage in ("saved", *STAGES)}
    return {
        "schema_version": 1,
        "evidence_class": "synthetic_geometry_fixture",
        "source_sha256": TOOLS["SOURCE_SHA256"],
        "candidate_sha256": "a" * 64,
        "capture_script_sha256": "b" * 64,
        "saved_tip_brep_sha256": source_members[SOURCE_CONTRACT["body_tip"]]["saved_brep"][
            "sha256"
        ],
        "runtime_version": "synthetic fixture, no FreeCAD execution",
        "candidate_path_kind": "separate_copy",
        "source_unchanged": True,
        "save_reopen_force_recompute_completed": True,
        "object_states": {
            name: {stage: ["Up-to-date"] for stage in STAGES}
            for name in ["Body", *SOURCE_CONTRACT["ordered_body_members"]]
        },
        "assembly_target_types": copy.deepcopy(SOURCE_CONTRACT["assembly_target_types"]),
        "body": {stage: copy.deepcopy(shape) for stage in ("saved", *STAGES)},
        "datums": {
            name: {
                stage: TOOLS["_matrix_from_placement"](source_members[name]["placement_mm_xyzw"])
                for stage in ("saved", *STAGES)
            }
            for name in SOURCE_CONTRACT["assembly_target_types"]
            if name != "Body"
        },
        "bolt_holes": holes,
        "cut_effects_mm3": {
            name: dict.fromkeys(("saved", *STAGES), volume)
            for name, volume in (("Pocket", 119.38316867512139), ("Pocket001", 22.0))
        },
    }


def compare(capture):
    return TOOLS["compare_capture"](capture, SOURCE_CONTRACT)


def test_complete_synthetic_capture_checks_math_without_becoming_native_evidence():
    result = compare(complete_capture())
    assert result["all_numerical_and_contract_checks_passed"]
    assert not result["eligible_for_native_manual_review"]
    assert not result["migration_accepted"]
    assert not result["saved_body_geometry_independently_authenticated"]
    assert not result["thresholds_are_manufacturing_tolerances"]


@pytest.mark.parametrize("stage", STAGES)
def test_empty_bolt_cut_fails_despite_valid_solid_and_up_to_date_objects(stage):
    capture = complete_capture()
    capture["cut_effects_mm3"]["Pocket"][stage] = 0
    result = compare(capture)
    assert not result["all_numerical_and_contract_checks_passed"]
    assert f"material_removal:Pocket:{stage}" in result["failures"]


def test_zero_booleans_do_not_override_volume_drift():
    capture = complete_capture()
    capture["body"]["rebuilt"]["volume_mm3"] += 2.864236906170845
    result = compare(capture)
    assert "body:rebuilt:volume_mm3" in result["failures"]
    assert not result["migration_accepted"]


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("valid", False, "body_solid:reopened"),
        ("solid_count", 2, "body_solid:reopened"),
        ("bounds_mm", [-5, 5, -5, 5, -5, 6], "body:reopened:bounds_mm"),
        ("center_of_mass_mm", [0, 0.001, 0], "body:reopened:center_of_mass_mm"),
        ("source_minus_candidate_mm3", 0.01, "body:reopened:source_minus_candidate_mm3"),
        ("candidate_minus_source_mm3", 0.01, "body:reopened:candidate_minus_source_mm3"),
        ("surface_distance_mm", 0.01, "body:reopened:surface_distance_mm"),
    ],
)
def test_independent_shape_checks_each_reject_a_counterexample(field, value, expected):
    capture = complete_capture()
    capture["body"]["reopened"][field] = value
    assert expected in compare(capture)["failures"]


@pytest.mark.parametrize("field", ["volume_mm3", "surface_distance_mm"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True, "0"])
def test_nonfinite_or_wrong_numeric_type_is_not_a_pass(field, value):
    capture = complete_capture()
    capture["body"]["restored"][field] = value
    with pytest.raises(ValueError, match="finite"):
        compare(capture)


@pytest.mark.parametrize("field", ["source_unchanged", "save_reopen_force_recompute_completed"])
def test_missing_run_preconditions_are_not_inferred_from_shapes(field):
    capture = complete_capture()
    del capture[field]
    assert field in compare(capture)["failures"]


def test_object_states_must_cover_the_whole_body_and_all_stages():
    capture = complete_capture()
    del capture["object_states"]["Sketch001"]
    assert "complete_object_states" in compare(capture)["failures"]
    capture = complete_capture()
    del capture["object_states"]["Sketch001"]["reopened"]
    with pytest.raises(ValueError, match="states"):
        compare(capture)


def test_cached_valid_final_solid_is_rejected_when_history_is_invalid():
    capture = complete_capture()
    capture["object_states"]["Sketch005"]["rebuilt"] = ["Touched", "Invalid"]
    capture["object_states"]["Body"]["restored"] = ["Touched"]
    failures = compare(capture)["failures"]
    assert "object_state:Sketch005:rebuilt" in failures
    assert "object_state:Body:restored" in failures


@pytest.mark.parametrize("section", ["datums", "bolt_holes", "cut_effects_mm3"])
def test_incomplete_collections_fail_instead_of_vacuous_acceptance(section):
    capture = complete_capture()
    capture[section] = {}
    assert not compare(capture)["all_numerical_and_contract_checks_passed"]


def test_name_and_type_both_belong_to_external_assembly_contract():
    capture = complete_capture()
    capture["assembly_target_types"]["HoleAxis_1"] = "PartDesign::CoordinateSystem"
    assert "assembly_target_name_type_contract" in compare(capture)["failures"]


def test_one_datum_that_moves_after_reopen_fails():
    capture = complete_capture()
    capture["datums"]["HoleAxis_1"]["reopened"][3] += 0.001
    assert "datum:HoleAxis_1:reopened" in compare(capture)["failures"]


@pytest.mark.parametrize("field", ["center_mm", "axis", "radius_mm", "depth_mm"])
def test_semantic_hole_changes_fail_even_if_body_volume_matches(field):
    capture = complete_capture()
    value = capture["bolt_holes"]["body_bolt"]["rebuilt"]
    value[field] = {
        "center_mm": [0, 1, 0],
        "axis": [1, 0, 0],
        "radius_mm": 2.0,
        "depth_mm": 12,
    }[field]
    assert any(f"hole:body_bolt:rebuilt:{field}" == x for x in compare(capture)["failures"])


def test_nonunit_axis_rejected_as_invalid_input():
    capture = complete_capture()
    capture["bolt_holes"]["head_recess"]["restored"]["axis"] = [0, 2, 0]
    with pytest.raises(ValueError, match="unit vector"):
        compare(capture)


def test_all_stages_cannot_silently_redefine_a_saved_datum():
    capture = complete_capture()
    for stage in ("saved", *STAGES):
        capture["datums"]["HoleAxis_1"][stage][3] += 1
    assert "datum:HoleAxis_1:saved_does_not_match_source" in compare(capture)["failures"]


def test_all_stages_cannot_silently_redefine_the_saved_bolt_circle():
    capture = complete_capture()
    for stage in ("saved", *STAGES):
        capture["bolt_holes"]["body_bolt"][stage]["radius_mm"] += 0.1
    assert "hole:body_bolt:saved_does_not_match_source_sketch" in compare(capture)["failures"]


@pytest.mark.parametrize("kind", ["reflection", "scale", "homogeneous"])
def test_matching_malformed_datum_matrices_do_not_pass(kind):
    capture = complete_capture()
    datum = "HoleAxis_1"
    for stage in ("saved", *STAGES):
        matrix = capture["datums"][datum][stage]
        if kind == "reflection":
            for index in (0, 1, 2):
                matrix[index] *= -1
        elif kind == "scale":
            for index in (0, 1, 2):
                matrix[index] *= 2
        else:
            matrix[15] = 0
    with pytest.raises(ValueError, match="rotation|transform"):
        compare(capture)


def test_boolean_schema_version_rejected():
    capture = complete_capture()
    capture["schema_version"] = True
    with pytest.raises(ValueError, match="schema"):
        compare(capture)


def test_duplicate_json_fields_rejected_instead_of_shadowing_evidence(tmp_path):
    path = tmp_path / "ambiguous.json"
    path.write_text('{"evidence_class":"synthetic", "evidence_class":"native"}')
    with pytest.raises(ValueError, match="duplicate JSON"):
        TOOLS["_load"](path)


def test_historical_probe_reanalysis_reports_only_observed_drift():
    result = TOOLS["historical_diagnostics"](
        json.loads(HISTORY_PATH.read_text()), hashlib.sha256(HISTORY_PATH.read_bytes()).hexdigest()
    )
    assert result["earliest_captured_drift"] == "Groove"
    assert result["earliest_true_rebuild_drift"] is None
    assert result["uncaptured_early_features"] == list(TOOLS["EARLY_CHAIN"][:-1])
    assert result["saved_pocket_removed_mm3"] == pytest.approx(119.38316867512139)
    assert result["rebuilt_pocket_removed_mm3"] == 0
    assert result["disappearing_cut_detected"]
    assert not result["native_recompute_performed"]
    assert not result["root_cause_isolated"]
    assert not result["migration_accepted"]
    tracked = json.loads(
        (ROOT / "hardware" / "cad" / "thor-art1-desktop-historical-check.json").read_text()
    )
    assert result == tracked


def test_source_report_preserves_eighty_members_twenty_four_datums_and_twenty_five_targets():
    assert len(SOURCE_CONTRACT["members"]) == 80
    assert len(SOURCE_CONTRACT["ordered_body_members"]) == 80
    assert len(SOURCE_CONTRACT["assembly_target_types"]) == 25
    assert (
        sum(
            "placement_mm_xyzw" in m and m["type"] in TOOLS["DATUM_TYPES"]
            for m in SOURCE_CONTRACT["members"]
        )
        == 24
    )
    assert SOURCE_CONTRACT["body_tip"] == "Pocket018"
    assert not SOURCE_CONTRACT["native_recompute_performed"]
    assert not SOURCE_CONTRACT["migration_accepted"]


def test_saved_bolt_sketch_frame_matches_historical_edge_fingerprint():
    circle = SOURCE_CONTRACT["saved_circle_frames"][0]
    assert circle["sketch"] == "Sketch004"
    assert circle["center_in_native_mm"] == pytest.approx([-31.5, -55, 8], abs=1e-12)
    assert circle["normal_in_native"] == pytest.approx([0, 1, 0], abs=1e-12)
    assert circle["radius_mm"] == 1.7
    geometry = json.loads(HISTORY_PATH.read_text())["failed_migration_probe"]["saved_pocket_edge13"]
    assert circle["center_in_native_mm"] == pytest.approx(geometry["Center"], abs=1e-12)
    assert circle["normal_in_native"] == pytest.approx(geometry["Axis"], abs=1e-12)


def test_arbitrary_or_modified_native_source_is_rejected_before_cad_import(tmp_path):
    source = tmp_path / "original.FCStd"
    source.write_bytes(b"not the pinned source")
    with pytest.raises(ValueError, match="SHA-256"):
        TOOLS["source_fingerprint"](source, json.loads(HISTORY_PATH.read_text()))
    assert source.read_bytes() == b"not the pinned source"


def test_cli_never_overwrites_previous_reports(tmp_path):
    output = tmp_path / "old.json"
    output.write_text("retained evidence")
    with pytest.raises(SystemExit) as exception:
        TOOLS["main"](["history", str(HISTORY_PATH), "--output", str(output)])
    assert exception.value.code == 2
    assert output.read_text() == "retained evidence"


def test_comparison_cli_failure_is_nonzero_and_keeps_a_reviewable_report(tmp_path):
    capture = complete_capture()
    capture["cut_effects_mm3"]["Pocket"]["rebuilt"] = 0
    input_path = tmp_path / "bad-capture.json"
    output = tmp_path / "comparison.json"
    input_path.write_text(json.dumps(capture))
    contract = ROOT / "hardware" / "cad" / "thor-art1-desktop-source-fingerprint.json"
    assert (
        TOOLS["main"](
            [
                "compare",
                str(input_path),
                "--source-contract",
                str(contract),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert "material_removal:Pocket:rebuilt" in json.loads(output.read_text())["failures"]


def test_missing_native_metadata_cannot_be_inferred_from_geometry():
    capture = complete_capture()
    del capture["runtime_version"]
    with pytest.raises(ValueError, match="runtime_version"):
        compare(capture)


def test_unmarked_capture_rejected_instead_of_defaulting_to_native():
    capture = complete_capture()
    del capture["evidence_class"]
    with pytest.raises(ValueError, match="evidence_class"):
        compare(capture)


def test_native_manual_review_requires_identifying_the_pinned_saved_tip():
    capture = complete_capture()
    capture["evidence_class"] = "native_geometry_capture"
    del capture["saved_tip_brep_sha256"]
    with pytest.raises(ValueError, match="saved tip BRep"):
        compare(capture)
