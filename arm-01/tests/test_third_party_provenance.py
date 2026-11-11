"""Synthetic notice/metadata fixtures; no licensed CAD or firmware is vendored."""

import copy
import hashlib
import importlib.util
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "third_party_audit", Path(__file__).parents[1] / "tools/audit_third_party_provenance.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def archive(name, data):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as output:
        output.writestr(name, data)
    return stream.getvalue()


def test_saved_document_metadata_is_not_replaced_by_repository_terms():
    xml = (
        b'<Document><Properties><Property name="License"><String value="All rights reserved"/>'
        b'</Property><Property name="LicenseURL"><String value="http://example.invalid/saved"/>'
        b"</Property></Properties></Document>"
    )
    result = audit.native_document_license(archive("Document.xml", xml))
    assert result["saved_properties"] == {
        "License": "All rights reserved",
        "LicenseURL": "http://example.invalid/saved",
    }
    assert result["document_xml_sha256"] == hashlib.sha256(xml).hexdigest()
    assert "applicable_license" not in result


def test_missing_saved_metadata_remains_unknown():
    result = audit.native_document_license(archive("Document.xml", b"<Document/>"))
    assert result["saved_properties"] == {"License": None, "LicenseURL": None}


@pytest.mark.parametrize(
    "xml",
    [
        b'<!DOCTYPE Document [<!ENTITY x "unsafe">]><Document/>',
        b'<Document><Properties><Property name="License"><String/></Property>'
        b'<Property name="License"><String/></Property></Properties></Document>',
        b'<Document><Properties><Property name="License"><String/><String/>'
        b"</Property></Properties></Document>",
    ],
)
def test_ambiguous_or_entity_native_metadata_rejects(xml):
    with pytest.raises(ValueError):
        audit.native_document_license(archive("Document.xml", xml))


def test_native_missing_or_duplicate_xml_rejects():
    with pytest.raises(ValueError):
        audit.native_document_license(archive("other.xml", b"<Document/>"))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as output:
        output.writestr("Document.xml", b"<Document/>")
        with pytest.warns(UserWarning, match="Duplicate"):
            output.writestr("Document.xml", b"<Document/>")
    with pytest.raises(ValueError):
        audit.native_document_license(stream.getvalue())


def test_notice_search_keeps_exact_bytes_and_explicit_decoding():
    data = b"Copyright fixture\nGNU Lesser General Public License\n\xb1\n"
    record = audit.notice(data, "fixture.h", "observed fixture only", ("GNU Lesser",))
    assert record["sha256"] == hashlib.sha256(data).hexdigest()
    assert record["evidence_lines"] == [2]
    assert "latin-1" in record["text_decoding"]
    with pytest.raises(ValueError, match="marker"):
        audit.notice(data, "fixture.h", "not inferred", ("absent declaration",))


