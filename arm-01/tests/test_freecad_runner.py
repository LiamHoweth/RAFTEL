"""Subprocess-level failure handling, without CAD or physical hardware."""

import json
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "run_freecad_audit.py"))
run_audit = MODULE["run_audit"]


def files(tmp_path):
    executable, source = tmp_path / "freecad", tmp_path / "part.FCStd"
    executable.write_text("executable fixture")
    source.write_bytes(b"protected source")
    return executable, source, tmp_path / "result.json"


def test_timeout_preserves_checkpoint_and_both_logs(tmp_path, monkeypatch):
    executable, source, report = files(tmp_path)

    def timeout(command, **kwargs):
        Path(kwargs["env"]["RAFTEL_FREECAD_REPORT"]).write_text('{"stage":"recomputing"}')
        raise subprocess.TimeoutExpired(command, 1, output=b"progress", stderr=b"diagnostic")

    monkeypatch.setattr(subprocess, "run", timeout)
    result = run_audit(executable, source, report, timeout_s=1)
    assert result["outcome"] == "timed_out" and result["checkpoint_exists"]
    assert json.loads(report.read_text())["stage"] == "recomputing"
    assert (tmp_path / "result.run/stdout.log").read_text() == "progress"
    assert (tmp_path / "result.run/stderr.log").read_text() == "diagnostic"
    assert source.read_bytes() == b"protected source"


def test_completed_process_without_report_is_explicit(tmp_path, monkeypatch):
    executable, source, report = files(tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    result = run_audit(executable, source, report)
    assert result["outcome"] == "process_completed" and not result["checkpoint_exists"]


def test_existing_evidence_and_cad_destinations_rejected(tmp_path):
    executable, source, report = files(tmp_path)
    report.write_text("retained evidence")
    with pytest.raises(ValueError, match="new JSON"):
        run_audit(executable, source, report)
    with pytest.raises(ValueError, match="new JSON"):
        run_audit(executable, source, source)
    assert source.read_bytes() == b"protected source"
    assert report.read_text() == "retained evidence"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), 7201])
def test_invalid_timeout_rejected_before_running(tmp_path, timeout):
    executable, source, report = files(tmp_path)
    with pytest.raises(ValueError, match="timeout"):
        run_audit(executable, source, report, timeout_s=timeout)


def test_native_exit_zero_does_not_hide_failed_audit(tmp_path, monkeypatch):
    executable, source, report = files(tmp_path)

    def failed(command, **kwargs):
        Path(kwargs["env"]["RAFTEL_FREECAD_REPORT"]).write_text('{"status":"failed"}')
        return SimpleNamespace(returncode=0, stdout="", stderr="failed restore")

    monkeypatch.setattr(subprocess, "run", failed)
    result = run_audit(executable, source, report)
    assert result["process_returncode"] == 0 and result["audit_status"] == "failed"


def test_native_worker_snapshot_and_child_paths_are_isolated(tmp_path, monkeypatch):
    import hashlib
    import os

    executable, source, report = files(tmp_path)
    monkeypatch.setenv("FREECAD_USER_HOME", "existing-global-home")
    monkeypatch.setenv("PYTHONPATH", "unrelated-python-source")
    original = (Path(__file__).parents[1] / "tools/audit_freecad_assembly.py").read_bytes()

    def completed(command, **kwargs):
        snapshot = Path(command[-1])
        assert snapshot.parent == report.with_suffix(".run")
        assert snapshot.read_bytes() == original
        assert kwargs["env"]["RAFTEL_FREECAD_ISOLATION_ROOT"] == str(snapshot.parent)
        for key in ("FREECAD_USER_HOME", "FREECAD_USER_DATA", "FREECAD_USER_TEMP"):
            assert Path(kwargs["env"][key]).is_relative_to(snapshot.parent)
        assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
        assert "PYTHONPATH" not in kwargs["env"] and "PYTHONHOME" not in kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", completed)
    result = run_audit(executable, source, report)
    assert result["worker_snapshot_sha256"] == hashlib.sha256(original).hexdigest()
    assert result["worker_snapshot_unchanged"] and result["master_source_unchanged"]
    assert result["runner_snapshot_unchanged"]
    assert os.environ["FREECAD_USER_HOME"] == "existing-global-home"
    assert os.environ["PYTHONPATH"] == "unrelated-python-source"
    assert b"\r" not in (report.with_suffix(".run") / "runner.json").read_bytes()


@pytest.mark.parametrize("mutate_worker", [False, True])
def test_changed_source_or_snapshot_is_not_hidden_by_zero_exit(
    tmp_path, monkeypatch, mutate_worker
):
    executable, source, report = files(tmp_path)

    def changed(command, **kwargs):
        Path(command[-1] if mutate_worker else source).write_bytes(b"changed by fixture")
        Path(kwargs["env"]["RAFTEL_FREECAD_REPORT"]).write_text('{"status":"complete"}')
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", changed)
    result = run_audit(executable, source, report)
    assert result["process_returncode"] == 0 and result["audit_status"] == "complete"
    assert result["worker_snapshot_unchanged"] is not mutate_worker
    assert result["master_source_unchanged"] is mutate_worker


def test_changed_retained_runner_is_an_explicit_preservation_failure(tmp_path, monkeypatch):
    executable, source, report = files(tmp_path)

    def changed(command, **kwargs):
        (Path(command[-1]).parent / "run_freecad_audit.py").write_bytes(b"changed receipt source")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", changed)
    result = run_audit(executable, source, report)
    assert not result["runner_snapshot_unchanged"]
    assert result["worker_snapshot_unchanged"] and result["master_source_unchanged"]
