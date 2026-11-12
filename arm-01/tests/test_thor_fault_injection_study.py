"""Fault-pack witnesses remain synthetic and distinguish observer/oracle state."""

import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/thor_fault_injection_study.py"
SPEC = importlib.util.spec_from_file_location("thor_fault_injection_study", TOOL)
PACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACK)
CONFIG = ROOT / "config/thor-fault-injection-v1.json"


def report():
    pack, digest = PACK.load_pack(CONFIG)
    return PACK.build_report(pack, digest)


def case(study, identifier):
    return next(item for item in study["cases"] if item["case_id"] == identifier)


def test_default_pack_is_deterministic_bounded_and_fingerprints_existing_contracts():
    first, second = report(), report()
    assert first == second
    assert len(first["cases"]) == 11
    assert first["all_expected_invariants_observed"]
    assert not first["hardware_connected"] and not first["firmware_executed"]
    assert first["evidence_class"] == PACK.EVIDENCE_CLASS
    source = first["implementation_fingerprint"]["installed_file_sha256"]
    assert {
        "control/mock.py",
        "tasks/sorter.py",
        "control/thor_protocol_replay.py",
    } <= source.keys()
    assert len(first["producer_script_sha256"]) == 64


@pytest.mark.parametrize("identifier", list(PACK.EXPECTED_FAULT))
def test_protocol_faults_stay_nonready_after_good_observation_and_reset(identifier):
    result = case(report(), identifier)
    assert result["initial_fault"] == PACK.EXPECTED_FAULT[identifier]
    assert all(operation["rejected"] for operation in result["followup_operations"].values())
    assert result["command_after_reset"]["rejected"]
    assert result["fault_after_reset"] is not None
    assert not result["receipts"][0]["completed_in_simulation"]
    assert result["receipts"][0]["invalidated_by_reset"]


def test_lost_ack_retry_is_a_counterexample_not_a_safe_retry_claim():
    result = case(report(), "lost_ack_incremental_retry")
    assert result["receipts"][0]["parser_target_deg"][0] == 1
    assert result["receipts"][1]["parser_target_deg"][0] == 2
    assert all(not receipt["acknowledged"] for receipt in result["receipts"])
    assert all(receipt["completed_in_simulation"] for receipt in result["receipts"])
    assert result["automatic_retry_demonstrated_safe"] is False
    assert "not_real_untagged_ok_attribution" in result["acknowledgment_scope"]


def test_release_loss_worlds_are_observer_indistinguishable_despite_different_oracle_truth():
    study = report()
    before = case(study, "release_ack_lost_before_effect")
    after = case(study, "release_ack_lost_after_effect")
    assert before["observer_trace"] == after["observer_trace"]
    assert before["observer_trace_sha256"] == after["observer_trace_sha256"]
    assert before["fixture_oracle_truth"]["before_repeated_stop"] == {
        "held_object_id": "object-00",
        "placement_ids": [],
    }
    assert after["fixture_oracle_truth"]["before_repeated_stop"] == {
        "held_object_id": None,
        "placement_ids": ["object-00"],
    }
    for result in (before, after):
        assert result["held_object_knowledge"]["value"] == "unknown_after_fault"
        assert result["held_object_knowledge"]["automatic_recovery_allowed"] is False
        assert result["observer_trace"]["task_summary"]["sorted"] == 0
        assert result["observer_trace"]["task_summary"]["aborted"]
        assert result["observer_trace"]["task_summary"]["pending"] == 1
        assert not any(
            event["state"] == "verify" for event in result["observer_trace"]["task_events"]
        )
    assert all(study["release_ack_ambiguity_checks"].values())


