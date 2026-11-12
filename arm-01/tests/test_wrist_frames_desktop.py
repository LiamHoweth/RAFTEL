"""Host-only marker geometry and isolated native entry guards."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "new_wrist_probe", ROOT / "tools/probe_thor_wrist_frames_desktop.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def envelope(tmp_path, monkeypatch):
    monkeypatch.setattr(probe.shutil, "disk_usage", lambda _: SimpleNamespace(free=100 * 1024**3))
    source = tmp_path / "source"
    source.mkdir()
    worker = tmp_path / "worker.py"
    worker.write_text("# immutable worker\n", encoding="utf-8")
    result = {
        "copied_source_root": str(source),
        "report_path": str(tmp_path / "new.json"),
        "worker_sha256": probe.sha(worker),
        "module_pins": {},
    }
    for key, filename in (
        ("request", "request.json"),
        ("audit_helper", "audit.py"),
        ("pose_helper", "pose.py"),
        ("contract_helper", "contract.py"),
    ):
        path = tmp_path / filename
        path.write_text("{}\n", encoding="utf-8")
        result[key + "_path"] = str(path)
        result[key + "_sha256"] = probe.sha(path)
    result["expected_runtime_paths"] = {}
    for key in probe.PATH_KEYS:
        path = tmp_path / (key + ".cfg" if key.endswith("Parameter") else key)
        if not key.endswith("Parameter"):
            path.mkdir()
        result["expected_runtime_paths"][key] = str(path)
    for name in (
        "FastenersCmd",
        "freecad.gears.features",
        "pygears.involute_tooth",
        "pygears.bevel_tooth",
    ):
        result["module_pins"][name] = {"root": str(source), "sha256": "1" * 64}
    return result, worker


def test_marker_frame_uses_real_noncollinear_geometry_and_fixed_vertex_indices():
    points = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [1, 0, 4]]
    indices = probe.select_marker_indices(points)
    assert len(set(indices)) == 3
    frame = probe.marker_frame([points[i] for i in indices])
    assert frame[3] == [0, 0, 0, 1]
    moved = [[-p[1] + 7, p[0] + 8, p[2] + 9] for p in points]
    actual = probe.marker_frame([moved[i] for i in indices])
    for row, expected in zip(
        actual[:3],
        [[-v for v in frame[1][:3]] + [7], frame[0][:3] + [8], frame[2][:3] + [9]],
        strict=True,
    ):
        assert row == pytest.approx(expected)


@pytest.mark.parametrize(
    "points",
    [[[0, 0, 0]] * 3, [[0, 0, 0], [1, 1, 1], [2, 2, 2]], [[True, 0, 0], [1, 0, 0], [0, 1, 0]]],
)
def test_degenerate_or_nonfinite_native_marker_is_rejected(points):
    with pytest.raises(ValueError):
        probe.marker_frame(points)


def test_exact_five_path_snapshot_envelope(tmp_path, monkeypatch):
    request, worker = envelope(tmp_path, monkeypatch)
    assert probe.validate_envelope(request, tmp_path, worker) == request


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d, p: d.update(extra=True),
        lambda d, p: d.update(copied_source_root=str(p)),
        lambda d, p: d.update(worker_sha256="0" * 64),
        lambda d, p: d.update(contract_helper_sha256="0" * 64),
        lambda d, p: d["expected_runtime_paths"].update(UserHomePath=str(p)),
        lambda d, p: d["expected_runtime_paths"].update(UserHomePath=d["copied_source_root"]),
        lambda d, p: d.update(request_path=d["expected_runtime_paths"]["UserParameter"]),
        lambda d, p: d["expected_runtime_paths"].update(
            UserHomePath=d["expected_runtime_paths"]["UserAppData"]
        ),
        lambda d, p: d["module_pins"].update(unknown={"root": str(p.parent), "sha256": "0" * 64}),
    ],
)
def test_envelope_rejects_scope_pin_kind_and_path_alias_errors(tmp_path, monkeypatch, mutation):
    request, worker = envelope(tmp_path, monkeypatch)
    mutation(request, worker)
    with pytest.raises(ValueError):
        probe.validate_envelope(request, tmp_path, worker)


@pytest.mark.parametrize(
    "raw", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', "[" * 34 + "0" + "]" * 34]
)
def test_json_guards_preserve_ambiguous_nonfinite_and_bounded_inputs(tmp_path, raw):
    path = tmp_path / "request.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        probe.read_json(path)


def test_json_over_size_is_rejected_before_parse(tmp_path):
    path = tmp_path / "large.json"
    path.write_text(" " * (1024 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ValueError, match="1 MiB"):
        probe.read_json(path)


def test_optin_precedes_any_native_import_or_input_read(monkeypatch):
    monkeypatch.delenv(probe.FLAG, raising=False)
    with pytest.raises(ValueError, match="opt-in"):
        probe.native_capture()


def test_request_json_is_plain_standard_json(tmp_path):
    path = tmp_path / "request.json"
    value = {
        "schema_version": 1,
        "poses": [{"name": n, "q5_rad": a, "q6_rad": b} for n, a, b in probe.POSES],
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    assert probe.read_json(path) == value
