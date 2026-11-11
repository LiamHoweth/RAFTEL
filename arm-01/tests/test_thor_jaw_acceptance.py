"""Synthetic multi-pose predicates and historical unsolved-pose diagnostics."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAD = ROOT / "hardware/cad"


@pytest.fixture(scope="module")
def tool():
    # These tools are intentionally independent of the installed runtime package.
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "jaw_acceptance", ROOT / "tools/thor_jaw_acceptance.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.path.remove(str(ROOT / "tools"))


@pytest.fixture
def spec():
    return json.loads((CAD / "thor-jaw-repair-specification.json").read_text(encoding="utf-8"))


@pytest.fixture
def capture(spec):
    poses = []
    # Independent analytic construction: equal 35mm links, horizontal fingers,
    # source pivot separation. No CAD/native execution is implied by these values.
    for q in spec["required_q_rad"]:
        c, s = math.cos(q), math.sin(q)
        sides = {}
        for label, sign in (("left", -1), ("right", 1)):
            driven_tip = [sign * (0.0145 + 0.035 * c), 0.0325 + 0.035 * s, 0.0145]
            auxiliary_tip = [sign * (0.006 + 0.035 * c), 0.051 + 0.035 * s, 0.0145]
            sides[label] = {
                "driven_pivot_m": [sign * 0.0145, 0.0325, 0.0145],
                "auxiliary_pivot_m": [sign * 0.006, 0.051, 0.0145],
                "driven_tip_m": driven_tip,
                "auxiliary_tip_m": auxiliary_tip,
                "finger_driven_hole_m": driven_tip[:2] + [0.021925],
                "finger_auxiliary_hole_m": auxiliary_tip[:2] + [0.021925],
                "axis_units": {
                    name: [0, 0, 1]
                    for name in (
                        "driven_base",
                        "auxiliary_base",
                        "finger_driven",
                        "finger_auxiliary",
                    )
                },
                "contact_plane": {
                    "point_m": [sign * 0.035 * c, 0.07 + 0.035 * s, 0.021925],
                    "normal_unit": [-sign, 0, 0],
                },
            }
        poses.append({"q_rad": q, "sides": sides})
    return {
        "schema_version": 1,
        "evidence_class": "synthetic_fixture",
        "source_revision": spec["source_revision"],
        "original_source_sha256": copy.deepcopy(spec["original_source_sha256"]),
        "jaw_body_ledger_canonical_sha256": spec["jaw_body_ledger_canonical_sha256"],
        "coordinate_frame": spec["coordinate_frame"],
        "configuration": "ideal_derived_candidate",
        "provenance": {"fixture": "independent closed-form geometry; no native run"},
        "poses": poses,
    }


def test_committed_repair_specification_is_reproducible(tool, spec):
    ledger = json.loads((CAD / "thor-jaw-body-ledger.json").read_text(encoding="utf-8"))
    assert tool.repair_specification(ledger) == spec


def test_three_ideal_poses_pass_only_declared_geometry_predicates(tool, spec, capture):
    report = tool.evaluate_capture(spec, capture)
    assert report["declared_geometric_predicates_passed"]
    assert report["input_evidence_class"] == "synthetic_fixture"
    assert not report["missing_required_q_rad"]
    assert not report["native_rebuild_metadata_complete"]
    for field in (
        "native_verification_complete",
        "contact_qualified",
        "retention_qualified",
        "physical_calibration_qualified",
        "fabrication_released",
    ):
        assert report[field] is False
    assert report["usable_opening_m"] is None
    assert [p["measured_plane_separation_m"] for p in report["poses"]] == pytest.approx(
        [0.07, 0.07 * math.sqrt(3) / 2, 0.035]
    )
    assert all(len(pose["checks"]) >= 30 for pose in report["poses"])


@pytest.mark.parametrize("failure", ["pivot", "loop", "normal", "gap", "phase"])
def test_independent_geometric_counterexamples_fail(tool, spec, capture, failure):
    side = capture["poses"][1]["sides"]["left"]
    if failure == "pivot":
        side["driven_pivot_m"][0] += 0.0005
    elif failure == "loop":
        side["finger_driven_hole_m"][1] += 0.0005
    elif failure == "normal":
        side["contact_plane"]["normal_unit"] = [math.cos(0.01), math.sin(0.01), 0]
    elif failure == "gap":
        side["contact_plane"]["point_m"][0] -= 0.0005
    elif failure == "phase":
        side["driven_tip_m"][1] -= 0.0005
    report = tool.evaluate_capture(spec, capture)
    assert not report["declared_geometric_predicates_passed"]
    assert any(not check["passed"] for check in report["poses"][1]["checks"])


def test_original_saved_pose_diagnoses_residuals_without_assigning_q(tool, spec, capture):
    raw = json.loads((CAD / "thor-gripper-kinematics.json").read_text(encoding="utf-8"))
    points = raw["saved_assembly_points_in_bot_frame_mm"]
    pose = capture["poses"][0]
    pose["q_rad"] = None
    for label, driven in (("left", "active"), ("right", "passive")):
        side = pose["sides"][label]
        for kind in ("pivot", "tip"):
            side["driven_" + kind + "_m"] = [v / 1000 for v in points[driven + "_driven_" + kind]]
            side["auxiliary_" + kind + "_m"] = [
                v / 1000 for v in points[label + "_auxiliary_" + kind]
            ]
        for kind in ("driven", "auxiliary"):
            side["finger_" + kind + "_hole_m"] = [
                v / 1000 for v in points[label + "_finger_" + kind + "_hole"]
            ]
    capture["configuration"] = "saved_original"
    capture["poses"] = [pose]
    report = tool.evaluate_capture(spec, capture)
    assert not report["declared_geometric_predicates_passed"]
    assert report["poses"][0]["q_rad"] is None
    assert report["poses"][0]["conditional_ideal_aperture_m"] is None
    residuals = {check["predicate"]: check["residual"] for check in report["poses"][0]["checks"]}
    assert residuals["left.driven.loop_axis_distance_m"] == pytest.approx(0.00017144136, abs=1e-10)
    assert residuals["right.driven.loop_axis_distance_m"] == pytest.approx(0.00015271619, abs=1e-10)
    assert residuals["left.driven.base_pivot_xy_m"] == pytest.approx(15e-6, abs=1e-14)
    assert report["missing_required_q_rad"] == spec["required_q_rad"]


def test_native_metadata_never_authenticates_execution(tool, spec, capture):
    capture["evidence_class"] = "native_selected_geometry"
    capture["provenance"] = {
        "generator": "synthetic fixture exercising metadata schema",
        "runtime_name": "FreeCAD (test declaration)",
        "runtime_version": "test",
        "candidate_document_sha256": {"AssemblyArt56.FCStd": "a" * 64},
        "recompute_mode": "force_selected_feature_rebuild",
        "save_reopen_verified": True,
    }
    report = tool.evaluate_capture(spec, capture)
    assert report["native_rebuild_metadata_complete"] is True
    assert report["declared_geometric_predicates_passed"] is True
    assert report["native_verification_complete"] is False
    assert report["contact_qualified"] is False


def test_missing_required_pose_fails_complete_capture_predicates(tool, spec, capture):
    capture["poses"].pop()
    report = tool.evaluate_capture(spec, capture)
    assert report["missing_required_q_rad"] == [math.pi / 3]
    assert not report["declared_geometric_predicates_passed"]


@pytest.mark.parametrize(
    "failure",
    [
        "duplicate_pose",
        "boolean_schema",
        "unknown_class",
        "stale_ledger",
        "source",
        "wrong_frame",
        "nonfinite",
        "nonunit",
        "missing_axis",
        "saved_q",
        "unknown_side",
    ],
)
def test_malformed_or_ambiguous_capture_rejected(tool, spec, capture, failure):
    if failure == "duplicate_pose":
        capture["poses"].append(copy.deepcopy(capture["poses"][0]))
    elif failure == "boolean_schema":
        capture["schema_version"] = True
    elif failure == "unknown_class":
        capture["evidence_class"] = "physical_test"
    elif failure == "stale_ledger":
        capture["jaw_body_ledger_canonical_sha256"] = "b" * 64
    elif failure == "source":
        capture["original_source_sha256"]["Assembly.FCStd"] = "b" * 64
    elif failure == "wrong_frame":
        capture["coordinate_frame"] = "millimetres"
    elif failure == "nonfinite":
        capture["poses"][0]["sides"]["left"]["driven_tip_m"][0] = math.nan
    elif failure == "nonunit":
        capture["poses"][0]["sides"]["left"]["axis_units"]["driven_base"] = [0, 0, 0.5]
    elif failure == "missing_axis":
        del capture["poses"][0]["sides"]["left"]["axis_units"]["driven_base"]
    elif failure == "saved_q":
        capture["configuration"] = "saved_original"
    elif failure == "unknown_side":
        capture["poses"][0]["sides"]["unknown"] = capture["poses"][0]["sides"]["left"]
    with pytest.raises(ValueError):
        tool.evaluate_capture(spec, capture)


def test_axis_line_check_preserves_axial_stack_unknown(tool, spec, capture):
    capture["poses"][0]["sides"]["left"]["driven_tip_m"][2] += 0.01
    report = tool.evaluate_capture(spec, capture)
    assert report["declared_geometric_predicates_passed"]
    assert report["retention_qualified"] is False
    assert report["contact_qualified"] is False


def test_cli_report_output_and_clean_failures(tool, spec, capture, tmp_path):
    source = tmp_path / "capture.json"
    output = tmp_path / "report.json"
    source.write_text(json.dumps(capture), encoding="utf-8")
    command = [
        sys.executable,
        str(ROOT / "tools/thor_jaw_acceptance.py"),
        "--capture",
        str(source),
        "--output",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert b"\r" not in output.read_bytes()
    assert report["input_evidence_class"] == "synthetic_fixture"
    original = output.read_bytes()
    duplicate = subprocess.run(command, capture_output=True, text=True)
    assert duplicate.returncode == 2
    assert "new output path" in duplicate.stderr
    assert "Traceback" not in duplicate.stderr
    assert output.read_bytes() == original
    source.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    bad = subprocess.run(
        command[:-1] + [str(tmp_path / "bad-report.json")], capture_output=True, text=True
    )
    assert bad.returncode == 2
    assert "duplicate JSON key" in bad.stderr
    assert "Traceback" not in bad.stderr