@pytest.mark.parametrize("identifier", list(PACK.UNCERTAIN_TASK_CASES))
def test_mock_faults_stop_without_retry_release_or_automatic_recovery(identifier):
    result = case(report(), identifier)
    assert result["all_checks_passed"]
    assert result["held_object_knowledge"]["value"] == "unknown_after_fault"
    assert (
        result["fixture_oracle_truth"]["before_repeated_stop"]
        == result["fixture_oracle_truth"]["after_repeated_stop"]
        == result["fixture_oracle_truth"]["after_rejected_operations_and_rerun"]
    )
    assert all(
        operation["rejected"]
        for operation in result["observer_trace"]["blocked_operations"].values()
    )
    assert result["observer_trace"]["rerun_summary"]["aborted"]
    assert result["observer_trace"]["rerun_summary"]["sorted"] == 0


def test_uncertain_grasp_and_protocol_reset_preserve_held_mock_truth():
    for identifier in ("grasp_ack_lost_after_effect", "reset_during_transfer"):
        result = case(report(), identifier)
        assert (
            result["fixture_oracle_truth"]["after_repeated_stop"]["held_object_id"] == "object-00"
        )
        assert result["fixture_oracle_truth"]["after_repeated_stop"]["placement_ids"] == []


@pytest.mark.parametrize("attempt_budget", [1, 2, 5])
def test_false_grasp_exhaustion_respects_existing_config_budget_and_continues(
    monkeypatch, attempt_budget
):
    config = replace(PACK.load_config(), max_attempts=attempt_budget)
    monkeypatch.setattr(PACK, "load_config", lambda: config)
    result = PACK._grasp_budget_case(42)
    assert result["all_checks_passed"]
    assert result["observed_failed_object_attempts"] == list(range(1, attempt_budget + 1))
    assert result["task_summary"]["failed"] == 1
    assert result["task_summary"]["sorted"] == 1
    assert result["task_summary"]["aborted"] is False


def test_pack_read_limit_rejects_oversized_input_before_json_parsing(tmp_path):
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * 100000)
    with pytest.raises(ValueError, match="exceeds64KiB"):
        PACK.load_pack(path)


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": True},
        {"pack_revision": "other"},
        {"evidence_class": "physical"},
        {"seed": True},
        {"seed": -1},
        {"seed": 2**32},
        {"protocol_max_age_s": True},
        {"protocol_max_age_s": 0},
        {"protocol_max_age_s": float("inf")},
        {"protocol_max_age_s": 10**500},
        {"case_ids": ["stale_status"]},
        {"case_ids": list(reversed(PACK.CASE_IDS))},
        {"serial_port": "not-opened"},
    ],
)
def test_wrong_schema_seed_timing_case_or_transport_fields_rejected(tmp_path, change):
    document = json.loads(CONFIG.read_bytes())
    document.update(change)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(document), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError):
        PACK.load_pack(path)


@pytest.mark.parametrize("text", ['{"schema_version":1,"schema_version":1}', '{"x":NaN}', "[]"])
def test_duplicate_nonfinite_or_nonobject_pack_is_invalid(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8", newline="\n")
    with pytest.raises(ValueError):
        PACK.load_pack(path)


def test_cli_default_and_output_exclusivity(tmp_path):
    result = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True, check=True)
    study = json.loads(result.stdout)
    assert study["all_expected_invariants_observed"]
    output = tmp_path / "existing.json"
    output.write_text("historical evidence", encoding="utf-8", newline="\n")
    failed = subprocess.run(
        [sys.executable, str(TOOL), "--output", str(output)], capture_output=True, text=True
    )
    assert failed.returncode == 2
    assert output.read_text() == "historical evidence"
    assert not failed.stdout


def test_changed_seed_is_explicit_and_preserves_ambiguity_checks(tmp_path):
    document = json.loads(CONFIG.read_bytes())
    document["seed"] = 123
    path = tmp_path / "another-seed.json"
    path.write_text(json.dumps(document), encoding="utf-8", newline="\n")
    pack, digest = PACK.load_pack(path)
    other = PACK.build_report(pack, digest)
    assert other["pack_input"]["seed"] == 123
    assert other["pack_input_sha256"] != report()["pack_input_sha256"]
    assert other["all_expected_invariants_observed"]
    assert all(other["release_ack_ambiguity_checks"].values())
