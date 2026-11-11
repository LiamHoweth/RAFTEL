"""Host guards and bounded sampling; never substitutes for a native measurement."""

import copy
import hashlib
import json
import math
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = runpy.run_path(
    str(Path(__file__).parents[1] / "tools/probe_thor_metric_semantics_freecad.py")
)


def selections():
    return [
        dict(
            selection_id=name,
            source_sha256=pins[0],
            brep_entry=pins[1],
            brep_sha256=pins[2],
            object_name="Body",
            uniform_density=None,
            tessellation=None,
        )
        for name, pins in TOOLS["PINNED"].items()
    ]


def test_exact_cached_archive_and_brep_identity_required():
    assert TOOLS["validate_metric_selections"](selections()) == selections()


@pytest.mark.parametrize(
    "key,value",
    [
        ("source_sha256", "a" * 64),
        ("brep_sha256", "a" * 64),
        ("brep_entry", "Other.brp"),
        ("object_name", "Pocket018"),
        ("uniform_density", 1000),
        ("tessellation", {}),
        ("selection_id", "unknown"),
    ],
)
def test_metric_selection_changes_reject(key, value):
    rows = selections()
    rows[0][key] = value
    with pytest.raises(ValueError):
        TOOLS["validate_metric_selections"](rows)


def test_missing_or_duplicate_selection_rejects():
    rows = selections()
    for malformed in (rows[:1], rows + [copy.deepcopy(rows[0])], [rows[0], rows[0]]):
        with pytest.raises(ValueError):
            TOOLS["validate_metric_selections"](malformed)


def test_tetrahedral_integral_and_translation_use_actual_triangles():
    points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    faces = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)]
    for shifted in (
        points,
        [tuple(v + d for v, d in zip(p, (10, -20, 30), strict=True)) for p in points],
    ):
        result = TOOLS["mesh_summary"](shifted, faces)
        assert result["oriented_triangle_integral_mm3"] == pytest.approx(1 / 6)
        assert result["closed_manifold_or_self_intersection_proven"] is False
    reversed_faces = [tuple(reversed(f)) for f in faces]
    assert TOOLS["mesh_summary"](points, reversed_faces)[
        "oriented_triangle_integral_mm3"
    ] == pytest.approx(-1 / 6)


@pytest.mark.parametrize(
    "points,faces",
    [
        ([], []),
        ([(0, 0, math.nan)], [(0, 0, 0)]),
        ([(0, 0, 0)], [(0, 0, True)]),
        ([(0, 0, 0)], [(0, 0, 1)]),
        ([(0, 0, 0)], [(0, 0)]),
    ],
)
def test_malformed_or_nonfinite_mesh_rejects(points, faces):
    with pytest.raises(ValueError):
        TOOLS["mesh_summary"](points, faces)


def test_sampling_is_bounded_deterministic_and_keeps_coordinate_extrema():
    points = [(float(i), float(i % 7), -float(i % 11)) for i in range(1000)]
    sampled = TOOLS["sample_points"](points)
    assert sampled == TOOLS["sample_points"](list(reversed(points)) + points)
    assert len(sampled) <= 96
    for axis in range(3):
        assert min(p[axis] for p in sampled) == min(p[axis] for p in points)
        assert max(p[axis] for p in sampled) == max(p[axis] for p in points)


def test_worker_requires_explicit_opt_in_before_native_import(monkeypatch):
    monkeypatch.delenv(TOOLS["FLAG"], raising=False)
    with pytest.raises(ValueError, match="opt-in"):
        TOOLS["native_capture"]()


def test_distance_targets_faces_and_keeps_sampling_limit_explicit():
    targets = []
    boundary = SimpleNamespace(Solids=[])

    class Vertex:
        def __init__(self, *point):
            self.point = point

        def distToShape(self, target, tolerance):
            targets.append(target)
            assert tolerance == 1e-7
            return (0.75, [(self.point, self.point)], [])

    part = SimpleNamespace(makeCompound=lambda faces: boundary, Vertex=Vertex)
    target = SimpleNamespace(Faces=["face"], Solids=["solid"])
    result = TOOLS["directed_samples"](part, [(1, 1.5, 2)], target)
    assert targets == [boundary]
    assert result["maximum_sampled_distance_mm"] == 0.75
    assert result["true_maximum_or_Hausdorff_distance_proven"] is False


@pytest.mark.parametrize("kind", ["solid_target", "nan_distance", "no_solution"])
def test_unusable_boundary_distance_fails_closed(kind):
    boundary = SimpleNamespace(Solids=["unexpected"] if kind == "solid_target" else [])
    distance = math.nan if kind == "nan_distance" else 0
    pairs = [] if kind == "no_solution" else [((), ())]
    part = SimpleNamespace(
        makeCompound=lambda faces: boundary,
        Vertex=lambda *point: SimpleNamespace(distToShape=lambda *args: (distance, pairs, [])),
    )
    with pytest.raises(ValueError):
        TOOLS["directed_samples"](part, [(0, 0, 0)], SimpleNamespace(Faces=[]))


