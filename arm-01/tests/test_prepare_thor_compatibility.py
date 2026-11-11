"""Guard the native snapshot recipe without requiring FreeCAD in ordinary CI."""

import hashlib
import runpy
import zipfile
from pathlib import Path

import pytest

TOOLS = runpy.run_path(str(Path(__file__).parents[1] / "tools" / "prepare_thor_compatibility.py"))


def native_fixture(path, *, body_position="0", datum_position="1"):
    placement = (
        f'<PropertyPlacement Px="{body_position}" Py="0" Pz="0" Q0="0" Q1="0" Q2="0" Q3="1"/>'
    )
    datum = f'<PropertyPlacement Px="{datum_position}" Py="2" Pz="3" Q0="0" Q1="0" Q2="0" Q3="1"/>'
    xml = f"""<Document><Objects>
<Object name="Body" type="PartDesign::Body"/>
<Object name="LCS_Bot" type="PartDesign::CoordinateSystem"/>
</Objects><ObjectData>
<Object name="Body"><Properties>
<Property name="Shape"><Part file="body.brp"/></Property>
<Property name="Placement">{placement}</Property>
</Properties></Object>
<Object name="LCS_Bot"><Properties>
<Property name="Placement">{datum}</Property>
</Properties></Object>
</ObjectData></Document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Document.xml", xml)
        archive.writestr("body.brp", b"test saved geometry")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_saved_geometry_and_datum_metadata_are_read_without_running_cad(tmp_path):
    source = tmp_path / "Art1Body.fcstd"
    digest = native_fixture(source)
    data = TOOLS["read_reference"](source, digest)
    assert data["source_sha256"] == digest
    assert data["brep"] == b"test saved geometry"
    assert data["datums"] == [
        {
            "name": "LCS_Bot",
            "type": "PartDesign::CoordinateSystem",
            "placement": [1, 2, 3, 0, 0, 0, 1],
        }
    ]


def test_source_hash_mismatch_rejected_before_importing_cad(tmp_path):
    source = tmp_path / "Art1Body.fcstd"
    native_fixture(source)
    with pytest.raises(ValueError, match="SHA-256"):
        TOOLS["read_reference"](source)


def test_nonidentity_body_placement_rejected_instead_of_double_transform(tmp_path):
    source = tmp_path / "Art1Body.fcstd"
    digest = native_fixture(source, body_position="10")
    with pytest.raises(ValueError, match="identity Body"):
        TOOLS["read_reference"](source, digest)


def test_nonfinite_datum_rejected(tmp_path):
    source = tmp_path / "Art1Body.fcstd"
    digest = native_fixture(source, datum_position="nan")
    with pytest.raises(ValueError, match="nonfinite"):
        TOOLS["read_reference"](source, digest)


def test_source_and_existing_outputs_are_never_overwritten(tmp_path):
    source = tmp_path / "Art1Body.fcstd"
    source.write_bytes(b"original")
    with pytest.raises(ValueError, match="never overwritten"):
        TOOLS["validate_destinations"](source, source, tmp_path / "new.json")
    output = tmp_path / "output.FCStd"
    output.write_bytes(b"previous work")
    with pytest.raises(ValueError, match="never overwritten"):
        TOOLS["validate_destinations"](source, output, tmp_path / "new.json")
    assert source.read_bytes() == b"original" and output.read_bytes() == b"previous work"


def test_report_extension_and_new_report_guard(tmp_path):
    source = tmp_path / "Art1Body.fcstd"
    source.write_bytes(b"original")
    with pytest.raises(ValueError, match="report must be .json"):
        TOOLS["validate_destinations"](source, tmp_path / "new.fcstd", tmp_path / "report.fcstd")
    report = tmp_path / "old.json"
    report.write_text("retained evidence")
    with pytest.raises(ValueError, match="never overwritten"):
        TOOLS["validate_destinations"](source, tmp_path / "new.fcstd", report)
    assert report.read_text() == "retained evidence"
