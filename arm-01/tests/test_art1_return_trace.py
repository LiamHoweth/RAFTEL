"""Host guard checks; these never constitute native CAD evidence."""

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOL = Path(__file__).parents[1] / "tools/probe_thor_art1_return_trace.py"
spec = importlib.util.spec_from_file_location("art1_return_trace", TOOL)
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


@pytest.fixture
def packet(tmp_path, monkeypatch):
    base = tmp_path / "project"
    tools = base / "tools"
    history = base / "hardware/cad"
    tools.mkdir(parents=True)
    history.mkdir(parents=True)
    worker = tools / TOOL.name
    worker.write_bytes(TOOL.read_bytes())
    for name in trace.HELPERS:
        (tools / name).write_bytes(b"# retained test helper\n")
    for name in (
        "thor-art1-migration-evidence.json",
        "thor-art1-desktop-candidate-study-v1.json",
        "thor-art1-desktop-candidate-runner-v1.json",
        "thor-art1-desktop-native-evidence-v1.json",
    ):
        (history / name).write_bytes(b"{}\n")
    runtime = tmp_path / "runtime"
    (runtime / "bin").mkdir(parents=True)
    (runtime / "lib").mkdir()
    exe = runtime / "bin/freecadcmd.exe"
    exe.write_bytes(b"console")
    (runtime / "bin/FreeCAD.pyd").write_bytes(b"freecad-module")
    (runtime / "lib/Part.pyd").write_bytes(b"part-module")
    source, candidate = tmp_path / "source.fcstd", tmp_path / "candidate.fcstd"
    source.write_bytes(b"preserved source")
    candidate.write_bytes(b"preserved candidate")
    monkeypatch.setattr(trace, "__file__", str(worker))
    for key, path in (
        ("SOURCE_SHA256", source),
        ("CANDIDATE_SHA256", candidate),
        ("EXECUTABLE_SHA256", exe),
    ):
        monkeypatch.setattr(trace, key, trace.sha(path))
    monkeypatch.setattr(trace.shutil, "disk_usage", lambda _: SimpleNamespace(free=100 * 1024**3))
    root = tmp_path / "run"
    return exe, source, candidate, root


def test_prepare_retains_exact_bytes_and_never_launches(packet, monkeypatch):
    monkeypatch.setenv("RAFTEL_RUN_FREECAD_AUDIT", "1")
    result = trace.prepare_run(*packet)
    root = packet[-1]
    request = trace.strict_request(root / "request.json")
    trace.validate_request(root, request)
    assert result["prepared_only_no_native_launch"] is True
    assert "RAFTEL_RUN_FREECAD_AUDIT" in result["remove_environment"]
    assert len(request["protected_sha256"]) == 7
    assert (root / "inputs/candidate.fcstd").read_bytes() == packet[2].read_bytes()
    assert not (root / "probe.json").exists()
    assert b"\r" not in (root / "request.json").read_bytes()
    assert result["timeout_s"] == 300


@pytest.mark.parametrize("which", [0, 1, 2])
def test_wrong_pin_creates_no_run(packet, which):
    packet[which].write_bytes(b"changed")
    with pytest.raises(ValueError, match="exact pin"):
        trace.prepare_run(*packet)
    assert not packet[-1].exists()


