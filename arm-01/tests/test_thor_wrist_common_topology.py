"""Exact identity membership and raw debug-retention tests without native CAD."""

from __future__ import annotations

import copy
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/probe_thor_wrist_common_topology.py"


@pytest.fixture
def probe(monkeypatch):
    for flag in (
        "RAFTEL_RUN_FREECAD_AUDIT",
        "RAFTEL_RUN_WRIST_POSE_DESKTOP",
        "RAFTEL_RUN_WRIST_FAILURE_PAIR",
        "RAFTEL_RUN_WRIST_COMMON_TOPOLOGY",
    ):
        monkeypatch.delenv(flag, raising=False)
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        spec = importlib.util.spec_from_file_location("wrist_topology_probe", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(ROOT / "tools"))


class IdentityShape:
    def __init__(self, identity, *, orientation="Forward", location=0):
        self.identity, self.location, self.Orientation = identity, location, orientation

    def isSame(self, other):
        return self.identity == other.identity and self.location == other.location


class Face(IdentityShape):
    def __init__(self, identity, *, orientation="Forward", location=0):
        super().__init__(identity, orientation=orientation, location=location)
        self.Area = 2.0
        self.Surface = type("Plane", (), {})()


class Shell(IdentityShape):
    def __init__(self, identity, faces, closed):
        super().__init__(identity)
        self.Faces, self.closed = faces, closed

    def isClosed(self):
        return self.closed


class Solid(IdentityShape):
    def __init__(self, identity, faces, shells):
        super().__init__(identity)
        self.Faces, self.Shells, self.Volume = faces, shells, 0.1

    def isClosed(self):
        return True


class Common:
    def __init__(self):
        self.Faces = [Face(1), Face(2), Face(3, orientation="Reversed")]
        self.Shells = [Shell(10, self.Faces[:2], True), Shell(11, self.Faces[2:], False)]
        # Distinct Python wrappers and opposite orientation still share topology/location.
        self.Solids = [Solid(20, [Face(1, orientation="Reversed"), Face(2)], [self.Shells[0]])]
        self.Volume, self.ShapeType, self.Orientation = -0.55, "Compound", "Forward"
        self.export_calls = 0

    def isNull(self):
        return False

    def exportBrep(self, filename):
        self.export_calls += 1
        Path(filename).write_bytes(b"synthetic debug BRep bytes; not native geometry\n")


def test_exact_ownership_includes_free_faces_and_shells_without_repair(probe):
    common = Common()
    result = probe.topology_membership(common)
    assert [row["solid_indices"] for row in result["faces"]] == [[1], [1], []]
    assert result["unowned_common_face_indices"] == [3]
    assert result["unowned_common_shell_indices"] == [2]
    assert result["solids"][0]["face_count"] == 2
    assert result["solids"][0]["shell_count"] == 1
    assert result["shells"][0]["is_closed"] is True
    assert result["shells"][1]["is_closed"] is False
    assert result["faces"][2]["orientation"] == "Reversed"
    assert result["negative_aggregate_cause_proven"] is False
    assert common.Volume == -0.55 and common.Solids[0].Volume == 0.1


def test_isSame_uses_location_and_does_not_infer_ownership_from_same_geometry(probe):
    common = Common()
    common.Solids[0].Faces[1] = Face(2, location=99)
    result = probe.topology_membership(common)
    assert result["faces"][1]["solid_indices"] == []
    assert result["unowned_common_face_indices"] == [2, 3]


def test_unavailable_closed_query_stays_unknown(probe):
    assert probe._closed(object()) == {
        "is_closed_evaluated": False,
        "is_closed": None,
        "is_closed_error": "method unavailable",
    }


