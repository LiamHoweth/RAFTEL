"""Audit a working copy in a dedicated FreeCAD console process, without saving.

Requires FreeCAD's Python runtime; deliberately absent from the core dependencies.
Set RAFTEL_RUN_FREECAD_AUDIT=1 and RAFTEL_FREECAD_ASSEMBLY to the copied native
document, and RAFTEL_FREECAD_REPORT
to a new JSON output path, then run this script using FreeCAD's console executable.
Do not use an interactive CAD session containing unsaved user work.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def audit(assembly: Path) -> dict:
    if not assembly.is_file() or assembly.suffix.casefold() != ".fcstd":
        raise ValueError("assembly must be an existing native FreeCAD document")
    import FreeCAD as App

    prior_documents = set(App.listDocuments())
    report = {
        "validation_level": "native CAD import/recompute; not kinematics or physical validation",
        "freecad_version": list(App.Version()),
        "assembly_filename": assembly.name,
        "documents": [],
        "errors": [],
        "saved_source_changes": False,
    }
    try:
        master = App.openDocument(str(assembly))
        report["master_document"] = master.Name
        documents = {
            name: doc for name, doc in App.listDocuments().items() if name not in prior_documents
        }
        for name, document in sorted(documents.items()):
            entry = {"name": name, "objects": []}
            try:
                entry["forced_recompute_return"] = document.recompute(None, True)
            except Exception as error:
                entry["recompute_error"] = str(error)
            for obj in document.Objects:
                item = {
                    "name": obj.Name,
                    "label": obj.Label,
                    "type": obj.TypeId,
                    "state": list(obj.State),
                }
                if hasattr(obj, "Shape"):
                    try:
                        shape = obj.Shape
                        item["shape_null"] = shape.isNull()
                        if not shape.isNull():
                            box = shape.BoundBox
                            item.update(
                                {
                                    "shape_valid": shape.isValid(),
                                    "volume_mm3": shape.Volume,
                                    "solid_count": len(shape.Solids),
                                    "bounds_mm": {
                                        "xmin": box.XMin,
                                        "xmax": box.XMax,
                                        "ymin": box.YMin,
                                        "ymax": box.YMax,
                                        "zmin": box.ZMin,
                                        "zmax": box.ZMax,
                                    },
                                }
                            )
                    except Exception as error:
                        item["shape_error"] = str(error)
                entry["objects"].append(item)
            entry["object_count"] = len(entry["objects"])
            report["documents"].append(entry)
    except Exception as error:
        report["errors"].append(str(error))
    finally:
        for name in set(App.listDocuments()) - prior_documents:
            App.closeDocument(name)
    return report


def main() -> None:
    try:
        assembly = Path(os.environ["RAFTEL_FREECAD_ASSEMBLY"])
        output = Path(os.environ["RAFTEL_FREECAD_REPORT"])
    except KeyError as error:
        raise ValueError("set RAFTEL_FREECAD_ASSEMBLY and RAFTEL_FREECAD_REPORT") from error
    if output.suffix.lower() != ".json" or output.exists():
        raise ValueError("report must be a new .json path; existing files are never overwritten")
    report = audit(assembly)
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("RAFTEL_CAD_REPORT_WRITTEN", output)


if __name__ == "__main__" or os.environ.get("RAFTEL_RUN_FREECAD_AUDIT") == "1":
    main()
