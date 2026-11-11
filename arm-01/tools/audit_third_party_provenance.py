"""Observe pinned third-party notices without selecting a distribution license.

Reads only explicit project source roots/receipts. No source is executed, no
network is used, and no external CAD, firmware, runtime or license is copied.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

PINS = {
    "thor": ("AngelLM/Thor", "286b081fe6f056d87c379b884781ef77ff6a0159"),
    "fasteners": ("shaise/FreeCAD_FastenersWB", "fddd07af422b7d3a69098b32333711c5eeae184c"),
    "gears": ("looooo/freecad.gears", "ffe86c85e8061546a3fbaa598993d8e1be2b0de2"),
    "grbl": ("AngelLM/grbl", "1f6437a77e3abcb652d3f8ce718faf7e041ae6ff"),
    "ros": ("AngelLM/Thor-ROS", "e11a56b5aa0d89f0b68a3ea7bd084eab4a050952"),
    "asgard": ("AngelLM/Asgard", "30bf2f8850670f728a0f4c3e2e5d22db4f57d8c6"),
}
MAX_DOCUMENT_BYTES = 32 * 1024 * 1024
RUNTIME_SHA256 = "4828741fc91ee37fafcdb97a1abacb18b04ba451ac4372d9ff7a7349b36f4d6d"
TOOLCHAIN_SHA256 = "a54f64755fff4cb792a1495e5defdd789902a2a3503982e81b898299cf39800e"
TOOLCHAIN_ARCHIVE = "avr-gcc-7.3.0-atmel3.6.1-arduino7-i686-w64-mingw32.zip"
CREATOR = "AngelLM and Thor contributors"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes | str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite JSON number")
        return parsed

    def invalid_constant(value):
        raise ValueError(f"nonfinite JSON constant: {value}")

    try:
        value = json.loads(
            data, object_pairs_hook=pairs, parse_float=number, parse_constant=invalid_constant
        )
    except RecursionError as exc:
        raise ValueError("excessive JSON nesting") from exc
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def validate_receipt(value: dict, name: str) -> None:
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("unsupported evidence receipt schema")
    if name == "thor-windows-native-foundation-v1.json":
        source, runtime = value.get("source"), value.get("runtime")
        if not isinstance(source, dict) or not isinstance(runtime, dict):
            raise ValueError("incomplete native source/runtime receipt")
        if (
            source.get("revision") != PINS["thor"][1]
            or type(source.get("native_file_count")) is not int
            or source["native_file_count"] != 57
        ):
            raise ValueError("native receipt source pin/count is unsupported")
        if (
            not isinstance(runtime.get("version"), list)
            or runtime["version"][:3] != ["1", "1", "4"]
            or runtime.get("official_archive_sha256") != RUNTIME_SHA256
        ):
            raise ValueError("native receipt runtime pin is unsupported")
    elif name == "thor-grbl-build-feasibility.json":
        if (
            value.get("evidence_class")
            != "host_avr_cross_compilation_not_firmware_execution_or_hardware_validation"
            or value.get("source_revision") != PINS["grbl"][1]
        ):
            raise ValueError("GRBL receipt source/evidence class is unsupported")
        toolchain, reproduction = value.get("toolchain"), value.get("reproduction")
        if not isinstance(toolchain, dict) or not isinstance(reproduction, dict):
            raise ValueError("incomplete build toolchain receipt")
        if (
            toolchain.get("archive_sha256") != TOOLCHAIN_SHA256
            or toolchain.get("version") != "7.3.0-atmel3.6.1-arduino7"
            or toolchain.get("official_url")
            != f"https://downloads.arduino.cc/tools/{TOOLCHAIN_ARCHIVE}"
        ):
            raise ValueError("unsupported toolchain pin")
        for key, expected in {
            "build_succeeded": True,
            "upstream_original_preserved": True,
            "copied_source_unmodified": True,
            "firmware_executed": False,
            "firmware_flashed": False,
            "hardware_connected": False,
        }.items():
            if value.get(key) is not expected:
                raise ValueError("unsupported build/hardware evidence scope")
    else:
        raise ValueError("unknown evidence receipt")


def scratch_archive_path(project_root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or "\\" in relative or ":" in relative:
        raise ValueError("toolchain archive path must be a normalized relative scratch path")
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != relative
        or not path.parts
        or path.parts[0] != ".work"
    ):
        raise ValueError("toolchain archive path escapes normalized scratch scope")
    if relative != f".work/controller/toolchain/{TOOLCHAIN_ARCHIVE}":
        raise ValueError("unsupported toolchain archive location")
    scratch = (project_root / ".work").resolve(strict=True)
    if not scratch.is_relative_to(project_root.resolve(strict=True)):
        raise ValueError("scratch root symlink escapes project scope")
    candidate = (project_root / path).resolve(strict=True)
    if not candidate.is_relative_to(scratch):
        raise ValueError("toolchain archive symlink escapes scratch scope")
    return candidate


def release_asset(release: dict) -> dict:
    url = "https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4"
    name = "FreeCAD_1.1.4-Windows-x86_64-py311.7z"
    if (
        release.get("tag_name") != "1.1.4"
        or release.get("html_url") != url
        or not isinstance(release.get("assets"), list)
    ):
        raise ValueError("unsupported official runtime release identity")
    selected = [
        row for row in release["assets"] if isinstance(row, dict) and row.get("name") == name
    ]
    if (
        len(selected) != 1
        or selected[0].get("digest") != "sha256:" + RUNTIME_SHA256
        or selected[0].get("browser_download_url")
        != f"https://github.com/FreeCAD/FreeCAD/releases/download/1.1.4/{name}"
    ):
        raise ValueError("unsupported official runtime archive pin")
    return selected[0]


def read_bounded(path: Path, limit: int = MAX_DOCUMENT_BYTES) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"document exceeds audit byte limit: {path.name}")
    return data


def git_tree(root: Path, revision: str) -> dict[str, str]:
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"]).decode().strip()
    if head != revision:
        raise ValueError(f"unexpected pinned source revision: {root.name}")
    output = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "-z", "HEAD"])
    records = {}
    for row in output.split(b"\0"):
        if not row:
            continue
        identity, path = row.split(b"\t", 1)
        _, kind, sha = identity.split()
        if kind == b"blob":
            records[path.decode("utf-8")] = sha.decode("ascii")
    return records


def pinned_bytes(root: Path, path: str, tree: dict[str, str]) -> bytes:
    candidate = (root / path).resolve(strict=True)
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError("source notice escapes its explicit root")
    data = read_bounded(candidate)
    git_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if tree.get(path) != git_blob:
        raise ValueError(f"source bytes differ from pinned Git blob: {path}")
    return data


def notice(data: bytes, path: str, declaration: str, markers: tuple[str, ...]) -> dict:
    try:
        text = data.decode("utf-8")
        decoding = "utf-8"
    except UnicodeDecodeError:
        text = data.decode("latin-1")
        decoding = "latin-1 byte-preserving fallback for notice search"
    lines = text.splitlines()
    found = []
    for marker in markers:
        matches = [index for index, line in enumerate(lines, 1) if marker in line]
        if not matches:
            raise ValueError(f"expected notice marker missing: {path}")
        found.extend(matches)
    return {
        "path": path,
        "bytes": len(data),
        "sha256": digest(data),
        "observed_declaration": declaration,
        "text_decoding": decoding,
        "evidence_lines": sorted(set(found)),
    }


def native_document_license(data: bytes) -> dict:
    """Read saved document properties only; never treat them as resolved terms."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.namelist().count("Document.xml") != 1:
            raise ValueError("expected exactly one native Document.xml")
        info = archive.getinfo("Document.xml")
        if info.file_size > 8 * 1024 * 1024:
            raise ValueError("native XML exceeds audit limit")
        xml = archive.read("Document.xml")
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)\b", xml, re.I):
        raise ValueError("native metadata DTD/entities are not permitted")
    document = ET.fromstring(xml)
    properties = document.find("Properties")
    values = {"License": None, "LicenseURL": None}
    seen = set()
    for item in [] if properties is None else properties:
        name = item.get("name")
        if name in values:
            if name in seen or len(item) != 1:
                raise ValueError("ambiguous native license metadata")
            seen.add(name)
            values[name] = item[0].get("value")
    return {"document_xml_sha256": digest(xml), "saved_properties": values}


