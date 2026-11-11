"""Read-only Art1 source fingerprints and fail-closed geometry-capture checks.

Ordinary Python never imports FreeCAD or executes document proxies. A source
fingerprint is not a rebuild. The comparison command checks supplied numerical
captures; it cannot authenticate a native run or approve a CAD replacement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
SOURCE_SHA256 = "8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a"
EARLY_CHAIN = ("Sketch", "Pad", "Sketch001", "Pad001", "Sketch002", "Groove")
CRITICAL_CHAIN = (*EARLY_CHAIN, "Thickness", "Sketch003", "Pad002", "Sketch004", "Pocket")
STAGES = ("rebuilt", "reopened", "restored")
DATUM_TYPES = {"PartDesign::CoordinateSystem", "PartDesign::Line"}
TOLERANCES = {
    "volume_mm3": 1e-6,
    "bounds_mm": 1e-9,
    "center_of_mass_mm": 1e-9,
    "datum_matrix": 1e-12,
    "hole_center_mm": 1e-9,
    "hole_axis": 1e-12,
    "hole_radius_mm": 1e-9,
    "hole_depth_mm": 1e-9,
    "surface_distance_mm": 1e-9,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _number(value: object, field: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    if not math.isfinite(value) or (nonnegative and value < 0):
        raise ValueError(
            f"{field} must be finite and {'nonnegative' if nonnegative else 'numeric'}"
        )
    return float(value)


def _vector(value: object, count: int, field: str) -> list[float]:
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"{field} must contain {count} numbers")
    return [_number(item, field) for item in value]


def _mapping(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256")
    return value


def _load(path: Path) -> dict:
    def invalid(value: str) -> None:
        raise ValueError(f"nonfinite JSON value: {value}")

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return _mapping(
        json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=invalid,
            object_pairs_hook=unique_pairs,
        ),
        str(path),
    )


def _xml_value(element: ET.Element) -> dict:
    """Preserve saved attributes/ordering without interpreting FreeCAD enums."""
    result: dict = {"tag": element.tag, "attributes": dict(sorted(element.attrib.items()))}
    children = [_xml_value(child) for child in element]
    if children:
        result["children"] = children
    if element.text and element.text.strip():
        result["text"] = element.text.strip()
    return result


def _property(object_node: ET.Element, name: str) -> ET.Element | None:
    return object_node.find(f'./Properties/Property[@name="{name}"]')


def _placement(object_node: ET.Element, field: str = "Placement") -> list[float]:
    prop = _property(object_node, field)
    placement = None if prop is None else prop.find("PropertyPlacement")
    if placement is None:
        raise ValueError(f"missing {field} in {object_node.get('name')}")
    result = [float(placement.attrib[key]) for key in ("Px", "Py", "Pz", "Q0", "Q1", "Q2", "Q3")]
    _vector(result, 7, field)
    if abs(sum(x * x for x in result[3:]) - 1) > 1e-12:
        raise ValueError("saved placement quaternion must have unit norm")
    return result


def _rotate(vector: list[float], quaternion: list[float]) -> list[float]:
    x, y, z, w = quaternion
    vx, vy, vz = vector
    # Quaternion-vector multiplication, independent of FreeCAD runtime.
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return [
        vx + w * tx + y * tz - z * ty,
        vy + w * ty + z * tx - x * tz,
        vz + w * tz + x * ty - y * tx,
    ]


def source_fingerprint(source: Path, evidence: dict) -> dict:
    """Fingerprint pinned Body members, references, saved BReps and circle frames."""
    if evidence.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("migration evidence does not identify the pinned Art1 source")
    content = source.read_bytes()
    if _sha(content) != SOURCE_SHA256:
        raise ValueError("Art1 source SHA-256 differs from the pinned reference")
    with zipfile.ZipFile(source) as archive:
        names = [item.filename for item in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive members")
        if sum(item.file_size for item in archive.infolist()) > 100_000_000:
            raise ValueError("Art1 source archive exceeds the read-only inspection bound")
        document_bytes = archive.read("Document.xml")
        document = ET.fromstring(document_bytes)
        kinds = {
            node.attrib["name"]: node.attrib["type"]
            for node in document.findall("./Objects/Object")
        }
        objects = {node.attrib["name"]: node for node in document.findall("./ObjectData/Object")}
        if kinds.get("Body") != "PartDesign::Body":
            raise ValueError("source Body type differs")
        body = objects["Body"]
        if _placement(body) != [0, 0, 0, 0, 0, 0, 1]:
            raise ValueError("source Body must have identity placement; do not double-transform")
        members = [
            n.attrib["value"]
            for n in body.findall('./Properties/Property[@name="Group"]/LinkList/Link')
        ]
        if members != evidence["ordered_body_members"] or len(members) != len(set(members)):
            raise ValueError("ordered Body members differ from pinned migration evidence")
        tip = body.find('./Properties/Property[@name="Tip"]/Link')
        if tip is None or tip.get("value") != evidence["body_tip"]:
            raise ValueError("Body tip differs from pinned migration evidence")
        targets = evidence["assembly_contract"]["unique_target_names"]
        if set(targets) != {"Body"} | {n for n in members if kinds[n] in DATUM_TYPES}:
            raise ValueError("AssemblyArt1 target contract differs from saved source datums")
        fingerprints = []
        circles = []
        selected_properties = {
            "BaseFeature",
            "Profile",
            "ReferenceAxis",
            "Support",
            "ExternalGeometry",
            "ExpressionEngine",
            "Length",
            "Length2",
            "Type",
            "Reversed",
            "Midplane",
            "Intersection",
            "Value",
            "Join",
            "Angle",
            "MapMode",
            "AttachmentOffset",
        }
        for name in members:
            node = objects[name]
            record = {"name": name, "type": kinds[name]}
            shape = node.find('./Properties/Property[@name="Shape"]/Part')
            if shape is not None:
                member = shape.attrib["file"]
                data = archive.read(member)
                record["saved_brep"] = {"member": member, "bytes": len(data), "sha256": _sha(data)}
            record["property_fingerprints"] = {
                p.attrib["name"]: _sha(json.dumps(_xml_value(p), sort_keys=True).encode())
                for p in node.findall("./Properties/Property")
                if p.attrib["name"]
                in selected_properties | {"Constraints", "Geometry", "Placement"}
            }
            if name in CRITICAL_CHAIN or name in ("DatumPlane001", "Sketch005", "Pocket001"):
                record["saved_properties"] = {
                    p.attrib["name"]: _xml_value(p)
                    for p in node.findall("./Properties/Property")
                    if p.attrib["name"] in selected_properties
                }
                record["placement_mm_xyzw"] = _placement(node)
                record["constraints"] = [
                    dict(c.attrib)
                    for c in node.findall("./Properties/Property/ConstraintList/Constrain")
                ]
                record["geometry"] = [
                    _xml_value(g)
                    for g in node.findall("./Properties/Property/GeometryList/Geometry")
                ]
            if kinds[name] in DATUM_TYPES:
                record["placement_mm_xyzw"] = _placement(node)
            fingerprints.append(record)
            for circle in node.findall("./Properties/Property/GeometryList/Geometry/Circle"):
                if name not in ("Sketch004", "Sketch005"):
                    continue
                placement = _placement(node)
                center = [float(circle.attrib[f"Center{axis}"]) for axis in "XYZ"]
                normal = [float(circle.attrib[f"Normal{axis}"]) for axis in "XYZ"]
                center_rotated = _rotate(center, placement[3:])
                circles.append(
                    {
                        "sketch": name,
                        "radius_mm": float(circle.attrib["Radius"]),
                        "center_in_sketch_mm": center,
                        "center_in_native_mm": [
                            a + b for a, b in zip(placement[:3], center_rotated, strict=True)
                        ],
                        "normal_in_native": _rotate(normal, placement[3:]),
                        "interpretation": (
                            "saved sketch geometry transformed by saved placement; "
                            "not a rebuilt cut"
                        ),
                    }
                )
    if _sha(source.read_bytes()) != SOURCE_SHA256:
        raise ValueError("source changed during read-only inspection")
    return {
        "schema_version": 1,
        "evidence_class": "pinned_zip_xml_source_inspection_only",
        "source_revision": SOURCE_REVISION,
        "source_sha256": SOURCE_SHA256,
        "document_xml_sha256": _sha(document_bytes),
        "source_program_version": document.get("ProgramVersion"),
        "source_unchanged": True,
        "body_tip": tip.attrib["value"],
        "ordered_body_members": members,
        "assembly_target_types": {name: kinds[name] for name in targets},
        "saved_circle_frames": circles,
        "spreadsheet_cells": [
            dict(c.attrib)
            for c in objects["Spreadsheet"].findall("./Properties/Property/Cells/Cell")
        ],
        "members": fingerprints,
        "native_recompute_performed": False,
        "earliest_true_rebuild_drift": None,
        "migration_accepted": False,
    }


def historical_diagnostics(evidence: dict, evidence_sha256: str) -> dict:
    """Re-evaluate captured numbers without claiming a new native experiment."""
    if evidence.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("unexpected Art1 evidence source hash")
    probe = evidence["failed_migration_probe"]
    measurements = probe["feature_measurements"]
    names = [item["name"] for item in measurements]
    if len(names) != len(set(names)):
        raise ValueError("duplicate feature measurements")
    by_name = {item["name"]: item for item in measurements}
    rows = []
    for item in measurements:
        saved = _number(item["saved"]["volume_mm3"], "saved volume", nonnegative=True)
        rebuilt = _number(
            item["intersection_rebuild"]["volume_mm3"], "rebuilt volume", nonnegative=True
        )
        rows.append(
            {
                "name": item["name"],
                "saved_volume_mm3": saved,
                "rebuilt_volume_mm3": rebuilt,
                "volume_delta_mm3": rebuilt - saved,
                "exact_volume_check_passed": abs(rebuilt - saved) < TOLERANCES["volume_mm3"],
            }
        )
    base, cut = by_name["Pad002"], by_name["Pocket"]
    saved_removed = base["saved"]["volume_mm3"] - cut["saved"]["volume_mm3"]
    rebuilt_removed = (
        base["intersection_rebuild"]["volume_mm3"] - cut["intersection_rebuild"]["volume_mm3"]
    )
    if saved_removed <= 0:
        raise ValueError("historical saved Pocket does not remove material")
    return {
        "schema_version": 1,
        "evidence_class": "offline_reanalysis_of_historical_native_capture",
        "input_evidence_sha256": _digest(evidence_sha256, "evidence_sha256"),
        "source_revision": SOURCE_REVISION,
        "source_sha256": SOURCE_SHA256,
        "native_recompute_performed": False,
        "feature_measurements": rows,
        "earliest_captured_drift": next(
            (row["name"] for row in rows if not row["exact_volume_check_passed"]), None
        ),
        "uncaptured_early_features": [name for name in EARLY_CHAIN if name not in by_name],
        "earliest_true_rebuild_drift": None,
        "saved_pocket_removed_mm3": saved_removed,
        "rebuilt_pocket_removed_mm3": rebuilt_removed,
        "disappearing_cut_detected": rebuilt_removed <= TOLERANCES["volume_mm3"],
        "solver_failure": probe["first_invalid_feature"],
        "root_cause_isolated": False,
        "migration_accepted": False,
        "required_next_capture": (
            "Saved and rebuilt early sketch/feature dimensions, placements, bounds, volumes "
            "and semantic support geometry; one variable per experiment."
        ),
    }


def _shape(value: object, field: str) -> dict:
    shape = _mapping(value, field)
    if not isinstance(shape.get("valid"), bool):
        raise ValueError(f"{field}.valid must be a boolean")
    if type(shape.get("solid_count")) is not int or shape["solid_count"] < 0:
        raise ValueError(f"{field}.solid_count must be a nonnegative integer")
    _number(shape["volume_mm3"], field, nonnegative=True)
    bounds = _vector(shape["bounds_mm"], 6, field)
    if any(bounds[i] > bounds[i + 1] for i in (0, 2, 4)):
        raise ValueError(f"{field} bounds are reversed")
    _vector(shape["center_of_mass_mm"], 3, field)
    return shape


def _max_error(first: list, second: list) -> float:
    return max(abs(a - b) for a, b in zip(first, second, strict=True))


def _matrix_from_placement(value: list[float]) -> list[float]:
    """Row-major homogeneous native-mm matrix from FreeCAD's saved xyzw quaternion."""
    px, py, pz, x, y, z, w = _vector(value, 7, "placement")
    if abs(x * x + y * y + z * z + w * w - 1) > 1e-12:
        raise ValueError("source quaternion must have unit norm")
    return [
        1 - 2 * (y * y + z * z),
        2 * (x * y - w * z),
        2 * (x * z + w * y),
        px,
        2 * (x * y + w * z),
        1 - 2 * (x * x + z * z),
        2 * (y * z - w * x),
        py,
        2 * (x * z - w * y),
        2 * (y * z + w * x),
        1 - 2 * (x * x + y * y),
        pz,
        0,
        0,
        0,
        1,
    ]


