#!/usr/bin/env python3
"""Deterministic offline fault witnesses using existing replay/mock/task contracts.

The private MockArm subclass below is only a diagnostic injection fixture. It
does not add unknown-held state, transport, recovery or hardware capabilities to
the package. Fixture oracle truth and observer knowledge remain separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from importlib.resources import files
from numbers import Real
from pathlib import Path

from raftel_arm01.config import load_config
from raftel_arm01.control.interface import ArmFault
from raftel_arm01.control.mock import MockArm
from raftel_arm01.control.thor_protocol_replay import DiagnosticReplay, SyntheticStatus
from raftel_arm01.evaluation.benchmark import canonical_sha256, implementation_fingerprint
from raftel_arm01.evaluation.replay import _json_object
from raftel_arm01.models import ObjectPose, Position
from raftel_arm01.perception.synthetic import generate_objects
from raftel_arm01.tasks.sorter import Sorter

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_CLASS = "logical_fault_injection_not_firmware_or_physical_validation"
PACK_REVISION = "thor-fault-injection-v1"
CASE_IDS = (
    "stale_status",
    "partial_status",
    "out_of_order_status",
    "shoulder_disagreement",
    "pending_command_reset",
    "lost_ack_incremental_retry",
    "grasp_ack_lost_after_effect",
    "release_ack_lost_before_effect",
    "release_ack_lost_after_effect",
    "reset_during_transfer",
    "grasp_false_exhaustion",
)
UNCERTAIN_TASK_CASES = CASE_IDS[6:10]
EXPECTED_FAULT = {
    "stale_status": "stale_or_future_status",
    "partial_status": "partial_or_malformed_status",
    "out_of_order_status": "out_of_order_or_malformed_status",
    "shoulder_disagreement": "duplicate_shoulder_disagreement",
    "pending_command_reset": "reset_invalidates_mode_offsets_and_position_knowledge",
}


def load_pack(path: Path) -> tuple[dict, str]:
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("fault pack exceeds64KiB")
    document = _json_object(raw)
    expected = {
        "schema_version",
        "pack_revision",
        "evidence_class",
        "seed",
        "protocol_max_age_s",
        "case_ids",
    }
    if (
        set(document) != expected
        or type(document["schema_version"]) is not int
        or document["schema_version"] != 1
    ):
        raise ValueError("fault pack requires exact schema1 fields")
    if document["pack_revision"] != PACK_REVISION or document["evidence_class"] != EVIDENCE_CLASS:
        raise ValueError("unsupported pack revision or evidence class")
    if type(document["seed"]) is not int or not 0 <= document["seed"] <= 2**32 - 1:
        raise ValueError("seed must be an integer within0..2**32-1")
    age = document["protocol_max_age_s"]
    if (
        isinstance(age, bool)
        or not isinstance(age, Real)
        or not 0 < age <= 60
        or not math.isfinite(age)
    ):
        raise ValueError("protocol_max_age_s must be finite within(0,60]")
    if not isinstance(document["case_ids"], list) or tuple(document["case_ids"]) != CASE_IDS:
        raise ValueError("fault pack must retain the exact eleven ordered case identities")
    return document, hashlib.sha256(raw).hexdigest()


def _capture_failure(function, expected_exception: type[Exception]) -> dict:
    try:
        function()
    except expected_exception as error:
        return {"rejected": True, "exception": type(error).__name__, "detail": str(error)}
    return {"rejected": False, "exception": None, "detail": None}


def _protocol_case(identifier: str, max_age: float) -> dict:
    replay = DiagnosticReplay(max_commands=8, max_pending=8)
    replay.submit("G0 B1 C1 D2")
    original = replay.status(0)
    initial_error = None
    if identifier == "pending_command_reset":
        replay.reset()
    else:
        now = max_age / 2
        status = original
        if identifier == "stale_status":
            now = max_age + 1
        elif identifier == "partial_status":
            status = replace(original, completed_steps=(0,) * 6)
        elif identifier == "shoulder_disagreement":
            status = replace(original, completed_steps=(0, 270, 0, 0, 0, 0, 0))
        elif identifier == "out_of_order_status":
            replay.observe_status(replay.status(now), now_s=now, max_age_s=max_age)
        else:
            raise ValueError("unsupported protocol fault case")
        initial_error = _capture_failure(
            lambda: replay.observe_status(status, now_s=now, max_age_s=max_age), ValueError
        )
    initial_fault = replay.fault
    operations = {
        "new_command": _capture_failure(lambda: replay.submit("G0 A1"), ValueError),
        "completion": _capture_failure(replay.complete_next, ValueError),
        "new_status": _capture_failure(lambda: replay.status(max_age + 1), ValueError),
        "fresh_good_observation": _capture_failure(
            lambda: replay.observe_status(
                SyntheticStatus(100, max_age + 1, (0,) * 7, 1), now_s=max_age + 1, max_age_s=max_age
            ),
            ValueError,
        ),
    }
    # Reset may replace the reason, but must not restore a ready state.
    replay.reset()
    after_reset = _capture_failure(lambda: replay.submit("G90"), ValueError)
    checks = {
        "expected_initial_fault": initial_fault == EXPECTED_FAULT[identifier],
        "initial_fault_observed": identifier == "pending_command_reset"
        or initial_error["rejected"],
        "all_followup_operations_rejected": all(item["rejected"] for item in operations.values()),
        "reset_does_not_recover": after_reset["rejected"] and replay.fault is not None,
        "no_false_completion": not replay.receipts[0].completed_in_simulation,
        "pending_command_invalidated": replay.receipts[0].invalidated_by_reset,
        "completed_steps_unchanged": replay.completed_steps == (0,) * 7,
    }
    return {
        "case_id": identifier,
        "kind": "existing_diagnostic_replay_fault",
        "initial_error": initial_error,
        "initial_fault": initial_fault,
        "followup_operations": operations,
        "fault_after_reset": replay.fault,
        "command_after_reset": after_reset,
        "receipts": [asdict(item) for item in replay.receipts],
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "state_origin": "command_derived_synthetic_steps_not_measured_pose",
    }


def _lost_ack_case() -> dict:
    replay = DiagnosticReplay(max_commands=8, max_pending=8)
    first = replay.submit("G91 A1", acknowledgment_received=False)
    retried = replay.submit("A1", acknowledgment_received=False)
    replay.complete_next()
    replay.complete_next()
    checks = {
        "first_effect_one": first.parser_target_deg[0] == 1,
        "retry_doubles_effect": retried.parser_target_deg[0] == 2,
        "no_ack_attribution_invented": all(not item.acknowledged for item in replay.receipts),
        "synthetic_execution_can_precede_ack": all(
            item.completed_in_simulation for item in replay.receipts
        ),
    }
    return {
        "case_id": "lost_ack_incremental_retry",
        "kind": "unsafe_automatic_retry_counterexample",
        "receipts": [asdict(item) for item in replay.receipts],
        "completed_steps": replay.completed_steps,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "automatic_retry_demonstrated_safe": False,
        "acknowledgment_scope": (
            "per_command_synthetic_ground_truth_not_real_untagged_ok_attribution"
        ),
    }


class _InjectedMockArm(MockArm):
    """Tool-only injection fixture; observer knowledge is not a core capability."""

    def __init__(self, config, injection: str):
        super().__init__(config.envelope)
        self.injection = injection
        self.injected = False
        self.held_knowledge = "known_empty_in_mock"
        self.observer_calls = []
        self.replay = DiagnosticReplay(max_commands=8, max_pending=8)

    def move_to(self, position: Position) -> None:
        self.observer_calls.append({"method": "move_to", "position": asdict(position)})
        self._ready()
        if (
            self.held is not None
            and self.injection == "reset_during_transfer"
            and not self.injected
        ):
            self.replay.submit("G0 B1 C1 D2")
            self.replay.reset()
            self.injected = True
            self.held_knowledge = "unknown_after_fault"
            raise ArmFault("synthetic protocol reset; held-object state unknown")
        super().move_to(position)

    def grasp(self, obj: ObjectPose) -> bool:
        self.observer_calls.append({"method": "grasp", "object_id": obj.identifier})
        self._ready()
        if self.injection == "grasp_ack_lost_after_effect" and not self.injected:
            super().grasp(obj)
            self.injected = True
            self.held_knowledge = "unknown_after_fault"
            raise ArmFault("synthetic grasp acknowledgment lost; held-object state unknown")
        held = super().grasp(obj)
        if held:
            self.held_knowledge = "known_held_in_mock"
        return held

    def release(self) -> None:
        self.observer_calls.append({"method": "release"})
        self._ready()
        if (
            self.injection in {"release_ack_lost_before_effect", "release_ack_lost_after_effect"}
            and not self.injected
        ):
            if self.injection == "release_ack_lost_after_effect":
                super().release()
            self.injected = True
            self.held_knowledge = "unknown_after_fault"
            raise ArmFault("synthetic release acknowledgment lost; held-object state unknown")
        super().release()
        self.held_knowledge = "known_empty_in_mock"

    def verify_placement(self, obj: ObjectPose, destination: Position) -> bool:
        self.observer_calls.append(
            {
                "method": "verify_placement",
                "object_id": obj.identifier,
                "destination": asdict(destination),
            }
        )
        return super().verify_placement(obj, destination)

    def stop(self) -> None:
        self.observer_calls.append({"method": "stop"})
        super().stop()


def _task_case(identifier: str, seed: int) -> dict:
    config = load_config()
    objects = generate_objects(seed, 2, categories=tuple(item.category for item in config.bins))
    arm = _InjectedMockArm(config, identifier)
    result = Sorter(arm, config).run(objects)
    oracle_before_stop = {
        "held_object_id": None if arm.held is None else arm.held.identifier,
        "placement_ids": sorted(arm.placements),
    }
    arm.stop()
    arm.stop()
    after_stop = {
        "held_object_id": None if arm.held is None else arm.held.identifier,
        "placement_ids": sorted(arm.placements),
    }
    blocked = {
        "move": _capture_failure(lambda: arm.move_to(objects[0].position), ArmFault),
        "grasp": _capture_failure(lambda: arm.grasp(objects[0]), ArmFault),
        "release": _capture_failure(arm.release, ArmFault),
        "verification": _capture_failure(
            lambda: arm.verify_placement(objects[0], objects[0].position), ArmFault
        ),
    }
    rerun = Sorter(arm, config).run(objects)
    after_rerun = {
        "held_object_id": None if arm.held is None else arm.held.identifier,
        "placement_ids": sorted(arm.placements),
    }
    observer_trace = {
        "calls": arm.observer_calls,
        "task_events": result.records(),
        "task_summary": result.summary(),
        "blocked_operations": blocked,
        "rerun_events": rerun.records(),
        "rerun_summary": rerun.summary(),
    }
    checks = {
        "injection_observed": arm.injected,
        "task_aborted": result.aborted,
        "no_false_sorted_claim": not result.sorted_ids,
        "remaining_object_pending": result.pending_ids == (objects[1].identifier,),
        "one_grasp_attempt_no_blind_retry": sum(event.state == "grasp" for event in result.events)
        == 1,
        "stop_latched": arm.stopped,
        "repeated_stop_preserves_oracle_state": oracle_before_stop == after_stop,
        "rejected_operations_and_rerun_preserve_oracle_state": after_rerun == after_stop,
        "post_stop_operations_rejected": all(value["rejected"] for value in blocked.values()),
        "rerun_does_not_recover": rerun.aborted and not rerun.sorted_ids,
        "unknown_knowledge_not_cleared": arm.held_knowledge == "unknown_after_fault",
    }
    return {
        "case_id": identifier,
        "kind": "tool_only_mock_fault_injection",
        "observer_trace": observer_trace,
        "observer_trace_sha256": canonical_sha256(observer_trace),
        "held_object_knowledge": {
            "value": arm.held_knowledge,
            "origin": "pack_only_bookkeeping_not_core_MockArm_feedback",
            "automatic_recovery_allowed": False,
        },
        "fixture_oracle_truth": {
            "before_repeated_stop": oracle_before_stop,
            "after_repeated_stop": after_stop,
            "after_rejected_operations_and_rerun": after_rerun,
            "scope": "synthetic_fixture_truth_not_observer_evidence_or_physical_measurement",
        },
        "input_objects": [asdict(item) for item in objects],
        "input_config": asdict(config),
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def _grasp_budget_case(seed: int) -> dict:
    config = load_config()
    objects = generate_objects(seed, 2, categories=tuple(item.category for item in config.bins))
    arm = MockArm(config.envelope, failed_grasps={objects[0].identifier})
    result = Sorter(arm, config).run(objects)
    failed_attempts = [
        event.attempt
        for event in result.events
        if event.state == "grasp" and event.object_id == objects[0].identifier
    ]
    checks = {
        "retry_budget_exact": failed_attempts == list(range(1, config.max_attempts + 1)),
        "failed_object_not_sorted": result.failed_ids == (objects[0].identifier,),
        "next_object_accounted": result.sorted_ids == (objects[1].identifier,),
        "no_abort_or_pending": not result.aborted and not result.pending_ids,
        "only_successful_object_placed": sorted(arm.placements) == [objects[1].identifier],
        "failed_grasp_did_not_hold_object": arm.held is None,
    }
    return {
        "case_id": "grasp_false_exhaustion",
        "kind": "existing_mock_failed_grasp_retry_budget",
        "configured_max_attempts": config.max_attempts,
        "observed_failed_object_attempts": failed_attempts,
        "task_summary": result.summary(),
        "task_events": result.records(),
        "input_objects": [asdict(item) for item in objects],
        "input_config": asdict(config),
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "scope": "ordinary_false_grasp_retry_is_distinct_from_ArmFault_abort",
    }


def build_report(pack: dict, pack_sha256: str) -> dict:
    cases = [_protocol_case(identifier, pack["protocol_max_age_s"]) for identifier in CASE_IDS[:5]]
    cases.append(_lost_ack_case())
    cases.extend(_task_case(identifier, pack["seed"]) for identifier in UNCERTAIN_TASK_CASES)
    cases.append(_grasp_budget_case(pack["seed"]))
    before = next(item for item in cases if item["case_id"] == "release_ack_lost_before_effect")
    after = next(item for item in cases if item["case_id"] == "release_ack_lost_after_effect")
    ambiguity = {
        "observer_visible_traces_identical": before["observer_trace"] == after["observer_trace"],
        "fixture_oracle_worlds_differ": before["fixture_oracle_truth"]
        != after["fixture_oracle_truth"],
        "both_observer_knowledge_unknown": all(
            item["held_object_knowledge"]["value"] == "unknown_after_fault"
            for item in (before, after)
        ),
        "neither_world_claims_sorted": all(
            item["observer_trace"]["task_summary"]["sorted"] == 0 for item in (before, after)
        ),
    }
    fingerprint = implementation_fingerprint()
    package = files("raftel_arm01")
    for path in ("control/thor_protocol_replay.py", "control/thor_source_conversion.py"):
        fingerprint["installed_file_sha256"][path] = hashlib.sha256(
            package.joinpath(*path.split("/")).read_bytes()
        ).hexdigest()
    return {
        "schema_version": 1,
        "pack_revision": PACK_REVISION,
        "evidence_class": EVIDENCE_CLASS,
        "pack_input": pack,
        "pack_input_sha256": pack_sha256,
        "producer_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "implementation_fingerprint": fingerprint,
        "cases": cases,
        "release_ack_ambiguity_checks": ambiguity,
        "all_expected_invariants_observed": all(item["all_checks_passed"] for item in cases)
        and all(ambiguity.values()),
        "hardware_connected": False,
        "firmware_executed": False,
        "limitations": [
            "Existing DiagnosticReplay and logical sorter behavior only; no actual firmware parser",
            "Fault adapters and unknown-held bookkeeping live only in this tool",
            "Fixture oracle truth never establishes observer knowledge or physical state",
            (
                "An acknowledgment, command-derived step count or logical placement "
                "is not measured motion"
            ),
            "No autonomous recovery, backend, transport or physical safety acceptance",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/thor-fault-injection-v1.json")
    parser.add_argument("--output", type=Path, help="New report path; existing evidence is refused")
    args = parser.parse_args(argv)
    try:
        pack, digest = load_pack(args.config)
        report = build_report(pack, digest)
        encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            sys.stdout.write(encoded)
        else:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
    except (OSError, ValueError, TypeError, OverflowError) as error:
        print(f"Fault injection study failed: {error}", file=sys.stderr)
        return 2
    return 0 if report["all_expected_invariants_observed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
