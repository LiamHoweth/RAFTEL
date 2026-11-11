"""Pure guards/completion contracts; these tests do not run a native CAD process."""

from __future__ import annotations

import copy
import math
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/probe_thor_wrist_pose_desktop.py"


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.delenv("RAFTEL_RUN_WRIST_POSE_DESKTOP", raising=False)
    return runpy.run_path(str(SCRIPT))


def test_import_and_default_script_never_launch_a_native_process(probe):
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "no process launched" in result.stderr
    assert len(probe["pose_plan"]()) == 3


def test_three_pose_source_and_ideal_coordinates_are_explicit(probe):
    plan = probe["pose_plan"]()
    assert [(p["q5_deg"], p["q6_deg"]) for p in plan] == [(0, 0), (20, 15), (-20, -15)]
    angle = probe["rotor_angle_deg"]
    assert angle(20, 15, -1, 1) == 50
    assert angle(20, 15, 1, 1) == -10
    assert angle(-20, -15, -1, 1) == -50
    assert angle(-20, -15, 1, 1) == 10
    assert angle(20, 15, -1, -1) == -10
    # A common pure fold carries plate and both side shafts together.
    assert angle(20, 0, -1, 1) == angle(20, 0, 1, 1) == 20


@pytest.mark.parametrize(
    "arguments",
    [
        (True, 0, -1, 1),
        (math.nan, 0, -1, 1),
        (0, math.inf, -1, 1),
        (91, 0, -1, 1),
        (0, 0, True, 1),
        (0, 0, -1, False),
        (0, 0, 0, 1),
    ],
)
def test_invalid_or_unbounded_rotation_parameters_rejected(probe, arguments):
    with pytest.raises(ValueError):
        probe["rotor_angle_deg"](*arguments)


def test_numeric_fold_comparison_never_qualifies_physical_gear_contact(probe):
    assert probe["compare_rigid_fold"](0.2, 0.2000001)["passed"]
    assert not probe["compare_rigid_fold"](0.2, 0.4)["passed"]
    with pytest.raises(ValueError):
        probe["compare_rigid_fold"](-0.1, 0.1)


@pytest.mark.parametrize(
    "values", [(10, 9, 10), (0, 11, 10), (0, 1, 601), (0, 1, 0), (0, math.inf, 10)]
)
def test_time_budget_is_bounded(probe, values):
    with pytest.raises(ValueError):
        probe["within_budget"](*values)


def test_budget_boundary_is_inclusive(probe):
    assert probe["within_budget"](10, 610) is None


def test_conflicting_generic_flag_is_rejected_before_helper_or_native_import(probe, monkeypatch):
    monkeypatch.setenv("RAFTEL_RUN_FREECAD_AUDIT", "1")
    called = []
    monkeypatch.setattr(
        probe["native_probe"].__globals__["runpy"], "run_path", lambda path: called.append(path)
    )
    with pytest.raises(ValueError, match="conflicting generic"):
        probe["native_probe"](Path("missing"), Path("missing.json"), Path("missing"))
    assert called == []


def test_existing_outputs_and_escape_paths_rejected_before_native_import(probe, tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "Assembly.FCStd"
    source.write_bytes(b"synthetic source")
    existing = tmp_path / "existing.json"
    existing.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="new JSON"):
        probe["validate_inputs"](source, existing, tmp_path)
    assert existing.read_text(encoding="utf-8") == "preserve"
    with pytest.raises(ValueError, match="isolated run root"):
        probe["validate_inputs"](source, tmp_path / "new.json", source_dir)


def test_source_pin_and_disk_reserve_checks_are_deterministic(probe, tmp_path, monkeypatch):
    source = tmp_path / "Assembly.FCStd"
    source.write_bytes(b"synthetic")
    globals_ = probe["validate_inputs"].__globals__
    monkeypatch.setattr(
        globals_["shutil"], "disk_usage", lambda path: SimpleNamespace(free=49 * 1024**3)
    )
    with pytest.raises(ValueError, match="50 GiB"):
        probe["validate_inputs"](source, tmp_path / "new.json", tmp_path)
    monkeypatch.setattr(
        globals_["shutil"], "disk_usage", lambda path: SimpleNamespace(free=64 * 1024**3)
    )
    with pytest.raises(ValueError, match="source hash"):
        probe["validate_inputs"](source, tmp_path / "new.json", tmp_path)


