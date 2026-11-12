"""Host guard/effect classification tests; these never run native FreeCAD."""

import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).parents[1] / "tools/probe_thor_art1_attachment_engine.py"
SPEC = importlib.util.spec_from_file_location("art1_attachment_tested", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
IDENTITY = [float(i == j) for i in range(4) for j in range(4)]


def translated(x, y, z):
    result = IDENTITY.copy()
    result[3], result[7], result[11] = x, y, z
    return result


def test_effect_requires_observed_challenge_recovery_not_unchanged_getter():
    challenge = translated(*MODULE.CHALLENGE_MM)
    recovered = MODULE.engine_effect(IDENTITY, challenge, IDENTITY, "FlatFace")
    assert recovered["engine_effect_observed"] and recovered["challenge_recovered"]
    noop = MODULE.engine_effect(IDENTITY, challenge, challenge, "FlatFace")
    assert not noop["engine_effect_observed"] and not noop["challenge_recovered"]
    cached = MODULE.engine_effect(IDENTITY, IDENTITY, IDENTITY, "FlatFace")
    assert not cached["engine_effect_observed"] and not cached["challenge_recovered"]


def test_deactivated_control_cannot_be_promoted_to_engine_pass():
    challenge = translated(*MODULE.CHALLENGE_MM)
    row = MODULE.engine_effect(IDENTITY, challenge, challenge, "Deactivated")
    assert row["deactivated_no_effect_control"]
    assert not row["challenge_recovered"] and not row["engine_effect_observed"]
    wrong = MODULE.engine_effect(IDENTITY, challenge, translated(9, 0, 0), "FlatFace")
    assert wrong["engine_effect_observed"] and not wrong["challenge_recovered"]


@pytest.mark.parametrize(
    "bad", [[], [0] * 15, [True] * 16, [float("nan")] * 16, [float("inf")] * 16, ["1"] * 16]
)
def test_frame_rejects_nonfinite_or_wrong_matrix(bad):
    with pytest.raises(ValueError):
        MODULE.matrix(bad)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":1e999}',
        b"[]",
        b"{bad",
        '{"a":1}'.encode("utf-16"),
        '{"a":1}'.encode("utf-32"),
    ],
)
def test_request_json_rejects_ambiguous_nonfinite_and_non_utf8(tmp_path, raw):
    path = tmp_path / "request.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        MODULE.strict_json(path)


def test_json_read_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "MAX_BYTES", 16)
    path = tmp_path / "request.json"
    path.write_bytes(b" " * 17)
    with pytest.raises(ValueError, match="budget"):
        MODULE.strict_json(path)


def prepared(tmp_path, monkeypatch):
    root = tmp_path / ".work/swarm/a01_engine/run-01"
    for name in MODULE.INPUTS:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"retained test bytes")
    pins = {name: MODULE.sha(root / name) for name in MODULE.INPUTS[1:]}
    request = {
        "schema_version": 1,
        "evidence_class": "copied_Art1_direct_attachment_engine_request",
        "pins": pins,
        "runtime_modules": {"FreeCAD": {}, "Part": {}},
    }
    (root / "request.json").write_text(json.dumps(request), encoding="utf-8")
    monkeypatch.setenv(MODULE.FLAG, "1")
    monkeypatch.setattr(MODULE, "SOURCE_SHA256", pins["inputs/source.fcstd"])
    monkeypatch.setattr(MODULE, "CANDIDATE_SHA256", pins["inputs/candidate.fcstd"])
    monkeypatch.setattr(MODULE.shutil, "disk_usage", lambda _: SimpleNamespace(free=10**12))
    return root, root / MODULE.INPUTS[4]


def test_optin_and_conflicts_reject_before_any_input_read(tmp_path, monkeypatch):
    monkeypatch.delenv(MODULE.FLAG, raising=False)
    monkeypatch.setattr(MODULE, "checked_path", lambda *a, **k: pytest.fail("input accessed"))
    with pytest.raises(ValueError, match="opt-in"):
        MODULE.guard_request(tmp_path, PATH)
    monkeypatch.setenv(MODULE.FLAG, "1")
    monkeypatch.setenv("RAFTEL_RUN_ART1_SEMANTIC_SUPPORTS", "1")
    with pytest.raises(ValueError, match="conflicting"):
        MODULE.guard_request(tmp_path, PATH)


