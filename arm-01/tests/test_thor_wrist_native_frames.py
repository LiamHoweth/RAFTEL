"""Independent source-line oracle, never production FK or worker predictions.

These checks corroborate imposed AppLink fold/roll coordinates and cached-body
refresh. They cannot establish tooth contact, differential closure, calibrated
motor signs, full-body clearance, or physical wrist performance.
"""

import copy
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "hardware/cad/thor-wrist-native-frames-v1.json"
SOURCE_CAPTURE = ROOT / "hardware/cad/thor-printed-tensor-frames-v1.json"
SOURCE_CAPTURE_SHA = "fa4a2f88e027c17a33c8d092640c747cfbe7d1fc9ad008c151701eb7b0d05a20"
XACRO_SHA = "19b83e26f86aae15fda5c21418f768d0e3ed1b0d1daa6d149abd9b45ceccd8b9"
RING = "Art56MotorCoverRing_Art56MotorCoverRing"
PLATE = "Art56GearPlate_Art56GearPlate"
GRIPPER = "GripperBot_GripperBot"
BODIES = {RING, PLATE, GRIPPER}
STATIONARY = "AssemblyArt4"
TOL_MM = 1e-6  # numerical replay tolerance, never a manufacturing tolerance


def _dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b, strict=True))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _apply(frame, point):
    return [_dot(row[:3], point) + row[3] for row in frame[:3]]


def _multiply(a, b):
    return [[math.fsum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _quaternion_frame(position, quaternion):
    # Generic quaternion action; deliberately independent of FreeCAD/host helpers.
    length = math.hypot(*quaternion)
    x, y, z, w = [component / length for component in quaternion]
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), position[0]],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), position[1]],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), position[2]],
        [0, 0, 0, 1],
    ]


def _source_axes():
    # Thor-ROS e11a56b5, pinned by XACRO_SHA, joint_1..5 origin xyz, all rpy=0.
    # joint_5 axis is source +X, joint_6 is source +Z; native->source Rz(-pi/2).
    heights_m = (0.099, 0.103, 0.16, 0.0895, 0.1045)
    fold_origin = [0, 0, 1000 * math.fsum(heights_m)]
    source_to_native = ((0, -1, 0), (1, 0, 0), (0, 0, 1))
    fold_axis = [_dot(row, (1, 0, 0)) for row in source_to_native]
    # Independently inspected pinned CAD XML placements, not model-derived data:
    # Assembly::AssemblyArt56 * AssemblyArt56::ring * ring::LCS_BigGear.
    half = math.sqrt(0.5)
    master = _quaternion_frame(fold_origin, (0, 0, half, half))
    ring = _quaternion_frame((0, 0, 0), (0.5, -0.5, 0.5, -0.5))
    datum = _quaternion_frame((0, -19.5, 0), (0.5, -0.5, 0.5, 0.5))
    roll_parent = _multiply(_multiply(master, ring), datum)
    return (
        fold_origin,
        fold_axis,
        [row[3] for row in roll_parent[:3]],
        [row[2] for row in roll_parent[:3]],
    )


def _rotate(point, origin, axis, angle):
    """Rodrigues axis-line action for arbitrary signed axes and units."""
    axis = [v / math.hypot(*axis) for v in axis]
    delta = [p - c for p, c in zip(point, origin, strict=True)]
    cosine, sine = math.cos(angle), math.sin(angle)
    cross = _cross(axis, delta)
    projection = _dot(axis, delta)
    return [
        origin[i] + cosine * delta[i] + sine * cross[i] + (1 - cosine) * projection * axis[i]
        for i in range(3)
    ]


def _expected_point(point, q5, q6, *, roll):
    fold_origin, fold_axis, roll_origin, roll_axis = _source_axes()
    # Serial hierarchy: rotate in the saved plate-parent frame, then carry the
    # entire wrist with fold. Reversing these rotations is a different motion.
    rolled = _rotate(point, roll_origin, roll_axis, q6) if roll else point
    return _rotate(rolled, fold_origin, fold_axis, q5)


