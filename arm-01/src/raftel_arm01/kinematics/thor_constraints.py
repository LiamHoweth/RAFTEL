"""Pure provisional/source constraint checks, without hardware authority.

Source bounds describe a pinned URDF, study bounds describe a declared
numerical experiment, and calibrated bounds require separate physical
evidence. Passing a source/study check is not collision clearance or safety.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .thor_frames import NOMINAL_SOURCE_SHA256, _unique_object, finite, validate_nominal_source
from .thor_model import SOURCE_PATH, SOURCE_REVISION, _angles

SOURCE_XACRO_SHA256 = NOMINAL_SOURCE_SHA256


@dataclass(frozen=True)
class JointBounds:
    lower_rad: float
    upper_rad: float
    max_velocity_rad_s: float | None
    max_acceleration_rad_s2: float | None
    evidence: str

    def __post_init__(self) -> None:
        lower, upper = finite(self.lower_rad), finite(self.upper_rad)
        if lower >= upper:
            raise ValueError("joint lower bound must be below upper bound")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("joint bounds require explicit evidence")
        object.__setattr__(self, "lower_rad", lower)
        object.__setattr__(self, "upper_rad", upper)
        for field in ("max_velocity_rad_s", "max_acceleration_rad_s2"):
            value = getattr(self, field)
            if value is not None:
                value = finite(value)
                if value <= 0:
                    raise ValueError("rate bounds must be positive or unknown")
                object.__setattr__(self, field, value)


@dataclass(frozen=True)
class JointConstraint:
    name: str
    source: JointBounds | None
    study: JointBounds | None
    calibrated: JointBounds | None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or self.name not in {f"joint_{i}" for i in range(1, 7)}:
            raise ValueError("unknown nominal Thor joint")
        for family in ("source", "study", "calibrated"):
            value = getattr(self, family)
            if value is not None and not isinstance(value, JointBounds):
                raise ValueError("joint bounds must be JointBounds or null")
        if self.source is not None and self.study is not None:
            if (
                self.study.lower_rad < self.source.lower_rad
                or self.study.upper_rad > self.source.upper_rad
            ):
                raise ValueError("study bounds must be a subset of the declared source bounds")
            for field in ("max_velocity_rad_s", "max_acceleration_rad_s2"):
                source, study = getattr(self.source, field), getattr(self.study, field)
                if source is not None and study is not None and study > source:
                    raise ValueError("study rate bound exceeds its declared source bound")


@dataclass(frozen=True)
class ConstraintSet:
    revision: str
    joints: tuple[JointConstraint, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise ValueError("constraints require an explicit revision")
        if not isinstance(self.joints, Sequence) or len(self.joints) != 6:
            raise ValueError("exactly six ordered joint constraints are required")
        if any(
            not isinstance(item, JointConstraint) or item.name != f"joint_{i}"
            for i, item in enumerate(self.joints, 1)
        ):
            raise ValueError("constraints must be ordered joint_1 through joint_6")
        object.__setattr__(self, "joints", tuple(self.joints))

    def bounds(self, family: str = "study") -> tuple[JointBounds, ...]:
        if not isinstance(family, str) or family not in {"source", "study", "calibrated"}:
            raise ValueError("constraint family must be source, study or calibrated")
        result = tuple(getattr(joint, family) for joint in self.joints)
        missing = [
            joint.name for joint, bound in zip(self.joints, result, strict=True) if bound is None
        ]
        if missing:
            raise ValueError(f"unknown required {family} bounds: {', '.join(missing)}")
        return result


def validate_joint_state(
    joints_rad: Sequence[float],
    constraints: ConstraintSet,
    *,
    family: str = "study",
    velocities_rad_s: Sequence[float] | None = None,
    accelerations_rad_s2: Sequence[float] | None = None,
) -> tuple[str, ...]:
    """Return explicit violations; unknown required limits raise ValueError.

    This checks six independent scalar coordinates only. Coupled shaft, cable,
    collision, load and feedback constraints remain additional unresolved gates.
    """
    angles = _angles(joints_rad)
    if not isinstance(constraints, ConstraintSet):
        raise ValueError("constraints must be a ConstraintSet")
    bounds = constraints.bounds(family)
    violations = []
    for i, (value, bound) in enumerate(zip(angles, bounds, strict=True), 1):
        if not bound.lower_rad <= value <= bound.upper_rad:
            violations.append(f"joint_{i}: position outside {family} bounds")
    for values, field, label in (
        (velocities_rad_s, "max_velocity_rad_s", "velocity"),
        (accelerations_rad_s2, "max_acceleration_rad_s2", "acceleration"),
    ):
        if values is None:
            continue
        rates = _angles(values)
        for i, (value, bound) in enumerate(zip(rates, bounds, strict=True), 1):
            limit = getattr(bound, field)
            if limit is None:
                raise ValueError(f"joint_{i}: required {family} {label} limit is unknown")
            if abs(value) > limit:
                violations.append(f"joint_{i}: {label} outside {family} bounds")
    return tuple(violations)


def load_constraints(path: str | Path) -> ConstraintSet:
    data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if (
        not isinstance(data, Mapping)
        or type(data.get("schema_version")) is not int
        or data.get("schema_version") != 1
        or data.get("units") != "m_rad_s"
    ):
        raise ValueError("constraint manifest requires schema_version 1 and m_rad_s units")
    validate_nominal_source(data.get("source"))
    records = data.get("joints")
    if not isinstance(records, list):
        raise ValueError("constraint manifest requires joint records")
    if any(
        not isinstance(record, Mapping) or set(record) != {"name", "source", "study", "calibrated"}
        for record in records
    ):
        raise ValueError("invalid joint constraint fields")
    try:
        joints = tuple(
            JointConstraint(
                name=record["name"],
                **{
                    family: None if record[family] is None else JointBounds(**record[family])
                    for family in ("source", "study", "calibrated")
                },
            )
            for record in records
        )
        return ConstraintSet(data.get("revision"), joints)
    except (KeyError, TypeError) as error:
        raise ValueError("invalid joint constraint fields") from error


def audit_source_constraints(path: str | Path, constraints: ConstraintSet) -> dict:
    """Check a local pinned source byte-for-byte, then compare its six limits.

    Nothing is downloaded or executed. This supports reproduction from a
    separately obtained immutable source, without vendoring upstream source or
    treating its generic effort field as a running-capacity specification.
    """
    if not isinstance(constraints, ConstraintSet):
        raise ValueError("constraints must be a ConstraintSet")
    contents = Path(path).read_bytes()
    digest = hashlib.sha256(contents).hexdigest()
    if digest != SOURCE_XACRO_SHA256:
        raise ValueError("source xacro SHA256 does not match the pinned model")
    document = ET.fromstring(contents)
    properties = {
        item.get("name"): item.get("value")
        for item in document.findall("{http://www.ros.org/wiki/xacro}property")
    }
    pi = finite(float(properties["PI"]))

    def scalar(text: str) -> float:
        if text == "${PI / 2}":
            return pi / 2
        if text == "-${PI / 2}":
            return -pi / 2
        return finite(float(text))

    source_bounds = constraints.bounds("source")
    results = []
    for i, declared in enumerate(source_bounds, 1):
        joint = document.find(f"joint[@name='joint_{i}']")
        limit = joint.find("limit")
        values = {
            "lower_rad": scalar(limit.get("lower")),
            "upper_rad": scalar(limit.get("upper")),
            "max_velocity_rad_s": scalar(limit.get("velocity")),
        }
        if any(getattr(declared, field) != value for field, value in values.items()):
            raise ValueError(f"declared source bounds differ from pinned joint_{i}")
        if declared.max_acceleration_rad_s2 is not None:
            raise ValueError("source xacro does not establish acceleration limits")
        results.append(
            {
                "joint": f"joint_{i}",
                **values,
                "max_acceleration_rad_s2": None,
                "effort_adopted": False,
            }
        )
    return {
        "validation_class": "pinned_source_limit_audit_not_physical_calibration",
        "source_revision": SOURCE_REVISION,
        "source_path": SOURCE_PATH,
        "source_sha256": digest,
        "constraint_revision": constraints.revision,
        "joints": results,
    }
