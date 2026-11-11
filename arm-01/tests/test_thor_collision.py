"""Box mathematics, edge-cross-axis counterexamples and explicit coverage gates."""

import hashlib
import importlib.util
import json
import math
import random
from pathlib import Path

import pytest

from raftel_arm01.kinematics.thor_collision import (
    AABB,
    BoxProxy,
    PairExclusion,
    intersect_boxes,
    screen_proxies,
    transform_proxy,
)
from raftel_arm01.kinematics.thor_frames import IDENTITY

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "thor_collision_study", ROOT / "tools/thor_collision_study.py"
)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def pose(angles=(0, 0, 0), center=(0, 0, 0)):
    a, b, c = angles
    ca, sa, cb, sb, cc, sc = (
        math.cos(a),
        math.sin(a),
        math.cos(b),
        math.sin(b),
        math.cos(c),
        math.sin(c),
    )
    return (
        (cc * cb, cc * sb * sa - sc * ca, cc * sb * ca + sc * sa, center[0]),
        (sc * cb, sc * sb * sa + cc * ca, sc * sb * ca - cc * sa, center[1]),
        (-sb, cb * sa, cb * ca, center[2]),
        (0, 0, 0, 1),
    )


def box(name="a", half=(1, 1, 1), angles=(0, 0, 0), center=(0, 0, 0), frame="fixture"):
    return BoxProxy(
        name,
        frame,
        half,
        pose(angles, center),
        "Explicit synthetic mathematical fixture",
        "synthetic_exact_box",
    )


@pytest.mark.parametrize(
    "distance,relation,contact",
    (
        (0, "proxy_overlap_or_contact", "interior_overlap"),
        (1.9, "proxy_overlap_or_contact", "interior_overlap"),
        (2, "proxy_overlap_or_contact", "within_numerical_tolerance"),
        (2.1, "no_proxy_overlap", "separated"),
    ),
)
def test_aabb_intersection_tangent_and_separated(distance, relation, contact):
    a = AABB((-1, -1, -1), (1, 1, 1)).proxy("a", "fixture", "Synthetic cube")
    b = AABB((distance - 1, -1, -1), (distance + 1, 1, 1)).proxy("b", "fixture", "Synthetic cube")
    result = intersect_boxes(a, b)
    assert result.relation == relation
    assert result.contact_classification == contact
    assert result.maximum_axis_gap_m == pytest.approx(distance - 2)
    assert result.physical_clearance_established is False


def test_numerical_tolerance_does_not_claim_physical_clearance():
    a, b = box(), box("b", center=(2 + 5e-10, 0, 0))
    assert intersect_boxes(a, b, numerical_tolerance_m=1e-9).relation == "proxy_overlap_or_contact"
    assert intersect_boxes(a, b, numerical_tolerance_m=0).relation == "no_proxy_overlap"
    assert not intersect_boxes(a, b, numerical_tolerance_m=0).physical_clearance_established


def test_rotated_obb_separated_while_its_aabb_overlaps():
    a = box(half=(1, 0.05, 0.05), angles=(0, 0, math.pi / 4))
    b = box("b", half=(1, 0.05, 0.05), angles=(0, 0, math.pi / 4), center=(-0.15, 0.15, 0))
    assert intersect_boxes(a, b).relation == "no_proxy_overlap"
    assert (
        intersect_boxes(
            a.aabb().proxy("aa", "fixture", "AABB of synthetic OBB"),
            b.aabb().proxy("bb", "fixture", "AABB of synthetic OBB"),
        ).relation
        == "proxy_overlap_or_contact"
    )


def test_edge_cross_axis_required_when_all_six_face_axes_overlap():
    a = box(half=(1, 0.2, 0.1))
    b = box(
        "b",
        half=(0.8, 0.15, 0.1),
        angles=(2.5272549266958766, -2.2482578366841084, -2.26555243474823),
        center=(-0.23219172223120865, -0.5536713525815719, 0.3858714912656882),
    )
    for axis in (*a.axes, *b.axes):
        pa = [sum(p[i] * axis[i] for i in range(3)) for p in a.corners_m()]
        pb = [sum(p[i] * axis[i] for i in range(3)) for p in b.corners_m()]
        assert min(max(pa), max(pb)) > max(min(pa), min(pb))
    result = intersect_boxes(a, b)
    assert result.relation == "no_proxy_overlap"
    assert result.maximum_axis_gap_m == pytest.approx(0.2747286833896902)
    assert result.axes_tested == 15


def test_nearly_parallel_axes_tangent_and_finite():
    a = box()
    b = box("b", angles=(0, 0, 1e-14), center=(2, 0, 0))
    result = intersect_boxes(a, b)
    assert result.relation == "proxy_overlap_or_contact"
    assert all(math.isfinite(value) for value in result.witness_axis_unit)
    assert math.hypot(*result.witness_axis_unit) == pytest.approx(1)


