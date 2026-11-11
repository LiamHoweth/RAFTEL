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
