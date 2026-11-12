import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PureWindowsPath

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "printed_frames", ROOT / "tools/probe_thor_printed_tensor_frames.py"
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_markers_authenticate_nonidentity_translation_and_rotation_without_com_fit():
    source = [[0, 0, 0], [2, 0, 0], [0, 3, 0], [0, 0, 4]]
    transform = [[0, -1, 0, 7], [1, 0, 0, 11], [0, 0, 1, -5], [0, 0, 0, 1]]
    target = [[7 - y, 11 + x, -5 + z] for x, y, z in source]
    result = probe.marker_check(source, target, transform)
    assert result["all_ordered_vertices_checked"] == 4
    assert result["maximum_marker_error_mm"] == 0
    inverse = probe.inverse_rigid(transform)
    assert [probe.point(inverse, point) for point in target] == source
    wrong = [point[:] for point in target]
    wrong[3][0] += 0.01
    with pytest.raises(ValueError, match="disagree"):
        probe.marker_check(source, wrong, transform)


@pytest.mark.parametrize("source", [[], [[0, 0, 0]] * 4, [[i, 0, 0] for i in range(4)]])
def test_degenerate_markers_cannot_authenticate_frame(source):
    identity = [[float(i == j) for j in range(4)] for i in range(4)]
    with pytest.raises(ValueError):
        probe.marker_check(source, source, identity)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 2, -1])
def test_improper_or_nonfinite_delta_rejected(bad):
    transform = [[float(i == j) for j in range(4)] for i in range(4)]
    transform[0][0] = bad
    with pytest.raises(ValueError):
        probe.validate_rigid(transform)


def test_transformed_box_geometric_tensor_covariance_and_volume_gate():
    source = {
        "volume_mm3": 24,
        "com_mm": [1, 1.5, 2],
        "centroidal_geometric_inertia_mm5": [[50, 0, 0], [0, 40, 0], [0, 0, 26]],
    }
    target = {
        "volume_mm3": 24,
        "com_mm": [5.5, 12, -3],
        "centroidal_geometric_inertia_mm5": [[40, 0, 0], [0, 50, 0], [0, 0, 26]],
    }
    transform = [[0, -1, 0, 7], [1, 0, 0, 11], [0, 0, 1, -5], [0, 0, 0, 1]]
    result = probe.metric_check(source, target, transform)
    assert all(value == 0 for value in result.values())
    target["volume_mm3"] = 25
    with pytest.raises(ValueError, match="covariance"):
        probe.metric_check(source, target, transform)


def test_entry_flags_rejected_before_native_import(monkeypatch):
    monkeypatch.delenv(probe.FLAG, raising=False)
    with pytest.raises(ValueError, match="opt-in"):
        probe.capture()
    monkeypatch.setenv(probe.FLAG, "1")
    monkeypatch.setenv("RAFTEL_RUN_FREECAD_AUDIT", "1")
    with pytest.raises(ValueError, match="conflicting"):
        probe.capture()


def test_rigid_inverse_roundtrip_varied_scales():
    for angle in [0.01, 0.7, -2.2]:
        c, s = math.cos(angle), math.sin(angle)
        transform = [[c, -s, 0, 100], [s, c, 0, -23], [0, 0, 1, 500], [0, 0, 0, 1]]
        identity = probe.product(probe.inverse_rigid(transform), transform)
        for i in range(4):
            for j in range(4):
                assert identity[i][j] == pytest.approx(float(i == j), abs=1e-12)


@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf")])
def test_typed_finite_authentication_rejects_ambiguous_numbers(bad):
    identity = [[float(i == j) for j in range(4)] for i in range(4)]
    matrix = copy.deepcopy(identity)
    matrix[0][0] = bad
    with pytest.raises(ValueError):
        probe.validate_rigid(matrix)
    source = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    with pytest.raises(ValueError):
        probe.marker_check(source, source, identity, tolerance_mm=bad)
    vertices = copy.deepcopy(source)
    vertices[0][0] = bad
    with pytest.raises(ValueError):
        probe.marker_check(vertices, source, identity)
    metrics = {
        "volume_mm3": 24.0,
        "com_mm": [1.0, 1.5, 2.0],
        "centroidal_geometric_inertia_mm5": [[50.0, 0.0, 0.0], [0.0, 40.0, 0.0], [0.0, 0.0, 26.0]],
    }
    for field in ["volume", "com", "tensor"]:
        wrong = copy.deepcopy(metrics)
        if field == "volume":
            wrong["volume_mm3"] = bad
        elif field == "com":
            wrong["com_mm"][0] = bad
        else:
            wrong["centroidal_geometric_inertia_mm5"][0][0] = bad
        with pytest.raises(ValueError):
            probe.metric_check(metrics, wrong, identity)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b"[]", b"\xff"])
def test_request_rejects_ambiguous_nonfinite_or_non_utf8_json(tmp_path, raw):
    path = tmp_path / "request.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        probe.strict_request(path)


def test_containment_guard_rejects_external_and_missing_inputs(tmp_path):
    inside = tmp_path / "run"
    inside.mkdir()
    (tmp_path / "outside.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        probe.contained_file(inside, "../outside.json")
    with pytest.raises(ValueError):
        probe.contained_file(inside, "missing.json")


def test_retained_native_capture_replays_all65_markers_and_actual_source_paths():
    capture = json.loads(
        (ROOT / "hardware/cad/thor-printed-tensor-frames-v1.json").read_text(encoding="utf-8")
    )
    assert capture["status"] == "complete_frame_authentication"
    assert capture["complete_65_printed_coverage"]
    assert capture["authenticated_instance_count"] == 65
    assert capture["installed_leaf_count"] == 518
    assert capture["open_document_count_before"] == capture["open_document_count_after"] == 0
    assert capture["preexisting_documents_preserved"] and capture["source_copy_bytes_unchanged"]
    assert not capture["source_assembly_recomputed"] and not capture["cad_saved"]
    assert len(capture["loaded_document_sources"]) == 53
    parents = set()
    for row in capture["loaded_document_sources"]:
        path = PureWindowsPath(row["path"])
        parents.add(path.parent)
        assert capture["source_copy_sha256_before"][path.name] == row["sha256"]
    assert len(parents) == 1
    assert next(iter(parents)).name == "source"
    variants = {row["selection_id"]: row for row in capture["variants"]}
    assert len(variants) == 47
    assert len({row["instance_id"] for row in capture["instances"]}) == 65
    for row in capture["instances"]:
        variant = variants[row["selection_id"]]
        assert row["status"] == "authenticated"
        markers = probe.marker_check(
            variant["source_vertices_mm"],
            row["installed_vertices_mm"],
            row["source_raw_to_installed_raw_mm"],
        )
        for key, value in markers.items():
            if isinstance(value, float):
                assert row["marker_check"][key] == pytest.approx(value, rel=1e-12, abs=1e-15)
            else:
                assert row["marker_check"][key] == value
        probe.metric_check(
            variant["cached_shape_properties"]["aggregate"],
            row["installed_raw_metrics"]["aggregate"],
            row["source_raw_to_installed_raw_mm"],
        )
    derived = capture.pop("publication_provenance")
    serialized = (json.dumps(capture, indent=2, allow_nan=False) + "\n").encode("utf-8")
    assert hashlib.sha256(serialized).hexdigest() == derived["actual_raw_capture_sha256"]
    assert (
        capture["worker_sha256"]
        == hashlib.sha256(
            (ROOT / "tools/probe_thor_printed_tensor_frames.py").read_bytes()
        ).hexdigest()
    )