def test_corner_transform_aabb_and_zero_width_geometry():
    proxy = box(half=(1, 2, 3), angles=(0, 0, math.pi / 2), center=(10, 20, 30))
    bounds = proxy.aabb()
    assert bounds.minimum_m == pytest.approx((8, 19, 27))
    assert bounds.maximum_m == pytest.approx((12, 21, 33))
    point = box("point", half=(0, 0, 0), center=(10, 20, 30))
    assert intersect_boxes(proxy, point).relation == "proxy_overlap_or_contact"
    assert (
        intersect_boxes(box(), box("far", half=(0, 0, 0), center=(3, 0, 0))).relation
        == "no_proxy_overlap"
    )


def test_random_pair_symmetry_and_rigid_covariance():
    rng = random.Random(90210)
    for _ in range(100):
        a = box(
            half=tuple(rng.uniform(0.05, 1) for _ in range(3)),
            angles=tuple(rng.uniform(-3, 3) for _ in range(3)),
        )
        b = box(
            "b",
            half=tuple(rng.uniform(0.05, 1) for _ in range(3)),
            angles=tuple(rng.uniform(-3, 3) for _ in range(3)),
            center=tuple(rng.uniform(-2, 2) for _ in range(3)),
        )
        original = intersect_boxes(a, b)
        reverse = intersect_boxes(b, a)
        assert original.relation == reverse.relation
        assert original.maximum_axis_gap_m == pytest.approx(reverse.maximum_axis_gap_m, abs=1e-14)
        change = pose((0.7, -0.3, 1.2), (5, -7, 2))
        moved = intersect_boxes(
            transform_proxy(a, change, "other"), transform_proxy(b, change, "other")
        )
        assert moved.relation == original.relation
        assert moved.maximum_axis_gap_m == pytest.approx(original.maximum_axis_gap_m, abs=1e-13)


@pytest.mark.parametrize("scale", (1e-300, 1e-9, 1, 1e100))
def test_scale_and_tiny_projection_gaps(scale):
    result = intersect_boxes(
        box(half=(scale,) * 3),
        box("b", half=(scale,) * 3, center=(3 * scale, 0, 0)),
        numerical_tolerance_m=0,
    )
    assert result.relation == "no_proxy_overlap"
    assert math.isclose(result.maximum_axis_gap_m, scale, rel_tol=1e-14, abs_tol=0)


def test_unrepresentable_projection_or_center_delta_rejects_cleanly():
    with pytest.raises(ValueError):
        intersect_boxes(box(center=(-1e308, 0, 0)), box("b", center=(1e308, 0, 0)))
    with pytest.raises(ValueError):
        intersect_boxes(box(half=(1.7e308,) * 3, angles=(0, 0, math.pi / 4)), box("b"))


def test_exclusions_are_exact_and_do_not_hide_geometry_or_adjacent_pairs():
    proxies = (box("joint_1"), box("joint_2", center=(2, 0, 0)), box("obstacle", center=(5, 0, 0)))
    exclusion = PairExclusion(
        "joint_2",
        "joint_1",
        "Intentional synthetic face contact",
        "Fixture only; no robot contact evidence",
    )
    result = screen_proxies(proxies, (exclusion,))
    assert result["pair_count"] == 3
    assert result["explicit_exclusion_count"] == 1
    excluded = [r for r in result["pairs"] if r["policy_exclusion"] is not None]
    assert len(excluded) == 1
    assert excluded[0]["intersection"]["relation"] == "proxy_overlap_or_contact"
    assert excluded[0]["policy_exclusion"]["reason"] == exclusion.reason
    assert result["automatic_adjacency_exclusions"] is False
    assert result["physical_collision_free"] is None
    assert result["complete_robot_obstacle_or_swept_coverage"] is False


@pytest.mark.parametrize("bad", (float("nan"), float("inf"), True, -1))
def test_invalid_tolerance_even_for_empty_scene(bad):
    with pytest.raises(ValueError):
        screen_proxies((), numerical_tolerance_m=bad)
    with pytest.raises(ValueError):
        intersect_boxes(box(), box("b"), numerical_tolerance_m=bad)


@pytest.mark.parametrize(
    "case",
    (
        "negative_half",
        "reflection",
        "nonfinite",
        "unknown_frame",
        "unsupported_enclosure",
        "reversed_aabb",
    ),
)
def test_invalid_box_contracts(case):
    with pytest.raises(ValueError):
        if case == "negative_half":
            box(half=(-1, 1, 1))
        elif case == "reflection":
            BoxProxy("a", "f", (1, 1, 1), ((-1, 0, 0, 0), *IDENTITY[1:]), "fixture")
        elif case == "nonfinite":
            box(center=(float("nan"), 0, 0))
        elif case == "unknown_frame":
            intersect_boxes(box(), box("b", frame="unknown"))
        elif case == "unsupported_enclosure":
            BoxProxy("a", "f", (1, 1, 1), IDENTITY, "fixture", "physical_enclosure_verified")
        elif case == "reversed_aabb":
            AABB((2, 0, 0), (1, 1, 1))


