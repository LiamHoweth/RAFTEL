"""Hand-counted observations and adversarial logs; no physical trials."""

import copy
import json

import pytest

from raftel_arm01.evaluation.replay import (
    MAX_LINE_BYTES,
    RunManifest,
    read_jsonl,
    score_replay,
    wilson_interval,
)


def manifest():
    return {
        "schema_version": 1,
        "run_id": "hand-counted",
        "layout_id": "layout-1",
        "evidence_class": "logical_only",
        "provenance": "hand-counted synthetic fixture; no physical observations",
        "max_attempts": 2,
        "objects": [
            {"id": name, "expected_bin": "red", "eligible": name != "excluded"}
            for name in (
                "first",
                "retry",
                "miss",
                "assisted",
                "timeout",
                "active",
                "failed",
                "excluded",
            )
        ],
    }


def observations():
    rows = []

    def add(identifier, kind, **fields):
        rows.append({"sequence": len(rows), "event": kind, "object_id": identifier, **fields})

    add("first", "detected")
    add("first", "attempted", attempt=1)
    add("first", "verified", attempt=1, observed_bin="red", independent_verification=True)
    add("retry", "detected")
    add("retry", "attempted", attempt=1)
    add("retry", "verified", attempt=1, observed_bin="blue", independent_verification=True)
    add("retry", "attempted", attempt=2)
    add("retry", "verified", attempt=2, observed_bin="red", independent_verification=True)
    add("assisted", "detected")
    add("assisted", "attempted", attempt=1)
    add("assisted", "assisted", detail="synthetic intervention")
    add("assisted", "verified", attempt=1, observed_bin="red", independent_verification=True)
    add("timeout", "timed_out")
    add("active", "detected")
    add("active", "attempted", attempt=1)
    add("failed", "detected")
    for attempt in (1, 2):
        add("failed", "attempted", attempt=attempt)
        add("failed", "failed", attempt=attempt, detail="synthetic failed grasp")
    return rows


def test_hand_counted_denominators_misses_retries_assistance_and_partial_log():
    report = score_replay(manifest(), observations())
    counts = report["counts"]
    assert counts == {
        "presented": 8,
        "eligible": 7,
        "excluded": 1,
        "detected": 5,
        "attempted": 5,
        "attempts": 7,
        "correct": 2,
        "first_attempt_correct": 1,
        "correct_after_retry": 1,
        "unsuccessful_attempted_objects": 3,
        "assisted": 1,
        "assisted_correct": 1,
        "timed_out": 1,
        "detection_misses": 2,
        "unresolved": 2,
        "misroutes": 1,
        "failed_attempts": 3,
        "failed": 2,
    }
    assert report["evidence_class"] == "logical_only"
    assert report["metrics"]["first_attempt_cycle_success"] == 1 / 5
    assert report["metrics"]["after_retry_cycle_success"] == 2 / 5
    assert report["metrics"]["eligible_end_to_end_completion"] == 2 / 7
    assert report["metrics"]["presented_end_to_end_completion"] == 2 / 8
    assert report == score_replay(RunManifest.from_dict(manifest()), observations())


def test_empty_log_never_discards_presented_or_eligible_objects():
    report = score_replay(manifest(), [])
    assert report["counts"]["presented"] == 8
    assert report["counts"]["detection_misses"] == 7
    assert report["counts"]["correct"] == 0
    assert report["counts"]["unresolved"] == 7
    assert report["metrics"]["after_retry_cycle_success"] is None
    assert report["metrics"]["eligible_end_to_end_completion"] == 0
    assert report["metrics"]["cycle_success_wilson_95_object_level"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.update(sequence=True),
        lambda row: row.update(sequence=2),
        lambda row: row.update(object_id="undeclared"),
        lambda row: row.update(event="sent_command"),
        lambda row: row.update(independent_verification=True),
        lambda row: row.update(attempt=0),
        lambda row: row.update(detail=""),
        lambda row: row.update(unrecognized="ignored?"),
    ],
)
def test_malformed_or_out_of_order_events_are_rejected(mutation):
    row = observations()[0]
    mutation(row)
    with pytest.raises(ValueError):
        score_replay(manifest(), [row])


