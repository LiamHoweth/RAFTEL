"""Inspect pinned cached elbow belt/drum/clamp BReps without opening documents.

Run in FreeCAD's console with RAFTEL_RUN_THOR_BELT_PROBE=1,
RAFTEL_THOR_BELT_SOURCE naming the original pinned freecad-src directory, and
RAFTEL_THOR_BELT_REPORT naming a new JSON file. No addon, source save, history
recompute, or real mechanism operation occurs. Contact results are undeformed
saved geometry, not belt tension, force, pitch-cord or fit qualification.
"""

from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
EXPECTED = {
    "Assembly.FCStd": "5ee729246229e7494466010ab68e2c2367ba4ec1361b7701df21c0f8b00c2c1b",
    "AssemblyArt2.FCStd": "96a41e5eaa728a89e8e7a3340ec10a8c71034ff30b76f8679d23ed435574638f",
    "AssemblyArt3.FCStd": "8b5b8ba6da66f9deb1ec1f03ec1ff75f2ea10e02ca67a7e2b5e5f955aaec4398",
    "Art3Pulley.fcstd": "d450cc565e722981346fc2b1aa3662474c83d574ca39a5602bacb98d8619fd9e",
}


def properties(root: ET.Element, name: str) -> ET.Element:
    value = root.find(f"ObjectData/Object[@name='{name}']/Properties")
    if value is None:
        raise ValueError(f"missing source object {name}")
    return value