def test_nested_helper_native_execution_is_rejected(monkeypatch):
    monkeypatch.setenv(TOOLS["FLAG"], "1")
    monkeypatch.setenv("RAFTEL_RUN_THOR_SOLID_PROPERTIES", "1")
    with pytest.raises(ValueError, match="nested"):
        TOOLS["native_capture"]()


def isolated(monkeypatch, tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    for name in ("home", "data", "temp", "sources"):
        (root / name).mkdir()
    (root / "request.json").write_text("{}")
    values = {
        TOOLS["FLAG"]: "1",
        "RAFTEL_METRIC_RUN_DIR": str(root),
        "RAFTEL_METRIC_REQUEST": str(root / "request.json"),
        "RAFTEL_METRIC_SOURCE_ROOT": str(root / "sources"),
        "RAFTEL_METRIC_REPORT": str(root / "probe.json"),
        "FREECAD_USER_HOME": str(root / "home"),
        "FREECAD_USER_DATA": str(root / "data"),
        "FREECAD_USER_TEMP": str(root / "temp"),
        "PYTHONNOUSERSITE": "1",
    }
    monkeypatch.delenv("RAFTEL_RUN_THOR_SOLID_PROPERTIES", raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return root


@pytest.mark.parametrize("fault", ["outside_report", "outside_home", "existing_report", "low_disk"])
def test_run_isolation_preserves_existing_evidence(monkeypatch, tmp_path, fault):
    root = isolated(monkeypatch, tmp_path)
    if fault == "outside_report":
        monkeypatch.setenv("RAFTEL_METRIC_REPORT", str(tmp_path / "outside.json"))
    elif fault == "outside_home":
        monkeypatch.setenv("FREECAD_USER_HOME", str(tmp_path))
    elif fault == "existing_report":
        (root / "probe.json").write_text("preserved")
    else:
        monkeypatch.setattr(
            TOOLS["_paths"].__globals__["shutil"],
            "disk_usage",
            lambda _: type("Disk", (), {"free": 0})(),
        )
    with pytest.raises(ValueError, match="isolated"):
        TOOLS["_paths"]()
    if fault == "existing_report":
        assert (root / "probe.json").read_text() == "preserved"


def test_retained_metric_evidence_preserves_cache_and_integration_uncertainty():
    root = Path(__file__).parents[2]
    receipt = json.loads(
        (root / "arm-01/hardware/cad/thor-native-metric-semantics.json").read_text()
    )
    actual = receipt["actual_native_experiment"]
    capture_path = root / actual["capture_path"]
    runner_path = root / actual["runner_path"]
    assert hashlib.sha256(capture_path.read_bytes()).hexdigest() == actual["capture_sha256"]
    assert hashlib.sha256(runner_path.read_bytes()).hexdigest() == actual["runner_sha256"]
    report = json.loads(capture_path.read_text())
    assert report["audit_status"] == "complete_diagnostic_not_equivalence"
    assert report["open_document_count_before"] == report["open_document_count_after"] == 0
    assert report["input_copy_bytes_unchanged"] and report["retained_inputs_unchanged"]
    assert not report["native_document_saved"] and not report["document_opened_or_recomputed"]
    assert all(value is False for value in actual["qualification"].values())
    source = report["selections"]["source"]
    candidate = report["selections"]["candidate"]
    assert (
        source["properties"]["aggregate"]["volume_mm3"]
        - candidate["properties"]["aggregate"]["volume_mm3"]
        > 3.65
    )
    assert (
        abs(source["optimal_unmeshed_bounds_mm"][-1] - candidate["optimal_unmeshed_bounds_mm"][-1])
        < 1e-6
    )
    assert report["interior_box_control"]["minimum_solid_distance_mm"] == 0
    assert report["interior_box_control"]["distance_to_boundary_faces_mm"] == pytest.approx(0.75)
    for level in report["mesh_convergence"]:
        for row in level["shapes"].values():
            before = row["native_metrics_before_meshing"]
            after = row["native_metrics_after_meshing"]
            assert before["aggregate"] == after["aggregate"]
            assert before["native_bounds_mm"] != after["native_bounds_mm"]
            assert row["directed_boundary_samples"]["sample_count"] <= 96
            assert (
                row["directed_boundary_samples"]["true_maximum_or_Hausdorff_distance_proven"]
                is False
            )
    for direction in ("source_minus_candidate", "candidate_minus_source"):
        assert report[direction] == dict(
            is_null=False, solid_count=0, face_count=0, edge_count=0, volume_mm3=0.0
        )
    assert receipt["conclusions"]["actual_Art1_discrepancy_fully_explained"] is False
