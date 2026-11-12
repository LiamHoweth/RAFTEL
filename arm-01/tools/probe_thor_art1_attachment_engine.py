"""Copied Art1 direct attachment-engine experiment; never repairs or saves CAD.

The native entry point is deliberately opt-in. Host tests cannot establish an
executed FreeCAD engine witness. Root owns the serialized external launcher.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import stat
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

FLAG = "RAFTEL_RUN_ART1_ATTACHMENT_ENGINE"
ROOT_ENV = "RAFTEL_ATTACHMENT_ENGINE_ROOT"
SOURCE_SHA256 = "8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a"
CANDIDATE_SHA256 = "6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd"
MAX_BYTES = 32 * 1024**2
RESERVE_BYTES = 50 * 1024**3 + 512 * 1024**2
CHALLENGE_MM = (1.25, -2.5, 3.75)
FRAME_TOLERANCE = 1e-8
INPUTS = (
    "request.json",
    "inputs/source.fcstd",
    "inputs/candidate.fcstd",
    "inputs/evidence.json",
    "scripts/probe_thor_art1_attachment_engine.py",
    "scripts/probe_thor_art1_semantic_supports.py",
)


def checked_path(root: Path, relative: str, *, exists: bool = True) -> Path:
    """Reject escapes and Windows reparse points before reading any bytes."""
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("unsafe relative path")
    candidate = root / relative
    for item in (root, *root.parents, candidate, *candidate.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if item.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(
                stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
            ):
                raise ValueError("reparse or symbolic input path forbidden")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("input escaped owned run")
    if exists and not candidate.is_file():
        raise ValueError("required regular input missing")
    if exists and candidate.stat().st_size > MAX_BYTES:
        raise ValueError("input exceeds byte budget")
    return candidate


def sha(path: Path) -> str:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("input exceeds byte budget")
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite JSON number")
        return result

    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("JSON exceeds byte budget")
    try:
        result = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=invalid,
            parse_float=finite_float,
        )
    except (UnicodeError, RecursionError) as error:
        raise ValueError("bounded UTF-8 JSON required") from error
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    return result


def matrix(value) -> list[float]:
    values = list(value)
    if len(values) != 16 or any(
        isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
        for v in values
    ):
        raise ValueError("finite sixteen-entry matrix required")
    return [float(v) for v in values]


def matrix_error(first, second) -> float:
    return max(abs(a - b) for a, b in zip(matrix(first), matrix(second), strict=True))


def engine_effect(before, challenged, after, mode: str) -> dict:
    """Classification needs an observed mutation, never just a successful call."""
    imposed = matrix_error(before, challenged)
    effect = matrix_error(challenged, after)
    residual = matrix_error(before, after)
    active = mode != "Deactivated"
    return {
        "challenge_max_matrix_delta": imposed,
        "engine_max_matrix_effect": effect,
        "engine_return_max_matrix_error": residual,
        "active_mode": active,
        "engine_effect_observed": active and imposed > 1 and effect > 1,
        "challenge_recovered": active and imposed > 1 and residual <= FRAME_TOLERANCE,
        "deactivated_no_effect_control": not active and effect <= FRAME_TOLERANCE,
        "tolerance_is_diagnostic_not_migration": True,
    }


def reject_conflicting_flags() -> None:
    if any(k.startswith("RAFTEL_") and k != FLAG and v == "1" for k, v in os.environ.items()):
        raise ValueError("conflicting native execution flag")


def guard_request(root: Path, worker: Path) -> tuple[dict, dict[str, str]]:
    reject_conflicting_flags()
    if os.environ.get(FLAG) != "1":
        raise ValueError("explicit native attachment-engine opt-in required")
    if (
        re.fullmatch(r"run-[0-9]{2}", root.name) is None
        or [p.name for p in list(root.parents)[:3]] != ["a01_engine", "swarm", ".work"]
        or worker.resolve() != (root / INPUTS[4]).resolve()
    ):
        raise ValueError("worker must execute in a fresh owned swarm run")
    paths = {name: checked_path(root, name) for name in INPUTS}
    for name in ("user.cfg", "system.cfg", "home", "data", "temp"):
        checked_path(root, name, exists=False)
    for output in ("probe.json", "probe.tmp"):
        if checked_path(root, output, exists=False).exists():
            raise ValueError("existing evidence is never overwritten or relaunched")
    if shutil.disk_usage(root).free < RESERVE_BYTES:
        raise ValueError("50 GiB reserve plus 512 MiB scratch required")
    request = strict_json(paths["request.json"])
    if (
        set(request) != {"schema_version", "evidence_class", "pins", "runtime_modules"}
        or type(request["schema_version"]) is not int
        or request["schema_version"] != 1
        or request["evidence_class"] != "copied_Art1_direct_attachment_engine_request"
        or not isinstance(request["pins"], dict)
        or set(request["pins"]) != set(INPUTS[1:])
        or not isinstance(request["runtime_modules"], dict)
        or set(request["runtime_modules"]) != {"FreeCAD", "Part"}
        or any(
            not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{64}", v) is None
            for v in request["pins"].values()
        )
    ):
        raise ValueError("unsupported attachment-engine request")
    pins = {name: sha(path) for name, path in paths.items()}
    if any(pins[name] != digest for name, digest in request["pins"].items()):
        raise ValueError("retained execution/input pin differs")
    if (
        pins["inputs/source.fcstd"] != SOURCE_SHA256
        or pins["inputs/candidate.fcstd"] != CANDIDATE_SHA256
    ):
        raise ValueError("pinned source or unaccepted candidate differs")
    return request, pins


def load_semantic(root: Path):
    path = checked_path(root, INPUTS[5])
    spec = importlib.util.spec_from_file_location("attachment_semantic_retained", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def actual_isolation(App, root: Path) -> dict:
    expected = {
        "UserParameter": root / "user.cfg",
        "SystemParameter": root / "system.cfg",
        "UserHomePath": root / "home",
        "UserAppData": root / "data",
        "AppTempPath": root / "temp",
    }
    actual = {key: App.ConfigGet(key) for key in expected}
    if any(Path(actual[key]).resolve() != path.resolve() for key, path in expected.items()):
        raise ValueError("actual five native paths differ from isolated run")
    return {"passed": True, "actual_paths": actual}


def process_image_path() -> Path:
    """Read the running process image, independently of embedded Python metadata."""
    if sys.platform == "win32":
        import ctypes

        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, len(buffer))
        if length == 0 or length >= len(buffer):
            raise ValueError("cannot authenticate actual Windows process image")
        return Path(buffer.value).resolve(strict=True)
    return Path("/proc/self/exe").resolve(strict=True)


def runtime_module_records(App, Part, declarations: dict) -> dict:
    """FreeCADcmd embeds FreeCAD without __file__; Part remains an extension."""
    record = {}
    embedded = declarations["FreeCAD"]
    if (
        not isinstance(embedded, dict)
        or set(embedded) != {"kind", "host_path", "host_sha256"}
        or embedded["kind"] != "embedded_no_file"
    ):
        raise ValueError("embedded FreeCAD declaration invalid")
    if getattr(App, "__file__", None) is not None:
        raise ValueError("expected embedded FreeCAD module without file origin")
    executable = process_image_path()
    if executable != Path(embedded["host_path"]).resolve(strict=True):
        raise ValueError("actual embedded host executable differs")
    with executable.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != embedded["host_sha256"]:
        raise ValueError("actual embedded host executable bytes differ")
    record["FreeCAD"] = {
        "kind": "embedded_no_file",
        "module_file": None,
        "host_path": str(executable),
        "host_sha256": digest,
        "python_sys_executable": sys.executable,
        "freecad_version": list(App.Version()),
        "module_spec_origin": getattr(getattr(App, "__spec__", None), "origin", None),
    }
    extension = declarations["Part"]
    if (
        not isinstance(extension, dict)
        or set(extension) != {"kind", "path", "sha256"}
        or extension["kind"] != "extension"
    ):
        raise ValueError("Part extension declaration invalid")
    origin = Path(Part.__file__).resolve(strict=True)
    if origin != Path(extension["path"]).resolve(strict=True):
        raise ValueError("actual Part extension origin differs")
    with origin.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != extension["sha256"]:
        raise ValueError("actual Part extension bytes differ")
    record["Part"] = {"kind": "extension", "path": str(origin), "sha256": digest}
    return record


def placement(obj) -> list[float]:
    return matrix(obj.Placement.toMatrix().A)


def owner_snapshot(obj, semantic) -> dict:
    properties = set(obj.PropertiesList)
    prop = "AttachmentSupport" if "AttachmentSupport" in properties else "Support"
    return {
        "name": obj.Name,
        "type_id": obj.TypeId,
        "state": list(obj.State),
        "placement_matrix": placement(obj),
        "mode": str(obj.MapMode) if "MapMode" in properties else None,
        "attachment_property": prop if prop in properties else None,
        "targets": semantic.current_property_entries(getattr(obj, prop))
        if prop in properties
        else [],
        "attachment_offset_matrix": matrix(obj.AttachmentOffset.toMatrix().A)
        if "AttachmentOffset" in properties
        else None,
        "attacher_type": str(obj.AttacherType) if "AttacherType" in properties else None,
    }


def challenge_owner(App, obj, semantic) -> dict:
    """Restore exactly this object's saved Placement even when an engine call fails."""
    original = App.Placement(obj.Placement)
    row = {
        "saved": owner_snapshot(obj, semantic),
        "method": "positionBySupport",
        "explicit_support_assignment": False,
        "recompute_requested": False,
    }
    try:
        if not callable(getattr(obj, "positionBySupport", None)):
            row["status"] = "no_attachment_engine_method"
            return row
        result = obj.positionBySupport()
        row["nominal_call_return"] = (
            result if isinstance(result, (bool, int, str, type(None))) else repr(result)
        )
        row["nominal_engine"] = owner_snapshot(obj, semantic)
        challenge = App.Placement(obj.Placement)
        challenge.Base = challenge.Base + App.Vector(*CHALLENGE_MM)
        obj.Placement = challenge
        row["challenged"] = owner_snapshot(obj, semantic)
        result = obj.positionBySupport()
        row["challenge_call_return"] = (
            result if isinstance(result, (bool, int, str, type(None))) else repr(result)
        )
        row["after_engine"] = owner_snapshot(obj, semantic)
        row.update(
            engine_effect(
                row["nominal_engine"]["placement_matrix"],
                row["challenged"]["placement_matrix"],
                row["after_engine"]["placement_matrix"],
                row["nominal_engine"]["mode"],
            )
        )
        row["saved_to_engine_max_matrix_delta"] = matrix_error(
            row["saved"]["placement_matrix"], row["nominal_engine"]["placement_matrix"]
        )
        row["targets_unchanged"] = all(
            row[phase]["targets"] == row["saved"]["targets"]
            for phase in ("nominal_engine", "challenged", "after_engine")
        )
        row["public_target_change_observed"] = not row["targets_unchanged"]
        row["status"] = "observed_direct_engine_call"
    except Exception as error:
        row.update(status="engine_error", error_type=type(error).__name__, message=str(error))
    finally:
        obj.Placement = original
        row["restored_saved"] = owner_snapshot(obj, semantic)
        row["saved_placement_restored"] = (
            matrix_error(placement(obj), row["saved"]["placement_matrix"]) <= FRAME_TOLERANCE
        )
    return row