def _rigid_matrix(value: object, field: str) -> list[float]:
    matrix = _vector(value, 16, field)
    if _max_error(matrix[12:], [0, 0, 0, 1]) > 1e-12:
        raise ValueError(f"{field} is not a homogeneous rigid transform")
    rows = [matrix[i : i + 3] for i in (0, 4, 8)]
    for i in range(3):
        for j in range(3):
            dot = sum(a * b for a, b in zip(rows[i], rows[j], strict=True))
            if abs(dot - int(i == j)) > 1e-12:
                raise ValueError(f"{field} rotation is not orthonormal")
    a, b, c = rows
    determinant = (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )
    if abs(determinant - 1) > 1e-12:
        raise ValueError(f"{field} rotation must preserve handedness")
    return matrix


def compare_capture(capture: dict, source_contract: dict) -> dict:
    """Require all supplied comparisons to agree; never approve a migration.

    `source_contract` must be the pinned source fingerprint. Capture producers must
    measure both Boolean directions, surface distance, semantic bolt cylinders,
    24 datum matrices and the complete 25-target/80-member contract. Synthetic
    fixtures may exercise the checker but cannot become native evidence.
    """
    if (
        source_contract.get("source_sha256") != SOURCE_SHA256
        or source_contract.get("evidence_class") != "pinned_zip_xml_source_inspection_only"
    ):
        raise ValueError("comparison requires a pinned source fingerprint")
    if (
        type(capture.get("schema_version")) is not int
        or capture.get("schema_version") != 1
        or capture.get("source_sha256") != SOURCE_SHA256
    ):
        raise ValueError("capture schema/source does not match pinned Art1")
    evidence_class = capture.get("evidence_class")
    if evidence_class not in ("native_geometry_capture", "synthetic_geometry_fixture"):
        raise ValueError("capture evidence_class must explicitly identify native or synthetic data")
    _digest(capture.get("candidate_sha256"), "candidate_sha256")
    _digest(capture.get("capture_script_sha256"), "capture_script_sha256")
    saved_tip = next(
        member
        for member in source_contract["members"]
        if member["name"] == source_contract["body_tip"]
    )["saved_brep"]["sha256"]
    if capture.get("saved_tip_brep_sha256") != saved_tip:
        raise ValueError("capture saved tip BRep does not identify the source fingerprint")
    _string(capture.get("runtime_version"), "runtime_version")
    _string(capture.get("candidate_path_kind"), "candidate_path_kind")
    if capture["candidate_path_kind"] != "separate_copy":
        raise ValueError("candidate must be a separate copy")
    failures: list[str] = []
    errors: dict[str, float] = {}
    if capture.get("source_unchanged") is not True:
        failures.append("source_unchanged")
    if capture.get("save_reopen_force_recompute_completed") is not True:
        failures.append("save_reopen_force_recompute_completed")
    states = _mapping(capture.get("object_states"), "object_states")
    expected_objects = {"Body", *source_contract["ordered_body_members"]}
    if len(expected_objects) != 81 or len(source_contract["assembly_target_types"]) != 25:
        raise ValueError("source fingerprint must retain 80 Body members and 25 assembly targets")
    if set(states) != expected_objects:
        failures.append("complete_object_states")
    for name, per_stage in states.items():
        for stage in STAGES:
            state = _mapping(per_stage, name).get(stage)
            if (
                not isinstance(state, list)
                or not state
                or any(not isinstance(s, str) for s in state)
            ):
                raise ValueError(f"{name}.{stage} states must be a nonempty string list")
            if state != ["Up-to-date"]:
                failures.append(f"object_state:{name}:{stage}")
    expected_targets = source_contract["assembly_target_types"]
    if capture.get("assembly_target_types") != expected_targets:
        failures.append("assembly_target_name_type_contract")
    body = _mapping(capture.get("body"), "body")
    saved = _shape(body.get("saved"), "body.saved")
    if saved["volume_mm3"] <= 0:
        raise ValueError("saved Body must have positive volume")
    for stage in STAGES:
        actual = _shape(body.get(stage), f"body.{stage}")
        if (
            not actual["valid"]
            or actual["solid_count"] != 1
            or not saved["valid"]
            or saved["solid_count"] != 1
        ):
            failures.append(f"body_solid:{stage}")
        for field in ("volume_mm3", "bounds_mm", "center_of_mass_mm"):
            error = (
                abs(saved[field] - actual[field])
                if field == "volume_mm3"
                else _max_error(saved[field], actual[field])
            )
            errors[f"body:{stage}:{field}"] = error
            if error >= TOLERANCES[field]:
                failures.append(f"body:{stage}:{field}")
        for field in ("source_minus_candidate_mm3", "candidate_minus_source_mm3"):
            if _number(actual.get(field), field, nonnegative=True) != 0:
                failures.append(f"body:{stage}:{field}")
        if (
            _number(actual.get("surface_distance_mm"), "surface_distance_mm", nonnegative=True)
            >= TOLERANCES["surface_distance_mm"]
        ):
            failures.append(f"body:{stage}:surface_distance_mm")
    expected_datums = set(expected_targets) - {"Body"}
    source_members = {item["name"]: item for item in source_contract["members"]}
    datums = _mapping(capture.get("datums"), "datums")
    if set(datums) != expected_datums:
        failures.append("complete_datum_matrices")
    for name, value in datums.items():
        datum = _mapping(value, name)
        reference = _rigid_matrix(datum.get("saved"), f"{name}.saved")
        if name not in source_members or "placement_mm_xyzw" not in source_members[name]:
            failures.append(f"datum:{name}:not_in_source_contract")
        elif (
            _max_error(reference, _matrix_from_placement(source_members[name]["placement_mm_xyzw"]))
            >= TOLERANCES["datum_matrix"]
        ):
            failures.append(f"datum:{name}:saved_does_not_match_source")
        for stage in STAGES:
            matrix = _rigid_matrix(datum.get(stage), f"{name}.{stage}")
            error = _max_error(reference, matrix)
            errors[f"datum:{name}:{stage}"] = error
            if error >= TOLERANCES["datum_matrix"]:
                failures.append(f"datum:{name}:{stage}")
    holes = _mapping(capture.get("bolt_holes"), "bolt_holes")
    if set(holes) != {"body_bolt", "head_recess"}:
        failures.append("complete_semantic_bolt_holes")
    for name, value in holes.items():
        hole = _mapping(value, name)
        saved_hole = _mapping(hole.get("saved"), name)
        expected_sketch = "Sketch004" if name == "body_bolt" else "Sketch005"
        source_circle = next(
            item
            for item in source_contract["saved_circle_frames"]
            if item["sketch"] == expected_sketch
        )
        if (
            _max_error(
                _vector(saved_hole.get("center_mm"), 3, name), source_circle["center_in_native_mm"]
            )
            >= TOLERANCES["hole_center_mm"]
            or _max_error(
                _vector(saved_hole.get("axis"), 3, name), source_circle["normal_in_native"]
            )
            >= TOLERANCES["hole_axis"]
            or abs(_number(saved_hole.get("radius_mm"), name) - source_circle["radius_mm"])
            >= TOLERANCES["hole_radius_mm"]
        ):
            failures.append(f"hole:{name}:saved_does_not_match_source_sketch")
        for stage in STAGES:
            actual = _mapping(hole.get(stage), name)
            for field, count in (("center_mm", 3), ("axis", 3)):
                first = _vector(saved_hole.get(field), count, name)
                second = _vector(actual.get(field), count, name)
                if field == "axis" and any(
                    abs(sum(x * x for x in axis) - 1) > 1e-12 for axis in (first, second)
                ):
                    raise ValueError("hole axis must be a unit vector")
                error = _max_error(first, second)
                if error >= TOLERANCES["hole_center_mm" if field == "center_mm" else "hole_axis"]:
                    failures.append(f"hole:{name}:{stage}:{field}")
            for field in ("radius_mm", "depth_mm"):
                first = _number(saved_hole.get(field), name, nonnegative=True)
                second = _number(actual.get(field), name, nonnegative=True)
                if first <= 0 or second <= 0 or abs(first - second) >= TOLERANCES[f"hole_{field}"]:
                    failures.append(f"hole:{name}:{stage}:{field}")
    effects = _mapping(capture.get("cut_effects_mm3"), "cut_effects_mm3")
    if set(effects) != {"Pocket", "Pocket001"}:
        failures.append("complete_cut_effects")
    for name, value in effects.items():
        effect = _mapping(value, name)
        reference = _number(effect.get("saved"), name, nonnegative=True)
        for stage in STAGES:
            actual = _number(effect.get(stage), name, nonnegative=True)
            if (
                reference <= TOLERANCES["volume_mm3"]
                or actual <= TOLERANCES["volume_mm3"]
                or abs(reference - actual) >= TOLERANCES["volume_mm3"]
            ):
                failures.append(f"material_removal:{name}:{stage}")
    return {
        "schema_version": 1,
        "evidence_class": "offline_geometry_capture_comparison",
        "input_evidence_class": evidence_class,
        "source_sha256": SOURCE_SHA256,
        "candidate_sha256": capture["candidate_sha256"],
        "saved_tip_brep_sha256": saved_tip,
        "saved_body_geometry_independently_authenticated": False,
        "comparison_tolerances": TOLERANCES,
        "thresholds_are_manufacturing_tolerances": False,
        "all_numerical_and_contract_checks_passed": not failures,
        "eligible_for_native_manual_review": not failures
        and evidence_class == "native_geometry_capture",
        "failures": sorted(set(failures)),
        "absolute_errors": errors,
        "migration_accepted": False,
        "remaining_gates": [
            "Authenticate native captures, runtime/addon pins and original bytes independently.",
            "Check semantic expression/support migration and reversible design edits (A3-A6).",
            "Validate a separate whole assembly; regenerate geometry/load evidence (A8).",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    source = commands.add_parser("source", help="Read pinned Art1 ZIP/XML; no CAD execution")
    source.add_argument("source", type=Path)
    source.add_argument("--evidence", type=Path, required=True)
    history = commands.add_parser("history", help="Reanalyze the saved failed probe")
    history.add_argument("evidence", type=Path)
    compare = commands.add_parser("compare", help="Check a supplied geometry capture")
    compare.add_argument("capture", type=Path)
    compare.add_argument("--source-contract", type=Path, required=True)
    for command in (source, history, compare):
        command.add_argument("--output", type=Path, help="New JSON path; never overwrite")
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError("output already exists; historical evidence is never overwritten")
        if args.command == "source":
            result = source_fingerprint(args.source, _load(args.evidence))
        elif args.command == "history":
            result = historical_diagnostics(_load(args.evidence), _sha(args.evidence.read_bytes()))
        else:
            result = compare_capture(_load(args.capture), _load(args.source_contract))
        data = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(data)
        else:
            print(data, end="")
        if args.command == "compare" and not result["all_numerical_and_contract_checks_passed"]:
            return 1
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
