"""Pure signed-result/guard tests; no native kernel or process is run."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/probe_thor_wrist_failure_pair.py"


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.delenv("RAFTEL_RUN_WRIST_FAILURE_PAIR", raising=False)
    monkeypatch.delenv("RAFTEL_RUN_WRIST_POSE_DESKTOP", raising=False)
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        spec = importlib.util.spec_from_file_location("wrist_failure_pair", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(ROOT / "tools"))


def test_default_entry_point_never_starts_native_process(probe):
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "no process launched" in result.stderr
    assert probe.POSE == {
        "q5_deg": -20,
        "q6_deg": -15,
        "candidate_s": 1,
        "side_y": 1,
        "rotor_deg": 10,
    }


@pytest.mark.parametrize("flag", ["RAFTEL_RUN_FREECAD_AUDIT", "RAFTEL_RUN_WRIST_POSE_DESKTOP"])
def test_conflicting_flags_fail_before_helper_loading(probe, monkeypatch, flag):
    called = []
    monkeypatch.setattr(probe.runpy, "run_path", lambda path: called.append(path))
    monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match="conflicting native"):
        probe.native_probe(Path("missing"), Path("missing.json"), Path("missing"))
    assert called == []


def test_wrong_wrist_flag_cannot_autoexecute_during_module_import(probe):
    env = os.environ.copy()
    env["RAFTEL_RUN_WRIST_POSE_DESKTOP"] = "1"
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env)
    assert result.returncode != 0
    assert "conflicting native worker flag" in result.stderr
    assert "No module named 'FreeCAD'" not in result.stderr


def test_negative_signed_volume_and_orientation_are_preserved_before_validity(probe):
    class Shape:
        Volume = -0.125
        ShapeType = "Compound"
        Orientation = "Forward"
        Solids = [
            SimpleNamespace(Volume=0.1, Orientation="Forward"),
            SimpleNamespace(Volume=-0.225, Orientation="Reversed"),
        ]
        Shells = [object(), object()]
        Faces = [object(), object(), object()]

        def isNull(self):
            return False

        def isValid(self):
            raise AssertionError("validity must remain a separately checkpointed native operation")

    metrics = probe.shape_metrics(Shape())
    assert metrics["signed_volume_mm3"] == -0.125
    assert metrics["solid_count"] == 2
    assert metrics["orientation"] == "Forward"
    assert metrics["solids"] == [
        {"signed_volume_mm3": 0.1, "orientation": "Forward"},
        {"signed_volume_mm3": -0.225, "orientation": "Reversed"},
    ]
    assert metrics["validity_evaluated"] is False and metrics["valid"] is None
    assert probe.signed_result_classification(-0.125) == "negative_signed_volume_reproduced"


@pytest.mark.parametrize("volume", [0, 1e-12, 12])
def test_nonnegative_followup_does_not_rewrite_original_failure(probe, volume):
    assert probe.signed_result_classification(volume) == "negative_signed_volume_not_reproduced"


@pytest.mark.parametrize("volume", [math.nan, math.inf, True, "-1"])
def test_invalid_signed_metrics_fail_closed(probe, volume):
    with pytest.raises(ValueError):
        probe.signed_result_classification(volume)


@pytest.mark.parametrize(
    "report", [None, {}, {"schema_version": True}, {"common": None}, "complete"]
)
def test_partial_or_malformed_capture_is_not_complete(probe, report):
    assert probe.capture_is_complete(report) is False


def _complete_report(probe):
    baseline = json.loads(
        (ROOT / "hardware/cad/thor-baseline-inspection.json").read_text(encoding="utf-8")
    )
    source = {Path(row["path"]).name: row["sha256"] for row in baseline["files"]}
    assert len(source) == 57

    def metrics(volume=10.0, valid=True, orientation="Forward"):
        return {
            "signed_volume_mm3": volume,
            "shape_type": "Solid",
            "orientation": orientation,
            "null_shape": False,
            "solid_count": 1,
            "shell_count": 1,
            "face_count": 6,
            "solids": [{"signed_volume_mm3": volume, "orientation": orientation}],
            "validity_evaluated": True,
            "valid": valid,
        }

    report = {
        "schema_version": 1,
        "validation_class": "native_single_Boolean_signed_result_diagnostic",
        "source_revision": probe.wrist.SOURCE_REVISION,
        "coordinate_frame": "native_CAD_world_mm",
        "source_geometry_mode": "saved cached BReps and declared rigid copied-shape pose",
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
        "worker_sha256": probe.wrist._sha(SCRIPT),
        "wrist_helper_sha256": probe.wrist._sha(Path(probe.wrist.__file__)),
        "audit_helper_sha256": probe.wrist._sha(SCRIPT.with_name("audit_freecad_assembly.py")),
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
        "audit_status": "complete",
        "errors": [],
        "pose": dict(probe.POSE),
        "source_bytes_unchanged": True,
        "source_sha256_before": dict(source),
        "source_sha256_after": dict(source),
        "boolean_operations_executed": 1,
        "inputs": [
            {
                "object_reference": "AssemblyArt56::" + probe.wrist.NAMES[index],
                "saved_restore_state": ["Up-to-date"],
                "saved": metrics(),
                "posed": metrics(),
            }
            for index in (0, 2)
        ],
        "common": metrics(-0.125, False, "Reversed"),
        "diagnostic_outcome": "negative_signed_volume_reproduced",
        "open_document_count_before": 0,
        "open_document_count_after_close": 0,
        **{
            key: False
            for key in (
                "absolute_volume_substituted",
                "shape_reversed_or_healed",
                "source_saved",
                "feature_history_recomputed",
                "constraint_kinematics_solved",
                "geometric_intersection_accepted",
                "exact_conjugate_mesh_qualified",
                "physical_calibration_qualified",
                "fabrication_released",
            )
        },
    }
    return report, source


def test_negative_validity_result_can_be_fully_recorded_without_material_acceptance(probe):
    report, source = _complete_report(probe)
    assert probe.capture_is_complete(report, expected_source_sha256=source)
    assert not probe.capture_is_complete(report)  # Unbound source claims cannot pass.
    assert report["common"]["signed_volume_mm3"] < 0
    assert report["geometric_intersection_accepted"] is False
    assert report["common"]["valid"] is False


@pytest.mark.parametrize(
    "corruption",
    [
        "source_names",
        "source_pin",
        "schema",
        "revision",
        "frame",
        "class",
        "runtime",
        "worker_pin",
        "helper_pin",
        "saved_missing",
        "saved_invalid",
        "posed_negative",
        "common_orientation",
        "solid_records",
        "count_bool",
        "pose_bool",
        "object_reference",
        "operand_order",
        "open_docs_bool",
        "open_docs",
        "isolation_escape",
        "common_validity_missing",
        "common_nan",
        "accepted_material",
    ],
)
def test_identity_topology_and_coverage_tampering_are_rejected(probe, corruption):
    report, source = _complete_report(probe)
    if corruption == "source_names":
        source = {str(i): "a" * 64 for i in range(57)}
        report["source_sha256_before"] = report["source_sha256_after"] = source
    elif corruption == "source_pin":
        report["source_sha256_after"]["Assembly.FCStd"] = "a" * 64
    elif corruption == "schema":
        report["schema_version"] = True
    elif corruption == "revision":
        report["source_revision"] = "wrong"
    elif corruption == "frame":
        report["coordinate_frame"] = "ROS"
    elif corruption == "class":
        report["validation_class"] = "physical"
    elif corruption == "runtime":
        report["freecad_version"][2] = "5"
    elif corruption == "worker_pin":
        report["worker_sha256"] = "b" * 64
    elif corruption == "helper_pin":
        report["wrist_helper_sha256"] = "b" * 64
    elif corruption == "saved_missing":
        del report["inputs"][0]["saved"]
    elif corruption == "saved_invalid":
        report["inputs"][0]["saved"]["valid"] = False
    elif corruption == "posed_negative":
        report["inputs"][0]["posed"]["signed_volume_mm3"] = -1
    elif corruption == "common_orientation":
        report["common"]["orientation"] = "unknown"
    elif corruption == "solid_records":
        report["common"]["solids"] = []
    elif corruption == "count_bool":
        report["common"]["solid_count"] = True
    elif corruption == "pose_bool":
        report["pose"]["candidate_s"] = True
    elif corruption == "object_reference":
        report["inputs"][0]["object_reference"] = "wrong"
    elif corruption == "operand_order":
        report["inputs"].reverse()
    elif corruption == "open_docs_bool":
        report["open_document_count_before"] = False
    elif corruption == "open_docs":
        report["open_document_count_after_close"] = 1
    elif corruption == "isolation_escape":
        report["runtime_isolation"]["actual_paths"]["UserHomePath"] = "/other"
    elif corruption == "common_validity_missing":
        report["common"]["validity_evaluated"] = False
    elif corruption == "common_nan":
        report["common"]["signed_volume_mm3"] = math.nan
    elif corruption == "accepted_material":
        report["geometric_intersection_accepted"] = True
    assert not probe.capture_is_complete(report, expected_source_sha256=source)


def test_retained_snapshot_needs_independent_explicit_pin(probe):
    report, source = _complete_report(probe)
    report["worker_sha256"] = "b" * 64
    assert not probe.capture_is_complete(report, expected_source_sha256=source)
    assert probe.capture_is_complete(
        report, expected_source_sha256=source, expected_worker_sha256="b" * 64
    )


def test_checker_does_not_mutate_negative_capture(probe):
    report, source = _complete_report(probe)
    original = copy.deepcopy(report)
    probe.capture_is_complete(report, expected_source_sha256=source)
    assert report == original


def test_frozen_actual_capture_preserves_aggregate_and_solid_discrepancy(probe):
    import hashlib

    cad = ROOT / "hardware/cad"
    receipt = json.loads((cad / "thor-wrist-failure-pair.json").read_text(encoding="utf-8"))
    capture_bytes = (cad / receipt["capture"]["path"]).read_bytes()
    runner_bytes = (cad / receipt["runner"]["path"]).read_bytes()
    assert hashlib.sha256(capture_bytes).hexdigest() == receipt["capture"]["sha256"]
    assert hashlib.sha256(runner_bytes).hexdigest() == receipt["runner"]["sha256"]
    capture, runner = json.loads(capture_bytes), json.loads(runner_bytes)
    pins = runner["worker_snapshots_sha256"]
    assert probe.capture_is_complete(
        capture,
        expected_source_sha256=runner["source_sha256_before"],
        expected_worker_sha256=pins["probe_thor_wrist_failure_pair.py"],
        expected_wrist_helper_sha256=pins["probe_thor_wrist_pose_desktop.py"],
        expected_audit_helper_sha256=pins["audit_freecad_assembly.py"],
    )
    common = capture["common"]
    assert common["signed_volume_mm3"] == pytest.approx(-0.5552516265803887, abs=1e-14)
    assert common["valid"] is True and common["orientation"] == "Forward"
    assert common["solid_count"] == 3
    assert common["face_count"] == 11 and common["shell_count"] == 3
    assert all(
        row["signed_volume_mm3"] > 0 and row["orientation"] == "Forward" for row in common["solids"]
    )
    total = math.fsum(row["signed_volume_mm3"] for row in common["solids"])
    assert total == pytest.approx(0.10630907314212505, abs=1e-15)
    assert receipt["derived_arithmetic"]["sum_reported_solid_signed_volumes_mm3"] == total
    assert receipt["geometric_intersection_accepted"] is False
    assert receipt["standalone_face_or_shell_membership_captured"] is False
    assert receipt["raw_common_BRep_exported"] is False
    assert runner["all_source_bytes_unchanged"] is True
