"""Strict, bounded outcome replay with predeclared denominators and honest misses.

This consumes observations, not actuator commands. A recorded independent
verification is a data claim; the scorer cannot establish that it happened.
"""

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

EVIDENCE_CLASSES = frozenset(
    {"logical_only", "kinematic_simulation", "physics_simulation", "physical"}
)
MAX_OBJECTS = 10_000
MAX_EVENTS = 1_000_000
MAX_LINE_BYTES = 1_048_576
MAX_FILE_BYTES = 67_108_864
MAX_AGGREGATE_OBJECTS = 10_000_000


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise ValueError(f"{name} must be nonempty text of at most 512 characters")
    return value


def _integer(value: object, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def _fields(record: Mapping, required: set[str], optional: set[str], name: str) -> None:
    if not isinstance(record, Mapping) or not required <= record.keys():
        raise ValueError(f"{name} is missing required fields")
    if record.keys() - required - optional:
        raise ValueError(f"{name} contains unknown fields")


@dataclass(frozen=True)
class PresentedObject:
    identifier: str
    expected_bin: str
    eligible: bool


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    layout_id: str
    evidence_class: str
    provenance: str
    max_attempts: int
    objects: tuple[PresentedObject, ...]

    @classmethod
    def from_dict(cls, record: Mapping) -> "RunManifest":
        _fields(
            record,
            {
                "schema_version",
                "run_id",
                "layout_id",
                "evidence_class",
                "provenance",
                "max_attempts",
                "objects",
            },
            set(),
            "manifest",
        )
        if type(record["schema_version"]) is not int or record["schema_version"] != 1:
            raise ValueError("unsupported manifest schema_version")
        evidence = _text(record["evidence_class"], "evidence_class")
        if evidence not in EVIDENCE_CLASSES:
            raise ValueError("unsupported evidence class")
        rows = record["objects"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_OBJECTS:
            raise ValueError(f"objects must contain 1..{MAX_OBJECTS} predeclared objects")
        objects = []
        for row in rows:
            _fields(row, {"id", "expected_bin", "eligible"}, set(), "presented object")
            if type(row["eligible"]) is not bool:
                raise ValueError("eligibility must be a predeclared boolean")
            objects.append(
                PresentedObject(
                    _text(row["id"], "id"),
                    _text(row["expected_bin"], "expected_bin"),
                    row["eligible"],
                )
            )
        if len({row.identifier for row in objects}) != len(objects):
            raise ValueError("duplicate presented object IDs")
        return cls(
            _text(record["run_id"], "run_id"),
            _text(record["layout_id"], "layout_id"),
            evidence,
            _text(record["provenance"], "provenance"),
            _integer(record["max_attempts"], "max_attempts", 1, 20),
            tuple(objects),
        )


@dataclass
class _Outcome:
    detected: bool = False
    attempts: int = 0
    active_attempt: int | None = None
    correct_attempt: int | None = None
    assisted: bool = False
    timed_out: bool = False
    misroutes: int = 0
    failures: int = 0


def wilson_interval(successes: int, trials: int) -> list[float] | None:
    """95% object-level Wilson interval; does not model within-layout correlation."""
    _integer(trials, "trials", 0, MAX_AGGREGATE_OBJECTS)
    _integer(successes, "successes", 0, trials)
    if trials == 0:
        return None
    z = 1.959963984540054
    p = successes / trials
    divisor = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / divisor
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / divisor
    return [max(0.0, center - radius), min(1.0, center + radius)]


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score_replay(manifest: RunManifest | Mapping, events: Iterable[Mapping]) -> dict:
    """Replay ordered observations, including truncated logs as unresolved outcomes.

    Retries require a closed prior attempt; detections and attempt starts alone
    never count as correct placements. Assisted objects stay out of autonomous
    success counts while remaining in all predeclared denominators.
    """
    if not isinstance(manifest, RunManifest):
        manifest = RunManifest.from_dict(manifest)
    else:
        # Dataclass constructors must not bypass input validation.
        manifest = RunManifest.from_dict(
            {
                "schema_version": 1,
                "run_id": manifest.run_id,
                "layout_id": manifest.layout_id,
                "evidence_class": manifest.evidence_class,
                "provenance": manifest.provenance,
                "max_attempts": manifest.max_attempts,
                "objects": [
                    {
                        "id": row.identifier,
                        "expected_bin": row.expected_bin,
                        "eligible": row.eligible,
                    }
                    for row in manifest.objects
                ],
            }
        )
    objects = {row.identifier: row for row in manifest.objects}
    states = {identifier: _Outcome() for identifier in objects}
    count = 0
    for sequence, event in enumerate(events):
        if sequence >= MAX_EVENTS:
            raise ValueError("event limit exceeded")
        _fields(
            event,
            {"sequence", "event", "object_id"},
            {"attempt", "observed_bin", "independent_verification", "detail"},
            "event",
        )
        if _integer(event["sequence"], "sequence", 0, MAX_EVENTS - 1) != sequence:
            raise ValueError("event sequences must be contiguous and start at zero")
        identifier = _text(event["object_id"], "object_id")
        if identifier not in objects:
            raise ValueError("event references an undeclared object")
        kind = _text(event["event"], "event")
        state = states[identifier]
        obj = objects[identifier]
        if state.correct_attempt is not None or state.timed_out:
            raise ValueError("event after terminal object outcome")
        if "detail" in event:
            _text(event["detail"], "detail")
        required_fields = {
            "detected": set(),
            "attempted": {"attempt"},
            "verified": {"attempt", "observed_bin", "independent_verification"},
            "failed": {"attempt", "detail"},
            "timed_out": set(),
            "assisted": {"detail"},
        }
        if kind not in required_fields:
            raise ValueError("unsupported observation event")
        specific = event.keys() - {"sequence", "event", "object_id", "detail"}
        if (
            specific != required_fields[kind] - {"detail"}
            or not required_fields[kind] <= event.keys()
        ):
            raise ValueError(f"invalid fields for {kind} event")
        if kind == "detected":
            if state.detected or state.attempts:
                raise ValueError("duplicate or late detection")
            state.detected = True
        elif kind == "attempted":
            attempt = _integer(event["attempt"], "attempt", 1, manifest.max_attempts)
            if not obj.eligible or not state.detected or state.active_attempt is not None:
                raise ValueError("attempt requires eligibility, detection and no active attempt")
            if attempt != state.attempts + 1:
                raise ValueError("attempt numbers must be consecutive")
            state.attempts = attempt
            state.active_attempt = attempt
        elif kind in {"verified", "failed"}:
            attempt = _integer(event["attempt"], "attempt", 1, manifest.max_attempts)
            if state.active_attempt != attempt:
                raise ValueError("outcome requires the matching active attempt")
            if kind == "verified":
                if event["independent_verification"] is not True:
                    raise ValueError("placement requires an explicit independent observation claim")
                observed = _text(event["observed_bin"], "observed_bin")
                if observed == obj.expected_bin:
                    state.correct_attempt = attempt
                else:
                    state.misroutes += 1
                    state.failures += 1
            else:
                state.failures += 1
            state.active_attempt = None
        elif kind == "timed_out":
            state.timed_out = True
            state.active_attempt = None
        else:
            if state.assisted:
                raise ValueError("duplicate assistance")
            state.assisted = True
        count += 1
    rows = []
    for identifier, obj in objects.items():
        state = states[identifier]
        autonomous = state.correct_attempt is not None and not state.assisted
        rows.append(
            {
                "id": identifier,
                "eligible": obj.eligible,
                "detected": state.detected,
                "attempts": state.attempts,
                "autonomous_correct": autonomous,
                "first_attempt_correct": autonomous and state.correct_attempt == 1,
                "correct_after_retry": autonomous and state.correct_attempt > 1,
                "assisted": state.assisted,
                "assisted_correct": state.assisted and state.correct_attempt is not None,
                "timed_out": state.timed_out,
                "misroutes": state.misroutes,
                "failed_attempts": state.failures,
                "failed": obj.eligible
                and state.correct_attempt is None
                and (
                    state.timed_out
                    or (state.attempts == manifest.max_attempts and state.active_attempt is None)
                ),
                "unresolved": obj.eligible
                and state.correct_attempt is None
                and not state.timed_out
                and (state.active_attempt is not None or state.attempts < manifest.max_attempts),
                "detection_miss": obj.eligible and not state.detected,
            }
        )
    presented = len(rows)
    eligible = sum(row["eligible"] for row in rows)
    attempted = sum(row["attempts"] > 0 for row in rows)
    correct = sum(row["autonomous_correct"] for row in rows)
    first = sum(row["first_attempt_correct"] for row in rows)
    counts = {
        "presented": presented,
        "eligible": eligible,
        "excluded": presented - eligible,
        "detected": sum(row["detected"] for row in rows),
        "attempted": attempted,
        "attempts": sum(row["attempts"] for row in rows),
        "correct": correct,
        "first_attempt_correct": first,
        "correct_after_retry": correct - first,
        "unsuccessful_attempted_objects": attempted - correct,
        "assisted": sum(row["assisted"] for row in rows),
        "assisted_correct": sum(row["assisted_correct"] for row in rows),
        "timed_out": sum(row["timed_out"] for row in rows),
        "detection_misses": sum(row["detection_miss"] for row in rows),
        "unresolved": sum(row["unresolved"] for row in rows),
        "misroutes": sum(row["misroutes"] for row in rows),
        "failed_attempts": sum(row["failed_attempts"] for row in rows),
        "failed": sum(row["failed"] for row in rows),
    }
    return {
        "schema_version": 1,
        "run_id": manifest.run_id,
        "layout_id": manifest.layout_id,
        "evidence_class": manifest.evidence_class,
        "provenance": manifest.provenance,
        "input_event_count": count,
        "counts": counts,
        "objects": rows,
        "metrics": {
            "attempted_coverage": _ratio(attempted, presented),
            "eligible_coverage": _ratio(eligible, presented),
            "first_attempt_cycle_success": _ratio(first, attempted),
            "after_retry_cycle_success": _ratio(correct, attempted),
            "eligible_end_to_end_completion": _ratio(correct, eligible),
            "presented_end_to_end_completion": _ratio(correct, presented),
            "cycle_success_wilson_95_object_level": wilson_interval(correct, attempted),
        },
        "limitations": [
            "Recorded observations are input claims; physical evidence is not authenticated.",
            "Assisted objects remain in denominators and never count as autonomous successes.",
            "Object-level interval does not account for correlation within a layout.",
            "Simulation results cannot establish physical sorting reliability.",
        ],
    }


def _json_object(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite JSON number")
        return parsed

    def invalid_constant(value):
        raise ValueError(f"nonfinite JSON constant: {value}")

    try:
        record = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=number,
            parse_constant=invalid_constant,
        )
    except RecursionError as exc:
        raise ValueError("JSON nesting limit exceeded") from exc
    if not isinstance(record, dict):
        raise ValueError("JSON record must be an object")
    return record


def read_manifest(path: Path) -> RunManifest:
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_LINE_BYTES + 1)
    if len(raw) > MAX_LINE_BYTES:
        raise ValueError("manifest size limit exceeded")
    return RunManifest.from_dict(_json_object(raw))


def read_jsonl(path: Path, *, max_events: int = MAX_EVENTS) -> list[dict]:
    """Read bounded UTF-8 records; reject duplicate keys and nonfinite constants."""
    _integer(max_events, "max_events", 1, MAX_EVENTS)
    records = []
    total_bytes = 0
    with Path(path).open("rb") as stream:
        for number in range(max_events + 1):
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                break
            if len(line) > MAX_LINE_BYTES or number == max_events:
                raise ValueError("JSONL size/record limit exceeded")
            total_bytes += len(line)
            if total_bytes > MAX_FILE_BYTES:
                raise ValueError("JSONL total size limit exceeded")
            if not line.strip():
                raise ValueError("blank JSONL lines are not records")
            records.append(_json_object(line))
    return records
