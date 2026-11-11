"""Read saved Thor wrist geometry and compare conditional small-angle mesh phases.

Optional FreeCAD console tool. Set RAFTEL_RUN_THOR_WRIST_CONTACT=1,
RAFTEL_THOR_WRIST_SOURCE to a compatible copied Assembly.FCStd, and
RAFTEL_THOR_WRIST_REPORT to a new JSON file. No recompute or save is performed.
Boolean intersections diagnose interference; zero distance is not contact proof.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

NAMES = (
    "Art56GearPlate_Art56GearPlate",
    "Art56SmallGear_Art56SmallGear",
    "Art56SmallGear_Art56SmallGear001",
)
BOUND_FIELDS = ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
SOURCE_FILES = (
    "Assembly.FCStd",
    "AssemblyArt56.FCStd",
    "Art56GearPlate.fcstd",
    "Art56SmallGear.fcstd",
)


def main() -> None:
    source = Path(os.environ["RAFTEL_THOR_WRIST_SOURCE"])
    output = Path(os.environ["RAFTEL_THOR_WRIST_REPORT"])
    if not source.is_file() or source.name != "Assembly.FCStd":
        raise ValueError("source must be an existing compatible copied Assembly.FCStd")
    if output.exists() or output.suffix.lower() != ".json":
        raise ValueError("report must be a new JSON path")
    if not all((source.parent / name).is_file() for name in SOURCE_FILES):
        raise ValueError("required sibling native source files are missing")

    import FreeCAD as App

    report = {
        "schema_version": 1,
        "validation_class": (
            "native_saved_geometry_diagnostic_not_conjugate_mesh_or_physical_calibration"
        ),
        "native_source_revision": "286b081fe6f056d87c379b884781ef77ff6a0159",
        "freecad_version": list(App.Version()),
        "coordinate_frame": "native_CAD_world_mm",
        "source_sha256": {
            name: hashlib.sha256((source.parent / name).read_bytes()).hexdigest()
            for name in SOURCE_FILES
        },
        "recomputed": False,
        "saved_source_changes": False,
        "audit_status": "in_progress",
        "objects": [],
        "nearest_shape_witnesses": [],
        "conditional_rotation_overlap_probes": [],
        "errors": [],
    }
    # Reserve output before executing a potentially expensive native operation.
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")

    def checkpoint() -> None:
        temporary = output.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        temporary.replace(output)

    previous = set(App.listDocuments())
    try:
        if previous:
            raise ValueError("run the probe in an isolated console with no documents already open")
        master = App.openDocument(str(source.resolve()), True)
        document = App.getDocument("AssemblyArt56")
        ancestor = master.getObject("AssemblyArt56").LinkPlacement
        shapes = []
        for name in NAMES:
            shape = document.getObject(name).Shape.copy()
            # Raw link Shape includes its own placement, excluding this ancestor.
            shape.Placement = ancestor.multiply(shape.Placement)
            shapes.append(shape)
            item = {
                "object_reference": "AssemblyArt56::" + name,
                "valid": shape.isValid(),
                "volume_mm3": shape.Volume,
                "face_count": len(shape.Faces),
                "world_bounds_mm": {key: getattr(shape.BoundBox, key) for key in BOUND_FIELDS},
                "world_shape_matrix": list(shape.Placement.toMatrix().A),
                "analytic_cone_faces": [],
            }
            for index, face in enumerate(shape.Faces, 1):
                surface = face.Surface
                if type(surface).__name__ != "Cone":
                    continue
                item["analytic_cone_faces"].append(
                    {
                        "face": index,
                        "center_mm": list(surface.Center),
                        "axis": list(surface.Axis),
                        "reference_radius_mm": surface.Radius,
                        "semi_angle_rad": surface.SemiAngle,
                        "world_bounds_mm": {
                            key: getattr(face.BoundBox, key) for key in BOUND_FIELDS
                        },
                    }
                )
            report["objects"].append(item)
            checkpoint()
        for index, side in ((1, -1), (2, 1)):
            distance, points, support = shapes[0].distToShape(shapes[index])
            report["nearest_shape_witnesses"].append(
                {
                    "side_y": side,
                    "distance_mm": distance,
                    "point_pairs_mm": [[list(left), list(right)] for left, right in points],
                    "support_information": support,
                    "interpretation": (
                        "Zero distance also occurs for intersecting shapes; not verified contact"
                    ),
                }
            )
            checkpoint()
        origin, roll_axis, side_axis = (
            App.Vector(0, 0, 556),
            App.Vector(0, 0, 1),
            App.Vector(0, 1, 0),
        )
        for roll_deg, candidate_s in ((0, 0), (0.25, 1), (0.25, -1), (-0.25, 1), (-0.25, -1)):
            plate = shapes[0].copy()
            plate.rotate(origin, roll_axis, roll_deg)
            for index, side in ((1, -1), (2, 1)):
                rotor = shapes[index].copy()
                side_deg = -side * candidate_s * 2 * roll_deg
                rotor.rotate(origin, side_axis, side_deg)
                overlap = plate.common(rotor)
                report["conditional_rotation_overlap_probes"].append(
                    {
                        "q6_roll_deg": roll_deg,
                        "candidate_s": candidate_s,
                        "side_y": side,
                        "side_rotation_about_common_positive_y_deg": side_deg,
                        "intersection_volume_mm3": overlap.Volume,
                        "intersection_solid_count": len(overlap.Solids),
                    }
                )
                checkpoint()
        report["audit_status"] = "complete"
    except Exception as error:
        report["errors"].append(str(error))
        report["audit_status"] = "failed"
    finally:
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
        checkpoint()
    print("RAFTEL_THOR_WRIST_CONTACT_REPORT_WRITTEN", output, report["audit_status"])


if __name__ == "__main__" or os.environ.get("RAFTEL_RUN_THOR_WRIST_CONTACT") == "1":
    main()