def native_fixture(App, Part, semantic, owned: list[str], receipt: dict) -> dict:
    receipt.update(passed=False, recompute_requested=False, document_saved=False)
    doc = App.newDocument("RAFTELAttachmentEngineFixture")
    owned.append(doc.Name)
    try:
        support = doc.addObject("Part::Feature", "PlaneProvider")
        support.Shape = Part.makePlane(4, 3)
        plane = doc.addObject("PartDesign::Plane", "AttachedPlane")
        prop = "AttachmentSupport" if "AttachmentSupport" in plane.PropertiesList else "Support"
        setattr(plane, prop, [(support, ("Face1",))])
        plane.MapMode = "FlatFace"
        first = challenge_owner(App, plane, semantic)
        receipt["flat_face"] = first
        if not first.get("challenge_recovered") or not first.get("engine_effect_observed"):
            raise ValueError("FlatFace fixture failed genuine engine effect")
        plane.positionBySupport()
        baseline = App.Placement(plane.Placement)
        transform = App.Placement(App.Vector(4, -3, 2), App.Rotation(App.Vector(0, 1, 0), 37))
        support.Placement = transform
        expected = matrix(transform.multiply(baseline).toMatrix().A)
        receipt.update(
            provider_transform_matrix=matrix(transform.toMatrix().A),
            provider_expected_owner_matrix=expected,
            provider_before_call_owner_matrix=placement(plane),
        )
        plane.positionBySupport()
        moved = placement(plane)
        receipt["provider_actual_owner_matrix"] = moved
        covariance_error = matrix_error(expected, moved)
        support.Placement = App.Placement()
        plane.positionBySupport()
        return_error = matrix_error(placement(plane), matrix(baseline.toMatrix().A))
        plane.MapMode = "Deactivated"
        control = challenge_owner(App, plane, semantic)
        receipt.update(
            deactivated=control,
            provider_transform_matrix=matrix(transform.toMatrix().A),
            provider_expected_owner_matrix=expected,
            provider_actual_owner_matrix=moved,
            provider_covariance_max_matrix_error=covariance_error,
            provider_return_max_matrix_error=return_error,
        )
        if (
            covariance_error > FRAME_TOLERANCE
            or return_error > FRAME_TOLERANCE
            or not control.get("deactivated_no_effect_control")
        ):
            raise ValueError("provider covariance/return or deactivated control failed")
        # Independent quarter-turn matrices supplied by the fixture reviewer.
        # These constants are ordinary rigid-frame arithmetic, not native API outputs.
        datum = doc.addObject("Part::Feature", "ObjectXYProvider")
        consumer = doc.addObject("Part::Feature", "ObjectXYConsumer")
        consumer.addExtension("Part::AttachExtensionPython")
        if str(consumer.AttacherType) != "Attacher::AttachEngine3D":
            raise ValueError("ObjectXY fixture requires explicit native Engine3D")
        prop = "AttachmentSupport" if "AttachmentSupport" in consumer.PropertiesList else "Support"
        setattr(consumer, prop, [(datum, ("",))])
        consumer.MapMode = "ObjectXY"
        consumer.MapReversed = False
        if "BaseMapMode" in consumer.PropertiesList and str(consumer.BaseMapMode) != "Deactivated":
            raise ValueError("ObjectXY fixture requires inactive base mapping")
        z90 = App.Rotation(App.Vector(0, 0, 1), 90)
        x90 = App.Rotation(App.Vector(1, 0, 0), 90)
        y90 = App.Rotation(App.Vector(0, 1, 0), 90)
        nominal_support = App.Placement(App.Vector(10, 20, 30), z90)
        nominal_offset = App.Placement(App.Vector(2, 3, 4), x90)
        phases = [
            (
                "nominal",
                nominal_support,
                nominal_offset,
                [0, 0, 1, 7, 1, 0, 0, 22, 0, 1, 0, 34, 0, 0, 0, 1],
            ),
            (
                "translated_support",
                App.Placement(App.Vector(15, 13, 41), z90),
                nominal_offset,
                [0, 0, 1, 12, 1, 0, 0, 15, 0, 1, 0, 45, 0, 0, 0, 1],
            ),
            (
                "rotated_support",
                App.Placement(App.Vector(10, 20, 30), y90),
                nominal_offset,
                [0, 1, 0, 14, 0, 0, -1, 23, -1, 0, 0, 28, 0, 0, 0, 1],
            ),
            (
                "changed_offset",
                nominal_support,
                App.Placement(App.Vector(-5, 7, 11), y90),
                [0, -1, 0, 3, 0, 0, 1, 15, -1, 0, 0, 41, 0, 0, 0, 1],
            ),
            (
                "nominal_return",
                nominal_support,
                nominal_offset,
                [0, 0, 1, 7, 1, 0, 0, 22, 0, 1, 0, 34, 0, 0, 0, 1],
            ),
        ]
        oracle_rows = []
        receipt["object_xy_independent_oracle"] = oracle_rows
        receipt["object_xy_attacher_type"] = str(consumer.AttacherType)
        for name, provider_placement, offset, expected_matrix in phases:
            datum.Placement = provider_placement
            consumer.AttachmentOffset = offset
            # Map property assignment can itself execute; force a visible wrong frame
            # immediately before the explicitly witnessed direct engine invocation.
            consumer.Placement = App.Placement(App.Vector(-100, -200, -300), App.Rotation())
            before = placement(consumer)
            phase = {
                "phase": name,
                "observed_provider_matrix": placement(datum),
                "observed_offset_matrix": matrix(consumer.AttachmentOffset.toMatrix().A),
                "mode": str(consumer.MapMode),
                "map_reversed": bool(consumer.MapReversed),
                "expected_matrix": expected_matrix,
                "before_explicit_call_matrix": before,
            }
            oracle_rows.append(phase)
            try:
                result = consumer.positionBySupport()
                actual = placement(consumer)
                error = matrix_error(actual, expected_matrix)
                phase.update(actual_matrix=actual, call_return=result, max_matrix_error=error)
            except Exception as call_error:
                phase.update(error_type=type(call_error).__name__, message=str(call_error))
                raise
            if result is not True or error > FRAME_TOLERANCE or matrix_error(before, actual) < 1:
                raise ValueError(f"independent ObjectXY engine fixture failed: {name}")
        receipt["passed"] = True
        return receipt
    finally:
        name = doc.Name
        App.closeDocument(name)
        owned.remove(name)


