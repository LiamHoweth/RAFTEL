"""Native selected wrist BRep diagnostics; no feature solve, save or hardware.

Use a fresh isolated FreeCAD process and a compatible copied Assembly.FCStd.
Saved source shapes and rigidly transformed ideal scenarios remain distinct.
An outer process timeout must bound any individual blocked native operation.
"""

from __future__ import annotations

import hashlib
import math
import os
import runpy
import shutil
import time
from pathlib import Path, PurePosixPath, PureWindowsPath

FLAG = "RAFTEL_RUN_WRIST_POSE_DESKTOP"
SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
PINNED = {
    "Assembly.FCStd": "5ee729246229e7494466010ab68e2c2367ba4ec1361b7701df21c0f8b00c2c1b",
    "AssemblyArt56.FCStd": "a04836216dcae82eb033c15daba6e41dedb85b03f86ff21e56b77cdff835a473",
    "Art56GearPlate.fcstd": "38ca5952d4e03e4009f94628d0c435153b980ea558a608fca9ac1c9aaf79d411",
    "Art56SmallGear.fcstd": "b737ce24c58bc5ffc3763fcd6cdcfdd425747565c2850054397f066ecd5a63a0",
}
NAMES = (
    "Art56GearPlate_Art56GearPlate",
    "Art56SmallGear_Art56SmallGear",
    "Art56SmallGear_Art56SmallGear001",
)
BOUNDS = ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("probe values must be finite real numbers")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("probe values must be finite real numbers") from error
    if not math.isfinite(result):
        raise ValueError("probe values must be finite real numbers")
    return result


def pose_plan() -> tuple[dict, ...]:
    """Three declared wrist poses, with a reversed-sign diagnostic comparator."""
    return (
        {"pose_id": "saved_zero", "q5_deg": 0.0, "q6_deg": 0.0, "signs": (1,)},
        {"pose_id": "positive_fold_roll", "q5_deg": 20.0, "q6_deg": 15.0, "signs": (1, -1)},
        {"pose_id": "negative_fold_roll", "q5_deg": -20.0, "q6_deg": -15.0, "signs": (1, -1)},
    )


def rotor_angle_deg(q5_deg: float, q6_deg: float, side_y: int, candidate_s: int) -> float:
    if type(side_y) is not int or side_y not in (-1, 1):
        raise ValueError("side_y must be -1 or +1")
    if type(candidate_s) is not int or candidate_s not in (-1, 1):
        raise ValueError("candidate_s must be -1 or +1")
    q5, q6 = _finite(q5_deg), _finite(q6_deg)
    if abs(q5) > 90 or abs(q6) > 90:
        raise ValueError("probe angles exceed the bounded analytical study")
    return _finite(q5 - side_y * candidate_s * 2 * q6)


def source_hashes(directory: Path) -> dict[str, str]:
    paths = sorted(path for path in directory.iterdir() if path.suffix.casefold() == ".fcstd")
    if not paths:
        raise ValueError("native source directory contains no documents")
    return {path.name: _sha(path) for path in paths}


def validate_inputs(source: Path, output: Path, isolation_root: Path) -> dict[str, str]:
    if not source.is_file() or source.name != "Assembly.FCStd":
        raise ValueError("source must be the compatible copied Assembly.FCStd")
    if output.exists() or output.suffix.lower() != ".json" or not output.parent.is_dir():
        raise ValueError("output must be a new JSON path in an existing directory")
    if not isolation_root.is_dir() or not output.resolve().is_relative_to(isolation_root.resolve()):
        raise ValueError("report must remain inside its existing isolated run root")
    if shutil.disk_usage(output.parent).free < 50 * 1024**3:
        raise ValueError("native probe requires at least 50 GiB free")
    observed = source_hashes(source.parent)
    if any(observed.get(name) != digest for name, digest in PINNED.items()):
        raise ValueError("selected wrist source hash differs from the immutable baseline")
    return observed


def within_budget(started: float, now: float, maximum_s: float = 600) -> None:
    values = tuple(_finite(value) for value in (started, now, maximum_s))
    if not 0 < values[2] <= 600 or values[1] < values[0] or values[1] - values[0] > values[2]:
        raise ValueError("native wrist diagnostic exceeded its bounded time budget")


