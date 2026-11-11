"""One guarded native common with exact topology ownership and debug BRep.

No process is launched here. Source documents are never saved. The exported
common is raw diagnostic data, not a repaired or manufacturing-ready asset.
"""

from __future__ import annotations

import importlib
import os
import runpy
import tempfile
import time
from pathlib import Path, PurePosixPath, PureWindowsPath


def reject_conflicting_environment() -> None:
    for name in (
        "RAFTEL_RUN_FREECAD_AUDIT",
        "RAFTEL_RUN_WRIST_POSE_DESKTOP",
        "RAFTEL_RUN_WRIST_FAILURE_PAIR",
    ):
        if os.environ.get(name) == "1":
            raise ValueError(
                "conflicting native worker flag before topology helper import: " + name
            )


reject_conflicting_environment()
pair = importlib.import_module("probe_thor_wrist_failure_pair")
FLAG = "RAFTEL_RUN_WRIST_COMMON_TOPOLOGY"
MEMBERSHIP_METHOD = "TopoShape.isSame, same topology and location; no nearest matching"


def _closed(shape) -> dict:
    method = getattr(shape, "isClosed", None)
    if not callable(method):
        return {
            "is_closed_evaluated": False,
            "is_closed": None,
            "is_closed_error": "method unavailable",
        }
    try:
        return {"is_closed_evaluated": True, "is_closed": bool(method()), "is_closed_error": None}
    except Exception as error:
        return {"is_closed_evaluated": False, "is_closed": None, "is_closed_error": str(error)}


def topology_membership(common) -> dict:
    """Record exact isSame membership; never substitute geometric proximity."""
    faces, shells, solids = list(common.Faces), list(common.Shells), list(common.Solids)
    if len(faces) > 10_000 or len(shells) > 1000 or len(solids) > 1000:
        raise ValueError("selected common topology exceeds diagnostic bounds")
    solid_faces = [list(solid.Faces) for solid in solids]
    solid_shells = [list(solid.Shells) for solid in solids]
    shell_faces = [list(shell.Faces) for shell in shells]

    def occurrences(children, whole, singular):
        return [
            {
                "local_" + singular + "_index": index,
                "common_" + singular + "_indices": [
                    i for i, candidate in enumerate(whole, 1) if child.isSame(candidate)
                ],
            }
            for index, child in enumerate(children, 1)
        ]

    face_rows = []
    for index, face in enumerate(faces, 1):
        owners = [
            i
            for i, children in enumerate(solid_faces, 1)
            if any(face.isSame(child) for child in children)
        ]
        face_rows.append(
            {
                "face_index": index,
                "orientation": str(face.Orientation),
                "surface_type": type(face.Surface).__name__,
                "area_mm2": pair.wrist._finite(face.Area),
                "solid_indices": owners,
                "shell_indices": [
                    i
                    for i, children in enumerate(shell_faces, 1)
                    if any(face.isSame(child) for child in children)
                ],
                "owned_by_any_solid": bool(owners),
            }
        )
    shell_rows = []
    for index, shell in enumerate(shells, 1):
        shell_rows.append(
            {
                "shell_index": index,
                "orientation": str(shell.Orientation),
                "face_count": len(shell_faces[index - 1]),
                "face_occurrences": occurrences(shell_faces[index - 1], faces, "face"),
                "common_face_indices": [
                    row["face_index"] for row in face_rows if index in row["shell_indices"]
                ],
                "solid_indices": [
                    i
                    for i, children in enumerate(solid_shells, 1)
                    if any(shell.isSame(child) for child in children)
                ],
                **_closed(shell),
            }
        )
    solid_rows = []
    for index, solid in enumerate(solids, 1):
        solid_rows.append(
            {
                "solid_index": index,
                "orientation": str(solid.Orientation),
                "signed_volume_mm3": pair.wrist._finite(solid.Volume),
                "face_count": len(solid_faces[index - 1]),
                "shell_count": len(solid_shells[index - 1]),
                "face_occurrences": occurrences(solid_faces[index - 1], faces, "face"),
                "shell_occurrences": occurrences(solid_shells[index - 1], shells, "shell"),
                "common_face_indices": [
                    row["face_index"] for row in face_rows if index in row["solid_indices"]
                ],
                "common_shell_indices": [
                    row["shell_index"] for row in shell_rows if index in row["solid_indices"]
                ],
                **_closed(solid),
            }
        )
    return {
        "membership_method": MEMBERSHIP_METHOD,
        "faces": face_rows,
        "shells": shell_rows,
        "solids": solid_rows,
        "unowned_common_face_indices": [
            row["face_index"] for row in face_rows if not row["solid_indices"]
        ],
        "unowned_common_shell_indices": [
            row["shell_index"] for row in shell_rows if not row["solid_indices"]
        ],
        "standalone_membership_observed": True,
        "negative_aggregate_cause_proven": False,
    }


