"""Inspect native CAD in a dedicated FreeCAD console process without saving.

Opt in with RAFTEL_RUN_FREECAD_AUDIT=1, set RAFTEL_FREECAD_ASSEMBLY and a new
RAFTEL_FREECAD_REPORT .json path. RECOMPUTE defaults to ``none`` (restore/cache
inspection); ``changed`` and ``force`` explicitly request feature recomputation.
SHAPE_SCOPE defaults to ``terminal``; use ``all`` or ``none`` as needed.
VALIDATE_SHAPES=1 enables potentially expensive native topology checks.
CHECKPOINT_INTERVAL_S defaults to 2 seconds for object events; document and
recompute boundaries always flush. Completed observations stay in the final report.
All optional names have the RAFTEL_FREECAD_ prefix. DOCUMENTS/OBJECTS accept
comma-separated names; object selectors can be qualified as Document::Object.
Use a source working copy and an outer timeout. This script cannot interrupt a
blocked native operation, but atomic checkpoints preserve completed evidence.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _source_guard(assembly: Path) -> None:
    if not assembly.is_file() or assembly.suffix.casefold() != ".fcstd":
        raise ValueError("assembly must be an existing native FreeCAD document")


def _runtime_isolation(app, root: Path | None) -> dict:
    """Check the actual native paths before opening any requested document."""
    if root is None:
        return {"requested": False, "verified": False}
    root = root.resolve()
    values = {
        key: app.ConfigGet(key)
        for key in (
            "UserParameter",
            "SystemParameter",
            "UserHomePath",
            "UserAppData",
            "AppTempPath",
        )
    }
    if any(
        not value or not Path(value).resolve().is_relative_to(root) for value in values.values()
    ):
        raise ValueError("native configuration/data path escaped the task isolation root")
    if app.listDocuments():
        raise ValueError("isolated audit requires a fresh process without open documents")
    return {"requested": True, "verified": True, "root": str(root), "actual_paths": values}


class ReportWriter:
    """Own a newly created report path; replace only our own checkpoints."""

    def __init__(self, output: Path):
        if output.suffix.lower() != ".json" or output.exists():
            raise ValueError(
                "report must be a new .json path; existing files are never overwritten"
            )
        self.output = output
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write('{"status":"starting"}\n')
            stream.flush()
            os.fsync(stream.fileno())
        self.identity = (output.stat().st_dev, output.stat().st_ino)

    def __call__(self, report: dict) -> None:
        current = self.output.lstat()
        if (current.st_dev, current.st_ino) != self.identity or self.output.is_symlink():
            raise RuntimeError("report ownership changed; refusing to replace another file")
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{self.output.name}.",
                suffix=".tmp",
                dir=self.output.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(report, stream, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            # Recheck after serialization, before replacing the owned report.
            current = self.output.lstat()
            if (current.st_dev, current.st_ino) != self.identity or self.output.is_symlink():
                raise RuntimeError("report ownership changed during checkpoint")
            os.replace(temporary, self.output)
            temporary = None
            current = self.output.stat()
            self.identity = (current.st_dev, current.st_ino)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def _reference(obj) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, tuple):
        obj = obj[0] if obj else None
    if obj is None:
        return None
    document = getattr(getattr(obj, "Document", None), "Name", None)
    name = getattr(obj, "Name", None)
    return f"{document}::{name}" if document and name else str(obj)


def _placement(value) -> dict:
    matrix = value.toMatrix()
    return {
        "translation_mm": [value.Base.x, value.Base.y, value.Base.z],
        "quaternion_xyzw": list(value.Rotation.Q),
        "matrix": [
            [getattr(matrix, f"A{row}{column}") for column in range(1, 5)] for row in range(1, 5)
        ],
    }


def _object_metadata(obj) -> dict:
    item = {"name": obj.Name, "label": obj.Label, "type": obj.TypeId, "state": list(obj.State)}
    errors = []
    for property_name, key in (("Placement", "placement"), ("LinkPlacement", "link_placement")):
        if hasattr(obj, property_name):
            try:
                item[key] = _placement(getattr(obj, property_name))
            except Exception as error:
                errors.append(f"{property_name}: {error}")
    if hasattr(obj, "getGlobalPlacement"):
        try:
            item["global_placement"] = _placement(obj.getGlobalPlacement())
        except Exception as error:
            errors.append(f"getGlobalPlacement: {error}")
    for property_name, key in (("Visibility", "visibility"), ("LinkTransform", "link_transform")):
        if hasattr(obj, property_name):
            try:
                item[key] = bool(getattr(obj, property_name))
            except Exception as error:
                errors.append(f"{property_name}: {error}")
    for property_name, key in (("Tip", "body_tip"), ("LinkedObject", "linked_object")):
        if hasattr(obj, property_name):
            try:
                item[key] = _reference(getattr(obj, property_name))
            except Exception as error:
                errors.append(f"{property_name}: {error}")
    if hasattr(obj, "getLinkedObject"):
        try:
            item["linked_object_direct"] = _reference(obj.getLinkedObject(False))
        except Exception as error:
            errors.append(f"getLinkedObject: {error}")
    for property_name, key in (
        ("Group", "group_members"),
        ("InList", "in_list"),
        ("OutList", "out_list"),
    ):
        if hasattr(obj, property_name):
            try:
                item[key] = [_reference(child) for child in getattr(obj, property_name)]
            except Exception as error:
                errors.append(f"{property_name}: {error}")
    if errors:
        item["metadata_errors"] = errors
    return item


def _is_terminal(obj) -> bool:
    if obj.TypeId == "PartDesign::Body":
        return True
    if obj.TypeId == "App::Link":
        # Assembly/group links can aggregate hundreds of repeated solids. Their
        # shape is neither a leaf part nor useful for a nonduplicated mass sum.
        # Preserve link/tree/placement metadata, inspect source Bodies and true
        # leaf links instead of repeatedly calculating assembly compounds.
        try:
            target = obj.getLinkedObject(True)
        except Exception:
            return False
        if target is None or target is obj:
            return False
        if target.TypeId in {
            "App::Part",
            "App::DocumentObjectGroup",
            "App::DocumentObjectGroupPython",
        }:
            return False
        if hasattr(target, "isDerivedFrom") and target.isDerivedFrom("App::DocumentObjectGroup"):
            return False
        return True
    if not hasattr(obj, "isDerivedFrom") or not obj.isDerivedFrom("Part::Feature"):
        return False
    # Exclude consumed construction/history features. App::Part grouping alone
    # is not consumption; Bodies and Links are explicitly represented above.
    return not any(
        parent.TypeId == "PartDesign::Body"
        or (
            hasattr(parent, "isDerivedFrom")
            and parent.isDerivedFrom("Part::Feature")
            and not parent.isDerivedFrom("Part::Datum")
        )
        for parent in getattr(obj, "InList", [])
    )


def _shape_metadata(obj, item: dict, validate_shapes: bool) -> None:
    if not hasattr(obj, "Shape"):
        return
    errors = []
    try:
        shape = obj.Shape
        item["shape_null"] = shape.isNull()
        if shape.isNull():
            return
    except Exception as error:
        item["shape_error"] = str(error)
        return
    # Independent reads retain valid bounds/volume even when a generic
    # TopoShape cannot supply CenterOfMass or another optional property.
    try:
        box = shape.BoundBox
        item["bounds_mm"] = {
            "xmin": box.XMin,
            "xmax": box.XMax,
            "ymin": box.YMin,
            "ymax": box.YMax,
            "zmin": box.ZMin,
            "zmax": box.ZMax,
        }
    except Exception as error:
        errors.append(f"bounds: {error}")
    try:
        item["volume_mm3"] = shape.Volume
    except Exception as error:
        errors.append(f"volume: {error}")
    try:
        solids = list(shape.Solids)
        item["solid_count"] = len(solids)
    except Exception as error:
        solids = []
        errors.append(f"solids: {error}")
    try:
        center = shape.CenterOfMass
        item["shape_center_of_mass_mm"] = [center.x, center.y, center.z]
        item["center_of_mass_source"] = "Shape.CenterOfMass"
    except Exception:
        try:
            total_volume = sum(solid.Volume for solid in solids)
            if total_volume > 0:
                item["shape_center_of_mass_mm"] = [
                    sum(solid.Volume * getattr(solid.CenterOfMass, axis) for solid in solids)
                    / total_volume
                    for axis in ("x", "y", "z")
                ]
                item["center_of_mass_source"] = "volume-weighted solid centroids"
            else:
                item["center_of_mass_unavailable"] = "no positive-volume solids"
        except Exception as error:
            errors.append(f"center_of_mass: {error}")
    item["shape_coordinates"] = "raw FreeCAD Shape values; inspect placements before aggregation"
    if validate_shapes:
        try:
            item["shape_valid"] = shape.isValid()
        except Exception as error:
            errors.append(f"shape_validity: {error}")
    if errors:
        item["shape_errors"] = errors


def audit(
    assembly: Path,
    *,
    recompute: str = "none",
    shape_scope: str = "terminal",
    validate_shapes: bool = False,
    document_names: tuple[str, ...] = (),
    object_names: tuple[str, ...] = (),
    checkpoint: Callable[[dict], None] | None = None,
    checkpoint_interval_s: float = 2.0,
    isolation_root: Path | None = None,
) -> dict:
    _source_guard(assembly)
    if recompute not in {"none", "changed", "force"}:
        raise ValueError("recompute must be none, changed or force")
    if shape_scope not in {"terminal", "all", "none"}:
        raise ValueError("shape scope must be terminal, all or none")
    if not math.isfinite(checkpoint_interval_s) or checkpoint_interval_s < 0:
        raise ValueError("checkpoint interval must be finite and nonnegative")
    import FreeCAD as App

    isolation = _runtime_isolation(App, isolation_root)
    prior_documents = set(App.listDocuments())
    report = {
        "schema_version": 2,
        "validation_level": "native CAD inspection; not kinematics or physical validation",
        "freecad_version": list(App.Version()),
        "runtime_isolation": isolation,
        "open_document_count_before": len(prior_documents),
        "assembly_filename": assembly.name,
        "audit_mode": recompute,
        "shape_scope": shape_scope,
        "shape_validation_requested": validate_shapes,
        "object_checkpoint_interval_s": checkpoint_interval_s,
        "document_filter": list(document_names),
        "object_filter": list(object_names),
        "created_at_utc": _timestamp(),
        "documents": [],
        "errors": [],
        "saved_source_changes": False,
        "restore_completed": False,
        "status": "running",
        "stage": "opening",
        "completed_document_count": 0,
    }

    last_object_checkpoint: float | None = None

    def emit(stage: str, document: str | None = None, obj: str | None = None) -> None:
        nonlocal last_object_checkpoint
        report.update(
            stage=stage, current_document=document, current_object=obj, updated_at_utc=_timestamp()
        )
        if stage == "document_start":
            last_object_checkpoint = None
        object_event = stage in {"inspecting_shape", "shape_finished", "inspecting_metadata"}
        now = time.monotonic()
        if object_event:
            if (
                last_object_checkpoint is not None
                and now - last_object_checkpoint < checkpoint_interval_s
            ):
                return
            last_object_checkpoint = now
        if checkpoint:
            checkpoint(report)

    emit("opening")
    try:
        master = App.openDocument(str(assembly), True)
        report.update(master_document=master.Name, restore_completed=True)
        emit("restored")
        documents = {
            name: doc for name, doc in App.listDocuments().items() if name not in prior_documents
        }
        report["loaded_document_names"] = sorted(documents)
        for name, document in sorted(documents.items()):
            if document_names and name not in document_names:
                continue
            entry = {
                "name": name,
                "objects": [],
                "status": "running",
                "native_object_count": len(document.Objects),
            }
            report["documents"].append(entry)
            emit("document_start", name)
            if recompute != "none":
                emit("recomputing", name)
                try:
                    entry["recompute_return"] = document.recompute(None, recompute == "force")
                except Exception as error:
                    entry["recompute_error"] = str(error)
                emit("recompute_finished", name)
            for index, obj in enumerate(document.Objects):
                if (
                    object_names
                    and obj.Name not in object_names
                    and f"{name}::{obj.Name}" not in object_names
                ):
                    continue
                item = _object_metadata(obj)
                entry["objects"].append(item)
                selected = shape_scope == "all" or (shape_scope == "terminal" and _is_terminal(obj))
                if selected:
                    emit("inspecting_shape", name, obj.Name)
                    _shape_metadata(obj, item, validate_shapes)
                    emit("shape_finished", name, obj.Name)
                elif index % 25 == 0:
                    emit("inspecting_metadata", name, obj.Name)
            entry.update(object_count=len(entry["objects"]), status="complete")
            report["completed_document_count"] += 1
            emit("document_complete", name)
        # Later child-document recomputes can touch a parent already inspected.
        # Capture current global state instead of treating earlier rows as final.
        final_states = {}
        not_up_to_date = []
        final_count = 0
        for name, document in sorted(documents.items()):
            for obj in document.Objects:
                states = list(obj.State)
                final_count += 1
                for state in states:
                    final_states[state] = final_states.get(state, 0) + 1
                if states != ["Up-to-date"]:
                    not_up_to_date.append({"object": f"{name}::{obj.Name}", "state": states})
        report["final_loaded_object_states"] = {
            "object_count": final_count,
            "state_token_counts": final_states,
            "not_up_to_date": not_up_to_date,
            "scope": "all newly loaded documents after every requested recompute",
        }
        report["status"] = "complete"
    except Exception as error:
        report["errors"].append(str(error))
        report["status"] = "failed"
    finally:
        checkpoint_error = None
        try:
            emit("closing")
        except Exception as error:
            checkpoint_error = error
        for name in sorted(set(App.listDocuments()) - prior_documents):
            try:
                App.closeDocument(name)
            except Exception as error:
                report["errors"].append(f"close {name}: {error}")
                report["status"] = "failed"
        report["open_document_count_after"] = len(App.listDocuments())
        if checkpoint_error is not None:
            raise checkpoint_error
        emit("finished")
    return report


def _names(variable: str) -> tuple[str, ...]:
    return tuple(name.strip() for name in os.environ.get(variable, "").split(",") if name.strip())


def main() -> None:
    try:
        assembly = Path(os.environ["RAFTEL_FREECAD_ASSEMBLY"])
        output = Path(os.environ["RAFTEL_FREECAD_REPORT"])
    except KeyError as error:
        raise ValueError("set RAFTEL_FREECAD_ASSEMBLY and RAFTEL_FREECAD_REPORT") from error
    # Protect evidence/output before attempting any native import.
    if output.suffix.lower() != ".json" or output.exists():
        raise ValueError("report must be a new .json path; existing files are never overwritten")
    _source_guard(assembly)
    validate = os.environ.get("RAFTEL_FREECAD_VALIDATE_SHAPES", "0")
    if validate not in {"0", "1"}:
        raise ValueError("RAFTEL_FREECAD_VALIDATE_SHAPES must be 0 or 1")
    recompute = os.environ.get("RAFTEL_FREECAD_RECOMPUTE", "none")
    shape_scope = os.environ.get("RAFTEL_FREECAD_SHAPE_SCOPE", "terminal")
    if recompute not in {"none", "changed", "force"}:
        raise ValueError("recompute must be none, changed or force")
    if shape_scope not in {"terminal", "all", "none"}:
        raise ValueError("shape scope must be terminal, all or none")
    interval = float(os.environ.get("RAFTEL_FREECAD_CHECKPOINT_INTERVAL_S", "2"))
    if not math.isfinite(interval) or interval < 0:
        raise ValueError("checkpoint interval must be finite and nonnegative")
    writer = ReportWriter(output)
    audit(
        assembly,
        recompute=recompute,
        shape_scope=shape_scope,
        validate_shapes=validate == "1",
        document_names=_names("RAFTEL_FREECAD_DOCUMENTS"),
        object_names=_names("RAFTEL_FREECAD_OBJECTS"),
        checkpoint=writer,
        checkpoint_interval_s=interval,
        isolation_root=(
            Path(os.environ["RAFTEL_FREECAD_ISOLATION_ROOT"])
            if os.environ.get("RAFTEL_FREECAD_ISOLATION_ROOT")
            else None
        ),
    )
    print("RAFTEL_CAD_REPORT_WRITTEN", output)


if __name__ == "__main__" or os.environ.get("RAFTEL_RUN_FREECAD_AUDIT") == "1":
    main()
