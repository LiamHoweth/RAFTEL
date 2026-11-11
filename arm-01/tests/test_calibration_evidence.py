"""Calibration evidence is not commissioned driver configuration."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from raftel_arm01.control.calibration_evidence import (
    load_calibration,
    validate_calibration_document,
)

TEMPLATE = Path(__file__).resolve().parents[1] / "config/thor-calibration-template.json"


def template():
    return json.loads(TEMPLATE.read_text())


def evidence(state):
    return {
        "source": [{"reference": "pinned/file", "revision": "a" * 40, "sha256": "b" * 64}],
        "assumed": [
            {"rationale": "declared analysis scenario", "revisit_trigger": "measure input"}
        ],
        "synthetic": [{"fixture": "generated fixture", "sha256": "c" * 64, "seed": 42}],
        "physical": [
            {
                "record": "example-test-only.json",
                "sha256": "d" * 64,
                "instrument": "test-only instrument id",
                "observed_at": "2026-11-11T20:00:00Z",
                "conditions": (
                    "synthetic fixture describing physical record syntax; no real measurement"
                ),
            }
        ],
    }[state]


def known_record(document, name, state="assumed", value=1):
    record = document["parameters"][name]
    record.update(state=state, value=value, evidence=evidence(state))
    if state == "physical":
        record["uncertainty_abs"] = [0.01] * 7 if isinstance(value, list) else 0.01
    return record


def test_unknown_template_retains_every_gate_and_never_commissions():
    summary = load_calibration(TEMPLATE)
    assert len(summary.unknown_parameters) == 10
    assert summary.unknown_artifact_hashes == ("installed_firmware", "installed_settings")
    assert not summary.analysis_inputs_complete
    assert not summary.commissioned
    assert len(summary.nonphysical_parameters) == 10


@pytest.mark.parametrize("state", ["source", "assumed", "synthetic", "physical"])
def test_states_remain_distinct_and_physical_record_is_not_commissioning(state):
    document = template()
    known_record(document, "elbow_belt_ratio", state, 5.8)
    summary = validate_calibration_document(document)
    assert "elbow_belt_ratio" not in summary.unknown_parameters
    assert ("elbow_belt_ratio" in summary.nonphysical_parameters) == (state != "physical")
    assert not summary.commissioned
    assert not summary.analysis_inputs_complete


def test_even_complete_evidence_document_does_not_assert_commissioning():
    document = template()
    for name in document["parameters"]:
        known_record(document, name, "physical", [1] * 7 if name.startswith("channel_") else 1)
    for item in document["artifacts"].values():
        item.update(state="physical", sha256="f" * 64, evidence=evidence("physical"))
    summary = validate_calibration_document(document)
    assert summary.analysis_inputs_complete
    assert not summary.nonphysical_parameters
    assert not summary.commissioned


@pytest.mark.parametrize("state", ["source", "assumed", "synthetic", "physical"])
def test_known_values_require_evidence_specific_to_the_state(state):
    document = template()
    record = known_record(document, "carrier_coefficient", state)
    record["evidence"] = []
    with pytest.raises(ValueError, match="evidence"):
        validate_calibration_document(document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("commissioning_status", "commissioned"),
        ("channel_order", ["A", "B", "D"]),
        ("evidence_class", "physical_test"),
    ],
)
def test_document_contract_cannot_be_promoted_or_reordered(field, value):
    document = template()
    document[field] = value
    with pytest.raises(ValueError):
        validate_calibration_document(document)


@pytest.mark.parametrize(
    "name,value",
    [
        ("elbow_belt_ratio", 0),
        ("shoulder_branch_ratio", -1),
        ("wrist_handedness", 0),
        ("elbow_belt_sign", 1.0),
        ("elbow_belt_sign", True),
        ("wrist_positive_y_rotor_scale", 0),
        ("carrier_coefficient", float("nan")),
        ("carrier_coefficient", float("inf")),
        ("channel_steps_per_degree", [1] * 6),
        ("channel_steps_per_degree", [1] * 6 + [0]),
        ("channel_zero_deg", [0] * 6 + [True]),
    ],
)
def test_invalid_numeric_parameters_rejected(name, value):
    document = template()
    known_record(document, name, value=value)
    with pytest.raises(ValueError):
        validate_calibration_document(document)


def test_unknown_values_and_uncertainty_cannot_look_measured():
    document = template()
    document["parameters"]["elbow_belt_ratio"]["value"] = 5.8
    with pytest.raises(ValueError, match="null"):
        validate_calibration_document(document)
    document = template()
    record = known_record(document, "elbow_belt_ratio", "physical", 5.8)
    record["uncertainty_abs"] = None
    with pytest.raises(ValueError, match="uncertainty"):
        validate_calibration_document(document)
    record["uncertainty_abs"] = -1
    with pytest.raises(ValueError, match="uncertainty"):
        validate_calibration_document(document)


def test_physical_provenance_requires_instrument_conditions_utc_and_hash():
    document = template()
    record = known_record(document, "carrier_coefficient", "physical")
    for field, bad in (
        ("instrument", ""),
        ("conditions", ""),
        ("sha256", "unhashed"),
        ("observed_at", "2026-11-11T12:00:00"),
        ("observed_at", "yesterday"),
    ):
        candidate = copy.deepcopy(document)
        candidate["parameters"]["carrier_coefficient"]["evidence"][0][field] = bad
        with pytest.raises(ValueError):
            validate_calibration_document(candidate)
    record["evidence"][0]["observed_at"] = "2026-11-11T15:00:00-05:00"
    with pytest.raises(ValueError, match="UTC"):
        validate_calibration_document(document)


def test_source_revision_is_immutable_not_a_branch_name():
    document = template()
    record = known_record(document, "elbow_belt_ratio", "source")
    record["evidence"][0]["revision"] = "main"
    with pytest.raises(ValueError, match="immutable"):
        validate_calibration_document(document)


def test_stale_file_hash_wrong_schema_and_malformed_json_fail(tmp_path):
    correct_hash = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
    assert not load_calibration(TEMPLATE, expected_sha256=correct_hash).commissioned
    with pytest.raises(ValueError, match="stale"):
        load_calibration(TEMPLATE, expected_sha256="0" * 64)
    document = template()
    del document["parameters"]["carrier_coefficient"]
    with pytest.raises(ValueError, match="fields"):
        validate_calibration_document(document)
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version":')
    with pytest.raises(ValueError, match="malformed"):
        load_calibration(path)


@pytest.mark.parametrize("text", ['{"schema_version":1,"schema_version":2}', '{"x":NaN}'])
def test_evidence_json_duplicate_and_nonfinite_constants_rejected(tmp_path, text):
    path = tmp_path / "ambiguous.json"
    path.write_text(text)
    with pytest.raises(ValueError, match="malformed"):
        load_calibration(path)