@pytest.mark.parametrize("verified", [False, 1, "true", None])
def test_command_or_unverified_placement_cannot_be_scored_as_success(verified):
    rows = observations()[:3]
    rows[-1]["independent_verification"] = verified
    with pytest.raises(ValueError):
        score_replay(manifest(), rows)


def test_repeat_or_skipped_attempts_active_overlap_and_terminal_events_fail():
    fixtures = [
        [
            observations()[0],
            {"sequence": 1, "event": "attempted", "object_id": "first", "attempt": 2},
        ],
        observations()[:2]
        + [{"sequence": 2, "event": "attempted", "object_id": "first", "attempt": 2}],
        observations()[:3] + [{"sequence": 3, "event": "detected", "object_id": "first"}],
        [{"sequence": 0, "event": "attempted", "object_id": "first", "attempt": 1}],
        [
            {"sequence": 0, "event": "detected", "object_id": "excluded"},
            {"sequence": 1, "event": "attempted", "object_id": "excluded", "attempt": 1},
        ],
    ]
    for fixture in fixtures:
        with pytest.raises(ValueError):
            score_replay(manifest(), fixture)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("max_attempts", 0),
        ("max_attempts", True),
        ("max_attempts", 21),
        ("evidence_class", "hardware_success"),
        ("objects", []),
        ("provenance", ""),
    ],
)
def test_invalid_manifests_fail_without_denominator_inference(key, value):
    record = manifest()
    record[key] = value
    with pytest.raises(ValueError):
        score_replay(record, [])


def test_eligibility_duplicate_ids_unknown_fields_and_direct_dataclass_are_validated():
    original = manifest()
    cases = []
    record = copy.deepcopy(original)
    record["objects"][0]["eligible"] = "yes"
    cases.append(record)
    record = copy.deepcopy(original)
    record["objects"][1]["id"] = "first"
    cases.append(record)
    record = copy.deepcopy(original)
    record["motion_allowed"] = True
    cases.append(record)
    for record in cases:
        with pytest.raises(ValueError):
            RunManifest.from_dict(record)
    valid = RunManifest.from_dict(original)
    invalid = RunManifest(
        valid.run_id, valid.layout_id, "fake", valid.provenance, valid.max_attempts, valid.objects
    )
    with pytest.raises(ValueError):
        score_replay(invalid, [])


def test_wilson_known_reference_and_endpoints():
    # Independently tabulated two-sided 95% Wilson score interval for 90/100.
    assert wilson_interval(90, 100) == pytest.approx([0.8256343385, 0.9447708629], abs=1e-10)
    assert wilson_interval(0, 100)[0] == pytest.approx(0, abs=1e-15)
    assert wilson_interval(100, 100)[1] == pytest.approx(1)
    assert wilson_interval(0, 0) is None
    for args in [(1, 0), (True, 1), (2, 1), (0, -1)]:
        with pytest.raises(ValueError):
            wilson_interval(*args)


@pytest.mark.parametrize(
    "text",
    ["\n", "[]\n", '{"sequence":0,"sequence":1}\n', '{"x":NaN}\n', "{broken}\n", "\udcff"],
)
def test_jsonl_rejects_ambiguous_malformed_or_nonfinite_records(tmp_path, text):
    path = tmp_path / "events.jsonl"
    path.write_bytes(text.encode("utf-8", errors="surrogatepass"))
    with pytest.raises((ValueError, UnicodeError)):
        read_jsonl(path)


def test_jsonl_bounded_reader_and_order_preservation(tmp_path):
    path = tmp_path / "events.jsonl"
    rows = observations()
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert read_jsonl(path) == rows
    with pytest.raises(ValueError, match="limit"):
        read_jsonl(path, max_events=1)
    path.write_bytes(b" " * (MAX_LINE_BYTES + 1))
    with pytest.raises(ValueError, match="limit"):
        read_jsonl(path)