def draft_license(data: bytes, expected_license: str, expected_revision: str) -> dict:
    """Check declared metadata of one draft, without validating mesh geometry."""
    metadata = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.namelist().count("3D/3dmodel.model") != 1:
            raise ValueError("expected exactly one generic 3MF model")
        with archive.open("3D/3dmodel.model") as stream:
            # Generated metadata precedes resources; never expand an entire mesh.
            prefix = stream.read(1_048_576)
        if re.search(rb"<!\s*(DOCTYPE|ENTITY)\b", prefix, re.I):
            raise ValueError("draft metadata DTD/entities are not permitted")
        for event, element in ET.iterparse(io.BytesIO(prefix), events=("start", "end")):
            local = element.tag.rsplit("}", 1)[-1]
            if event == "start" and local == "resources":
                break
            if event == "end" and local == "metadata":
                name = element.get("name")
                if name in metadata:
                    raise ValueError("duplicate draft metadata")
                metadata[name] = element.text or ""
        else:
            raise ValueError("draft metadata/resources boundary is missing or excessive")
    text, separator, source = metadata.get("LicenseTerms", "").rpartition("\nSource: ")
    if not separator or digest(text.encode("utf-8")) != expected_license or not source:
        raise ValueError("draft license text/hash or source attribution does not match")

    provenance = strict_json(metadata["raftel:Provenance"])
    designer = metadata.get("Designer", "")
    if (
        provenance.get("source_revision") != expected_revision
        or provenance.get("upstream_license_sha256") != expected_license
        or not isinstance(provenance.get("modifications"), str)
        or not provenance["modifications"].strip()
        or not source.startswith(f"https://github.com/AngelLM/Thor/blob/{expected_revision}/")
        or not (designer == CREATOR or designer.startswith(CREATOR + ";"))
    ):
        raise ValueError("draft source/revision/modification attribution is incomplete")
    qualification = provenance.get("qualification")
    if (
        not isinstance(qualification, dict)
        or qualification.get("manufacturing_release") is not False
    ):
        raise ValueError("draft must retain an explicit false manufacturing release")
    return {
        "archive_sha256": digest(data),
        "designer": metadata["Designer"],
        "source_url": source,
        "source_revision": provenance["source_revision"],
        "license_sha256": expected_license,
        "modification_statement": provenance["modifications"],
        "mesh_origin": provenance.get("mesh_origin", "upstream_published_STL"),
        "geometry_or_process_accepted": False,
        "manufacturing_release": False,
    }


