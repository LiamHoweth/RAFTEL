#!/usr/bin/env python3
"""Prepare a narrow copied-source value-word mask candidate and compile objects.

The canonical pinned source is always read-only. Only copied gcode.c changes:
value_words becomes uint32_t and gets a dedicated unsigned value-word mask.
No linking, execution, emulator, upload, hardware interface or source promotion.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from audit_thor_grbl_warnings import elf_probe_sections
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

PINNED_GCODE_SHA256 = "fd6be78b5b6c2258f7aefee5913a1968989ed19f91383b08a16cc3a10cf07321"
HELPER = "#define VALUE_WORD_MASK(n) (UINT32_C(1) << (n))"
WORD_ORDER = ("F", "I", "J", "K", "L", "N", "P", "R", "S", "T", "A", "B", "C", "D", "X", "Y", "Z")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def word_mask(index: int) -> int:
    """Desired candidate bookkeeping contract, not an upstream parser model."""
    if type(index) is not int or not 0 <= index <= 16:
        raise ValueError("candidate value-word index must be an integer within0..16")
    return 1 << index


def candidate_bytes(original: bytes) -> tuple[bytes, dict]:
    if _hash(original) != PINNED_GCODE_SHA256:
        raise ValueError("candidate requires the exact pinned gcode.c bytes")
    text = original.decode("utf-8")
    replacements = {}
    for before, after, count in (
        (
            "#define FAIL(status) return(status);",
            "#define FAIL(status) return(status);\n" + HELPER,
            1,
        ),
        ("uint16_t value_words = 0;", "uint32_t value_words = 0;", 1),
        (
            "bit_istrue(value_words,bit(word_bit))",
            "bit_istrue(value_words,VALUE_WORD_MASK(word_bit))",
            1,
        ),
        ("if ( bit(word_bit) & (", "if ( VALUE_WORD_MASK(word_bit) & (", 1),
        ("value_words |= bit(word_bit);", "value_words |= VALUE_WORD_MASK(word_bit);", 1),
    ):
        if text.count(before) != count:
            raise ValueError(f"pinned replacement anchor differs: {before}")
        text = text.replace(before, after)
        replacements[before] = count
    text, constants = re.subn(r"\bbit\((WORD_[A-Z])\)", r"VALUE_WORD_MASK(\1)", text)
    text, direct = re.subn(r"\b1<<(WORD_[A-Z])", r"VALUE_WORD_MASK(\1)", text)
    if not constants or direct != 2 or re.search(r"\bbit\(WORD_|1<<WORD_", text):
        raise ValueError("value-word constant-mask coverage differs from the pinned source")
    if text.count("command_words |= bit(word_bit);") != 2:
        raise ValueError("candidate changed command-word bookkeeping")
    axis_lines = [
        line
        for line in original.decode().splitlines()
        if "case '" in line and "axis_words |=" in line
    ]
    if len(axis_lines) != 7 or any(line not in text for line in axis_lines):
        raise ValueError("candidate changed source axis-target assignment")
    if (
        text[text.index("case 95:") : text.index("// NOTE: All remaining letters assign values.")]
        != original.decode()[
            original.decode().index("case 95:") : original.decode().index(
                "// NOTE: All remaining letters assign values."
            )
        ]
    ):
        raise ValueError("candidate changed the unresolved M95/command path")
    candidate = text.encode("utf-8")
    patch = "".join(
        difflib.unified_diff(
            original.decode().splitlines(keepends=True),
            text.splitlines(keepends=True),
            fromfile="baseline/grbl/gcode.c",
            tofile="candidate/grbl/gcode.c",
        )
    )
    return candidate, {
        "baseline_sha256": _hash(original),
        "candidate_sha256": _hash(candidate),
        "constant_bit_macro_replacements": constants,
        "direct_constant_shift_replacements": direct,
        "specific_replacements": replacements,
        "helper": HELPER,
        "patch": patch,
        "unchanged_scope": [
            "global bit(n)",
            "axis_words and per-axis target assignment",
            "command_words and M95",
            "motion dispatch",
            "spindle and EEPROM routines",
        ],
    }


def validate_word_indices(header: str) -> dict[str, int]:
    records = re.findall(r"^#define WORD_([A-Z])\s+(\d+)", header, re.MULTILINE)
    actual = {name: int(index) for name, index in records}
    if len(records) != 17 or actual != {name: i for i, name in enumerate(WORD_ORDER)}:
        raise ValueError("candidate requires the pinned 17-word index contract")
    return actual


def _probe_source() -> str:
    lines = ['#include "grbl/grbl.h"', HELPER]
    for name in WORD_ORDER:
        lines.append(
            f"const uint32_t warning_candidate_mask_{name} = VALUE_WORD_MASK(WORD_{name});"
        )
    axes = "|".join(f"VALUE_WORD_MASK(WORD_{name})" for name in ("A", "B", "C", "D", "X", "Y", "Z"))
    full = "|".join(f"VALUE_WORD_MASK(WORD_{name})" for name in WORD_ORDER)
    lines.extend(
        [
            (
                "const uint8_t warning_candidate_duplicate_Z = "
                "(VALUE_WORD_MASK(WORD_Z) & VALUE_WORD_MASK(WORD_Z)) != 0;"
            ),
            (
                "const uint8_t warning_candidate_duplicate_Y = "
                "(VALUE_WORD_MASK(WORD_Y) & VALUE_WORD_MASK(WORD_Y)) != 0;"
            ),
            (
                "const uint8_t warning_candidate_y_z_distinct = "
                "(VALUE_WORD_MASK(WORD_Y) & VALUE_WORD_MASK(WORD_Z)) == 0;"
            ),
            f"const uint32_t warning_candidate_clear_axes = ({full}) & ~({axes});",
            (
                "const uint32_t warning_candidate_preserve_Z = "
                "VALUE_WORD_MASK(WORD_Z) & ~VALUE_WORD_MASK(WORD_Y);"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def prepare(source: Path, archive: Path, compiler_root: Path, output: Path) -> dict:
    if sys.platform != "win32":
        raise ValueError("the pinned candidate compiler requires Windows")
    source, archive, compiler_root = (
        path.resolve(strict=True) for path in (source, archive, compiler_root)
    )
    output = output.resolve()
    if output.exists() or any(
        output.is_relative_to(path) or path.is_relative_to(output)
        for path in (source, compiler_root)
    ):
        raise ValueError("candidate output must be new and separate from source/compiler")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < MIN_FREE_BYTES + 5_000_000:
        raise ValueError("candidate preparation would violate50GiB free-space reserve")
    manifest = verify_source(source)
    validate_word_indices((source / "grbl/gcode.h").read_text(encoding="utf-8"))
    original = (source / "grbl/gcode.c").read_bytes()
    candidate, patch = candidate_bytes(original)
    verify_archive(archive)
    with zipfile.ZipFile(archive) as compressed:
        compiler_files = {
            item.filename: _hash(compressed.read(item))
            for item in compressed.infolist()
            if not item.is_dir()
        }
    _verify_extracted(compiler_root, compiler_files)
    output.mkdir()
    copies = {}
    for variant in ("baseline", "candidate"):
        copied = output / variant
        copied.mkdir()
        for name in manifest:
            path = copied / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(
                candidate
                if variant == "candidate" and name == "grbl/gcode.c"
                else (source / name).read_bytes()
            )
        (copied / "diagnostic-build").mkdir()
        copies[variant] = copied
    logs = []
    compiler = compiler_root / "avr/bin/avr-gcc.exe"
    objects = {}
    for variant, copied in copies.items():
        for level, additional in (("default", []), ("strict", ["-Wshift-overflow=2"])):
            obj = f"diagnostic-build/gcode-{level}.o"
            result = _run_tool(
                compiler, [*FLAGS, *additional, "-c", "grbl/gcode.c", "-o", obj], copied, logs
            )
            raw = (copied / obj).read_bytes()
            if (
                raw[:7] != b"\x7fELF\x01\x01\x01"
                or int.from_bytes(raw[16:18], "little") != 1
                or int.from_bytes(raw[18:20], "little") != 83
            ):
                raise ValueError("candidate comparison must remain relocatable AVR objects only")
            objects[f"{variant}_{level}"] = {
                "sha256": _hash(raw),
                "bytes": len(raw),
                "warnings": [
                    line for line in result.stderr.decode().splitlines() if "warning:" in line
                ],
            }
    probe = copies["candidate"] / "candidate-mask-probes.c"
    probe.write_text(_probe_source(), encoding="utf-8", newline="\n")
    result = _run_tool(
        compiler,
        [
            *FLAGS,
            "-Wshift-overflow=2",
            "-c",
            "candidate-mask-probes.c",
            "-o",
            "diagnostic-build/candidate-mask-probes.o",
        ],
        copies["candidate"],
        logs,
    )
    raw = (copies["candidate"] / "diagnostic-build/candidate-mask-probes.o").read_bytes()
    sections = elf_probe_sections(raw)
    expected = {
        f"warning_candidate_mask_{name}": word_mask(i) for i, name in enumerate(WORD_ORDER)
    } | {
        "warning_candidate_duplicate_Z": 1,
        "warning_candidate_duplicate_Y": 1,
        "warning_candidate_y_z_distinct": 1,
        "warning_candidate_clear_axes": 1023,
        "warning_candidate_preserve_Z": 65536,
    }
    if {name: record["unsigned_little_endian"] for name, record in sections.items()} != expected:
        raise ValueError("candidate static bookkeeping contract probes disagree")
    changed = []
    for variant, copied in copies.items():
        for name, record in manifest.items():
            digest = _hash((copied / name).read_bytes())
            if digest != record["sha256"]:
                changed.append(
                    {
                        "variant": variant,
                        "path": name,
                        "baseline_sha256": record["sha256"],
                        "candidate_sha256": digest,
                    }
                )
    if changed != [
        {
            "variant": "candidate",
            "path": "grbl/gcode.c",
            "baseline_sha256": patch["baseline_sha256"],
            "candidate_sha256": patch["candidate_sha256"],
        }
    ]:
        raise ValueError("candidate changed files outside the approved gcode.c patch")
    _verify_extracted(compiler_root, compiler_files)
    if verify_source(source) != manifest:
        raise ValueError("canonical source changed during candidate preparation")
    report = {
        "schema_version": 1,
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "evidence_class": (
            "copied_source_mask_candidate_and_compile_only_objects_not_runtime_fix_acceptance"
        ),
        "source_revision": SOURCE_REVISION,
        "source_files": manifest,
        "toolchain_archive_sha256": TOOLCHAIN_SHA256,
        "candidate_patch": patch,
        "changed_tracked_files": changed,
        "compile_objects": objects,
        "compile_log": logs,
        "static_probe": {
            "source_sha256": _hash(probe.read_bytes()),
            "object_sha256": _hash(raw),
            "sections": sections,
            "warnings": [
                line for line in result.stderr.decode().splitlines() if "warning:" in line
            ],
        },
        "semantics_scope": [
            "17 distinct representable unsigned value-word bits",
            "Z duplicate and axis-word cleanup bookkeeping only",
            "all axis/command/motion paths unmodified",
            "baseline undefined-C encoding is not a portable behavioral oracle",
        ],
        "remaining_gates": [
            "M95 word_bit path unchanged",
            "spindle recovery/signature unchanged",
            "EEPROM compatibility/algorithm unchanged",
            "no full parser/link/timing/stack/runtime/release/physical validation",
        ],
        "canonical_source_preserved": True,
        "candidate_promoted": False,
        "firmware_linked": False,
        "firmware_executed": False,
        "firmware_flashed": False,
        "hardware_connected": False,
    }
    for name, value in (("report.json", report), ("compile-log.json", logs)):
        with (output / name).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
    (output / "candidate.patch").write_text(patch["patch"], encoding="utf-8", newline="\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--toolchain-archive", type=Path, required=True)
    parser.add_argument("--toolchain-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = prepare(args.source, args.toolchain_archive, args.toolchain_root, args.output_dir)
        print(
            json.dumps(
                {
                    "candidate_promoted": False,
                    "objects": report["compile_objects"],
                    "changed_tracked_files": report["changed_tracked_files"],
                },
                indent=2,
            )
        )
    except (
        OSError,
        ValueError,
        UnicodeError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ) as error:
        print(f"GRBL warning candidate failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