def _complete_report(probe):
    pairs = []
    folds = []
    for pose in probe["pose_plan"]():
        for sign in pose["signs"]:
            for side in (-1, 1):
                pairs.append(
                    {
                        "pose_id": pose["pose_id"],
                        "candidate_s": sign,
                        "side_y": side,
                        "q5_deg": pose["q5_deg"],
                        "q6_deg": pose["q6_deg"],
                        "side_rotation_common_positive_y_deg": probe["rotor_angle_deg"](
                            pose["q5_deg"], pose["q6_deg"], side, sign
                        ),
                        "configuration": "saved_original"
                        if pose["q5_deg"] == pose["q6_deg"] == 0
                        else "declared_ideal_rigid_transform",
                        "distance_status": "complete",
                        "minimum_distance_mm": 0.0,
                        "intersection_volume_mm3": 0.2,
                        "intersection_solid_count": 1,
                    }
                )
                if sign == 1 and pose["q5_deg"] != 0:
                    folds.append(
                        {
                            "pose_id": pose["pose_id"],
                            "side_y": side,
                            "unfolded_intersection_mm3": 0.2,
                            "folded_intersection_mm3": 0.2,
                            **probe["compare_rigid_fold"](0.2, 0.2),
                        }
                    )
    source_hashes = {
        **dict(probe["PINNED"]),
        **{f"synthetic-{i}.FCStd": "a" * 64 for i in range(53)},
    }
    worker = Path(probe["__file__"])
    return {
        "schema_version": 1,
        "validation_class": "native_saved_BRep_and_declared_rigid_pose_interference_diagnostic",
        "source_revision": probe["SOURCE_REVISION"],
        "coordinate_frame": "native_CAD_world_mm",
        "source_geometry_mode": "saved cached source BReps; no feature-history rebuild",
        "freecad_version": [
            "1",
            "1",
            "4",
            "synthetic",
            "synthetic",
            "synthetic",
            "synthetic",
            "4fd3bf320d9566a27e60069fc8387448aaa3a094",
        ],
        "worker_sha256": probe["_sha"](worker),
        "audit_helper_sha256": probe["_sha"](worker.with_name("audit_freecad_assembly.py")),
        "pose_plan": list(probe["pose_plan"]()),
        "audit_status": "complete",
        "errors": [],
        "source_bytes_unchanged": True,
        "selected_document_placements_unchanged": True,
        "source_sha256_before": dict(source_hashes),
        "source_sha256_after": dict(source_hashes),
        "runtime_isolation": {
            "requested": True,
            "verified": True,
            "root": "/synthetic/isolated",
            "actual_paths": {
                key: "/synthetic/isolated/" + key
                for key in (
                    "UserParameter",
                    "SystemParameter",
                    "UserHomePath",
                    "UserAppData",
                    "AppTempPath",
                )
            },
        },
        "boolean_operations_executed": 14,
        "objects": [
            {
                "object_reference": "AssemblyArt56::" + name,
                "source_shape_valid": True,
                "solid_count": 1,
                "volume_mm3": 1,
            }
            for name in probe["NAMES"]
        ],
        "pose_pair_diagnostics": pairs,
        "rigid_fold_invariance": folds,
        "feature_history_recomputed": False,
        "constraint_kinematics_solved": False,
        "exact_conjugate_mesh_qualified": False,
        "physical_calibration_qualified": False,
        "source_document_saved": False,
        "jaw_loop_closure_evaluated": False,
        "contact_force_or_retention_qualified": False,
        "fabrication_released": False,
    }


@pytest.mark.parametrize(
    "field",
    [
        "errors",
        "source_bytes_unchanged",
        "selected_document_placements_unchanged",
        "objects",
        "pose_pair_diagnostics",
        "rigid_fold_invariance",
        "feature_history_recomputed",
        "constraint_kinematics_solved",
        "exact_conjugate_mesh_qualified",
        "physical_calibration_qualified",
    ],
)
def test_completion_contract_rejects_partial_results_and_acceptance_upgrades(probe, field):
    report = _complete_report(probe)
    assert probe["report_is_complete"](report)
    broken = copy.deepcopy(report)
    if isinstance(broken[field], list):
        broken[field] = ["incomplete"]
    else:
        broken[field] = not broken[field]
    assert not probe["report_is_complete"](broken)


