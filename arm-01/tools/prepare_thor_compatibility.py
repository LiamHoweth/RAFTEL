"""Build a separate static Art1Body geometry/datum snapshot in FreeCAD.

The original editable document is never opened or saved. This converts exact
saved geometry, not the failed procedural feature history. Set
RAFTEL_PREPARE_THOR_COMPAT=1, RAFTEL_THOR_SOURCE, RAFTEL_THOR_OUTPUT and
RAFTEL_THOR_REPORT, then execute this file in a dedicated FreeCAD console.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
SOURCE_SHA256 = "8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a"
DATUM_TYPES = {"PartDesign::CoordinateSystem", "PartDesign::Line"}


def read_reference(source: Path, expected_sha: str = SOURCE_SHA256) -> dict:
    """Read and validate pinned input without importing FreeCAD or running proxies."""
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != expected_sha:
        raise ValueError("Art1Body source SHA-256 differs from the pinned reference")
    with zipfile.ZipFile(source) as archive:
        document = ET.fromstring(archive.read("Document.xml"))
        objects = {
            node.get("name"): node.get("type") for node in document.findall("./Objects/Object")
        }
        if objects.get("Body") != "PartDesign::Body":
            raise ValueError("expected a PartDesign Body")
        body = document.find('./ObjectData/Object[@name="Body"]')
        shape = body.find('./Properties/Property[@name="Shape"]/Part')
        if shape is None:
            raise ValueError("Body has no saved BRep")
        brep = archive.read(shape.get("file"))
        datums = []
        for name, kind in objects.items():
            if kind not in DATUM_TYPES:
                continue
            node = document.find(f'./ObjectData/Object[@name="{name}"]')
            placement = node.find('./Properties/Property[@name="Placement"]/PropertyPlacement')
            if placement is None:
                raise ValueError(f"missing saved placement for {name}")
            values = [
                float(placement.get(key)) for key in ("Px", "Py", "Pz", "Q0", "Q1", "Q2", "Q3")
            ]
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"nonfinite placement for {name}")
            datums.append({"name": name, "type": kind, "placement": values})
        body_placement = body.find('./Properties/Property[@name="Placement"]/PropertyPlacement')
        values = [
            float(body_placement.get(key)) for key in ("Px", "Py", "Pz", "Q0", "Q1", "Q2", "Q3")
        ]
        if values != [0, 0, 0, 0, 0, 0, 1]:
            raise ValueError("this recipe requires the pinned identity Body placement")
    return {
        "source_sha256": digest,
        "brep": brep,
        "brep_sha256": hashlib.sha256(brep).hexdigest(),
        "datums": datums,
    }


def validate_destinations(source: Path, output: Path, report: Path) -> None:
    if output.suffix.casefold() != ".fcstd" or report.suffix.casefold() != ".json":
        raise ValueError("output must be native .FCStd and report must be .json")
    if source.resolve() == output.resolve() or output.exists() or report.exists():
        raise ValueError("use new output/report paths; existing files are never overwritten")
    if output.resolve() == report.resolve():
        raise ValueError("output/report paths must differ")


def prepare(source: Path, output: Path, report_path: Path) -> dict:
    validate_destinations(source, output, report_path)
    reference = read_reference(source)
    import FreeCAD as App
    import Part

    def placement(values):
        return App.Placement(App.Vector(*values[:3]), App.Rotation(*values[3:]))

    def shape_info(shape):
        bounds = shape.BoundBox
        return {
            "valid": shape.isValid(),
            "solid_count": len(shape.Solids),
            "volume_mm3": shape.Volume,
            "bounds_mm": [
                bounds.XMin,
                bounds.XMax,
                bounds.YMin,
                bounds.YMax,
                bounds.ZMin,
                bounds.ZMax,
            ],
        }

    def matrix_values(value):
        return list(value.toMatrix().A)

    previous = set(App.listDocuments())
    doc = None
    report = {
        "source_revision": SOURCE_REVISION,
        "source_sha256": reference["source_sha256"],
        "source_body_brep_sha256": reference["brep_sha256"],
        "freecad_version": list(App.Version()),
        "validation_level": (
            "static saved-geometry/datum compatibility snapshot; "
            "not procedural rebuild or physical validation"
        ),
        "original_procedural_history_preserved_in_upstream": True,
        "datum_count": len(reference["datums"]),
    }
    try:
        with tempfile.TemporaryDirectory(prefix="raftel-brep-", dir=output.parent) as directory:
            path = Path(directory) / "source-body.brp"
            path.write_bytes(reference["brep"])
            original = Part.Shape()
            original.read(str(path))
        if not original.isValid() or len(original.Solids) != 1:
            raise ValueError("saved Body must be one valid solid")
        doc = App.newDocument("Art1Body")
        body = doc.addObject("PartDesign::Body", "Body")
        feature = doc.addObject("PartDesign::Feature", "FrozenSourceSolid")
        body.addObject(feature)
        feature.Shape = original.copy()
        body.Tip = feature
        body.addProperty("App::PropertyString", "RaftelSnapshotKind")
        body.RaftelSnapshotKind = (
            "Static cached source geometry; original editable history remains separate"
        )
        body.addProperty("App::PropertyString", "RaftelSourceRevision")
        body.RaftelSourceRevision = SOURCE_REVISION
        body.addProperty("App::PropertyString", "RaftelSourceBrepSHA256")
        body.RaftelSourceBrepSHA256 = reference["brep_sha256"]
        for item in reference["datums"]:
            datum = doc.addObject(item["type"], item["name"])
            body.addObject(datum)
            datum.MapMode = "Deactivated"
            datum.Placement = placement(item["placement"])
        doc.recompute(None, True)
        report["before"] = shape_info(original)
        report["prepared"] = shape_info(body.Shape)
        doc.saveAs(str(output))
        App.closeDocument(doc.Name)
        doc = App.openDocument(str(output))
        doc.recompute(None, True)
        actual = doc.getObject("Body").Shape
        report["reopened"] = shape_info(actual)
        report["symmetric_difference_mm3"] = (
            actual.cut(original).Volume + original.cut(actual).Volume
        )
        mismatches = []
        for item in reference["datums"]:
            expected = matrix_values(placement(item["placement"]))
            actual_matrix = matrix_values(doc.getObject(item["name"]).getGlobalPlacement())
            error = max(abs(a - b) for a, b in zip(expected, actual_matrix, strict=True))
            if error > 1e-12:
                mismatches.append({"name": item["name"], "matrix_max_abs_error": error})
        report["datum_matrix_mismatches"] = mismatches
        report["object_states"] = {obj.Name: list(obj.State) for obj in doc.Objects}
        report["source_unchanged"] = (
            hashlib.sha256(source.read_bytes()).hexdigest() == reference["source_sha256"]
        )
        report["output_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
        invalid = [
            name
            for name, states in report["object_states"].items()
            if "Invalid" in states or "Touched" in states
        ]
        report["body_bounds_max_abs_error_mm"] = max(
            abs(a - b)
            for a, b in zip(
                report["before"]["bounds_mm"], report["reopened"]["bounds_mm"], strict=True
            )
        )
        report["validated_static_snapshot"] = (
            not invalid
            and not mismatches
            and report["source_unchanged"]
            and report["reopened"]["valid"]
            and report["reopened"]["solid_count"] == 1
            and report["symmetric_difference_mm3"] == 0
            and report["body_bounds_max_abs_error_mm"] < 1e-9
            and abs(actual.Volume - original.Volume) < 1e-6
        )
        with report_path.open("x") as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        if not report["validated_static_snapshot"]:
            raise ValueError("snapshot validation failed; inspect report, do not adopt the file")
        return report
    finally:
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)


def main() -> None:
    prepare(
        Path(os.environ["RAFTEL_THOR_SOURCE"]),
        Path(os.environ["RAFTEL_THOR_OUTPUT"]),
        Path(os.environ["RAFTEL_THOR_REPORT"]),
    )


if __name__ == "__main__" or os.environ.get("RAFTEL_PREPARE_THOR_COMPAT") == "1":
    main()
