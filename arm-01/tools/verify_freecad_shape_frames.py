"""Native synthetic frame fixture; requires a dedicated FreeCAD console.

Set RAFTEL_RUN_FREECAD_FRAME_FIXTURE=1 and RAFTEL_FREECAD_FRAME_REPORT to a new
JSON path. No robot CAD is opened or saved. The independently known cube
centroids establish whether raw Shape coordinates already include placement.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

EXPECTED_CENTERS_MM = {
    "Source": [11, 1, 1],
    "LinkFalse": [1, 21, 1],
    "LinkTrue": [11, 21, 1],
    "Child": [11, 1, 1],
    "GroupLinkFalse": [11, 21, 1],
    "GroupLinkTrue": [111, 21, 1],
    "NestedLink": [1, 21, 1],
    "RotatedFalse": [-1, 21, 1],
    "RotatedTrue": [-1, 29, 1],
}


def verify_records(records: list[dict]) -> None:
    actual = {record["name"]: record for record in records}
    if set(actual) != set(EXPECTED_CENTERS_MM) or len(records) != len(actual):
        raise ValueError("fixture cases are missing, duplicated or unexpected")
    for name, expected in EXPECTED_CENTERS_MM.items():
        center = actual[name]["shape_center_mm"]
        if len(center) != 3 or not all(
            math.isclose(value, target, abs_tol=1e-8, rel_tol=0)
            for value, target in zip(center, expected, strict=True)
        ):
            raise ValueError(f"native shape-coordinate contract differs for {name}: {center}")


def _xyz(vector) -> list[float]:
    return [vector.x, vector.y, vector.z]


def _record(obj) -> dict:
    solids = list(obj.Shape.Solids)
    volume = sum(solid.Volume for solid in solids)
    center = [
        sum(solid.Volume * getattr(solid.CenterOfMass, axis) for solid in solids) / volume
        for axis in ("x", "y", "z")
    ]
    return {
        "name": obj.Name,
        "shape_center_mm": center,
        "placement_mm": _xyz(obj.Placement.Base),
        "placement_quaternion_xyzw": list(obj.Placement.Rotation.Q),
        "global_placement_mm": _xyz(obj.getGlobalPlacement().Base)
        if hasattr(obj, "getGlobalPlacement")
        else None,
        "link_placement_mm": _xyz(obj.LinkPlacement.Base)
        if hasattr(obj, "LinkPlacement")
        else None,
        "link_transform": obj.LinkTransform if hasattr(obj, "LinkTransform") else None,
    }


def run_fixture() -> dict:
    import FreeCAD as App
    import Part

    document = App.newDocument("RAFTELFrameFixture")
    try:
        source = document.addObject("Part::Feature", "Source")
        source.Shape = Part.makeBox(2, 2, 2)
        source.Placement.Base = App.Vector(10, 0, 0)
        records = [_record(source)]
        for flag in (False, True):
            link = document.addObject("App::Link", f"Link{flag}")
            link.setLink(source)
            link.LinkTransform = flag
            link.LinkPlacement = App.Placement(App.Vector(0, 20, 0), App.Rotation())
            document.recompute()
            records.append(_record(link))
        parent = document.addObject("App::Part", "Parent")
        parent.Placement.Base = App.Vector(100, 0, 0)
        child = document.addObject("Part::Feature", "Child")
        child.Shape = Part.makeBox(2, 2, 2)
        parent.addObject(child)
        child.Placement.Base = App.Vector(10, 0, 0)
        records.append(_record(child))
        for flag in (False, True):
            link = document.addObject("App::Link", f"GroupLink{flag}")
            link.setLink(parent)
            link.LinkTransform = flag
            link.LinkPlacement = App.Placement(App.Vector(0, 20, 0), App.Rotation())
            document.recompute()
            records.append(_record(link))
        nested = document.addObject("App::Link", "NestedLink")
        parent.addObject(nested)
        nested.setLink(source)
        nested.LinkTransform = False
        nested.LinkPlacement = App.Placement(App.Vector(0, 20, 0), App.Rotation())
        document.recompute()
        records.append(_record(nested))
        # Noncommuting source/link rotations catch assumptions hidden by
        # translation-only fixtures. Earlier cases are snapshots at measurement.
        source.Placement.Rotation = App.Rotation(App.Vector(0, 0, 1), 90)
        for flag in (False, True):
            link = document.addObject("App::Link", f"Rotated{flag}")
            link.setLink(source)
            link.LinkTransform = flag
            link.LinkPlacement = App.Placement(
                App.Vector(0, 20, 0), App.Rotation(App.Vector(0, 0, 1), 90)
            )
            document.recompute()
            records.append(_record(link))
        verify_records(records)
        return {
            "schema_version": 1,
            "freecad_version": list(App.Version()),
            "native_fixture_verified": True,
            "saved_cad_files": False,
            "cases": records,
            "contract": [
                "Raw Shape values include the object's own Placement/LinkPlacement.",
                "Raw Shape values exclude ancestor App::Part placement.",
                "LinkTransform false ignores the linked target's own placement.",
                "LinkTransform true includes the linked target's own placement.",
                "No robot axes or physical calibration are validated by this fixture.",
            ],
        }
    finally:
        App.closeDocument(document.Name)


def main() -> None:
    output = Path(os.environ["RAFTEL_FREECAD_FRAME_REPORT"])
    if output.suffix.lower() != ".json" or output.exists():
        raise ValueError("fixture report must be a new .json path")
    report = run_fixture()
    with output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("RAFTEL_FRAME_FIXTURE_WRITTEN", output)


if __name__ == "__main__" or os.environ.get("RAFTEL_RUN_FREECAD_FRAME_FIXTURE") == "1":
    main()
