#!/usr/bin/env python3
"""Pinned source-warning consumers and optional static AVR object-data probes.

No source edits, firmware linking/execution, emulator, uploader or device API.
The optional compiler creates a relocatable object from separate probe code;
Python reads ELF sections as data. Undefined-C expressions are reported only as
observed encodings of this pinned compiler, never portable runtime semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from build_thor_grbl_diagnostic import (
    FLAGS,
    MIN_FREE_BYTES,
    SOURCE_REVISION,
    TOOLCHAIN_SHA256,
    _run_tool,
    _verify_extracted,
    verify_archive,
    verify_source,
)

PROBE_SOURCE = """#include <stdint.h>
const uint16_t warning_shift16_encoding = (1 << 16);
const uint16_t warning_shift15_encoding = (1 << 15);
const uint16_t warning_unsigned_shift15 = (1U << 15);
const uint16_t warning_wide_cast_u16 = ((uint32_t)1 << 16);
const uint32_t warning_wide_value_u32 = ((uint32_t)1 << 16);
const uint8_t warning_axis_g_mask = (1 << 6);
const uint16_t warning_axis_word_mask_encoding =
    (1<<10)|(1<<11)|(1<<12)|(1<<13)|(1<<14)|(1<<15)|(1<<16);
const uint8_t warning_logical_or_2 = ((2 << 1) || (2 >> 7));
const uint8_t warning_bitwise_or_2 = ((2 << 1) | (2 >> 7));
const uint8_t warning_checksum_pair_1_42 = ((1 << 1) || (1 >> 7)) + 42;
const uint8_t warning_checksum_pair_2_42 = ((2 << 1) || (2 >> 7)) + 42;
"""
PROBE_EXPECTED = {
    "warning_shift16_encoding": 0,
    "warning_shift15_encoding": 32768,
    "warning_unsigned_shift15": 32768,
    "warning_wide_cast_u16": 0,
    "warning_wide_value_u32": 65536,
    "warning_axis_g_mask": 64,
    "warning_axis_word_mask_encoding": 64512,
    "warning_logical_or_2": 1,
    "warning_bitwise_or_2": 4,
    "warning_checksum_pair_1_42": 43,
    "warning_checksum_pair_2_42": 43,
}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checksum_source_semantics(data: bytes) -> int:
    """Defined uchar/logical-OR expression model, not EEPROM access."""
    if not isinstance(data, bytes) or len(data) > 65536:
        raise ValueError("checksum fixture requires at most 65536 bytes")
    checksum = 0
    for byte in data:
        checksum = (int(bool((checksum << 1) or (checksum >> 7))) + byte) % 256
    return checksum


def elf_probe_sections(data: bytes) -> dict[str, dict]:
    """Read only named data sections of bounded little-endian ELF32 EM_AVR ET_REL."""
    if not isinstance(data, bytes) or not 52 <= len(data) <= 1_048_576:
        raise ValueError("probe must be a bounded ELF object")
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    if data[:7] != b"\x7fELF\x01\x01\x01" or header[1] != 1 or header[2] != 83:
        raise ValueError("probe must remain a little-endian relocatable AVR object")
    shoff, shsize, shcount, string_index = header[6], header[11], header[12], header[13]
    if shsize != 40 or not 1 <= shcount <= 4096 or string_index >= shcount:
        raise ValueError("malformed probe section table")
    if shoff + shsize * shcount > len(data):
        raise ValueError("truncated probe section table")
    sections = [
        struct.unpack_from("<10I", data, shoff + shsize * index) for index in range(shcount)
    ]
    string_section = sections[string_index]
    start, size = string_section[4], string_section[5]
    if start + size > len(data):
        raise ValueError("truncated section-name table")
    names = data[start : start + size]
    result = {}
    for section in sections:
        name_offset, offset, size = section[0], section[4], section[5]
        if name_offset >= len(names):
            raise ValueError("invalid probe section-name offset")
        end = names.find(b"\0", name_offset)
        if end < 0:
            raise ValueError("unterminated probe section name")
        name = names[name_offset:end].decode("ascii")
        if name.startswith(".rodata.warning_"):
            if section[1] != 1 or offset + size > len(data) or size not in {1, 2, 4}:
                raise ValueError("unexpected probe data section representation")
            identifier = name.removeprefix(".rodata.")
            if identifier in result:
                raise ValueError("duplicate probe data section")
            raw = data[offset : offset + size]
            result[identifier] = {
                "section": name,
                "bytes_hex": raw.hex(),
                "unsigned_little_endian": int.from_bytes(raw, "little"),
            }
    return result


def _line(text: str, anchor: str, *, occurrence: int | None = None) -> int:
    lines = [i for i, line in enumerate(text.splitlines(), 1) if anchor in line]
    if occurrence is not None and lines:
        return lines[occurrence]
    if len(lines) != 1:
        raise ValueError(f"pinned warning anchor missing or ambiguous: {anchor}")
    return lines[0]


def source_findings(texts: dict[str, str]) -> list[dict]:
    """Fact inventory tied to exact pinned source; not a general C analyzer."""
    gcode, header = texts["grbl/gcode.c"], texts["grbl/gcode.h"]
    if "#define WORD_Z  16" not in header or "uint16_t value_words = 0" not in gcode:
        raise ValueError("pinned axis-word width evidence differs")
    m95 = gcode[
        gcode.index("case 95:") : gcode.index(
            "default: FAIL(STATUS_GCODE_UNSUPPORTED_COMMAND); // [Unsupported M command]"
        )
    ]
    if "word_bit =" in m95 or "mc_homing_cycle();" not in m95:
        raise ValueError("pinned M95 control-flow evidence differs")
    spindle = texts["grbl/spindle_control.c"]
    if "spindle_set_state(uint8_t state, float rpm){\n}" not in spindle:
        raise ValueError("pinned spindle empty-body evidence differs")
    if texts["grbl/eeprom.c"].count("checksum = (checksum << 1) || (checksum >> 7);") != 2:
        raise ValueError("pinned EEPROM recurrence evidence differs")
    z_line = _line(gcode, "case 'Z': word_bit = WORD_Z;")
    return [
        {
            "id": "axis_word_mask_width",
            "compiler_warning_count": 1,
            "proven": [
                "WORD_Z is 16, value_words has 16 bits, and bit(n) shifts signed int literal 1",
                (
                    "On this AVR ABI, 1<<16 exceeds operand width; uint16 storage cannot "
                    "track bit 16 even after widening only the literal"
                ),
                "Z independently writes xyz[G_AXIS] and axis_words bit G_AXIS (6)",
                (
                    "axis_words drives target presence/conversion and motion dispatch; "
                    "value_words handles duplicate/unused-word bookkeeping"
                ),
            ],
            "not_proven": [
                "Z motion always fails",
                "all compiler versions encode the undefined shift identically",
                "the complete firmware parser matches offline replay",
            ],
            "references": [
                {"path": "grbl/gcode.h", "line": _line(header, "#define WORD_Z  16")},
                {
                    "path": "grbl/nuts_bolts.h",
                    "line": _line(texts["grbl/nuts_bolts.h"], "#define bit(n)"),
                },
                {"path": "grbl/gcode.c", "line": _line(gcode, "uint16_t value_words = 0")},
                {"path": "grbl/gcode.c", "line": z_line},
                {
                    "path": "grbl/gcode.c",
                    "line": _line(gcode, "if (bit_istrue(value_words,bit(word_bit)))"),
                },
                {
                    "path": "grbl/gcode.c",
                    "line": _line(gcode, "if ( bit_isfalse(axis_words,bit(idx)) )"),
                },
                {
                    "path": "grbl/gcode.c",
                    "line": _line(gcode, "if (axis_command) { bit_false(value_words"),
                },
                {
                    "path": "grbl/gcode.c",
                    "line": _line(
                        gcode, "mc_line(gc_block.values.xyz, -1.0, false);", occurrence=-1
                    ),
                },
            ],
        },
        {
            "id": "m95_unassigned_modal_word_bit",
            "compiler_warning_count": 1,
            "proven": [
                "word_bit is a local declaration without an initializer",
                (
                    "M95 enabled-homing branch has no word_bit assignment and no return "
                    "before the later modal mask"
                ),
                (
                    "If M95 is first and the enabled-homing path returns from its calls, "
                    "word_bit is read without an earlier assignment"
                ),
                (
                    "sys.abort only skips idle cleanup in this branch; it does not itself "
                    "return before modal-mask use"
                ),
                (
                    "With prior words, M95 can reuse a stale prior word_bit instead of "
                    "a defined M95 modal-group assignment"
                ),
            ],
            "not_proven": [
                "every command path leaves word_bit unassigned",
                "M95 is present in the modeled G0/G90/G91 replay subset",
                "installed homing setting or runtime result",
            ],
            "references": [
                {"path": "grbl/gcode.c", "line": _line(gcode, "uint8_t word_bit;")},
                {"path": "grbl/gcode.c", "line": _line(gcode, "case 95:")},
                {
                    "path": "grbl/gcode.c",
                    "line": _line(
                        gcode,
                        "if ( bit_istrue(command_words,bit(word_bit)) )",
                        occurrence=-1,
                    ),
                },
            ],
            "default_homing_flag": _line(
                texts["grbl/defaults/defaults_thor.h"], "#define DEFAULT_HOMING_ENABLE 1"
            ),
        },
        {
            "id": "spindle_signature_and_empty_reenable_body",
            "compiler_warning_count": 2,
            "proven": [
                (
                    "definition omits return type while header declares void, producing "
                    "implicit-int/conflicting-type warnings"
                ),
                "spindle_set_state body is empty in the pinned source",
                (
                    "its only call is the protocol re-energize spindle path; normal "
                    "speed/modal changes call spindle_run instead"
                ),
            ],
            "not_proven": [
                "all M3/S control is empty",
                "physical servo behavior",
                "safe recovery behavior",
            ],
            "references": [
                {
                    "path": "grbl/spindle_control.c",
                    "line": _line(spindle, "spindle_set_state(uint8_t state, float rpm)"),
                },
                {
                    "path": "grbl/spindle_control.h",
                    "line": _line(
                        texts["grbl/spindle_control.h"],
                        "void spindle_set_state(uint8_t state, float rpm);",
                    ),
                },
                {
                    "path": "grbl/protocol.c",
                    "line": _line(
                        texts["grbl/protocol.c"],
                        "spindle_set_state(gc_state.modal.spindle, gc_state.spindle_speed);",
                    ),
                },
                {
                    "path": "grbl/gcode.c",
                    "line": _line(
                        gcode, "spindle_run(gc_block.modal.spindle, gc_state.spindle_speed);"
                    ),
                },
            ],
        },
        {
            "id": "eeprom_logical_or_checksum",
            "compiler_warning_count": 2,
            "proven": [
                "both write/read checksum loops use logical OR, not a bitwise rotate",
                (
                    "For uchar state c, ((c<<1)||(c>>7)) is 0 if c==0 and 1 otherwise "
                    "on the captured 16-bit-int ABI"
                ),
                "source recurrence is c_next=(int(c!=0)+next_byte) modulo 256",
                "records [1,42] and [2,42] have the same modeled checksum 43",
                (
                    "startup/build-info/coordinate/global-settings writers and readers "
                    "all call these checksum functions"
                ),
                (
                    "both loops agree with each other; changing only one side can break "
                    "stored-record compatibility"
                ),
            ],
            "not_proven": [
                "the intended checksum algorithm",
                "all corruption is detected",
                "owner EEPROM contents or measured failures",
            ],
            "references": [
                {
                    "path": "grbl/eeprom.c",
                    "line": _line(texts["grbl/eeprom.c"], "void memcpy_to_eeprom_with_checksum"),
                },
                {
                    "path": "grbl/eeprom.c",
                    "line": _line(texts["grbl/eeprom.c"], "int memcpy_from_eeprom_with_checksum"),
                },
                {
                    "path": "grbl/settings.c",
                    "line": _line(
                        texts["grbl/settings.c"],
                        "memcpy_to_eeprom_with_checksum(EEPROM_ADDR_GLOBAL",
                    ),
                },
                {
                    "path": "grbl/settings.c",
                    "line": _line(
                        texts["grbl/settings.c"],
                        "memcpy_from_eeprom_with_checksum((char*)&settings",
                    ),
                },
            ],
        },
    ]


def compile_static_probes(archive: Path, toolchain_root: Path, output: Path) -> dict:
    if sys.platform != "win32":
        raise ValueError("pinned AVR probe compiler requires Windows")
    verify_archive(archive)
    with zipfile.ZipFile(archive) as compressed:
        manifest = {
            item.filename: _hash(compressed.read(item))
            for item in compressed.infolist()
            if not item.is_dir()
        }
    _verify_extracted(toolchain_root, manifest)
    probe_dir = output / "probe-copy"
    probe_dir.mkdir()
    probe = probe_dir / "warning-probes.c"
    probe.write_text(PROBE_SOURCE, encoding="utf-8", newline="\n")
    logs = []
    compiler = toolchain_root / "avr/bin/avr-gcc.exe"
    _run_tool(
        compiler, [*FLAGS, "-c", "warning-probes.c", "-o", "warning-probes.o"], probe_dir, logs
    )
    binary = (probe_dir / "warning-probes.o").read_bytes()
    sections = elf_probe_sections(binary)
    actual = {key: value["unsigned_little_endian"] for key, value in sections.items()}
    if actual != PROBE_EXPECTED:
        raise ValueError("selected compiler probe encodings differ from recorded expectation")
    _run_tool(
        compiler,
        [*FLAGS, "-Wshift-overflow=2", "-c", "warning-probes.c", "-o", "warning-probes-strict.o"],
        probe_dir,
        logs,
    )
    strict_binary = (probe_dir / "warning-probes-strict.o").read_bytes()
    if elf_probe_sections(strict_binary) != sections:
        raise ValueError("stricter diagnostic flag changed observed probe data")
    _verify_extracted(toolchain_root, manifest)
    return {
        "evidence_class": "host_avr_static_object_encoding_not_firmware_execution",
        "toolchain_archive_sha256": TOOLCHAIN_SHA256,
        "probe_source_sha256": _hash(probe.read_bytes()),
        "relocatable_object_sha256": _hash(binary),
        "relocatable_object_bytes": len(binary),
        "strict_diagnostic_object_sha256": _hash(strict_binary),
        "additional_diagnostic_flag": "-Wshift-overflow=2",
        "sign_bit_scope": (
            "WORD_Y=15 reaches signed int16 sign bit; matching 0x8000 encoding "
            "does not establish portable C semantics, unlike unsigned 1U<<15"
        ),
        "sections": sections,
        "compile_log": logs,
        "undefined_shift_scope": (
            "encoding observed only for pinned compiler; no portable C or runtime behavior inferred"
        ),
        "firmware_linked": False,
        "firmware_executed": False,
    }


def audit(
    source: Path, output: Path, *, archive: Path | None = None, toolchain_root: Path | None = None
) -> dict:
    source, output = source.resolve(strict=True), output.resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("warning evidence output must be new and separate from source")
    if (archive is None) != (toolchain_root is None):
        raise ValueError("compiler archive and extracted root must be supplied together")
    if archive is not None:
        archive, toolchain_root = archive.resolve(strict=True), toolchain_root.resolve(strict=True)
        if output.is_relative_to(toolchain_root) or toolchain_root.is_relative_to(output):
            raise ValueError("warning output must not overlap the preserved compiler tree")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < MIN_FREE_BYTES + 1_048_576:
        raise ValueError("warning audit would violate the 50 GiB free-space reserve")
    manifest = verify_source(source)
    needed = (
        "grbl/gcode.c",
        "grbl/gcode.h",
        "grbl/nuts_bolts.h",
        "grbl/spindle_control.c",
        "grbl/spindle_control.h",
        "grbl/protocol.c",
        "grbl/eeprom.c",
        "grbl/settings.c",
        "grbl/defaults/defaults_thor.h",
    )
    texts = {name: (source / name).read_text(encoding="utf-8") for name in needed}
    findings = source_findings(texts)
    output.mkdir(parents=True)
    probes = None
    if archive is not None:
        probes = compile_static_probes(archive, toolchain_root, output)
    report = {
        "schema_version": 1,
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "evidence_class": (
            "pinned_source_consumer_audit_and_optional_static_object_data_not_runtime_validation"
        ),
        "source_revision": SOURCE_REVISION,
        "source_files": {name: manifest[name] for name in needed},
        "findings": findings,
        "compiler_warning_count_explained": 6,
        "checksum_collision_fixture": {
            "input_a_hex": "012a",
            "input_b_hex": "022a",
            "checksum_a": checksum_source_semantics(bytes([1, 42])),
            "checksum_b": checksum_source_semantics(bytes([2, 42])),
            "evidence_class": "defined_C_expression_model_not_EEPROM_access",
        },
        "static_probes": probes,
        "source_preserved": verify_source(source) == manifest,
        "source_patch_accepted": False,
        "firmware_executed": False,
        "firmware_flashed": False,
        "hardware_connected": False,
    }
    if not report["source_preserved"]:
        raise ValueError("source changed during warning audit")
    with (output / "report.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--toolchain-archive", type=Path)
    parser.add_argument("--toolchain-root", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(
            args.source,
            args.output_dir,
            archive=args.toolchain_archive,
            toolchain_root=args.toolchain_root,
        )
        print(
            json.dumps(
                {
                    "warnings_explained": result["compiler_warning_count_explained"],
                    "static_probes_captured": result["static_probes"] is not None,
                    "source_preserved": result["source_preserved"],
                },
                indent=2,
            )
        )
    except (
        OSError,
        ValueError,
        KeyError,
        UnicodeError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ) as error:
        print(f"GRBL warning audit failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