def test_guard_accepts_only_fresh_retained_run_and_detects_tamper(tmp_path, monkeypatch):
    root, worker = prepared(tmp_path, monkeypatch)
    _, pins = MODULE.guard_request(root, worker)
    assert pins["request.json"] == hashlib.sha256((root / "request.json").read_bytes()).hexdigest()
    (root / "inputs/candidate.fcstd").write_bytes(b"changed")
    with pytest.raises(ValueError, match="pin differs"):
        MODULE.guard_request(root, worker)


@pytest.mark.parametrize("output", ["probe.json", "probe.tmp"])
def test_existing_evidence_is_never_relaunched(tmp_path, monkeypatch, output):
    root, worker = prepared(tmp_path, monkeypatch)
    (root / output).write_text("preserve me", encoding="utf-8")
    with pytest.raises(ValueError, match="never overwritten"):
        MODULE.guard_request(root, worker)
    assert (root / output).read_text(encoding="utf-8") == "preserve me"


def test_guard_rejects_insufficient_real_reserve(tmp_path, monkeypatch):
    root, worker = prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(
        MODULE.shutil, "disk_usage", lambda _: SimpleNamespace(free=MODULE.RESERVE_BYTES - 1)
    )
    with pytest.raises(ValueError, match="reserve"):
        MODULE.guard_request(root, worker)


def test_path_escape_is_rejected_before_file_access(tmp_path):
    with pytest.raises(ValueError, match="unsafe"):
        MODULE.checked_path(tmp_path, "../outside")


def test_all_five_actual_native_paths_must_match(tmp_path):
    values = {
        "UserParameter": tmp_path / "user.cfg",
        "SystemParameter": tmp_path / "system.cfg",
        "UserHomePath": tmp_path / "home",
        "UserAppData": tmp_path / "data",
        "AppTempPath": tmp_path / "temp",
    }
    app = SimpleNamespace(ConfigGet=lambda key: str(values[key]))
    assert MODULE.actual_isolation(app, tmp_path)["passed"]
    values["AppTempPath"] = tmp_path / "wrong"
    with pytest.raises(ValueError, match="five"):
        MODULE.actual_isolation(app, tmp_path)


def test_isolated_configuration_reparse_is_rejected_before_native_launch(tmp_path, monkeypatch):
    root, worker = prepared(tmp_path, monkeypatch)
    home = root / "home"
    home.mkdir()
    original_lstat = Path.lstat

    def observed_lstat(path, *args, **kwargs):
        result = original_lstat(path, *args, **kwargs)
        if path == home:
            return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=0x400)
        return result

    monkeypatch.setattr(Path, "lstat", observed_lstat)
    with pytest.raises(ValueError, match="reparse"):
        MODULE.guard_request(root, worker)


def test_report_is_utf8_lf_and_forbids_nonfinite(tmp_path):
    MODULE.write_report(tmp_path, {"scope": "diagnostic", "migration_accepted": False})
    raw = (tmp_path / "probe.json").read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    assert not (tmp_path / "probe.tmp").exists()
    with pytest.raises(ValueError):
        MODULE.write_report(tmp_path, {"bad": float("nan")})


@pytest.mark.parametrize("engine_raises", [False, True])
def test_owner_saved_placement_restores_even_when_native_call_raises(monkeypatch, engine_raises):
    class Vector(tuple):
        def __new__(cls, *values):
            return super().__new__(cls, values)

        def __add__(self, other):
            return Vector(*(a + b for a, b in zip(self, other, strict=True)))

    class Placement:
        def __init__(self, source=None):
            self.Base = Vector(*(source.Base if source else (0, 0, 0)))

        def toMatrix(self):
            return SimpleNamespace(A=translated(*self.Base))

    obj = SimpleNamespace(Placement=Placement())
    obj.Placement.Base = Vector(9, 8, 7)
    calls = []

    def execute():
        calls.append(1)
        if engine_raises:
            raise RuntimeError("synthetic native failure")
        obj.Placement = Placement()
        return True

    def snapshot(owner, _):
        return {"placement_matrix": MODULE.placement(owner), "mode": "ObjectXY", "targets": []}

    obj.positionBySupport = execute
    monkeypatch.setattr(MODULE, "owner_snapshot", snapshot)
    row = MODULE.challenge_owner(SimpleNamespace(Placement=Placement, Vector=Vector), obj, None)
    assert obj.Placement.Base == (9, 8, 7)
    assert row["saved_placement_restored"]
    assert not row["explicit_support_assignment"] and not row["recompute_requested"]
    if engine_raises:
        assert row["status"] == "engine_error" and len(calls) == 1
    else:
        assert row["challenge_recovered"] and row["engine_effect_observed"] and len(calls) == 2


