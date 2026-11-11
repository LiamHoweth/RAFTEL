"""Synthetic imports exercise mass accounting without inventing physical evidence."""

import copy
import json
import math
from pathlib import Path

import pytest

from raftel_arm01.engineering.fabrication_records import (
    measurement_template,
    validate_fabrication_records,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def manifest():
    return json.loads((ROOT / "hardware/cad/thor-printable-assets-v1.json").read_text())


def provenance():
    return {
        "source": "synthetic fixture; no real print, slicer or measurement",
        "captured_at": "2026-11-11T00:00:00Z",
        "conditions": "deterministic fabricated test values only",
    }


def synthetic_slicer():
    return {
        "evidence_state": "synthetic",
        "provenance": provenance(),
        "slicer_name": "fixture",
        "slicer_version": "1.0",
        "machine_profile_sha256": "1" * 64,
        "material_profile_sha256": "2" * 64,
        "export_sha256": "3" * 64,
        "density_kg_m3": 1240,
        "layer_height_m": 0.0002,
        "nozzle_diameter_m": 0.0004,
        "orientation": "synthetic +Z up",
        "support_strategy": "fixture supports separated from model",
        "model_mass_kg": 0.020,
        "support_mass_kg": 0.003,
        "purge_mass_kg": 0.002,
    }


def synthetic_weighing():
    return {
        "evidence_state": "synthetic",
        "provenance": provenance(),
        "sample_id": "synthetic-part-1",
        "instrument_id": "synthetic-scale",
        "resolution_kg": 0.0001,
        "cleaned_part_mass_kg": 0.021,
        "repeat_count": 3,
        "supports_and_purge_removed": True,
    }


def synthetic_fit():
    return {
        "evidence_state": "synthetic",
        "provenance": provenance(),
        "feature_id": "fixture-bore-X",
        "instrument_id": "synthetic-caliper",
        "nominal_m": 0.006,
        "measured_m": 0.00605,
        "resolution_m": 0.00001,
        "required_min_m": None,
        "required_max_m": None,
        "requirement_source": None,
    }


def sample_import(manifest):
    data = measurement_template(manifest)
    data["records"] = data["records"][:1]
    row = data["records"][0]
    row["slicer"] = synthetic_slicer()
    row["weighing"] = synthetic_weighing()
    row["fit"] = [synthetic_fit()]
    return data


def test_blank_template_has_no_invented_measurements_and_reproduces(manifest):
    template = measurement_template(manifest)
    assert len(template["records"]) == 65
    assert all(
        row["slicer"] is None and row["weighing"] is None and row["fit"] == []
        for row in template["records"]
    )
    tracked = json.loads(
        (ROOT / "hardware/measurements/thor-fabrication-template.json").read_text()
    )
    assert template == tracked
    result = validate_fabrication_records(template, manifest)
    assert result["observed_cleaned_mass_kg"] is None
    assert result["synthetic_cleaned_mass_kg"] is None
    assert not result["manufacturing_release"]


def test_synthetic_mass_support_purge_and_fit_never_become_physical_evidence(manifest):
    result = validate_fabrication_records(sample_import(manifest), manifest)
    assert result["synthetic_cleaned_mass_count"] == 1
    assert result["synthetic_cleaned_mass_kg"] == pytest.approx(0.021)
    assert result["observed_cleaned_mass_kg"] is None
    assert result["observed_slicer_model_mass_kg"] is None
    assert result["observed_slicer_support_purge_mass_kg"] is None
    assert not result["mass_ledger_modified"]
    row = result["records"][0]
    assert row["cleaned_mass_minus_slicer_model_kg"] == pytest.approx(0.001)
    assert row["fit_comparisons"][0]["comparison"] == "requirement_unknown"
    assert row["fit_comparisons"][0]["deviation_from_nominal_m"] == pytest.approx(0.00005)
    assert len(result["unreported_instance_ids"]) == 64


def test_observed_slicer_mass_excludes_support_purge_and_does_not_imply_weighing(manifest):
    data = sample_import(manifest)
    data["records"][0]["slicer"]["evidence_state"] = "observed"
    result = validate_fabrication_records(data, manifest)
    assert result["observed_slicer_model_mass_kg"] == pytest.approx(0.020)
    assert result["observed_slicer_support_purge_mass_kg"] == pytest.approx(0.005)
    assert result["observed_cleaned_mass_kg"] is None
    assert result["records"][0]["cleaned_mass_minus_slicer_model_kg"] is None


@pytest.mark.parametrize(
    "minimum,maximum,expected",
    [
        (0.006, 0.0061, "within_supplied_interval_not_qualification"),
        (0.00605, 0.0061, "boundary_unresolved_at_recorded_resolution"),
        (0.00606, 0.0061, "outside_supplied_interval"),
    ],
)
def test_fit_interval_requires_source_and_considers_instrument_resolution(
    manifest, minimum, maximum, expected
):
    data = sample_import(manifest)
    fit = data["records"][0]["fit"][0]
    fit.update(
        required_min_m=minimum,
        required_max_m=maximum,
        requirement_source="synthetic requirement, no physical acceptance",
    )
    result = validate_fabrication_records(data, manifest)
    comparison = result["records"][0]["fit_comparisons"][0]
    assert comparison["comparison"] == expected
    assert not comparison["retention_or_structural_acceptance"]


@pytest.mark.parametrize(
    "bad",
    [
        "stale_manifest",
        "wrong_units",
        "purchased",
        "duplicate",
        "wrong_variant",
        "wrong_hash",
        "missing_provenance",
        "missing_profile",
        "supports_in_weight",
        "sample_reuse",
        "no_timezone",
        "contradictory_fit",
        "incomplete_fit",
        "physical_permission",
    ],
)
def test_invalid_or_misleading_imports_fail(manifest, bad):
    data = sample_import(manifest)
    row = data["records"][0]
    if bad == "stale_manifest":
        data["manifest_canonical_sha256"] = "0" * 64
    elif bad == "wrong_units":
        data["units"]["mass"] = "g"
    elif bad == "purchased":
        row["instance_id"] = "Assembly::Motor"
    elif bad == "duplicate":
        data["records"].append(copy.deepcopy(row))
    elif bad == "wrong_variant":
        row["variant_id"] = "reflected"
    elif bad == "wrong_hash":
        row["source_sha256"] = "0" * 64
    elif bad == "missing_provenance":
        del row["weighing"]["provenance"]
    elif bad == "missing_profile":
        row["slicer"]["machine_profile_sha256"] = None
    elif bad == "supports_in_weight":
        row["weighing"]["supports_and_purge_removed"] = False
    elif bad == "sample_reuse":
        other = measurement_template(manifest)["records"][1]
        other["weighing"] = copy.deepcopy(row["weighing"])
        data["records"].append(other)
    elif bad == "no_timezone":
        row["fit"][0]["provenance"]["captured_at"] = "2026-11-11T00:00:00"
    elif bad == "contradictory_fit":
        row["fit"][0].update(
            required_min_m=0.0061, required_max_m=0.006, requirement_source="synthetic"
        )
    elif bad == "incomplete_fit":
        row["fit"][0]["required_min_m"] = 0.006
    else:
        data["qualification"]["hardware_operation_authorized"] = True
    with pytest.raises(ValueError):
        validate_fabrication_records(data, manifest)


@pytest.mark.parametrize(
    "section,field",
    [
        ("slicer", "model_mass_kg"),
        ("weighing", "resolution_kg"),
        ("weighing", "cleaned_part_mass_kg"),
    ],
)
@pytest.mark.parametrize("value", [math.nan, math.inf, -1, True, "0.2", 0])
def test_nonfinite_nonpositive_or_wrong_type_mass_values_fail(manifest, section, field, value):
    data = sample_import(manifest)
    data["records"][0][section][field] = value
    with pytest.raises(ValueError):
        validate_fabrication_records(data, manifest)


@pytest.mark.parametrize(
    "bad",
    [
        "bool_schema",
        "bool_manifest_schema",
        "wrong_evidence",
        "wrong_manifest_evidence",
        "bool_count",
        "not_object",
    ],
)
def test_schema_identity_and_evidence_classes_are_not_coerced(manifest, bad):
    data = measurement_template(manifest)
    if bad == "bool_schema":
        data["schema_version"] = True
    elif bad == "bool_manifest_schema":
        manifest["schema_version"] = True
    elif bad == "wrong_evidence":
        data["evidence_class"] = "physical_qualification"
    elif bad == "wrong_manifest_evidence":
        manifest["evidence_class"] = "manufacturing_release"
    elif bad == "bool_count":
        manifest["counts"]["installed_printed_leaves"] = True
    else:
        data = []
    with pytest.raises(ValueError):
        validate_fabrication_records(data, manifest)


def test_aggregate_mass_overflow_is_a_rejected_import(manifest):
    data = measurement_template(manifest)
    data["records"] = data["records"][:2]
    for index, record in enumerate(data["records"]):
        record["weighing"] = synthetic_weighing()
        record["weighing"]["sample_id"] = f"synthetic-extreme-{index}"
        record["weighing"]["cleaned_part_mass_kg"] = 1e308
    with pytest.raises(ValueError, match="overflow"):
        validate_fabrication_records(data, manifest)


@pytest.mark.parametrize("bad", ["assets", "instances", "instance", "counts", "qualification"])
def test_malformed_nested_containers_are_rejected(manifest, bad):
    data = measurement_template(manifest)
    if bad == "assets":
        manifest["assets"] = None
    elif bad == "instances":
        manifest["assets"][0]["instances"] = True
    elif bad == "instance":
        manifest["assets"][0]["instances"][0] = 42
    elif bad == "counts":
        manifest["counts"] = []
    else:
        data["qualification"] = True
    with pytest.raises(ValueError):
        validate_fabrication_records(data, manifest)
