"""Read pinned Thor jaw datums and cached shapes without recomputing or saving.

Run in FreeCAD console with RAFTEL_RUN_THOR_GRIPPER_PROBE=1,
RAFTEL_THOR_GRIPPER_SOURCE=native-sibling-directory and
RAFTEL_THOR_GRIPPER_REPORT=new.json. Existing files are never overwritten.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
FILES = (
    "GripperBot.FCStd",
    "GripperArm.FCStd",
    "GripperActiveArm.FCStd",
    "GripperPassiveArm.FCStd",
    "GripperFinger.FCStd",
    "AssemblyArt56.FCStd",
)

PINNED_SHA256 = {
    "GripperBot.FCStd": "a65e68644312adee7381e3a640b2b827f9c2c3362bbe4a842ccee9fea969d176",
    "GripperArm.FCStd": "f1511f4b319a5727cf07771abe4c75002d5527e0a10291d47c1fe8024a44c6fc",
    "GripperActiveArm.FCStd": "3ba5ba6f74c5d2f45eeca56f28534dc750e7f0ae735b6a0b3e16beeef21adc67",
    "GripperPassiveArm.FCStd": "d14ac1debf67735fd623e052d468a9773066c32356390799b4ea07addcba68d4",
    "GripperFinger.FCStd": "ab4daca4dd2f447029f4c76150b7f617fbdda74ae467cf6962938efe148d57a6",
    "AssemblyArt56.FCStd": "a04836216dcae82eb033c15daba6e41dedb85b03f86ff21e56b77cdff835a473",
}


def main() -> None:
    import FreeCAD as App

    source = Path(os.environ["RAFTEL_THOR_GRIPPER_SOURCE"])
    output = Path(os.environ["RAFTEL_THOR_GRIPPER_REPORT"])
    if output.exists():
        raise ValueError("output must be a new report")
    objects = {}
    hashes = {}
    for filename in FILES:
        path = source / filename
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashes[filename] != PINNED_SHA256[filename]:
            raise ValueError(f"source differs from pinned gripper file: {filename}")
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("Document.xml"))
        objects[filename] = {o.attrib["name"]: o for o in root.findall("./ObjectData/Object")}

    def placement(filename, name):
        element = objects[filename][name].find(
            './Properties/Property[@name="Placement"]/PropertyPlacement'
        )
        values = [float(element.attrib[k]) for k in ("Px", "Py", "Pz", "Q0", "Q1", "Q2", "Q3")]
        return App.Placement(App.Vector(*values[:3]), App.Rotation(*values[3:]))

    assembly = "AssemblyArt56.FCStd"
    bot_inverse = placement(assembly, "GripperBot_GripperBot").inverse()

    def bot_point(name, point):
        return list(bot_inverse.multVec(placement(assembly, name).multVec(App.Vector(*point))))

    left_finger = "Unnamed1_GripperFinger"
    right_finger = "GripperFinger_sym001"
    active = "GripperActiveArm_GripperActiveArm"
    passive = "Unnamed3_GripperPassiveArm"
    passive_tip = list(placement("GripperPassiveArm.FCStd", "LCS_GripperPassiveArm_1").Base)
    points = {
        "active_driven_pivot": bot_point(active, (0, 0, 2.3)),
        "active_driven_tip": bot_point(active, (35, 0, 0)),
        "passive_driven_pivot": bot_point(passive, (0, 0, 0)),
        "passive_driven_tip": bot_point(passive, passive_tip),
        "left_auxiliary_pivot": bot_point("Unnamed2_GripperArm001", (0, 0, 0)),
        "left_auxiliary_tip": bot_point("Unnamed2_GripperArm001", (0, 35, 0)),
        "right_auxiliary_pivot": bot_point("Unnamed2_GripperArm", (0, 0, 0)),
        "right_auxiliary_tip": bot_point("Unnamed2_GripperArm", (0, 35, 0)),
        "left_finger_driven_hole": bot_point(left_finger, (4, 4, 12.5)),
        "left_finger_auxiliary_hole": bot_point(left_finger, (12.5, 22.5, 12.5)),
        "right_finger_driven_hole": bot_point(right_finger, (-4, 4, 12.5)),
        "right_finger_auxiliary_hole": bot_point(right_finger, (-12.5, 22.5, 12.5)),
    }
    residuals = {}
    for side, drive in (("left", "active"), ("right", "passive")):
        for kind, endpoint in (
            ("driven", f"{drive}_driven_tip"),
            ("auxiliary", f"{side}_auxiliary_tip"),
        ):
            hole = points[f"{side}_finger_{kind}_hole"]
            delta = [points[endpoint][i] - hole[i] for i in (0, 1)]
            residuals[f"{side}_{kind}"] = {
                "projected_xy_delta_mm": delta,
                "projected_axis_misalignment_mm": math.hypot(*delta),
            }
    datum_positions = {}
    for filename in FILES[:-1]:
        datum_positions[filename] = {
            name: list(placement(filename, name).Base)
            for name in objects[filename]
            if name.startswith(("LCS", "HoleAxis"))
        }
    native_shapes = {}
    previous = set(App.listDocuments())
    try:
        for filename in FILES[:-1]:
            doc = App.openDocument(str(source / filename), True)
            shape = doc.getObject("Body").Shape
            planes = []
            if filename == "GripperFinger.FCStd":
                for index, face in enumerate(shape.Faces, 1):
                    if type(face.Surface).__name__ == "Plane" and face.Area > 100:
                        planes.append(
                            {
                                "face": index,
                                "normal": list(face.normalAt(0, 0)),
                                "center_mm": list(face.CenterOfMass),
                                "area_mm2": face.Area,
                            }
                        )
            native_shapes[filename] = {
                "volume_mm3": shape.Volume,
                "bounds_mm": {
                    name: getattr(shape.BoundBox, name)
                    for name in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
                },
                "large_planar_faces": planes,
            }
            App.closeDocument(doc.Name)
    finally:
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
    gear_properties = {}
    for filename in ("GripperActiveArm.FCStd", "GripperPassiveArm.FCStd"):
        gear = objects[filename]["involutegear"]
        gear_properties[filename] = {
            name: float(gear.find(f'./Properties/Property[@name="{name}"]')[0].attrib["value"])
            for name in ("teeth", "module", "dw")
        }
    report = {
        "schema_version": 1,
        "validation_class": "pinned_saved_geometry_and_conditional_nominal_jaw_model",
        "source_revision": SOURCE_REVISION,
        "source_sha256": hashes,
        "freecad_version": list(App.Version()),
        "coordinate_frame": "GripperBot source Body local XYZ, millimetres",
        "recomputed": False,
        "saved_source_changes": False,
        "source_datum_positions_mm": datum_positions,
        "gear_pair": {
            "saved_properties": gear_properties,
            "source_objects": ["GripperActiveArm::involutegear", "GripperPassiveArm::involutegear"],
            "ideal_increment_relation": "opposite equal shaft increments about common +Z",
            "gear_contact_or_phase_qualified": False,
        },
        "saved_assembly_points_in_bot_frame_mm": points,
        "saved_loop_axis_residuals": residuals,
        "cached_shapes": native_shapes,
        "ideal_model": {
            "assumed_symmetric_driven_pivots_mm": [[-14.5, 32.5], [14.5, 32.5]],
            "auxiliary_pivots_mm": [[-6, 51], [6, 51]],
            "link_length_mm": 35,
            "finger_pivot_delta_mm": [8.5, 18.5],
            "contact_face_source_x_mm": 18.5,
            "gap_formula_mm": "70*cos(q)",
            "q_definition": "ideal closing q from outward-horizontal links; not servo angle",
            "study_interval_rad": "0 <= q < pi/2; not a physical travel limit",
            "parallelism": "constant finger orientation; assumed uncrossed parallelogram branch",
            "actual_saved_geometry_loop_solved": False,
            "physical_parallelism_or_stroke_qualified": False,
        },
        "remaining_gates": [
            "Reconcile saved servo axis -14.515mm and gear/link phase with nominal parallelogram",
            "Joint clearance, gear contact, collision/stops, deflection and servo zero/range",
            "Verify jaw pads, gripping force and payload retention independently",
            "Integrate jaw hardware/mass after phase and pivot ownership reconciliation",
        ],
    }
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__" or os.environ.get("RAFTEL_RUN_THOR_GRIPPER_PROBE") == "1":
    main()