@pytest.mark.parametrize("mismatch", [None, "host", "module_file", "part_pin"])
def test_embedded_runtime_identity_has_no_invented_freecad_file(tmp_path, monkeypatch, mismatch):
    executable, part = tmp_path / "freecadcmd.exe", tmp_path / "Part.pyd"
    executable.write_bytes(b"synthetic executable bytes")
    part.write_bytes(b"synthetic Part bytes")
    app = SimpleNamespace(Version=lambda: ["1", "1", "4"])
    declarations = {
        "FreeCAD": {
            "kind": "embedded_no_file",
            "host_path": str(executable),
            "host_sha256": MODULE.sha(executable),
        },
        "Part": {"kind": "extension", "path": str(part), "sha256": MODULE.sha(part)},
    }
    monkeypatch.setattr(MODULE, "process_image_path", lambda: executable.resolve())
    if mismatch == "host":
        other = tmp_path / "other.exe"
        other.write_bytes(b"other")
        monkeypatch.setattr(MODULE, "process_image_path", lambda: other.resolve())
    elif mismatch == "module_file":
        app.__file__ = str(tmp_path / "FreeCAD.pyd")
    elif mismatch == "part_pin":
        declarations["Part"]["sha256"] = "0" * 64
    if mismatch:
        with pytest.raises(ValueError):
            MODULE.runtime_module_records(app, SimpleNamespace(__file__=str(part)), declarations)
    else:
        records = MODULE.runtime_module_records(
            app, SimpleNamespace(__file__=str(part)), declarations
        )
        assert records["FreeCAD"]["module_file"] is None
        assert records["FreeCAD"]["host_path"] == str(executable.resolve())
        assert records["Part"]["path"] == str(part.resolve())


def test_actual_receipt_preserves_raw_native_bytes_and_bounded_engine_scope():
    """Authenticate recorded data; this test itself executes no native engine."""
    path = Path(__file__).parents[1] / "hardware/cad/thor-art1-attachment-engine-v1.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    provenance = receipt.pop("native_provenance")
    reconstructed = (json.dumps(receipt, indent=2, allow_nan=False) + "\n").encode("utf-8")
    expected = "5e49533ca489a0c7d384cd668dd4d617e0c9f2d15e36651bf35e828f07207409"
    assert hashlib.sha256(reconstructed).hexdigest() == provenance["raw_report_sha256"] == expected
    assert provenance["native_launch"]["passed"]
    assert provenance["native_launch"]["preservation"] == {"retained": True, "protected": True}
    assert len(provenance["native_stderr_warnings"]) == 6
    assert all(
        "axes of inertia are undefined" in line for line in provenance["native_stderr_warnings"]
    )
    assert receipt["open_documents_after"] == [] and receipt["input_execution_bytes_preserved"]
    assert not receipt["errors"] and receipt["fixture"]["passed"]
    assert len(receipt["candidate_runtime_type_inventory"]) == 90
    assert len(receipt["owners"]) == 53
    assert Counter(row["status"] for row in receipt["owners"]) == {
        "observed_direct_engine_call": 51,
        "no_attachment_engine_method": 2,
    }
    assert (
        receipt["active_engine_effect_count"] == receipt["active_challenge_recovered_count"] == 51
    )
    for row in receipt["owners"]:
        assert row["saved_placement_restored"]
        assert row["saved"]["placement_matrix"] == row["restored_saved"]["placement_matrix"]
        if row["status"] == "observed_direct_engine_call":
            assert row["nominal_call_return"] is True and row["challenge_call_return"] is True
            assert (
                row["after_engine"]["placement_matrix"] == row["nominal_engine"]["placement_matrix"]
            )
            assert row["engine_max_matrix_effect"] == 3.75
            assert row["targets_unchanged"]
    for field in (
        "document_saved",
        "source_document_opened",
        "recompute_requested",
        "explicit_support_assignment",
        "attachment_approved",
        "migration_accepted",
        "manufacturing_release",
        "physical_calibration",
        "engine_internal_persistent_name_path_traced",
    ):
        assert receipt[field] is False
