"""Inspect selected Thor cylinder axes and finger bounds in a dedicated FreeCAD console.

Set RAFTEL_RUN_THOR_AXIS_PROBE=1, RAFTEL_THOR_AXIS_SOURCE to a compatible copied
Assembly.FCStd, and RAFTEL_THOR_AXIS_REPORT to a new JSON report. Cached shapes
are inspected without recompute/save. Addon setup is documented separately.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

SELECTED = {
    "AssemblyBase": ("Bearing_16014zz001",),
    "AssemblyArt2": ("Bearing_625ZZ001", "Bearing_625ZZ002"),
    "AssemblyArt4": ("Art4TransmissionColumn_Art4TransmissionColumn", "Bearing_625ZZ001"),
    "AssemblyArt56": ("Bearing_625ZZ001",),
}


def main() -> None:
    source = Path(os.environ["RAFTEL_THOR_AXIS_SOURCE"])
    output = Path(os.environ["RAFTEL_THOR_AXIS_REPORT"])
    if not source.is_file() or source.suffix.casefold() != ".fcstd":
        raise ValueError("source must be an existing native working-copy assembly")
    if output.exists() or output.suffix.lower() != ".json":
        raise ValueError("report must be a new JSON path")
    import FreeCAD as App
    import Part

    previous = set(App.listDocuments())
    report = {
        "validation_class": "native cached analytic geometry, not physical calibration",
        "freecad_version": list(App.Version()),
        "objects": [],
        "errors": [],
        "recomputed": False,
        "saved_source_changes": False,
    }
    fixture = Part.makeCylinder(5, 10)
    fixture.translate(App.Vector(10, 20, 30))
    surface = next(
        face.Surface for face in fixture.Faces if type(face.Surface).__name__ == "Cylinder"
    )
    report["surface_coordinate_fixture"] = {
        "translated_cylinder_center_mm": list(surface.Center),
        "expected_mm": [10, 20, 30],
    }
    try:
        master = App.openDocument(str(source), True)
        for docname, names in SELECTED.items():
            document = App.getDocument(docname)
            ancestor = master.getObject(docname).LinkPlacement
            for name in names:
                obj = document.getObject(name)
                if obj is None:
                    report["errors"].append(f"missing object {docname}::{name}")
                    continue
                item = {"document": docname, "object": name, "cylinders": []}
                for index, face in enumerate(obj.Shape.Faces, 1):
                    surface = face.Surface
                    if type(surface).__name__ != "Cylinder":
                        continue
                    item["cylinders"].append(
                        {
                            "face": index,
                            "radius_mm": surface.Radius,
                            "world_axis": list(ancestor.Rotation.multVec(surface.Axis)),
                            "world_point_mm": list(ancestor.multVec(surface.Center)),
                        }
                    )
                report["objects"].append(item)
        document = App.getDocument("AssemblyArt56")
        root = master.getObject("AssemblyArt56").LinkPlacement
        report["finger_bounds"] = []
        selections = (
            ("Unnamed1_GripperFinger", root),
            (
                "Unnamed1_GripperFinger_mirrored",
                root.multiply(document.getObject("GripperFinger_sym001").LinkPlacement),
            ),
        )
        for name, ancestor in selections:
            shape = document.getObject(name).Shape.copy()
            shape.Placement = ancestor.multiply(shape.Placement)
            box = shape.BoundBox
            report["finger_bounds"].append(
                {
                    "object": name,
                    "world_bounds_mm": {
                        key: getattr(box, key)
                        for key in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
                    },
                }
            )
    except Exception as error:
        report["errors"].append(str(error))
    finally:
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("RAFTEL_THOR_AXIS_REPORT_WRITTEN", output)


if __name__ == "__main__" or os.environ.get("RAFTEL_RUN_THOR_AXIS_PROBE") == "1":
    main()