def compare_rigid_fold(unfolded_mm3: float, folded_mm3: float) -> dict:
    before, after = _finite(unfolded_mm3), _finite(folded_mm3)
    if before < 0 or after < 0:
        raise ValueError("intersection volumes must be nonnegative")
    error = abs(before - after)
    limit = 1e-4 + 1e-6 * max(before, after)
    return {"volume_error_mm3": error, "numerical_limit_mm3": limit, "passed": error <= limit}


def report_is_complete(
    report: object,
    *,
    expected_worker_sha256: str | None = None,
    expected_helper_sha256: str | None = None,
) -> bool:
    """Check completion against actual capture pins; never qualify gear contact.

    Defaults bind to this worker/helper. Historical snapshots require their
    independently retained launch pins. Malformed or partial input returns False.
    """
    try:
        if not isinstance(report, dict):
            return False
        worker_pin = expected_worker_sha256 or _sha(Path(__file__))
        helper_pin = expected_helper_sha256 or _sha(
            Path(__file__).with_name("audit_freecad_assembly.py")
        )

        def digest(value):
            return (
                isinstance(value, str)
                and len(value) == 64
                and all(c in "0123456789abcdef" for c in value)
            )

        if (
            type(report.get("schema_version")) is not int
            or report["schema_version"] != 1
            or report.get("validation_class")
            != "native_saved_BRep_and_declared_rigid_pose_interference_diagnostic"
            or report.get("source_revision") != SOURCE_REVISION
            or report.get("coordinate_frame") != "native_CAD_world_mm"
            or report.get("source_geometry_mode")
            != "saved cached source BReps; no feature-history rebuild"
            or not digest(worker_pin)
            or not digest(helper_pin)
            or report.get("worker_sha256") != worker_pin
            or report.get("audit_helper_sha256") != helper_pin
            or report.get("audit_status") != "complete"
            or report.get("errors") != []
            or report.get("failed_native_operations", []) != []
            or report.get("source_bytes_unchanged") is not True
            or report.get("selected_document_placements_unchanged") is not True
            or type(report.get("boolean_operations_executed")) is not int
            or report["boolean_operations_executed"] != 14
        ):
            return False
        version = report["freecad_version"]
        if (
            not isinstance(version, list)
            or len(version) < 8
            or version[:3] != ["1", "1", "4"]
            or version[-1] != "4fd3bf320d9566a27e60069fc8387448aaa3a094"
        ):
            return False
        for flag in (
            "feature_history_recomputed",
            "constraint_kinematics_solved",
            "exact_conjugate_mesh_qualified",
            "physical_calibration_qualified",
            "source_document_saved",
            "jaw_loop_closure_evaluated",
            "contact_force_or_retention_qualified",
            "fabrication_released",
        ):
            if report.get(flag) is not False:
                return False
        before, after = report["source_sha256_before"], report["source_sha256_after"]
        if not isinstance(before, dict) or len(before) != 57 or before != after:
            return False
        if any(before.get(name) != value for name, value in PINNED.items()) or any(
            not digest(value) for value in before.values()
        ):
            return False
        isolation = report["runtime_isolation"]
        if (
            not isinstance(isolation, dict)
            or isolation.get("requested") is not True
            or isolation.get("verified") is not True
        ):
            return False
        root = isolation["root"]
        if not isinstance(root, str) or not root:
            return False
        path_type = (
            PureWindowsPath if "\\" in root or (len(root) > 1 and root[1] == ":") else PurePosixPath
        )
        parent = path_type(root)
        paths = isolation["actual_paths"]
        if (
            not parent.is_absolute()
            or not isinstance(paths, dict)
            or set(paths)
            != {"UserParameter", "SystemParameter", "UserHomePath", "UserAppData", "AppTempPath"}
        ):
            return False
        if any(
            not isinstance(value, str)
            or ".." in path_type(value).parts
            or not path_type(value).is_absolute()
            or not path_type(value).is_relative_to(parent)
            for value in paths.values()
        ):
            return False
        captured_plan = report["pose_plan"]
        if not isinstance(captured_plan, list) or len(captured_plan) != 3:
            return False
        for actual, planned in zip(captured_plan, pose_plan(), strict=True):
            if (
                not isinstance(actual, dict)
                or set(actual) != set(planned)
                or actual["pose_id"] != planned["pose_id"]
                or _finite(actual["q5_deg"]) != planned["q5_deg"]
                or _finite(actual["q6_deg"]) != planned["q6_deg"]
            ):
                return False
            if (
                not isinstance(actual["signs"], (tuple, list))
                or any(type(value) is not int for value in actual["signs"])
                or tuple(actual["signs"]) != planned["signs"]
            ):
                return False
        objects = report["objects"]
        if (
            not isinstance(objects, list)
            or len(objects) != 3
            or {row["object_reference"] for row in objects}
            != {"AssemblyArt56::" + name for name in NAMES}
        ):
            return False
        if any(
            row["source_shape_valid"] is not True
            or type(row["solid_count"]) is not int
            or row["solid_count"] < 1
            or _finite(row["volume_mm3"]) <= 0
            for row in objects
        ):
            return False
        expected = {
            (pose["pose_id"], sign, side): pose
            for pose in pose_plan()
            for sign in pose["signs"]
            for side in (-1, 1)
        }
        pairs = report["pose_pair_diagnostics"]
        if not isinstance(pairs, list) or len(pairs) != 10:
            return False
        observed = set()
        for row in pairs:
            key = (row["pose_id"], row["candidate_s"], row["side_y"])
            if key not in expected or key in observed:
                return False
            observed.add(key)
            pose = expected[key]
            configuration = (
                "saved_original"
                if pose["q5_deg"] == pose["q6_deg"] == 0
                else "declared_ideal_rigid_transform"
            )
            if (
                _finite(row["q5_deg"]) != pose["q5_deg"]
                or _finite(row["q6_deg"]) != pose["q6_deg"]
                or row["side_rotation_common_positive_y_deg"]
                != rotor_angle_deg(
                    pose["q5_deg"], pose["q6_deg"], row["side_y"], row["candidate_s"]
                )
                or row["configuration"] != configuration
                or row["distance_status"] != "complete"
                or _finite(row["minimum_distance_mm"]) < 0
                or _finite(row["intersection_volume_mm3"]) < 0
                or type(row["intersection_solid_count"]) is not int
                or row["intersection_solid_count"] < 0
            ):
                return False
        folds = report["rigid_fold_invariance"]
        if observed != set(expected) or not isinstance(folds, list) or len(folds) != 4:
            return False
        if {(row["pose_id"], row["side_y"]) for row in folds} != {
            (pose["pose_id"], side) for pose in pose_plan()[1:] for side in (-1, 1)
        }:
            return False
        for row in folds:
            if type(row["side_y"]) is not int or type(row["passed"]) is not bool:
                return False
            comparison = compare_rigid_fold(
                row["unfolded_intersection_mm3"], row["folded_intersection_mm3"]
            )
            if any(row[key] != value for key, value in comparison.items()):
                return False
        for optional_count in ("open_document_count_before", "open_document_count_after_close"):
            if optional_count in report and (
                type(report[optional_count]) is not int or report[optional_count] != 0
            ):
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        return False


