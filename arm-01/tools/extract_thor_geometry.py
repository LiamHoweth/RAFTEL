"""Extract saved Thor assembly metadata and compare a pinned nominal ROS model.

No CAD code executes and no files are modified. Saved placements are not a
recomputed assembly, and assembly origins are not automatically robot joints.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

THOR_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
ROS_REVISION = "e11a56b5aa0d89f0b68a3ea7bd084eab4a050952"
ROS_PATH = "ws_thor/src/thor_urdf/urdf/thor.urdf.xacro"
SELECTED_LCS = {
    "AssemblyBase": ("LCS_Art1003",),
    "AssemblyArt1": ("LCS_Art2002",),
    "AssemblyArt2": ("LCS_Art1", "LCS_Model_1"),
    "AssemblyArt3": ("LCS_Art2Fix", "LCS_Art4Fix"),
    "AssemblyArt4": ("LCS_Art3Fix", "LCS_Art56Fix"),
    "AssemblyArt56": ("LCS_Art4Fix",),
}


def number(expression: str, pi: float) -> float:
    """Evaluate only finite numbers, PI, signs and arithmetic; never Python eval."""
    expression = expression.strip()
    expression = re.sub(r"\$\{([^{}]+)\}", r"(\1)", expression)
    if len(expression) > 256:
        raise ValueError("numeric expression too long")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id == "PI":
            return pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
        ):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            return left / right
        raise ValueError("unsupported numeric expression")

    try:
        result = visit(ast.parse(expression, mode="eval").body)
    except (SyntaxError, ZeroDivisionError, OverflowError) as error:
        raise ValueError("invalid numeric expression") from error
    if not math.isfinite(result):
        raise ValueError("numeric expression must be finite")
    return result


def placement(obj: ET.Element) -> dict:
    node = obj.find('./Properties/Property[@name="Placement"]/PropertyPlacement')
    if node is None:
        raise ValueError(f"missing Placement for {obj.get('name')}")
    values = [float(node.attrib[key]) for key in ("Px", "Py", "Pz", "Q0", "Q1", "Q2", "Q3")]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("placement contains nonfinite values")
    quaternion = values[3:]
    if not math.isclose(sum(v * v for v in quaternion), 1.0, abs_tol=1e-9):
        raise ValueError("placement quaternion must be unit length")
    return {"position_m": [v / 1000 for v in values[:3]], "quaternion_xyzw": quaternion}


def transform_point(frame: dict, point_m: list[float]) -> list[float]:
    """Apply a saved FreeCAD quaternion placement to a point, without recompute."""
    x, y, z, w = frame["quaternion_xyzw"]
    rotation = (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )
    return [
        frame["position_m"][i] + sum(rotation[i][j] * point_m[j] for j in range(3))
        for i in range(3)
    ]


def _native(directory: Path, name: str) -> tuple[ET.Element, dict]:
    matches = [p for p in directory.iterdir() if p.name.casefold() == (name + ".fcstd").casefold()]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one native source document: {name}")
    path = matches[0]
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("Document.xml"))
    return document, {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def source_urdf(path: Path) -> dict:
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    pi_element = root.find('{http://www.ros.org/wiki/xacro}property[@name="PI"]')
    pi = float(pi_element.attrib["value"]) if pi_element is not None else math.pi
    joints = []
    for index in range(1, 7):
        node = root.find(f'joint[@name="joint_{index}"]')
        if node is None:
            raise ValueError("source model must define joint_1 through joint_6")
        origin, axis, limit = node.find("origin"), node.find("axis"), node.find("limit")
        if origin is None or axis is None or limit is None:
            raise ValueError("joint lacks geometry or source limits")
        joints.append(
            {
                "name": node.attrib["name"],
                "type": node.attrib["type"],
                "parent": node.find("parent").attrib["link"],
                "child": node.find("child").attrib["link"],
                "origin_xyz_m": [float(v) for v in origin.attrib["xyz"].split()],
                "origin_rpy_rad": [float(v) for v in origin.get("rpy", "0 0 0").split()],
                "axis_local_unit": [float(v) for v in axis.attrib["xyz"].split()],
                "source_lower_rad": number(limit.attrib["lower"], pi),
                "source_upper_rad": number(limit.attrib["upper"], pi),
            }
        )
    return {
        "revision_claim": ROS_REVISION,
        "path": ROS_PATH,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "joints": joints,
        "source_inertials_usable_for_loads": False,
        "reason": "all default link masses=1kg and inertias=identity; placeholder model values",
    }


def extract(directory: Path, urdf: Path | None = None, inventory: Path | None = None) -> dict:
    master, master_source = _native(directory, "Assembly")
    master_objects = {o.attrib["name"]: o for o in master.findall("./ObjectData/Object")}
    model = master_objects.get("Model")
    if model is None:
        raise ValueError("master has no Model assembly object")
    installed_names = {
        node.attrib["value"] for node in model.findall('./Properties/Property[@name="Group"]//Link')
    }
    instances, files = [], [master_source]
    for name, selected in SELECTED_LCS.items():
        if name not in installed_names:
            raise ValueError(f"assembly link is not an installed master Model member: {name}")
        obj = master_objects[name]
        frame = placement(obj)
        subdocument, sub_source = _native(directory, name)
        files.append(sub_source)
        subobjects = {o.attrib["name"]: o for o in subdocument.findall("./ObjectData/Object")}
        link = obj.find('./Properties/Property[@name="LinkedObject"]/XLink')
        lcs = []
        for label in selected:
            local = placement(subobjects[label])
            origin = transform_point(frame, local["position_m"])
            basis = []
            for axis_index in range(3):
                endpoint_local = transform_point(local, [float(j == axis_index) for j in range(3)])
                endpoint_world = transform_point(frame, endpoint_local)
                basis.append([endpoint_world[i] - origin[i] for i in range(3)])
            lcs.append(
                {
                    "name": label,
                    "local_placement": local,
                    "saved_world_position_m": origin,
                    "saved_world_basis_xyz": basis,
                }
            )
        instances.append(
            {
                "name": name,
                "saved_world_placement": frame,
                "linked_file": link.get("file") if link is not None else None,
                "linked_object": link.get("name") if link is not None else None,
                "selected_mating_lcs": lcs,
            }
        )
    expected = {}
    if inventory:
        expected = {
            Path(item["path"]).name.casefold(): item["sha256"]
            for item in json.loads(inventory.read_text())["files"]
        }
    return {
        "schema_version": 1,
        "validation_class": "saved_native_metadata_not_recomputed_or_calibrated",
        "cad_revision_claim": THOR_REVISION,
        "selected_files_match_pinned_inventory": bool(expected)
        and all(expected.get(item["path"].casefold()) == item["sha256"] for item in files),
        "source_files": files,
        "installed_master_subassemblies": instances,
        "upstream_nominal_model": source_urdf(urdf) if urdf else None,
        "cad_axis_directions_calibrated": False,
        "joint_limits_verified": False,
        "mass_or_load_properties_extracted": False,
    }


def _identity() -> list[list[float]]:
    return [[float(i == j) for j in range(4)] for i in range(4)]


def _product(a: list, b: list) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _frame(obj: dict, key: str = "placement") -> list[list[float]]:
    matrix = obj.get(key, {}).get("matrix")
    if matrix is None:
        return _identity()
    if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ValueError("native placement matrix must be 4x4")
    if not all(math.isfinite(value) for row in matrix for value in row):
        raise ValueError("native placement matrix must be finite")
    return matrix


def _point(matrix: list, xyz_mm: list) -> list[float]:
    return [
        (sum(matrix[i][j] * xyz_mm[j] for j in range(3)) + matrix[i][3]) / 1000 for i in range(3)
    ]


def _inverse_rigid(matrix: list) -> list[list[float]]:
    inverse = _identity()
    for i in range(3):
        for j in range(3):
            inverse[i][j] = matrix[j][i]
        inverse[i][3] = -sum(matrix[j][i] * matrix[j][3] for j in range(3))
    return inverse


def _derived_link_geometry(obj: dict, target: dict | None) -> dict:
    """Reproduce the empirically checked native Link.Shape transform rule."""
    if (
        target is None
        or target.get("volume_mm3") is None
        or target.get("shape_center_of_mass_mm") is None
    ):
        return obj
    if obj.get("volume_mm3") is not None and not obj.get("shape_error"):
        return obj
    matrix = _frame(obj, "link_placement")
    if not obj.get("link_transform"):
        matrix = _product(matrix, _inverse_rigid(_frame(target)))
    raw_com_m = _point(matrix, target["shape_center_of_mass_mm"])
    derived = dict(obj)
    derived.pop("shape_error", None)
    derived.update(
        {
            "volume_mm3": target["volume_mm3"],
            "solid_count": target.get("solid_count", 0),
            "shape_center_of_mass_mm": [v * 1000 for v in raw_com_m],
            "shape_valid": target.get("shape_valid"),
            "geometry_derivation": "native source shape + empirically verified LinkTransform rule",
        }
    )
    return derived


def installed_leaf_instances(report: dict) -> dict:
    """Flatten installed Model groups; never aggregate procedural body history.

    Raw Shape COM includes its own object/link placement, but excludes ancestor
    App::Part placements (verified with native synthetic fixtures). Model links
    therefore contribute ancestor transforms; leaf placements are not reapplied.
    """
    if not report.get("restore_completed"):
        raise ValueError("native report must record a completed assembly restore")
    objects = {
        f"{doc['name']}::{obj['name']}": obj
        for doc in report["documents"]
        for obj in doc["objects"]
    }
    master = report.get("master_document", "Assembly")
    root_reference = f"{master}::Model"
    leaves, missing, errors = [], [], []
    excluded_construction = []
    seen = set()
    active = {
        "AssemblyBase": 0,
        "AssemblyArt1": 1,
        "AssemblyArt2": 2,
        "AssemblyArt3": 3,
        "AssemblyArt4": 4,
        "AssemblyArt56": 5,
    }

    def physical_members(container):
        members = container.get("group_members", [])
        consumed = {}
        for reference in members:
            consumer = objects.get(reference, {})
            procedural = consumer.get("type") in {
                "Part::Mirroring",
                "Part::Compound",
                "Part::Cut",
                "Part::Fuse",
                "Part::MultiFuse",
                "Part::Common",
            } or (
                consumer.get("type") == "Part::FeaturePython"
                and consumer.get("name", "").casefold().startswith("array")
            )
            if not procedural:
                continue
            for source in consumer.get("out_list", []):
                if source in members and objects.get(source, {}).get("visibility") is False:
                    consumed[source] = reference
        for reference, consumer in consumed.items():
            excluded_construction.append(
                {
                    "source": reference,
                    "consumer": consumer,
                    "reason": "hidden procedural input alongside its installed output",
                }
            )
        return [reference for reference in members if reference not in consumed]

    def walk(reference, ancestors, path, root_group=None, stack=()):
        if reference in stack:
            errors.append({"reference": reference, "reason": "group/link cycle"})
            return
        obj = objects.get(reference)
        if obj is None:
            missing.append(reference)
            return
        object_type = obj["type"]
        current_path = (*path, reference)
        if object_type == "App::Link":
            target_reference = obj.get("linked_object_direct") or obj.get("linked_object")
            target = objects.get(target_reference)
            if target is not None and target["type"] in {"App::Part", "App::DocumentObjectGroup"}:
                group = root_group or obj["name"]
                combined = _product(ancestors, _frame(obj, "link_placement"))
                if obj.get("link_transform"):
                    combined = _product(combined, _frame(target))
                for child in physical_members(target):
                    walk(child, combined, current_path, group, (*stack, reference))
                return
            if target is None and target_reference and target_reference.endswith("::Model"):
                missing.append(target_reference)
                return
            obj = _derived_link_geometry(obj, target)
        if object_type in {"App::Part", "App::DocumentObjectGroup"}:
            combined = _product(ancestors, _frame(obj))
            for child in physical_members(obj):
                walk(child, combined, current_path, root_group, (*stack, reference))
            return
        # An editor group can alias objects already listed directly in Model.
        # Ignore those grouping-only hops in physical instance identity, while
        # retaining App::Link hops so repeated prototype instances remain distinct.
        identity = tuple(
            item for item in current_path if objects[item]["type"] != "App::DocumentObjectGroup"
        )
        if identity in seen:
            return
        seen.add(identity)
        # Bodies are leaves, even though Group includes sketches/features.
        # Geometry histories and OutList dependencies must not be traversed.
        if obj.get("shape_error"):
            errors.append(
                {
                    "reference": reference,
                    "instance_path": "/".join(current_path),
                    "reason": obj["shape_error"],
                }
            )
            return
        volume = obj.get("volume_mm3")
        if volume is None and (object_type.startswith("Part::") or object_type == "App::Link"):
            errors.append(
                {
                    "reference": reference,
                    "instance_path": "/".join(current_path),
                    "reason": "physical leaf lacks native shape inventory",
                }
            )
            return
        count = obj.get("solid_count", 0)
        if volume is None or volume <= 0 or count <= 0:
            return
        com = obj.get("shape_center_of_mass_mm")
        if com is None or not all(math.isfinite(value) for value in com):
            errors.append(
                {"reference": reference, "reason": "positive-volume shape lacks finite COM"}
            )
            return
        leaves.append(
            {
                "instance_id": "/".join(current_path),
                "object_reference": reference,
                "label": obj.get("label"),
                "object_type": object_type,
                "root_subassembly": root_group,
                "active_joint_count_assumption": active.get(root_group),
                "wrist_roll_membership_resolved": root_group != "AssemblyArt56",
                "volume_mm3": volume,
                "solid_count": count,
                "raw_shape_com_mm": com,
                "zero_world_com_m": _point(ancestors, com),
                "ancestor_transform_mm": ancestors,
                "linked_object": obj.get("linked_object_direct"),
                "native_state": obj.get("state", []),
                "shape_valid": obj.get("shape_valid"),
                "visibility": obj.get("visibility"),
                "mass_assignment": "not provided by geometry extraction",
                "geometry_derivation": obj.get(
                    "geometry_derivation", "direct raw native Shape inventory"
                ),
            }
        )

    walk(root_reference, _identity(), ())
    return {
        "coordinate_frame": "native Assembly::Model zero-pose frame, metres",
        "validation_class": "restored_cached_geometry_with_explicit_grouping_assumptions",
        "cad_joint_axes_verified": False,
        "complete_mass_model": False,
        "wrist_roll_body_membership_resolved": False,
        "native_audit_status": report.get("status"),
        "native_shape_validity_checked": report.get("shape_validation_requested", False),
        "instance_count": len(leaves),
        "mounted_bodies": leaves,
        "missing_object_records": sorted(set(missing)),
        "excluded_construction_sources": excluded_construction,
        "errors": errors,
        "body_grouping_assumption": (
            "Master Model subassembly membership; wrist internals unresolved"
        ),
    }


def merge_native_reports(metadata: dict, shapes: dict) -> dict:
    """Overlay filtered shape observations onto complete object metadata.

    This checks runtime/master names, not source-directory immutability. The
    caller must retain both source manifests and avoid changing CAD between runs.
    """
    for key in ("assembly_filename", "master_document", "freecad_version"):
        if metadata.get(key) != shapes.get(key):
            raise ValueError(f"native report {key} mismatch")
    if not metadata.get("restore_completed") or not shapes.get("restore_completed"):
        raise ValueError("both native reports must record a completed restore")
    result = json.loads(json.dumps(metadata))
    updates = {
        (doc["name"], obj["name"]): obj for doc in shapes["documents"] for obj in doc["objects"]
    }
    for doc in result["documents"]:
        for index, obj in enumerate(doc["objects"]):
            update = updates.get((doc["name"], obj["name"]))
            if update is not None:
                doc["objects"][index] = update
    result["shape_validation_requested"] = shapes.get("shape_validation_requested", False)
    result["merged_shape_report_status"] = shapes.get("status")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="read-only upstream freecad-src directory")
    parser.add_argument("--urdf", type=Path, help="pinned upstream thor.urdf.xacro, not executed")
    parser.add_argument("--inventory", type=Path, help="pinned native source hash inventory")
    parser.add_argument(
        "--native-report", type=Path, help="restored native audit JSON for installed leaves"
    )
    parser.add_argument(
        "--shape-report", type=Path, help="optional filtered native shape supplement"
    )
    args = parser.parse_args()
    result = extract(args.source, args.urdf, args.inventory)
    if args.native_report:
        native = json.loads(args.native_report.read_text())
        if args.shape_report:
            native = merge_native_reports(native, json.loads(args.shape_report.read_text()))
        result["native_installed_instances"] = installed_leaf_instances(native)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
