"""Guard partial A6 procedures; no synthetic record becomes migration acceptance."""

import copy
import json
import runpy
from pathlib import Path

import pytest

TOOLS = runpy.run_path(str(Path(__file__).parents[1] / "tools/prepare_thor_art1_candidate.py"))


def test_candidate_path_is_fresh_scoped_and_visibly_unaccepted(tmp_path):
    run = tmp_path / "cad" / "new-run"
    output = tmp_path / "cad" / "candidates" / "Art1-UNACCEPTED.FCStd"
    assert TOOLS["candidate_path"](output, run) == output.resolve()


@pytest.mark.parametrize("kind", ["outside", "unmarked", "wrong_suffix", "existing"])
def test_candidate_path_rejects_unsafe_or_ambiguous_destination(tmp_path, kind):
    run = tmp_path / "cad" / "new-run"
    output = tmp_path / "cad" / "candidates" / "Art1-UNACCEPTED.FCStd"
    if kind == "outside":
        output = tmp_path / "other" / output.name
    elif kind == "unmarked":
        output = output.with_name("Art1Body.FCStd")
    elif kind == "wrong_suffix":
        output = output.with_suffix(".json")
    else:
        output.parent.mkdir(parents=True)
        output.write_bytes(b"retained candidate")
    with pytest.raises(ValueError, match="fresh UNACCEPTED"):
        TOOLS["candidate_path"](output, run)
    if kind == "existing":
        assert output.read_bytes() == b"retained candidate"


def complete_metadata():
    # Retained native metadata is a fixture, not a native execution by this test.
    root = Path(__file__).parents[1] / "hardware/cad"
    capture = json.loads((root / "thor-art1-desktop-candidate-study-v1.json").read_text())
    runner = json.loads((root / "thor-art1-desktop-candidate-runner-v1.json").read_text())
    return capture, runner


def test_procedural_completion_remains_separate_from_native_default_and_acceptance():
    capture, runner = complete_metadata()
    assert TOOLS["candidate_procedure_complete"](capture, runner)
    assert not capture["migration_accepted"] and not capture["candidate_accepted"]
    # The default no-save diagnostic checker must reject this saved-candidate class.
    assert not TOOLS["PROBE"]["native_report_is_complete"](capture, "a" * 64)
    assert capture["candidate_study"]["restored_volume_within_1e_minus_6_mm3"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "missing_phase",
        "wrong_alias",
        "wrong_radius",
        "missing_body",
        "missing_states",
        "missing_constraints",
        "bad_script_hash",
        "bad_candidate_hash",
        "wrong_experiment",
        "wrong_audit",
        "wrong_source",
        "missing_version",
        "wrong_filename",
        "corrupt_error",
    ],
)
def test_incomplete_or_corrupt_procedure_cannot_complete(fault):
    capture, runner = complete_metadata()
    study = capture["candidate_study"]
    phase = study["phases"][2]
    if fault == "missing_phase":
        study["phases"].pop()
    elif fault == "wrong_alias":
        phase["cell_alias"] = "UnrelatedRadius"
    elif fault == "wrong_radius":
        phase["sketch004_circle_radius_mm"] = 1.7
    elif fault == "missing_body":
        del phase["body"]
    elif fault == "missing_states":
        del phase["all_document_own_states"]["Sketch004"]
    elif fault == "missing_constraints":
        phase["affected_constraints_and_expressions"]["Sketch004"]["constraints"] = []
    elif fault == "bad_script_hash":
        capture["capture_script_sha256"] = "a" * 64
    elif fault == "bad_candidate_hash":
        study["candidate_sha256_after_reopen_and_perturbations"] = "a" * 64
    elif fault == "wrong_experiment":
        capture["experiment"] = "unchanged"
    elif fault == "wrong_audit":
        capture["audit_status"] = "partial"
    elif fault == "wrong_source":
        capture["source_sha256_after"] = "a" * 64
    elif fault == "missing_version":
        del capture["freecad_version"]
    elif fault == "wrong_filename":
        phase["document_filename"] = study["input_copy_document_filename"]
    elif fault == "corrupt_error":
        study["restored_nominal_body_volume_error_mm3"] = 0
    assert not TOOLS["candidate_procedure_complete"](capture, runner)


def test_recorded_unclean_own_state_remains_diagnostic_procedure_coverage():
    capture, runner = complete_metadata()
    capture["candidate_study"]["phases"][2]["all_document_own_states"]["Body"] = ["Invalid"]
    assert not TOOLS["candidate_procedure_complete"](capture, runner)
    capture["candidate_study"]["all_phase_own_states_up_to_date"] = False
    assert TOOLS["candidate_procedure_complete"](capture, runner)
    assert capture["migration_accepted"] is False


def test_boolean_schema_and_inconsistent_constraint_summary_reject():
    capture, runner = complete_metadata()
    capture["schema_version"] = True
    assert not TOOLS["candidate_procedure_complete"](capture, runner)
    capture, runner = complete_metadata()
    capture["candidate_study"]["phases"][2]["expression_and_constraint_structure_preserved"] = False
    assert not TOOLS["candidate_procedure_complete"](capture, runner)


@pytest.mark.parametrize("key", ["source_saved", "migration_accepted", "candidate_accepted"])
def test_candidate_metadata_cannot_promote_source_save_or_acceptance(key):
    capture, runner = complete_metadata()
    capture[key] = True
    assert not TOOLS["candidate_procedure_complete"](capture, runner)


def test_candidate_flag_without_explicit_candidate_callback_does_not_enter_native_mode(monkeypatch):
    monkeypatch.setenv("RAFTEL_PREPARE_THOR_ART1_CANDIDATE", "1")
    monkeypatch.delenv("RAFTEL_RUN_THOR_ART1_PROBE", raising=False)
    with pytest.raises(ValueError, match="opt-in"):
        TOOLS["PROBE"]["native_capture"]()


def test_timeout_or_changed_inputs_do_not_complete_candidate_procedure():
    capture, runner = complete_metadata()
    runner["outcome"] = "timed_out"
    assert not TOOLS["candidate_procedure_complete"](capture, runner)
    capture, runner = complete_metadata()
    runner["capture_snapshot_bytes_unchanged"] = False
    assert not TOOLS["candidate_procedure_complete"](capture, runner)


def test_candidate_structure_comparison_ignores_controlled_values_but_not_deleted_constraints():
    records = {
        "Sketch004": {
            "expressions": [["Constraints[0]", "Spreadsheet.M3BoltBodyRadius"]],
            "constraints": [{"Type": "Radius", "First": 0, "Value": 1.7}],
        }
    }
    changed = copy.deepcopy(records)
    changed["Sketch004"]["constraints"][0]["Value"] = 1.71
    assert TOOLS["_structure"](records) == TOOLS["_structure"](changed)
    changed["Sketch004"]["constraints"] = []
    assert TOOLS["_structure"](records) != TOOLS["_structure"](changed)