def write_report(root: Path, report: dict) -> None:
    temporary = checked_path(root, "probe.tmp", exists=False)
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    os.replace(temporary, root / "probe.json")


def native_capture() -> dict:
    root = Path(os.environ[ROOT_ENV]).absolute()
    request, pins = guard_request(root, Path(__file__))
    semantic = load_semantic(root)
    evidence = strict_json(root / "inputs/evidence.json")
    references = semantic.authenticate_ledger(root / "inputs/source.fcstd", evidence)
    import FreeCAD as App
    import Part

    report = {
        "schema_version": 1,
        "evidence_class": "native_copied_Art1_direct_attachment_engine_diagnostic",
        "status": "starting",
        "input_execution_hashes_before": pins,
        "freecad_version": list(App.Version()),
        "addons_requested": [],
        "opencascade_version": Part.OCC_VERSION,
        "owners": [],
        "errors": [],
        "document_saved": False,
        "source_document_opened": False,
        "recompute_requested": False,
        "explicit_support_assignment": False,
        "attachment_approved": False,
        "migration_accepted": False,
        "manufacturing_release": False,
        "physical_calibration": False,
        "engine_internal_persistent_name_path_traced": False,
    }
    owned = []
    write_report(root, report)
    try:
        report["runtime_isolation"] = actual_isolation(App, root)
        report["actual_runtime_modules"] = runtime_module_records(
            App, Part, request["runtime_modules"]
        )
        if App.listDocuments():
            raise ValueError("fresh console required; preexisting documents are never closed")
        report["fixture"] = {}
        native_fixture(App, Part, semantic, owned, report["fixture"])
        with zipfile.ZipFile(root / "inputs/candidate.fcstd") as archive:
            info = archive.getinfo("Document.xml")
            if info.file_size > MAX_BYTES:
                raise ValueError("native XML exceeds inspection budget")
            xml = ET.fromstring(archive.read(info))
        saved_types = {n.get("name"): n.get("type") for n in xml.findall("./Objects/Object")}
        try:
            doc = App.openDocument(str(root / "inputs/candidate.fcstd"), True)
        except Exception:
            # Fresh console invariant was verified; documents introduced by this
            # attempted open are owned even if the native restore raised.
            owned.extend(name for name in App.listDocuments() if name not in owned)
            raise
        owned.append(doc.Name)
        report["candidate_runtime_type_inventory"] = [
            {"name": o.Name, "saved_type_id": saved_types.get(o.Name), "runtime_type_id": o.TypeId}
            for o in doc.Objects
        ]
        if len(saved_types) != len(doc.Objects) or any(
            saved_types.get(o.Name) != o.TypeId for o in doc.Objects
        ):
            raise ValueError("candidate runtime TypeIds differ from saved XML")
        for name in sorted({r["owner"] for r in references}):
            report["owners"].append(challenge_owner(App, doc.getObject(name), semantic))
            write_report(root, report)
        report["final_object_states"] = [
            {"name": o.Name, "state": list(o.State)} for o in doc.Objects
        ]
        report["result_counts"] = dict(Counter(row["status"] for row in report["owners"]))
        report["active_engine_effect_count"] = sum(
            r.get("engine_effect_observed", False) for r in report["owners"]
        )
        report["active_challenge_recovered_count"] = sum(
            r.get("challenge_recovered", False) for r in report["owners"]
        )
        report["public_target_change_count"] = sum(
            r.get("public_target_change_observed", False) for r in report["owners"]
        )
        report["status"] = "complete_engine_diagnostic_not_migration"
    except Exception as error:
        report["status"] = "failed_engine_diagnostic"
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        for name in reversed(owned):
            try:
                App.closeDocument(name)
            except Exception as error:
                report["errors"].append(
                    {
                        "type": type(error).__name__,
                        "message": str(error),
                        "phase": "owned_document_cleanup",
                        "name": name,
                    }
                )
        report["open_documents_after"] = list(App.listDocuments())
        report["input_execution_hashes_after"] = {}
        for name in INPUTS:
            try:
                report["input_execution_hashes_after"][name] = sha(checked_path(root, name))
            except Exception as error:
                report["errors"].append(
                    {
                        "type": type(error).__name__,
                        "message": str(error),
                        "phase": "preservation",
                        "name": name,
                    }
                )
        report["input_execution_bytes_preserved"] = pins == report["input_execution_hashes_after"]
        if (
            report["errors"]
            or report["open_documents_after"]
            or not report["input_execution_bytes_preserved"]
        ):
            report["status"] = "failed_engine_diagnostic"
        write_report(root, report)
    return report


if os.environ.get(FLAG) == "1":
    result = native_capture()
    if result["status"] != "complete_engine_diagnostic_not_migration":
        raise RuntimeError("native attachment engine diagnostic failed; retain probe.json")