def _expected_frame(frame, q5, q6, *, roll):
    origin = [row[3] for row in frame[:3]]
    moved = _expected_point(origin, q5, q6, roll=roll)
    columns = []
    for j in range(3):
        tip = [origin[i] + frame[i][j] for i in range(3)]
        moved_tip = _expected_point(tip, q5, q6, roll=roll)
        columns.append([moved_tip[i] - moved[i] for i in range(3)])
    return [[columns[j][i] for j in range(3)] + [moved[i]] for i in range(3)] + [[0, 0, 0, 1]]


def _assert_close(actual, expected, tolerance=TOL_MM):
    assert len(actual) == len(expected)
    assert all(math.isfinite(x) for x in actual)
    assert math.dist(actual, expected) < tolerance


def _assert_frame(actual, expected):
    assert len(actual) == 4 and actual[3] == [0, 0, 0, 1]
    for row, reference in zip(actual[:3], expected[:3], strict=True):
        _assert_close(row, reference)
    columns = [[actual[i][j] for i in range(3)] for j in range(3)]
    for i in range(3):
        for j in range(3):
            assert _dot(columns[i], columns[j]) == pytest.approx(float(i == j), abs=1e-9)
    assert _dot(columns[0], _cross(columns[1], columns[2])) == pytest.approx(1, abs=1e-9)


def _source_instances():
    raw = SOURCE_CAPTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_CAPTURE_SHA
    data = json.loads(raw)
    variants = {row["selection_id"]: row for row in data["variants"]}
    return {
        row["object_metadata"]["name"]: (row, variants[row["selection_id"]])
        for row in data["instances"]
        if row["object_metadata"]["name"] in BODIES
    }


def _assert_body_triplet(zero, actual, q5, q6):
    name = zero["object"]
    assert actual["object"] == name
    assert actual["marker_vertex_indices_zero_based"] == zero["marker_vertex_indices_zero_based"]
    indices = actual["marker_vertex_indices_zero_based"]
    assert len(indices) == len(set(indices)) == 3
    assert all(type(i) is int and 0 <= i < actual["vertex_count"] for i in indices)
    assert actual["vertex_count"] == zero["vertex_count"]
    assert actual["linked_document"] == zero["linked_document"]
    assert actual["linked_object"] == zero["linked_object"] == "Body"
    baseline = zero["actual_markers_native_world_mm"]
    observed = actual["actual_markers_native_world_mm"]
    assert len(baseline) == len(observed) == 3
    edge1 = [baseline[1][i] - baseline[0][i] for i in range(3)]
    edge2 = [baseline[2][i] - baseline[0][i] for i in range(3)]
    assert math.hypot(*_cross(edge1, edge2)) > 1e-3
    for point, reference in zip(observed, baseline, strict=True):
        _assert_close(point, _expected_point(reference, q5, q6, roll=name != RING))
    for key in ("body_frame_native_world_mm", "marker_frame_native_world_mm"):
        _assert_frame(actual[key], _expected_frame(zero[key], q5, q6, roll=name != RING))
    for i in range(3):
        for j in range(i):
            assert math.dist(observed[i], observed[j]) == pytest.approx(
                math.dist(baseline[i], baseline[j]), abs=TOL_MM
            )


def test_independent_pinned_xacro_and_cad_datum_axes_agree():
    prior = json.loads((ROOT / "hardware/cad/thor-native-pose-frames.json").read_bytes())
    assert prior["request"]["source_xacro_sha256"] == XACRO_SHA
    fold, axis, roll, roll_axis = _source_axes()
    _assert_close(fold, [0, 0, 556])
    _assert_close(axis, [0, 1, 0])
    _assert_close(roll, [0, 0, 575.5])
    _assert_close(roll_axis, [0, 0, 1])
    # Source joint_6 z=569.5 and cached native plate z=577.5 lie on the same
    # infinite roll line. Their distinct axial origins must not become offsets.
    for height in (569.5, 577.5):
        _assert_close(_cross([0, 0, height - roll[2]], roll_axis), [0, 0, 0])