def build_report(project_root: Path) -> dict:
    scratch = project_root / ".work"
    foundation = scratch / "native-foundation"
    specifications = [
        (
            "thor",
            foundation / "Thor-original",
            [
                (
                    "LICENSE",
                    "CC-BY-SA-4.0 repository license text",
                    ("Attribution-ShareAlike 4.0 International",),
                ),
            ],
        ),
        (
            "fasteners",
            foundation / "FreeCAD_FastenersWB",
            [
                (
                    "LICENSE",
                    "GPL version 2 license text",
                    ("GNU GENERAL PUBLIC LICENSE", "Version 2, June 1991"),
                ),
                ("package.xml", "GPL-2.0-or-later package declaration", ("GPL-2.0-or-later",)),
                (
                    "FastenersCmd.py",
                    "GPL version 2 or later file header",
                    ("GNU General Public License", "either version 2", "any later version"),
                ),
                (
                    "screw_maker.py",
                    "LGPL version 2 or later file header",
                    ("GNU Lesser General Public License (LGPL)", "any later version"),
                ),
            ],
        ),
        (
            "gears",
            foundation / "freecad.gears-legacy003",
            [
                (
                    "LICENSE",
                    "GPL version 3 license text",
                    ("GNU GENERAL PUBLIC LICENSE", "Version 3, 29 June 2007"),
                ),
                (
                    "README.md",
                    "GPL version 3 README declaration",
                    ("GNU General Public License v3.0",),
                ),
                (
                    "freecad/gears/features.py",
                    "LGPL version 2 or later file header",
                    ("GNU Lesser General Public License (LGPL)", "any later version"),
                ),
                (
                    "pygears/__init__.py",
                    "LGPL version 2 or later file header",
                    ("GNU Lesser General Public License (LGPL)", "any later version"),
                ),
            ],
        ),
        (
            "grbl",
            scratch / "controller/grbl-source/upstream",
            [
                (
                    "COPYING",
                    "GPL version 3 or later with author notices",
                    ("COPYRIGHT NOTICE FOR GRBL", "GNU GENERAL PUBLIC LICENSE"),
                ),
                (
                    "grbl/main.c",
                    "GPL version 3 or later file header",
                    ("GNU General Public License", "any later version"),
                ),
            ],
        ),
    ]
    components = []
    native = []
    for key, root, selections in specifications:
        repository, revision = PINS[key]
        tree = git_tree(root, revision)
        observed = [
            notice(pinned_bytes(root, path, tree), path, declaration, markers)
            for path, declaration, markers in selections
        ]
        for row in observed:
            row["source_url"] = f"https://github.com/{repository}/blob/{revision}/{row['path']}"
        component = {
            "id": key,
            "repository": f"https://github.com/{repository}",
            "revision": revision,
            "git_tree_file_count": len(tree),
            "notices": observed,
            "applicable_distribution_terms_resolved": None,
        }
        if key == "thor":
            for path in sorted(tree):
                if path.startswith("freecad-src/") and Path(path).suffix.lower() == ".fcstd":
                    data = pinned_bytes(root, path, tree)
                    native.append(
                        {"path": path, "sha256": digest(data), **native_document_license(data)}
                    )
            if len(native) != 57:
                raise ValueError("pinned Thor native source count changed")
            component["native_document_license_metadata"] = native
        components.append(component)
    # Small public source documents were captured separately at immutable URLs.
    remote_notices = []
    for key, name, source_path, expected, declaration, markers in [
        (
            "ros",
            "thor-ros-LICENSE",
            "LICENSE",
            "7abe19ec9bb73b36141b999b861d24ad855e808bafe0f81e84cce28556f6c297",
            "CC-BY-SA-4.0 repository license text",
            ("Attribution-ShareAlike 4.0 International",),
        ),
        (
            "ros",
            "thor-ros-controller-package.xml",
            "ws_thor/src/thor_controller/package.xml",
            "217edb7be38806babd71e178a89eb71ca1df1278621bc9e1e386f177df79bbf6",
            "Apache-2.0 package declaration",
            ("<license>Apache-2.0</license>",),
        ),
        (
            "asgard",
            "asgard-LICENSE",
            "LICENSE",
            "7abe19ec9bb73b36141b999b861d24ad855e808bafe0f81e84cce28556f6c297",
            "CC-BY-SA-4.0 repository license text",
            ("Attribution-ShareAlike 4.0 International",),
        ),
    ]:
        data = read_bounded(scratch / "third-party" / name)
        if digest(data) != expected:
            raise ValueError("captured public source notice hash changed")
        repository, revision = PINS[key]
        remote_notices.append(
            {
                "component": key,
                "repository": f"https://github.com/{repository}",
                "revision": revision,
                "source_url": f"https://github.com/{repository}/blob/{revision}/{source_path}",
                **notice(data, source_path, declaration, markers),
            }
        )
    receipts = []
    receipt_data = {}
    for relative in [
        "arm-01/hardware/cad/thor-windows-native-foundation-v1.json",
        "arm-01/hardware/cad/thor-grbl-build-feasibility.json",
    ]:
        data = read_bounded(project_root / relative)
        receipts.append({"path": relative, "sha256": digest(data)})
        name = Path(relative).name
        parsed = strict_json(data)
        validate_receipt(parsed, name)
        receipt_data[name] = parsed
    runtime_root = scratch / "cad/runtime"
    runtime_docs = []
    for name, declaration, markers in [
        ("LICENSE.html", "Bundled FreeCAD notice declares LGPL2+", ("LGPL2+",)),
        (
            "ThirdPartyLibraries.html",
            "Bundled third-party component notice index; not a complete SBOM",
            ("List of Open Source components",),
        ),
    ]:
        path = f"extracted/FreeCAD_1.1.4-Windows-x86_64-py311/doc/{name}"
        runtime_docs.append(notice(read_bounded(runtime_root / path), path, declaration, markers))
    release_data = read_bounded(runtime_root / "official-release-1.1.4.json")
    release = strict_json(release_data)
    asset = release_asset(release)
    runtime = receipt_data["thor-windows-native-foundation-v1.json"]["runtime"]
    if asset["digest"] != "sha256:" + runtime["official_archive_sha256"]:
        raise ValueError("runtime official release receipt disagrees with native evidence")
    runtime_observation = {
        "version": "1.1.4",
        "release_url": release["html_url"],
        "release_receipt_sha256": digest(release_data),
        "official_archive_sha256": runtime["official_archive_sha256"],
        "archive_hash_rechecked_by_this_audit": False,
        "notices": runtime_docs,
        "all_bundled_dependency_licenses_audited": False,
    }
    build = receipt_data["thor-grbl-build-feasibility.json"]
    toolchain_path = scratch_archive_path(project_root, build["reproduction"]["toolchain_archive"])
    toolchain_bytes = read_bounded(toolchain_path, 64 * 1024 * 1024)
    if digest(toolchain_bytes) != build["toolchain"]["archive_sha256"]:
        raise ValueError("toolchain bytes differ from pinned build receipt")
    with zipfile.ZipFile(io.BytesIO(toolchain_bytes)) as archive:
        toolchain_headers = [
            notice(
                archive.read("avr/avr/include/stdio.h"),
                "avr/avr/include/stdio.h",
                "avr-libc copyright and three-clause redistribution notice",
                (
                    "Redistribution and use in source and binary forms",
                    "Neither the name of the copyright holders",
                ),
            ),
            notice(
                archive.read("avr/lib/gcc/avr/7.3.0/include/stddef.h"),
                "avr/lib/gcc/avr/7.3.0/include/stddef.h",
                "GPL version 3 or later header with GCC Runtime Library Exception version 3.1",
                (
                    "GNU General Public License",
                    "GCC Runtime Library Exception",
                    "3.1, as published",
                ),
            ),
        ]
        standalone_notices = [
            name
            for name in archive.namelist()
            if re.search(r"(?:license|licence|copying|copyright|notice)", name, re.I)
        ]
    toolchain_observation = {
        "version": build["toolchain"]["version"],
        "official_url": build["toolchain"]["official_url"],
        "archive_sha256": digest(toolchain_bytes),
        "archive_hash_rechecked_by_this_audit": True,
        "selected_headers": toolchain_headers,
        "standalone_notice_named_members": standalone_notices,
        "all_toolchain_component_licenses_audited": False,
        "binary_distribution_approved": None,
    }
    expected_license = components[0]["notices"][0]["sha256"]
    drafts = []
    for directory in sorted((scratch / "print-planning").glob("projects*")):
        for path in sorted(directory.glob("*.3mf")):
            drafts.append(
                {
                    "path": path.relative_to(project_root).as_posix(),
                    **draft_license(read_bounded(path), expected_license, PINS["thor"][1]),
                }
            )
    return {
        "schema_version": 1,
        "evidence_class": "pinned_source_notice_and_saved_metadata_observation",
        "components": components,
        "captured_reference_notices": remote_notices,
        "runtime_notice_observation": runtime_observation,
        "toolchain_notice_observation": toolchain_observation,
        "bound_engineering_receipts": receipts,
        "draft_projects_observed": drafts,
        "scope": {
            "all_57_native_license_properties_observed": True,
            "selected_notice_files_match_pinned_git_blobs": True,
            "all_addon_noncode_asset_licenses_audited": False,
            "all_runtime_toolchain_dependency_licenses_audited": False,
        },
        "release_gates": {
            "company_license_selected": None,
            "license_metadata_differences_resolved": None,
            "external_distribution_approved": None,
            "manufacturing_release": False,
        },
        "limitations": [
            "Repository, package, file-header and saved-document declarations remain separate.",
            "This report does not determine legal applicability or approve a distribution.",
            "Draft metadata checks do not qualify geometry, slicing, fit or printed performance.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True, help="fresh evidence file")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.project_root.resolve(strict=True))
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    except (
        ValueError,
        OSError,
        KeyError,
        zipfile.BadZipFile,
        ET.ParseError,
        subprocess.SubprocessError,
    ) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
