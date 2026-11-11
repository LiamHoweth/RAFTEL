"""Bounded offline observation replay, with explicit clocks, frames and misses.

Input observations and their provenance are supplied claims, not camera access,
calibrated accuracy, eligibility or sorting success. No clock is read here.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from raftel_arm01.kinematics.thor_frames import (
    FrameGraph,
    covariance,
    finite,
    matrix,
    multiply,
    transform_point,
    transpose,
)
from raftel_arm01.models import ObjectPose, Position

MAX_OBJECTS = 10_000
MAX_OBSERVATIONS = 100_000
MAX_FILE_BYTES = 8_388_608
UNITS = {"position": "m", "mass": "kg", "timestamp": "s", "position_covariance": "m^2"}
Matrix3 = tuple[tuple[float, ...], ...]


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise ValueError(f"{name} must be nonempty text of at most 512 characters")
    return value


def _fields(value: object, required: set[str], name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError(f"{name} requires exactly {sorted(required)}")


def _sha256(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
    return value


def _canonical_hash(value: object) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError) as error:
        raise ValueError("observation document must be finite JSON data") from error
    return hashlib.sha256(raw.encode()).hexdigest()


def _position(value: object) -> Position:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 3:
        raise ValueError("position_m must contain three finite metre coordinates")
    return Position(*(finite(v) for v in value))


def _point_covariance(value: object) -> Matrix3 | None:
    if value is None:
        return None
    checked = matrix(value, 3, 3)
    # Reuse the existing PSD validator only. A point covariance is NOT an SE(3)
    # pose covariance and is never transformed with its six-dimensional adjoint.
    embedded = tuple(
        tuple(checked[i][j] if i < 3 and j < 3 else 0.0 for j in range(6)) for i in range(6)
    )
    covariance(embedded)
    return checked


def _frame_hash(graph: FrameGraph | None) -> str | None:
    if graph is None:
        return None
    return _canonical_hash(
        [
            {
                "parent": row.parent,
                "child": row.child,
                "parent_from_child": row.parent_from_child,
                "evidence_class": row.evidence_class,
                "evidence": row.evidence,
            }
            for row in graph.records
        ]
    )


@dataclass(frozen=True)
class ObservationDecision:
    """One supplied detection and its explicit offline policy disposition."""

    sequence: int
    observation_id: str
    object_id: str
    timestamp_s: float
    category: str
    mass_kg: float
    source_frame: str
    frame: str
    source_position: Position
    position: Position
    position_covariance_m2: Matrix3 | None
    uncertainty_evidence: str
    rejection_reasons: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return not self.rejection_reasons

    def as_object_pose(self) -> ObjectPose:
        """Create a logical sorter value only after explicit arm_base resolution."""
        if not self.accepted or self.frame != "arm_base":
            raise ValueError("ObjectPose requires an accepted observation in logical arm_base")
        return ObjectPose(self.object_id, self.category, self.position, self.mass_kg)

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "observation_id": self.observation_id,
            "object_id": self.object_id,
            "timestamp_s": self.timestamp_s,
            "category": self.category,
            "mass_kg": self.mass_kg,
            "source_frame": self.source_frame,
            "frame": self.frame,
            "source_position_m": [
                self.source_position.x,
                self.source_position.y,
                self.source_position.z,
            ],
            "position_m": [self.position.x, self.position.y, self.position.z],
            "position_covariance_m2": self.position_covariance_m2,
            "uncertainty_evidence": self.uncertainty_evidence,
            "accepted": self.accepted,
            "rejection_reasons": list(self.rejection_reasons),
        }


@dataclass(frozen=True)
class ObservationReplay:
    run_id: str
    source_kind: str
    provenance: Mapping
    time_domain: str
    as_of_s: float
    max_age_s: float
    require_uncertainty: bool
    presented_ids: tuple[str, ...]
    source_frame: str
    requested_frame: str
    frame_graph_sha256: str | None
    transform_error: str | None
    input_sha256: str
    decisions: tuple[ObservationDecision, ...]

    @property
    def current_decisions(self) -> tuple[ObservationDecision, ...]:
        """Latest sequence wins, even if rejected; never backfill an older pose."""
        latest = {row.object_id: row for row in self.decisions}
        return tuple(
            latest[identifier] for identifier in self.presented_ids if identifier in latest
        )

    def objects(self) -> tuple[ObjectPose, ...]:
        """Return current accepted logical poses, without eligibility/success claims."""
        return tuple(row.as_object_pose() for row in self.current_decisions if row.accepted)

    def to_dict(self) -> dict:
        current = self.current_decisions
        detected = {row.object_id for row in self.decisions}
        return {
            "schema_version": 1,
            "validation_class": "offline_supplied_observation_replay",
            "run_id": self.run_id,
            "source_kind": self.source_kind,
            "provenance": dict(self.provenance),
            "input_canonical_sha256": self.input_sha256,
            "frame_graph_canonical_sha256": self.frame_graph_sha256,
            "time_domain": self.time_domain,
            "as_of_s": self.as_of_s,
            "max_age_s": self.max_age_s,
            "unknown_position_uncertainty_allowed": not self.require_uncertainty,
            "source_frame": self.source_frame,
            "requested_frame": self.requested_frame,
            "transform_error": self.transform_error,
            "counts": {
                "presented": len(self.presented_ids),
                "supplied_detected": len(detected),
                "current_accepted": sum(row.accepted for row in current),
                "current_rejected": sum(not row.accepted for row in current),
                "never_observed": len(self.presented_ids) - len(detected),
                "observation_records": len(self.decisions),
                "rejected_records": sum(not row.accepted for row in self.decisions),
            },
            "presented_ids": list(self.presented_ids),
            "never_observed_ids": [
                identifier for identifier in self.presented_ids if identifier not in detected
            ],
            "current_observation_ids": [row.observation_id for row in current],
            "observations": [row.to_dict() for row in self.decisions],
            "uncertainty_scope": (
                "position observation noise only; extrinsic/clock/model uncertainty excluded"
            ),
            "extrinsic_uncertainty_included": False,
            "physical_calibration_qualified": False,
            "sorting_outcomes_evaluated": False,
            "limitations": [
                "Recorded observations and source hashes are unauthenticated supplied claims.",
                "Known or assumed frame transforms do not establish calibrated accuracy.",
                "Newest rejected data never falls back to an older accepted observation.",
                "Detection, eligibility, attempts and correct sorting are separate denominators.",
            ],
        }


def replay_observations(
    document: Mapping,
    *,
    as_of_s: float,
    time_domain: str,
    max_age_s: float,
    target_frame: str | None = None,
    frame_graph: FrameGraph | None = None,
    require_uncertainty: bool = True,
) -> ObservationReplay:
    """Replay ordered records at an explicit time without reading a live clock.

    Nondecreasing acquisition timestamps and contiguous sequences are required.
    Equal timestamps retain sequence order. Stale/future/unknown-uncertainty rows
    remain explicit rejections; malformed records invalidate the document.
    """
    _fields(
        document,
        {
            "schema_version",
            "run_id",
            "source_kind",
            "provenance",
            "time_domain",
            "units",
            "coordinate_frame",
            "presented_ids",
            "observations",
        },
        "observation document",
    )
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("unsupported observation schema_version")
    if document["units"] != UNITS:
        raise ValueError("observation units must be explicit m, kg, s and m^2")
    kind = document["source_kind"]
    if kind not in ("synthetic", "recorded"):
        raise ValueError("source_kind must be synthetic or recorded")
    provenance = document["provenance"]
    _fields(provenance, {"description", "source_id", "source_sha256"}, "provenance")
    _text(provenance["description"], "provenance.description")
    _text(provenance["source_id"], "provenance.source_id")
    if provenance["source_sha256"] is not None or kind == "recorded":
        _sha256(provenance["source_sha256"])
    domain = _text(document["time_domain"], "time_domain")
    if _text(time_domain, "requested time_domain") != domain:
        raise ValueError("cannot compare timestamps from different clock domains")
    now, age_limit = finite(as_of_s), finite(max_age_s)
    if now < 0 or age_limit < 0:
        raise ValueError("as_of_s and max_age_s must be nonnegative seconds")
    if type(require_uncertainty) is not bool:
        raise ValueError("require_uncertainty must be an explicit boolean")
    if frame_graph is not None and not isinstance(frame_graph, FrameGraph):
        raise ValueError("frame_graph must be an existing FrameGraph")
    known_frames = {"arm_base"} | (set(frame_graph.frames) if frame_graph else set())
    source_frame = _text(document["coordinate_frame"], "coordinate_frame")
    destination = source_frame if target_frame is None else _text(target_frame, "target_frame")
    if source_frame not in known_frames or destination not in known_frames:
        raise ValueError("observation/requested frame is unknown; provide an explicit frame graph")
    transform, transform_error = None, None
    if destination != source_frame:
        try:
            if frame_graph is None:
                raise ValueError("no frame graph supplied for requested conversion")
            transform = frame_graph.transform(destination, source_frame)
        except ValueError as error:
            transform_error = str(error)
    presented = document["presented_ids"]
    if not isinstance(presented, list) or not 1 <= len(presented) <= MAX_OBJECTS:
        raise ValueError(f"presented_ids must contain 1..{MAX_OBJECTS} objects")
    presented_ids = tuple(_text(identifier, "presented object ID") for identifier in presented)
    if len(set(presented_ids)) != len(presented_ids):
        raise ValueError("duplicate presented object ID")
    presented_set = set(presented_ids)
    rows = document["observations"]
    if not isinstance(rows, list) or len(rows) > MAX_OBSERVATIONS:
        raise ValueError("observation record bound exceeded")
    decisions, seen, last_time = [], set(), -1.0
    for sequence, row in enumerate(rows):
        _fields(
            row,
            {
                "sequence",
                "observation_id",
                "object_id",
                "timestamp_s",
                "category",
                "position_m",
                "mass_kg",
                "position_covariance_m2",
                "uncertainty_evidence",
            },
            "observation",
        )
        if type(row["sequence"]) is not int or row["sequence"] != sequence:
            raise ValueError("observation sequences must be contiguous from zero")
        identifier = _text(row["observation_id"], "observation_id")
        if identifier in seen:
            raise ValueError("duplicate observation ID")
        seen.add(identifier)
        object_id = _text(row["object_id"], "object_id")
        if object_id not in presented_set:
            raise ValueError("observation references an undeclared presented object")
        timestamp = finite(row["timestamp_s"])
        if timestamp < 0 or timestamp < last_time:
            raise ValueError("acquisition timestamps must be nonnegative and nondecreasing")
        last_time = timestamp
        category = _text(row["category"], "category")
        mass = finite(row["mass_kg"])
        if mass <= 0:
            raise ValueError("observed mass_kg must be positive")
        source_position = _position(row["position_m"])
        position = source_position
        position_covariance = _point_covariance(row["position_covariance_m2"])
        uncertainty_evidence = _text(row["uncertainty_evidence"], "uncertainty_evidence")
        reasons = []
        if timestamp > now:
            reasons.append("future_timestamp")
        elif now - timestamp > age_limit:
            reasons.append("stale_observation")
        if position_covariance is None and require_uncertainty:
            reasons.append("unknown_position_uncertainty")
        frame = source_frame
        if transform_error is not None:
            reasons.append("missing_or_unknown_transform")
        elif transform is not None:
            position = Position(*transform_point(transform, (position.x, position.y, position.z)))
            frame = destination
            if position_covariance is not None:
                rotation = tuple(tuple(transform[i][j] for j in range(3)) for i in range(3))
                position_covariance = _point_covariance(
                    multiply(multiply(rotation, position_covariance), transpose(rotation))
                )
        decisions.append(
            ObservationDecision(
                sequence,
                identifier,
                object_id,
                timestamp,
                category,
                mass,
                source_frame,
                frame,
                source_position,
                position,
                position_covariance,
                uncertainty_evidence,
                tuple(reasons),
            )
        )
    return ObservationReplay(
        _text(document["run_id"], "run_id"),
        kind,
        dict(provenance),
        domain,
        now,
        age_limit,
        require_uncertainty,
        presented_ids,
        source_frame,
        destination,
        _frame_hash(frame_graph),
        transform_error,
        _canonical_hash(document),
        tuple(decisions),
    )


def read_observation_document(path: str | Path) -> dict:
    """Read bounded UTF-8 JSON with duplicate/nonfinite values rejected."""
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("observation file exceeds byte bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate observation JSON key: {key}")
            result[key] = value
        return result

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite observation JSON number")
        return parsed

    def invalid(value):
        raise ValueError(f"nonfinite observation JSON constant: {value}")

    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_float=number,
            parse_constant=invalid,
        )
    except (RecursionError, UnicodeError) as error:
        raise ValueError("observation JSON is invalid UTF-8 or too deeply nested") from error
    if not isinstance(document, dict):
        raise ValueError("observation JSON root must be an object")
    return document
