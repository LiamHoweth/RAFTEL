#!/usr/bin/env python3
"""Offline cross-build of pinned GRBL Thor, never firmware execution/upload.

Inputs are an already obtained exact clean source checkout and official pinned
Windows AVR compiler archive. This script downloads/installs nothing, invokes
no Makefile target, uploader, serial/USB tool, emulator or resulting firmware.
All extraction, source copying and build outputs stay in a NEW output folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

SOURCE_REVISION = "1f6437a77e3abcb652d3f8ce718faf7e041ae6ff"
SOURCE_TREE = "0748cdaf21d34b189ffb7fd926f6217040e2f952"
TOOLCHAIN_VERSION = "7.3.0-atmel3.6.1-arduino7"
TOOLCHAIN_URL = (
    "https://downloads.arduino.cc/tools/avr-gcc-7.3.0-atmel3.6.1-arduino7-i686-w64-mingw32.zip"
)
TOOLCHAIN_SHA256 = "a54f64755fff4cb792a1495e5defdd789902a2a3503982e81b898299cf39800e"
TOOLCHAIN_ARCHIVE_BYTES = 52_519_412
MIN_FREE_BYTES = 50 * 1024**3
FLAGS = (
    "-Wall",
    "-Os",
    "-DF_CPU=16000000",
    "-mmcu=atmega2560",
    "-I.",
    "-ffunction-sections",
    "-fdata-sections",
)
SOURCES = (
    "main.c",
    "motion_control.c",
    "gcode.c",
    "spindle_control.c",
    "coolant_control.c",
    "serial.c",
    "protocol.c",
    "stepper.c",
    "eeprom.c",
    "settings.c",
    "planner.c",
    "nuts_bolts.c",
    "limits.c",
    "print.c",
    "probe.c",
    "report.c",
    "system.c",
)
PINNED_FILES = {
    "Makefile": "64cbfb821e47b82a8e4d3c7404104d753fba0ed3543e63c0c0df63adb5c73be3",
    "COPYING": "ad370acdba3ebfb015919bb70cdd474d370a6cca956790becf86ea3c0bf2f5b9",
    "grbl/config.h": "a5b19542474d8e8de295c9bec22b5933917d54b1086525cdf6615e3ef25dc17a",
}
ALLOWED_TOOL_NAMES = {"avr-gcc.exe", "avr-objcopy.exe", "avr-size.exe"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative(name: str) -> PurePosixPath:
    if not name or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError("unsafe relative source/archive path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError("unsafe relative source/archive path")
    return path


def _git(source: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(source), *arguments], capture_output=True, timeout=60, check=False
    )
    if result.returncode:
        raise ValueError(
            "source Git verification failed: " + result.stderr.decode(errors="replace")
        )
    return result.stdout


def verify_source(source: Path) -> dict[str, dict]:
    """Verify every tracked on-disk blob against the exact immutable tree."""
    source = source.resolve(strict=True)
    if _git(source, "rev-parse", "HEAD").decode().strip() != SOURCE_REVISION:
        raise ValueError("source HEAD differs from pinned GRBL revision")
    if _git(source, "rev-parse", "HEAD^{tree}").decode().strip() != SOURCE_TREE:
        raise ValueError("source tree differs from pinned GRBL tree")
    if _git(source, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise ValueError("source checkout must be clean, including untracked files")
    entries = _git(source, "ls-tree", "-rz", "HEAD").split(b"\x00")
    manifest = {}
    for entry in entries:
        if not entry:
            continue
        metadata, raw_name = entry.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        name = raw_name.decode("utf-8")
        relative = _relative(name)
        path = source.joinpath(*relative.parts)
        if mode not in {"100644", "100755"} or kind != "blob" or path.is_symlink():
            raise ValueError("source contains unsupported links/submodules or modes")
        if not path.resolve().is_relative_to(source):
            raise ValueError("source path resolves outside the source checkout")
        data = path.read_bytes()
        actual_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()
        if actual_blob != blob:
            raise ValueError(f"source bytes differ from pinned Git blob: {name}")
        manifest[name] = {"git_blob": blob, "sha256": _sha256(data), "bytes": len(data)}
    if len(manifest) != 72:
        raise ValueError("pinned source file coverage differs from the audited 72-file tree")
    for name, expected in PINNED_FILES.items():
        if manifest.get(name, {}).get("sha256") != expected:
            raise ValueError(f"pinned source/notice hash differs: {name}")
    return manifest


def verify_archive(path: Path) -> None:
    if path.stat().st_size != TOOLCHAIN_ARCHIVE_BYTES:
        raise ValueError("official AVR compiler archive size differs from pin")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != TOOLCHAIN_SHA256:
        raise ValueError("official AVR compiler archive SHA-256 differs from pin")


def _extract_archive(archive: Path, destination: Path) -> dict[str, str]:
    """Extract only verified archive members, rejecting traversal and links."""
    if destination.exists():
        raise ValueError("toolchain extraction destination must be new")
    destination.mkdir()
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(archive) as compressed:
        entries = compressed.infolist()
        if len(entries) > 10_000 or sum(item.file_size for item in entries) > 350_000_000:
            raise ValueError("toolchain archive exceeds bounded extraction budget")
        for item in entries:
            path = _relative(item.filename)
            if not path.parts or path.parts[0] != "avr":
                raise ValueError("unexpected toolchain archive root")
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("toolchain archive links are unsupported")
            output = destination.joinpath(*path.parts)
            if not output.resolve().is_relative_to(destination.resolve()):
                raise ValueError("toolchain archive escapes destination")
            if item.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            if item.filename in manifest or output.exists():
                raise ValueError("duplicate compiler archive file")
            output.parent.mkdir(parents=True, exist_ok=True)
            data = compressed.read(item)
            output.write_bytes(data)
            manifest[item.filename] = _sha256(data)
    return manifest


def _verify_extracted(destination: Path, manifest: dict[str, str]) -> None:
    actual = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    }
    if actual != set(manifest):
        raise ValueError("extracted compiler file coverage changed")
    for name, expected in manifest.items():
        path = destination.joinpath(*_relative(name).parts)
        if path.is_symlink() or _sha256(path.read_bytes()) != expected:
            raise ValueError(f"extracted compiler bytes changed: {name}")


def _run_tool(
    tool: Path, arguments: list[str], cwd: Path, logs: list[dict]
) -> subprocess.CompletedProcess:
    if tool.name not in ALLOWED_TOOL_NAMES:
        raise ValueError("only compiler, object conversion and size inspection are permitted")
    # Preserve the host environment globally, but prevent per-user compiler
    # search overrides from escaping the byte-verified diagnostic toolchain.
    compiler_overrides = {
        "GCC_EXEC_PREFIX",
        "COMPILER_PATH",
        "LIBRARY_PATH",
        "CPATH",
        "C_INCLUDE_PATH",
        "CPLUS_INCLUDE_PATH",
        "OBJC_INCLUDE_PATH",
        "GCC_SPECS",
        "CFLAGS",
        "CPPFLAGS",
        "LDFLAGS",
    }
    environment = {
        key: value for key, value in os.environ.items() if key.upper() not in compiler_overrides
    }
    windows_system = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    environment["PATH"] = os.pathsep.join(
        (str(tool.parent), str(tool.parent.parent / "avr/bin"), str(windows_system))
    )
    temporary = cwd.parent / "compiler-temp"
    temporary.mkdir(exist_ok=True)
    environment.update(SOURCE_DATE_EPOCH="0", LC_ALL="C", TEMP=str(temporary), TMP=str(temporary))
    result = subprocess.run(
        [str(tool), *arguments],
        cwd=cwd,
        capture_output=True,
        timeout=90,
        check=False,
        env=environment,
    )
    record = {
        "tool": tool.name,
        "arguments": arguments,
        "returncode": result.returncode,
        "stdout": result.stdout.decode(errors="replace"),
        "stderr": result.stderr.decode(errors="replace"),
    }
    logs.append(record)
    if result.returncode:
        raise ValueError(f"{tool.name} failed with exit {result.returncode}: {record['stderr']}")
    return result


def build(source: Path, archive: Path, output: Path) -> dict:
    if sys.platform != "win32":
        raise ValueError("this pinned compiler artifact requires a Windows host")
    source, archive = source.resolve(strict=True), archive.resolve(strict=True)
    output = output.resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("output must be new and separate from the preserved source checkout")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < MIN_FREE_BYTES + 350_000_000:
        raise ValueError("build would violate the 50 GiB free-space reserve")
    manifest = verify_source(source)
    verify_archive(archive)
    output.mkdir()
    copied = output / "source-copy"
    copied.mkdir()
    for name in manifest:
        path = copied.joinpath(*_relative(name).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.joinpath(*_relative(name).parts).read_bytes())
    compiler_root = output / "toolchain"
    toolchain_manifest = _extract_archive(archive, compiler_root)
    _verify_extracted(compiler_root, toolchain_manifest)
    bin_dir = compiler_root / "avr/bin"
    compiler, objcopy, size = (
        bin_dir / name for name in ("avr-gcc.exe", "avr-objcopy.exe", "avr-size.exe")
    )
    logs: list[dict] = []
    version = _run_tool(compiler, ["--version"], copied, logs).stdout.decode().splitlines()[0]
    if version != "avr-gcc.exe (GCC) 7.3.0":
        (output / "build-log.json").write_text(
            json.dumps(logs, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        raise ValueError("extracted compiler reports unexpected version")
    macros_raw = _run_tool(compiler, [*FLAGS, "-dM", "-E", "grbl/main.c"], copied, logs).stdout
    macros = {}
    for line in macros_raw.decode().splitlines():
        if line.startswith("#define "):
            name, _, value = line[8:].partition(" ")
            macros[name] = value
    selected = {
        key: macros.get(key)
        for key in (
            "DEFAULTS_THOR",
            "CPU_MAP_ATMEGA2560",
            "F_CPU",
            "N_AXIS",
            "__AVR_ATmega2560__",
            "__SIZEOF_DOUBLE__",
            "__SIZEOF_FLOAT__",
            "__SIZEOF_INT__",
            "__SIZEOF_LONG__",
            "COREXY",
        )
    }
    if (
        selected["DEFAULTS_THOR"] != ""
        or selected["CPU_MAP_ATMEGA2560"] != ""
        or selected["N_AXIS"] != "7"
        or selected["__AVR_ATmega2560__"] != "1"
        or selected["COREXY"] is not None
        or selected["__SIZEOF_DOUBLE__"] != "4"
        or selected["__SIZEOF_FLOAT__"] != "4"
        or selected["__SIZEOF_INT__"] != "2"
        or selected["__SIZEOF_LONG__"] != "4"
        or selected["F_CPU"] != "16000000"
    ):
        (output / "build-log.json").write_text(
            json.dumps(logs, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        raise ValueError("selected compile-time Thor/ATmega2560/seven-axis macros differ")
    (copied / "build").mkdir(exist_ok=True)
    objects = []
    try:
        for filename in SOURCES:
            obj = "build/" + filename.removesuffix(".c") + ".o"
            _run_tool(
                compiler, [*FLAGS, "-MMD", "-MP", "-c", "grbl/" + filename, "-o", obj], copied, logs
            )
            objects.append(obj)
        _run_tool(
            compiler,
            [*FLAGS, "-o", "build/main.elf", *objects, "-lm", "-Wl,--gc-sections"],
            copied,
            logs,
        )
        _run_tool(
            objcopy,
            ["-j", ".text", "-j", ".data", "-O", "ihex", "build/main.elf", "build/grbl.hex"],
            copied,
            logs,
        )
        berkeley = _run_tool(
            size, ["--format=berkeley", "build/main.elf"], copied, logs
        ).stdout.decode()
        memory = _run_tool(
            size, ["-C", "--mcu=atmega2560", "build/main.elf"], copied, logs
        ).stdout.decode()
    except (ValueError, subprocess.TimeoutExpired):
        with (output / "build-log.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(logs, stream, indent=2)
            stream.write("\n")
        raise
    _verify_extracted(compiler_root, toolchain_manifest)
    if verify_source(source) != manifest:
        raise ValueError("upstream source changed during build")
    for name, record in manifest.items():
        if _sha256(copied.joinpath(*_relative(name).parts).read_bytes()) != record["sha256"]:
            raise ValueError("copied source changed during compile")
    if shutil.disk_usage(output).free < MIN_FREE_BYTES:
        raise ValueError("post-build free space violates the reserve")
    numbers = berkeley.splitlines()[-1].split()
    text_bytes, data_bytes, bss_bytes = (int(value) for value in numbers[:3])
    report = {
        "schema_version": 1,
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "evidence_class": (
            "host_avr_cross_compilation_not_firmware_execution_or_hardware_validation"
        ),
        "source_revision": SOURCE_REVISION,
        "source_tree": SOURCE_TREE,
        "source_files": manifest,
        "source_file_count": len(manifest),
        "toolchain": {
            "version": TOOLCHAIN_VERSION,
            "compiler_version_line": version,
            "official_url": TOOLCHAIN_URL,
            "archive_sha256": TOOLCHAIN_SHA256,
            "archive_bytes": TOOLCHAIN_ARCHIVE_BYTES,
            "extracted_file_count": len(toolchain_manifest),
            "extracted_manifest_sha256": _sha256(
                json.dumps(toolchain_manifest, sort_keys=True, separators=(",", ":")).encode()
            ),
        },
        "build_flags": FLAGS,
        "compiler_environment": {
            "global_environment_modified": False,
            "path_scope": "byte_verified_toolchain_and_windows_system32_only",
            "compiler_search_overrides_removed": True,
            "temporary_files": "private_per_build_directory",
            "source_date_epoch": "0",
        },
        "translation_units": SOURCES,
        "active_macros": selected,
        "all_macros_sha256": _sha256(macros_raw),
        "artifacts": {
            name: {
                "sha256": _sha256((copied / name).read_bytes()),
                "bytes": (copied / name).stat().st_size,
            }
            for name in ("build/main.elf", "build/grbl.hex")
        },
        "size": {
            "text_bytes": text_bytes,
            "data_bytes": data_bytes,
            "bss_bytes": bss_bytes,
            "flash_image_bytes": text_bytes + data_bytes,
            "static_sram_bytes": data_bytes + bss_bytes,
            "berkeley_output": berkeley,
            "device_memory_output": memory,
        },
        "warning_lines": [
            line for log in logs for line in log["stderr"].splitlines() if "warning:" in line
        ],
        "compiler_command_count": len(logs),
        "build_succeeded": True,
        "upstream_original_preserved": True,
        "copied_source_unmodified": True,
        "firmware_executed": False,
        "firmware_flashed": False,
        "hardware_connected": False,
        "makefile_or_upload_target_invoked": False,
        "license": {
            "upstream": "GPL-3.0-or-later",
            "notice_file": "COPYING",
            "notice_sha256": PINNED_FILES["COPYING"],
            "binary_distribution": "none; diagnostic ELF/HEX remain local ignored scratch",
        },
    }
    for name, value in (("build-log.json", logs), ("report.json", report)):
        with (output / name).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, required=True, help="Exact clean pinned GRBL checkout"
    )
    parser.add_argument(
        "--toolchain-archive", type=Path, required=True, help="Official pinned Windows AVR zip"
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="New isolated scratch build directory"
    )
    args = parser.parse_args(argv)
    try:
        report = build(args.source, args.toolchain_archive, args.output_dir)
        print(
            json.dumps(
                {
                    "build_succeeded": report["build_succeeded"],
                    "artifacts": report["artifacts"],
                    "size": report["size"],
                },
                indent=2,
            )
        )
    except (ValueError, OSError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print(f"GRBL diagnostic build failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
