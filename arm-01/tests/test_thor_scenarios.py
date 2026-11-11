"""Scenario provenance, changed-input rejection and preserved load evidence."""

import copy
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from raftel_arm01.engineering.scenarios import (
    canonical_sha256,
    load_scenario_manifest,
    validate_scenario_manifest,
    verify_scenario_inputs,
)

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "tools"
for name in ("thor_load_analysis", "thor_scenario_analysis"):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
study = sys.modules["thor_scenario_analysis"]


def manifest():
    return load_scenario_manifest(ROOT / "config/thor-scenario-v1.json")


def assert_close_json(actual, expected):
    """Exact structure/discrete evidence, tight platform-independent float tolerance."""
    if isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=2e-12, abs=2e-12)
    elif isinstance(expected, dict):
        assert set(actual) == set(expected)
        for key in expected:
            assert_close_json(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected, strict=True):
            assert_close_json(left, right)
    else:
        assert actual == expected


def test_bound_scenario_reproduces_and_retains_exact_mass_identity():
    config = manifest()
    report = study.scenario_report(config, ROOT)
    expected = json.loads((ROOT / "hardware/cad/thor-scenario-study-v1.json").read_text())
    assert_close_json(report, expected)
    mass = report["mass_conservation"]
    assert mass["native_leaf_count"] == 518
    assert mass["mass_record_count"] == 517
    assert mass["motor_asset_count"] == 7
    assert mass["motor_mass_kg"] == pytest.approx(2.120, abs=1e-14)
    assert report["full_physical_wrist_holding_torques_remain_unknown"]
    assert not report["actuator_or_fabrication_qualification"]
    assert not report["native_recompute_performed"]
    for case in report["cases"]:
        assert case["joints"][4]["required_ideal_holding_torque_nm"] is None
        assert case["joints"][5]["required_ideal_holding_torque_nm"] is None
        if case["jaw"]["configuration"] == "saved_frozen":
            assert case["conditional_jaw_gravity_torque_nm"] is None
        else:
            assert math.isfinite(case["conditional_jaw_gravity_torque_nm"])


def test_manifest_validation_defensively_copies_and_hashes_normalized_content():
    config = manifest()
    saved = copy.deepcopy(config)
    result = validate_scenario_manifest(config)
    result["cases"][0]["joint_angles_rad"][0] = 1
    assert config == saved
    assert canonical_sha256(config) == canonical_sha256(json.loads(json.dumps(config, indent=4)))


@pytest.mark.parametrize(
    "section,key,bad",
    [
        (None, "schema_version", True),
        (None, "schema_version", 99),
        (None, "evidence_class", "physical_test"),
        (None, "coordinate_frame", "native_CAD_world_m"),
        (None, "gravity_m_s2", [0, 0, -1]),
        ("material", "density_kg_m3", math.nan),
        ("material", "density_kg_m3", True),
        ("material", "effective_whole_part_solid_fraction", 0),
        ("material", "effective_whole_part_solid_fraction", 1.1),
        ("material", "density_evidence", ""),
        ("source_revisions", "thor_cad", "main"),
        ("source_revisions", "thor_ros", "0" * 39),
    ],
)
def test_ambiguous_nonfinite_or_unsupported_manifest_fields_rejected(section, key, bad):
    config = manifest()
    target = config if section is None else config[section]
    target[key] = bad
    with pytest.raises(ValueError):
        validate_scenario_manifest(config)


@pytest.mark.parametrize("path", ["../input.json", "/input.json", "C:/input.json", "a\\b", "a//b"])
def test_input_paths_cannot_escape_or_change_path_syntax(path):
    config = manifest()
    config["inputs"]["inventory"]["path"] = path
    with pytest.raises(ValueError, match="path"):
        validate_scenario_manifest(config)


def test_hash_bound_input_rejects_changed_bytes_even_if_json_content_is_equal(tmp_path):
    config = manifest()
    for binding in config["inputs"].values():
        source = ROOT / binding["path"]
        target = tmp_path / binding["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    verify_scenario_inputs(config, tmp_path)
    changed = tmp_path / config["inputs"]["inventory"]["path"]
    changed.write_bytes(changed.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="stale input hash for inventory"):
        verify_scenario_inputs(config, tmp_path)


def test_cross_file_revision_membership_and_belt_changes_rejected():
    for mutate in (
        lambda config, inputs: config["source_revisions"].update(thor_ros="0" * 40),
        lambda config, inputs: inputs["inventory"].update(native_source_revision="0" * 40),
        lambda config, inputs: inputs["membership"].update(source_geometry_sha256="0" * 64),
        lambda config, inputs: inputs["membership"]["instance_mass_overrides"].clear(),
    ):
        config = manifest()
        inputs = verify_scenario_inputs(config, ROOT)
        mutate(config, inputs)
        with pytest.raises(ValueError):
            study.validate_bound_model(config, inputs)


def test_saved_and_ideal_jaw_coordinates_cannot_be_conflated():
    config = manifest()
    config["cases"][0]["jaw"]["closing_angle_rad"] = 0
    with pytest.raises(ValueError, match="no common solved"):
        validate_scenario_manifest(config)
    config["cases"][0]["jaw"]["configuration"] = "ideal_body_overlay"
    config["inputs"].pop("jaw_bodies")
    with pytest.raises(ValueError, match="jaw_bodies"):
        validate_scenario_manifest(config)


def test_missing_units_payload_evidence_duplicate_cases_and_unknown_keys_fail():
    for mutate in (
        lambda data: data["units"].update(position="mm"),
        lambda data: data["cases"][0]["payload"].update(com_evidence=""),
        lambda data: data["cases"].append(copy.deepcopy(data["cases"][0])),
        lambda data: data.update(unrecognized_motion_permission=True),
        lambda data: data["inputs"].pop("membership"),
    ):
        config = manifest()
        mutate(config)
        with pytest.raises(ValueError):
            validate_scenario_manifest(config)


def test_cli_rejects_existing_evidence_and_stale_inputs(tmp_path):
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        str(TOOLS / "thor_scenario_analysis.py"),
        str(ROOT / "config/thor-scenario-v1.json"),
        "--output",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    before = output.read_bytes()
    assert json.loads(before)["case_count"] == len(manifest()["cases"])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode != 0 and "File exists" in result.stderr
    assert output.read_bytes() == before
    bad = manifest()
    bad["inputs"]["inventory"]["sha256"] = hashlib.sha256(b"unrelated").hexdigest()
    bad_manifest = tmp_path / "bad.json"
    bad_manifest.write_text(json.dumps(bad))
    result = subprocess.run(
        [sys.executable, str(TOOLS / "thor_scenario_analysis.py"), str(bad_manifest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "stale input hash" in result.stderr


@pytest.mark.parametrize("raw", ['{"schema_version":1,"schema_version":1}', '{"a":NaN}'])
def test_ambiguous_duplicate_keys_or_nonfinite_json_cannot_be_evidence(tmp_path, raw):
    path = tmp_path / "ambiguous.json"
    path.write_text(raw)
    with pytest.raises(ValueError, match="duplicate JSON|nonfinite JSON"):
        load_scenario_manifest(path)
    config = manifest()
    binding = config["inputs"]["inventory"]
    target = tmp_path / binding["path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(raw.encode())
    binding["sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    with pytest.raises(ValueError, match="duplicate JSON|nonfinite JSON"):
        verify_scenario_inputs(config, tmp_path)