def native_probe(source: Path, output: Path, isolation_root: Path) -> dict:
    """Read saved shapes, compute native Booleans on copies, checkpoint progress."""
    if os.environ.get("RAFTEL_RUN_FREECAD_AUDIT") == "1":
        raise ValueError(
            "conflicting generic native audit flag must be cleared before helper loading"
        )
    before = validate_inputs(source, output, isolation_root)
    import FreeCAD as App

    helper_path = Path(__file__).with_name("audit_freecad_assembly.py")
    helpers = runpy.run_path(str(helper_path))
    isolation = helpers["_runtime_isolation"](App, isolation_root)
    writer = helpers["ReportWriter"](output)
    started = time.monotonic()
    report = {
        "schema_version": 1,
        "validation_class": "native_saved_BRep_and_declared_rigid_pose_interference_diagnostic",
        "source_revision": SOURCE_REVISION,
        "coordinate_frame": "native_CAD_world_mm",
        "freecad_version": list(App.Version()),
        "runtime_isolation": isolation,
        "open_document_count_before": len(App.listDocuments()),
        "worker_sha256": _sha(Path(__file__)),
        "audit_helper_sha256": _sha(helper_path),
        "source_sha256_before": before,
        "source_sha256_after": {},
        "source_bytes_unchanged": False,
        "source_geometry_mode": "saved cached source BReps; no feature-history rebuild",
        "native_operations": (
            "selected shape validity, transformed copies, Boolean common, minimum distance"
        ),
        "pose_plan": list(pose_plan()),
        "objects": [],
        "pose_pair_diagnostics": [],
        "rigid_fold_invariance": [],
        "failed_native_operations": [],
        "boolean_operations_executed": 0,
        "feature_history_recomputed": False,
        "constraint_kinematics_solved": False,
        "source_document_saved": False,
        "selected_document_placements_unchanged": False,
        "exact_conjugate_mesh_qualified": False,
        "physical_calibration_qualified": False,
        "jaw_loop_closure_evaluated": False,
        "contact_force_or_retention_qualified": False,
        "fabrication_released": False,
        "audit_status": "in_progress",
        "errors": [],
    }
    writer(report)
    previous = set(App.listDocuments())
    selected_placements = {}
    document = None

    def checkpoint() -> None:
        report["elapsed_s"] = time.monotonic() - started
        writer(report)

    def bound() -> None:
        within_budget(started, time.monotonic())

    try:
        master = App.openDocument(str(source.resolve()), True)
        document = App.getDocument("AssemblyArt56")
        ancestor = master.getObject("AssemblyArt56").LinkPlacement
        shapes = []
        for name in NAMES:
            bound()
            obj = document.getObject(name)
            if obj is None:
                raise ValueError("selected wrist object is missing: " + name)
            selected_placements[name] = list(obj.Placement.toMatrix().A)
            shape = obj.Shape.copy()
            # Existing frame fixture: raw link Shape includes its own placement,
            # excluding this master ancestor. Never apply the link twice.
            shape.Placement = ancestor.multiply(shape.Placement)
            valid = (
                not shape.isNull() and bool(shape.Solids) and shape.Volume > 0 and shape.isValid()
            )
            report["objects"].append(
                {
                    "object_reference": "AssemblyArt56::" + name,
                    "saved_restore_state": list(obj.State),
                    "source_shape_valid": valid,
                    "solid_count": len(shape.Solids),
                    "volume_mm3": shape.Volume,
                    "world_bounds_mm": {key: getattr(shape.BoundBox, key) for key in BOUNDS},
                    "source_shape_matrix": list(shape.Placement.toMatrix().A),
                }
            )
            checkpoint()
            if not valid:
                raise ValueError("selected saved source shape is invalid: " + name)
            shapes.append(shape)
        origin = App.Vector(0, 0, 556)
        side_axis, roll_axis = App.Vector(0, 1, 0), App.Vector(0, 0, 1)

        def transformed(q5: float, q6: float, sign: int, index: int):
            shape = shapes[index].copy()
            if index == 0:
                shape.rotate(origin, side_axis, q5)
                carried_axis = App.Rotation(side_axis, q5).multVec(roll_axis)
                shape.rotate(origin, carried_axis, q6)
            else:
                side = -1 if index == 1 else 1
                shape.rotate(origin, side_axis, rotor_angle_deg(q5, q6, side, sign))
            return shape

        def intersection_volume(left, right, context: dict) -> tuple[float, int]:
            bound()
            common = left.common(right)
            report["boolean_operations_executed"] += 1
            volume = _finite(common.Volume)
            if volume < 0:
                report["failed_native_operations"].append(
                    {
                        **context,
                        "operation": "Boolean common",
                        "signed_volume_mm3": volume,
                        "solid_count": len(common.Solids),
                        "topology_validity_evaluated": False,
                        "topology_valid": None,
                    }
                )
                checkpoint()
                raise ValueError("native intersection reported a negative volume")
            return volume, len(common.Solids)

        for pose in pose_plan():
            q5, q6 = pose["q5_deg"], pose["q6_deg"]
            for sign in pose["signs"]:
                plate = transformed(q5, q6, sign, 0)
                for index, side in ((1, -1), (2, 1)):
                    rotor = transformed(q5, q6, sign, index)
                    context = {
                        "pose_id": pose["pose_id"],
                        "q5_deg": q5,
                        "q6_deg": q6,
                        "candidate_s": sign,
                        "side_y": side,
                    }
                    volume, solids = intersection_volume(plate, rotor, context)
                    pair = {
                        "pose_id": pose["pose_id"],
                        "configuration": "saved_original"
                        if q5 == q6 == 0
                        else "declared_ideal_rigid_transform",
                        "q5_deg": q5,
                        "q6_deg": q6,
                        "candidate_s": sign,
                        "side_y": side,
                        "side_rotation_common_positive_y_deg": rotor_angle_deg(q5, q6, side, sign),
                        "intersection_volume_mm3": volume,
                        "intersection_solid_count": solids,
                        "distance_status": "not_measured",
                        "minimum_distance_mm": None,
                        "nearest_witness_pairs_mm": [],
                        "interpretation": (
                            "zero distance can include penetration; no contact qualification"
                        ),
                    }
                    report["pose_pair_diagnostics"].append(pair)
                    checkpoint()
                    bound()
                    distance, points, _ = plate.distToShape(rotor)
                    pair.update(
                        distance_status="complete",
                        minimum_distance_mm=_finite(distance),
                        nearest_witness_pairs_mm=[[list(a), list(b)] for a, b in points[:4]],
                    )
                    checkpoint()
                    if sign == 1 and q5 != 0:
                        unfolded_plate = transformed(0, q6, sign, 0)
                        unfolded_rotor = transformed(0, q6, sign, index)
                        unfolded_volume, _ = intersection_volume(
                            unfolded_plate,
                            unfolded_rotor,
                            {**context, "comparison": "unfolded_same_roll"},
                        )
                        report["rigid_fold_invariance"].append(
                            {
                                "pose_id": pose["pose_id"],
                                "side_y": side,
                                "unfolded_intersection_mm3": unfolded_volume,
                                "folded_intersection_mm3": volume,
                                **compare_rigid_fold(unfolded_volume, volume),
                            }
                        )
                        checkpoint()
        report["selected_document_placements_unchanged"] = all(
            list(document.getObject(name).Placement.toMatrix().A) == value
            for name, value in selected_placements.items()
        )
        report["source_sha256_after"] = source_hashes(source.parent)
        report["source_bytes_unchanged"] = before == report["source_sha256_after"]
        report["audit_status"] = "complete"
        if not report_is_complete(report):
            raise ValueError("native wrist diagnostic did not satisfy its completion contract")
    except Exception as error:
        report["errors"].append(str(error))
        report["audit_status"] = "failed"
    finally:
        if not report["source_sha256_after"]:
            report["source_sha256_after"] = source_hashes(source.parent)
            report["source_bytes_unchanged"] = before == report["source_sha256_after"]
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
        report["open_document_count_after_close"] = len(App.listDocuments())
        if report["open_document_count_after_close"] != 0:
            report["errors"].append("native documents remain open after isolated cleanup")
            report["audit_status"] = "failed"
        checkpoint()
    print("RAFTEL_WRIST_POSE_REPORT", output, report["audit_status"])
    return report


if os.environ.get(FLAG) == "1":
    native_probe(
        Path(os.environ["RAFTEL_WRIST_POSE_SOURCE"]),
        Path(os.environ["RAFTEL_WRIST_POSE_REPORT"]),
        Path(os.environ["RAFTEL_WRIST_POSE_ISOLATION_ROOT"]),
    )
elif __name__ == "__main__":
    raise SystemExit(
        "Run only through an explicitly scheduled isolated native launcher; no process launched."
    )
