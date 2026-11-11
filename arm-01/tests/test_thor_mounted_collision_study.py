"""Saved-zero numerical pair coverage and strict pinned input/policy contracts."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "thor_mounted_collision_study", ROOT / "tools/thor_mounted_collision_study.py"
)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


@pytest.fixture(scope="module")
def inputs():
    return (ROOT / study.CAPTURE_PATH).read_bytes(), (ROOT / study.INVENTORY_PATH).read_bytes()


def fixture_row(name, low, high, *, default_low=None, default_high=None):
    return {
        "instance_id": name,
        "root_subassembly": "synthetic_group",
        "world_optimal_bounds_m": [low, high],
        "world_default_bounds_m": [default_low or low, default_high or high],
    }


def test_three_box_contact_separated_and_explicit_metric_comparison():
    rows = [
        fixture_row("a", [0, 0, 0], [1, 1, 1]),
        fixture_row("b", [1, 0, 0], [2, 1, 1]),
        fixture_row("c", [3, 0, 0], [4, 1, 1], default_low=[1.5, 0, 0]),
    ]
    report = study.derive_pairs(rows)
    assert report["counts"]["total_pairs"] == 3
    assert report["counts"]["optimal_overlap_or_contact"] == 1
    assert report["counts"]["default_overlap_or_contact"] == 2
    assert report["counts"]["default_only_candidate"] == 1
    candidate = report["optimal_overlap_candidates"][0]
    assert (candidate["left_index"], candidate["right_index"]) == (0, 1)
    assert candidate["optimal_axis_gaps_m"] == (0, -1, -1)
    assert candidate["optimal_contact_classification"] == "within_numerical_tolerance"
    assert candidate["sat_confirmation_relation"] == "proxy_overlap_or_contact"
    alternative = report["default_only_candidates"][0]
    assert (alternative["left_index"], alternative["right_index"]) == (1, 2)
    assert alternative["optimal_axis_gaps_m"] == (1, -1, -1)
    assert alternative["default_axis_gaps_m"] == (-0.5, -1, -1)
    assert report["candidate_pair_exclusions"] == []
    assert report["intended_contact_audit_complete"] is False


def test_identical_boxes_and_adjacent_named_groups_are_not_excluded():
    rows = [
        fixture_row(name, [0, 0, 0], [1, 1, 1]) for name in ("joint1", "joint2", "bearing", "motor")
    ]
    report = study.derive_pairs(rows)
    assert report["counts"]["total_pairs"] == 6
    assert len(report["optimal_overlap_candidates"]) == 6
    assert all(
        row["optimal_contact_classification"] == "interior_overlap"
        for row in report["optimal_overlap_candidates"]
    )
    assert report["counts"]["sat_confirmation_disagreements"] == 0


def test_exact_numerical_boundary_retained_despite_sat_roundoff_disagreement():
    rows = [
        fixture_row("a", [-1, 0, 0], [0, 1, 1]),
        fixture_row("b", [1e-12, 0, 0], [1, 1, 1]),
    ]
    report = study.derive_pairs(rows)
    assert report["counts"]["optimal_overlap_or_contact"] == 1
    candidate = report["optimal_overlap_candidates"][0]
    assert candidate["optimal_axis_gaps_m"][0] == study.POLICY["numerical_tolerance_m"]
    assert candidate["optimal_contact_classification"] == "within_numerical_tolerance"
    assert candidate["sat_confirmation_relation"] == "no_proxy_overlap"
    assert report["counts"]["sat_confirmation_disagreements"] == 1
    # Centre/half-width cancellation must not silently remove an endpoint-policy candidate.
    assert len(report["optimal_overlap_candidates"]) == 1


@pytest.mark.parametrize(
    "field,value",
    (
        ("selected_bounds_field", "world_default_bounds_m"),
        ("coordinate_units", "mm"),
        ("enclosure_status", "verified"),
        ("pair_exclusions", [["a", "b"]]),
        ("automatic_adjacency_exclusions", True),
        ("schema_version", True),
        ("numerical_tolerance_m", 1e-3),
    ),
)
def test_policy_changes_reject_instead_of_silently_changing_meaning(field, value):
    policy = copy.deepcopy(study.POLICY)
    policy[field] = value
    with pytest.raises(ValueError, match="policy"):
        study.derive_pairs([], policy=policy)


@pytest.mark.parametrize(
    "mutation",
    (
        "schema_bool",
        "source_revision",
        "units_frame",
        "evidence_class",
        "inventory_hash",
        "missing_identity",
        "duplicate_identity",
        "foreign_identity",
        "wrong_object",
        "wrong_root",
        "enclosure_true",
        "global_enclosure_true",
        "qualification_true",
        "missing_fixture",
        "fixture_failed",
        "fixture_error",
        "wrong_count",
        "state_erased",
        "recompute_true",
        "nonfinite_bounds",
        "reversed_bounds",
        "missing_bounds",
        "source_changed",
    ),
)
def test_source_capture_negative_fixtures(inputs, mutation):
    capture_raw, inventory_raw = inputs
    value = json.loads(capture_raw)
    first = value["instances"][0]
    if mutation == "schema_bool":
        value["schema_version"] = True
    elif mutation == "source_revision":
        value["cad_revision"] = "0" * 40
    elif mutation == "units_frame":
        value["frame"] = "native frame millimetres"
    elif mutation == "evidence_class":
        value["evidence_class"] = "conservative_collision_boxes"
    elif mutation == "inventory_hash":
        value["inventory_sha256"] = "0" * 64
    elif mutation == "missing_identity":
        value["instances"].pop()
    elif mutation == "duplicate_identity":
        first["instance_id"] = value["instances"][1]["instance_id"]
    elif mutation == "foreign_identity":
        first["instance_id"] = "unknown_source_instance"
    elif mutation == "wrong_object":
        first["object_reference"] = "wrong::object"
    elif mutation == "wrong_root":
        first["root_subassembly"] = "wrong_root"
    elif mutation == "enclosure_true":
        first["enclosure_verified"] = True
    elif mutation == "global_enclosure_true":
        value["physical_enclosure_verified"] = True
    elif mutation == "qualification_true":
        value["collision_clearance_accepted"] = True
    elif mutation == "missing_fixture":
        value["synthetic_coordinate_fixture"]["cases"].pop()
    elif mutation == "fixture_failed":
        value["synthetic_coordinate_fixture"]["passed"] = False
    elif mutation == "fixture_error":
        value["synthetic_coordinate_fixture"]["cases"][0]["maximum_extremum_error_mm"] = 1
    elif mutation == "wrong_count":
        value["captured_bounds_count"] = True
    elif mutation == "state_erased":
        value["final_state_counts"] = {"Up-to-date": 3001}
    elif mutation == "recompute_true":
        value["native_scope"]["changed_recompute_requested"] = True
    elif mutation == "nonfinite_bounds":
        first["world_optimal_bounds_m"][0][0] = float("nan")
    elif mutation == "reversed_bounds":
        first["world_optimal_bounds_m"][0][0] = 1e6
    elif mutation == "missing_bounds":
        first.pop("world_optimal_bounds_m")
    elif mutation == "source_changed":
        value["source_copy_bytes_unchanged"] = False
    raw = json.dumps(value).encode()
    with pytest.raises(ValueError):
        study.validate_inputs(
            raw, inventory_raw, expected_capture_sha256=hashlib.sha256(raw).hexdigest()
        )


def test_raw_byte_pin_and_inventory_schema_reject(inputs):
    capture_raw, inventory_raw = inputs
    with pytest.raises(ValueError, match="frozen input pin"):
        study.validate_inputs(capture_raw + b" ", inventory_raw)
    inventory = json.loads(inventory_raw)
    inventory["inventory_revision"] = True
    modified_inventory = json.dumps(inventory).encode()
    capture = json.loads(capture_raw)
    capture["inventory_sha256"] = hashlib.sha256(modified_inventory).hexdigest()
    modified_capture = json.dumps(capture).encode()
    with pytest.raises(ValueError, match="inventory semantic"):
        study.validate_inputs(
            modified_capture,
            modified_inventory,
            expected_capture_sha256=hashlib.sha256(modified_capture).hexdigest(),
        )


def test_all_source_identities_and_units_are_used_once(inputs):
    capture, rows = study.validate_inputs(*inputs)
    assert len(rows) == 518
    assert [row["instance_id"] for row in rows] == sorted(row["instance_id"] for row in rows)
    assert capture["frame"] == study.FRAME
    assert all(row["enclosure_verified"] is False for row in rows)
    base = next(row for row in rows if row["instance_id"].endswith("AssemblyBase::BaseBot_BaseBot"))
    # Worker already converted native mm to m; do not divide by1000 again.
    assert base["world_optimal_bounds_m"][1][0] == pytest.approx(0.10000000019999988)


def test_tracked_report_reproduces_all_pairs_and_keeps_qualification_unknown(inputs):
    actual = json.loads(json.dumps(study.build_study(*inputs)))
    expected = json.loads((ROOT / "hardware/cad/thor-mounted-collision-study-v1.json").read_bytes())
    assert actual == expected
    assert actual["policy_canonical_sha256"] == study.canonical_sha256(actual["policy"])
    coverage = actual["proxy_coverage"]
    assert coverage["numerical_AABB_proxies"] == 518
    assert coverage["verified_geometry_enclosures"] == 0
    pairs = actual["pair_diagnostics"]
    assert pairs["counts"]["total_pairs"] == 518 * 517 // 2
    assert pairs["counts"]["optimal_overlap_or_contact"] == len(pairs["optimal_overlap_candidates"])
    assert pairs["counts"]["default_only_candidate"] == len(pairs["default_only_candidates"])
    assert pairs["counts"]["total_pairs"] == sum(
        pairs["counts"][key]
        for key in (
            "both_metrics_candidate",
            "optimal_only_candidate",
            "default_only_candidate",
            "neither_metric_candidate",
        )
    )
    assert not pairs["candidate_pair_exclusions"]
    assert actual["physical_collision_free"] is None
    assert actual["swept_path_clearance"] is None
    assert not any(actual["qualification"].values())
    registry = actual["proxy_registry"]
    indices = {
        (row["left_index"], row["right_index"]) for row in pairs["optimal_overlap_candidates"]
    }
    assert len(indices) == len(pairs["optimal_overlap_candidates"])
    assert all(0 <= a < b < len(registry) for a, b in indices)


def test_existing_cli_output_preserved(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_bytes(b"preserved")
    assert study.main(["--output", str(path)]) == 2
    assert path.read_bytes() == b"preserved"
