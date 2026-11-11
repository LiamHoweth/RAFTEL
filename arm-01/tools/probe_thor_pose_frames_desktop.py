"""Limited native pose/axis checks on a copied compatible Thor assembly.

There are no saved joint-angle variables. This worker applies explicitly
declared in-memory rotations to existing Assembly4 AttachmentOffsets, evaluates
their existing placement expressions, and observes native link geometry.
No file is saved; q5/q6, contact, TCP and physical calibration are excluded.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
import os
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

FLAG = "RAFTEL_RUN_THOR_POSE_FRAMES"
CAD_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
ROS_REVISION = "e11a56b5aa0d89f0b68a3ea7bd084eab4a050952"
XACRO_SHA256 = "19b83e26f86aae15fda5c21418f768d0e3ed1b0d1daa6d149abd9b45ceccd8b9"
STATIC_ART1_SHA256 = "142d754d3551352ffd2338d940cc3edecb9d272b2401f70aea9f89fea164c140"
NATIVE_TO_ROS = ((0, 1, 0), (-1, 0, 0), (0, 0, 1))
LINKS = (
    "AssemblyBase",
    "AssemblyArt1",
    "AssemblyArt2",
    "AssemblyArt3",
    "AssemblyArt4",
    "AssemblyArt56",
)
ACTUATION = (
    ("AssemblyArt1", "AssemblyBase", "LCS_Art1003", (0, 0, 1)),
    ("AssemblyArt2", "AssemblyArt1", "LCS_Art2002", (0, 0, 1)),
    ("AssemblyArt3", "AssemblyArt2", "LCS_Model_1", (0, 1, 0)),
    ("AssemblyArt4", "AssemblyArt3", "LCS_Art4Fix", (0, 0, 1)),
)
POSES = (
    ("saved_zero", (0, 0, 0, 0, 0, 0)),
    ("base_rotation", (0.3, 0, 0, 0, 0, 0)),
    ("shoulder_rotation", (0, 0.25, 0, 0, 0, 0)),
    ("mixed_proximal", (0.2, -0.3, 0.25, 0.4, 0, 0)),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("expected finite real numeric input")
    return float(value)


def _vector(value, length=3):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f"expected {length} finite components")
    return [_finite(item) for item in value]


def _matrix(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("expected a finite 4x4 pose matrix")
    matrix = [_vector(row, 4) for row in value]
    if matrix[3] != [0, 0, 0, 1]:
        raise ValueError("invalid homogeneous last row")
    rotation = [row[:3] for row in matrix[:3]]
    if (
        any(
            abs(math.fsum(rotation[i][k] * rotation[j][k] for k in range(3)) - float(i == j)) > 1e-8
            for i in range(3)
            for j in range(3)
        )
        or abs(_dot(rotation[0], _cross(rotation[1], rotation[2])) - 1) > 1e-8
    ):
        raise ValueError("pose rotation must be proper orthonormal")
    return matrix


def _norm(value):
    return math.hypot(*value)


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b, strict=True))


def _unit(value):
    vector = _vector(value)
    length = _norm(vector)
    if length <= 0:
        raise ValueError("axis direction cannot be zero")
    return [item / length for item in vector]


def native_vector_to_ros(value):
    x, y, z = _vector(value)
    return [y, -x, z]


def native_pose_mm_to_ros_m(value):
    native = _matrix(value)
    return [
        [
            math.fsum(NATIVE_TO_ROS[i][k] * native[k][j] for k in range(3))
            * (1e-3 if j == 3 else 1)
            for j in range(4)
        ]
        for i in range(3)
    ] + [[0, 0, 0, 1]]


def pose_residual(actual, expected):
    a, b = _matrix(actual), _matrix(expected)
    relative = [
        [math.fsum(b[k][i] * a[k][j] for k in range(3)) for j in range(3)] for i in range(3)
    ]
    sine = (
        _norm(
            [
                relative[2][1] - relative[1][2],
                relative[0][2] - relative[2][0],
                relative[1][0] - relative[0][1],
            ]
        )
        / 2
    )
    cosine = (math.fsum(relative[i][i] for i in range(3)) - 1) / 2
    return {
        "position_error_m": _norm([a[i][3] - b[i][3] for i in range(3)]),
        "orientation_error_rad": abs(math.atan2(sine, cosine)),
        "maximum_rotation_element_error": max(
            abs(a[i][j] - b[i][j]) for i in range(3) for j in range(3)
        ),
    }


def axis_residual(point_m, axis, expected_point_m, expected_axis):
    point, reference = _vector(point_m), _vector(expected_point_m)
    a, b = _unit(axis), _unit(expected_axis)
    return {
        "point_to_expected_axis_line_m": _norm(
            _cross([point[i] - reference[i] for i in range(3)], b)
        ),
        "unsigned_direction_error": min(
            _norm([a[i] - b[i] for i in range(3)]), _norm([a[i] + b[i] for i in range(3)])
        ),
        "signed_axis_dot_for_diagnostics": _dot(a, b),
    }


def _xml(source):
    with zipfile.ZipFile(source) as archive:
        return ET.fromstring(archive.read("Document.xml"))


def _object(tree, name):
    matches = [obj for obj in tree.findall("./ObjectData/Object") if obj.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"missing or ambiguous source object {name}")
    return matches[0]


def _placement_xml(obj, name):
    node = obj.find(f'./Properties/Property[@name="{name}"]/PropertyPlacement')
    if node is None:
        raise ValueError(f"missing source {name}")
    return {
        "position_mm": [float(node.get(key)) for key in ("Px", "Py", "Pz")],
        "quaternion_xyzw": [float(node.get(key)) for key in ("Q0", "Q1", "Q2", "Q3")],
    }


def source_bindings(source_root: Path, baseline: dict) -> dict:
    expected = {Path(row["path"]).name: row["sha256"] for row in baseline["files"]}
    files = {path.name: path for path in source_root.iterdir() if path.is_file()}
    if len(expected) != 57 or set(files) != set(expected):
        raise ValueError("compatible copied source must contain the declared 57 native files")
    actual = {name: sha(path) for name, path in files.items()}
    expected["Art1Body.fcstd"] = STATIC_ART1_SHA256
    if actual != expected:
        raise ValueError(
            "compatible source differs from static Art1 wrapper plus 56 pinned originals"
        )
    master = _xml(source_root / "Assembly.FCStd")
    variables = _object(master, "Variables")
    variable_names = [
        prop.get("name")
        for prop in variables.findall("./Properties/Property")
        if prop.get("name") not in {"ExpressionEngine", "Label", "Label2", "Proxy", "Visibility"}
    ]
    if variable_names:
        raise ValueError(
            "saved master unexpectedly contains angle variables; inspect before driving"
        )
    bindings = []
    for link_name, parent, datum, axis in ACTUATION:
        obj = _object(master, link_name)
        expressions = [
            [node.get("path"), node.get("expression")]
            for node in obj.findall(
                './Properties/Property[@name="ExpressionEngine"]/ExpressionEngine/Expression'
            )
        ]
        if (
            len(expressions) != 1
            or expressions[0][0] != "Placement"
            or "AttachmentOffset" not in expressions[0][1]
        ):
            raise ValueError("saved link lacks the expected source Placement expression")
        parent_tree = _xml(source_root / (parent + ".FCStd"))
        bindings.append(
            {
                "link": link_name,
                "parent_link": parent,
                "parent_datum": datum,
                "local_right_increment_axis": list(axis),
                "saved_expression_engine": expressions,
                "saved_attachment_offset": _placement_xml(obj, "AttachmentOffset"),
                "saved_parent_datum": _placement_xml(_object(parent_tree, datum), "Placement"),
            }
        )
    return {
        "source_sha256": actual,
        "source_file_count": len(actual),
        "static_art1_is_unrepaired_history_replacement": True,
        "empty_saved_variables_custom_properties": variable_names,
        "actuation_bindings": bindings,
    }


def prepare_contract(source_root: Path, project_root: Path, xacro: Path) -> dict:
    """Host-side immutable request; native worker never recreates the ROS chain."""
    from raftel_arm01.kinematics import thor_model

    if sha(xacro) != XACRO_SHA256:
        raise ValueError("nominal source Xacro byte pin differs")
    source_xml = ET.fromstring(xacro.read_text(encoding="utf-8"))
    joint6 = source_xml.find('./joint[@name="joint_6"]')
    fixed_z = float(joint6.find("origin").get("xyz").split()[2])
    if fixed_z != thor_model.JOINT_Z_OFFSETS_M[5] or fixed_z != 0.0135:
        raise ValueError("source joint6 fixed translation differs; no fitted fold offset allowed")
    baseline_path = project_root / "hardware/cad/thor-baseline-inspection.json"
    axes_path = project_root / "hardware/cad/thor-axis-evidence.json"
    source = source_bindings(source_root, json.loads(baseline_path.read_text(encoding="utf-8")))
    axes = json.loads(axes_path.read_text(encoding="utf-8"))
    poses = []
    for name, q in POSES:
        frames, target = thor_model.chain(q)
        # FK link6 * TransZ(-d6): source-defined fold frame with q5=q6=0.
        expected = [list(row) for row in target]
        for i in range(3):
            expected[i][3] -= expected[i][2] * fixed_z
        poses.append(
            {
                "name": name,
                "joint_angles_rad": list(q),
                "expected_fold_frame_base_link_m": expected,
                "expected_joint_axes": [
                    {
                        "name": frame.name,
                        "origin_m": list(frame.origin_m),
                        "axis_unit": list(frame.axis_unit),
                    }
                    for frame in frames
                ],
            }
        )
    return {
        "schema_version": 1,
        "evidence_class": "limited_existing_native_assembly_pose_request",
        "cad_upstream_revision": CAD_REVISION,
        "ros_revision": ROS_REVISION,
        "source_contract": source,
        "source_xacro_sha256": XACRO_SHA256,
        "host_nominal_module_sha256": sha(Path(thor_model.__file__)),
        "baseline_inspection_sha256": sha(baseline_path),
        "zero_axis_evidence_sha256": sha(axes_path),
        "axis_selections": axes["joint_axes"],
        "fold_source_joint6_translation_m": fixed_z,
        "poses": poses,
        "q5_q6_fixed_zero": True,
        "physical_calibration_or_TCP_validation": False,
    }


def validate_contract(contract):
    if (
        not isinstance(contract, dict)
        or type(contract.get("schema_version")) is not int
        or contract["schema_version"] != 1
    ):
        raise ValueError("unsupported pose-frame contract")
    if contract.get("evidence_class") != "limited_existing_native_assembly_pose_request":
        raise ValueError("pose-frame scope differs")
    if (
        contract.get("cad_upstream_revision") != CAD_REVISION
        or contract.get("ros_revision") != ROS_REVISION
        or contract.get("source_xacro_sha256") != XACRO_SHA256
        or contract.get("fold_source_joint6_translation_m") != 0.0135
    ):
        raise ValueError("source revisions, Xacro pin or source-derived fold offset differs")
    source = contract.get("source_contract", {})
    pins = source.get("source_sha256", {})
    if not isinstance(pins, dict) or len(pins) != 57 or source.get("source_file_count") != 57:
        raise ValueError("pose request must bind all 57 compatible source files")
    if source.get("empty_saved_variables_custom_properties") != []:
        raise ValueError("saved source Variables contract differs")
    if (
        contract.get("source_contract", {}).get("source_sha256", {}).get("Art1Body.fcstd")
        != STATIC_ART1_SHA256
    ):
        raise ValueError("pose request must retain the accepted static Art1 analysis wrapper")
    poses = contract.get("poses")
    if not isinstance(poses, list) or len(poses) != len(POSES):
        raise ValueError("require zero baseline and exactly three bounded nonzero cases")
    for row, (name, expected_q) in zip(poses, POSES, strict=True):
        q = _vector(row.get("joint_angles_rad"), 6)
        if row.get("name") != name or q != list(expected_q) or q[4:] != [0, 0]:
            raise ValueError("pose names/angles must match the declared limited experiment")
        _matrix(row["expected_fold_frame_base_link_m"])
        if len(row.get("expected_joint_axes", [])) != 6:
            raise ValueError("pose requires six source axis references")
    if (
        contract.get("q5_q6_fixed_zero") is not True
        or contract.get("physical_calibration_or_TCP_validation") is not False
    ):
        raise ValueError("limited pose experiment cannot declare physical/TCP validation")
    json.dumps(contract, allow_nan=False)
    return contract


def _load_helper(path, expected_sha):
    if sha(path) != expected_sha:
        raise ValueError("retained audit helper byte pin differs")
    if os.environ.get("RAFTEL_RUN_FREECAD_AUDIT") == "1":
        raise ValueError("generic audit entry flag must not execute inside pose worker")
    spec = importlib.util.spec_from_file_location("retained_pose_audit_helper", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def _state_records(App):
    result = []
    for name, document in sorted(App.listDocuments().items()):
        result.append(
            {
                "document": name,
                "objects": [
                    {"name": obj.Name, "type": obj.TypeId, "state": list(obj.State)}
                    for obj in document.Objects
                ],
            }
        )
    return result


def _summary(states):
    rows = [{"document": doc["document"], **row} for doc in states for row in doc["objects"]]
    return {
        "documents": len(states),
        "objects": len(rows),
        "non_up_to_date": [row for row in rows if row["state"] != ["Up-to-date"]],
        "invalid_or_error": [
            row
            for row in rows
            if any("Invalid" in item or "Error" in item for item in row["state"])
        ],
    }


def close_created_documents(app, prior_names):
    """Never close documents that caused a fresh-process guard to reject."""
    for name in set(app.listDocuments()) - set(prior_names):
        app.closeDocument(name)
    return set(app.listDocuments())


def native_capture():
    if os.environ.get(FLAG) != "1":
        raise ValueError("pose-frame native worker requires explicit opt-in")
    run = Path(os.environ["RAFTEL_POSE_RUN_DIR"]).resolve(strict=True)
    envelope_path = Path(os.environ["RAFTEL_POSE_ENVELOPE"]).resolve(strict=True)
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    source_root = Path(envelope["copied_source_root"]).resolve(strict=True)
    output = Path(envelope["report_path"]).resolve()
    request_path = Path(envelope["request_path"]).resolve(strict=True)
    if (
        any(
            not path.is_relative_to(run)
            for path in (source_root, output, request_path, envelope_path)
        )
        or output.exists()
    ):
        raise ValueError("pose inputs/copy/new report must stay inside the fresh isolated run")
    if (
        sha(request_path) != envelope["request_sha256"]
        or sha(Path(__file__)) != envelope["worker_sha256"]
    ):
        raise ValueError("pose request or worker snapshot changed")
    if shutil.disk_usage(run).free < 50 * 1024**3 + 128 * 1024**2:
        raise ValueError("pose capture needs 50 GiB reserve plus scratch budget")
    request = validate_contract(json.loads(request_path.read_text(encoding="utf-8")))
    hashes = {name: sha(source_root / name) for name in request["source_contract"]["source_sha256"]}
    if hashes != request["source_contract"]["source_sha256"]:
        raise ValueError("copied compatible source bytes differ from request")
    helper = _load_helper(Path(envelope["audit_helper_path"]), envelope["audit_helper_sha256"])
    writer = helper.ReportWriter(output)
    report = {
        "schema_version": 1,
        "evidence_class": "limited_native_existing_assembly_offsets_not_calibration_or_full_FK",
        "status": "starting",
        "request": request,
        "request_sha256": sha(request_path),
        "capture_script_sha256": sha(Path(__file__)),
        "audit_helper_sha256": envelope["audit_helper_sha256"],
        "source_copy_sha256_before": hashes,
        "copied_source_files": len(hashes),
        "cad_documents_saved": False,
        "forced_feature_history_rebuild": False,
        "explicit_external_document_recompute_requested": False,
        "new_joint_variables_created": False,
        "q5_q6_fixed_zero": True,
        "physical_sign_zero_limit_contact_or_TCP_calibration": False,
        "poses": [],
        "errors": [],
    }
    writer(report)
    App = None
    prior_document_names = None
    try:
        import FreeCAD as App

        prior_document_names = set(App.listDocuments())
        report["open_document_count_before"] = len(prior_document_names)
        report["runtime_isolation"] = helper._runtime_isolation(App, run)
        import Part

        expected = envelope["expected_runtime_paths"]
        if any(
            Path(App.ConfigGet(key)).resolve() != Path(value).resolve()
            for key, value in expected.items()
        ):
            raise ValueError("actual runtime paths differ from requested dedicated paths")
        report["expected_runtime_paths"] = expected
        report.update(
            freecad_version=list(App.Version()),
            python_version=sys.version,
            opencascade_version=getattr(Part, "OCC_VERSION", None),
        )
        report["modules"] = {}
        for name, pin in envelope["module_pins"].items():
            module = importlib.import_module(name)
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(Path(pin["root"]).resolve()) or sha(path) != pin["sha256"]:
                raise ValueError(f"native module origin/pin differs: {name}")
            report["modules"][name] = {
                "path": str(path),
                "sha256": sha(path),
                "origin_verified": True,
            }
        report["stage"] = "opening_compatible_assembly"
        writer(report)
        master = App.openDocument(str(source_root / "Assembly.FCStd"), True)
        report["loaded_state_before"] = _summary(_state_records(App))
        if report["loaded_state_before"]["invalid_or_error"]:
            raise ValueError("restored assembly contains invalid/error states")
        for doc_name in LINKS:
            doc = (
                App.getDocument(doc_name)
                if doc_name != "AssemblyBase"
                else App.getDocument("AssemblyBase")
            )
            model = doc.getObject("Model")
            values = helper._placement(model.Placement)["matrix"]
            if max(abs(values[i][j] - float(i == j)) for i in range(4) for j in range(4)) > 1e-9:
                raise ValueError(
                    f"nonidentity source Model ancestor needs separate frame handling: {doc_name}"
                )
        main_model = helper._placement(master.getObject("Model").Placement)["matrix"]
        if max(abs(main_model[i][j] - float(i == j)) for i in range(4) for j in range(4)) > 1e-9:
            raise ValueError("nonidentity master Model parent needs explicit handling")
        original = {
            name: App.Placement(master.getObject(name).AttachmentOffset)
            for name, _, _, _ in ACTUATION
        }
        expressions = {
            name: [list(item) for item in master.getObject(name).ExpressionEngine]
            for name in original
        }
        for binding in request["source_contract"]["actuation_bindings"]:
            name = binding["link"]
            if expressions[name] != binding["saved_expression_engine"]:
                raise ValueError("runtime Placement expression differs from pinned XML")
            saved = binding["saved_attachment_offset"]
            expected_offset = App.Placement(
                App.Vector(*saved["position_mm"]), App.Rotation(*saved["quaternion_xyzw"])
            )
            actual_matrix = helper._placement(original[name])["matrix"]
            expected_matrix = helper._placement(expected_offset)["matrix"]
            if (
                max(
                    abs(actual_matrix[i][j] - expected_matrix[i][j])
                    for i in range(4)
                    for j in range(4)
                )
                > 1e-8
            ):
                raise ValueError("runtime AttachmentOffset differs from pinned XML")
        report["original_offset_and_expression_readback"] = {
            name: {"offset": helper._placement(value), "expressions": expressions[name]}
            for name, value in original.items()
        }
        report["zero_increment_axis_mapping"] = []
        for i, (name, parent, datum, axis) in enumerate(ACTUATION):
            prefix = (
                master.getObject(parent)
                .Placement.multiply(App.getDocument(parent).getObject(datum).Placement)
                .multiply(original[name])
            )
            direction = list(prefix.Rotation.multVec(App.Vector(*axis)))
            ref = request["axis_selections"][i]
            expected_axis = ref["nominal_axis_direction_in_native_frame"]
            residual = axis_residual(
                [x * 1e-3 for x in prefix.Base],
                direction,
                ref["nominal_axis_point_in_native_frame_m"],
                expected_axis,
            )
            if (
                residual["point_to_expected_axis_line_m"] > 1e-8
                or _dot(_unit(direction), _unit(expected_axis)) < 1 - 1e-8
            ):
                raise ValueError(f"source-derived local increment mapping differs: {name}")
            report["zero_increment_axis_mapping"].append(
                {
                    "link": name,
                    "prefix_frame_mm": helper._placement(prefix),
                    "local_axis": list(axis),
                    "observed_native_axis": direction,
                    "residual": residual,
                }
            )
        marker_zero = marker_frame_zero = marker_vertex_count = None
        for pose in request["poses"]:
            report["stage"] = "applying_in_memory_offsets_" + pose["name"]
            writer(report)
            q = pose["joint_angles_rad"]
            for i, (name, _, _, axis) in enumerate(ACTUATION):
                delta = App.Placement(
                    App.Vector(0, 0, 0), App.Rotation(App.Vector(*axis), math.degrees(q[i]))
                )
                master.getObject(name).AttachmentOffset = original[name].multiply(delta)
            recomputed = master.recompute()
            fold_placement = master.getObject("AssemblyArt56").Placement
            fold = native_pose_mm_to_ros_m(helper._placement(fold_placement)["matrix"])
            fold_error = pose_residual(fold, pose["expected_fold_frame_base_link_m"])
            observed = []
            for selection, expected_axis in zip(
                request["axis_selections"], pose["expected_joint_axes"], strict=True
            ):
                doc_name, object_name = selection["native_object"].split("::")
                obj = App.getDocument(doc_name).getObject(object_name)
                face = obj.Shape.Faces[selection["native_face_index"] - 1]
                surface = face.Surface
                if type(surface).__name__ != "Cylinder" or not math.isclose(
                    surface.Radius, selection["cylinder_radius_mm"], abs_tol=1e-8, rel_tol=0
                ):
                    raise ValueError("selected cached cylindrical face changed identity")
                ancestor = master.getObject(doc_name).Placement
                native_point = list(ancestor.multVec(surface.Center))
                native_axis = list(ancestor.Rotation.multVec(surface.Axis))
                point = native_vector_to_ros([x * 1e-3 for x in native_point])
                direction = native_vector_to_ros(native_axis)
                observed.append(
                    {
                        "joint": selection["joint"],
                        "native_object": selection["native_object"],
                        "face_index": selection["native_face_index"],
                        "radius_mm": surface.Radius,
                        "native_point_mm": native_point,
                        "native_direction": native_axis,
                        "point_base_link_m": point,
                        "direction_base_link": direction,
                        "residual": axis_residual(
                            point, direction, expected_axis["origin_m"], expected_axis["axis_unit"]
                        ),
                    }
                )
            shape = master.getObject("AssemblyArt56").Shape
            vertices = shape.Vertexes
            marker = list(vertices[0].Point)
            if marker_zero is None:
                marker_zero = marker
                marker_frame_zero = App.Placement(fold_placement)
                marker_vertex_count = len(vertices)
            predicted = list(
                fold_placement.multiply(marker_frame_zero.inverse()).multVec(
                    App.Vector(*marker_zero)
                )
            )
            marker_error = _norm([marker[i] - predicted[i] for i in range(3)])
            readback = {
                name: {
                    "offset": helper._placement(master.getObject(name).AttachmentOffset),
                    "expressions": [list(item) for item in master.getObject(name).ExpressionEngine],
                    "state": list(master.getObject(name).State),
                }
                for name in original
            }
            expression_preserved = all(
                readback[name]["expressions"] == expressions[name] for name in original
            )
            state = _summary(_state_records(App))
            passed = (
                fold_error["position_error_m"] <= 1e-8
                and fold_error["orientation_error_rad"] <= 1e-8
                and all(
                    row["residual"]["point_to_expected_axis_line_m"] <= 1e-8
                    and row["residual"]["unsigned_direction_error"] <= 1e-8
                    for row in observed
                )
                and marker_error <= 1e-5
                and len(vertices) == marker_vertex_count
                and expression_preserved
                and not state["invalid_or_error"]
            )
            report["poses"].append(
                {
                    "name": pose["name"],
                    "joint_angles_rad": q,
                    "master_recompute_return": recomputed,
                    "offset_and_expression_readback": readback,
                    "expressions_preserved": expression_preserved,
                    "observed_fold_frame_base_link_m": fold,
                    "fold_frame_residual": fold_error,
                    "observed_axes": observed,
                    "link_shape_marker": {
                        "raw_shape_first_vertex_mm": marker,
                        "expected_from_observed_parent_delta_mm": predicted,
                        "error_mm": marker_error,
                        "vertex_count": len(vertices),
                        "own_shape_placement_not_applied_twice": True,
                    },
                    "descendant_state_summary": state,
                    "limited_pose_checks_passed": passed,
                }
            )
            writer(report)
            if not passed:
                raise ValueError(
                    "limited native pose/line/refresh comparison failed; "
                    "inspect retained observations"
                )
        for name, placement in original.items():
            master.getObject(name).AttachmentOffset = placement
        master.recompute()
        report["saved_offset_reset_maximum_matrix_error"] = max(
            abs(
                helper._placement(master.getObject(name).AttachmentOffset)["matrix"][i][j]
                - helper._placement(value)["matrix"][i][j]
            )
            for name, value in original.items()
            for i in range(4)
            for j in range(4)
        )
        report["saved_offsets_restored_in_memory"] = (
            report["saved_offset_reset_maximum_matrix_error"] < 1e-9
        )
        if not report["saved_offsets_restored_in_memory"]:
            raise ValueError("saved offsets did not reset before document close")
        report["final_loaded_document_states"] = _state_records(App)
        report["final_state_summary"] = _summary(report["final_loaded_document_states"])
        report["status"] = "complete_limited_native_pose_frames"
    except Exception as error:
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
        report["status"] = "failed_limited_native_pose_capture"
    finally:
        if App is not None and prior_document_names is not None:
            remaining_documents = close_created_documents(App, prior_document_names)
            report["open_document_count_after_close"] = len(App.listDocuments())
            report["preexisting_documents_preserved"] = remaining_documents == prior_document_names
        elif App is not None:
            report["cleanup_skipped_unknown_initial_document_state"] = True
            report["preexisting_documents_preserved"] = None
        report["source_copy_sha256_after"] = {name: sha(source_root / name) for name in hashes}
        report["source_copy_bytes_unchanged"] = report["source_copy_sha256_after"] == hashes
        if (
            not report["source_copy_bytes_unchanged"]
            or report.get("preexisting_documents_preserved", True) is not True
        ):
            report["status"] = "failed_preservation_or_close_guard"
        writer(report)
    print("RAFTEL_NATIVE_POSE_FRAME_RESULT", report["status"])
    return report


if __name__ == "__main__" or os.environ.get(FLAG) == "1":
    native_capture()