@pytest.mark.parametrize("q5,q6", [(0, 0), (math.pi / 2, 0), (0, math.pi / 2), (math.pi / 2,) * 2])
def test_independent_quarter_turn_fixture_has_known_signed_coordinates(q5, q6):
    # Hand-calculated quarter turns of (10,20,586): Rz maps (x,y)->(-y,x),
    # Ry about z556 maps (x,z-556)->(z-556,-x). No FK-generated expectations.
    expected = {
        (0, 0): [10, 20, 586],
        (math.pi / 2, 0): [30, 20, 546],
        (0, math.pi / 2): [-20, 10, 586],
        (math.pi / 2, math.pi / 2): [30, 10, 576],
    }[(q5, q6)]
    _assert_close(_expected_point([10, 20, 586], q5, q6, roll=True), expected)


def test_oracle_distinguishes_wrong_sign_order_units_and_fold_only_membership():
    point = [11, 23, 603]
    q5, q6 = 0.2, 0.15
    expected = _expected_point(point, q5, q6, roll=True)
    fold, axis, roll, roll_axis = _source_axes()
    wrong_order = _rotate(_rotate(point, fold, axis, q5), roll, roll_axis, q6)
    for wrong in (
        _expected_point(point, -q5, q6, roll=True),
        _expected_point(point, q5, -q6, roll=True),
        _expected_point(point, q5, q6, roll=False),
        _expected_point([p / 1000 for p in point], q5, q6, roll=True),
        wrong_order,
    ):
        assert math.dist(wrong, expected) > 0.1


def _analytic_triplets():
    zero = {
        "object": PLATE,
        "linked_document": "Art56GearPlate",
        "linked_object": "Body",
        "vertex_count": 3,
        "marker_vertex_indices_zero_based": [0, 1, 2],
        "actual_markers_native_world_mm": [[10, 20, 586], [12, 20, 586], [10, 23, 586]],
        "body_frame_native_world_mm": [[1, 0, 0, 10], [0, 1, 0, 20], [0, 0, 1, 586], [0, 0, 0, 1]],
        "marker_frame_native_world_mm": [
            [1, 0, 0, 10],
            [0, 1, 0, 20],
            [0, 0, 1, 586],
            [0, 0, 0, 1],
        ],
    }
    # Exact hand-derived Ry(pi/2) Rz(pi/2), not generated by the oracle.
    moved = copy.deepcopy(zero)
    moved["actual_markers_native_world_mm"] = [[30, 10, 576], [30, 12, 576], [30, 10, 579]]
    for key in ("body_frame_native_world_mm", "marker_frame_native_world_mm"):
        moved[key] = [[0, 0, 1, 30], [1, 0, 0, 10], [0, 1, 0, 576], [0, 0, 0, 1]]
    return zero, moved


def test_hand_derived_marker_body_frames_and_return_pass_independent_replay():
    zero, moved = _analytic_triplets()
    _assert_body_triplet(zero, moved, math.pi / 2, math.pi / 2)
    _assert_body_triplet(zero, zero, 0, 0)


@pytest.mark.parametrize("corruption", ["stale_vertex", "reflection", "wrong_sign", "wrong_index"])
def test_triplet_replay_rejects_changes_that_a_frame_readback_alone_could_miss(corruption):
    zero, moved = _analytic_triplets()
    q5, q6 = math.pi / 2, math.pi / 2
    if corruption == "stale_vertex":
        moved["actual_markers_native_world_mm"][2] = zero["actual_markers_native_world_mm"][2]
    elif corruption == "reflection":
        moved["body_frame_native_world_mm"][0][2] = -1
    elif corruption == "wrong_sign":
        q6 = -q6
    else:
        moved["marker_vertex_indices_zero_based"] = [0, 2, 1]
    with pytest.raises(AssertionError):
        _assert_body_triplet(zero, moved, q5, q6)