def export_debug_brep(common, destination: Path, isolation_root: Path) -> dict:
    """One native export into private scratch, then exclusive byte-preserving retention."""
    root = isolation_root.resolve()
    if destination.exists() or destination.is_symlink() or destination.suffix.casefold() != ".brep":
        raise ValueError("raw common BRep must use a new .brep path")
    if not destination.parent.is_dir() or not destination.resolve().is_relative_to(root):
        raise ValueError("debug BRep must stay inside the isolated run")
    with tempfile.TemporaryDirectory(prefix=".common-brep-", dir=root) as directory:
        scratch = Path(directory).resolve()
        if not scratch.is_relative_to(root):
            raise ValueError("private debug export escaped isolated root")
        temporary = scratch / "common.brep"
        common.exportBrep(str(temporary))
        if not temporary.is_file() or not 0 < temporary.stat().st_size <= 128 * 1024**2:
            raise ValueError("native debug BRep export is empty or exceeds its bound")
        with temporary.open("rb") as stream:
            raw = stream.read(128 * 1024**2 + 1)
        if len(raw) > 128 * 1024**2:
            raise ValueError("debug BRep changed beyond its byte bound")
        with destination.open("xb") as stream:
            stream.write(raw)
    return {
        "path": str(destination.resolve()),
        "sha256": pair.wrist._sha(destination),
        "bytes": len(raw),
        "native_export_calls": 1,
        "exported_object": "unaltered Boolean common",
        "diagnostic_only": True,
        "CAD_document_saved": False,
        "manufacturing_release": False,
    }