@pytest.mark.parametrize(
    "case",
    (
        "duplicates",
        "foreign_pair",
        "duplicate_exclusion",
        "pair_budget",
        "bool_budget",
        "same_id_exclusion",
        "empty_reason",
    ),
)
def test_invalid_scene_policies(case):
    with pytest.raises(ValueError):
        if case == "duplicates":
            screen_proxies((box(), box()))
        elif case == "foreign_pair":
            screen_proxies((box(),), (PairExclusion("a", "missing", "reason", "evidence"),))
        elif case == "duplicate_exclusion":
            screen_proxies(
                (box(), box("b")),
                (PairExclusion("a", "b", "r", "e"), PairExclusion("b", "a", "r", "e")),
            )
        elif case == "pair_budget":
            screen_proxies((box(), box("b")), max_pairs=0)
        elif case == "bool_budget":
            screen_proxies((), max_pairs=True)
        elif case == "same_id_exclusion":
            PairExclusion("a", "a", "r", "e")
        elif case == "empty_reason":
            PairExclusion("a", "b", "", "e")


def test_no_silent_robot_coverage_or_contact_exclusions():
    report = study.build_study()
    coverage = report["source_coverage"]
    assert coverage["installed_leaf_count"] == 518
    assert sum(coverage["wrist_motion_class_counts"].values()) == 518
    assert coverage["mounted_full_shape_proxy_bindings_verified"] == 0
    assert coverage["robot_geometry_proxies_constructed"] == 0
    assert coverage["robot_pair_exclusions"] == []
    assert not coverage["robot_intended_contact_exclusion_audit_complete"]
    assert not any(report["qualification"].values())
    assert report["synthetic_witnesses"]["scene"]["physical_collision_free"] is None


def test_report_input_hashes_and_reproduction():
    actual = json.loads(json.dumps(study.build_study()))
    expected = json.loads((ROOT / "hardware/cad/thor-collision-study-v1.json").read_bytes())
    # Only the synthetic nominal-FK transform uses libm; provenance and all
    # discrete fields stay exact. Preserve the existing 1e-12 roundoff boundary.
    a_fk = actual["synthetic_witnesses"].pop("nominal_fk_transform_example")
    e_fk = expected["synthetic_witnesses"].pop("nominal_fk_transform_example")
    a_matrix, e_matrix = (value["proxy"].pop("frame_from_box") for value in (a_fk, e_fk))
    for a_row, e_row in zip(a_matrix, e_matrix, strict=True):
        assert a_row == pytest.approx(e_row, rel=1e-12, abs=1e-12)
    a_bounds, e_bounds = (value.pop("aabb_m") for value in (a_fk, e_fk))
    for key in a_bounds:
        assert a_bounds[key] == pytest.approx(e_bounds[key], rel=1e-12, abs=1e-12)
    assert a_fk == e_fk
    assert actual == expected
    for binding in actual["input_bindings"].values():
        assert (
            hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest()
            == binding["raw_sha256"]
        )


def test_source_membership_binding_mismatch_rejected(tmp_path):
    for relative in study.INPUTS.values():
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    path = tmp_path / study.INPUTS["wrist_membership"]
    value = json.loads(path.read_bytes())
    value["source_geometry_sha256"] = "0" * 64
    path.write_text(json.dumps(value), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        study.build_study(tmp_path)


@pytest.mark.parametrize(
    "role,field,bad",
    (
        ("mounted_inventory", "inventory_revision", True),
        ("mounted_inventory", "coordinate_frame", "unknown"),
        ("mounted_inventory", "validation_class", "physical_geometry_verified"),
        ("mounted_inventory", "native_source_revision", "0" * 40),
        ("wrist_membership", "schema_version", True),
        ("wrist_membership", "schema_version", 3),
        ("wrist_membership", "coordinate_frame", "local_unbound"),
        ("wrist_membership", "validation_class", "physical_geometry_verified"),
        ("wrist_membership", "native_source_revision", "0" * 40),
    ),
)
def test_unsupported_source_semantic_contracts_rejected(tmp_path, role, field, bad):
    for relative in study.INPUTS.values():
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    path = tmp_path / study.INPUTS[role]
    value = json.loads(path.read_bytes())
    value[field] = bad
    path.write_text(json.dumps(value), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="unsupported"):
        study.build_study(tmp_path)


def test_existing_cli_output_preserved(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_bytes(b"preserved")
    assert study.main(["--output", str(path)]) == 2
    assert path.read_bytes() == b"preserved"
