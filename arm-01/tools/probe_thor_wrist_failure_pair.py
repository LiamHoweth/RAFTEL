"""One scheduled native wrist-common diagnostic, preserving signed results.

No native process is launched by this module. It requires the integration
owner's isolated slot, fresh output path and an outer timeout of at most 180s.
It never reverses/heals a shape or turns a negative volume into material.
"""

from __future__ import annotations

import importlib
import os
import runpy
import time
from pathlib import Path, PurePosixPath, PureWindowsPath


def reject_conflicting_environment() -> None:
    for name in ("RAFTEL_RUN_FREECAD_AUDIT", "RAFTEL_RUN_WRIST_POSE_DESKTOP"):
        if os.environ.get(name) == "1":
            raise ValueError(
                "conflicting native worker flag must be cleared before helper import: " + name
            )


def _load_wrist_helper():
    reject_conflicting_environment()
    return importlib.import_module("probe_thor_wrist_pose_desktop")


wrist = _load_wrist_helper()

FLAG = "RAFTEL_RUN_WRIST_FAILURE_PAIR"
POSE = {"q5_deg": -20.0, "q6_deg": -15.0, "candidate_s": 1, "side_y": 1, "rotor_deg": 10.0}


def signed_result_classification(volume_mm3: float) -> str:
    value = wrist._finite(volume_mm3)
    if value < 0:
        return "negative_signed_volume_reproduced"
    return "negative_signed_volume_not_reproduced"


def shape_metrics(shape) -> dict:
    """Capture existing shape properties, with no orientation repair or abs()."""
    signed = wrist._finite(shape.Volume)
    return {
        "signed_volume_mm3": signed,
        "shape_type": str(shape.ShapeType),
        "orientation": str(shape.Orientation),
        "null_shape": bool(shape.isNull()),
        "solid_count": len(shape.Solids),
        "shell_count": len(shape.Shells),
        "face_count": len(shape.Faces),
        "solids": [
            {
                "signed_volume_mm3": wrist._finite(solid.Volume),
                "orientation": str(solid.Orientation),
            }
            for solid in shape.Solids
        ],
        "validity_evaluated": False,
        "valid": None,
    }


