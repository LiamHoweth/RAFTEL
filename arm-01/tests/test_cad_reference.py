"""Source-container checks need no CAD application or network."""

from pathlib import Path
import runpy
import zipfile

import pytest

inspect_reference = runpy.run_path(
    str(Path(__file__).parents[1] / "tools" / "inspect_thor_reference.py")
)["inspect_reference"]


def native(directory, name, references=()):
    links = "".join(f'<XLink file="{reference}"/>' for reference in references)
    with zipfile.ZipFile(directory / name, "w") as archive:
        archive.writestr("Document.xml", f"<Document>{links}</Document>")


def test_exact_reference(tmp_path):
    native(tmp_path, "Assembly.FCStd", ["Part.fcstd"])
    native(tmp_path, "Part.fcstd")
    result = inspect_reference(tmp_path)
    assert result["parsed_file_count"] == 2
    assert not result["reference_filename_case_mismatches"]
    assert not result["missing_reference_files"]
    assert len(result["files"][0]["sha256"]) == 64


def test_extension_case_mismatch_even_on_case_insensitive_host(tmp_path):
    native(tmp_path, "Assembly.FCStd", ["Part.FCStd"])
    native(tmp_path, "Part.fcstd")
    result = inspect_reference(tmp_path)
    assert result["reference_filename_case_mismatches"] == {"Part.FCStd": ["Part.fcstd"]}
    assert not result["missing_reference_files"]


def test_missing_reference(tmp_path):
    native(tmp_path, "Assembly.FCStd", ["Missing.FCStd"])
    assert inspect_reference(tmp_path)["missing_reference_files"] == ["Missing.FCStd"]


def test_bad_container_reported(tmp_path):
    (tmp_path / "Broken.fcstd").write_text("not a ZIP")
    result = inspect_reference(tmp_path)
    assert result["errors"][0]["path"] == "Broken.fcstd"
    assert result["parsed_file_count"] == 0


def test_empty_or_absent_source_rejected(tmp_path):
    with pytest.raises(ValueError, match="No FreeCAD"):
        inspect_reference(tmp_path)
    with pytest.raises(ValueError, match="Not a source"):
        inspect_reference(tmp_path / "absent")
