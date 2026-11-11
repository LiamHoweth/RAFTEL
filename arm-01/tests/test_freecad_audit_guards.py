"""Guard native audit inputs without requiring a FreeCAD installation."""

import runpy
from pathlib import Path

import pytest

TOOLS = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "audit_freecad_assembly.py"))


def test_missing_native_source_rejected_before_importing_freecad(tmp_path):
    with pytest.raises(ValueError, match="existing native"):
        TOOLS["audit"](tmp_path / "missing.FCStd")


def test_existing_report_is_never_overwritten(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("retained evidence")
    monkeypatch.setenv("RAFTEL_FREECAD_ASSEMBLY", str(tmp_path / "source.FCStd"))
    monkeypatch.setenv("RAFTEL_FREECAD_REPORT", str(output))
    with pytest.raises(ValueError, match="never overwritten"):
        TOOLS["main"]()
    assert output.read_text() == "retained evidence"


def test_report_cannot_overwrite_a_cad_file(tmp_path, monkeypatch):
    source = tmp_path / "source.FCStd"
    source.write_bytes(b"protected native data")
    monkeypatch.setenv("RAFTEL_FREECAD_ASSEMBLY", str(source))
    monkeypatch.setenv("RAFTEL_FREECAD_REPORT", str(source))
    with pytest.raises(ValueError, match="new .json"):
        TOOLS["main"]()
    assert source.read_bytes() == b"protected native data"
