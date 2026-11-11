"""Revisioned offline calibration evidence, deliberately not runtime settings.

Known source constants, assumptions, synthetic fixtures and physical records
remain different states. Even a complete physical record is not commissioning:
limits, motor-energy isolation, feedback, collision and supervised acceptance
are outside this schema. No function exports driver or firmware configuration.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from numbers import Real
from pathlib import Path
from typing import Any

_STATES = {"unknown", "source", "assumed", "synthetic", "physical"}
_SHA256 = re.compile(r"[0-9a-f]{64}", re.ASCII)
_REVISION = re.compile(r"[0-9a-f]{40}", re.ASCII)
CHANNEL_ORDER = ["A", "B", "C", "D", "X", "Y", "Z"]
# Units are explicit source-coordinate units, not measured physical shaft units.
_PARAMETERS = {
    "shoulder_branch_ratio": ("1", "positive", 1),
    "elbow_gearbox_ratio": ("1", "positive", 1),
    "elbow_belt_ratio": ("1", "positive", 1),
    "carrier_coefficient": ("1", "finite", 1),
    "elbow_belt_sign": ("1", "sign", 1),
    "wrist_handedness": ("1", "sign", 1),
    "wrist_negative_y_rotor_scale": ("1", "nonzero", 1),
    "wrist_positive_y_rotor_scale": ("1", "nonzero", 1),
    "channel_steps_per_degree": ("step/source_degree", "positive", 7),
    "channel_zero_deg": ("source_degree", "finite", 7),
}


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{label} must be nonempty bounded text")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be finite numeric data")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{label} must be finite numeric data") from error
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite numeric data")
    return result


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _keys(record: Mapping, expected: set[str], label: str) -> None:
    if set(record) != expected:
        raise ValueError(f"{label} fields differ: expected {sorted(expected)}")


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 hash")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON evidence field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON evidence constant: {value}")


def _evidence(state: str, evidence: Any, label: str) -> None:
    if not isinstance(evidence, list) or len(evidence) > 64:
        raise ValueError(f"{label} evidence must be a bounded list")
    if state == "unknown":
        if evidence:
            raise ValueError(f"{label} unknown state must keep supporting evidence empty")
        return
    if not evidence:
        raise ValueError(f"{label} known state requires supporting evidence")
    for item in evidence:
        item = _mapping(item, label)
        if state == "source":
            _keys(item, {"reference", "revision", "sha256"}, label)
            _text(item["reference"], label)
            revision = item["revision"]
            if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
                raise ValueError(f"{label} source evidence requires an immutable Git revision")
            _hash(item["sha256"], label)
        elif state == "assumed":
            _keys(item, {"rationale", "revisit_trigger"}, label)
            _text(item["rationale"], label)
            _text(item["revisit_trigger"], label)
        elif state == "synthetic":
            _keys(item, {"fixture", "sha256", "seed"}, label)
            _text(item["fixture"], label)
            _hash(item["sha256"], label)
            if type(item["seed"]) is not int or not 0 <= item["seed"] <= 2**32 - 1:
                raise ValueError(f"{label} synthetic evidence requires a bounded integer seed")
        elif state == "physical":
            _keys(item, {"record", "sha256", "instrument", "observed_at", "conditions"}, label)
            for field in ("record", "instrument", "conditions"):
                _text(item[field], label)
            _hash(item["sha256"], label)
            observed_at = _text(item["observed_at"], label)
            # Explicit UTC is required to prevent ambiguous local measurement times.
            try:
                parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError(
                    f"{label} physical observation requires an ISO timestamp"
                ) from error
            if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
                raise ValueError(f"{label} physical observation timestamp must be UTC")


@dataclass(frozen=True)
class CalibrationSummary:
    revision: str
    unknown_parameters: tuple[str, ...]
    nonphysical_parameters: tuple[str, ...]
    unknown_artifact_hashes: tuple[str, ...]
    analysis_inputs_complete: bool
    commissioned: bool = False
    evidence_class: str = "offline_calibration_record_not_commissioning"


def validate_calibration_document(document: Mapping[str, Any]) -> CalibrationSummary:
    """Validate provenance and units without promoting a record to commissioning."""
    document = _mapping(document, "calibration")
    _keys(
        document,
        {
            "schema_version",
            "revision",
            "evidence_class",
            "commissioning_status",
            "channel_order",
            "parameters",
            "artifacts",
        },
        "calibration",
    )
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("unsupported calibration schema version")
    revision = _text(document["revision"], "revision")
    if document["evidence_class"] != "offline_calibration_record_not_commissioning":
        raise ValueError("calibration evidence class must remain offline")
    if document["commissioning_status"] != "not_commissioned":
        raise ValueError("this evidence schema cannot assert commissioned settings")
    if document["channel_order"] != CHANNEL_ORDER:
        raise ValueError("channel order must explicitly remain A,B,C,D,X,Y,Z")
    parameters = _mapping(document["parameters"], "parameters")
    _keys(parameters, set(_PARAMETERS), "parameters")
    unknown, nonphysical = [], []
    for name, (unit, bound, count) in _PARAMETERS.items():
        record = _mapping(parameters[name], name)
        _keys(record, {"state", "value", "unit", "uncertainty_abs", "evidence"}, name)
        state = record["state"]
        if not isinstance(state, str) or state not in _STATES:
            raise ValueError(f"{name} has unsupported evidence state")
        if record["unit"] != unit:
            raise ValueError(f"{name} must use unit {unit}")
        _evidence(state, record["evidence"], name)
        if state != "physical":
            nonphysical.append(name)
        if state == "unknown":
            if record["value"] is not None or record["uncertainty_abs"] is not None:
                raise ValueError(f"{name} unknown values and uncertainty must remain null")
            unknown.append(name)
            continue
        values = record["value"]
        if count == 1:
            values = [values]
        elif not isinstance(values, list) or len(values) != count:
            raise ValueError(f"{name} requires {count} channel values")
        numbers = [_number(value, name) for value in values]
        if bound == "positive" and any(value <= 0 for value in numbers):
            raise ValueError(f"{name} must be positive")
        if bound == "nonzero" and any(value == 0 for value in numbers):
            raise ValueError(f"{name} must be nonzero")
        if bound == "sign" and any(
            type(value) is not int or value not in {-1, 1} for value in values
        ):
            raise ValueError(f"{name} requires an explicit integer sign +1 or -1")
        uncertainty = record["uncertainty_abs"]
        if state == "physical" and uncertainty is None:
            raise ValueError(f"{name} physical evidence requires uncertainty")
        if uncertainty is not None:
            if count == 1:
                uncertainty = [uncertainty]
            elif not isinstance(uncertainty, list) or len(uncertainty) != count:
                raise ValueError(f"{name} requires {count} uncertainty values")
            if any(_number(value, name) < 0 for value in uncertainty):
                raise ValueError(f"{name} uncertainty must be nonnegative")
    artifacts = _mapping(document["artifacts"], "artifacts")
    _keys(artifacts, {"installed_firmware", "installed_settings"}, "artifacts")
    missing_hashes = []
    for name, artifact in artifacts.items():
        artifact = _mapping(artifact, name)
        _keys(artifact, {"state", "sha256", "evidence"}, name)
        state = artifact["state"]
        if not isinstance(state, str) or state not in _STATES:
            raise ValueError(f"{name} has unsupported evidence state")
        _evidence(state, artifact["evidence"], name)
        if state == "unknown":
            if artifact["sha256"] is not None:
                raise ValueError(f"{name} unknown hash must remain null")
            missing_hashes.append(name)
        else:
            _hash(artifact["sha256"], name)
    return CalibrationSummary(
        revision,
        tuple(unknown),
        tuple(nonphysical),
        tuple(missing_hashes),
        not unknown and not missing_hashes,
    )


def load_calibration(path: Path, *, expected_sha256: str | None = None) -> CalibrationSummary:
    """Load a bounded local evidence document, optionally bound to its exact bytes."""
    raw = Path(path).read_bytes()
    if len(raw) > 1_048_576:
        raise ValueError("calibration record exceeds one MiB")
    if expected_sha256 is not None:
        _hash(expected_sha256, "expected_sha256")
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError("calibration evidence file hash is stale")
    try:
        document = json.loads(
            raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (ValueError, UnicodeError) as error:
        raise ValueError("malformed calibration JSON") from error
    return validate_calibration_document(document)
