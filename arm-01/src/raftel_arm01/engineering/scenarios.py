"""Versioned, hash-bound inputs for reproducible conditional Thor studies.

A scenario is an analytical declaration, never a commissioned configuration.
Native captures, ideal jaw overlays and physical evidence remain separate.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from numbers import Real
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
EVIDENCE_CLASS = "conditional_analytical_model"
COORDINATE_FRAME = "thor_ros_nominal_base_link_m"
UNITS = {
    "position": "m",
    "mass": "kg",
    "angle": "rad",
    "gravity": "m/s^2",
    "torque": "N*m",
}
INPUT_EVIDENCE_CLASSES = {
    "saved_native_cad_capture",
    "source_audit",
    "conditional_model",
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REVISION = re.compile(r"[0-9a-f]{40}\Z")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def _strict_json(value: str | bytes) -> Any:
    return json.loads(value, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("expected finite real number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("expected finite real number") from error
    if not math.isfinite(number):
        raise ValueError("expected finite real number")
    return number


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} requires nonempty text")
    return value


def _object(value: Any, keys: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{name} requires exactly {sorted(keys)}")
    return value


def _vector(value: Any, length: int, name: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f"{name} requires {length} finite values")
    return [finite_number(item) for item in value]


def _relative_path(value: Any) -> str:
    raw = _text(value, "input path")
    path = PurePosixPath(raw)
    if (
        "\\" in raw
        or ":" in raw
        or path.is_absolute()
        or ".." in path.parts
        or raw != path.as_posix()
        or not path.parts
    ):
        raise ValueError("input path must be normalized project-relative POSIX path")
    return raw


def canonical_sha256(data: Any) -> str:
    """Hash JSON content independently of indentation; reject NaN/Infinity."""
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def validate_scenario_manifest(data: Any) -> dict:
    """Return a defensive normalized copy, rejecting ambiguous/missing inputs.

    The explicit belt overrides must also match the bound membership when the
    study is run. This validator performs no file I/O or physical inference.
    """
    top_keys = {
        "schema_version",
        "scenario_id",
        "evidence_class",
        "coordinate_frame",
        "units",
        "source_revisions",
        "inputs",
        "material",
        "belt_mass_overrides",
        "wrist_motion_scenario",
        "gravity_m_s2",
        "cases",
        "unresolved_gates",
    }
    result = copy.deepcopy(_object(data, top_keys, "scenario manifest"))
    if type(result["schema_version"]) is not int or result["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported scenario schema_version")
    _text(result["scenario_id"], "scenario_id")
    if result["evidence_class"] != EVIDENCE_CLASS:
        raise ValueError("scenario evidence_class must remain conditional_analytical_model")
    if result["coordinate_frame"] != COORDINATE_FRAME or result["units"] != UNITS:
        raise ValueError("scenario requires the declared nominal frame and SI units")
    revisions = _object(result["source_revisions"], {"thor_cad", "thor_ros"}, "source revisions")
    if any(
        not isinstance(value, str) or not _REVISION.fullmatch(value) for value in revisions.values()
    ):
        raise ValueError("source revisions must be immutable 40-character Git SHAs")
    inputs = result["inputs"]
    if not isinstance(inputs, dict) or not {"inventory", "membership", "moving_mass"} <= set(
        inputs
    ):
        raise ValueError("scenario requires bound inventory, membership and moving_mass inputs")
    paths = []
    for role, binding in inputs.items():
        _text(role, "input role")
        _object(binding, {"path", "sha256", "evidence_class"}, f"input {role}")
        paths.append(_relative_path(binding["path"]))
        if not isinstance(binding["sha256"], str) or not _SHA256.fullmatch(binding["sha256"]):
            raise ValueError("input SHA256 must be lowercase 64-character hex")
        if (
            not isinstance(binding["evidence_class"], str)
            or binding["evidence_class"] not in INPUT_EVIDENCE_CLASSES
        ):
            raise ValueError("input evidence class is not a supported source/model class")
    if len(paths) != len(set(paths)):
        raise ValueError("input roles must bind distinct files")
    material = _object(
        result["material"],
        {"family", "density_kg_m3", "density_evidence", "effective_whole_part_solid_fraction"},
        "material",
    )
    if not isinstance(material["family"], str) or material["family"] not in {"PLA", "PETG", "ABS"}:
        raise ValueError("material family must be PLA, PETG or ABS")
    material["density_kg_m3"] = finite_number(material["density_kg_m3"])
    material["effective_whole_part_solid_fraction"] = finite_number(
        material["effective_whole_part_solid_fraction"]
    )
    if (
        material["density_kg_m3"] <= 0
        or not 0 < material["effective_whole_part_solid_fraction"] <= 1
    ):
        raise ValueError("material requires positive density and whole-part fraction in (0,1]")
    _text(material["density_evidence"], "density evidence")
    overrides = result["belt_mass_overrides"]
    if not isinstance(overrides, dict) or not overrides:
        raise ValueError("explicit per-instance belt masses are required")
    for path, override in overrides.items():
        _text(path, "belt instance path")
        _object(override, {"mass_kg", "evidence"}, "belt mass override")
        override["mass_kg"] = finite_number(override["mass_kg"])
        if override["mass_kg"] <= 0:
            raise ValueError("belt mass must be positive")
        _text(override["evidence"], "belt mass evidence")
    _text(result["wrist_motion_scenario"], "wrist motion scenario")
    result["gravity_m_s2"] = _vector(result["gravity_m_s2"], 3, "gravity")
    # Reuse the existing load engine's exact declared gravity; arbitrary gravity
    # is deliberately rejected instead of silently ignored by that engine.
    if result["gravity_m_s2"] != [0.0, 0.0, -9.80665]:
        raise ValueError("v1 scenarios require existing gravity [0,0,-9.80665] m/s^2")
    cases = result["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 256:
        raise ValueError("scenario requires 1..256 explicit cases")
    names = []
    for case in cases:
        _object(case, {"name", "joint_angles_rad", "jaw", "payload"}, "case")
        names.append(_text(case["name"], "case name"))
        case["joint_angles_rad"] = _vector(case["joint_angles_rad"], 6, "joint angles")
        jaw = _object(case["jaw"], {"configuration", "closing_angle_rad", "evidence"}, "jaw")
        _text(jaw["evidence"], "jaw evidence")
        if jaw["configuration"] == "saved_frozen":
            if jaw["closing_angle_rad"] is not None:
                raise ValueError("saved_frozen jaw has no common solved closing coordinate")
        elif jaw["configuration"] == "ideal_body_overlay":
            q = finite_number(jaw["closing_angle_rad"])
            if not 0 <= q < math.pi / 2:
                raise ValueError("ideal jaw coordinate must lie in analytical [0,pi/2) interval")
            jaw["closing_angle_rad"] = q
            if "jaw_bodies" not in inputs:
                raise ValueError("ideal jaw overlay requires a hash-bound jaw_bodies input")
        else:
            raise ValueError("jaw configuration must distinguish saved_frozen/ideal_body_overlay")
        payload = _object(case["payload"], {"mass_kg", "point_zero_m", "com_evidence"}, "payload")
        payload["mass_kg"] = finite_number(payload["mass_kg"])
        if payload["mass_kg"] < 0:
            raise ValueError("payload mass must be nonnegative")
        payload["point_zero_m"] = _vector(payload["point_zero_m"], 3, "payload point")
        _text(payload["com_evidence"], "payload COM evidence")
    if len(names) != len(set(names)):
        raise ValueError("case names must be unique")
    gates = result["unresolved_gates"]
    if not isinstance(gates, list) or not gates:
        raise ValueError("conditional scenario must retain unresolved gates")
    for gate in gates:
        _text(gate, "unresolved gate")
    return result


def load_scenario_manifest(path: Path | str) -> dict:
    return validate_scenario_manifest(_strict_json(Path(path).read_text(encoding="utf-8")))


def verify_scenario_inputs(manifest: dict, project_root: Path | str) -> dict[str, dict]:
    """Read exact bound JSON files, rejecting stale files and path escapes.

    File hashes cover bytes, while generated reports additionally record a
    canonical manifest hash. This distinction is intentional and explicit.
    """
    scenario = validate_scenario_manifest(manifest)
    root = Path(project_root).resolve(strict=True)
    inputs = {}
    for role, binding in scenario["inputs"].items():
        path = (root / binding["path"]).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"bound input {role} escapes project root or is not a file")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
            raise ValueError(f"stale input hash for {role}: {binding['path']}")
        try:
            data = _strict_json(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"bound input {role} is not valid JSON") from error
        if not isinstance(data, dict):
            raise ValueError(f"bound input {role} must be a JSON object")
        inputs[role] = data
    return inputs
