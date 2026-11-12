"""Fabricated observations exercise metadata; no physical measurement occurs."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from raftel_arm01.engineering.fabrication_records import measurement_template
from raftel_arm01.engineering.scenarios import canonical_sha256

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "readiness", ROOT / "tools/thor_measurement_readiness.py"
)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
AS_OF = "2026-11-11T13:00:00Z"


def fixture(tmp_path, state="observed"):
    manifest = json.loads(
        (ROOT / "hardware/cad/thor-printable-assets-v1.json").read_text(encoding="utf-8")
    )
    fabrication = measurement_template(manifest)
    fabrication["records"] = fabrication["records"][:1]
    fabrication["records"][0]["weighing"] = {
        "evidence_state": state,
        "provenance": {
            "source": "fabricated test observation only",
            "captured_at": "2026-11-11T12:00:00Z",
            "conditions": "fabricated bench conditions; no physical measurement",
        },
        "sample_id": "fixture-sample",
        "instrument_id": "fixture-scale",
        "resolution_kg": 0.0001,
        "cleaned_part_mass_kg": 0.020,
        "repeat_count": 3,
        "supports_and_purge_removed": True,
    }

    def reference(name):
        raw = ("Synthetic fixture evidence only: " + name).encode()
        (tmp_path / name).write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    sidecar = tool.template(fabrication, manifest)
    sidecar["instruments"][0]["calibration"] = {
        "evidence_state": state,
        "calibrated_at_utc": "2026-11-10T00:00:00Z",
        "valid_until_utc": "2026-11-12T00:00:00Z",
        "applicable_conditions": "fabricated indoor bench declaration",
        "evidence": reference("calibration.txt"),
        "invalidation": None,
    }
    sidecar["records"][0]["uncertainty"] = {
        "standard_uncertainty_kg": 0.0002,
        "coverage_factor": 2.0,
        "expanded_uncertainty_kg": 0.0004,
        "budget_description": "fabricated instrument/resolution/repeatability budget",
        "resolution_accounted_for": True,
        "repeatability_accounted_for": True,
        "calibration_accounted_for": True,
        "uncertainty_evidence": reference("budget.txt"),
        "conditions_applicability_evidence": reference("conditions.txt"),
    }
    return manifest, fabrication, sidecar


def assess(tmp_path, manifest, fabrication, sidecar, *, as_of=AS_OF):
    return tool.assess(sidecar, fabrication, manifest, evidence_root=tmp_path, as_of_utc=as_of)


def test_existing_blank_form_gets_only_blank_metadata_and_reproduces_template(tmp_path):
    manifest = json.loads(
        (ROOT / "hardware/cad/thor-printable-assets-v1.json").read_text(encoding="utf-8")
    )
    fabrication = measurement_template(manifest)
    sidecar = tool.template(fabrication, manifest)
    assert sidecar["instruments"] == []
    assert len(sidecar["records"]) == 65
    assert all(
        row["uncertainty"] is row["weighing_canonical_sha256"] is None for row in sidecar["records"]
    )
    result = assess(tmp_path, manifest, fabrication, sidecar)
    assert result["ready_observed_record_count"] == result["complete_synthetic_fixture_count"] == 0
    assert all(row["blocking_reasons"] == ["weighing_unknown"] for row in result["records"])
    tracked = json.loads(
        (ROOT / "hardware/measurements/thor-measurement-readiness-template.json").read_text(
            encoding="utf-8"
        )
    )
    assert sidecar == tracked


def test_complete_declarations_are_reviewable_without_authenticating_measurement(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    result = assess(tmp_path, manifest, fabrication, sidecar)
    assert result["ready_observed_record_count"] == 1
    assert len(result["unreported_instance_ids"]) == 64
    assert result["declarations_and_artifact_availability_only"]
    assert result["certificate_or_uncertainty_content_authenticated"] is False
    assert result["confidence_probability_inferred_from_coverage_factor"] is None
    assert all(value is False for value in result["qualification"].values())
    assert result["input_canonical_sha256"] == {
        "fabrication_records": canonical_sha256(fabrication),
        "printable_manifest": canonical_sha256(manifest),
        "readiness_sidecar": canonical_sha256(sidecar),
    }


def test_synthetic_complete_declarations_never_count_as_observed_ready(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path, "synthetic")
    result = assess(tmp_path, manifest, fabrication, sidecar)
    assert result["ready_observed_record_count"] == 0
    assert result["complete_synthetic_fixture_count"] == 1


def test_known_weighing_with_blank_support_remains_unknown_and_mixed_states_block(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    blank = tool.template(fabrication, manifest)
    result = assess(tmp_path, manifest, fabrication, blank)
    assert set(result["records"][0]["blocking_reasons"]) == {
        "uncertainty_unknown",
        "calibration_unknown",
    }
    sidecar["instruments"][0]["calibration"]["evidence_state"] = "synthetic"
    result = assess(tmp_path, manifest, fabrication, sidecar)
    assert not result["records"][0]["ready_for_engineering_review"]
    assert "calibration_evidence_state_mismatch" in result["records"][0]["blocking_reasons"]


@pytest.mark.parametrize("change", ["mass", "sample", "instrument", "conditions", "source"])
def test_changed_existing_measurement_invalidates_companion_binding(tmp_path, change):
    manifest, fabrication, sidecar = fixture(tmp_path)
    row = fabrication["records"][0]
    if change == "mass":
        row["weighing"]["cleaned_part_mass_kg"] += 0.001
    elif change == "sample":
        row["weighing"]["sample_id"] += "-different"
    elif change == "instrument":
        row["weighing"]["instrument_id"] += "-different"
    elif change == "conditions":
        row["weighing"]["provenance"]["conditions"] += " changed"
    else:
        row["source_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="stale|differs"):
        assess(tmp_path, manifest, fabrication, sidecar)


def test_weighing_row_pin_still_rejects_after_only_whole_document_is_rebound(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    fabrication["records"][0]["weighing"]["cleaned_part_mass_kg"] += 0.001
    sidecar["fabrication_records_canonical_sha256"] = canonical_sha256(fabrication)
    with pytest.raises(ValueError, match="weighing row"):
        assess(tmp_path, manifest, fabrication, sidecar)


@pytest.mark.parametrize(
    "field,value",
    [
        ("standard_uncertainty_kg", 0),
        ("standard_uncertainty_kg", True),
        ("expanded_uncertainty_kg", float("nan")),
        ("coverage_factor", float("inf")),
        ("coverage_factor", 0.5),
        ("expanded_uncertainty_kg", 0.0005),
        ("resolution_accounted_for", 1),
        ("calibration_accounted_for", False),
        ("repeatability_accounted_for", None),
        ("budget_description", ""),
    ],
)
def test_uncertainty_declaration_is_typed_finite_consistent_and_explicit(tmp_path, field, value):
    manifest, fabrication, sidecar = fixture(tmp_path)
    sidecar["records"][0]["uncertainty"][field] = value
    with pytest.raises(ValueError):
        assess(tmp_path, manifest, fabrication, sidecar)


@pytest.mark.parametrize(
    "date,expected",
    [
        ("2026-11-10T00:00:00Z", True),
        ("2026-11-11T23:59:59Z", True),
        ("2026-11-12T00:00:00Z", False),
        ("2026-11-09T23:59:59Z", False),
    ],
)
def test_calibration_window_is_half_open_at_measurement_time(tmp_path, date, expected):
    manifest, fabrication, sidecar = fixture(tmp_path)
    fabrication["records"][0]["weighing"]["provenance"]["captured_at"] = date
    updated = tool.template(fabrication, manifest)
    updated["instruments"] = sidecar["instruments"]
    updated["records"][0]["uncertainty"] = sidecar["records"][0]["uncertainty"]
    result = assess(tmp_path, manifest, fabrication, updated, as_of="2026-11-13T00:00:00Z")
    assert result["records"][0]["ready_for_engineering_review"] is expected
    assert result["records"][0]["calibration_expired_at_review_time"] is True


def test_future_measurement_and_future_calibration_never_become_ready(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    result = assess(tmp_path, manifest, fabrication, sidecar, as_of="2026-11-09T00:00:00Z")
    assert not result["records"][0]["ready_for_engineering_review"]
    assert {"measurement_in_future", "calibration_in_future"} <= set(
        result["records"][0]["blocking_reasons"]
    )


def test_existing_explicit_timezone_is_normalized_without_changing_base_form(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    fabrication["records"][0]["weighing"]["provenance"]["captured_at"] = "2026-11-11T06:00:00-06:00"
    updated = tool.template(fabrication, manifest)
    updated["instruments"] = sidecar["instruments"]
    updated["records"][0]["uncertainty"] = sidecar["records"][0]["uncertainty"]
    assert assess(tmp_path, manifest, fabrication, updated)["ready_observed_record_count"] == 1


@pytest.mark.parametrize("stamp", ["2026-11-10T00:00:00", "2026-11-10T00:00:00-06:00", "bad"])
def test_sidecar_calibration_and_review_dates_require_explicit_utc(tmp_path, stamp):
    manifest, fabrication, sidecar = fixture(tmp_path)
    with pytest.raises(ValueError):
        assess(tmp_path, manifest, fabrication, sidecar, as_of=stamp)
    sidecar["instruments"][0]["calibration"]["calibrated_at_utc"] = stamp
    with pytest.raises(ValueError):
        assess(tmp_path, manifest, fabrication, sidecar)


def test_retrospective_invalidation_blocks_previously_in_window_measurement(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    ref = sidecar["instruments"][0]["calibration"]["evidence"]
    invalid = {
        "recorded_at_utc": "2026-11-11T13:00:00Z",
        "affects_measurements_from_utc": "2026-11-11T11:00:00Z",
        "reason": "fabricated retrospective out-of-spec finding",
        "evidence": ref,
    }
    sidecar["instruments"][0]["calibration"]["invalidation"] = invalid
    result = assess(tmp_path, manifest, fabrication, sidecar)
    assert "calibration_invalidated_for_measurement" in result["records"][0]["blocking_reasons"]
    assert not result["records"][0]["ready_for_engineering_review"]
    invalid["affects_measurements_from_utc"] = "2026-11-11T12:00:00Z"
    assert not assess(tmp_path, manifest, fabrication, sidecar)["records"][0][
        "ready_for_engineering_review"
    ]
    invalid["affects_measurements_from_utc"] = "2026-11-11T12:00:01Z"
    assert assess(tmp_path, manifest, fabrication, sidecar)["records"][0][
        "ready_for_engineering_review"
    ]


def test_future_invalidation_finding_blocks_readiness_and_bad_chronology_rejects(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    calibration = sidecar["instruments"][0]["calibration"]
    invalid = {
        "recorded_at_utc": "2026-11-11T14:00:00Z",
        "affects_measurements_from_utc": "2026-11-11T13:30:00Z",
        "reason": "fabricated future finding",
        "evidence": calibration["evidence"],
    }
    calibration["invalidation"] = invalid
    result = assess(tmp_path, manifest, fabrication, sidecar)
    assert "invalidation_record_in_future" in result["records"][0]["blocking_reasons"]
    assert not result["records"][0]["ready_for_engineering_review"]
    invalid["affects_measurements_from_utc"] = "2026-11-11T15:00:00Z"
    with pytest.raises(ValueError, match="effective time"):
        assess(tmp_path, manifest, fabrication, sidecar)
    invalid.update(
        recorded_at_utc="2026-11-09T00:00:00Z", affects_measurements_from_utc="2026-11-08T00:00:00Z"
    )
    with pytest.raises(ValueError, match="before it was issued"):
        assess(tmp_path, manifest, fabrication, sidecar)


def test_nonpositive_calibration_window_rejects(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    calibration = sidecar["instruments"][0]["calibration"]
    calibration["valid_until_utc"] = calibration["calibrated_at_utc"]
    with pytest.raises(ValueError, match="positive duration"):
        assess(tmp_path, manifest, fabrication, sidecar)


@pytest.mark.parametrize("section", ["calibration", "budget", "conditions"])
def test_missing_or_changed_support_bytes_prevent_readiness(tmp_path, section):
    manifest, fabrication, sidecar = fixture(tmp_path)
    path = tmp_path / (section + ".txt")
    path.write_text("changed synthetic evidence", encoding="utf-8")
    result = assess(tmp_path, manifest, fabrication, sidecar)
    assert not result["records"][0]["ready_for_engineering_review"]
    path.unlink()
    assert not assess(tmp_path, manifest, fabrication, sidecar)["records"][0][
        "ready_for_engineering_review"
    ]


@pytest.mark.parametrize(
    "path",
    ["../outside", "nested/../outside", "/absolute", "C:/private", "x\\y", "https://example.com"],
)
def test_support_artifacts_cannot_escape_evidence_root(tmp_path, path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    sidecar["records"][0]["uncertainty"]["uncertainty_evidence"]["path"] = path
    with pytest.raises(ValueError, match="path"):
        assess(tmp_path, manifest, fabrication, sidecar)


def test_artifact_size_bound_never_turns_unread_contents_into_ready(tmp_path):
    manifest, fabrication, sidecar = fixture(tmp_path)
    with (tmp_path / "budget.txt").open("wb") as stream:
        stream.seek(32 * 1024**2)
        stream.write(b"x")
    result = assess(tmp_path, manifest, fabrication, sidecar)
    assert not result["records"][0]["ready_for_engineering_review"]
    assert "uncertainty_evidence_exceeds_32_MiB_bound" in result["records"][0]["blocking_reasons"]


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_record",
        "duplicate_instrument",
        "unknown_instrument",
        "qualification",
        "schema",
        "units",
        "extra",
    ],
)
def test_identity_schema_units_and_no_qualification_contract(tmp_path, change):
    manifest, fabrication, sidecar = fixture(tmp_path)
    if change == "duplicate_record":
        sidecar["records"].append(copy.deepcopy(sidecar["records"][0]))
    elif change == "duplicate_instrument":
        sidecar["instruments"].append(copy.deepcopy(sidecar["instruments"][0]))
    elif change == "unknown_instrument":
        sidecar["instruments"][0]["instrument_id"] += "wrong"
    elif change == "qualification":
        sidecar["qualification"]["mass_ledger_modified"] = True
    elif change == "schema":
        sidecar["schema_version"] = True
    elif change == "units":
        sidecar["units"]["mass"] = "g"
    else:
        sidecar["physical_mass_kg"] = 0.02
    with pytest.raises(ValueError):
        assess(tmp_path, manifest, fabrication, sidecar)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b"[]", b"\xff"])
def test_strict_bounded_json_rejects_ambiguous_or_nonfinite_input(tmp_path, raw):
    path = tmp_path / "input.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        tool.strict_json(path)


def test_json_read_bound_applies_before_decode(tmp_path):
    path = tmp_path / "large.json"
    path.write_bytes(b" " * 1048577)
    with pytest.raises(ValueError, match="one MiB"):
        tool.strict_json(path)
