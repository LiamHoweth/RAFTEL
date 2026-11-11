"""Static source evidence and ELF-data guards; never firmware execution."""

import hashlib
import importlib.util
import json
import random
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ORIGINAL_PATH = list(sys.path)
try:
    sys.path.insert(0, str(ROOT / "tools"))
    SPEC = importlib.util.spec_from_file_location(
        "audit_thor_grbl_warnings", ROOT / "tools/audit_thor_grbl_warnings.py"
    )
    AUDIT = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(AUDIT)
finally:
    sys.path[:] = _ORIGINAL_PATH
REPORT_PATH = ROOT / "hardware/cad/thor-grbl-warning-audit.json"


def elf_object(sections):
    names = b"\0.shstrtab\0"
    offsets = {}
    for name in sections:
        offsets[name] = len(names)
        names += (".rodata." + name).encode() + b"\0"
    count = 2 + len(sections)
    start = 52 + 40 * count
    headers = [(0,) * 10, (1, 3, 0, 0, start, len(names), 0, 0, 1, 0)]
    data = names
    for name, raw in sections.items():
        headers.append((offsets[name], 1, 2, 0, start + len(data), len(raw), 0, 0, 1, 0))
        data += raw
    ident = b"\x7fELF\x01\x01\x01" + b"\0" * 9
    header = struct.pack("<16sHHIIIIIHHHHHH", ident, 1, 83, 1, 0, 0, 52, 0, 52, 0, 0, 40, count, 1)
    return header + b"".join(struct.pack("<10I", *section) for section in headers) + data


def test_elf_parser_accepts_only_relocatable_avr_data_and_preserves_encoding():
    raw = elf_object({"warning_example16": b"\x34\x12", "warning_example32": b"\x00\x00\x01\x00"})
    result = AUDIT.elf_probe_sections(raw)
    assert result["warning_example16"]["unsigned_little_endian"] == 0x1234
    assert result["warning_example32"]["unsigned_little_endian"] == 65536
    assert result["warning_example16"]["bytes_hex"] == "3412"


@pytest.mark.parametrize(
    "kind", ["magic", "executable", "machine", "truncated", "bad_size", "huge"]
)
def test_bad_elf_representations_are_rejected(kind):
    raw = bytearray(elf_object({"warning_example": b"\0\0"}))
    if kind == "magic":
        raw[0] = 0
    elif kind == "executable":
        struct.pack_into("<H", raw, 16, 2)
    elif kind == "machine":
        struct.pack_into("<H", raw, 18, 62)
    elif kind == "truncated":
        raw = raw[:60]
    elif kind == "bad_size":
        struct.pack_into("<H", raw, 46, 20)
    else:
        raw = b"\0" * 1_048_577
    with pytest.raises(ValueError):
        AUDIT.elf_probe_sections(bytes(raw))


def test_checksum_recurrence_collapse_and_collision_are_expression_evidence():
    assert AUDIT.checksum_source_semantics(bytes([1, 42])) == 43
    assert AUDIT.checksum_source_semantics(bytes([2, 42])) == 43
    for initial in range(256):
        expression = bool((initial << 1) or (initial >> 7))
        assert int(expression) == int(initial != 0)
    rng = random.Random(781)
    for _ in range(100):
        values = rng.randbytes(rng.randrange(1, 100))
        expected = 0
        for byte in values:
            expected = (byte + (1 if expected else 0)) & 255
        assert AUDIT.checksum_source_semantics(values) == expected


@pytest.mark.parametrize("bad", [[1, 42], "012a", b"\0" * 65537], ids=["list", "text", "oversized"])
def test_checksum_input_is_bounded_bytes(bad):
    with pytest.raises(ValueError):
        AUDIT.checksum_source_semantics(bad)


def test_tracked_capture_binds_same_source_as_the_preserved_build_and_current_script():
    report = json.loads(REPORT_PATH.read_bytes())
    baseline = json.loads((ROOT / "hardware/cad/thor-grbl-build-feasibility.json").read_bytes())
    assert report["source_revision"] == baseline["source_revision"]
    for name, item in report["source_files"].items():
        assert item == baseline["source_files"][name]
    assert sum(f["compiler_warning_count"] for f in report["findings"]) == 6
    assert (
        report["reproduction"]["script_sha256"]
        == hashlib.sha256((ROOT / "tools/audit_thor_grbl_warnings.py").read_bytes()).hexdigest()
    )
    assert report["source_preserved"]
    assert not report["source_patch_accepted"]
    assert not report["firmware_executed"]
    assert not report["hardware_connected"]


def test_static_capture_is_object_encoding_and_never_claims_portable_undefined_semantics():
    report = json.loads(REPORT_PATH.read_bytes())
    probe = report["static_probes"]
    assert not probe["firmware_linked"] and not probe["firmware_executed"]
    assert "no portable C or runtime behavior inferred" in probe["undefined_shift_scope"]
    actual = {key: value["unsigned_little_endian"] for key, value in probe["sections"].items()}
    assert actual == AUDIT.PROBE_EXPECTED
    assert len(probe["compile_log"]) == 2
    for command in probe["compile_log"]:
        assert command["tool"] == "avr-gcc.exe"
        assert "-c" in command["arguments"]
        assert command["returncode"] == 0
    assert "-Wshift-overflow=2" in probe["compile_log"][1]["arguments"]


def test_source_consumer_scope_keeps_z_target_dispatch_separate_from_word_bookkeeping():
    report = json.loads(REPORT_PATH.read_bytes())
    mask = next(item for item in report["findings"] if item["id"] == "axis_word_mask_width")
    assert "Z motion always fails" in mask["not_proven"]
    assert any("axis_words" in fact and "target" in fact for fact in mask["proven"])
    assert {reference["line"] for reference in mask["references"]} >= {97, 373, 378, 620, 852, 989}
    m95 = next(item for item in report["findings"] if item["id"] == "m95_unassigned_modal_word_bit")
    assert any("sys.abort" in fact and "does not" in fact for fact in m95["proven"])
    spindle = next(
        item
        for item in report["findings"]
        if item["id"] == "spindle_signature_and_empty_reenable_body"
    )
    assert "all M3/S control is empty" in spindle["not_proven"]


def test_anchor_ambiguity_and_missing_evidence_fail():
    with pytest.raises(ValueError, match="missing or ambiguous"):
        AUDIT._line("one\none", "one")
    with pytest.raises(ValueError, match="missing or ambiguous"):
        AUDIT._line("one", "missing")


def test_warning_output_cannot_pollute_byte_verified_compiler_tree(tmp_path, monkeypatch):
    source, compiler = tmp_path / "source", tmp_path / "compiler"
    source.mkdir()
    compiler.mkdir()
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"guard fixture")
    output = compiler / "must-not-be-created"

    def forbidden(*args):
        pytest.fail("overlap must fail before further source/compiler work")

    monkeypatch.setattr(AUDIT, "verify_source", forbidden)
    with pytest.raises(ValueError, match="compiler tree"):
        AUDIT.audit(source, output, archive=archive, toolchain_root=compiler)
    assert not output.exists()
