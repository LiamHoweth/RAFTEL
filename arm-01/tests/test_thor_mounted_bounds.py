"""Guard and coordinate-composition tests; no FreeCAD dependency or process."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools/probe_thor_mounted_bounds_freecad.py"
spec = importlib.util.spec_from_file_location("mounted_bounds_tool", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_pinned_source_and_inventory_inputs_are_exact():
    sources, ids = module.pinned_inputs(
        ROOT / "hardware/cad/thor-baseline-inspection.json",
        ROOT / "hardware/cad/thor-mounted-geometry-v2.json",
    )
    assert len(sources) == 57 and len(ids) == 518
    assert sources["Art1Body.fcstd"] == module.STATIC_ART1_SHA256
    assert (
        sources["Assembly.FCStd"]
        == "5ee729246229e7494466010ab68e2c2367ba4ec1361b7701df21c0f8b00c2c1b"
    )


def test_mutable_inspection_cannot_change_source_hashes(tmp_path):
    path = tmp_path / "inspection.json"
    value = json.loads((ROOT / "hardware/cad/thor-baseline-inspection.json").read_text())
    value["files"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="pinned JSON"):
        module.pinned_inputs(path, ROOT / "hardware/cad/thor-mounted-geometry-v2.json")


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', "[]"])
def test_json_rejects_duplicates_nonfinite_and_nonobject(tmp_path, raw):
    path = tmp_path / "input.json"
    path.write_text(raw)
    with pytest.raises(ValueError):
        module.strict_json(path)


@pytest.mark.parametrize("bad", ["../x", "/absolute", "C:/x", "a\\b", "a//b", "a/./b", ""])
def test_unsafe_source_names_are_rejected(bad):
    with pytest.raises(ValueError, match="relative POSIX"):
        module.safe_relative(bad)


def test_verify_files_checks_actual_content_and_retains_it(tmp_path):
    path = tmp_path / "source.FCStd"
    path.write_bytes(b"pinned fixture only")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert module.verify_files(tmp_path, {path.name: digest}) == {path.name: digest}
    with pytest.raises(ValueError, match="bytes changed"):
        module.verify_files(tmp_path, {path.name: "0" * 64})
    assert path.read_bytes() == b"pinned fixture only"


def test_box_corners_recover_known_extrema():
    bounds = [[-2, -3, 5], [7, 11, 13]]
    points = module.bound_corners(bounds)
    assert len(points) == 8 and len({tuple(p) for p in points}) == 8
    assert module.corner_bounds(points) == bounds


@pytest.mark.parametrize(
    "bounds", [[[2, 0, 0], [1, 1, 1]], [[0, 0, 0], [1, float("inf"), 1]], [[0, 0], [1, 1]]]
)
def test_invalid_bounds_reject(bounds):
    with pytest.raises(ValueError):
        module.bound_corners(bounds)


class Placement:
    def __init__(self, values):
        self.values = values.values if isinstance(values, Matrix) else values

    def multiply(self, other):
        return Placement(
            [
                [sum(self.values[i][k] * other.values[k][j] for k in range(4)) for j in range(4)]
                for i in range(4)
            ]
        )


class Matrix:
    def __init__(self, *values):
        self.values = [list(values[i : i + 4]) for i in range(0, 16, 4)]


class Shape:
    def __init__(self, placement):
        self.Placement = placement

    def copy(self):
        return copy.deepcopy(self)


def test_placed_copy_applies_ancestors_before_own_placement_once():
    # A 90deg ancestor rotation carries the child's +10X to +10Y.
    ancestor = [[0, -1, 0, 100], [1, 0, 0, 20], [0, 0, 1, 0], [0, 0, 0, 1]]
    own = [[1, 0, 0, 10], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    shape = Shape(Placement(own))
    result = module.placed_copy(
        shape, ancestor, SimpleNamespace(Matrix=Matrix, Placement=Placement)
    )
    assert result is not shape
    assert [result.Placement.values[i][3] for i in range(3)] == [100, 30, 0]
    assert shape.Placement.values == own


def test_cleanup_preserves_documents_open_before_probe():
    class App:
        documents = {"Original": object(), "Created": object()}

        def listDocuments(self):
            return dict(self.documents)

        def closeDocument(self, name):
            self.documents.pop(name)

    app = App()
    assert module.close_created_documents(app, {"Original"}) == {"Original"}
    assert set(app.documents) == {"Original"}


def test_native_capture_cannot_start_without_opt_in(monkeypatch):
    monkeypatch.delenv(module.FLAG, raising=False)
    with pytest.raises(ValueError, match="explicit opt-in"):
        module.native_capture()


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_native_disk_reserve_is_explicit_and_fail_closed(monkeypatch, tmp_path, delta):
    free = module.MIN_FREE_BYTES + delta
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _: SimpleNamespace(free=free))
    if delta < 0:
        with pytest.raises(ValueError, match="50 GiB"):
            module.require_disk_reserve(tmp_path)
    else:
        assert module.require_disk_reserve(tmp_path) == free


def test_generic_audit_flag_cannot_execute_imported_helper(monkeypatch):
    monkeypatch.setenv(module.FLAG, "1")
    monkeypatch.setenv("RAFTEL_RUN_FREECAD_AUDIT", "1")
    with pytest.raises(ValueError, match="must be unset"):
        module.native_capture()


def test_helper_pin_prevents_loading_wrong_code(tmp_path):
    path = tmp_path / "helper.py"
    path.write_text("raise RuntimeError('must not execute')")
    with pytest.raises(ValueError, match="snapshot bytes"):
        module.load_snapshot(path, "0" * 64, "wrong_helper")


def test_native_fixture_constants_catch_double_transforms():
    assert module.FIXTURE_EXPECTED_MM["direct_child"] == [[96, 30, 0], [100, 32, 6]]
    assert module.FIXTURE_EXPECTED_MM["link_false"] != module.FIXTURE_EXPECTED_MM["link_true"]
    assert (
        module.FIXTURE_EXPECTED_MM["group_link_false"]
        != module.FIXTURE_EXPECTED_MM["group_link_true"]
    )


def test_actual_bounds_dataset_keeps_complete_identity_and_honest_native_scope():
    data = module.strict_json(ROOT / "hardware/cad/thor-native-mounted-bounds-v1.json")
    _, expected = module.pinned_inputs(
        ROOT / "hardware/cad/thor-baseline-inspection.json",
        ROOT / "hardware/cad/thor-mounted-geometry-v2.json",
    )
    assert len(data["instances"]) == 518
    assert {row["instance_id"] for row in data["instances"]} == expected
    assert data["bounds_gap_count"] == 0 and data["captured_bounds_count"] == 518
    assert data["shape_history_rebuilt"] is False
    assert data["physical_enclosure_verified"] is False
    assert data["collision_clearance_accepted"] is False
    assert data["final_state_counts"] == {"Up-to-date": 1147, "Touched": 1854}


def test_actual_coordinate_traces_use_ancestor_times_own_once_and_finite_bounds():
    data = module.strict_json(ROOT / "hardware/cad/thor-native-mounted-bounds-v1.json")
    for row in data["instances"]:
        ancestor = row["ancestor_transform_mm"]
        own = row["raw_shape_placement"]["matrix"]
        actual = row["copied_world_shape_placement"]["matrix"]
        expected = [
            [math.fsum(ancestor[i][k] * own[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)
        ]
        assert max(abs(actual[i][j] - expected[i][j]) for i in range(4) for j in range(4)) < 1e-8
        module.bound_corners(row["world_optimal_bounds_m"])
        module.bound_corners(row["world_default_bounds_m"])
        assert row["enclosure_verified"] is False
        assert row["raw_shape_placement_unchanged"] is True
        assert math.dist(row["native_world_com_m"], row["zero_world_com_m"]) < 1e-9