def _digest(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def _metrics_complete(value: object, *, material_input: bool) -> bool:
    if not isinstance(value, dict):
        return False
    try:
        volume = wrist._finite(value["signed_volume_mm3"])
        if (
            value["orientation"] not in {"Forward", "Reversed", "Internal", "External"}
            or not isinstance(value["shape_type"], str)
            or not value["shape_type"]
        ):
            return False
        if (
            type(value["null_shape"]) is not bool
            or value["validity_evaluated"] is not True
            or type(value["valid"]) is not bool
        ):
            return False
        for count in ("solid_count", "shell_count", "face_count"):
            if type(value[count]) is not int or not 0 <= value[count] <= 1_000_000:
                return False
        solids = value["solids"]
        if not isinstance(solids, list) or len(solids) != value["solid_count"]:
            return False
        for solid in solids:
            wrist._finite(solid["signed_volume_mm3"])
            if solid["orientation"] not in {"Forward", "Reversed", "Internal", "External"}:
                return False
        if material_input and (
            volume <= 0
            or value["null_shape"]
            or value["solid_count"] < 1
            or value["valid"] is not True
        ):
            return False
        return True
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def capture_is_complete(
    report: object,
    *,
    expected_source_sha256: dict | None = None,
    expected_worker_sha256: str | None = None,
    expected_wrist_helper_sha256: str | None = None,
    expected_audit_helper_sha256: str | None = None,
) -> bool:
    """Check diagnostic coverage against independently retained launch bindings.

    Negative/invalid common results remain complete observations, never accepted
    material. Full expected source bindings are mandatory; code pins default to
    current files and may explicitly bind a retained historical snapshot.
    """
    try:
        if (
            not isinstance(report, dict)
            or not isinstance(expected_source_sha256, dict)
            or len(expected_source_sha256) != 57
        ):
            return False
        if any(
            not isinstance(name, str)
            or not name.casefold().endswith(".fcstd")
            or "/" in name
            or "\\" in name
            or not _digest(value)
            for name, value in expected_source_sha256.items()
        ):
            return False
        if any(expected_source_sha256.get(name) != value for name, value in wrist.PINNED.items()):
            return False
        pins = {
            "worker_sha256": expected_worker_sha256 or wrist._sha(Path(__file__)),
            "wrist_helper_sha256": expected_wrist_helper_sha256 or wrist._sha(Path(wrist.__file__)),
            "audit_helper_sha256": expected_audit_helper_sha256
            or wrist._sha(Path(__file__).with_name("audit_freecad_assembly.py")),
        }
        if any(not _digest(value) or report.get(key) != value for key, value in pins.items()):
            return False
        if (
            type(report.get("schema_version")) is not int
            or report["schema_version"] != 1
            or report.get("validation_class") != "native_single_Boolean_signed_result_diagnostic"
            or report.get("source_revision") != wrist.SOURCE_REVISION
            or report.get("coordinate_frame") != "native_CAD_world_mm"
            or report.get("source_geometry_mode")
            != "saved cached BReps and declared rigid copied-shape pose"
            or report.get("audit_status") != "complete"
            or report.get("errors") != []
            or report.get("source_bytes_unchanged") is not True
            or report.get("source_sha256_before") != expected_source_sha256
            or report.get("source_sha256_after") != expected_source_sha256
            or type(report.get("boolean_operations_executed")) is not int
            or report["boolean_operations_executed"] != 1
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
        pose = report["pose"]
        if not isinstance(pose, dict) or set(pose) != set(POSE):
            return False
        for key in ("q5_deg", "q6_deg", "rotor_deg"):
            if wrist._finite(pose[key]) != POSE[key]:
                return False
        for key in ("candidate_s", "side_y"):
            if type(pose[key]) is not int or pose[key] != POSE[key]:
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
        for key in ("open_document_count_before", "open_document_count_after_close"):
            if type(report.get(key)) is not int or report[key] != 0:
                return False
        inputs = report["inputs"]
        if (
            not isinstance(inputs, list)
            or len(inputs) != 2
            or [row["object_reference"] for row in inputs]
            != ["AssemblyArt56::" + wrist.NAMES[index] for index in (0, 2)]
        ):
            return False
        for row in inputs:
            if not _metrics_complete(row["saved"], material_input=True) or not _metrics_complete(
                row["posed"], material_input=True
            ):
                return False
            if not isinstance(row["saved_restore_state"], list) or any(
                not isinstance(value, str) for value in row["saved_restore_state"]
            ):
                return False
        if not _metrics_complete(report["common"], material_input=False):
            return False
        return report["diagnostic_outcome"] == signed_result_classification(
            report["common"]["signed_volume_mm3"]
        ) and all(
            report.get(flag) is False
            for flag in (
                "absolute_volume_substituted",
                "shape_reversed_or_healed",
                "source_saved",
                "feature_history_recomputed",
                "constraint_kinematics_solved",
                "geometric_intersection_accepted",
                "exact_conjugate_mesh_qualified",
                "physical_calibration_qualified",
                "fabrication_released",
            )
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        return False


def native_probe(source: Path, output: Path, isolation_root: Path) -> dict:
    reject_conflicting_environment()
    before = wrist.validate_inputs(source, output, isolation_root)
    import FreeCAD as App

    helpers = runpy.run_path(str(Path(__file__).with_name("audit_freecad_assembly.py")))
    isolation = helpers["_runtime_isolation"](App, isolation_root)
    writer = helpers["ReportWriter"](output)
    started = time.monotonic()
    report = {
        "schema_version": 1,
        "validation_class": "native_single_Boolean_signed_result_diagnostic",
        "source_revision": wrist.SOURCE_REVISION,
        "coordinate_frame": "native_CAD_world_mm",
        "freecad_version": list(App.Version()),
        "runtime_isolation": isolation,
        "worker_sha256": wrist._sha(Path(__file__)),
        "wrist_helper_sha256": wrist._sha(Path(wrist.__file__)),
        "audit_helper_sha256": wrist._sha(Path(__file__).with_name("audit_freecad_assembly.py")),
        "source_sha256_before": before,
        "source_sha256_after": {},
        "source_bytes_unchanged": False,
        "pose": dict(POSE),
        "source_geometry_mode": "saved cached BReps and declared rigid copied-shape pose",
        "inputs": [],
        "common": None,
        "boolean_operations_executed": 0,
        "diagnostic_outcome": None,
        "absolute_volume_substituted": False,
        "shape_reversed_or_healed": False,
        "source_saved": False,
        "feature_history_recomputed": False,
        "constraint_kinematics_solved": False,
        "geometric_intersection_accepted": False,
        "exact_conjugate_mesh_qualified": False,
        "physical_calibration_qualified": False,
        "fabrication_released": False,
        "open_document_count_before": len(App.listDocuments()),
        "audit_status": "in_progress",
        "errors": [],
    }
    previous = set(App.listDocuments())

    def checkpoint():
        report["elapsed_s"] = time.monotonic() - started
        writer(report)

    def bound():
        wrist.within_budget(started, time.monotonic(), 180)

    checkpoint()
    try:
        master = App.openDocument(str(source.resolve()), True)
        document = App.getDocument("AssemblyArt56")
        ancestor = master.getObject("AssemblyArt56").LinkPlacement
        origin, fold_axis, roll_axis = (
            App.Vector(0, 0, 556),
            App.Vector(0, 1, 0),
            App.Vector(0, 0, 1),
        )
        shapes = []
        for index in (0, 2):
            bound()
            obj = document.getObject(wrist.NAMES[index])
            shape = obj.Shape.copy()
            shape.Placement = ancestor.multiply(shape.Placement)
            saved = shape_metrics(shape)
            saved["valid"] = bool(shape.isValid())
            saved["validity_evaluated"] = True
            if index == 0:
                shape.rotate(origin, fold_axis, POSE["q5_deg"])
                carried_axis = App.Rotation(fold_axis, POSE["q5_deg"]).multVec(roll_axis)
                shape.rotate(origin, carried_axis, POSE["q6_deg"])
            else:
                shape.rotate(origin, fold_axis, POSE["rotor_deg"])
            posed = shape_metrics(shape)
            record = {
                "object_reference": "AssemblyArt56::" + wrist.NAMES[index],
                "saved_restore_state": list(obj.State),
                "saved": saved,
                "posed": posed,
            }
            report["inputs"].append(record)
            checkpoint()
            bound()
            posed["valid"] = bool(shape.isValid())
            posed["validity_evaluated"] = True
            checkpoint()
            if (
                not saved["valid"]
                or not posed["valid"]
                or saved["signed_volume_mm3"] <= 0
                or posed["signed_volume_mm3"] <= 0
            ):
                raise ValueError(
                    "source/rigidly posed input must be valid with positive signed volume"
                )
            shapes.append(shape)
        bound()
        common = shapes[0].common(shapes[1])
        report["boolean_operations_executed"] = 1
        report["common"] = shape_metrics(common)
        # Preserve the signed result and orientation BEFORE expensive validity.
        checkpoint()
        bound()
        report["common"]["valid"] = bool(common.isValid())
        report["common"]["validity_evaluated"] = True
        report["diagnostic_outcome"] = signed_result_classification(
            report["common"]["signed_volume_mm3"]
        )
        report["audit_status"] = "complete"
        checkpoint()
    except Exception as error:
        report["errors"].append(str(error))
        report["audit_status"] = "failed"
    finally:
        report["source_sha256_after"] = wrist.source_hashes(source.parent)
        report["source_bytes_unchanged"] = before == report["source_sha256_after"]
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
        report["open_document_count_after_close"] = len(App.listDocuments())
        if report["open_document_count_after_close"] != 0 or not report["source_bytes_unchanged"]:
            report["errors"].append("source/isolated cleanup preservation failed")
            report["audit_status"] = "failed"
        checkpoint()
    print("RAFTEL_WRIST_FAILURE_PAIR", output, report["audit_status"], report["diagnostic_outcome"])
    return report


if os.environ.get(FLAG) == "1":
    native_probe(
        Path(os.environ["RAFTEL_WRIST_FAILURE_SOURCE"]),
        Path(os.environ["RAFTEL_WRIST_FAILURE_REPORT"]),
        Path(os.environ["RAFTEL_WRIST_FAILURE_ISOLATION_ROOT"]),
    )
elif __name__ == "__main__":
    raise SystemExit("Native slot approval and isolated launcher required; no process launched.")
