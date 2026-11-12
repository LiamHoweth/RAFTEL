"""Allowlisted saved-project software observations; never physical confirmation.

Only Metadata/project_settings.config is read. The archive reader is shared with
the structural audit. Unknown keys (including credentials and custom G-code) are
neither copied nor named in the result. No config directory is searched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import zipfile
import zlib
from pathlib import Path
from typing import Protocol

MEMBER = "Metadata/project_settings.config"
MAX_SETTINGS_BYTES = 2 * 1024 * 1024
MAX_FIELDS = 4096
MAX_VECTOR = 16
MAX_DEPTH = 32
SCHEMA = "raftel.anycubic_process_observation.v1"


class Archive(Protocol):
    names: tuple[str, ...]
    sha256: str
    size: int

    def read(self, name: str, *, max_bytes: int) -> bytes: ...


# Same field names and units as the existing local-profile-audit.json contract.
GROUPS = {
    "machine": {
        "printer_model",
        "printer_variant",
        "nozzle_diameter",
        "printable_height",
        "printable_area",
        "bed_exclude_area",
    },
    "process": {
        "layer_height",
        "initial_layer_print_height",
        "wall_loops",
        "sparse_infill_density",
        "sparse_infill_pattern",
        "enable_support",
        "support_type",
        "brim_type",
        "brim_width",
    },
    "filament": {
        "filament_type",
        "filament_vendor",
        "filament_density",
        "filament_diameter",
        "filament_max_volumetric_speed",
        "nozzle_temperature",
        "nozzle_temperature_initial_layer",
        "hot_plate_temp",
        "hot_plate_temp_initial_layer",
        "textured_plate_temp",
        "textured_plate_temp_initial_layer",
    },
}
SELECTORS = {"printer_settings_id", "print_settings_id", "filament_settings_id", "curr_bed_type"}
NUMBERS = {
    "nozzle_diameter": (0.05, 5, "mm"),
    "printable_height": (1, 5000, "mm"),
    "layer_height": (0.001, 5, "mm"),
    "initial_layer_print_height": (0.001, 5, "mm"),
    "wall_loops": (0, 100, "count"),
    "brim_width": (0, 500, "mm"),
    "filament_density": (0.01, 30, "g/cm^3"),
    "filament_diameter": (0.1, 10, "mm"),
    "filament_max_volumetric_speed": (0, 1000, "mm^3/s"),
    **{
        key: (0, 500, "degC")
        for key in (
            "nozzle_temperature",
            "nozzle_temperature_initial_layer",
            "hot_plate_temp",
            "hot_plate_temp_initial_layer",
            "textured_plate_temp",
            "textured_plate_temp_initial_layer",
        )
    },
}
ALLOWED = SELECTORS | set().union(*GROUPS.values())
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")
MACHINE = "Anycubic Kobra 3 Max 0.4 nozzle"
TEXT_VALUES = {
    "printer_settings_id": {MACHINE},
    "print_settings_id": {f"0.20mm Standard @{MACHINE}"},
    "filament_settings_id": {
        f"Anycubic {material} @{MACHINE}" for material in ("PLA", "PETG", "ABS")
    },
    "printer_model": {"Anycubic Kobra 3 Max"},
    "printer_variant": {"0.4"},
    # Code meaning is deliberately not inferred from this saved numeric code.
    "curr_bed_type": {str(index) for index in range(16)},
    "filament_type": {"PLA", "PETG", "ABS", "ASA", "TPU", "PC", "PA", "PVA", "HIPS"},
    "filament_vendor": {"Anycubic", "Generic"},
    "sparse_infill_pattern": {
        "3dhoneycomb",
        "honeycomb",
        "grid",
        "gyroid",
        "rectilinear",
        "cubic",
        "adaptivecubic",
        "alignedrectilinear",
        "lightning",
        "crosshatch",
    },
    "support_type": {"tree(auto)", "tree(manual)", "normal(auto)", "normal(manual)"},
    "brim_type": {"auto_brim", "no_brim", "outer_only", "inner_only", "outer_and_inner"},
}


def _text(value: object) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 256
        or any(not char.isprintable() for char in value)
    ):
        raise ValueError("invalid allowlisted text field")
    return value


def _number(value: object, low: float, high: float) -> float:
    if isinstance(value, str):
        if len(value) > 32 or not NUMBER.fullmatch(value):
            raise ValueError("invalid allowlisted numeric field")
    elif type(value) not in (int, float):
        raise ValueError("invalid allowlisted numeric field")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid allowlisted numeric field") from exc
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError("allowlisted numeric field out of bounds")
    return result


def _values(value: object) -> list:
    if isinstance(value, list):
        if not 1 <= len(value) <= MAX_VECTOR:
            raise ValueError("invalid allowlisted vector length")
        return value
    return [value]


def _validate(key: str, value: object) -> None:
    if key in ("printable_area", "bed_exclude_area"):
        if not isinstance(value, list) or not 1 <= len(value) <= 256:
            raise ValueError("invalid allowlisted point vector")
        for item in value:
            if not isinstance(item, str) or len(item) > 65 or len(item.split("x")) != 2:
                raise ValueError("invalid allowlisted point")
            for coordinate in item.split("x"):
                _number(coordinate, -5000, 5000)
        return
    values = _values(value)
    if key in ("printer_settings_id", "print_settings_id", "curr_bed_type") and isinstance(
        value, list
    ):
        raise ValueError("invalid allowlisted selector shape")
    for item in values:
        if key in NUMBERS:
            low, high, _unit = NUMBERS[key]
            number = _number(item, low, high)
            if key == "wall_loops" and not number.is_integer():
                raise ValueError("wall count must be integral")
        elif key == "sparse_infill_density":
            if not isinstance(item, str) or not item.endswith("%"):
                raise ValueError("infill must have explicit percent units")
            _number(item[:-1], 0, 100)
        elif key == "enable_support":
            if type(item) not in (str, int, bool) or item not in ("0", "1", 0, 1):
                raise ValueError("invalid support flag")
        else:
            _text(item)


def _settings(data: bytes) -> dict:
    if len(data) > MAX_SETTINGS_BYTES:
        raise ValueError("saved settings exceed size bound")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("saved settings must be UTF-8 JSON") from exc
    # Bound nesting before json.loads, including ignored private values.
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError("saved settings exceed nesting bound")
        elif char in "]}":
            depth -= 1

    def pairs(items: list[tuple[str, object]]) -> dict:
        result = {}
        if len(items) > MAX_FIELDS:
            raise ValueError("saved settings exceed field bound")
        for key, value in items:
            if key in result:
                raise ValueError("duplicate saved settings field")
            result[key] = value
        return result

    def invalid_constant(_value: str) -> None:
        raise ValueError("nonfinite saved settings constant")

    def json_float(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite saved settings number")
        return result

    try:
        result = json.loads(
            text, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=json_float
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid saved settings JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("saved settings must be an object")
    return result


def observe_project_profiles(archive: Archive) -> dict:
    """Observe only saved values; absent evidence remains explicitly unknown."""
    present = MEMBER in archive.names
    data = archive.read(MEMBER, max_bytes=MAX_SETTINGS_BYTES) if present else None
    settings = {} if data is None else _settings(data)
    for key in sorted(settings.keys() & ALLOWED):
        _validate(key, settings[key])
    # A key allowlist alone cannot protect private text stored in custom profile
    # names. Unknown catalog text is withheld, while its source bytes stay bound.
    unknown_values = sorted(
        key
        for key, accepted in TEXT_VALUES.items()
        if key in settings and any(value not in accepted for value in _values(settings[key]))
    )
    observed = {key: value for key, value in settings.items() if key not in unknown_values}
    profile_fields = {
        output: observed[source]
        for output, source in (
            ("machine", "printer_settings_id"),
            ("process", "print_settings_id"),
            ("curr_bed_type", "curr_bed_type"),
        )
        if source in observed
    }
    canonical = json.dumps(
        profile_fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return {
        "schema": SCHEMA,
        "validation_class": "saved_project_software_metadata_not_physical_confirmation",
        "project_sha256": archive.sha256,
        "project_size_bytes": archive.size,
        "settings_member": MEMBER if present else None,
        "settings_member_sha256": None if data is None else hashlib.sha256(data).hexdigest(),
        "settings_status": "observed" if present else "unknown_absent_member",
        "unknown_field_count": len(settings.keys() - ALLOWED),
        "unknown_value_fields": unknown_values,
        "missing_allowlisted_fields": sorted(ALLOWED - settings.keys()),
        "saved_selection": {
            "source": MEMBER if present else None,
            "profile_fields": profile_fields,
            "project_filament_entries": (
                [
                    {"project_array_index": index, "profile_id": value}
                    for index, value in enumerate(_values(observed["filament_settings_id"]))
                ]
                if "filament_settings_id" in observed
                else None
            ),
            "project_filament_shape": (
                "array"
                if isinstance(observed.get("filament_settings_id"), list)
                else "scalar"
                if "filament_settings_id" in observed
                else "unknown"
            ),
            "profile_fields_canonical_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "is_live_gui_state": False,
            "is_physical_hardware_confirmation": False,
            "full_private_config_or_account_ids_copied": False,
        },
        "profiles": {
            group: {
                "resolved_allowlisted_fields": {
                    key: observed[key] for key in sorted(keys & observed.keys())
                },
                "inheritance_resolution_performed": False,
            }
            for group, keys in GROUPS.items()
        },
        "source_units": {
            **{key: unit for key, (_low, _high, unit) in NUMBERS.items() if key in settings},
            **({"sparse_infill_density": "percent"} if "sparse_infill_density" in settings else {}),
            **{key: "mm" for key in ("printable_area", "bed_exclude_area") if key in settings},
        },
        "physical_confirmation": dict.fromkeys(
            (
                "printer_revision",
                "installed_nozzle_mm",
                "loaded_filament_brand_product",
                "loaded_filament_material",
                "actual_bed_surface",
                "calibrated_flow_or_dimensional_fit",
            )
        ),
        "limitations": [
            "Saved project values do not establish current GUI selectors or physical hardware.",
            "Unknown keys and custom G-code are omitted; warnings and slicing are not inspected.",
            "Unrecognized catalog text is withheld, including custom profile names.",
            "Saved fields do not establish resolved inheritance or print qualification.",
            "Profile dimensions do not override nominal physical printer dimensions.",
            "Project filament indices are not mapped to application saved-config slot aliases.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    # Deferred import keeps the protocol usable in independent host-only tests.
    from audit_anycubic_draft_project import ProjectArchive

    try:
        with ProjectArchive(args.project) as archive:
            result = observe_project_profiles(archive)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
        # Do not include paths or untrusted JSON content in error output.
        parser.exit(2, f"process observation failed ({type(exc).__name__})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