def test_source_cached_vertices_authenticate_saved_triplets_without_native_runtime():
    instances = _source_instances()
    assert set(instances) == BODIES
    for instance, variant in instances.values():
        indices = instance["marker_check"]["noncollinear_witness_indices"]
        assert len(indices) == len(set(indices)) == 3
        for index in indices:
            source = variant["source_vertices_mm"][index]
            installed = instance["installed_vertices_mm"][index]
            _assert_close(_apply(instance["source_raw_to_installed_raw_mm"], source), installed)
            _assert_close(
                _apply(instance["ancestor_transform_mm"], installed),
                _apply(instance["source_raw_to_master_mm"], source),
            )


def test_actual_native_capture_replays_source_vertices_frames_and_zero_return():
    if not CAPTURE.exists():
        pytest.skip("fresh native wrist capture has not been published; fixtures are host-only")
    data = json.loads(CAPTURE.read_text(encoding="utf-8"))
    assert data["status"] == "complete_native_wrist_observations_pending_independent_review"
    assert data["source_copy_bytes_unchanged"] and data["saved_offsets_restored_in_memory"]
    assert data["source_copy_sha256_before"] == data["source_copy_sha256_after"]
    assert data["source_copy_sha256_before"] == data["request"]["source_sha256"]
    assert data["saved_offset_return_maximum_matrix_error"] <= 1e-9
    contract = data["request"]["source_contract"]
    assert contract["source_revision"] == "286b081fe6f056d87c379b884781ef77ff6a0159"
    assert contract["coordinate_frame"] == "native_CAD_world_mm_at_zero_proximal_four_joints"
    assert contract["angle_units"] == "radians"
    bindings = {row["object"]: row for row in contract["bindings"]}
    assert bindings["AssemblyArt56"]["increment_side"] == "right"
    assert bindings["AssemblyArt56"]["increment_axis"] == [1, 0, 0]
    assert bindings[PLATE]["increment_side"] == "left"
    assert bindings[PLATE]["increment_axis"] == [0, 0, 1]
    assert bindings[PLATE]["parent_link"] == RING
    assert bindings[PLATE]["parent_datum"] == "LCS_BigGear"
    assert bindings[GRIPPER]["parent_link"] == PLATE
    assert not data["errors"]
    for key in (
        "constraint_kinematics_solved",
        "side_differential_gears_driven",
        "physical_calibration_or_contact_or_TCP_qualified",
        "cad_documents_saved",
        "forced_feature_history_rebuild",
    ):
        assert data[key] is False
    assert [pose["name"] for pose in data["poses"]] == ["saved_zero", "fold_roll", "saved_return"]
    zero, moved, returned = data["poses"]
    assert [(pose["q5_rad"], pose["q6_rad"]) for pose in data["poses"]] == [
        (0, 0),
        (0.2, 0.15),
        (0, 0),
    ]
    baseline = {row["object"]: row for row in zero["bodies"]}
    assert set(baseline) == BODIES | {STATIONARY}
    sources = _source_instances()
    for name, body in baseline.items():
        if name == STATIONARY:
            continue
        instance, variant = sources[name]
        binding = variant["source_binding"]
        assert (
            data["source_copy_sha256_before"][Path(binding["source_file"]).name]
            == binding["source_sha256"]
        )
        assert body["vertex_count"] == len(variant["source_vertices_mm"])
        assert body["linked_document"] + "::" + body["linked_object"] == variant["asset_id"]
        for position, index in enumerate(body["marker_vertex_indices_zero_based"]):
            _assert_close(
                body["actual_markers_native_world_mm"][position],
                _apply(instance["source_raw_to_master_mm"], variant["source_vertices_mm"][index]),
            )
        _assert_frame(body["body_frame_native_world_mm"], instance["source_raw_to_master_mm"])
    for pose in data["poses"]:
        assert not pose["state_summary"]["invalid_or_error"]
        for observed, original in zip(
            pose["driver_readbacks"], data["driver_original_readback"], strict=True
        ):
            assert observed["expressions"] == original["expressions"]
            assert (observed["document"], observed["object"]) == (
                original["document"],
                original["object"],
            )
            if pose["name"] in ("saved_zero", "saved_return"):
                _assert_frame(observed["offset"]["matrix"], original["offset"]["matrix"])
        assert len(pose["bodies"]) == 4
        assert {body["object"] for body in pose["bodies"]} == BODIES | {STATIONARY}
        for body in pose["bodies"]:
            if body["object"] == STATIONARY:
                original = baseline[STATIONARY]
                assert body["linked_document"] == "AssemblyArt4"
                assert body["linked_object"] == "Model"
                assert body["document"] == "Assembly"
                assert (
                    body["ordered_raw_vertices_sha256"] == original["ordered_raw_vertices_sha256"]
                )
                assert body["vertex_count"] == original["vertex_count"]
                for key in ("body_frame_native_world_mm", "marker_frame_native_world_mm"):
                    _assert_frame(body[key], original[key])
                for point, reference in zip(
                    body["actual_markers_native_world_mm"],
                    original["actual_markers_native_world_mm"],
                    strict=True,
                ):
                    _assert_close(point, reference)
                assert body["linked_source_vertex_count"] == body["vertex_count"]
                for source, actual in zip(
                    body["linked_source_markers_mm"],
                    body["actual_markers_native_world_mm"],
                    strict=True,
                ):
                    _assert_close(_apply(body["body_frame_native_world_mm"], source), actual)
                continue
            _assert_body_triplet(baseline[body["object"]], body, pose["q5_rad"], pose["q6_rad"])
            _, variant = sources[body["object"]]
            binding = variant["source_binding"]
            cached = body["cached_source_binding"]
            for key in ("source_sha256", "brep_sha256", "brep_entry", "object_name", "object_type"):
                assert cached[key] == binding[key]
            # Windows restores document references using their saved extension
            # spelling (.FCStd), even when the pinned disk basename is .fcstd.
            assert PureWindowsPath(cached["source_file"]) == PureWindowsPath(
                Path(binding["source_file"]).name
            )
            assert (
                body["cached_source_vertex_count"]
                == body["linked_source_vertex_count"]
                == len(variant["source_vertices_mm"])
            )
            for position, index in enumerate(body["marker_vertex_indices_zero_based"]):
                source = variant["source_vertices_mm"][index]
                _assert_close(body["cached_source_markers_mm"][position], source)
                _assert_close(body["linked_source_markers_mm"][position], source)
                _assert_close(
                    _apply(body["body_frame_native_world_mm"], source),
                    body["actual_markers_native_world_mm"][position],
                )
            for raw, actual in zip(
                body["raw_shape_markers_subassembly_mm"],
                body["actual_markers_native_world_mm"],
                strict=True,
            ):
                _assert_close(_apply(pose["master_wrist_placement"]["matrix"], raw), actual)
    # Subassembly raw shapes roll for plate/gripper, while ring stays fixed;
    # world markers move for all three under the common q5 ancestor.
    for body in moved["bodies"]:
        if body["object"] == STATIONARY:
            continue
        original = baseline[body["object"]]
        same_raw = body["ordered_raw_vertices_sha256"] == original["ordered_raw_vertices_sha256"]
        assert same_raw == (body["object"] == RING)
        assert (
            max(
                math.dist(a, b)
                for a, b in zip(
                    body["actual_markers_native_world_mm"],
                    original["actual_markers_native_world_mm"],
                    strict=True,
                )
            )
            > 1
        )
    for body in returned["bodies"]:
        if body["object"] == STATIONARY:
            continue
        _assert_body_triplet(baseline[body["object"]], body, 0, 0)
    # A stale selected vertex cannot hide behind an unchanged frame/readback.
    bad = copy.deepcopy(moved["bodies"][0])
    bad["actual_markers_native_world_mm"][2][0] += 0.01
    with pytest.raises(AssertionError):
        _assert_body_triplet(baseline[bad["object"]], bad, 0.2, 0.15)
