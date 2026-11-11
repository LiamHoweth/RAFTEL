"""Guard tests use synthetic files; actual AVR build evidence is a separate capture."""

import hashlib
import importlib.util
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools/build_thor_grbl_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("build_thor_grbl_diagnostic", TOOL)
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


def synthetic_source(tmp_path, monkeypatch):
    source = tmp_path / "synthetic-source"
    source.mkdir()
    listing = []
    for i in range(72):
        name = f"file-{i:02}.c"
        content = f"synthetic guard fixture {i}\n".encode()
        (source / name).write_bytes(content)
        blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        listing.append(f"100644 blob {blob}\t{name}\0".encode())
    outputs = {
        ("rev-parse", "HEAD"): BUILD.SOURCE_REVISION.encode() + b"\n",
        ("rev-parse", "HEAD^{tree}"): BUILD.SOURCE_TREE.encode() + b"\n",
        ("status", "--porcelain=v1", "--untracked-files=all"): b"",
        ("ls-tree", "-rz", "HEAD"): b"".join(listing),
    }
    monkeypatch.setattr(BUILD, "_git", lambda path, *args: outputs[args])
    monkeypatch.setattr(BUILD, "PINNED_FILES", {})
    return source, outputs


def test_source_validation_reconciles_all_blob_bytes_and_detects_tampering(tmp_path, monkeypatch):
    source, _ = synthetic_source(tmp_path, monkeypatch)
    manifest = BUILD.verify_source(source)
    assert len(manifest) == 72
    (source / "file-20.c").write_bytes(b"changed cached source")
    with pytest.raises(ValueError, match="bytes differ"):
        BUILD.verify_source(source)


@pytest.mark.parametrize(
    "command,value,reason",
    [
        (("rev-parse", "HEAD"), b"different\n", "HEAD"),
        (("rev-parse", "HEAD^{tree}"), b"different\n", "tree"),
        (("status", "--porcelain=v1", "--untracked-files=all"), b"?? local.c\n", "clean"),
    ],
)
def test_wrong_revision_tree_or_dirty_source_fails(tmp_path, monkeypatch, command, value, reason):
    source, outputs = synthetic_source(tmp_path, monkeypatch)
    outputs[command] = value
    with pytest.raises(ValueError, match=reason):
        BUILD.verify_source(source)