@pytest.mark.parametrize(
    "corruption",
    [
        "none",
        "objects_none",
        "pairs_none",
        "schema_bool",
        "class",
        "revision",
        "frame",
        "runtime",
        "worker_pin",
        "helper_pin",
        "plan_bool",
        "plan_sign_bool",
        "pair_bool",
        "pair_configuration",
        "metric_nan",
        "isolation_escape",
        "native_op_count",
    ],
)
def test_malformed_and_mismatched_completion_inputs_return_false(probe, corruption):
    report = _complete_report(probe)
    if corruption == "none":
        report = None
    elif corruption == "objects_none":
        report["objects"] = None
    elif corruption == "pairs_none":
        report["pose_pair_diagnostics"] = None
    elif corruption == "schema_bool":
        report["schema_version"] = True
    elif corruption == "class":
        report["validation_class"] = "physical"
    elif corruption == "revision":
        report["source_revision"] = "wrong"
    elif corruption == "frame":
        report["coordinate_frame"] = "ROS"
    elif corruption == "runtime":
        report["freecad_version"][2] = "5"
    elif corruption == "worker_pin":
        report["worker_sha256"] = "f" * 64
    elif corruption == "helper_pin":
        report["audit_helper_sha256"] = "f" * 64
    elif corruption == "plan_bool":
        report["pose_plan"][0]["q5_deg"] = False
    elif corruption == "plan_sign_bool":
        report["pose_plan"][0]["signs"] = (True,)
    elif corruption == "pair_bool":
        report["pose_pair_diagnostics"][0]["q5_deg"] = False
    elif corruption == "pair_configuration":
        report["pose_pair_diagnostics"][2]["configuration"] = "saved_original"
    elif corruption == "metric_nan":
        report["pose_pair_diagnostics"][0]["intersection_volume_mm3"] = math.nan
    elif corruption == "isolation_escape":
        report["runtime_isolation"]["actual_paths"]["UserAppData"] = "/synthetic/isolated/../other"
    elif corruption == "native_op_count":
        report["boolean_operations_executed"] = True
    assert probe["report_is_complete"](report) is False


def test_retained_snapshot_identity_requires_its_explicit_pin(probe):
    report = _complete_report(probe)
    report["worker_sha256"] = "f" * 64
    assert not probe["report_is_complete"](report)
    assert probe["report_is_complete"](report, expected_worker_sha256="f" * 64)


def test_windows_isolation_paths_are_checked_portably(probe):
    report = _complete_report(probe)
    report["runtime_isolation"]["root"] = "C:\\synthetic\\isolated"
    paths = report["runtime_isolation"]["actual_paths"]
    for key in paths:
        paths[key] = "C:\\synthetic\\isolated\\" + key
    assert probe["report_is_complete"](report)
    paths["UserAppData"] = "C:\\synthetic\\isolated\\..\\outside"
    assert not probe["report_is_complete"](report)


def test_frozen_actual_partial_capture_is_not_completed_or_qualified(probe):
    import hashlib
    import json

    cad = ROOT / "hardware/cad"
    receipt = json.loads((cad / "thor-wrist-pose-desktop.json").read_text(encoding="utf-8"))
    raw = (cad / receipt["capture"]["path"]).read_bytes()
    runner_raw = (cad / receipt["runner"]["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == receipt["capture"]["sha256"]
    assert hashlib.sha256(runner_raw).hexdigest() == receipt["runner"]["sha256"]
    capture, runner = json.loads(raw), json.loads(runner_raw)
    assert capture["audit_status"] == "failed"
    assert not probe["report_is_complete"](
        capture,
        expected_worker_sha256=capture["worker_sha256"],
        expected_helper_sha256=capture["audit_helper_sha256"],
    )
    assert len(capture["pose_pair_diagnostics"]) == 7
    assert len(capture["rigid_fold_invariance"]) == 3
    assert capture["boolean_operations_executed"] == 11
    assert capture["source_sha256_before"] == capture["source_sha256_after"]
    assert runner["original_source_sha256_before"] == runner["original_source_sha256_after"]
    assert receipt["failure"]["signed_volume_mm3"] is None
    assert receipt["failure"]["intermediate_topology_captured"] is False
    assert receipt["native_worker_completed"] is False
    assert receipt["process_returncode"] == 0
    assert receipt["exact_conjugate_mesh_qualified"] is False
