"""Copied native wrist offset/marker experiment; no native launch on import.

Existing AppLink offset expressions drive the copied bodies. Actual raw shape
vertices supply marker frames; nominal FK is never assigned to a target frame.
The imposed fold/roll is a mathematical operation, not a solved differential.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

FLAG = "RAFTEL_RUN_THOR_WRIST_FRAMES"
POSES = (("saved_zero", 0.0, 0.0), ("fold_roll", 0.2, 0.15), ("saved_return", 0.0, 0.0))
BODY_NAMES = (
    "Art56GearPlate_Art56GearPlate",
    "GripperBot_GripperBot",
    "Art56MotorCoverRing_Art56MotorCoverRing",
    "AssemblyArt4",
)
PATH_KEYS = {"UserParameter", "SystemParameter", "UserHomePath", "UserAppData", "AppTempPath"}


def read_json(path):
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("native JSON exceeds 1 MiB bound")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate native JSON key")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("nonfinite native JSON value: " + value)

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject)

    def bound(item, depth=0):
        if depth > 32:
            raise ValueError("native JSON nesting bound exceeded")
        if isinstance(item, (dict, list)):
            if len(item) > 10000:
                raise ValueError("native JSON container bound exceeded")
            for child in item.values() if isinstance(item, dict) else item:
                bound(child, depth + 1)
        elif isinstance(item, float) and not math.isfinite(item):
            raise ValueError("nonfinite native JSON number")

    bound(value)
    return value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("expected finite real marker coordinate")
    return float(value)


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("expected three marker coordinates")
    return [_finite(x) for x in value]


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def marker_frame(points):
    """Recover an oriented frame from three real noncollinear shape vertices."""
    if not isinstance(points, (list, tuple)) or len(points) != 3:
        raise ValueError("exactly three marker points required")
    p, q, r = [_point(v) for v in points]
    x = _sub(q, p)
    z = _cross(x, _sub(r, p))
    if math.hypot(*x) <= 1e-6 or math.hypot(*z) <= 1e-6:
        raise ValueError("native marker points must be distinct and noncollinear")
    x = [v / math.hypot(*x) for v in x]
    z = [v / math.hypot(*z) for v in z]
    y = _cross(z, x)
    return [[x[i], y[i], z[i], p[i]] for i in range(3)] + [[0, 0, 0, 1]]


def select_marker_indices(points):
    """Select spread vertices deterministically; indices remain fixed across poses."""
    values = [_point(p) for p in points]
    if len(values) < 3:
        raise ValueError("shape has fewer than three vertices")
    second = max(range(1, len(values)), key=lambda i: math.hypot(*_sub(values[i], values[0])))
    baseline = _sub(values[second], values[0])
    third = max(
        range(len(values)),
        key=lambda i: math.hypot(*_cross(baseline, _sub(values[i], values[0]))),
    )
    chosen = [0, second, third]
    marker_frame([values[i] for i in chosen])
    return chosen


def _load(path, pin, name):
    path = Path(path)
    if sha(path) != pin:
        raise ValueError("retained helper snapshot pin differs: " + name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_envelope(envelope, run, worker_path):
    """Fail before importing FreeCAD or touching any CAD input."""
    run = Path(run).resolve(strict=True)
    if not isinstance(envelope, dict):
        raise ValueError("native envelope must be a mapping")
    expected_keys = {
        "copied_source_root",
        "report_path",
        "request_path",
        "audit_helper_path",
        "pose_helper_path",
        "contract_helper_path",
        "worker_sha256",
        "request_sha256",
        "audit_helper_sha256",
        "pose_helper_sha256",
        "contract_helper_sha256",
        "expected_runtime_paths",
        "module_pins",
    }
    if set(envelope) != expected_keys:
        raise ValueError("native envelope fields differ from exact schema")
    for key in expected_keys:
        if key.endswith("sha256") and not re.fullmatch("[0-9a-f]{64}", str(envelope[key])):
            raise ValueError("invalid native SHA256 pin")
    keys = (
        "copied_source_root",
        "report_path",
        "request_path",
        "audit_helper_path",
        "pose_helper_path",
        "contract_helper_path",
    )
    for key in keys:
        path = Path(envelope[key]).resolve()
        if path == run or not path.is_relative_to(run):
            raise ValueError("every input/helper/report must stay inside isolated run")
        if key == "copied_source_root":
            if not path.is_dir():
                raise ValueError("copied source must be a directory")
        elif key != "report_path" and (not path.is_file() or path.is_symlink()):
            raise ValueError("helper/request must be a regular existing file")
    if not Path(worker_path).resolve().is_relative_to(run):
        raise ValueError("worker must be an isolated immutable snapshot")
    if Path(envelope["report_path"]).exists():
        raise ValueError("native report must be new")
    if any(Path(envelope[key]).suffix != ".json" for key in ("request_path", "report_path")):
        raise ValueError("request and report must use json paths")
    if set(envelope["expected_runtime_paths"]) != PATH_KEYS:
        raise ValueError("all five native runtime paths required")
    runtime = [Path(value).resolve() for value in envelope["expected_runtime_paths"].values()]
    if len(set(runtime)) != 5:
        raise ValueError("all five runtime paths must be distinct")
    for key, value in envelope["expected_runtime_paths"].items():
        path = Path(value).resolve()
        source_root = Path(envelope["copied_source_root"]).resolve()
        files = {Path(envelope[k]).resolve() for k in keys if k != "copied_source_root"}
        files.add(Path(worker_path).resolve())
        if path in files or path.is_relative_to(source_root) or source_root.is_relative_to(path):
            raise ValueError("runtime paths must not alias inputs or enter copied source tree")
        if path == run or not path.is_relative_to(run):
            raise ValueError("runtime path escaped isolated run")
        if key in {"UserParameter", "SystemParameter"}:
            if path.suffix != ".cfg" or not path.parent.is_dir():
                raise ValueError("runtime parameter paths require run-local cfg files")
        elif not path.is_dir():
            raise ValueError("runtime home/data/temp must be existing directories")
    if (
        len({Path(envelope[k]).resolve() for k in keys} | {Path(worker_path).resolve()})
        != len(keys) + 1
    ):
        raise ValueError("native input/helper/worker/report paths must be distinct")
    for name in ("audit", "pose", "contract"):
        if (
            Path(envelope[name + "_helper_path"]).suffix != ".py"
            or sha(envelope[name + "_helper_path"]) != envelope[name + "_helper_sha256"]
        ):
            raise ValueError("native helper type/hash differs")
    if set(envelope["module_pins"]) != {
        "FastenersCmd",
        "freecad.gears.features",
        "pygears.involute_tooth",
        "pygears.bevel_tooth",
    }:
        raise ValueError("exact pinned Fasteners and Gears module set required")
    for pin in envelope["module_pins"].values():
        if (
            set(pin) != {"root", "sha256"}
            or not Path(pin["root"]).is_absolute()
            or not Path(pin["root"]).is_dir()
            or not re.fullmatch("[0-9a-f]{64}", str(pin["sha256"]))
        ):
            raise ValueError("native addon root/hash pin differs")
    if sha(worker_path) != envelope["worker_sha256"]:
        raise ValueError("worker snapshot changed")
    if sha(envelope["request_path"]) != envelope["request_sha256"]:
        raise ValueError("request snapshot changed")
    if shutil.disk_usage(run).free < 50 * 1024**3 + 128 * 1024**2:
        raise ValueError("native wrist run requires 50 GiB reserve plus scratch budget")
    return envelope


def prepare_contract(source_root, project_root):
    """Bind the full compatible tree plus source-only wrist operation contract."""
    directory = Path(__file__).parent
    pose = _load(
        directory / "probe_thor_pose_frames_desktop.py",
        sha(directory / "probe_thor_pose_frames_desktop.py"),
        "wrist_prepare_pose",
    )
    contract = _load(
        directory / "thor_wrist_pose_contract.py",
        sha(directory / "thor_wrist_pose_contract.py"),
        "wrist_prepare_contract",
    )
    baseline = json.loads(
        (Path(project_root) / "hardware/cad/thor-baseline-inspection.json").read_text(
            encoding="utf-8"
        )
    )
    source = pose.source_bindings(Path(source_root), baseline)
    prior = sys.modules.get("probe_thor_pose_frames_desktop")
    sys.modules["probe_thor_pose_frames_desktop"] = pose
    try:
        wrist_contract = contract.source_contract(Path(source_root))
    finally:
        if prior is None:
            sys.modules.pop("probe_thor_pose_frames_desktop", None)
        else:
            sys.modules["probe_thor_pose_frames_desktop"] = prior
    return {
        "schema_version": 1,
        "source_sha256": source["source_sha256"],
        "source_contract": wrist_contract,
        "poses": [{"name": n, "q5_rad": a, "q6_rad": b} for n, a, b in POSES],
    }


def validate_native_bindings(App, request, helper):
    """Authenticate source object, expression and saved offsets before mutation."""
    for binding in request["source_contract"]["bindings"]:
        document = App.getDocument(Path(binding["document"]).stem)
        if Path(document.FileName).name.lower() != binding["document"].lower():
            raise ValueError("actual source document filename differs")
        obj = document.getObject(binding["object"])
        if obj is None or obj.TypeId != "App::Link":
            raise ValueError("source operation target is not the expected existing AppLink")
        if [list(x) for x in obj.ExpressionEngine] != binding["saved_expression_engine"]:
            raise ValueError("existing Placement expression differs from source XML")
        saved = binding["saved_attachment_offset"]
        expected = App.Placement(
            App.Vector(*saved["position_mm"]), App.Rotation(*saved["quaternion_xyzw"])
        )
        a, b = (
            helper._placement(obj.AttachmentOffset)["matrix"],
            helper._placement(expected)["matrix"],
        )
        if max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4)) > 1e-8:
            raise ValueError("native saved offset differs from source XML")
        if obj.LinkedObject.Name != binding["linked_object"]:
            raise ValueError("actual linked object differs from source identity")
        if (
            Path(obj.LinkedObject.Document.FileName).name.lower()
            != Path(binding["linked_file"]).name.lower()
        ):
            raise ValueError("actual linked document differs from source identity")
        if obj.AttachedTo != binding["attached_to"]:
            raise ValueError("actual source attachment parent differs")


def cached_body_shape(Part, source_path, object_name, run):
    """Read a fresh cached BRep from pinned XML rather than recomputed history."""
    with zipfile.ZipFile(source_path) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError("ambiguous cached source archive")
        tree = ET.fromstring(archive.read("Document.xml"))
        objects = [o for o in tree.findall("./ObjectData/Object") if o.get("name") == object_name]
        if len(objects) != 1:
            raise ValueError("cached source object identity ambiguous")
        node = objects[0].find('./Properties/Property[@name="Shape"]/Part')
        if node is None:
            raise ValueError("linked Body lacks cached BRep")
        entry = node.get("file")
        if not 0 < archive.getinfo(entry).file_size <= 16 * 1024**2:
            raise ValueError("cached source BRep outside bounded size")
        raw = archive.read(entry)
    destination = run / (Path(source_path).stem + "-" + object_name + "-source.brep")
    with destination.open("xb") as stream:
        stream.write(raw)
    shape = Part.Shape()
    shape.read(str(destination))
    object_types = [
        o.get("type") for o in tree.findall("./Objects/Object") if o.get("name") == object_name
    ]
    if len(object_types) != 1:
        raise ValueError("cached source object type ambiguous")
    return shape, {
        "source_file": Path(source_path).name,
        "source_sha256": sha(source_path),
        "object_name": object_name,
        "object_type": object_types[0],
        "brep_entry": entry,
        "brep_sha256": hashlib.sha256(raw).hexdigest(),
        "source_raw_placement": list(shape.Placement.toMatrix().A),
    }


def native_capture():
    if os.environ.get(FLAG) != "1":
        raise ValueError("native wrist frame worker requires explicit opt-in")
    if any(
        os.environ.get(key) == "1"
        for key in ("RAFTEL_RUN_FREECAD_AUDIT", "RAFTEL_RUN_THOR_POSE_FRAMES")
    ):
        raise ValueError("conflicting native helper entry flags must be cleared")
    run = Path(os.environ["RAFTEL_WRIST_FRAMES_RUN_DIR"]).resolve(strict=True)
    envelope_path = Path(os.environ["RAFTEL_WRIST_FRAMES_ENVELOPE"]).resolve(strict=True)
    if not envelope_path.is_relative_to(run):
        raise ValueError("envelope escaped isolated run")
    if envelope_path.suffix != ".json":
        raise ValueError("native envelope must be a json file")
    envelope = validate_envelope(read_json(envelope_path), run, __file__)
    file_paths = [
        Path(envelope[k]).resolve()
        for k in (
            "request_path",
            "report_path",
            "audit_helper_path",
            "pose_helper_path",
            "contract_helper_path",
        )
    ]
    if (
        envelope_path in file_paths
        or envelope_path == Path(__file__).resolve()
        or envelope_path in [Path(p).resolve() for p in envelope["expected_runtime_paths"].values()]
    ):
        raise ValueError("envelope must not alias native inputs or runtime paths")
    pose = _load(envelope["pose_helper_path"], envelope["pose_helper_sha256"], "wrist_pose_helpers")
    helper = _load(
        envelope["audit_helper_path"], envelope["audit_helper_sha256"], "wrist_audit_helpers"
    )
    contract_module = _load(
        envelope["contract_helper_path"],
        envelope["contract_helper_sha256"],
        "wrist_contract_helpers",
    )
    request = read_json(envelope["request_path"])
    if (
        set(request) != {"schema_version", "source_sha256", "source_contract", "poses"}
        or type(request["schema_version"]) is not int
        or request["schema_version"] != 1
    ):
        raise ValueError("native wrist request fields differ")
    contract_module.validate_contract(request["source_contract"])
    if request["poses"] != [{"name": n, "q5_rad": a, "q6_rad": b} for n, a, b in POSES]:
        raise ValueError("wrist pose plan differs from bounded three-stage study")
    source = Path(envelope["copied_source_root"])
    pins = request["source_sha256"]
    if len(pins) != 57 or any(
        Path(name).name != name or not name.lower().endswith(".fcstd") for name in pins
    ):
        raise ValueError("source manifest must contain 57 native basenames")
    actual_files = list(source.iterdir())
    if {p.name for p in actual_files} != set(pins) or any(
        not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(source.resolve())
        for p in actual_files
    ):
        raise ValueError("copied source tree differs from exact regular-file manifest")
    before = {name: sha(source / name) for name in pins}
    if before != pins:
        raise ValueError("copied source hashes differ from request")
    writer = helper.ReportWriter(Path(envelope["report_path"]))
    report = {
        "schema_version": 1,
        "evidence_class": "native_existing_AppLink_wrist_offsets_and_cached_shape_refresh",
        "status": "starting",
        "request": request,
        "capture_script_sha256": sha(__file__),
        "request_sha256": envelope["request_sha256"],
        "helper_sha256": {
            key: envelope[key]
            for key in ("audit_helper_sha256", "pose_helper_sha256", "contract_helper_sha256")
        },
        "source_copy_sha256_before": before,
        "poses": [],
        "errors": [],
        "cad_documents_saved": False,
        "forced_feature_history_rebuild": False,
        "constraint_kinematics_solved": False,
        "side_differential_gears_driven": False,
        "physical_calibration_or_contact_or_TCP_qualified": False,
    }
    started = time.monotonic()
    App = None
    previous = None
    originals = None
    writer(report)

    def checkpoint(stage):
        report["stage"] = stage
        report["elapsed_s"] = time.monotonic() - started
        writer(report)
        if report["elapsed_s"] > 420:
            raise ValueError("bounded native wrist experiment exceeded 420 seconds")

    try:
        import FreeCAD as App
        import Part

        previous = set(App.listDocuments())
        report["open_document_count_before"] = len(previous)
        report["runtime_isolation"] = helper._runtime_isolation(App, run)
        report["expected_runtime_paths"] = envelope["expected_runtime_paths"]
        if any(
            Path(App.ConfigGet(k)).resolve() != Path(v).resolve()
            for k, v in envelope["expected_runtime_paths"].items()
        ):
            raise ValueError("actual five runtime paths differ from requested paths")
        report["freecad_version"] = list(App.Version())
        report["opencascade_version"] = getattr(Part, "OCC_VERSION", None)
        report["modules"] = {}
        import importlib

        for name, pin in envelope["module_pins"].items():
            module = importlib.import_module(name)
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(Path(pin["root"]).resolve()) or sha(path) != pin["sha256"]:
                raise ValueError("native module origin/hash differs: " + name)
            report["modules"][name] = {
                "path": str(path),
                "sha256": sha(path),
                "origin_verified": True,
            }
        checkpoint("opening_compatible_assembly")
        master = App.openDocument(str(source / "Assembly.FCStd"), True)
        wrist = App.getDocument("AssemblyArt56")
        report["loaded_documents"] = [
            {"document": doc.Name, "filename": doc.FileName, "sha256": sha(doc.FileName)}
            for doc in App.listDocuments().values()
        ]
        if any(
            not Path(row["filename"]).resolve().is_relative_to(source.resolve())
            for row in report["loaded_documents"]
        ):
            raise ValueError("restored document escaped copied source tree")
        for doc in (master, wrist):
            m = helper._placement(doc.getObject("Model").Placement)["matrix"]
            if max(abs(m[i][j] - float(i == j)) for i in range(4) for j in range(4)) > 1e-9:
                raise ValueError("nonidentity Model parent requires explicit handling")
        drivers = (
            master.getObject("AssemblyArt56"),
            wrist.getObject("Art56GearPlate_Art56GearPlate"),
        )
        originals = [App.Placement(obj.AttachmentOffset) for obj in drivers]
        expressions = [[list(item) for item in obj.ExpressionEngine] for obj in drivers]
        report["driver_original_readback"] = [
            {
                "document": obj.Document.Name,
                "object": obj.Name,
                "offset": helper._placement(obj.AttachmentOffset),
                "expressions": expression,
            }
            for obj, expression in zip(drivers, expressions, strict=True)
        ]
        # XML identity and source-offset equality is checked by the source contract.
        validate_native_bindings(App, request, helper)
        source_shapes = {}
        for body_name in BODY_NAMES:
            if body_name != "AssemblyArt4":
                linked = wrist.getObject(body_name).LinkedObject
                source_shapes[body_name] = cached_body_shape(
                    Part, Path(linked.Document.FileName), linked.Name, run
                )
        selections = {}
        zero_counts = {}
        for name, q5, q6 in POSES:
            checkpoint("applying_" + name)
            drivers[0].AttachmentOffset = originals[0].multiply(
                App.Placement(App.Vector(), App.Rotation(App.Vector(1, 0, 0), math.degrees(q5)))
            )
            drivers[1].AttachmentOffset = App.Placement(
                App.Vector(), App.Rotation(App.Vector(0, 0, 1), math.degrees(q6))
            ).multiply(originals[1])
            wrist_recomputed = wrist.recompute()
            master_recomputed = master.recompute()
            ancestor = master.getObject("AssemblyArt56").Placement
            row = {
                "name": name,
                "q5_rad": q5,
                "q6_rad": q6,
                "recompute_returns": {"wrist": wrist_recomputed, "master": master_recomputed},
                "master_wrist_placement": helper._placement(ancestor),
                "bodies": [],
                "driver_readbacks": [],
            }
            for obj, expression in zip(drivers, expressions, strict=True):
                actual_expression = [list(item) for item in obj.ExpressionEngine]
                row["driver_readbacks"].append(
                    {
                        "document": obj.Document.Name,
                        "object": obj.Name,
                        "offset": helper._placement(obj.AttachmentOffset),
                        "expressions": actual_expression,
                    }
                )
                if actual_expression != expression:
                    raise ValueError("existing source expression changed")
            for body_name in BODY_NAMES:
                obj = (
                    master.getObject(body_name)
                    if body_name == "AssemblyArt4"
                    else wrist.getObject(body_name)
                )
                body_ancestor = App.Placement() if body_name == "AssemblyArt4" else ancestor
                raw = [list(v.Point) for v in obj.Shape.Vertexes]
                if body_name not in selections:
                    selections[body_name] = select_marker_indices(raw)
                    zero_counts[body_name] = len(raw)
                if len(raw) != zero_counts[body_name]:
                    raise ValueError("ordered native body vertex count changed")
                indices = selections[body_name]
                raw_markers = [raw[i] for i in indices]
                world = [list(body_ancestor.multVec(App.Vector(*p))) for p in raw_markers]
                linked = obj.LinkedObject
                source_vertices = [list(v.Point) for v in linked.Shape.Vertexes]
                if len(source_vertices) != len(raw):
                    raise ValueError("linked source/installed ordered vertex counts differ")
                row["bodies"].append(
                    {
                        "document": obj.Document.Name,
                        "object": body_name,
                        "type_id": obj.TypeId,
                        "linked_document": linked.Document.Name,
                        "linked_object": linked.Name,
                        "vertex_count": len(raw),
                        "marker_vertex_indices_zero_based": indices,
                        "raw_shape_markers_subassembly_mm": raw_markers,
                        "linked_source_markers_mm": [source_vertices[i] for i in indices],
                        "linked_source_vertex_count": len(source_vertices),
                        "linked_source_placement": helper._placement(linked.Placement),
                        "link_transform": bool(obj.LinkTransform),
                        "actual_markers_native_world_mm": world,
                        "marker_frame_native_world_mm": marker_frame(world),
                        "body_frame_native_world_mm": helper._placement(
                            body_ancestor.multiply(obj.Placement)
                        )["matrix"],
                        "placement_in_subassembly": helper._placement(obj.Placement),
                        "shape_placement": helper._placement(obj.Shape.Placement),
                        "shape_own_placement_not_applied_twice": True,
                        "ordered_raw_vertices_sha256": hashlib.sha256(
                            json.dumps(raw, separators=(",", ":"), allow_nan=False).encode()
                        ).hexdigest(),
                        "state": list(obj.State),
                    }
                )
                if body_name in source_shapes:
                    cached, binding = source_shapes[body_name]
                    row["bodies"][-1]["cached_source_binding"] = binding
                    row["bodies"][-1]["cached_source_markers_mm"] = [
                        list(cached.Vertexes[i].Point) for i in indices
                    ]
                    row["bodies"][-1]["cached_source_vertex_count"] = len(cached.Vertexes)
            row["state_summary"] = pose._summary(pose._state_records(App))
            report["poses"].append(row)
            checkpoint("captured_" + name)
            if row["state_summary"]["invalid_or_error"]:
                raise ValueError("native descendants contain Invalid/Error states")
        report["saved_offset_return_maximum_matrix_error"] = max(
            abs(
                helper._placement(obj.AttachmentOffset)["matrix"][i][j]
                - helper._placement(saved)["matrix"][i][j]
            )
            for obj, saved in zip(drivers, originals, strict=True)
            for i in range(4)
            for j in range(4)
        )
        report["saved_offsets_restored_in_memory"] = (
            report["saved_offset_return_maximum_matrix_error"] <= 1e-9
        )
        if not report["saved_offsets_restored_in_memory"]:
            raise ValueError("actual offset readback did not return to saved zero")
        report["final_loaded_document_states"] = pose._state_records(App)
        report["final_state_summary"] = pose._summary(report["final_loaded_document_states"])
        report["status"] = "complete_native_wrist_observations_pending_independent_review"
    except Exception as error:
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
        report["status"] = "failed_native_wrist_frame_capture"
    finally:
        if App is not None and previous is not None:
            if originals is not None:
                try:
                    for obj, offset in zip(drivers, originals, strict=True):
                        obj.AttachmentOffset = offset
                    # No history rebuild/save in cleanup; documents immediately close.
                    report["offset_cleanup_assignment_completed"] = True
                except Exception as error:
                    report["errors"].append(
                        {"type": type(error).__name__, "message": "offset cleanup: " + str(error)}
                    )
                    report["status"] = "failed_native_wrist_frame_capture"
            remaining = pose.close_created_documents(App, previous)
            report["open_document_count_after_close"] = len(remaining)
            report["preexisting_documents_preserved"] = remaining == previous
        report["source_copy_sha256_after"] = {name: sha(source / name) for name in before}
        report["source_copy_bytes_unchanged"] = before == report["source_copy_sha256_after"]
        report["elapsed_s"] = time.monotonic() - started
        if (
            not report["source_copy_bytes_unchanged"]
            or report.get("preexisting_documents_preserved") is not True
        ):
            report["status"] = "failed_preservation_or_close_guard"
        writer(report)
    print("RAFTEL_NATIVE_WRIST_FRAME_RESULT", report["status"])
    return report


if __name__ == "__main__" or os.environ.get(FLAG) == "1":
    native_capture()
