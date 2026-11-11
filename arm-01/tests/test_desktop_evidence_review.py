"""Cross-artifact corruption fixtures, not a repeat of load model arithmetic."""

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAD = ROOT / "hardware" / "cad"


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


audit = _module("desktop_evidence_review", ROOT / "tools" / "review_desktop_evidence.py")
loads = _module("desktop_evidence_load_source", ROOT / "tools" / "thor_load_analysis.py")


def _json(name):
    return json.loads((CAD / name).read_text(encoding="utf-8"))


@pytest.fixture
def inputs():
    return (
        _json("thor-mounted-geometry-v2.json"),
        _json("thor-wrist-membership-v2.json"),
        _json("thor-mounted-geometry.json"),
    )


@pytest.fixture
def snapshot(inputs):
    inventory, membership, _ = inputs
    return loads.expand_mass_assignments(
        loads.build_thor_snapshot(
            inventory, instance_mass_overrides=membership["instance_mass_overrides"]
        ),
        membership,
    )


def test_pinned_cross_artifact_review_and_independent_mass_com(inputs, snapshot):
    result = audit.review(ROOT, snapshot)
    assert result["coverage"]["historical_leaves_preserved"] == 516
    assert result["coverage"]["native_source_terminal_traversal_performed"] is False
    assert result["study"]["stored_payload_pose_cases_checked"] == 72
    mass = result["mass_snapshot"]
    assert mass["whole_motor_count"] == 7
    assert mass["whole_motor_mass_kg"] == pytest.approx(2.120)
    assert mass["modeled_mass_kg"] == pytest.approx(5.6547224855756)
    assert mass["physical_mass_validated"] is False


@pytest.mark.parametrize("corruption", ["duplicate", "missing", "class", "old", "mass", "claim"])
def test_coverage_rejects_cross_artifact_corruption(inputs, corruption):
    inventory, membership, historical = inputs
    if corruption == "duplicate":
        membership["memberships"].append(copy.deepcopy(membership["memberships"][0]))
    elif corruption == "missing":
        membership["memberships"].pop()
    elif corruption == "class":
        membership["memberships"][0]["motion_class"] = "undefined"
    elif corruption == "old":
        inventory["mounted_bodies"][0]["zero_world_com_m"][0] += 0.001
    elif corruption == "mass":
        membership["instance_mass_overrides"].pop(next(iter(membership["instance_mass_overrides"])))
    else:
        inventory["complete_mass_model"] = True
    with pytest.raises(ValueError):
        audit.audit_coverage(inventory, membership, historical)


@pytest.mark.parametrize("corruption", ["duplicate", "omitted", "frame", "motor"])
def test_mass_audit_rejects_duplicate_missing_frame_and_motor_errors(inputs, snapshot, corruption):
    inventory, membership, _ = inputs
    if corruption == "duplicate":
        snapshot["bodies"][-1] = copy.deepcopy(snapshot["bodies"][0])
    elif corruption == "omitted":
        snapshot["bodies"].pop()
    elif corruption == "frame":
        # A common extraction error is applying the CAD->ROS rotation twice.
        body = next(row for row in snapshot["bodies"] if abs(row["com_m"][0]) > 0.001)
        x, y, z = body["com_m"]
        body["com_m"] = [y, -x, z]
    else:
        body = next(
            row
            for row in snapshot["bodies"]
            if row["mass_assignment"]["category"].startswith("manufacturer_motor_mass_")
        )
        body["mass_kg"] *= 2
    with pytest.raises(ValueError):
        audit.audit_mass_snapshot(snapshot, inventory, membership)


@pytest.mark.parametrize("corruption", ["stale", "wrist", "force", "moment", "support", "empty"])
def test_study_audit_rejects_provenance_and_wrench_corruption(inputs, corruption):
    inventory, membership, _ = inputs
    study = _json("thor-wrist-load-study-v2.json")
    case = study["cases"][0]
    payload = next(iter(case["poses"].values()))["payload_cases"][0]
    if corruption == "stale":
        study["membership_canonical_sha256"] = "0" * 64
    elif corruption == "wrist":
        payload["joints"][5]["required_ideal_holding_torque_nm"] = 0
    elif corruption == "force":
        payload["gravity_wrench_about_frame_origin"]["external_force_n"][2] -= 1
    elif corruption == "moment":
        wrench = payload["gravity_wrench_about_frame_origin"]
        wrench["external_moment_nm"][0] += 1
        wrench["ideal_support_moment_nm"][0] -= 1
    elif corruption == "support":
        payload["gravity_wrench_about_frame_origin"]["ideal_support_force_n"][2] = 0
    else:
        study["cases"] = []
    with pytest.raises(ValueError):
        audit.audit_study(study, inventory, membership)


def test_exact_file_digest_does_not_silently_normalize_line_endings(tmp_path):
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b'{\n  "value": 1\n}\n')
    crlf.write_bytes(lf.read_bytes().replace(b"\n", b"\r\n"))
    assert audit.file_sha256(lf) != audit.file_sha256(crlf)
    assert audit.canonical_sha256(json.loads(lf.read_bytes())) == audit.canonical_sha256(
        json.loads(crlf.read_bytes())
    )


def test_independent_point_transform_potential_agrees_with_seven_coordinate_efforts(
    inputs, snapshot
):
    _, membership, _ = inputs
    jaw = _json("thor-jaw-body-ledger.json")
    result = audit.independent_potential_review(snapshot, membership, jaw, loads, cases_per_phase=1)
    assert result["poses_checked"] == 2
    assert result["coordinate_gradient_checks"] == 14
    assert result["max_gravity_effort_discrepancy_nm"] < 3e-8


def test_independent_potential_check_rejects_corrupted_wrist_effort(inputs, snapshot, monkeypatch):
    _, membership, _ = inputs
    jaw = _json("thor-jaw-body-ledger.json")
    original = loads.analyze

    def wrong_effort(*args, **kwargs):
        result = original(*args, **kwargs)
        result["scenarios"][0]["joints"][5][
            "conditional_modeled_wrist_gravity_contribution_nm"
        ] += 0.1
        return result

    monkeypatch.setattr(loads, "analyze", wrong_effort)
    with pytest.raises(ValueError, match="potential gradients"):
        audit.independent_potential_review(snapshot, membership, jaw, loads, cases_per_phase=1)


def test_cli_reports_scope_and_rejects_absent_root(tmp_path):
    script = ROOT / "tools" / "review_desktop_evidence.py"
    valid = subprocess.run(
        [sys.executable, str(script), "--build-snapshot"], capture_output=True, text=True
    )
    assert valid.returncode == 0, valid.stderr
    result = json.loads(valid.stdout)
    assert "not_native_or_physical" in result["evidence_class"]
    invalid = subprocess.run(
        [sys.executable, str(script), "--root", str(tmp_path)], capture_output=True, text=True
    )
    assert invalid.returncode == 2
    assert "Traceback" not in invalid.stderr


def test_cli_preserves_existing_evidence_and_refuses_ambiguous_snapshot_source(tmp_path):
    script = ROOT / "tools" / "review_desktop_evidence.py"
    output = tmp_path / "review.json"
    output.write_bytes(b"existing evidence\n")
    result = subprocess.run(
        [sys.executable, str(script), "--output", str(output)], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert output.read_bytes() == b"existing evidence\n"
    result = subprocess.run(
        [sys.executable, str(script), "--math-checks", "--snapshot", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "choose one snapshot source" in result.stderr


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', "[]"])
def test_review_json_rejects_ambiguous_nonfinite_and_nonobject_inputs(tmp_path, text):
    path = tmp_path / "input.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        audit._load(path)