def test_existing_run_is_preserved(packet):
    root = packet[-1]
    root.mkdir()
    sentinel = root / "keep.txt"
    sentinel.write_text("existing evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="new"):
        trace.prepare_run(*packet)
    assert sentinel.read_text(encoding="utf-8") == "existing evidence"


def test_reserve_enforced_before_writes(packet, monkeypatch):
    monkeypatch.setattr(trace.shutil, "disk_usage", lambda _: SimpleNamespace(free=50 * 1024**3))
    with pytest.raises(ValueError, match="reserve"):
        trace.prepare_run(*packet)
    assert not packet[-1].exists()


@pytest.mark.parametrize("kind", ["snapshot", "source", "history", "runtime"])
def test_tamper_detected_by_preservation_ledger(packet, kind):
    trace.prepare_run(*packet)
    root = packet[-1]
    request = trace.strict_request(root / "request.json")
    target = {
        "snapshot": root / "scripts/audit_freecad_assembly.py",
        "source": packet[1],
        "history": Path(
            next(p for p in request["protected_sha256"] if p.endswith("candidate-study-v1.json"))
        ),
        "runtime": Path(request["runtime_modules"]["Part"]["path"]),
    }[kind]
    target.write_bytes(b"tampered")
    with pytest.raises(ValueError):
        trace.validate_request(root, request)


def test_request_inventory_and_protected_shape_are_closed(packet):
    trace.prepare_run(*packet)
    root = packet[-1]
    request = trace.strict_request(root / "request.json")
    for key in ("file_sha256", "protected_sha256", "runtime_modules"):
        malformed = copy.deepcopy(request)
        malformed[key]["unexpected"] = "0" * 64
        with pytest.raises(ValueError):
            trace.validate_request(root, malformed)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b"[]",
        b"x" * (256 * 1024 + 1),
        '{"a":1}'.encode("utf-16"),
        b'{"a":1e999}',
    ],
    ids=["duplicate", "nan", "array", "oversize", "utf16", "overflow"],
)
def test_bounded_strict_utf8_request(tmp_path, raw):
    path = tmp_path / "request.json"
    path.write_bytes(raw)
    with pytest.raises((ValueError, UnicodeError)):
        trace.strict_request(path)


def test_conflicting_flag_rejected_before_any_input_read(monkeypatch):
    monkeypatch.setenv(trace.FLAG, "1")
    monkeypatch.setenv("RAFTEL_RUN_ATTACHMENT_ENGINE", "1")
    monkeypatch.delenv(trace.ROOT_ENV, raising=False)
    with pytest.raises(ValueError, match="conflicting"):
        trace.native_capture()


def test_phase_sequence_keeps_cached_nominal_and_failed_return_separate():
    assert trace.PHASES == (
        ("restored_cached", 1.7),
        ("nominal_forced", 1.7),
        ("radius_minus_0_01_mm", 1.69),
        ("radius_plus_0_01_mm", 1.71),
        ("restored_nominal_radius", 1.7),
    )
    assert json.loads(json.dumps(trace.PHASES))[-1][1] == 1.7


def test_embedded_runtime_does_not_invent_freecad_module_file(packet):
    trace.prepare_run(*packet)
    request = trace.strict_request(packet[-1] / "request.json")
    part = SimpleNamespace(__file__=request["runtime_modules"]["Part"]["path"])
    result = trace.runtime_provenance(SimpleNamespace(), part, request, packet[0])
    assert result["FreeCAD"] == {"origin_kind": "embedded_module_without_file", "module_file": None}
    assert result["process_image"]["sha256"] == trace.EXECUTABLE_SHA256
    assert "FreeCAD" not in request["runtime_modules"]


def test_prior_failed_attempt_is_bound_and_preserved(packet):
    previous = packet[-1].parent / "run-001"
    previous.mkdir()
    failure = previous / "probe.json"
    failure.write_bytes(b'{"status":"failed_diagnostic"}\n')
    trace.prepare_run(*packet)
    request = trace.strict_request(packet[-1] / "request.json")
    assert request["protected_sha256"][str(failure)] == trace.sha(failure)
    failure.write_bytes(b"changed failure")
    with pytest.raises(ValueError, match="historical"):
        trace.validate_request(packet[-1], request)


@pytest.mark.parametrize("kind", ["process_path", "process_bytes", "part_path", "freecad_file"])
def test_runtime_origin_mismatch_fails(packet, tmp_path, kind):
    trace.prepare_run(*packet)
    request = trace.strict_request(packet[-1] / "request.json")
    app = SimpleNamespace()
    part = SimpleNamespace(__file__=request["runtime_modules"]["Part"]["path"])
    image = packet[0]
    alternate = tmp_path / "alternate"
    alternate.write_bytes(image.read_bytes())
    if kind == "process_path":
        image = alternate
    elif kind == "process_bytes":
        image.write_bytes(b"substituted executable")
    elif kind == "part_path":
        part.__file__ = str(alternate)
    else:
        app.__file__ = str(alternate)
    with pytest.raises(ValueError):
        trace.runtime_provenance(app, part, request, image)