def capture_is_complete(
    report: object,
    *,
    expected_source_sha256: dict,
    expected_worker_sha256: str | None = None,
    expected_pair_helper_sha256: str | None = None,
    expected_wrist_helper_sha256: str | None = None,
    expected_audit_helper_sha256: str | None = None,
) -> bool:
    """Extend the accepted one-pair measurement contract without relaxing it."""
    try:
        if (
            not isinstance(report, dict)
            or report.get("validation_class")
            != "native_common_topology_membership_debug_BRep_diagnostic"
        ):
            return False
        pair_pin = expected_pair_helper_sha256 or pair.wrist._sha(Path(pair.__file__))
        if report.get("pair_helper_sha256") != pair_pin or not pair._digest(pair_pin):
            return False
        projected = {**report, "validation_class": "native_single_Boolean_signed_result_diagnostic"}
        if not pair.capture_is_complete(
            projected,
            expected_source_sha256=expected_source_sha256,
            expected_worker_sha256=expected_worker_sha256 or pair.wrist._sha(Path(__file__)),
            expected_wrist_helper_sha256=expected_wrist_helper_sha256,
            expected_audit_helper_sha256=expected_audit_helper_sha256,
        ):
            return False
        topology = report["topology"]
        if topology.get("membership_method") != MEMBERSHIP_METHOD:
            return False
        common = report["common"]
        for key, count in (
            ("faces", "face_count"),
            ("shells", "shell_count"),
            ("solids", "solid_count"),
        ):
            if not isinstance(topology[key], list) or len(topology[key]) != common[count]:
                return False
        faces, shells, solids = topology["faces"], topology["shells"], topology["solids"]
        if any(
            type(row[key]) is not int
            for rows, key in (
                (faces, "face_index"),
                (shells, "shell_index"),
                (solids, "solid_index"),
            )
            for row in rows
        ):
            return False

        def indices(values, maximum):
            return (
                isinstance(values, list)
                and all(type(value) is int and 1 <= value <= maximum for value in values)
                and values == sorted(set(values))
            )

        def closed_state(row):
            if type(row["is_closed_evaluated"]) is not bool:
                return False
            if row["is_closed_evaluated"]:
                return type(row["is_closed"]) is bool and row["is_closed_error"] is None
            return (
                row["is_closed"] is None
                and isinstance(row["is_closed_error"], str)
                and bool(row["is_closed_error"])
            )

        def occurrence_union(rows, count, singular, maximum):
            if (
                type(count) is not int
                or not 0 <= count <= 1_000_000
                or not isinstance(rows, list)
                or len(rows) != count
            ):
                return None
            result = set()
            for expected, row in enumerate(rows, 1):
                index = row["local_" + singular + "_index"]
                members = row["common_" + singular + "_indices"]
                if (
                    type(index) is not int
                    or index != expected
                    or not indices(members, maximum)
                    or not members
                ):
                    return None
                result.update(members)
            return sorted(result)

        if (
            [row["face_index"] for row in faces] != list(range(1, len(faces) + 1))
            or [row["shell_index"] for row in shells] != list(range(1, len(shells) + 1))
            or [row["solid_index"] for row in solids] != list(range(1, len(solids) + 1))
        ):
            return False
        for face in faces:
            owners = face["solid_indices"]
            if not indices(owners, len(solids)) or not indices(face["shell_indices"], len(shells)):
                return False
            if (
                face["owned_by_any_solid"] is not bool(owners)
                or pair.wrist._finite(face["area_mm2"]) < 0
            ):
                return False
            if not isinstance(face["surface_type"], str) or not face["surface_type"]:
                return False
            if face["orientation"] not in {"Forward", "Reversed", "Internal", "External"}:
                return False
        for shell in shells:
            if not indices(shell["solid_indices"], len(solids)) or not closed_state(shell):
                return False
            if shell["orientation"] not in {"Forward", "Reversed", "Internal", "External"}:
                return False
            if shell["common_face_indices"] != [
                face["face_index"]
                for face in faces
                if shell["shell_index"] in face["shell_indices"]
            ]:
                return False
            if (
                occurrence_union(shell["face_occurrences"], shell["face_count"], "face", len(faces))
                != shell["common_face_indices"]
            ):
                return False
            for face_index in shell["common_face_indices"]:
                if not set(shell["solid_indices"]) <= set(faces[face_index - 1]["solid_indices"]):
                    return False
        for solid in solids:
            if solid["common_face_indices"] != [
                face["face_index"]
                for face in faces
                if solid["solid_index"] in face["solid_indices"]
            ]:
                return False
            if solid["common_shell_indices"] != [
                shell["shell_index"]
                for shell in shells
                if solid["solid_index"] in shell["solid_indices"]
            ] or not closed_state(solid):
                return False
            if (
                occurrence_union(solid["face_occurrences"], solid["face_count"], "face", len(faces))
                != solid["common_face_indices"]
                or occurrence_union(
                    solid["shell_occurrences"], solid["shell_count"], "shell", len(shells)
                )
                != solid["common_shell_indices"]
            ):
                return False
            saved_solid = common["solids"][solid["solid_index"] - 1]
            if (
                pair.wrist._finite(solid["signed_volume_mm3"]) != saved_solid["signed_volume_mm3"]
                or solid["orientation"] != saved_solid["orientation"]
            ):
                return False
        if topology["unowned_common_face_indices"] != [
            face["face_index"] for face in faces if not face["solid_indices"]
        ] or topology["unowned_common_shell_indices"] != [
            shell["shell_index"] for shell in shells if not shell["solid_indices"]
        ]:
            return False
        if (
            topology.get("standalone_membership_observed") is not True
            or topology.get("negative_aggregate_cause_proven") is not False
        ):
            return False
        exported = report["debug_BRep"]
        root = report["runtime_isolation"]["root"]
        path_type = (
            PureWindowsPath if "\\" in root or (len(root) > 1 and root[1] == ":") else PurePosixPath
        )
        path = exported["path"]
        if (
            not isinstance(path, str)
            or not path_type(path).is_absolute()
            or ".." in path_type(path).parts
            or not path_type(path).is_relative_to(path_type(root))
            or path_type(path).name != "common-debug.brep"
        ):
            return False
        return (
            pair._digest(exported["sha256"])
            and type(exported["bytes"]) is int
            and 0 < exported["bytes"] <= 128 * 1024**2
            and exported["exported_object"] == "unaltered Boolean common"
            and type(exported["native_export_calls"]) is int
            and exported["native_export_calls"] == 1
            and exported["diagnostic_only"] is True
            and exported["CAD_document_saved"] is False
            and exported["manufacturing_release"] is False
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        return False


def native_probe(
    source: Path, output: Path, isolation_root: Path, *, launch_context: dict | None = None
) -> dict:
    reject_conflicting_environment()
    before = pair.wrist.validate_inputs(source, output, isolation_root)
    import FreeCAD as App

    helper_path = Path(__file__).with_name("audit_freecad_assembly.py")
    helpers = runpy.run_path(str(helper_path))
    isolation = helpers["_runtime_isolation"](App, isolation_root)
    writer = helpers["ReportWriter"](output)
    started = time.monotonic()
    report = {
        "schema_version": 1,
        "validation_class": "native_common_topology_membership_debug_BRep_diagnostic",
        "source_revision": pair.wrist.SOURCE_REVISION,
        "coordinate_frame": "native_CAD_world_mm",
        "source_geometry_mode": "saved cached BReps and declared rigid copied-shape pose",
        "freecad_version": list(App.Version()),
        "runtime_isolation": isolation,
        "launch_context": dict(launch_context or {}),
        "worker_sha256": pair.wrist._sha(Path(__file__)),
        "pair_helper_sha256": pair.wrist._sha(Path(pair.__file__)),
        "wrist_helper_sha256": pair.wrist._sha(Path(pair.wrist.__file__)),
        "audit_helper_sha256": pair.wrist._sha(helper_path),
        "source_sha256_before": before,
        "source_sha256_after": {},
        "source_bytes_unchanged": False,
        "pose": dict(pair.POSE),
        "inputs": [],
        "common": None,
        "topology": None,
        "debug_BRep": None,
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
        pair.wrist.within_budget(started, time.monotonic(), 180)

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
            obj = document.getObject(pair.wrist.NAMES[index])
            shape = obj.Shape.copy()
            shape.Placement = ancestor.multiply(shape.Placement)
            saved = pair.shape_metrics(shape)
            saved.update(valid=bool(shape.isValid()), validity_evaluated=True)
            if index == 0:
                shape.rotate(origin, fold_axis, pair.POSE["q5_deg"])
                shape.rotate(
                    origin,
                    App.Rotation(fold_axis, pair.POSE["q5_deg"]).multVec(roll_axis),
                    pair.POSE["q6_deg"],
                )
            else:
                shape.rotate(origin, fold_axis, pair.POSE["rotor_deg"])
            posed = pair.shape_metrics(shape)
            record = {
                "object_reference": "AssemblyArt56::" + pair.wrist.NAMES[index],
                "saved_restore_state": list(obj.State),
                "saved": saved,
                "posed": posed,
            }
            report["inputs"].append(record)
            checkpoint()
            bound()
            posed.update(valid=bool(shape.isValid()), validity_evaluated=True)
            if not pair._metrics_complete(saved, material_input=True) or not pair._metrics_complete(
                posed, material_input=True
            ):
                raise ValueError(
                    "source/posed inputs do not satisfy the unchanged positive-solid contract"
                )
            shapes.append(shape)
        bound()
        common = shapes[0].common(shapes[1])
        report["boolean_operations_executed"] = 1
        report["common"] = pair.shape_metrics(common)
        checkpoint()
        bound()
        report["common"].update(valid=bool(common.isValid()), validity_evaluated=True)
        report["diagnostic_outcome"] = pair.signed_result_classification(
            report["common"]["signed_volume_mm3"]
        )
        checkpoint()
        bound()
        report["topology"] = topology_membership(common)
        checkpoint()
        bound()
        report["debug_BRep"] = export_debug_brep(
            common, isolation_root / "common-debug.brep", isolation_root
        )
        report["audit_status"] = "complete"
    except Exception as error:
        report["errors"].append(str(error))
        report["audit_status"] = "failed"
    finally:
        report["source_sha256_after"] = pair.wrist.source_hashes(source.parent)
        report["source_bytes_unchanged"] = before == report["source_sha256_after"]
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
        report["open_document_count_after_close"] = len(App.listDocuments())
        if report["open_document_count_after_close"] != 0 or not report["source_bytes_unchanged"]:
            report["errors"].append("source/isolation preservation failed")
            report["audit_status"] = "failed"
        checkpoint()
    print("RAFTEL_WRIST_COMMON_TOPOLOGY", output, report["audit_status"])
    return report


if os.environ.get(FLAG) == "1":
    native_probe(
        Path(os.environ["RAFTEL_WRIST_TOPOLOGY_SOURCE"]),
        Path(os.environ["RAFTEL_WRIST_TOPOLOGY_REPORT"]),
        Path(os.environ["RAFTEL_WRIST_TOPOLOGY_ISOLATION_ROOT"]),
    )
elif __name__ == "__main__":
    raise SystemExit("ROOT native slot and isolated launcher required; no process launched.")
