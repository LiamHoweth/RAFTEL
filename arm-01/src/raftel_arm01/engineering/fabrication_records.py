"""Offline slicer, cleaned-mass and fit records bound to printed CAD instances.

No record commissions a robot or releases a part. Blank values stay unknown;
synthetic fixtures remain separate from observations, and support/purge material
never silently becomes installed arm mass.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from typing import Any

_STATES = {"unknown", "synthetic", "observed"}


def _canonical_hash(data: dict) -> str:
    try:
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise ValueError("manifest must be finite JSON data") from error
    return hashlib.sha256(encoded).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{field} must be a finite number") from error
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        raise ValueError(f"{field} must be {'positive' if positive else 'nonnegative'} and finite")
    return result


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256")
    return value


def _total(values: list[float]) -> float | None:
    if not values:
        return None
    try:
        return _number(math.fsum(values), "aggregate mass")
    except OverflowError as error:
        raise ValueError("aggregate mass overflowed") from error


def _instances(manifest: dict) -> dict[str, tuple[dict, dict]]:
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int:
        raise ValueError("unsupported printable manifest schema")
    if manifest["schema_version"] != 1:
        raise ValueError("unsupported printable manifest schema")
    if manifest.get("evidence_class") != (
        "source_capture_reconciliation_not_export_or_manufacturing_release"
    ):
        raise ValueError("unexpected printable manifest evidence class")
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        raise ValueError("manifest assets must be a list")
    result = {}
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("instances"), list):
            raise ValueError("asset must supply an instance list")
        _text(asset.get("asset_id"), "asset_id")
        _sha256(asset.get("source_sha256"), "source_sha256")
        for instance in asset.get("instances", []):
            if not isinstance(instance, dict):
                raise ValueError("printable instance must be an object")
            identifier = _text(instance.get("instance_id"), "instance_id")
            if identifier in result:
                raise ValueError("duplicate printable instance in manifest")
            if instance.get("variant_id") not in {"nominal", "reflected"}:
                raise ValueError("unknown geometry variant")
            result[identifier] = (asset, instance)
    if not isinstance(manifest.get("counts"), dict):
        raise ValueError("manifest counts must be an object")
    count = manifest["counts"].get("installed_printed_leaves")
    if not result or type(count) is not int or count != len(result):
        raise ValueError("printable instance count inconsistent with manifest")
    return result


def measurement_template(manifest: dict) -> dict:
    """One blank record per installed print, preventing accidental quantity multiplication."""
    instances = _instances(manifest)
    return {
        "schema_version": 1,
        "evidence_class": "fabrication_observation_records_not_part_or_robot_qualification",
        "manifest_canonical_sha256": _canonical_hash(manifest),
        "units": {"mass": "kg", "length": "m", "density": "kg/m^3"},
        "records": [
            {
                "instance_id": identifier,
                "asset_id": asset["asset_id"],
                "variant_id": instance["variant_id"],
                "source_sha256": asset["source_sha256"],
                "slicer": None,
                "weighing": None,
                "fit": [],
            }
            for identifier, (asset, instance) in sorted(instances.items())
        ],
        "qualification": {
            "mass_or_fit_accepted_for_design": False,
            "manufacturing_release": False,
            "hardware_operation_authorized": False,
        },
    }


def _provenance(record: dict, section: str) -> str:
    state = record.get("evidence_state")
    if state not in _STATES - {"unknown"}:
        raise ValueError(f"{section} evidence_state must be synthetic or observed")
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError(f"{section} provenance required")
    _text(provenance.get("source"), f"{section} provenance source")
    stamp = _text(provenance.get("captured_at"), f"{section} captured_at")
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{section} captured_at must be ISO-8601 with timezone") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{section} captured_at must include timezone")
    conditions = provenance.get("conditions")
    _text(conditions, f"{section} conditions")
    return state


def validate_fabrication_records(data: dict, manifest: dict) -> dict:
    """Validate a partial or complete import without changing any mass ledger.

    Slicer estimates, cleaned observed masses and synthetic fixtures have
    separate totals. A fit status is only a comparison with a supplied sourced
    interval; it is never structural/material/retention acceptance.
    """
    instances = _instances(manifest)
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int:
        raise ValueError("unsupported fabrication records schema")
    if data["schema_version"] != 1:
        raise ValueError("unsupported fabrication records schema")
    if data.get("evidence_class") != (
        "fabrication_observation_records_not_part_or_robot_qualification"
    ):
        raise ValueError("unexpected fabrication evidence class")
    if data.get("manifest_canonical_sha256") != _canonical_hash(manifest):
        raise ValueError("stale or wrong printable manifest")
    if data.get("units") != {"mass": "kg", "length": "m", "density": "kg/m^3"}:
        raise ValueError("fabrication units must be explicit SI units")
    qualification = data.get("qualification", {})
    if not isinstance(qualification, dict):
        raise ValueError("qualification restrictions must be an object")
    if any(
        qualification.get(key) is not False
        for key in (
            "mass_or_fit_accepted_for_design",
            "manufacturing_release",
            "hardware_operation_authorized",
        )
    ):
        raise ValueError("observation records cannot grant qualification or operation")
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    seen, weighed_samples = set(), set()
    summary = []
    observed_mass, synthetic_mass, slicer_model_mass, slicer_waste_mass = [], [], [], []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each fabrication record must be an object")
        identifier = record.get("instance_id")
        if identifier not in instances:
            raise ValueError("record references unknown or purchased instance")
        if identifier in seen:
            raise ValueError("duplicate installed instance observation")
        seen.add(identifier)
        asset, instance = instances[identifier]
        if any(
            record.get(key) != expected
            for key, expected in (
                ("asset_id", asset["asset_id"]),
                ("variant_id", instance["variant_id"]),
                ("source_sha256", asset["source_sha256"]),
            )
        ):
            raise ValueError("record asset, variant or source hash differs from manifest")
        outcome = {
            "instance_id": identifier,
            "slicer_state": "unknown",
            "weighing_state": "unknown",
            "cleaned_mass_minus_slicer_model_kg": None,
            "fit_comparisons": [],
        }
        sliced = record.get("slicer")
        if sliced is not None:
            if not isinstance(sliced, dict):
                raise ValueError("slicer observation must be an object or null")
            state = _provenance(sliced, "slicer")
            _text(sliced.get("slicer_name"), "slicer_name")
            _text(sliced.get("slicer_version"), "slicer_version")
            for field in ("machine_profile_sha256", "material_profile_sha256", "export_sha256"):
                _sha256(sliced.get(field), field)
            _number(sliced.get("density_kg_m3"), "density_kg_m3", positive=True)
            _number(sliced.get("layer_height_m"), "layer_height_m", positive=True)
            _number(sliced.get("nozzle_diameter_m"), "nozzle_diameter_m", positive=True)
            _text(sliced.get("orientation"), "orientation")
            _text(sliced.get("support_strategy"), "support_strategy")
            model = _number(sliced.get("model_mass_kg"), "model_mass_kg", positive=True)
            support = _number(sliced.get("support_mass_kg"), "support_mass_kg")
            purge = _number(sliced.get("purge_mass_kg"), "purge_mass_kg")
            # Only actual slicer outputs are counted as estimates; synthetic
            # imports exercise validation without creating real estimates.
            if state == "observed":
                slicer_model_mass.append(model)
                slicer_waste_mass.append(_number(support + purge, "support plus purge mass"))
            outcome["slicer_state"] = state
        weighed = record.get("weighing")
        if weighed is not None:
            if not isinstance(weighed, dict):
                raise ValueError("weighing must be an object or null")
            state = _provenance(weighed, "weighing")
            sample = _text(weighed.get("sample_id"), "sample_id")
            if sample in weighed_samples:
                raise ValueError("one physical/synthetic sample cannot cover multiple instances")
            weighed_samples.add(sample)
            _text(weighed.get("instrument_id"), "weighing instrument_id")
            resolution = _number(weighed.get("resolution_kg"), "resolution_kg", positive=True)
            mass = _number(
                weighed.get("cleaned_part_mass_kg"), "cleaned_part_mass_kg", positive=True
            )
            if resolution > mass:
                raise ValueError("scale resolution coarser than part mass")
            repeats = weighed.get("repeat_count")
            if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
                raise ValueError("repeat_count must be a positive integer")
            if weighed.get("supports_and_purge_removed") is not True:
                raise ValueError("installed mass requires cleaned part without support/purge")
            (observed_mass if state == "observed" else synthetic_mass).append(mass)
            outcome["weighing_state"] = state
            if sliced is not None and state == outcome["slicer_state"]:
                outcome["cleaned_mass_minus_slicer_model_kg"] = mass - sliced["model_mass_kg"]
        fits = record.get("fit")
        if not isinstance(fits, list):
            raise ValueError("fit must be a list; empty means unknown")
        features = set()
        for fit in fits:
            if not isinstance(fit, dict):
                raise ValueError("fit observation must be an object")
            state = _provenance(fit, "fit")
            feature = _text(fit.get("feature_id"), "feature_id")
            if feature in features:
                raise ValueError("duplicate fit feature; use distinct measurement locations")
            features.add(feature)
            _text(fit.get("instrument_id"), "fit instrument_id")
            nominal = _number(fit.get("nominal_m"), "nominal_m", positive=True)
            measured = _number(fit.get("measured_m"), "measured_m", positive=True)
            resolution = _number(fit.get("resolution_m"), "resolution_m", positive=True)
            if resolution > measured:
                raise ValueError("fit resolution coarser than measured feature")
            minimum, maximum = fit.get("required_min_m"), fit.get("required_max_m")
            requirement = fit.get("requirement_source")
            status = "requirement_unknown"
            if any(value is not None for value in (minimum, maximum, requirement)):
                minimum = _number(minimum, "required_min_m")
                maximum = _number(maximum, "required_max_m", positive=True)
                _text(requirement, "requirement_source")
                if minimum > maximum:
                    raise ValueError("contradictory fit requirement interval")
                # A nominal interval comparison cannot resolve a boundary when
                # the recorded resolution extends outside the interval.
                if measured < minimum or measured > maximum:
                    status = "outside_supplied_interval"
                elif measured - resolution / 2 < minimum or measured + resolution / 2 > maximum:
                    status = "boundary_unresolved_at_recorded_resolution"
                else:
                    status = "within_supplied_interval_not_qualification"
            outcome["fit_comparisons"].append(
                {
                    "feature_id": feature,
                    "evidence_state": state,
                    "deviation_from_nominal_m": measured - nominal,
                    "comparison": status,
                    "retention_or_structural_acceptance": False,
                }
            )
        summary.append(outcome)
    return {
        "schema_version": 1,
        "evidence_class": "validated_offline_import_not_qualification",
        "records_present": len(records),
        "installed_printed_count": len(instances),
        "unreported_instance_ids": sorted(set(instances) - seen),
        "observed_cleaned_mass_count": len(observed_mass),
        "observed_cleaned_mass_kg": _total(observed_mass),
        "synthetic_cleaned_mass_count": len(synthetic_mass),
        "synthetic_cleaned_mass_kg": _total(synthetic_mass),
        "observed_slicer_model_mass_kg": _total(slicer_model_mass),
        "observed_slicer_support_purge_mass_kg": _total(slicer_waste_mass),
        "mass_ledger_modified": False,
        "physical_part_qualification": False,
        "manufacturing_release": False,
        "records": summary,
    }
