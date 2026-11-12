"""Read-only Art1 support descriptors; a match never approves an attachment.

Original cached provider BReps and restored candidate Shapes are inspected in
the common identity Body frame. No references, expressions or CAD files change.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

FLAG = "RAFTEL_RUN_ART1_SEMANTIC_SUPPORTS"
SOURCE_SHA256 = "8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a"
SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
CANDIDATE_SHA256 = "6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd"
POLICY = {"position_mm": 1e-6, "direction": 1e-9, "metric_relative": 1e-8}
IDENTITY = [float(i == j) for i in range(4) for j in range(4)]
SUPPORTED = {"plane", "cylinder", "cone", "sphere", "circle", "line"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def placement_error(actual, expected) -> float:
    if any(not isinstance(row, (list, tuple)) or len(row) != 16 for row in (actual, expected)):
        raise ValueError("two sixteen-entry placement matrices required")
    return max(abs(finite(a) - finite(b)) for a, b in zip(actual, expected, strict=True))


def strict_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"nonfinite JSON constant: {value}")

    with path.open("rb") as stream:
        raw = stream.read(32 * 1024**2 + 1)
    if len(raw) > 32 * 1024**2:
        raise ValueError("JSON exceeds inspection budget")
    result = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=invalid,
        parse_float=lambda x: finite(float(x)),
    )
    if not isinstance(result, dict):
        raise ValueError("JSON root must be an object")
    return result


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("finite numeric descriptor required")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("finite numeric descriptor required")
    return result


def vector(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("three descriptor coordinates required")
    return [finite(v) for v in value]


def unit(value):
    result = vector(value)
    length = math.hypot(*result)
    if not math.isclose(length, 1, rel_tol=0, abs_tol=1e-8):
        raise ValueError("descriptor direction must be unit length")
    return result


def ledger(evidence: dict) -> list[dict]:
    if (
        evidence.get("source_sha256") != SOURCE_SHA256
        or type(evidence.get("schema_version")) is not int
        or evidence["schema_version"] != 1
        or evidence.get("source_revision") != SOURCE_REVISION
        or evidence.get("validation_class")
        != "source_dependency_mapping_and_failed_native_migration_probe_not_repaired_history"
    ):
        raise ValueError("unsupported Art1 source")
    owners = evidence.get("all_subshape_attachment_dependencies")
    if not isinstance(owners, dict) or len(owners) != 53:
        raise ValueError("expected all 53 dependent owner objects")
    rows = []
    for owner, properties in owners.items():
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", owner) is None:
            raise ValueError("unsafe owner name")
        for prop in properties:
            if prop.get("property") not in {"Support", "ExternalGeometry", "MirrorPlane"}:
                raise ValueError("unsupported dependency property")
            for link in prop["links"]:
                provider = link.get("obj", link.get("value"))
                if not isinstance(provider, str) or not re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]*", provider
                ):
                    raise ValueError("unsafe provider name")
                for sub in link.get("subelements", [link.get("sub", "")]):
                    if not isinstance(sub, str) or not (
                        sub in {"", "V_Axis"} or re.fullmatch(r"(?:Face|Edge)[1-9][0-9]*", sub)
                    ):
                        raise ValueError("unsupported reference selector")
                    rows.append(
                        dict(
                            reference_id=f"reference-{len(rows):03d}",
                            owner=owner,
                            property=prop["property"],
                            provider=provider,
                            original_selector=sub,
                            geometric_reference=bool(
                                re.fullmatch(r"(?:Face|Edge)[1-9][0-9]*", sub)
                            ),
                        )
                    )
    if len(rows) != 80 or sum(row["geometric_reference"] for row in rows) != 69:
        raise ValueError("reference census differs from 80 total / 69 subshape references")
    identities = [(r["owner"], r["property"], r["provider"], r["original_selector"]) for r in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate dependency entry")
    return rows


def xml_reference_identities(document, members: list[str]) -> list[tuple[str, str, str, str]]:
    """Decode native serialized links, independently of the historical ledger."""
    objects = {node.get("name"): node for node in document.findall("./ObjectData/Object")}
    result = []
    for owner in members:
        for prop in objects[owner].findall("./Properties/Property"):
            name = prop.get("name")
            if name not in {"Support", "ExternalGeometry", "MirrorPlane"}:
                continue
            for container in prop:
                if container.tag == "LinkSubList":
                    links = list(container)
                    if int(container.get("count")) != len(links):
                        raise ValueError("serialized reference count mismatch")
                    result.extend((owner, name, link.get("obj"), link.get("sub")) for link in links)
                elif container.tag == "LinkSub":
                    subs = list(container)
                    if int(container.get("count")) != len(subs):
                        raise ValueError("serialized subelement count mismatch")
                    result.extend(
                        (owner, name, container.get("value"), s.get("value")) for s in subs
                    )
                else:
                    raise ValueError("unsupported serialized reference representation")
    return result


def authenticate_ledger(source: Path, evidence: dict) -> list[dict]:
    if source.stat().st_size > 16 * 1024**2 or sha(source) != SOURCE_SHA256:
        raise ValueError("original source archive pin differs")
    rows = ledger(evidence)
    with zipfile.ZipFile(source) as archive:
        document = ET.fromstring(archive.read("Document.xml"))
    members = [
        node.get("value")
        for node in document.findall(
            './ObjectData/Object[@name="Body"]/Properties/Property[@name="Group"]/LinkList/Link'
        )
    ]
    if len(members) != 80 or members != evidence.get("ordered_body_members"):
        raise ValueError("source ordered Body membership differs")
    actual = xml_reference_identities(document, evidence["ordered_body_members"])
    expected = [(r["owner"], r["property"], r["provider"], r["original_selector"]) for r in rows]
    if Counter(actual) != Counter(expected):
        raise ValueError("reference ledger differs from the exact source XML")
    return rows


def descriptor(value: dict) -> dict:
    if not isinstance(value, dict) or value.get("kind") not in SUPPORTED | {"unsupported"}:
        raise ValueError("unsupported descriptor schema")
    if not isinstance(value.get("subelement"), str) or not re.fullmatch(
        r"(?:Face|Edge)[1-9][0-9]*", value["subelement"]
    ):
        raise ValueError("invalid descriptor subelement")
    if value["kind"] == "unsupported":
        return value
    vector(value["anchor_mm"])
    if value["kind"] not in {"sphere"}:
        unit(value["axis"])
    if value["kind"] in {"cylinder", "sphere", "circle"} and finite(value["radius_mm"]) <= 0:
        raise ValueError("positive radius required")
    if value["kind"] == "cone" and not 0 < finite(value["semi_angle_rad"]) < math.pi / 2:
        raise ValueError("cone semi-angle outside supported range")
    if value.get("orientation") not in {"Forward", "Reversed", "Internal", "External"}:
        raise ValueError("unknown topological orientation")
    trim = value["trim"]
    vector(trim["center_mm"])
    if len(trim["bounds_mm"]) != 6:
        raise ValueError("six trim extrema required")
    bounds = [finite(x) for x in trim["bounds_mm"]]
    if any(bounds[i] > bounds[i + 3] for i in range(3)):
        raise ValueError("unordered trim extrema")
    if finite(trim["measure"]) <= 0:
        raise ValueError("positive trimmed area/length required")
    for key in ("vertex_count", "edge_count"):
        if type(trim[key]) is not int or trim[key] < 0:
            raise ValueError("invalid trim topology count")
    adjacency = value.get("adjacency")
    if adjacency is not None and (
        not isinstance(adjacency, list) or any(not isinstance(x, str) for x in adjacency)
    ):
        raise ValueError("invalid adjacency descriptor")
    return value


def comparison(expected: dict, actual: dict) -> dict:
    expected, actual = descriptor(expected), descriptor(actual)
    if "unsupported" in {expected["kind"], actual["kind"]}:
        return {"geometry_match": False, "strict_match": False, "reason": "unsupported_geometry"}
    if expected["kind"] != actual["kind"]:
        return {"geometry_match": False, "strict_match": False, "reason": "different_primitive"}
    errors = {}
    delta = [b - a for a, b in zip(expected["anchor_mm"], actual["anchor_mm"], strict=True)]
    same_axis_direction = True
    if expected["kind"] != "sphere":
        axis, other = expected["axis"], actual["axis"]
        along = math.fsum(x * y for x, y in zip(delta, axis, strict=True))
        errors["axis_unsigned"] = min(math.dist(axis, other), math.dist(axis, [-x for x in other]))
        same_axis_direction = math.dist(axis, other) <= POLICY["direction"]
        if expected["kind"] in {"cylinder", "line"}:
            delta = [d - along * a for d, a in zip(delta, axis, strict=True)]
        elif expected["kind"] == "plane":
            delta = [along]
    errors["support_position_mm"] = math.hypot(*delta)
    for field in ("radius_mm", "semi_angle_rad"):
        if field in expected:
            errors[field] = abs(expected[field] - actual[field])
    geometry = errors["support_position_mm"] <= POLICY["position_mm"]
    geometry &= errors.get("axis_unsigned", 0) <= POLICY["direction"]
    geometry &= errors.get("radius_mm", 0) <= POLICY["position_mm"]
    geometry &= errors.get("semi_angle_rad", 0) <= POLICY["direction"]
    first, second = expected["trim"], actual["trim"]
    errors["trim_center_mm"] = math.dist(first["center_mm"], second["center_mm"])
    errors["trim_bounds_mm"] = max(
        abs(a - b) for a, b in zip(first["bounds_mm"], second["bounds_mm"], strict=True)
    )
    errors["trim_measure_relative"] = abs(first["measure"] - second["measure"]) / max(
        first["measure"], second["measure"]
    )
    trim_matches = (
        errors["trim_center_mm"] <= POLICY["position_mm"]
        and errors["trim_bounds_mm"] <= POLICY["position_mm"]
        and errors["trim_measure_relative"] <= POLICY["metric_relative"]
        and all(first[key] == second[key] for key in ("vertex_count", "edge_count"))
    )
    adjacency_known = expected["adjacency"] is not None and actual["adjacency"] is not None
    return {
        "geometry_match": bool(geometry),
        "strict_match": bool(
            geometry
            and trim_matches
            and adjacency_known
            and expected["adjacency"] == actual["adjacency"]
            and expected["orientation"] == actual["orientation"]
            and same_axis_direction
        ),
        "trim_matches": trim_matches,
        "adjacency_known": adjacency_known,
        "adjacency_matches": adjacency_known and expected["adjacency"] == actual["adjacency"],
        "orientation_matches": expected["orientation"] == actual["orientation"],
        "axis_direction_matches": same_axis_direction,
        "errors": errors,
    }


def match_reference(expected: dict, candidates: list[dict], literal: str) -> dict:
    descriptor(expected)
    names = [descriptor(row)["subelement"] for row in candidates]
    if len(names) != len(set(names)):
        raise ValueError("duplicate candidate subelement")
    if expected["kind"] == "unsupported":
        return {"status": "unsupported", "selected": None, "strict_matches": [], "literal": None}
    checks = [(row["subelement"], comparison(expected, row)) for row in candidates]
    matches = [name for name, check in checks if check["strict_match"]]
    return {
        "status": "unique_descriptor_match"
        if len(matches) == 1
        else "ambiguous"
        if matches
        else "no_match",
        "selected": matches[0] if len(matches) == 1 else None,
        "strict_matches": matches,
        "geometric_candidates": [name for name, check in checks if check["geometry_match"]],
        "literal": next((check for name, check in checks if name == literal), None),
        "literal_exists": literal in names,
        "support_remapped": False,
        "attachment_approved": False,
    }


def _v(value):
    return [finite(value.x), finite(value.y), finite(value.z)]


def _primitive_type(shape, face: bool) -> str:
    try:
        return type(shape.Surface if face else shape.Curve).__name__
    except Exception:
        return "unavailable_native_geometry"


def native_descriptors(shape) -> list[dict]:
    if len(shape.Edges) > 5000 or len(shape.Faces) > 2500:
        raise ValueError("provider shape exceeds bounded descriptor census")
    edges = list(shape.Edges)
    adjacency = [[] for _ in edges]
    buckets = {}
    for index, edge in enumerate(edges):
        buckets.setdefault(edge.hashCode(), []).append((index, edge))
    for face in shape.Faces:
        for member in face.Edges:
            matches = [(i, e) for i, e in buckets.get(member.hashCode(), []) if e.isSame(member)]
            if len(matches) != 1:
                raise ValueError("provider adjacency cannot identify a unique native edge")
            adjacency[matches[0][0]].append(_primitive_type(face, True))
    result = []
    for category, objects in (("Face", shape.Faces), ("Edge", edges)):
        for index, item in enumerate(objects, 1):
            face = category == "Face"
            native_type = _primitive_type(item, face)
            kind = {
                "Plane": "plane",
                "Cylinder": "cylinder",
                "Cone": "cone",
                "Sphere": "sphere",
                "Circle": "circle",
                "Line": "line",
                "LineSegment": "line",
            }.get(native_type, "unsupported")
            record = {"subelement": f"{category}{index}", "kind": kind, "native_type": native_type}
            if kind == "unsupported":
                record["reason"] = "primitive_parameterization_not_implemented"
                result.append(record)
                continue
            try:
                geometry = item.Surface if face else item.Curve
                if kind == "plane":
                    u1, u2, v1, v2 = item.ParameterRange
                    anchor = item.valueAt((u1 + u2) / 2, (v1 + v2) / 2)
                    axis = item.normalAt((u1 + u2) / 2, (v1 + v2) / 2)
                elif kind == "line":
                    first, last = item.Vertexes[0].Point, item.Vertexes[-1].Point
                    anchor, axis = first, last.sub(first)
                else:
                    anchor = geometry.Apex if kind == "cone" else geometry.Center
                    axis = None if kind == "sphere" else geometry.Axis
                record.update(anchor_mm=_v(anchor), orientation=str(item.Orientation))
                if axis is not None:
                    length = math.hypot(*_v(axis))
                    record["axis"] = [x / length for x in _v(axis)]
                if kind in {"cylinder", "sphere", "circle"}:
                    record["radius_mm"] = finite(geometry.Radius)
                if kind == "cone":
                    record["semi_angle_rad"] = abs(finite(geometry.SemiAngle))
                box = item.optimalBoundingBox(False, False)
                record["trim"] = {
                    "center_mm": _v(item.CenterOfMass),
                    "bounds_mm": [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax],
                    "measure": finite(item.Area if face else item.Length),
                    "vertex_count": len(item.Vertexes),
                    "edge_count": len(item.Edges),
                }
                record["adjacency"] = (
                    sorted(_primitive_type(edge, False) for edge in item.Edges)
                    if face
                    else sorted(adjacency[index - 1])
                )
                descriptor(record)
            except Exception as error:
                record = {
                    "subelement": record["subelement"],
                    "kind": "unsupported",
                    "native_type": native_type,
                    "reason": str(error),
                }
            result.append(record)
    return result


def current_property_entries(value) -> list[dict]:
    """Observe public LinkSub values without guessing unsupported encodings."""
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and (hasattr(value[0], "Name") or isinstance(value[0], str))
    ):
        pairs = [value]
    elif isinstance(value, (list, tuple)):
        pairs = list(value)
    else:
        raise ValueError("unrecognized public reference-property representation")
    result = []
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("unrecognized public reference-property entry")
        target, selectors = pair
        name = target if isinstance(target, str) else getattr(target, "Name", None)
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("public reference target is not a local safe object name")
        if isinstance(selectors, str):
            selectors = [selectors]
        if not isinstance(selectors, (list, tuple)) or any(
            not isinstance(s, str) for s in selectors
        ):
            raise ValueError("public reference selectors are not a string sequence")
        result.extend({"target": name, "selector": selector} for selector in selectors)
    return result


def current_property_name(original: str, saved_names: set[str], runtime_names: set[str]) -> str:
    """Permit only an explicit, observed schema rename; never guess a reference."""
    if original in saved_names and original in runtime_names:
        return original
    if (
        original == "Support"
        and original not in saved_names
        and "AttachmentSupport" in saved_names
        and "AttachmentSupport" in runtime_names
    ):
        return "AttachmentSupport"
    raise ValueError("source property or explicitly saved schema alias unavailable")


def observe_native_getter(obj, selector: str, expected: dict | None, *, shape_getter=False) -> dict:
    """Record a public getter; identity matches do not prove attachment-engine use."""
    result = {
        "selector": selector,
        "method": "Shape.getElement" if shape_getter else "DocumentObject.getSubObject",
        "attachment_engine_resolution_proven": False,
    }
    try:
        if obj is None or not re.fullmatch(r"(?:Face|Edge)[1-9][0-9]*", selector):
            raise ValueError("getter requires an available provider and a supported selector")
        raw_shape = obj.Shape
        value = raw_shape.getElement(selector) if shape_getter else obj.getSubObject(selector)
        result["python_type"] = type(value).__name__
        if value is None:
            result["status"] = "returned_none"
            return result
        result["shape_type"] = getattr(value, "ShapeType", None)
        if result["shape_type"] not in {"Face", "Edge"}:
            result["status"] = "unsupported_getter_result"
            return result
        result["placement"] = list(value.Placement.toMatrix().A)
        category = "Face" if result["shape_type"] == "Face" else "Edge"
        raw_items = raw_shape.Faces if category == "Face" else raw_shape.Edges
        for method in ("isSame", "isEqual"):
            try:
                indices = [
                    f"{category}{index}"
                    for index, item in enumerate(raw_items, 1)
                    if getattr(value, method)(item)
                ]
                result[f"raw_provider_{method}_indices"] = indices
            except Exception as error:
                result[f"raw_provider_{method}_indices"] = None
                result[f"{method}_error"] = {"type": type(error).__name__, "message": str(error)}
        measured = next(d for d in native_descriptors(value) if d["subelement"] == category + "1")
        result["direct_descriptor"] = measured
        result["descriptor_neighborhood_context"] = "detached_getter_result_only"
        if expected is not None:
            result["source_descriptor_comparison"] = comparison(expected, measured)
        result["status"] = "observed_public_getter"
    except Exception as error:
        result.update(
            status="getter_unresolved", error_type=type(error).__name__, message=str(error)
        )
    return result


def load_helper(path: Path, digest: str, name: str):
    if sha(path) != digest:
        raise ValueError("retained helper bytes differ")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reject_conflicting_flags() -> None:
    if any(
        os.environ.get(key) == "1"
        for key in (
            "RAFTEL_RUN_FREECAD_AUDIT",
            "RAFTEL_RUN_THOR_ART1_PROBE",
            "RAFTEL_PREPARE_THOR_ART1_CANDIDATE",
        )
    ):
        raise ValueError("conflicting native helper flag must be unset before imports")


def contained_input_paths(root: Path) -> None:
    for name in (
        "request.json",
        "inputs/source.fcstd",
        "inputs/candidate.fcstd",
        "inputs/evidence.json",
        "scripts/audit_freecad_assembly.py",
        "scripts/thor_art1_diagnostics.py",
    ):
        if not (root / name).resolve().is_relative_to(root.resolve()):
            raise ValueError("input path escaped the isolated run")


def fixture(App, Part) -> dict:
    rows = []
    samples = [
        ("box", Part.makeBox(2, 3, 4), "Face1", "plane"),
        ("cylinder", Part.makeCylinder(2, 5), "Face1", "cylinder"),
        ("circle", Part.makeCircle(2), "Edge1", "circle"),
        ("line", Part.makeLine(App.Vector(0, 0, 0), App.Vector(2, 0, 0)), "Edge1", "line"),
    ]
    placement = App.Placement(App.Vector(4, -3, 2), App.Rotation(App.Vector(0, 1, 0), 90))
    for name, shape, selector, kind in samples:
        base = next(r for r in native_descriptors(shape) if r["subelement"] == selector)
        if base["kind"] != kind:
            raise ValueError(f"native fixture unsupported: {name}")
        placed = shape.copy()
        placed.Placement = placement
        moved = next(r for r in native_descriptors(placed) if r["subelement"] == selector)
        if moved["kind"] != kind:
            raise ValueError(f"native placed fixture unsupported: {name}")
        # Plane anchor is a parameter midpoint; the other primitive getters must
        # also include TopoDS placement exactly once.
        expected = _v(placement.multVec(App.Vector(*base["anchor_mm"])))
        error = math.dist(expected, moved["anchor_mm"])
        if error > 1e-8:
            raise ValueError(f"native primitive descriptor frame mismatch: {name}")
        axis_error = None
        if "axis" in base:
            target = _v(placement.Rotation.multVec(App.Vector(*base["axis"])))
            axis_error = math.dist(target, moved["axis"])
            if axis_error > 1e-10:
                raise ValueError(f"native primitive descriptor direction mismatch: {name}")
        rows.append({"name": name, "anchor_error_mm": error, "axis_error": axis_error})
    previous = set(App.listDocuments())
    document = App.newDocument("RAFTELSemanticGetterFixture")
    try:
        obj = document.addObject("Part::Feature", "PlacedBox")
        obj.Shape = Part.makeBox(2, 3, 4)
        obj.Placement = placement
        expected = next(d for d in native_descriptors(obj.Shape) if d["subelement"] == "Face1")
        observations = [
            observe_native_getter(obj, "Face1", expected),
            observe_native_getter(obj, "Face1", expected, shape_getter=True),
        ]
        for observation in observations:
            actual = observation.get("direct_descriptor")
            if observation["status"] != "observed_public_getter" or actual is None:
                raise ValueError("synthetic public native getter did not return a supported face")
            center_error = math.dist(expected["trim"]["center_mm"], actual["trim"]["center_mm"])
            bounds_error = max(
                abs(a - b)
                for a, b in zip(
                    expected["trim"]["bounds_mm"], actual["trim"]["bounds_mm"], strict=True
                )
            )
            direction_error = math.dist(expected["axis"], actual["axis"])
            if center_error > 1e-8 or bounds_error > 1e-8 or direction_error > 1e-10:
                raise ValueError("public native getter coordinate fixture failed")
            observation["fixture_center_error_mm"] = center_error
            observation["fixture_bounds_error_mm"] = bounds_error
            observation["fixture_direction_error"] = direction_error
        rows.append({"name": "public_document_and_shape_getters", "observations": observations})
    finally:
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
    return {
        "passed": True,
        "cases": rows,
        "source_cad_documents_opened": False,
        "synthetic_document_created": True,
        "synthetic_recompute_requested": False,
        "open_documents_after_synthetic_fixture": len(App.listDocuments()),
    }


def native_capture() -> dict:
    reject_conflicting_flags()
    if os.environ.get(FLAG) != "1":
        raise ValueError("explicit native semantic-support opt-in required")
    root = Path(os.environ["RAFTEL_SEMANTIC_SUPPORT_ROOT"]).resolve(strict=True)
    contained_input_paths(root)
    if shutil.disk_usage(root).free < 50 * 1024**3 + 512 * 1024**2:
        raise ValueError("50 GiB reserve plus descriptor scratch budget required")
    request = strict_json(root / "request.json")
    if (
        set(request)
        != {
            "schema_version",
            "evidence_class",
            "worker_sha256",
            "audit_sha256",
            "diagnostics_sha256",
            "evidence_sha256",
        }
        or type(request["schema_version"]) is not int
        or request["schema_version"] != 1
        or request["evidence_class"] != "Art1_semantic_support_read_only_request"
    ):
        raise ValueError("unsupported semantic-support request")
    if sha(Path(__file__)) != request["worker_sha256"]:
        raise ValueError("executed worker changed")
    source, candidate = root / "inputs/source.fcstd", root / "inputs/candidate.fcstd"
    if (
        max(source.stat().st_size, candidate.stat().st_size) > 32 * 1024**2
        or sha(source) != SOURCE_SHA256
        or sha(candidate) != CANDIDATE_SHA256
    ):
        raise ValueError("source or unaccepted candidate pin differs")
    evidence_path = root / "inputs/evidence.json"
    if sha(evidence_path) != request["evidence_sha256"]:
        raise ValueError("source evidence bytes changed")
    evidence = strict_json(evidence_path)
    references = authenticate_ledger(source, evidence)
    diagnostics = load_helper(
        root / "scripts/thor_art1_diagnostics.py",
        request["diagnostics_sha256"],
        "semantic_source_diagnostics",
    )
    contract = diagnostics.source_fingerprint(source, evidence)
    helper = load_helper(
        root / "scripts/audit_freecad_assembly.py",
        request["audit_sha256"],
        "semantic_audit_helpers",
    )
    writer = helper.ReportWriter(root / "probe.json")
    report = {
        "schema_version": 1,
        "evidence_class": "native_read_only_Art1_support_descriptor_audit",
        "status": "starting",
        "source_sha256": SOURCE_SHA256,
        "candidate_sha256": CANDIDATE_SHA256,
        "request_sha256": sha(root / "request.json"),
        "worker_sha256": sha(Path(__file__)),
        "comparison_policy": POLICY,
        "policy_is_not_migration_or_manufacturing_tolerance": True,
        "source_contract_canonical_sha256": canonical(contract),
        "fixture": None,
        "references": [],
        "providers": {},
        "errors": [],
        "document_saved": False,
        "source_document_opened": False,
        "recompute_requested": False,
        "support_remapped": False,
        "attachment_approved": False,
        "migration_accepted": False,
        "shape_equivalence_established": False,
        "manufacturing_release": False,
    }
    writer(report)
    import FreeCAD as App
    import Part

    previous = set(App.listDocuments())
    opened = None
    try:
        report["runtime_isolation"] = helper._runtime_isolation(App, root)
        expected_paths = {
            "UserParameter": root / "user.cfg",
            "SystemParameter": root / "system.cfg",
            "UserHomePath": root / "home",
            "UserAppData": root / "data",
            "AppTempPath": root / "temp",
        }
        if any(
            Path(App.ConfigGet(key)).resolve() != expected.resolve()
            for key, expected in expected_paths.items()
        ):
            raise ValueError("actual native path differs from its dedicated configuration")
        report["open_document_count_before"] = len(previous)
        report["freecad_version"] = list(App.Version())
        report["opencascade_version"] = Part.OCC_VERSION
        report["fixture"] = fixture(App, Part)
        writer(report)
        if previous:
            raise ValueError("fresh native console must have no preexisting documents")
        opened = App.openDocument(str(candidate), True)
        report["candidate_document_opened"] = True
        body_matrix = list(opened.getObject("Body").Placement.toMatrix().A)
        source_body_identity = True  # source_fingerprint above independently checks the XML Body.
        candidate_body_identity = (
            max(abs(a - b) for a, b in zip(body_matrix, IDENTITY, strict=True)) <= 1e-12
        )
        report["coordinate_contract"] = {
            "frame": "native_Art1_Body_identity_mm",
            "source_body_identity": source_body_identity,
            "candidate_body_identity": candidate_body_identity,
            "candidate_body_placement": body_matrix,
            "fixture_proves_getter_placement_once": True,
        }
        provider_names = sorted({r["provider"] for r in references if r["geometric_reference"]})
        source_nodes = {}
        candidate_nodes = {}
        with zipfile.ZipFile(source) as archive, zipfile.ZipFile(candidate) as candidate_archive:
            source_xml = ET.fromstring(archive.read("Document.xml"))
            candidate_xml = ET.fromstring(candidate_archive.read("Document.xml"))
            saved_types = {
                n.get("name"): n.get("type") for n in candidate_xml.findall("./Objects/Object")
            }
            report["candidate_runtime_type_inventory"] = [
                {
                    "name": obj.Name,
                    "saved_type_id": saved_types.get(obj.Name),
                    "runtime_type_id": obj.TypeId,
                    "type_matches_saved_xml": obj.TypeId == saved_types.get(obj.Name),
                    "python_wrapper_type": type(obj).__name__,
                }
                for obj in opened.Objects
            ]
            report["all_candidate_runtime_types_match_saved_xml"] = len(saved_types) == len(
                opened.Objects
            ) and all(
                item["type_matches_saved_xml"]
                for item in report["candidate_runtime_type_inventory"]
            )
            source_nodes = {n.get("name"): n for n in source_xml.findall("./ObjectData/Object")}
            candidate_nodes = {
                n.get("name"): n for n in candidate_xml.findall("./ObjectData/Object")
            }
            saved_dir = root / "saved-provider-breps"
            saved_dir.mkdir(exist_ok=False)
            for name in provider_names:
                node = source_nodes[name]
                part = node.find('./Properties/Property[@name="Shape"]/Part')
                if part is None:
                    report["providers"][name] = {"status": "source_cached_shape_missing"}
                    continue
                entry = part.get("file")
                if not isinstance(entry, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.brp", entry):
                    raise ValueError("unsafe saved provider BRep member")
                data = archive.read(entry)
                path = saved_dir / (name + ".brep")
                with path.open("xb") as stream:
                    stream.write(data)
                raw = Part.Shape()
                raw.read(str(path))
                obj = opened.getObject(name)
                item = {
                    "source_brep_entry": entry,
                    "source_brep_sha256": hashlib.sha256(data).hexdigest(),
                    "source_shape_placement": list(raw.Placement.toMatrix().A),
                    "source_xml_placement_mm_xyzw": diagnostics._placement(node),
                    "candidate_own_states": None if obj is None else list(obj.State),
                    "source_descriptors": native_descriptors(raw),
                    "candidate_descriptors": [],
                    "status": "captured_cached_providers",
                    "fresh_history_validated": False,
                }
                xml_placement = item["source_xml_placement_mm_xyzw"]
                expected_source = App.Placement(
                    App.Vector(*xml_placement[:3]), App.Rotation(*xml_placement[3:])
                )
                item["source_shape_vs_xml_placement_error"] = placement_error(
                    item["source_shape_placement"], list(expected_source.toMatrix().A)
                )
                if obj is not None and hasattr(obj, "Shape"):
                    item["candidate_shape_placement"] = list(obj.Shape.Placement.toMatrix().A)
                    item["candidate_object_placement"] = list(obj.Placement.toMatrix().A)
                    item["candidate_descriptors"] = native_descriptors(obj.Shape)
                    item["candidate_shape_vs_object_placement_error"] = placement_error(
                        item["candidate_shape_placement"], item["candidate_object_placement"]
                    )
                else:
                    item["status"] = "candidate_provider_missing_shape"
                item["provider_coordinate_trace_verified"] = (
                    item["source_shape_vs_xml_placement_error"] <= 1e-10
                    and item.get("candidate_shape_vs_object_placement_error", math.inf) <= 1e-10
                )
                report["providers"][name] = item
                writer(report)
        for ref in references:
            row = dict(ref)
            source_owner, candidate_owner = (
                source_nodes.get(ref["owner"]),
                candidate_nodes.get(ref["owner"]),
            )
            changed = []
            for key in (
                "Support",
                "ExternalGeometry",
                "MirrorPlane",
                "MapMode",
                "AttachmentOffset",
                "ExpressionEngine",
            ):
                a = None if source_owner is None else diagnostics._property(source_owner, key)
                b = None if candidate_owner is None else diagnostics._property(candidate_owner, key)
                if (None if a is None else diagnostics._xml_value(a)) != (
                    None if b is None else diagnostics._xml_value(b)
                ):
                    changed.append(key)
            row["consumer_saved_property_changes"] = changed
            row["attachment_approved"] = False
            provider = report["providers"].get(ref["provider"], {})
            expected = next(
                (
                    d
                    for d in provider.get("source_descriptors", [])
                    if d["subelement"] == ref["original_selector"]
                ),
                None,
            )
            if not ref["geometric_reference"]:
                row.update(status="unsupported_whole_datum_or_sketch_axis", selected=None)
            elif not candidate_body_identity:
                row.update(status="unknown_common_frame", selected=None)
            elif not provider.get("provider_coordinate_trace_verified"):
                row.update(status="provider_coordinate_trace_unresolved", selected=None)
            elif expected is None:
                row.update(status="source_selector_missing", selected=None)
            else:
                candidates = [
                    d
                    for d in provider["candidate_descriptors"]
                    if d["subelement"].startswith(
                        "Face" if ref["original_selector"].startswith("Face") else "Edge"
                    )
                ]
                row["source_descriptor"] = expected
                row.update(match_reference(expected, candidates, ref["original_selector"]))
            if ref["geometric_reference"]:
                obj = opened.getObject(ref["provider"])
                row["public_getter_observations"] = {
                    "original_selector_document_getter": observe_native_getter(
                        obj, ref["original_selector"], expected
                    ),
                    "original_selector_shape_getter": observe_native_getter(
                        obj, ref["original_selector"], expected, shape_getter=True
                    ),
                }
                owner = opened.getObject(ref["owner"])
                try:
                    if not report["all_candidate_runtime_types_match_saved_xml"]:
                        raise ValueError("candidate runtime type inventory differs from saved XML")
                    saved_property_names = (
                        set()
                        if candidate_owner is None
                        else {
                            p.get("name") for p in candidate_owner.findall("./Properties/Property")
                        }
                    )
                    property_name = current_property_name(
                        ref["property"], saved_property_names, set(owner.PropertiesList)
                    )
                    entries = current_property_entries(getattr(owner, property_name))
                    position = sum(
                        earlier["owner"] == ref["owner"] and earlier["property"] == ref["property"]
                        for earlier in report["references"]
                    )
                    observation = {
                        "status": "observed_public_property",
                        "source_property_name": ref["property"],
                        "current_property_name": property_name,
                        "runtime_owner_type_id": owner.TypeId,
                        "saved_owner_type_id": saved_types.get(ref["owner"]),
                        "schema_alias_is_not_attachment_engine_proof": True,
                        "entries": entries,
                        "source_property_occurrence_ordinal": position,
                        "ordinal_is_not_semantic_correspondence_proof": True,
                    }
                    if position < len(entries):
                        entry = entries[position]
                        observation["same_ordinal_entry"] = entry
                        observation["same_ordinal_target_getter"] = observe_native_getter(
                            opened.getObject(entry["target"]), entry["selector"], expected
                        )
                    row["current_owner_property_observation"] = observation
                except Exception as error:
                    row["current_owner_property_observation"] = {
                        "status": "unsupported_public_property",
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                row["attachment_engine_resolution_proven"] = False
            report["references"].append(row)
        report["census"] = {
            "owner_objects": 53,
            "references": len(references),
            "face_edge_references": 69,
            "whole_datum_or_axis_references": 11,
            "providers": len(provider_names),
        }
        report["result_counts"] = dict(Counter(row["status"] for row in report["references"]))
        report["final_object_states"] = {obj.Name: list(obj.State) for obj in opened.Objects}
        report["status"] = "complete_descriptor_diagnostic_not_migration"
    except Exception as error:
        report["status"] = "failed_semantic_descriptor_diagnostic"
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
        report["open_document_count_after"] = len(App.listDocuments())
        report["preexisting_documents_preserved"] = set(App.listDocuments()) == previous
        report["source_copy_unchanged"] = sha(source) == SOURCE_SHA256
        report["candidate_copy_unchanged"] = sha(candidate) == CANDIDATE_SHA256
        report["worker_unchanged"] = sha(Path(__file__)) == request["worker_sha256"]
        writer(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = authenticate_ledger(args.source, strict_json(args.evidence))
    output = {
        "schema_version": 1,
        "evidence_class": "host_Art1_support_reference_census_only",
        "references": rows,
        "native_capture_executed": False,
        "migration_accepted": False,
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(output, indent=2, allow_nan=False) + "\n")


if os.environ.get(FLAG) == "1":
    native_capture()
elif __name__ == "__main__":
    main()
