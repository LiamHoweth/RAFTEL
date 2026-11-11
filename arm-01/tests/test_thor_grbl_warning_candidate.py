"""Candidate contract and preservation guards, distinct from captured AVR compiles."""

import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ORIGINAL_PATH = list(sys.path)
try:
    sys.path.insert(0, str(ROOT / "tools"))
    SPEC = importlib.util.spec_from_file_location(
        "prepare_thor_grbl_warning_candidate", ROOT / "tools/prepare_thor_grbl_warning_candidate.py"
    )
    CANDIDATE = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(CANDIDATE)
finally:
    sys.path[:] = _ORIGINAL_PATH
REPORT = ROOT / "hardware/cad/thor-grbl-warning-candidate.json"


def synthetic_patch_fixture(monkeypatch):
    # This intentionally tiny text is only a transformation/guard fixture,
    # never compiled and never claimed to be the real GRBL source.
    text = """#define FAIL(status) return(status);
uint16_t value_words = 0;
if (bit_istrue(value_words,bit(word_bit))) {}
if ( bit(word_bit) & (bit(WORD_F)|bit(WORD_S))) {}
value_words |= bit(word_bit);
command_words |= bit(word_bit);
command_words |= bit(word_bit);
((1<<WORD_P)|(1<<WORD_L));
case 95:
    /* unchanged unresolved command sentinel */
// NOTE: All remaining letters assign values.
"""
    text += (
        "\n".join(
            f"case '{name}': axis_words |= sentinel_{name};"
            for name in ("A", "B", "C", "D", "X", "Y", "Z")
        )
        + "\n"
    )
    raw = text.encode()
    monkeypatch.setattr(CANDIDATE, "PINNED_GCODE_SHA256", hashlib.sha256(raw).hexdigest())
    return raw


def test_patch_is_bounded_to_value_word_bits_and_leaves_other_paths(monkeypatch):
    original = synthetic_patch_fixture(monkeypatch)
    result, ledger = CANDIDATE.candidate_bytes(original)
    assert b"uint32_t value_words = 0" in result
    assert CANDIDATE.HELPER.encode() in result
    assert result.count(b"command_words |= bit(word_bit);") == 2
    assert b"unchanged unresolved command sentinel" in result
    assert b"case 'Z': axis_words |= sentinel_Z;" in result
    assert ledger["baseline_sha256"] == hashlib.sha256(original).hexdigest()
    assert ledger["candidate_sha256"] == hashlib.sha256(result).hexdigest()
    assert ledger["direct_constant_shift_replacements"] == 2
    assert b"uint16_t value_words" in original


def test_stale_source_hash_and_incomplete_coverage_fail(monkeypatch):
    original = synthetic_patch_fixture(monkeypatch)
    with pytest.raises(ValueError, match="exact pinned"):
        CANDIDATE.candidate_bytes(original + b"changed")
    changed = original.replace(b"uint16_t value_words = 0;", b"uint16_t value_words;")
    monkeypatch.setattr(CANDIDATE, "PINNED_GCODE_SHA256", hashlib.sha256(changed).hexdigest())
    with pytest.raises(ValueError, match="anchor"):
        CANDIDATE.candidate_bytes(changed)


def test_all_17_bits_are_unique_duplicate_y_z_detect_and_selective_clear_preserves_rest():
    masks = [CANDIDATE.word_mask(i) for i in range(17)]
    assert len(set(masks)) == 17
    assert sum(masks) == 0x1FFFF
    for i in (15, 16):
        word = CANDIDATE.word_mask(i)
        assert not (0 & word)
        assert (word & word) != 0
    rng = random.Random(713)
    for _ in range(100):
        selected = {i for i in range(17) if rng.random() < 0.5}
        cleared = {i for i in range(17) if rng.random() < 0.5}
        bits = sum(masks[i] for i in selected)
        clearing = sum(masks[i] for i in cleared)
        assert bits & ~clearing == sum(masks[i] for i in selected - cleared)


@pytest.mark.parametrize("bad", [-1, 17, True, 1.0, "1"])
def test_invalid_value_word_index_rejected(bad):
    with pytest.raises(ValueError):
        CANDIDATE.word_mask(bad)


def test_pinned_header_contract_requires_every_word_index_once():
    header = "\n".join(f"#define WORD_{name} {i}" for i, name in enumerate(CANDIDATE.WORD_ORDER))
    assert CANDIDATE.validate_word_indices(header)["Z"] == 16
    with pytest.raises(ValueError, match="17-word"):
        CANDIDATE.validate_word_indices(header.replace("WORD_Z 16", "WORD_Z 15"))
    with pytest.raises(ValueError, match="17-word"):
        CANDIDATE.validate_word_indices(header + "\n#define WORD_Z 16")


def test_report_binds_source_and_script_and_limits_changed_file():
    report = json.loads(REPORT.read_bytes())
    baseline = json.loads((ROOT / "hardware/cad/thor-grbl-build-feasibility.json").read_bytes())
    assert report["source_files"] == baseline["source_files"]
    assert (
        report["reproduction"]["script_sha256"]
        == hashlib.sha256(
            (ROOT / "tools/prepare_thor_grbl_warning_candidate.py").read_bytes()
        ).hexdigest()
    )
    assert len(report["changed_tracked_files"]) == 1
    assert report["changed_tracked_files"][0]["path"] == "grbl/gcode.c"
    assert report["canonical_source_preserved"]
    assert not report["candidate_promoted"]
    assert not report["firmware_linked"] and not report["firmware_executed"]


def test_captured_candidate_objects_remove_width_diagnostics_but_retain_m95_warning():
    report = json.loads(REPORT.read_bytes())
    for kind in ("candidate_default", "candidate_strict"):
        warnings = report["compile_objects"][kind]["warnings"]
        assert len(warnings) == 1
        assert "word_bit" in warnings[0] and "uninitialized" in warnings[0]
        assert not any("shift" in warning for warning in warnings)
    assert len(report["compile_objects"]["baseline_default"]["warnings"]) == 2
    assert len(report["compile_objects"]["baseline_strict"]["warnings"]) == 3
    assert len(report["compile_log"]) == 5
    assert all("-c" in command["arguments"] for command in report["compile_log"])
    assert all(command["returncode"] == 0 for command in report["compile_log"])
    assert len(report["static_probe"]["sections"]) == 22
    assert report["static_probe"]["warnings"] == []


def test_new_candidate_output_cannot_modify_original_or_compiler(tmp_path, monkeypatch):
    monkeypatch.setattr(CANDIDATE.sys, "platform", "win32")
    source, compiler = tmp_path / "source", tmp_path / "compiler"
    source.mkdir()
    compiler.mkdir()
    archive = tmp_path / "toolchain.zip"
    archive.write_bytes(b"guard fixture")

    def forbidden(*args):
        pytest.fail("overlap must fail before any source/compiler work")

    monkeypatch.setattr(CANDIDATE, "verify_source", forbidden)
    for output in (source / "candidate", compiler / "candidate", tmp_path):
        with pytest.raises(ValueError, match="new and separate"):
            CANDIDATE.prepare(source, archive, compiler, output)
        if output != tmp_path:
            assert not output.exists()
