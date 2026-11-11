"""Offline replay ordering, denominator, clock and frame counterexamples."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from raftel_arm01.kinematics.thor_frames import FrameGraph, FrameRecord, load_frame_graph
from raftel_arm01.models import ObjectPose, Position
from raftel_arm01.perception import replay as module
from raftel_arm01.perception.replay import read_observation_document, replay_observations

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/observation-replay-v1.json"
DOMAIN = "simulation:observation-fixture-v1"


@pytest.fixture
def document():
    return read_observation_document(FIXTURE)


def test_point_covariance_replay_uses_scale_invariant_psd_check(document):
    row = document["observations"][0]
    row["position_covariance_m2"] = [[1e200, 5e199, 0], [5e199, 1e200, 0], [0, 0, 0]]
    # Finite synthetic uncertainty is validated independently of its usefulness.
    replay = _replay(document)
    assert replay.decisions[0].position_covariance_m2[0][0] == 1e200
    row["position_covariance_m2"] = [[1e-100, 2e-100, 0], [2e-100, 1e-100, 0], [0, 0, 0]]
    with pytest.raises(ValueError, match="positive semidefinite"):
        _replay(document)


def _replay(document, **overrides):
    return replay_observations(
        document,
        **{
            "as_of_s": 10.0,
            "time_domain": DOMAIN,
            "max_age_s": 1.0,
            **overrides,
        },
    )


def _camera_graph(*, translation=(0.1, -0.2, 0.3), known=True):
    # A hand-computable +90deg rotation about Z maps (x,y,z)->(-y,x,z).
    transform = (
        (
            (0.0, -1.0, 0.0, translation[0]),
            (1.0, 0.0, 0.0, translation[1]),
            (0.0, 0.0, 1.0, translation[2]),
            (0.0, 0.0, 0.0, 1.0),
        )
        if known
        else None
    )
    return FrameGraph(
        (
            FrameRecord(
                "arm_base",
                "camera",
                transform,
                "synthetic" if known else "unknown",
                "Explicit synthetic camera scenario" if known else "No measured extrinsic",
            ),
        )
    )


def test_hand_counted_replay_preserves_all_presented_and_rejected_rows(document):
    first, second = _replay(document), _replay(copy.deepcopy(document))
    assert first == second
    report = first.to_dict()
    assert report["counts"] == {
        "presented": 4,
        "supplied_detected": 3,
        "current_accepted": 1,
        "current_rejected": 2,
        "never_observed": 1,
        "observation_records": 4,
        "rejected_records": 3,
    }
    assert report["never_observed_ids"] == ["object-c"]
    assert report["current_observation_ids"] == ["observation-1", "observation-2", "observation-3"]
    assert first.objects() == (ObjectPose("object-a", "red", Position(0.03, 0.21, 0.02), 0.02),)
    assert first.decisions[0].rejection_reasons == ("stale_observation",)
    assert first.decisions[2].rejection_reasons == ("unknown_position_uncertainty",)
    assert first.decisions[3].rejection_reasons == ("future_timestamp",)
    assert not report["physical_calibration_qualified"]
    assert not report["sorting_outcomes_evaluated"]
    assert not report["extrinsic_uncertainty_included"]
    json.dumps(report, allow_nan=False)
    assert not any(
        key in report["counts"] for key in ("eligible", "attempted", "correct", "success")
    )


def test_unknown_uncertainty_requires_explicit_analysis_policy(document):
    replay = _replay(document, require_uncertainty=False)
    assert [obj.identifier for obj in replay.objects()] == ["object-a", "object-b"]
    unknown = replay.current_decisions[1]
    assert unknown.position_covariance_m2 is None
    assert replay.to_dict()["unknown_position_uncertainty_allowed"] is True
    assert replay.to_dict()["physical_calibration_qualified"] is False


@pytest.mark.parametrize("rejection", ["uncertainty", "future"])
def test_newest_bad_observation_never_backfills_old_good_pose(document, rejection):
    document["observations"] = document["observations"][:2]
    old, new = document["observations"]
    old["timestamp_s"] = 9.0
    if rejection == "uncertainty":
        new["position_covariance_m2"] = None
    else:
        new["timestamp_s"] = 10.2
    result = _replay(document)
    assert result.decisions[0].accepted
    assert not result.decisions[1].accepted
    assert result.current_decisions == (result.decisions[1],)
    assert result.objects() == ()
    assert result.to_dict()["counts"]["supplied_detected"] == 1
    assert result.to_dict()["counts"]["presented"] == 4


def test_equal_timestamps_keep_sequence_order_and_exact_age_boundary(document):
    document["observations"] = document["observations"][:2]
    for row in document["observations"]:
        row["timestamp_s"] = 9.0
    result = _replay(document)
    assert all(row.accepted for row in result.decisions)
    assert result.objects()[0].position == Position(0.03, 0.21, 0.02)
    assert result.current_decisions[0].observation_id == "observation-1"
    document["observations"][1]["timestamp_s"] = 10.0
    assert _replay(document, max_age_s=0).objects()[0].position == Position(0.03, 0.21, 0.02)


def test_no_observations_keeps_all_misses_in_denominator(document):
    document["observations"] = []
    replay = _replay(document)
    assert replay.objects() == ()
    report = replay.to_dict()
    assert report["counts"]["presented"] == report["counts"]["never_observed"] == 4
    assert report["counts"]["supplied_detected"] == 0


def test_point_and_full_correlated_covariance_rotation_are_independent_of_translation(document):
    document["coordinate_frame"] = "camera"
    document["observations"] = document["observations"][1:2]
    row = document["observations"][0]
    row["sequence"] = 0
    row["position_m"] = [1.0, 2.0, 3.0]
    row["position_covariance_m2"] = [
        [1e-6, 0.25e-6, 0.1e-6],
        [0.25e-6, 4e-6, 0.2e-6],
        [0.1e-6, 0.2e-6, 9e-6],
    ]
    replay = _replay(document, target_frame="arm_base", frame_graph=_camera_graph())
    decision = replay.decisions[0]
    assert decision.position == Position(-1.9, 0.8, 3.3)
    assert decision.source_position == Position(1.0, 2.0, 3.0)
    expected = ((4e-6, -0.25e-6, -0.2e-6), (-0.25e-6, 1e-6, 0.1e-6), (-0.2e-6, 0.1e-6, 9e-6))
    for actual, wanted in zip(decision.position_covariance_m2, expected, strict=True):
        assert actual == pytest.approx(wanted, abs=1e-18)
    moved = _replay(
        document, target_frame="arm_base", frame_graph=_camera_graph(translation=(1000, 2000, 3000))
    )
    assert moved.decisions[0].position_covariance_m2 == decision.position_covariance_m2
    assert replay.objects()[0].position == decision.position
    assert (
        replay.to_dict()["frame_graph_canonical_sha256"]
        != moved.to_dict()["frame_graph_canonical_sha256"]
    )
    assert replay.to_dict()["extrinsic_uncertainty_included"] is False


def test_missing_extrinsics_rejects_conversion_without_identity_fallback(document):
    document["coordinate_frame"] = "camera"
    replay = _replay(document, target_frame="arm_base", frame_graph=_camera_graph(known=False))
    assert replay.transform_error
    assert "unknown" in replay.transform_error
    assert all("missing_or_unknown_transform" in row.rejection_reasons for row in replay.decisions)
    assert all(
        row.frame == "camera" and row.position == row.source_position for row in replay.decisions
    )
    assert replay.objects() == ()
    assert replay.to_dict()["counts"]["presented"] == 4


def test_raw_known_camera_frame_cannot_become_logical_object_pose(document):
    document["coordinate_frame"] = "camera"
    replay = _replay(document, frame_graph=_camera_graph(known=False))
    assert replay.decisions[1].accepted
    assert replay.decisions[1].frame == "camera"
    with pytest.raises(ValueError, match="logical arm_base"):
        replay.objects()
    with pytest.raises(ValueError, match="unknown"):
        _replay(document)


def test_existing_nominal_base_link_is_not_an_arm_base_alias(document):
    graph = load_frame_graph(ROOT / "config/thor-frames-v1.json")
    document["coordinate_frame"] = "base_link"
    replay = _replay(document, target_frame="arm_base", frame_graph=graph)
    assert all("missing_or_unknown_transform" in row.rejection_reasons for row in replay.decisions)
    assert replay.objects() == ()


def test_recorded_provenance_is_preserved_without_upgrading_evidence(document):
    document["source_kind"] = "recorded"
    document["provenance"]["source_sha256"] = "a" * 64
    replay = _replay(document)
    assert replay.to_dict()["source_kind"] == "recorded"
    assert replay.to_dict()["provenance"]["source_sha256"] == "a" * 64
    assert replay.to_dict()["validation_class"] == "offline_supplied_observation_replay"
    assert replay.to_dict()["physical_calibration_qualified"] is False
    document["provenance"]["source_sha256"] = None
    with pytest.raises(ValueError, match="SHA-256"):
        _replay(document)


@pytest.mark.parametrize(
    "corruption",
    [
        "boolean_schema",
        "unknown_field",
        "row_unknown_field",
        "units",
        "source_kind",
        "duplicate_presented",
        "duplicate_observation",
        "undeclared_object",
        "sequence_gap",
        "out_of_order",
        "negative_timestamp",
        "boolean_timestamp",
        "nonfinite_position",
        "boolean_position",
        "negative_mass",
        "boolean_mass",
        "bad_covariance_shape",
        "indefinite_covariance",
        "asymmetric_covariance",
        "boolean_covariance",
        "unknown_frame",
        "missing_uncertainty",
        "blank_provenance",
    ],
)
def test_malformed_observations_fail_before_pose_use(document, corruption):
    row = document["observations"][0]
    if corruption == "boolean_schema":
        document["schema_version"] = True
    elif corruption == "unknown_field":
        document["permission_to_move"] = True
    elif corruption == "row_unknown_field":
        row["unexpected"] = 1
    elif corruption == "units":
        document["units"]["position"] = "mm"
    elif corruption == "source_kind":
        document["source_kind"] = "physical_success"
    elif corruption == "duplicate_presented":
        document["presented_ids"].append("object-a")
    elif corruption == "duplicate_observation":
        document["observations"][1]["observation_id"] = row["observation_id"]
    elif corruption == "undeclared_object":
        row["object_id"] = "missing"
    elif corruption == "sequence_gap":
        row["sequence"] = 1
    elif corruption == "out_of_order":
        row["timestamp_s"] = 9.9
    elif corruption == "negative_timestamp":
        row["timestamp_s"] = -1
    elif corruption == "boolean_timestamp":
        row["timestamp_s"] = True
    elif corruption == "nonfinite_position":
        row["position_m"][0] = math.inf
    elif corruption == "boolean_position":
        row["position_m"][0] = False
    elif corruption == "negative_mass":
        row["mass_kg"] = -1
    elif corruption == "boolean_mass":
        row["mass_kg"] = True
    elif corruption == "bad_covariance_shape":
        row["position_covariance_m2"] = [[0, 0], [0, 0]]
    elif corruption == "indefinite_covariance":
        row["position_covariance_m2"] = [[1, 2, 0], [2, 1, 0], [0, 0, 1]]
    elif corruption == "asymmetric_covariance":
        row["position_covariance_m2"][0][1] = 0.1
    elif corruption == "boolean_covariance":
        row["position_covariance_m2"][0][0] = True
    elif corruption == "unknown_frame":
        document["coordinate_frame"] = "unrecognized_optical_frame"
    elif corruption == "missing_uncertainty":
        del row["position_covariance_m2"]
    elif corruption == "blank_provenance":
        document["provenance"]["description"] = " "
    with pytest.raises(ValueError):
        _replay(document)


@pytest.mark.parametrize(
    "arguments",
    [
        {"time_domain": "unix:UTC"},
        {"as_of_s": -1},
        {"as_of_s": True},
        {"as_of_s": math.nan},
        {"max_age_s": -1},
        {"max_age_s": math.inf},
        {"require_uncertainty": "false"},
        {"frame_graph": {}},
        {"target_frame": "unknown"},
    ],
)
def test_policy_and_clock_domains_cannot_be_implicitly_coerced(document, arguments):
    with pytest.raises(ValueError):
        _replay(document, **arguments)


def test_input_bounds_are_enforced(document, monkeypatch):
    monkeypatch.setattr(module, "MAX_OBSERVATIONS", 3)
    with pytest.raises(ValueError, match="bound"):
        _replay(document)
    monkeypatch.setattr(module, "MAX_OBSERVATIONS", 100_000)
    monkeypatch.setattr(module, "MAX_OBJECTS", 3)
    with pytest.raises(ValueError, match="presented_ids"):
        _replay(document)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":{"a":1,"a":2}}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e999}',
        b"[]",
        b'{"x":"\xff"}',
    ],
)
def test_file_reader_rejects_ambiguous_or_nonfinite_json(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        read_observation_document(path)


def test_file_byte_bound_and_fixture_line_endings(tmp_path, monkeypatch):
    path = tmp_path / "large.json"
    path.write_bytes(b" " * 17)
    monkeypatch.setattr(module, "MAX_FILE_BYTES", 16)
    with pytest.raises(ValueError, match="byte bound"):
        read_observation_document(path)
    assert b"\r" not in FIXTURE.read_bytes()
