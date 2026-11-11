"""Host guards and frame-direction checks; no FreeCAD execution in these tests."""

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

from raftel_arm01.kinematics import thor_model

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pose_probe", ROOT / "tools/probe_thor_pose_frames_desktop.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def contract():
    baseline = json.loads((ROOT / "hardware/cad/thor-baseline-inspection.json").read_text())
    pins = {Path(row["path"]).name: row["sha256"] for row in baseline["files"]}
    pins["Art1Body.fcstd"] = probe.STATIC_ART1_SHA256
    poses = []
    for name, q in probe.POSES:
        frames, target = thor_model.chain(q)
        expected = [list(row) for row in target]
        for i in range(3):
            expected[i][3] -= expected[i][2] * 0.0135
        poses.append(
            {
                "name": name,
                "joint_angles_rad": list(q),
                "expected_fold_frame_base_link_m": expected,
                "expected_joint_axes": [
                    {
                        "name": frame.name,
                        "origin_m": list(frame.origin_m),
                        "axis_unit": list(frame.axis_unit),
                    }
                    for frame in frames
                ],
            }
        )
    return {
        "schema_version": 1,
        "evidence_class": "limited_existing_native_assembly_pose_request",
        "source_contract": {
            "source_sha256": pins,
            "source_file_count": 57,
            "empty_saved_variables_custom_properties": [],
        },
        "cad_upstream_revision": probe.CAD_REVISION,
        "ros_revision": probe.ROS_REVISION,
        "source_xacro_sha256": probe.XACRO_SHA256,
        "fold_source_joint6_translation_m": 0.0135,
        "poses": poses,
        "q5_q6_fixed_zero": True,
        "physical_calibration_or_TCP_validation": False,
    }


def test_native_to_source_rotation_and_mm_conversion_have_explicit_direction():
    assert probe.native_vector_to_ros([1, 2, 3]) == [2, -1, 3]
    native = [[0, -1, 0, 100], [1, 0, 0, 200], [0, 0, 1, 556], [0, 0, 0, 1]]
    assert probe.native_pose_mm_to_ros_m(native) == [
        [1, 0, 0, 0.2],
        [0, 1, 0, -0.1],
        [0, 0, 1, 0.556],
        [0, 0, 0, 1],
    ]


def test_full_orientation_catches_ambiguity_hidden_by_unsigned_axis_lines():
    identity = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    rotated = [[0, -1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    assert probe.pose_residual(rotated, identity)["orientation_error_rad"] == pytest.approx(
        math.pi / 2
    )
    assert probe.pose_residual(rotated, identity)["position_error_m"] == 0
    reflected = copy.deepcopy(identity)
    reflected[0][0] = -1
    with pytest.raises(ValueError, match="proper orthonormal"):
        probe.pose_residual(reflected, identity)


def test_axis_line_checks_allow_along_axis_origins_but_not_perpendicular_offsets():
    along = probe.axis_residual([0, 0, 0.5775], [0, 0, -1], [0, 0, 0.5695], [0, 0, 1])
    assert along["point_to_expected_axis_line_m"] == 0
    assert along["unsigned_direction_error"] == 0
    assert along["signed_axis_dot_for_diagnostics"] == -1
    aside = probe.axis_residual([0.008, 0, 0.5775], [0, 0, 1], [0, 0, 0.5695], [0, 0, 1])
    assert aside["point_to_expected_axis_line_m"] == pytest.approx(0.008)


def test_pose_contract_covers_zero_plus_three_cases_and_source_fold_translation():
    data = contract()
    before = copy.deepcopy(data)
    probe.validate_contract(data)
    assert data == before
    assert data["poses"][0]["expected_fold_frame_base_link_m"][2][3] == pytest.approx(0.556)
    assert all(row["joint_angles_rad"][4:] == [0, 0] for row in data["poses"])
    assert [row[3] for row in probe.ACTUATION] == [(0, 0, 1), (0, 0, 1), (0, 1, 0), (0, 0, 1)]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.update(schema_version=True),
        lambda data: data.update(source_xacro_sha256="0" * 64),
        lambda data: data.update(fold_source_joint6_translation_m=0.0215),
        lambda data: data["source_contract"]["source_sha256"].update(Art1Body_fcstd="0" * 64),
        lambda data: data["source_contract"]["source_sha256"].update({"Art1Body.fcstd": "0" * 64}),
        lambda data: data["source_contract"].update(empty_saved_variables_custom_properties=["q1"]),
        lambda data: data["poses"].pop(0),
        lambda data: data["poses"][1]["joint_angles_rad"].__setitem__(4, 0.1),
        lambda data: data["poses"][1]["expected_fold_frame_base_link_m"][0].__setitem__(0, -1),
        lambda data: data.update(physical_calibration_or_TCP_validation=True),
    ],
)
def test_incomplete_wrong_source_or_expanded_scope_rejected(mutate):
    data = contract()
    mutate(data)
    with pytest.raises(ValueError):
        probe.validate_contract(data)