def test_selected_source_hashes_and_root_containment(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    path = root / "LICENSE"
    path.write_bytes(b"fixture\n")
    tree = {"LICENSE": hashlib.sha1(b"blob 8\0fixture\n").hexdigest()}
    assert audit.pinned_bytes(root, "LICENSE", tree) == b"fixture\n"
    path.write_bytes(b"changed\n")
    with pytest.raises(ValueError, match="pinned Git blob"):
        audit.pinned_bytes(root, "LICENSE", tree)
    (tmp_path / "outside").write_text("unrelated")
    with pytest.raises(ValueError, match="escapes"):
        audit.pinned_bytes(root, "../outside", {})


def test_bounded_notice_reader(tmp_path):
    path = tmp_path / "file"
    path.write_bytes(b"1234")
    assert audit.read_bounded(path, 4) == b"1234"
    with pytest.raises(ValueError, match="limit"):
        audit.read_bounded(path, 3)


LICENSE = b"Synthetic license fixture only\n"
LICENSE_SHA = hashlib.sha256(LICENSE).hexdigest()
REVISION = "fixture-revision"


def draft(*, change=None, provenance_text=None, resources=True):
    provenance = {
        "source_revision": REVISION,
        "upstream_license_sha256": LICENSE_SHA,
        "modifications": "synthetic fixture translation only",
        "qualification": {"manufacturing_release": False},
    }
    metadata = {
        "Designer": "AngelLM and Thor contributors; synthetic test attribution",
        "LicenseTerms": LICENSE.decode() + "\nSource: "
        f"https://github.com/AngelLM/Thor/blob/{REVISION}/stl/fixture.stl",
        "raftel:Provenance": provenance,
    }
    if change:
        change(metadata)
    model = ET.Element("model")
    for key, value in metadata.items():
        if key == "raftel:Provenance":
            value = provenance_text if provenance_text is not None else json.dumps(value)
        ET.SubElement(model, "metadata", {"name": key}).text = value
    if resources:
        ET.SubElement(model, "resources")
    return archive("3D/3dmodel.model", ET.tostring(model))


def test_draft_notice_audit_does_not_upgrade_geometry_or_release():
    data = draft()
    result = audit.draft_license(data, LICENSE_SHA, REVISION)
    assert result["archive_sha256"] == hashlib.sha256(data).hexdigest()
    assert result["license_sha256"] == LICENSE_SHA
    assert result["geometry_or_process_accepted"] is False
    assert result["manufacturing_release"] is False


@pytest.mark.parametrize(
    "change",
    [
        lambda metadata: metadata.update(LicenseTerms="changed"),
        lambda metadata: metadata.update(Designer="unrelated"),
        lambda metadata: metadata["raftel:Provenance"].update(source_revision="stale"),
        lambda metadata: metadata["raftel:Provenance"].update(modifications=""),
        lambda metadata: metadata["raftel:Provenance"].update(
            qualification={"manufacturing_release": True}
        ),
        lambda metadata: metadata["raftel:Provenance"].update(qualification=False),
        lambda metadata: metadata.update(
            LicenseTerms=LICENSE.decode() + "\nSource: https://unrelated.invalid"
        ),
    ],
)
def test_draft_stale_or_incomplete_attribution_and_release_flags_reject(change):
    with pytest.raises(ValueError):
        audit.draft_license(draft(change=change), LICENSE_SHA, REVISION)


def test_draft_duplicate_provenance_and_missing_boundary_reject():
    with pytest.raises(ValueError, match="duplicate"):
        audit.draft_license(draft(provenance_text='{"key":1,"key":2}'), LICENSE_SHA, REVISION)
    with pytest.raises((ValueError, ET.ParseError)):
        audit.draft_license(draft(resources=False), LICENSE_SHA, REVISION)


@pytest.mark.parametrize(
    "text",
    [
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":-Infinity}',
        '{"x":1e309}',
        '{"x":[1e309]}',
        '{"x":1,"x":2}',
        "[]",
    ],
)
def test_strict_receipt_and_provenance_json_rejects_ambiguous_or_nonfinite_values(text):
    with pytest.raises(ValueError):
        audit.strict_json(text)


def test_partial_designer_and_nonfinite_draft_provenance_reject():
    with pytest.raises(ValueError):
        audit.draft_license(
            draft(change=lambda metadata: metadata.update(Designer="AngelLM")),
            LICENSE_SHA,
            REVISION,
        )
    with pytest.raises(ValueError):
        audit.draft_license(draft(provenance_text='{"extra":NaN}'), LICENSE_SHA, REVISION)


def native_receipt():
    return {
        "schema_version": 1,
        "source": {"revision": audit.PINS["thor"][1], "native_file_count": 57},
        "runtime": {"version": ["1", "1", "4"], "official_archive_sha256": audit.RUNTIME_SHA256},
    }


def build_receipt():
    return {
        "schema_version": 1,
        "source_revision": audit.PINS["grbl"][1],
        "evidence_class": (
            "host_avr_cross_compilation_not_firmware_execution_or_hardware_validation"
        ),
        "toolchain": {
            "archive_sha256": audit.TOOLCHAIN_SHA256,
            "version": "7.3.0-atmel3.6.1-arduino7",
            "official_url": f"https://downloads.arduino.cc/tools/{audit.TOOLCHAIN_ARCHIVE}",
        },
        "reproduction": {
            "toolchain_archive": f".work/controller/toolchain/{audit.TOOLCHAIN_ARCHIVE}"
        },
        "build_succeeded": True,
        "upstream_original_preserved": True,
        "copied_source_unmodified": True,
        "firmware_executed": False,
        "firmware_flashed": False,
        "hardware_connected": False,
    }


@pytest.mark.parametrize(
    "factory,name,mutation",
    [
        (
            native_receipt,
            "thor-windows-native-foundation-v1.json",
            lambda row: row.update(schema_version=True),
        ),
        (
            native_receipt,
            "thor-windows-native-foundation-v1.json",
            lambda row: row["source"].update(revision="0" * 40),
        ),
        (
            native_receipt,
            "thor-windows-native-foundation-v1.json",
            lambda row: row["source"].update(native_file_count=True),
        ),
        (
            native_receipt,
            "thor-windows-native-foundation-v1.json",
            lambda row: row["runtime"].update(version=["9"]),
        ),
        (
            native_receipt,
            "thor-windows-native-foundation-v1.json",
            lambda row: row["runtime"].update(official_archive_sha256="0" * 64),
        ),
        (
            build_receipt,
            "thor-grbl-build-feasibility.json",
            lambda row: row.update(schema_version=True),
        ),
        (
            build_receipt,
            "thor-grbl-build-feasibility.json",
            lambda row: row.update(evidence_class="fabricated"),
        ),
        (
            build_receipt,
            "thor-grbl-build-feasibility.json",
            lambda row: row.update(source_revision="0" * 40),
        ),
        (
            build_receipt,
            "thor-grbl-build-feasibility.json",
            lambda row: row.update(hardware_connected=True),
        ),
        (
            build_receipt,
            "thor-grbl-build-feasibility.json",
            lambda row: row["toolchain"].update(archive_sha256="0" * 64),
        ),
    ],
)
def test_receipt_schema_source_class_and_runtime_toolchain_pins_fail_closed(
    factory, name, mutation
):
    record = factory()
    audit.validate_receipt(record, name)
    mutation(record)
    with pytest.raises(ValueError):
        audit.validate_receipt(record, name)


@pytest.mark.parametrize(
    "relative",
    [
        ".work/../../../forbidden.zip",
        "../outside.zip",
        "/absolute.zip",
        "C:/forbidden.zip",
        ".work\\forbidden.zip",
        ".work//forbidden.zip",
        "other/archive.zip",
    ],
)
def test_receipt_paths_cannot_select_files_outside_explicit_scratch(tmp_path, relative):
    with pytest.raises(ValueError):
        audit.scratch_archive_path(tmp_path, relative)


def test_expected_scratch_path_and_symlink_containment(tmp_path):
    candidate = tmp_path / ".work/controller/toolchain" / audit.TOOLCHAIN_ARCHIVE
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"synthetic archive only")
    relative = f".work/controller/toolchain/{audit.TOOLCHAIN_ARCHIVE}"
    assert audit.scratch_archive_path(tmp_path, relative) == candidate.resolve()
    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"unrelated")
    candidate.unlink()
    try:
        candidate.symlink_to(outside)
    except OSError:
        pytest.skip("host does not permit unprivileged file symlinks")
    with pytest.raises(ValueError, match="escapes"):
        audit.scratch_archive_path(tmp_path, relative)


def test_release_identity_and_archive_pin_are_checked():
    name = "FreeCAD_1.1.4-Windows-x86_64-py311.7z"
    original = {
        "tag_name": "1.1.4",
        "html_url": "https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4",
        "assets": [
            {
                "name": name,
                "digest": "sha256:" + audit.RUNTIME_SHA256,
                "browser_download_url": f"https://github.com/FreeCAD/FreeCAD/releases/download/1.1.4/{name}",
            }
        ],
    }
    assert audit.release_asset(original) == original["assets"][0]
    for key, value in [
        ("tag_name", "other"),
        ("html_url", "https://unrelated.invalid"),
        ("assets", []),
    ]:
        record = copy.deepcopy(original)
        record[key] = value
        with pytest.raises(ValueError):
            audit.release_asset(record)
    record = copy.deepcopy(original)
    record["assets"][0]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        audit.release_asset(record)
