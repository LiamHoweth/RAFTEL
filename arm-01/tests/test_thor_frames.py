"""Frame direction, covariance and unknown-calibration checks."""

import copy
import json
import math
import random
from pathlib import Path

import pytest

from raftel_arm01.kinematics.thor_frames import (
    IDENTITY,
    FrameGraph,
    FrameRecord,
    adjoint,
    compose,
    compose_covariance,
    covariance,
    inverse,
    load_frame_graph,
    rigid_transform,
    transform_covariance,
    transform_point,
    with_nominal_pose,
)

ROOT = Path(__file__).parents[1]


def yaw_pose(angle, translation):
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = translation
    return ((c, -s, 0, x), (s, c, 0, y), (0, 0, 1, z), (0, 0, 0, 1))


def flat(value):
    return [component for row in value for component in row]


def test_source_native_direction_and_unknown_extrinsics():
    graph = load_frame_graph(ROOT / "config/thor-frames-v1.json")
    conversion = graph.transform("base_link", "native_cad")
    assert transform_point(conversion, (0, 1, 0)) == pytest.approx((1, 0, 0))
    assert transform_point(conversion, (1, 0, 0)) == pytest.approx((0, -1, 0))
    assert graph.transform("link_6", "gripper_mid_point")[2][3] == pytest.approx(0.118)
    with pytest.raises(ValueError, match="unknown"):
        graph.transform("base_link", "camera")
    with pytest.raises(ValueError, match="unknown"):
        graph.transform("gripper_mid_point", "tcp")
    # Link6 is dynamic and is deliberately not frozen to base_link here.
    with pytest.raises(ValueError, match="disconnected"):
        graph.transform("base_link", "link_6")


def test_nominal_pose_graph_composes_fixed_frames_without_calibration():
    graph = load_frame_graph(ROOT / "config/thor-frames-v1.json")
    posed = with_nominal_pose(graph, (0, math.pi / 2, 0, 0, 0, 0))
    point = transform_point(posed.transform("base_link", "gripper_mid_point"), (0, 0, 0))
    assert point == pytest.approx((0, -0.4855, 0.202), abs=1e-12)
    assert len(posed.records) == len(graph.records) + 1
    with pytest.raises(ValueError, match="unknown"):
        posed.transform("camera", "gripper_mid_point")
    with pytest.raises(ValueError, match="unknown"):
        posed.transform("base_link", "tcp")
    with pytest.raises(ValueError, match="one parent"):
        with_nominal_pose(posed, (0,) * 6)


def test_transform_composition_direction_nonzero_rotation_translation():
    a = yaw_pose(math.pi / 2, (1, 2, 3))
    b = yaw_pose(-math.pi / 2, (0, 1, 0))
    product = compose(a, b)
    assert transform_point(product, (2, 3, 4)) == pytest.approx((2, 5, 7))
    graph = FrameGraph(
        (
            FrameRecord("a", "b", a, "synthetic", "fixture"),
            FrameRecord("b", "c", b, "synthetic", "fixture"),
        )
    )
    assert flat(graph.transform("a", "c")) == pytest.approx(flat(product))
    assert flat(graph.transform("c", "a")) == pytest.approx(flat(inverse(product)))


def test_seeded_inverse_and_composition_point_identity():
    rng = random.Random(722)
    for _ in range(100):
        pose = yaw_pose(rng.uniform(-math.pi, math.pi), tuple(rng.uniform(-3, 3) for _ in range(3)))
        point = tuple(rng.uniform(-1, 1) for _ in range(3))
        assert flat(compose(pose, inverse(pose))) == pytest.approx(flat(IDENTITY), abs=2e-15)
        assert transform_point(inverse(pose), transform_point(pose, point)) == pytest.approx(
            point, abs=2e-15
        )


def test_covariance_translation_lever_arm_and_independent_composition():
    pose = yaw_pose(0, (1, 0, 0))
    original = tuple(tuple(float(i == j == 5) for j in range(6)) for i in range(6))
    carried = transform_covariance(pose, original)
    assert carried[1][1] == 1
    assert carried[5][5] == 1
    assert carried[1][5] == carried[5][1] == -1
    zeros = tuple((0.0,) * 6 for _ in range(6))
    assert compose_covariance(pose, zeros, original) == carried
    recovered = transform_covariance(inverse(pose), carried)
    assert flat(recovered) == pytest.approx(flat(original))


