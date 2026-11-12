"""Host replay of copied native wrist observations, never physical qualification.

The capture supplies observed vertices and placements. This reviewer checks
their products and source-line motion using the existing contract, rather than
using a pose supplied by the capture as its own expected pose.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath

from raftel_arm01.kinematics.thor_frames import compose, inverse, rigid_transform
from raftel_arm01.kinematics.thor_model import _rotation

TOOLS = Path(__file__).resolve().parent
BODY_NAMES = (
    "Art56GearPlate_Art56GearPlate",
    "GripperBot_GripperBot",
    "Art56MotorCoverRing_Art56MotorCoverRing",
    "AssemblyArt4",
)
POSES = (("saved_zero", 0.0, 0.0), ("fold_roll", 0.2, 0.15), ("saved_return", 0.0, 0.0))
PATH_KEYS = {"UserParameter", "SystemParameter", "UserHomePath", "UserAppData", "AppTempPath"}
TOLERANCE_MM = 1e-6
ROTATION_TOLERANCE = 1e-9
TENSOR_SHA256 = "fa4a2f88e027c17a33c8d092640c747cfbe7d1fc9ad008c151701eb7b0d05a20"


def _module(filename, name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value):
    _require(type(value) in (int, float), "finite nonboolean number required")
    try:
        number = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("finite nonboolean number required") from error
    _require(math.isfinite(number), "finite nonboolean number required")
    return number


def _digest(value):
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def _matrix(value):
    return rigid_transform(value)


def _close_matrix(actual, expected, label):
    a, b = _matrix(actual), _matrix(expected)
    _require(
        max(abs(a[i][3] - b[i][3]) for i in range(3)) <= TOLERANCE_MM
        and max(abs(a[i][j] - b[i][j]) for i in range(3) for j in range(3)) <= ROTATION_TOLERANCE,
        label + " differs",
    )


def _points(value):
    _require(isinstance(value, list) and len(value) == 3, "three observed markers required")
    _require(all(isinstance(p, list) and len(p) == 3 for p in value), "three-vector required")
    return [[_finite(v) for v in p] for p in value]


def _identity():
    return [[float(i == j) for j in range(4)] for i in range(4)]


def saved_placement_matrix(saved):
    """Reuse source quaternion arithmetic; all values here remain millimetres."""
    extractor = _module("extract_thor_geometry.py", "wrist_review_saved_placement")
    frame = {"position_m": saved["position_mm"], "quaternion_xyzw": saved["quaternion_xyzw"]}
    origin = extractor.transform_point(frame, [0, 0, 0])
    axes = [extractor.transform_point(frame, [float(i == j) for i in range(3)]) for j in range(3)]
    return [[axes[j][i] - origin[i] for j in range(3)] + [origin[i]] for i in range(3)] + [
        [0, 0, 0, 1]
    ]


def _marker_frame(points):
    # The native frame's columns are checked directly against its observations;
    # no imported native worker method supplies the expected result.
    p, q, r = _points(points)
    x = [q[i] - p[i] for i in range(3)]
    d = [r[i] - p[i] for i in range(3)]
    z = [x[1] * d[2] - x[2] * d[1], x[2] * d[0] - x[0] * d[2], x[0] * d[1] - x[1] * d[0]]
    _require(math.hypot(*x) > 1e-6 and math.hypot(*z) > 1e-6, "markers must be noncollinear")
    x = [v / math.hypot(*x) for v in x]
    z = [v / math.hypot(*z) for v in z]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    return [[x[i], y[i], z[i], p[i]] for i in range(3)] + [[0, 0, 0, 1]]


def _baseline_capture():
    path = TOOLS.parent / "hardware/cad/thor-printed-tensor-frames-v1.json"
    raw = path.read_bytes()
    _require(
        hashlib.sha256(raw).hexdigest() == TENSOR_SHA256, "source marker reference bytes differ"
    )
    return json.loads(raw)


def source_marker_reference():
    """Reuse the independently BRep-authenticated frozen ordered vertex table."""
    reference = _baseline_capture()
    assets = {name.split("_")[0] + "::Body" for name in BODY_NAMES[:3]}
    return {v["asset_id"]: v for v in reference["variants"] if v["asset_id"] in assets}, reference[
        "source_copy_sha256_before"
    ]


def review_body_observations(poses, expected_marker, reference=None):
    """Check source-line motion and actual shape/frame/return witnesses."""
    _require(
        isinstance(poses, list) and len(poses) == 3, "three ordered pose observations required"
    )
    tensor = _module("probe_thor_printed_tensor_frames.py", "wrist_review_tensor")
    if reference is None:
        reference, _ = source_marker_reference()
    zero = {}
    maximum_motion_error = 0.0
    for pose, (name, q5, q6) in zip(poses, POSES, strict=True):
        _require(pose.get("name") == name, "pose order or identity differs")
        _require(
            _finite(pose["q5_rad"]) == q5 and _finite(pose["q6_rad"]) == q6,
            "pose coordinate differs",
        )
        ancestor = _matrix(pose["master_wrist_placement"]["matrix"])
        bodies = pose["bodies"]
        _require(
            isinstance(bodies, list) and len(bodies) == 4, "exactly four body observations required"
        )
        _require(
            tuple(row.get("object") for row in bodies) == BODY_NAMES, "body identity/order differs"
        )
        for body in bodies:
            key = body["object"]
            stationary = key == "AssemblyArt4"
            body_ancestor = _identity() if stationary else ancestor
            _require(
                body.get("document") == ("Assembly" if stationary else "AssemblyArt56")
                and body.get("type_id") == "App::Link",
                "body document/type differs",
            )
            _require(
                body.get("shape_own_placement_not_applied_twice") is True,
                "shape convention unavailable",
            )
            count, indices = body["vertex_count"], body["marker_vertex_indices_zero_based"]
            _require(type(count) is int and 3 <= count <= 100000, "body vertex count outside bound")
            _require(
                isinstance(indices, list) and len(indices) == 3 and len(set(indices)) == 3,
                "distinct marker indices required",
            )
            _require(
                all(type(i) is int and 0 <= i < count for i in indices),
                "invalid marker vertex index",
            )
            _require(_digest(body["ordered_raw_vertices_sha256"]), "raw vertex digest required")
            _require(
                isinstance(body["state"], list)
                and all(
                    isinstance(v, str) and "Invalid" not in v and "Error" not in v
                    for v in body["state"]
                ),
                "invalid body state",
            )
            raw = _points(body["raw_shape_markers_subassembly_mm"])
            world = _points(body["actual_markers_native_world_mm"])
            tensor.marker_check(raw, world, body_ancestor, TOLERANCE_MM)
            _close_matrix(
                body["marker_frame_native_world_mm"], _marker_frame(world), "observed marker frame"
            )
            placement = _matrix(body["placement_in_subassembly"]["matrix"])
            shape_placement = _matrix(body["shape_placement"]["matrix"])
            _close_matrix(
                body["body_frame_native_world_mm"],
                compose(body_ancestor, placement),
                "body placement product",
            )
            linked_placement = _matrix(body["linked_source_placement"]["matrix"])
            _require(body.get("link_transform") is False, "unexpected LinkTransform convention")
            source_markers = _points(body["linked_source_markers_mm"])
            _require(body["linked_source_vertex_count"] == count, "source vertex count differs")
            tensor.marker_check(
                source_markers, raw, compose(placement, inverse(linked_placement)), TOLERANCE_MM
            )
            if not stationary:
                asset = key.split("_")[0]
                variant = reference[asset + "::Body"]
                _require(
                    body["linked_document"] == asset and body["linked_object"] == "Body",
                    "linked source object differs",
                )
                _require(
                    count == len(variant["source_vertices_mm"]),
                    "pinned source vertex count differs",
                )
                _close_matrix(
                    linked_placement, variant["source_raw_placement_mm"], "pinned source placement"
                )
                expected_source = [variant["source_vertices_mm"][i] for i in indices]
                tensor.marker_check(expected_source, source_markers, _identity(), TOLERANCE_MM)
                cached = body["cached_source_binding"]
                pinned = variant["source_binding"]
                for field in (
                    "source_sha256",
                    "object_name",
                    "object_type",
                    "brep_entry",
                    "brep_sha256",
                ):
                    _require(
                        cached[field] == pinned[field], "cached source binding differs: " + field
                    )
                _require(
                    Path(cached["source_file"]).name.casefold()
                    == Path(pinned["source_file"]).name.casefold(),
                    "cached source filename differs",
                )
                saved_matrix = cached["source_raw_placement"]
                _require(
                    isinstance(saved_matrix, list) and len(saved_matrix) == 16,
                    "cached source placement requires sixteen elements",
                )
                saved_matrix = [saved_matrix[i : i + 4] for i in range(0, 16, 4)]
                _close_matrix(
                    saved_matrix, variant["source_raw_placement_mm"], "cached source placement"
                )
                _require(body["cached_source_vertex_count"] == count, "cached source count differs")
                cached_points = _points(body["cached_source_markers_mm"])
                tensor.marker_check(expected_source, cached_points, _identity(), TOLERANCE_MM)
                tensor.marker_check(
                    cached_points,
                    raw,
                    compose(shape_placement, inverse(saved_matrix)),
                    TOLERANCE_MM,
                )
            else:
                _require(
                    body["linked_document"] == "AssemblyArt4" and body["linked_object"] == "Model",
                    "stationary source identity differs",
                )
            if name == "saved_zero":
                zero[key] = body
                continue
            baseline = zero[key]
            for identity in (
                "document",
                "object",
                "type_id",
                "linked_document",
                "linked_object",
                "vertex_count",
                "marker_vertex_indices_zero_based",
            ):
                _require(
                    body[identity] == baseline[identity],
                    "body source identity changed: " + identity,
                )
            expected = (
                baseline["actual_markers_native_world_mm"]
                if stationary
                else [
                    expected_marker(p, q5, q6, roll=key != BODY_NAMES[2])
                    for p in baseline["actual_markers_native_world_mm"]
                ]
            )
            error = max(math.dist(a, b) for a, b in zip(world, expected, strict=True))
            _require(error <= TOLERANCE_MM, "independent source-line motion differs")
            maximum_motion_error = max(maximum_motion_error, error)
            delta = compose(
                _matrix(body["body_frame_native_world_mm"]),
                inverse(_matrix(baseline["body_frame_native_world_mm"])),
            )
            tensor.marker_check(
                baseline["actual_markers_native_world_mm"], world, delta, TOLERANCE_MM
            )
            if name == "fold_roll" and key in BODY_NAMES[:2]:
                _require(
                    max(
                        math.dist(a, b)
                        for a, b in zip(
                            raw, baseline["raw_shape_markers_subassembly_mm"], strict=True
                        )
                    )
                    > 1e-3,
                    "raw Shape markers did not refresh",
                )
                _require(
                    body["ordered_raw_vertices_sha256"] != baseline["ordered_raw_vertices_sha256"],
                    "raw Shape digest did not refresh",
                )
            if name == "fold_roll" and (key == BODY_NAMES[2] or stationary):
                tensor.marker_check(
                    baseline["raw_shape_markers_subassembly_mm"], raw, _identity(), TOLERANCE_MM
                )
                _close_matrix(
                    placement,
                    baseline["placement_in_subassembly"]["matrix"],
                    "stationary subassembly witness",
                )
            if name == "saved_return":
                tensor.marker_check(
                    baseline["raw_shape_markers_subassembly_mm"], raw, _identity(), TOLERANCE_MM
                )
                _close_matrix(
                    body["body_frame_native_world_mm"],
                    baseline["body_frame_native_world_mm"],
                    "nominal return body frame",
                )
    return {
        "observed_poses": 3,
        "observed_bodies_per_pose": 4,
        "maximum_motion_error_mm": maximum_motion_error,
    }


def _path(value):
    _require(isinstance(value, str) and bool(value), "absolute runtime path required")
    cls = (
        PureWindowsPath if "\\" in value or (len(value) > 1 and value[1] == ":") else PurePosixPath
    )
    path = cls(value)
    _require(
        path.is_absolute() and ".." not in path.parts,
        "absolute runtime path without traversal required",
    )
    return path


def validate_capture(
    capture,
    *,
    expected_worker_sha256=None,
    expected_helper_sha256=None,
    expected_contract_sha256=None,
    expected_module_pins=None,
    expected_request_sha256=None,
):
    """Raise ValueError for malformed, partial, stale, or unsupported captures."""
    try:
        return _validate_capture(
            capture,
            expected_worker_sha256,
            expected_helper_sha256,
            expected_contract_sha256,
            expected_module_pins,
            expected_request_sha256,
        )
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError) as error:
        raise ValueError("malformed native wrist capture") from error


def _validate_capture(capture, worker_pin, helper_pin, contract_pin, module_pins, request_pin):
    contract = _module("thor_wrist_pose_contract.py", "wrist_review_contract")
    _require(isinstance(capture, dict), "capture root must be object")
    _require(
        type(capture.get("schema_version")) is int and capture["schema_version"] == 1,
        "unsupported capture schema",
    )
    _require(
        capture.get("evidence_class")
        == "native_existing_AppLink_wrist_offsets_and_cached_shape_refresh",
        "unsupported capture class",
    )
    _require(
        capture.get("status") == "complete_native_wrist_observations_pending_independent_review"
        and capture.get("errors") == [],
        "native capture incomplete or failed",
    )
    for key in (
        "cad_documents_saved",
        "forced_feature_history_rebuild",
        "constraint_kinematics_solved",
        "side_differential_gears_driven",
        "physical_calibration_or_contact_or_TCP_qualified",
    ):
        _require(capture.get(key) is False, "scope gate failed: " + key)
    for key in (
        "source_copy_bytes_unchanged",
        "preexisting_documents_preserved",
        "saved_offsets_restored_in_memory",
        "offset_cleanup_assignment_completed",
    ):
        _require(capture.get(key) is True, "preservation gate failed: " + key)
    for key in ("open_document_count_before", "open_document_count_after_close"):
        _require(
            type(capture.get(key)) is int and capture[key] == 0,
            "fresh process document count required",
        )
    _require(0 <= _finite(capture["elapsed_s"]) <= 420, "native elapsed time outside bound")
    pin = (
        worker_pin
        or hashlib.sha256((TOOLS / "probe_thor_wrist_frames_desktop.py").read_bytes()).hexdigest()
    )
    _require(_digest(pin) and capture["capture_script_sha256"] == pin, "worker pin differs")
    helper_expected = {
        "audit_helper_sha256": helper_pin
        or hashlib.sha256((TOOLS / "audit_freecad_assembly.py").read_bytes()).hexdigest(),
        "pose_helper_sha256": hashlib.sha256(
            (TOOLS / "probe_thor_pose_frames_desktop.py").read_bytes()
        ).hexdigest(),
        "contract_helper_sha256": contract_pin
        or hashlib.sha256((TOOLS / "thor_wrist_pose_contract.py").read_bytes()).hexdigest(),
    }
    _require(capture["helper_sha256"] == helper_expected, "helper pins differ")
    _require(_digest(capture["request_sha256"]), "request digest required")
    _require(
        _digest(request_pin) and capture["request_sha256"] == request_pin,
        "exact retained request bytes must be independently pinned",
    )
    request = capture["request"]
    contract.validate_contract(request["source_contract"])
    _require(
        type(request.get("schema_version")) is int
        and request["schema_version"] == 1
        and request["poses"] == [{"name": n, "q5_rad": a, "q6_rad": b} for n, a, b in POSES],
        "request pose/schema differs",
    )
    for pose in request["poses"]:
        _finite(pose["q5_rad"])
        _finite(pose["q6_rad"])
    before = capture["source_copy_sha256_before"]
    reference, source_pins = source_marker_reference()
    _require(
        isinstance(before, dict)
        and len(before) == 57
        and before == request["source_sha256"] == capture["source_copy_sha256_after"],
        "source ledgers differ",
    )
    _require(all(_digest(value) for value in before.values()), "source digest invalid")
    _require(
        before == source_pins, "full compatible source pins differ from authenticated baseline"
    )
    runtime = capture["runtime_isolation"]
    _require(
        runtime.get("requested") is True and runtime.get("verified") is True,
        "runtime isolation unavailable",
    )
    root = _path(runtime["root"])
    actual, expected = runtime["actual_paths"], capture["expected_runtime_paths"]
    _require(set(actual) == set(expected) == PATH_KEYS, "five runtime paths required")
    _require(len({_path(v) for v in actual.values()}) == 5, "runtime paths must be distinct")
    for key in PATH_KEYS:
        _require(
            _path(actual[key]) == _path(expected[key])
            and _path(actual[key]) != root
            and _path(actual[key]).is_relative_to(root),
            "runtime paths escaped or differ",
        )
    _require(
        isinstance(module_pins, dict)
        and set(module_pins)
        == {
            "FastenersCmd",
            "freecad.gears.features",
            "pygears.involute_tooth",
            "pygears.bevel_tooth",
        },
        "external addon module pins required",
    )
    modules = capture["modules"]
    _require(
        isinstance(modules, dict) and set(modules) == set(module_pins),
        "addon module coverage differs",
    )
    for name, pin in module_pins.items():
        observed = modules[name]
        _require(
            observed.get("origin_verified") is True
            and _digest(pin["sha256"])
            and observed["sha256"] == pin["sha256"]
            and _path(observed["path"]).is_relative_to(_path(pin["root"])),
            "addon module origin/hash differs",
        )
    documents = capture["loaded_documents"]
    _require(
        isinstance(documents, list)
        and len(documents) == 53
        and len({d["document"] for d in documents}) == 53,
        "53 private restored documents required",
    )
    source_casefold = {name.casefold(): digest for name, digest in before.items()}
    _require(len(source_casefold) == 57, "ambiguous casefold source filenames")
    expected_documents = {
        row["document"]: _path(row["path"]).name.casefold()
        for row in _baseline_capture()["loaded_document_sources"]
    }
    _require(
        {row["document"]: _path(row["filename"]).name.casefold() for row in documents}
        == expected_documents,
        "restored document source identities differ",
    )
    for doc in documents:
        path = _path(doc["filename"])
        _require(
            path.parent == root / "source"
            and source_casefold.get(path.name.casefold()) == doc["sha256"],
            "loaded source path/hash differs",
        )
    _require(
        capture.get("freecad_version", [])[:3] == ["1", "1", "4"]
        and capture.get("opencascade_version") == "7.8.1",
        "unsupported native runtime",
    )
    pose_helper = _module("probe_thor_pose_frames_desktop.py", "wrist_review_pose_helper")
    _require(
        capture["final_state_summary"]
        == pose_helper._summary(capture["final_loaded_document_states"]),
        "final native state summary differs",
    )
    final_states = capture["final_loaded_document_states"]
    _require(
        len(final_states) == 53
        and {d["document"] for d in final_states} == {d["document"] for d in documents},
        "final state document coverage differs",
    )
    for summary in [capture["final_state_summary"]] + [
        p["state_summary"] for p in capture["poses"]
    ]:
        _require(summary.get("invalid_or_error") == [], "native Invalid/Error state present")
    drivers = capture["driver_original_readback"]
    _require(
        isinstance(drivers, list) and len(drivers) == 2,
        "two original native driver readbacks required",
    )
    for original, binding in zip(drivers, request["source_contract"]["bindings"][:2], strict=True):
        _require(
            original["document"] == Path(binding["document"]).stem
            and original["object"] == binding["object"]
            and original["expressions"] == binding["saved_expression_engine"],
            "original driver source binding differs",
        )
        _close_matrix(
            original["offset"]["matrix"],
            saved_placement_matrix(binding["saved_attachment_offset"]),
            "source driver offset",
        )
    for pose in capture["poses"]:
        _require(
            set(pose["recompute_returns"]) == {"wrist", "master"}
            # Pinned FreeCAD DocumentPyImp.cpp:714-723 returns Py::Long
            # (objectCount), not a success boolean. Raw counts remain evidence;
            # the subsequent state/geometry checks establish actual response.
            and all(
                type(v) is int and 0 <= v <= 100000 for v in pose["recompute_returns"].values()
            ),
            "native recompute return types differ",
        )
        readbacks = pose["driver_readbacks"]
        _require(
            isinstance(readbacks, list) and len(readbacks) == 2,
            "two native driver readbacks required",
        )
        for actual, original in zip(readbacks, drivers, strict=True):
            _require(
                all(actual[k] == original[k] for k in ("document", "object", "expressions")),
                "native driver identity/expression changed",
            )
            _matrix(actual["offset"]["matrix"])
            if pose["name"] in {"saved_zero", "saved_return"}:
                _close_matrix(
                    actual["offset"]["matrix"], original["offset"]["matrix"], "driver offset return"
                )
        expected_offsets = (
            compose(_matrix(drivers[0]["offset"]["matrix"]), _rotation((1, 0, 0), pose["q5_rad"])),
            compose(_rotation((0, 0, 1), pose["q6_rad"]), _matrix(drivers[1]["offset"]["matrix"])),
        )
        for actual, expected_offset in zip(readbacks, expected_offsets, strict=True):
            _close_matrix(
                actual["offset"]["matrix"], expected_offset, "declared source offset increment"
            )
    result = review_body_observations(capture["poses"], contract.expected_marker, reference)
    return {
        **result,
        "physical_calibration_qualified": False,
        "full_body_clearance_qualified": False,
    }


def report_is_complete(capture, **pins):
    try:
        validate_capture(capture, **pins)
        return True
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument(
        "--envelope", type=Path, required=True, help="independently retained launch envelope"
    )
    args = parser.parse_args()
    reader = _module("thor_printed_inertia_study.py", "wrist_review_json")
    _, capture = reader.strict_json(args.capture)
    _, envelope = reader.strict_json(args.envelope)
    request_path = Path(envelope["request_path"])
    request_raw, request = reader.strict_json(request_path)
    _require(request == capture["request"], "retained request differs from capture")
    _require(
        hashlib.sha256(request_raw).hexdigest() == envelope["request_sha256"],
        "retained request bytes differ",
    )
    result = validate_capture(
        capture,
        expected_worker_sha256=envelope["worker_sha256"],
        expected_helper_sha256=envelope["audit_helper_sha256"],
        expected_contract_sha256=envelope["contract_helper_sha256"],
        expected_module_pins=envelope["module_pins"],
        expected_request_sha256=envelope["request_sha256"],
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