def test_native_debug_export_occurs_once_and_preserves_bytes(probe, tmp_path):
    common = Common()
    destination = tmp_path / "common.brep"
    record = probe.export_debug_brep(common, destination, tmp_path)
    assert common.export_calls == 1
    assert destination.read_bytes() == b"synthetic debug BRep bytes; not native geometry\n"
    assert record["sha256"] == probe.pair.wrist._sha(destination)
    assert record["native_export_calls"] == 1 and record["diagnostic_only"] is True
    assert record["CAD_document_saved"] is False and record["manufacturing_release"] is False
    with pytest.raises(ValueError, match="new"):
        probe.export_debug_brep(common, destination, tmp_path)
    assert common.export_calls == 1


def test_debug_export_path_escape_is_rejected_before_native_call(probe, tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    common = Common()
    with pytest.raises(ValueError, match="isolated"):
        probe.export_debug_brep(common, tmp_path / "outside.brep", private)
    assert common.export_calls == 0


def _complete_report(probe):
    # Reuse the accepted one-pair contract fixture; this extension must not relax it.
    spec = importlib.util.spec_from_file_location(
        "accepted_pair_fixture", ROOT / "tests/test_thor_wrist_failure_pair.py"
    )
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    report, source = fixtures._complete_report(probe.pair)
    report["validation_class"] = "native_common_topology_membership_debug_BRep_diagnostic"
    report["worker_sha256"] = probe.pair.wrist._sha(SCRIPT)
    report["pair_helper_sha256"] = probe.pair.wrist._sha(Path(probe.pair.__file__))
    common = Common()
    report["common"] = probe.pair.shape_metrics(common)
    report["common"].update(validity_evaluated=True, valid=True)
    report["topology"] = probe.topology_membership(common)
    report["debug_BRep"] = {
        "path": "/synthetic/isolated/common-debug.brep",
        "exported_object": "unaltered Boolean common",
        "sha256": "a" * 64,
        "bytes": 100,
        "native_export_calls": 1,
        "diagnostic_only": True,
        "CAD_document_saved": False,
        "manufacturing_release": False,
    }
    return report, source


def test_identity_duplicate_occurrences_do_not_require_raw_count_equal_unique_members(probe):
    report, source = _complete_report(probe)
    common = Common()
    common.Faces.append(Face(1, orientation="Reversed"))
    report["common"] = probe.pair.shape_metrics(common)
    report["common"].update(validity_evaluated=True, valid=True)
    report["topology"] = probe.topology_membership(common)
    assert report["topology"]["solids"][0]["face_count"] == 2
    assert report["topology"]["solids"][0]["common_face_indices"] == [1, 2, 4]
    assert probe.capture_is_complete(report, expected_source_sha256=source)


@pytest.mark.parametrize(
    "corruption",
    [
        "solid_face_count",
        "solid_shell_count",
        "shell_face_count",
        "transitivity",
        "export_path",
        "export_object",
        "export_bytes",
        "method",
    ],
)
def test_occurrence_hierarchy_and_export_contract_are_not_weakened(probe, corruption):
    report, source = _complete_report(probe)
    topology = report["topology"]
    if corruption == "solid_face_count":
        topology["solids"][0]["face_count"] = 999
    elif corruption == "solid_shell_count":
        topology["solids"][0]["shell_count"] = 999
    elif corruption == "shell_face_count":
        topology["shells"][0]["face_count"] = 999
    elif corruption == "transitivity":
        topology["faces"][0]["solid_indices"] = []
        topology["faces"][0]["owned_by_any_solid"] = False
        topology["unowned_common_face_indices"] = [1, 3]
        solid = topology["solids"][0]
        solid["common_face_indices"] = [2]
        solid["face_count"] = 1
        solid["face_occurrences"] = [{"local_face_index": 1, "common_face_indices": [2]}]
    elif corruption == "export_path":
        report["debug_BRep"]["path"] = "/outside/common-debug.brep"
    elif corruption == "export_object":
        report["debug_BRep"]["exported_object"] = "repaired shape"
    elif corruption == "export_bytes":
        report["debug_BRep"]["bytes"] = 129 * 1024**2
    elif corruption == "method":
        topology["membership_method"] = "nearest geometric proximity"
    assert not probe.capture_is_complete(report, expected_source_sha256=source)


def test_extended_contract_preserves_negative_result_and_no_cause_claim(probe):
    report, source = _complete_report(probe)
    original = copy.deepcopy(report)
    assert probe.capture_is_complete(report, expected_source_sha256=source)
    assert report == original
    assert report["common"]["signed_volume_mm3"] < 0
    assert report["topology"]["negative_aggregate_cause_proven"] is False


@pytest.mark.parametrize(
    "corruption",
    [
        "source",
        "worker",
        "pair_helper",
        "membership",
        "reciprocal",
        "count",
        "debug",
        "cause",
        "saved_input",
    ],
)
def test_extended_guard_rejects_identity_membership_and_export_tampering(probe, corruption):
    report, source = _complete_report(probe)
    if corruption == "source":
        report["source_revision"] = "wrong"
    elif corruption == "worker":
        report["worker_sha256"] = "b" * 64
    elif corruption == "pair_helper":
        report["pair_helper_sha256"] = "b" * 64
    elif corruption == "membership":
        report["topology"]["unowned_common_face_indices"] = []
    elif corruption == "reciprocal":
        report["topology"]["solids"][0]["common_face_indices"] = [1]
    elif corruption == "count":
        report["topology"]["faces"].pop()
    elif corruption == "debug":
        report["debug_BRep"]["manufacturing_release"] = True
    elif corruption == "cause":
        report["topology"]["negative_aggregate_cause_proven"] = True
    elif corruption == "saved_input":
        report["inputs"][0]["saved"]["valid"] = False
    assert not probe.capture_is_complete(report, expected_source_sha256=source)


@pytest.mark.parametrize(
    "flag",
    ["RAFTEL_RUN_FREECAD_AUDIT", "RAFTEL_RUN_WRIST_POSE_DESKTOP", "RAFTEL_RUN_WRIST_FAILURE_PAIR"],
)
def test_conflicting_workers_cannot_execute_during_import(probe, flag):
    env = os.environ.copy()
    env[flag] = "1"
    result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "conflicting native worker flag" in result.stderr
    assert "No module named 'FreeCAD'" not in result.stderr


def test_default_entry_point_never_launches(probe):
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode != 0 and "no process launched" in result.stderr


def test_actual_frozen_topology_has_no_unowned_faces_or_shells(probe):
    import json

    report = json.loads(
        (ROOT / "hardware/cad/thor-wrist-common-topology-v1.json").read_text(encoding="utf-8")
    )
    pins = report["launch_context"]["snapshot_sha256"]
    assert probe.capture_is_complete(
        report,
        expected_source_sha256=report["source_sha256_before"],
        expected_worker_sha256=pins["probe_thor_wrist_common_topology.py"],
        expected_pair_helper_sha256=pins["probe_thor_wrist_failure_pair.py"],
        expected_wrist_helper_sha256=pins["probe_thor_wrist_pose_desktop.py"],
        expected_audit_helper_sha256=pins["audit_freecad_assembly.py"],
    )
    topology = report["topology"]
    assert topology["unowned_common_face_indices"] == []
    assert topology["unowned_common_shell_indices"] == []
    assert [solid["face_count"] for solid in topology["solids"]] == [3, 4, 4]
    assert [solid["common_face_indices"] for solid in topology["solids"]] == [
        [1, 2, 3],
        [4, 5, 6, 7],
        [8, 9, 10, 11],
    ]
    assert all(solid["is_closed"] is True for solid in topology["solids"])
    assert all(shell["is_closed"] is True for shell in topology["shells"])
    assert all(len(face["solid_indices"]) == 1 for face in topology["faces"])
    assert report["common"]["signed_volume_mm3"] == pytest.approx(-0.5552516265803887, abs=1e-14)
    assert topology["negative_aggregate_cause_proven"] is False
    assert report["debug_BRep"]["bytes"] == 900661
    assert (
        report["debug_BRep"]["sha256"]
        == "f6a8a4f48a7c13f75fbde9a6e57aefb26fce268fc52d43278c589d934fea0678"
    )
    assert report["geometric_intersection_accepted"] is False