def test_adjoint_composition_and_covariance_rotation():
    a, b = yaw_pose(0.8, (1, -2, 3)), yaw_pose(-0.2, (0.3, 0.1, -0.5))
    from raftel_arm01.kinematics.thor_frames import multiply

    assert flat(adjoint(compose(a, b))) == pytest.approx(flat(multiply(adjoint(a), adjoint(b))))
    original = tuple(tuple(float(i == j == 0) for j in range(6)) for i in range(6))
    carried = transform_covariance(yaw_pose(math.pi / 2, (0, 0, 0)), original)
    assert carried[1][1] == pytest.approx(1)
    assert carried[0][0] == pytest.approx(0, abs=1e-30)


@pytest.mark.parametrize(
    "field,value",
    [("evidence", ""), ("evidence_class", "guessed"), ("child", "a"), ("parent_from_child", None)],
)
def test_invalid_frame_record(field, value):
    record = dict(
        parent="a",
        child="b",
        parent_from_child=IDENTITY,
        evidence_class="synthetic",
        evidence="fixture",
    )
    record[field] = value
    with pytest.raises(ValueError):
        FrameRecord(**record)


def test_cycles_duplicate_parents_unknowns_and_missing_frames():
    a = FrameRecord("a", "b", IDENTITY, "source", "fixture")
    b = FrameRecord("b", "a", IDENTITY, "source", "fixture")
    with pytest.raises(ValueError, match="cycle"):
        FrameGraph((a, b))
    with pytest.raises(ValueError, match="one parent"):
        FrameGraph((a, a))
    with pytest.raises(ValueError, match="unknown"):
        FrameRecord("a", "b", IDENTITY, "unknown", "fixture")
    graph = FrameGraph((a,))
    with pytest.raises(ValueError, match="absent"):
        graph.transform("a", "missing")
    assert graph.transform("b", "b") == IDENTITY


@pytest.mark.parametrize(
    "bad",
    [
        ((1, 0),) * 4,
        ((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        ((2, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        ((1, 0, 0, float("nan")), *IDENTITY[1:]),
        ((*IDENTITY[0][:3], True), *IDENTITY[1:]),
        (*IDENTITY[:3], (0, 0, 0, 0)),
    ],
)
def test_invalid_rigid_transform(bad):
    with pytest.raises(ValueError):
        rigid_transform(bad)


def test_covariance_rejects_non_psd_asymmetric_and_invalid_values():
    values = [[float(i == j) for j in range(6)] for i in range(6)]
    for invalid in (-1, float("nan"), True):
        bad = copy.deepcopy(values)
        bad[0][0] = invalid
        with pytest.raises(ValueError):
            covariance(bad)
    bad = copy.deepcopy(values)
    bad[0][1] = 1
    with pytest.raises(ValueError, match="symmetric"):
        covariance(bad)
    bad[1][0] = 1
    bad[0][0] = 0
    with pytest.raises(ValueError, match="positive"):
        covariance(bad)


def test_manifest_rejects_duplicate_and_malformed_json(tmp_path):
    path = tmp_path / "frames.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_frame_graph(path)
    data = json.loads((ROOT / "config/thor-frames-v1.json").read_text())
    data["frames"][0]["surprise"] = "not a supported field"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="fields"):
        load_frame_graph(path)


@pytest.mark.parametrize(
    "field,value",
    [("schema_version", True), ("schema_version", 1.0), ("source", None), ("revision", "")],
)
def test_frame_manifest_schema_and_provenance_reject(tmp_path, field, value):
    data = json.loads((ROOT / "config/thor-frames-v1.json").read_text())
    data[field] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_frame_graph(path)


def test_transform_overflow_and_invalid_evidence_type_reject():
    with pytest.raises(ValueError):
        compose(yaw_pose(0, (1e308, 0, 0)), yaw_pose(0, (1e308, 0, 0)))
    with pytest.raises(ValueError):
        FrameRecord("a", "b", IDENTITY, [], "fixture")
