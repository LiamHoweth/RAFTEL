"""Read selected cached motor/belt BReps without opening or saving CAD documents.

Run with FreeCADCmd using RAFTEL_PROBE_MOVING_MASS=1 and explicit
RAFTEL_MASS_SOURCE / RAFTEL_MASS_OUTPUT paths. No addon or recompute is needed.
The result is CAD geometry evidence, not manufacturer internal mass data.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

OBJECT_NAMES = ("Chamfer_solid", "Pad046", "Cut002001", "Pocket001")


def probe(source: Path) -> dict:
    import FreeCAD as App
    import Part

    with zipfile.ZipFile(source) as archive, tempfile.TemporaryDirectory() as temporary:
        root = ET.fromstring(archive.read("Document.xml"))
        objects = {obj.attrib["name"]: obj for obj in root.find("ObjectData")}
        results = {}
        for name in OBJECT_NAMES:
            obj = objects[name]
            filename = obj.find('./Properties/Property[@name="Shape"]/Part').attrib["file"]
            raw = archive.read(filename)
            local = Path(temporary) / (name + ".brp")
            local.write_bytes(raw)
            shape = Part.Shape()
            shape.read(str(local))
            solids = shape.Solids
            volume = sum(solid.Volume for solid in solids)
            if not volume > 0 or not shape.isValid():
                raise ValueError(f"{name}: expected valid positive-solid source geometry")
            center = App.Vector(0, 0, 0)
            for solid in solids:
                center += solid.CenterOfMass * solid.Volume / volume
            box = shape.BoundBox
            results[name] = {
                "brep_file": filename,
                "brep_sha256": hashlib.sha256(raw).hexdigest(),
                "shape_valid": True,
                "solid_count": len(solids),
                "volume_mm3": volume,
                "com_mm": list(center),
                "bounds_mm": {
                    key: getattr(box, key)
                    for key in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
                },
            }
    return {
        "schema_version": 1,
        "validation_class": "saved_native_BRep_geometry_not_mass_or_articulation_validation",
        "source_filename": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "freecad_version": App.Version(),
        "document_opened_or_recomputed": False,
        "source_saved": False,
        "objects": results,
    }


def main() -> int:
    source = Path(os.environ["RAFTEL_MASS_SOURCE"])
    output = Path(os.environ["RAFTEL_MASS_OUTPUT"])
    result = probe(source)
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__" or os.environ.get("RAFTEL_PROBE_MOVING_MASS") == "1":
    main()
