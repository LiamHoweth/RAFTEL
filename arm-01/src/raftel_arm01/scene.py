"""Explicit synthetic object layouts in the logical sorter's arm_base frame."""

import json
from dataclasses import asdict
from pathlib import Path

from raftel_arm01._validation import unique_object
from raftel_arm01.models import ObjectPose, Position

SCENE_VERSION = 1
SCENE_FRAME = "arm_base"


def scene_data(objects: list[ObjectPose]) -> dict:
    return {
        "schema_version": SCENE_VERSION,
        "frame": SCENE_FRAME,
        "objects": [asdict(obj) for obj in objects],
    }


def load_scene(path: Path) -> list[ObjectPose]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except RecursionError as exc:
        raise ValueError("scene JSON is nested too deeply") from exc
    if not isinstance(data, dict) or data.keys() != {"schema_version", "frame", "objects"}:
        raise ValueError("scene requires schema_version, frame and objects")
    version = data["schema_version"]
    if type(version) is not int or version != SCENE_VERSION:
        raise ValueError(f"scene schema_version must be {SCENE_VERSION}")
    if data["frame"] != SCENE_FRAME:
        raise ValueError(f"scene frame must be {SCENE_FRAME}")
    rows = data["objects"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError("scene objects must be an array of 1..1000 objects")
    objects = []
    for row in rows:
        if not isinstance(row, dict) or row.keys() != {
            "identifier",
            "category",
            "position",
            "mass_kg",
        }:
            raise ValueError("scene objects require identifier, category, position and mass_kg")
        position = row["position"]
        if not isinstance(position, dict) or position.keys() != {"x", "y", "z"}:
            raise ValueError("object position requires x, y and z in metres")
        objects.append(
            ObjectPose(row["identifier"], row["category"], Position(**position), row["mass_kg"])
        )
    return objects