def test_archive_size_and_published_digest_checked_before_extraction(tmp_path, monkeypatch):
    archive = tmp_path / "synthetic.zip"
    archive.write_bytes(b"synthetic archive guard fixture")
    with pytest.raises(ValueError, match="size"):
        BUILD.verify_archive(archive)
    monkeypatch.setattr(BUILD, "TOOLCHAIN_ARCHIVE_BYTES", archive.stat().st_size)
    with pytest.raises(ValueError, match="SHA-256"):
        BUILD.verify_archive(archive)
    monkeypatch.setattr(BUILD, "TOOLCHAIN_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    BUILD.verify_archive(archive)


def test_extracted_compiler_file_coverage_and_hashes_fail_closed(tmp_path):
    archive = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(archive, "w") as compressed:
        compressed.writestr("avr/bin/test.exe", b"not an executable; guard fixture only")
        compressed.writestr("avr/lib/specs", b"synthetic specs")
    output = tmp_path / "extracted"
    manifest = BUILD._extract_archive(archive, output)
    BUILD._verify_extracted(output, manifest)
    (output / "avr/lib/specs").write_bytes(b"modified specs")
    with pytest.raises(ValueError, match="bytes changed"):
        BUILD._verify_extracted(output, manifest)
    (output / "unexpected.dll").write_bytes(b"extra")
    with pytest.raises(ValueError, match="coverage"):
        BUILD._verify_extracted(output, manifest)


@pytest.mark.parametrize(
    "name", ["../escape", "avr/../../escape", "C:/escape", "other/bin/compiler"]
)
def test_zip_traversal_and_unexpected_roots_rejected(tmp_path, name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as compressed:
        compressed.writestr(name, b"bad")
    with pytest.raises(ValueError):
        BUILD._extract_archive(archive, tmp_path / "output")
    assert not (tmp_path / "escape").exists()


def test_raw_backslash_path_is_rejected_before_normalization():
    with pytest.raises(ValueError, match="unsafe"):
        BUILD._relative(r"avr\bin\escape")


def test_archive_links_and_existing_destination_rejected(tmp_path):
    archive = tmp_path / "link.zip"
    with zipfile.ZipFile(archive, "w") as compressed:
        link = zipfile.ZipInfo("avr/bin/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        compressed.writestr(link, "../../escape")
    with pytest.raises(ValueError, match="links"):
        BUILD._extract_archive(archive, tmp_path / "new")
    with pytest.raises(ValueError, match="new"):
        BUILD._extract_archive(archive, tmp_path / "new")


def test_uploaders_make_and_firmware_execution_are_not_permitted(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("a disallowed executable must never be invoked")

    monkeypatch.setattr(BUILD.subprocess, "run", forbidden)
    for name in ("avrdude.exe", "make.exe", "grbl.hex", "emulator.exe", "powershell.exe"):
        with pytest.raises(ValueError, match="only compiler"):
            BUILD._run_tool(tmp_path / name, [], tmp_path, [])
    assert BUILD.ALLOWED_TOOL_NAMES == {"avr-gcc.exe", "avr-objcopy.exe", "avr-size.exe"}


def test_fixed_cross_compile_flags_and_units_match_pinned_makefile_scope():
    assert "-mmcu=atmega2560" in BUILD.FLAGS
    assert "-DF_CPU=16000000" in BUILD.FLAGS
    assert len(BUILD.SOURCES) == 17
    assert BUILD.SOURCE_REVISION == "1f6437a77e3abcb652d3f8ce718faf7e041ae6ff"
    assert BUILD.MIN_FREE_BYTES == 50 * 1024**3
    assert not any("flash" in flag or "upload" in flag for flag in BUILD.FLAGS)


def test_compiler_environment_is_child_only_and_search_overrides_are_removed(tmp_path, monkeypatch):
    cwd = tmp_path / "source-copy"
    cwd.mkdir()
    monkeypatch.setenv("GCC_EXEC_PREFIX", "unverified-global-prefix")
    monkeypatch.setenv("C_INCLUDE_PATH", "unverified-global-headers")
    monkeypatch.setenv("PATH", "unverified-global-compiler")
    observed = {}

    def run(arguments, **kwargs):
        observed.update(kwargs)
        return subprocess.CompletedProcess(arguments, 0, b"synthetic guard output", b"")

    monkeypatch.setattr(BUILD.subprocess, "run", run)
    BUILD._run_tool(tmp_path / "toolchain/avr/bin/avr-gcc.exe", ["--version"], cwd, [])
    assert "GCC_EXEC_PREFIX" not in observed["env"]
    assert "C_INCLUDE_PATH" not in observed["env"]
    assert "unverified-global-compiler" not in observed["env"]["PATH"]
    assert observed["env"]["SOURCE_DATE_EPOCH"] == "0"
    assert Path(observed["env"]["TEMP"]).is_relative_to(tmp_path)
    assert BUILD.os.environ["GCC_EXEC_PREFIX"] == "unverified-global-prefix"
    assert BUILD.os.environ["PATH"] == "unverified-global-compiler"


def test_existing_or_overlapping_output_and_disk_reserve_fail_before_execution(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(BUILD.sys, "platform", "win32")
    source, archive = tmp_path / "source", tmp_path / "compiler.zip"
    source.mkdir()
    archive.write_bytes(b"no executable")
    for output in (source / "build", tmp_path):
        with pytest.raises(ValueError, match="new and separate"):
            BUILD.build(source, archive, output)
    monkeypatch.setattr(
        BUILD.shutil,
        "disk_usage",
        lambda path: type("Usage", (), {"free": BUILD.MIN_FREE_BYTES - 1})(),
    )
    with pytest.raises(ValueError, match="50 GiB"):
        BUILD.build(source, archive, tmp_path / "new-build")