def test_native_capture_requires_explicit_optin_before_import_or_files(monkeypatch):
    monkeypatch.delenv(probe.FLAG, raising=False)
    with pytest.raises(ValueError, match="opt-in"):
        probe.native_capture()


def test_failed_fresh_process_guard_preserves_preexisting_documents():
    documents = {"OwnerUnsaved": object(), "NewlyRestored": object()}
    closed = []

    def close(name):
        closed.append(name)
        documents.pop(name)

    app = SimpleNamespace(listDocuments=lambda: documents.copy(), closeDocument=close)
    remaining = probe.close_created_documents(app, {"OwnerUnsaved"})
    assert remaining == {"OwnerUnsaved"}
    assert closed == ["NewlyRestored"]
    assert "OwnerUnsaved" in documents


def test_pose_loader_rejects_inherited_generic_entry_before_helper_execution(tmp_path, monkeypatch):
    sentinel = tmp_path / "must-not-be-written"
    helper = tmp_path / "audit-helper.py"
    helper.write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n")
    expected = hashlib.sha256(helper.read_bytes()).hexdigest()
    monkeypatch.setenv("RAFTEL_RUN_FREECAD_AUDIT", "1")
    with pytest.raises(ValueError, match="generic audit entry flag"):
        probe._load_helper(helper, expected)
    assert not sentinel.exists()


def test_state_summary_keeps_repeated_object_names_document_qualified():
    states = [
        {
            "document": name,
            "objects": [{"name": "Body", "type": "PartDesign::Body", "state": ["Touched"]}],
        }
        for name in ("First", "Second")
    ]
    summary = probe._summary(states)
    assert summary["documents"] == summary["objects"] == 2
    assert {row["document"] for row in summary["non_up_to_date"]} == {"First", "Second"}
    assert not summary["invalid_or_error"]


def test_retained_actual_native_pose_capture_preserves_scope_and_replays_references():
    report = json.loads((ROOT / "hardware/cad/thor-native-pose-frames.json").read_text())
    assert report["status"] == "complete_limited_native_pose_frames"
    assert report["freecad_version"][:3] == ["1", "1", "4"]
    assert report["open_document_count_before"] == report["open_document_count_after_close"] == 0
    assert report["preexisting_documents_preserved"]
    assert report["q5_q6_fixed_zero"]
    assert not report["physical_sign_zero_limit_contact_or_TCP_calibration"]
    assert not report["forced_feature_history_rebuild"] and not report["cad_documents_saved"]
    probe.validate_contract(report["request"])
    assert report["source_copy_bytes_unchanged"]
    assert report["source_copy_sha256_before"] == report["source_copy_sha256_after"]
    assert len(report["source_copy_sha256_before"]) == 57
    for key, actual in report["runtime_isolation"]["actual_paths"].items():
        assert PureWindowsPath(actual) == PureWindowsPath(report["expected_runtime_paths"][key])
    assert len(report["poses"]) == 4
    zero_marker = report["poses"][0]["link_shape_marker"]["raw_shape_first_vertex_mm"]
    for pose, requested in zip(report["poses"], report["request"]["poses"], strict=True):
        assert pose["limited_pose_checks_passed"] and pose["expressions_preserved"]
        assert pose["joint_angles_rad"][4:] == [0, 0]
        error = probe.pose_residual(
            pose["observed_fold_frame_base_link_m"], requested["expected_fold_frame_base_link_m"]
        )
        assert error["position_error_m"] < 1e-8 and error["orientation_error_rad"] < 1e-8
        assert len(pose["observed_axes"]) == 6
        for observed, expected in zip(
            pose["observed_axes"], requested["expected_joint_axes"], strict=True
        ):
            residual = probe.axis_residual(
                observed["point_base_link_m"],
                observed["direction_base_link"],
                expected["origin_m"],
                expected["axis_unit"],
            )
            assert residual["point_to_expected_axis_line_m"] < 1e-8
            assert residual["unsigned_direction_error"] < 1e-8
        marker = pose["link_shape_marker"]
        assert marker["error_mm"] < 1e-5 and marker["vertex_count"] == 6129
        if pose["name"] != "saved_zero":
            assert math.dist(marker["raw_shape_first_vertex_mm"], zero_marker) > 1e-6
        for name, row in pose["offset_and_expression_readback"].items():
            assert (
                row["expressions"]
                == report["original_offset_and_expression_readback"][name]["expressions"]
            )
    summary = report["final_state_summary"]
    assert summary["documents"] == 53 and summary["objects"] == 3001
    assert len(summary["non_up_to_date"]) == 39 and not summary["invalid_or_error"]
    assert all("document" in row for row in summary["non_up_to_date"])
    assert report["saved_offsets_restored_in_memory"]
    receipt = report["publication_provenance"]["launcher_receipt"]
    assert receipt["worker_snapshot_sha256"] == report["capture_script_sha256"]
    assert receipt["original_compatible_source_bytes_unchanged"]
    assert (
        receipt["original_compatible_source_sha256_before"]
        == receipt["original_compatible_source_sha256_after"]
        == report["source_copy_sha256_before"]
    )
    assert receipt["worker_request_helper_snapshots_unchanged"]
