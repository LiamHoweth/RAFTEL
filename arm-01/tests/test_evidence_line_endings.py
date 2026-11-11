"""Catch generated worktree bytes that Git attributes alone cannot preserve."""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "evidence_line_endings", ROOT / "tools" / "check_evidence_line_endings.py"
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def test_crlf_json_parses_equally_but_has_different_published_byte_hash(tmp_path):
    path = tmp_path / "source.json"
    raw = b'{\r\n  "evidence": "source"\r\n}\r\n'
    path.write_bytes(raw)
    published = raw.replace(b"\r\n", b"\n")
    assert json.loads(raw) == json.loads(published)
    assert hashlib.sha256(raw).digest() != hashlib.sha256(published).digest()
    result = guard.inspect_paths(tmp_path, ["source.json"])
    assert len(result["violations"]) == 1
    assert result["files_changed"] is False
    assert path.read_bytes() == raw


def test_lf_text_passes_and_native_binary_carriage_returns_are_not_modified(tmp_path):
    text = tmp_path / "evidence.json"
    text.write_bytes(b'{"source":"pinned"}\n')
    binary = tmp_path / "Original.FCStd"
    binary.write_bytes(b"binary\r\nbytes\r")
    report = guard.inspect_paths(tmp_path, [text.name, binary.name, "not-present.md"])
    assert report["checked_text_file_count"] == 1
    assert report["violations"] == []
    assert report["missing_worktree_paths"] == ["not-present.md"]
    assert binary.read_bytes() == b"binary\r\nbytes\r"


def test_relative_parent_paths_rejected_before_reading_external_files(tmp_path):
    with pytest.raises(ValueError, match="project-relative"):
        guard.inspect_paths(tmp_path, ["../outside.json"])


def test_nonrepository_cli_failure_is_clear_without_traceback(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/check_evidence_line_endings.py"),
            "--root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "cannot list Git" in result.stderr
    assert "Traceback" not in result.stderr