def main() -> None:
    source = Path(os.environ["RAFTEL_THOR_BELT_SOURCE"])
    output = Path(os.environ["RAFTEL_THOR_BELT_REPORT"])
    if output.exists() or output.suffix.lower() != ".json":
        raise ValueError("report must be a new JSON file")
    archives = {}
    roots = {}
    for name, expected in EXPECTED.items():
        data = (source / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"source SHA-256 differs from pinned original: {name}")
        archives[name] = data
        with zipfile.ZipFile(source / name) as archive:
            roots[name] = ET.fromstring(archive.read("Document.xml"))

    import FreeCAD as App
    import Part

    def placement(file: str, name: str):
        raw = properties(roots[file], name).find("Property[@name='Placement']/PropertyPlacement")
        if raw is None:
            raise ValueError(f"missing placement {file}::{name}")
        p = raw.attrib
        return App.Placement(
            App.Vector(*(float(p[k]) for k in ("Px", "Py", "Pz"))),
            App.Rotation(*(float(p[k]) for k in ("Q0", "Q1", "Q2", "Q3"))),
        )

    def cached_shape(file: str, name: str):
        raw = properties(roots[file], name).find("Property[@name='Shape']/Part")
        if raw is None:
            raise ValueError(f"missing cached BRep {file}::{name}")
        with zipfile.ZipFile(source / file) as archive:
            content = archive.read(raw.attrib["file"])
        result = Part.Shape()
        result.importBrepFromString(content.decode())
        if result.isNull() or not result.isValid() or not result.Solids:
            raise ValueError(f"invalid cached solid {file}::{name}")
        return result, hashlib.sha256(content).hexdigest()

    def bounds(shape):
        box = shape.BoundBox
        return [getattr(box, key) for key in ("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax")]

    def center(shape):
        return [
            sum(solid.Volume * list(solid.CenterOfMass)[i] for solid in shape.Solids) / shape.Volume
            for i in range(3)
        ]

    belt, belt_hash = cached_shape("AssemblyArt2.FCStd", "Fusion154001")
    drum, drum_hash = cached_shape("Art3Pulley.fcstd", "Body")
    screw, screw_hash = cached_shape("AssemblyArt3.FCStd", "Screw010")
    # Saved shapes contain their own Placement; append ancestors exactly once.
    # Both assembly links have saved LinkTransform=False and identity target Model.
    belt_world = placement("Assembly.FCStd", "AssemblyArt2").multiply(
        placement("AssemblyArt2.FCStd", "GT2_Belt_Art3001")
    )
    drum_world = placement("Assembly.FCStd", "AssemblyArt3").multiply(
        placement("AssemblyArt3.FCStd", "Art3Pulley_Art3Pulley")
    )
    belt.Placement = belt_world.multiply(belt.Placement)
    drum.Placement = drum_world.multiply(drum.Placement)
    screw.Placement = placement("Assembly.FCStd", "AssemblyArt3").multiply(screw.Placement)
    belt_local, screw_local = belt.copy(), screw.copy()
    belt_local.Placement = drum_world.inverse().multiply(belt_local.Placement)
    screw_local.Placement = drum_world.inverse().multiply(screw_local.Placement)
    tails = []
    for index, edge in enumerate(belt_local.Edges, 1):
        points = [list(vertex.Point) for vertex in edge.Vertexes]
        if points and all(p[1] > 19 and abs(p[0]) < 12 for p in points):
            tails.append({"edge": index, "curve": type(edge.Curve).__name__, "vertices_mm": points})
    sketches = {}
    for name in ("Sketch001", "Sketch002", "Sketch003"):
        props = properties(roots["Art3Pulley.fcstd"], name)
        geometry = props.find("Property[@name='Geometry']/GeometryList")
        sketches[name] = {
            "geometry_in_sketch_frame": [
                {element.tag: element.attrib for element in item if element.tag != "GeoExtensions"}
                for item in geometry
            ],
            "sketch_to_drum": list(placement("Art3Pulley.fcstd", name).toMatrix().A),
        }
    attachments = {}
    for name in ("Screw010", "Nut010", "Art3Pulley_Art3Pulley"):
        props = properties(roots["AssemblyArt3.FCStd"], name)
        attachments[name] = {
            field: props.find(f"Property[@name='{field}']/String").attrib["value"]
            for field in ("Label", "AttachedTo")
        }
    report = {
        "schema_version": 1,
        "validation_class": "pinned_cached_geometry_not_physical_contact_or_pitch_validation",
        "source_revision": SOURCE_REVISION,
        "source_sha256": EXPECTED,
        "shape_sha256": {"belt": belt_hash, "drum": drum_hash, "screw": screw_hash},
        "freecad_version": list(App.Version()),
        "length_unit": "mm",
        "source_opened_or_recomputed_or_saved": False,
        "coordinate_frame": "Art3Pulley Body local zero frame; drum axis local Z",
        "belt_raw_to_drum_matrix": list(drum_world.inverse().multiply(belt_world).toMatrix().A),
        "cached_shape_validity": {
            "belt": belt.isValid(),
            "drum": drum.isValid(),
            "screw": screw.isValid(),
        },
        "world_com_mm": {"belt": center(belt), "drum": center(drum)},
        "cached_fit": {
            "belt_drum_common_volume_mm3": belt.common(drum).Volume,
            "belt_drum_minimum_distance_mm": belt.distToShape(drum)[0],
            "screw_belt_common_volume_mm3": screw.common(belt).Volume,
            "screw_bounds_in_drum_frame_mm": bounds(screw_local),
            "meaning": "Undeformed screw intersects belt; no contact/preload solution",
        },
        "belt_tail_edges_in_drum_frame": tails,
        "drum_entry_and_clamp_sketches": sketches,
        "source_attachments": attachments,
        "pitch_radius_m": None,
        "actual_belt_part_number": None,
        "clamp_capacity_verified": False,
        "unknowns": [
            "Exact installed belt, cord pitch-line offset, tooth-facing side and compression",
            "Physical clamp screw setting, end preparation, tooth engagement and retention force",
            "Physical routing sign, wrap and idler contact; cached idler mismatch persists",
            "Elasticity, slip, pretension, bearing forces, thermal and fatigue performance",
        ],
    }
    # Detect source drift even if another process changed a source during inspection.
    if any((source / name).read_bytes() != data for name, data in archives.items()):
        raise ValueError("source changed during cached geometry inspection")
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("RAFTEL_THOR_BELT_REPORT_WRITTEN", output)


if __name__ == "__main__" or os.environ.get("RAFTEL_RUN_THOR_BELT_PROBE") == "1":
    main()
