"""Source-bound declarations for a limited, copied native wrist experiment.

The saved Assembly4 expressions are static attachments, not joint constraints.
Declared offset changes test expression/shape propagation, not differential
closure or physical calibration. No FreeCAD or native process is launched here.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
PINNED = {
    "Art56GearPlate.fcstd": "38ca5952d4e03e4009f94628d0c435153b980ea558a608fca9ac1c9aaf79d411",
    "Art56MotorCoverRing.fcstd": "8d037cf7a3e63ee8f04b39be35836d35c5d6f330497c8df5a735cd05abd071fa",
    "Art56SmallGear.fcstd": "b737ce24c58bc5ffc3763fcd6cdcfdd425747565c2850054397f066ecd5a63a0",
    "Assembly.FCStd": "5ee729246229e7494466010ab68e2c2367ba4ec1361b7701df21c0f8b00c2c1b",
    "AssemblyArt4.FCStd": "9306c0461c1a979526c8f73554ddef8fa89b8880e613b42beed7ac19feb401da",
    "AssemblyArt56.FCStd": "a04836216dcae82eb033c15daba6e41dedb85b03f86ff21e56b77cdff835a473",
    "GripperBot.FCStd": "a65e68644312adee7381e3a640b2b827f9c2c3362bbe4a842ccee9fea969d176",
}
RING = "Art56MotorCoverRing_Art56MotorCoverRing"
PLATE = "Art56GearPlate_Art56GearPlate"
GRIPPER = "GripperBot_GripperBot"
# Exact canonical contract hash is separate from native evidence and source pins.
CONTRACT_SHA256 = "8dc284ecab1ce5e4ecbedc2d138ec4cb8ffae01240e48107bee276079d88efa9"


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _object(tree, name):
    matches = [obj for obj in tree.findall("./ObjectData/Object") if obj.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"missing or ambiguous source object {name}")
    return matches[0]


def _binding(trees, document, name, parent_document, parent_link, parent_datum, **motion):
    # Reuse the established saved-placement parser; no second quaternion engine.
    from probe_thor_pose_frames_desktop import _placement_xml

    obj = _object(trees[document], name)
    expressions = [
        [node.get("path"), node.get("expression")]
        for node in obj.findall(
            './Properties/Property[@name="ExpressionEngine"]/ExpressionEngine/Expression'
        )
    ]
    attached = obj.find('./Properties/Property[@name="AttachedTo"]/String')
    linked = obj.find('./Properties/Property[@name="LinkedObject"]/XLink')
    if attached is None or linked is None or len(expressions) != 1:
        raise ValueError("source link lacks unique attachment metadata")
    if expressions[0][0] != "Placement" or "AttachmentOffset" not in expressions[0][1]:
        raise ValueError("source link lacks saved offset placement expression")
    return {
        "document": document,
        "object": name,
        "parent_document": parent_document,
        "parent_link": parent_link,
        "parent_datum": parent_datum,
        "attached_to": attached.get("value"),
        "linked_file": linked.get("file"),
        "linked_object": linked.get("name"),
        "saved_expression_engine": expressions,
        "saved_attachment_offset": _placement_xml(obj, "AttachmentOffset"),
        "saved_placement": _placement_xml(obj, "Placement"),
        "saved_parent_datum": _placement_xml(
            _object(trees[parent_document], parent_datum), "Placement"
        ),
        **motion,
    }


def source_contract(source_root: Path) -> dict:
    """Authenticate seven pinned documents and extract the actual source links.

    Caller separately authenticates all 57 copied files and the static Art1
    compatibility wrapper. Only these seven unmodified files are inspected here.
    """
    trees = {}
    for name, expected in PINNED.items():
        path = Path(source_root) / name
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"source differs from pinned wrist input: {name}")
        with zipfile.ZipFile(path) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())):
                raise ValueError("duplicate native archive members")
            trees[name] = ET.fromstring(archive.read("Document.xml"))
    bindings = [
        _binding(
            trees,
            "Assembly.FCStd",
            "AssemblyArt56",
            "AssemblyArt4.FCStd",
            "AssemblyArt4",
            "LCS_Art56Fix",
            coordinate="q5",
            coefficient=1.0,
            increment_side="right",
            increment_axis=[1, 0, 0],
        ),
        _binding(
            trees,
            "AssemblyArt56.FCStd",
            PLATE,
            "Art56MotorCoverRing.fcstd",
            RING,
            "LCS_BigGear",
            coordinate="q6",
            coefficient=1.0,
            increment_side="left",
            increment_axis=[0, 0, 1],
        ),
        _binding(
            trees,
            "AssemblyArt56.FCStd",
            RING,
            "AssemblyArt56.FCStd",
            None,
            "LCS_Origin",
            coordinate=None,
            coefficient=0.0,
            increment_side=None,
            increment_axis=None,
        ),
        _binding(
            trees,
            "AssemblyArt56.FCStd",
            GRIPPER,
            "Art56GearPlate.fcstd",
            PLATE,
            "LCS_Gripper",
            coordinate=None,
            coefficient=0.0,
            increment_side=None,
            increment_axis=None,
        ),
    ]
    result = {
        "schema_version": 1,
        "source_revision": SOURCE_REVISION,
        "source_sha256": dict(PINNED),
        "bindings": bindings,
        "coordinate_frame": "native_CAD_world_mm_at_zero_proximal_four_joints",
        "angle_units": "radians",
        "saved_zero_axes": {
            "fold": {"origin_mm": [0, 0, 556], "axis_unit": [0, 1, 0]},
            "plate_roll": {"origin_mm": [0, 0, 575.5], "axis_unit": [0, 0, 1]},
        },
        "declaration": "imposed_AttachmentOffset_increments_existing_source_expressions",
        "q5_membership": "all_AssemblyArt56_descendants",
        "q6_membership": "plate_and_attachment_descendants_only",
        "side_shafts_driven_for_q6": False,
        "differential_or_mesh_solved": False,
        "native_corroboration_in_this_contract": False,
        "physical_calibration_qualified": False,
    }
    validate_contract(result)
    return result


def validate_contract(contract: dict) -> None:
    """Reject any changed field, including types, offset side, pins or claims."""
    try:
        valid = isinstance(contract, dict) and _digest(contract) == CONTRACT_SHA256
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        raise ValueError("wrist source contract differs from exact reviewed declaration")


def expected_marker(point_mm, q5_rad, q6_rad, *, roll=True):
    """Predict declared motion from observed zero markers, never target FK.

    Existing wrist algebra carries the roll line with fold. Passing this check
    corroborates expression/shape response to our input hypothesis only.
    """
    from raftel_arm01.kinematics.thor_frames import finite
    from raftel_arm01.kinematics.thor_wrist import MotionStep, point_state

    if not isinstance(point_mm, (list, tuple)) or len(point_mm) != 3:
        raise ValueError("native marker requires three finite millimetre coordinates")
    if type(roll) is not bool:
        raise ValueError("roll membership must be explicit boolean")
    point = tuple(finite(value) / 1000 for value in point_mm)
    steps = [MotionStep((0, 0, 0.556), (0, 1, 0), 1, 0, "source master fold declaration")]
    if roll:
        steps.append(MotionStep((0, 0, 0.5755), (0, 0, 1), 0, 1, "source plate roll declaration"))
    state = point_state(point, q5_rad, q6_rad, steps)
    return [finite(value * 1000) for value in state.position_m]
