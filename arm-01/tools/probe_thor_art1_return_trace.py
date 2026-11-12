"""Prepare or execute a copied Art1 radius-return diagnostic; never save CAD.

Preparation does not launch FreeCAD. Root owns the serialized native queue and
uses the retained launch.json only after reviewing this packet.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

FLAG = "RAFTEL_RUN_ART1_RETURN_TRACE"
ROOT_ENV = "RAFTEL_ART1_RETURN_ROOT"
SOURCE_SHA256 = "8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a"
CANDIDATE_SHA256 = "6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd"
EXECUTABLE_SHA256 = "1692e54224b48989974e8b91d3ac7a38d1d502d3db4dee1d4cf79ba91356e42d"
PHASES = (
    ("restored_cached", 1.7),
    ("nominal_forced", 1.7),
    ("radius_minus_0_01_mm", 1.69),
    ("radius_plus_0_01_mm", 1.71),
    ("restored_nominal_radius", 1.7),
)
HELPERS = (
    "audit_freecad_assembly.py",
    "thor_art1_diagnostics.py",
    "probe_thor_art1_freecad.py",
    "prepare_thor_art1_candidate.py",
    "probe_thor_art1_semantic_supports.py",
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def no_reparse(path: Path) -> None:
    for item in (path.absolute(), *path.absolute().parents):
        if item.is_symlink() or (
            item.exists() and getattr(item.stat(), "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("symlink/reparse paths are not owned isolated inputs")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def strict_request(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate request key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"nonfinite request number: {value}")

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            invalid(value)
        return result

    with path.open("rb") as stream:
        raw = stream.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        raise ValueError("request exceeds 256 KiB budget")
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique,
        parse_constant=invalid,
        parse_float=finite_float,
    )
    if not isinstance(value, dict):
        raise ValueError("request must be an object")
    return value


def validate_request(root: Path, request: dict) -> dict:
    no_reparse(root)
    if (
        set(request)
        != {
            "schema_version",
            "evidence_class",
            "file_sha256",
            "protected_sha256",
            "runtime_modules",
            "embedded_process",
        }
        or type(request["schema_version"]) is not int
        or request["schema_version"] != 1
        or request["evidence_class"] != "Art1_copied_parameter_return_trace_request"
    ):
        raise ValueError("unsupported return-trace request")
    expected = {
        "scripts/probe_thor_art1_return_trace.py",
        *(f"scripts/{name}" for name in HELPERS),
        "hardware/cad/thor-art1-migration-evidence.json",
        "inputs/source.fcstd",
        "inputs/candidate.fcstd",
    }
    if not isinstance(request["file_sha256"], dict) or set(request["file_sha256"]) != expected:
        raise ValueError("request snapshot inventory differs")
    for relative, digest in request["file_sha256"].items():
        no_reparse(root / relative)
        path = (root / relative).resolve(strict=True)
        if (
            not path.is_relative_to(root.resolve())
            or path.stat().st_size > 32 * 1024**2
            or sha(path) != digest
        ):
            raise ValueError("retained input escaped run or changed bytes")
    if (
        request["file_sha256"]["inputs/source.fcstd"] != SOURCE_SHA256
        or request["file_sha256"]["inputs/candidate.fcstd"] != CANDIDATE_SHA256
    ):
        raise ValueError("original/candidate pin differs")
    if (
        not isinstance(request["protected_sha256"], dict)
        or not 7 <= len(request["protected_sha256"]) <= 128
    ):
        raise ValueError(
            "bounded protected originals/history/runtime/previous-attempt ledger required"
        )
    for filename, digest in request["protected_sha256"].items():
        if (
            not isinstance(filename, str)
            or len(filename) > 2048
            or not Path(filename).is_absolute()
            or Path(filename).resolve().is_relative_to(root.resolve())
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("protected ledger path/digest invalid")
        if sha(Path(filename)) != digest:
            raise ValueError("protected original or historical evidence changed")
    if not isinstance(request["runtime_modules"], dict) or set(request["runtime_modules"]) != {
        "Part"
    }:
        raise ValueError("native module origin inventory differs")
    for item in [*request["runtime_modules"].values(), request["embedded_process"]]:
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "sha256"}
            or not isinstance(item["path"], str)
            or not Path(item["path"]).is_absolute()
            or not isinstance(item["sha256"], str)
            or len(item["sha256"]) != 64
            or sha(Path(item["path"])) != item["sha256"]
        ):
            raise ValueError("native module bytes differ")
    if (
        request["embedded_process"]["sha256"] != EXECUTABLE_SHA256
        or request["protected_sha256"].get(request["embedded_process"]["path"]) != EXECUTABLE_SHA256
    ):
        raise ValueError("embedded process must be the protected pinned launcher")
    return request


def prepare_run(freecad: Path, source: Path, candidate: Path, root: Path) -> dict:
    """Create an immutable-input launch packet without starting a process."""
    for path in (freecad, source, candidate, root):
        no_reparse(path)
    freecad, source, candidate, root = (p.resolve() for p in (freecad, source, candidate, root))
    if (
        sha(freecad) != EXECUTABLE_SHA256
        or sha(source) != SOURCE_SHA256
        or sha(candidate) != CANDIDATE_SHA256
    ):
        raise ValueError("executable/source/candidate exact pin differs")
    if root.exists() or any(p.is_relative_to(root) for p in (freecad, source, candidate)):
        raise ValueError("run directory must be new and separate from preserved inputs")
    ancestor = root.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if shutil.disk_usage(ancestor).free < 50 * 1024**3 + 512 * 1024**2:
        raise ValueError("50 GiB reserve plus 512 MiB scratch budget required")
    base = Path(__file__).resolve().parents[1]
    history = [
        base / "hardware/cad" / name
        for name in (
            "thor-art1-migration-evidence.json",
            "thor-art1-desktop-candidate-study-v1.json",
            "thor-art1-desktop-candidate-runner-v1.json",
            "thor-art1-desktop-native-evidence-v1.json",
        )
    ]
    protected = {str(p): sha(p) for p in [source, candidate, freecad, *history]}
    for attempt in root.parent.glob("run-*"):
        if attempt.is_dir() and attempt != root:
            no_reparse(attempt)
            for path in attempt.rglob("*"):
                no_reparse(path)
                if path.is_file():
                    protected[str(path.resolve())] = sha(path)
    if len(protected) > 128:
        raise ValueError("previous-attempt preservation ledger exceeds bounded scope")
    root.mkdir(parents=True)
    for folder in ("scripts", "inputs", "hardware/cad", "home", "data", "temp"):
        (root / folder).mkdir(parents=True)
    copies = {
        "inputs/source.fcstd": source,
        "inputs/candidate.fcstd": candidate,
        "hardware/cad/thor-art1-migration-evidence.json": history[0],
        "scripts/probe_thor_art1_return_trace.py": Path(__file__),
        **{f"scripts/{name}": base / "tools" / name for name in HELPERS},
    }
    for relative, path in copies.items():
        with (root / relative).open("xb") as stream:
            stream.write(path.read_bytes())
    request = {
        "schema_version": 1,
        "evidence_class": "Art1_copied_parameter_return_trace_request",
        "file_sha256": {relative: sha(root / relative) for relative in copies},
        "protected_sha256": protected,
        "runtime_modules": {
            name: {"path": str(path), "sha256": sha(path)}
            for name, path in {
                "Part": freecad.parent.parent / "lib/Part.pyd",
            }.items()
        },
        "embedded_process": {"path": str(freecad), "sha256": EXECUTABLE_SHA256},
    }
    write_new(root / "request.json", request)
    validate_request(root, request)
    packet = {
        "command": [
            str(freecad),
            "-u",
            str(root / "user.cfg"),
            "-s",
            str(root / "system.cfg"),
            str(root / "scripts/probe_thor_art1_return_trace.py"),
        ],
        "environment": {
            FLAG: "1",
            ROOT_ENV: str(root),
            "RAFTEL_ART1_RETURN_REQUEST_SHA256": sha(root / "request.json"),
            "FREECAD_USER_HOME": str(root / "home"),
            "FREECAD_USER_DATA": str(root / "data"),
            "FREECAD_USER_TEMP": str(root / "temp"),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        "remove_environment": [
            "PYTHONPATH",
            "PYTHONHOME",
            *(key for key in os.environ if key.startswith("RAFTEL_")),
        ],
        "timeout_s": 300,
        "prepared_only_no_native_launch": True,
        "request_sha256": sha(root / "request.json"),
        "native_executable_sha256": EXECUTABLE_SHA256,
        "migration_accepted": False,
    }
    write_new(root / "launch.json", packet)
    return packet


def object_trace(obj, metrics, semantic, saved_names: set[str]) -> dict:
    record = {"name": obj.Name, "type_id": obj.TypeId, "states": list(obj.State)}
    for field, method in (
        ("placement_matrix", "Placement"),
        ("global_placement_matrix", "getGlobalPlacement"),
    ):
        if hasattr(obj, method):
            value = getattr(obj, method)
            record[field] = list((value() if callable(value) else value).toMatrix().A)
    record["expressions"] = [list(pair) for pair in getattr(obj, "ExpressionEngine", [])]
    if hasattr(obj, "Geometry"):
        record["fully_constrained"] = bool(obj.FullyConstrained)
        record["sketch_circle_frames"] = [
            {
                "center_in_sketch_mm": list(geometry.Center),
                "center_in_document_mm": list(obj.Placement.multVec(geometry.Center)),
                "axis_in_document": list(obj.Placement.Rotation.multVec(geometry.Axis)),
                "radius_mm": geometry.Radius,
            }
            for geometry in obj.Geometry
            if type(geometry).__name__ == "Circle"
        ]
    record["attachment"] = {}
    for original in ("Support", "ExternalGeometry", "MirrorPlane"):
        if original not in saved_names and not (
            original == "Support" and "AttachmentSupport" in saved_names
        ):
            continue
        prop = semantic.current_property_name(original, saved_names, set(obj.PropertiesList))
        record["attachment"][original] = {
            "current_property": prop,
            "targets": semantic.current_property_entries(getattr(obj, prop)),
        }
    for prop in ("MapMode", "MapReversed", "MapPathParameter", "AttachmentOffset"):
        if prop in obj.PropertiesList:
            value = getattr(obj, prop)
            record["attachment"][prop] = (
                list(value.toMatrix().A) if prop == "AttachmentOffset" else value
            )
    if hasattr(obj, "Shape"):
        record["shape"] = metrics(obj.Shape)
    return record


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


def runtime_provenance(app, part, request: dict, process_image: Path) -> dict:
    """FreeCADCmd embeds FreeCAD; Part is an actual file-backed extension."""
    expected = request["embedded_process"]
    if (
        process_image.resolve() != Path(expected["path"]).resolve()
        or sha(process_image) != expected["sha256"]
    ):
        raise ValueError("actual process image differs from the pinned native launcher")
    if getattr(app, "__file__", None) is not None:
        raise ValueError("expected the pinned console's embedded FreeCAD module")
    actual_part = Path(part.__file__).resolve(strict=True)
    expected_part = request["runtime_modules"]["Part"]
    if (
        actual_part != Path(expected_part["path"]).resolve()
        or sha(actual_part) != expected_part["sha256"]
    ):
        raise ValueError("actual loaded Part module origin/hash differs")
    return {
        "FreeCAD": {"origin_kind": "embedded_module_without_file", "module_file": None},
        "process_image": {"path": str(process_image), "sha256": sha(process_image)},
        "python_sys_executable": sys.executable,
        "Part": {"path": str(actual_part), "sha256": sha(actual_part)},
    }


def native_capture() -> dict:
    if os.environ.get(FLAG) != "1":
        raise ValueError("explicit return-trace opt-in required")
    if any(
        value == "1" and key.startswith("RAFTEL_") and key != FLAG
        for key, value in os.environ.items()
    ):
        raise ValueError("conflicting native worker opt-in")
    no_reparse(Path(os.environ[ROOT_ENV]))
    root = Path(os.environ[ROOT_ENV]).resolve(strict=True)
    no_reparse(root / "request.json")
    if not (root / "request.json").resolve().is_relative_to(root):
        raise ValueError("request path escaped run")
    request = strict_request(root / "request.json")
    if sha(root / "request.json") != os.environ["RAFTEL_ART1_RETURN_REQUEST_SHA256"]:
        raise ValueError("request bytes differ from launch pin")
    request = validate_request(root, request)
    if Path(__file__).resolve() != root / "scripts/probe_thor_art1_return_trace.py":
        raise ValueError("must execute the retained worker snapshot")
    if (root / "probe.json").exists():
        raise ValueError("fresh report required")
    for relative in (
        "probe.json",
        "probe.checkpoint.tmp",
        "user.cfg",
        "system.cfg",
        "home",
        "data",
        "temp",
    ):
        no_reparse(root / relative)
    if shutil.disk_usage(root).free < 50 * 1024**3 + 512 * 1024**2:
        raise ValueError("native disk reserve insufficient")
    semantic = load(root / "scripts/probe_thor_art1_semantic_supports.py", "return_semantic")
    helper = load(root / "scripts/audit_freecad_assembly.py", "return_audit")
    candidate_helper = load(root / "scripts/prepare_thor_art1_candidate.py", "return_candidate")
    probe = candidate_helper.PROBE
    evidence = semantic.strict_json(root / "hardware/cad/thor-art1-migration-evidence.json")
    semantic.authenticate_ledger(root / "inputs/source.fcstd", evidence)
    with zipfile.ZipFile(root / "inputs/candidate.fcstd") as archive:
        xml = ET.fromstring(archive.read("Document.xml"))
    saved = {
        node.get("name"): {p.get("name") for p in node.findall("./Properties/Property")}
        for node in xml.findall("./ObjectData/Object")
    }
    types = {node.get("name"): node.get("type") for node in xml.findall("./Objects/Object")}
    report = {
        "schema_version": 1,
        "evidence_class": "native_copied_Art1_parameter_return_trace",
        "status": "starting",
        "request_sha256": sha(root / "request.json"),
        "worker_sha256": sha(Path(__file__)),
        "source_sha256": SOURCE_SHA256,
        "candidate_sha256": CANDIDATE_SHA256,
        "coordinate_frame": "native_Art1_Body_identity_mm",
        "ordered_body_members": evidence["ordered_body_members"],
        "phases": [],
        "errors": [],
        "document_saved": False,
        "support_remapped": False,
        "migration_accepted": False,
        "historical_failed_nominal_return_preserved": True,
        "shape_equivalence_established": False,
        "manufacturing_release": False,
    }

    def checkpoint():
        probe["_checkpoint"](root / "probe.json", report)

    probe["_checkpoint"](root / "probe.json", report, first=True)
    import FreeCAD as App
    import Part

    previous = set(App.listDocuments())
    owned = None
    try:
        report["runtime_module_origins"] = runtime_provenance(
            App, Part, request, process_image_path()
        )
        report["addons_requested"] = []
        report["full_runtime_and_addon_bundle_verified"] = False
        if previous:
            raise ValueError("fresh console has preexisting documents")
        report["runtime_isolation"] = helper._runtime_isolation(App, root)
        for key, relative in {
            "UserParameter": "user.cfg",
            "SystemParameter": "system.cfg",
            "UserHomePath": "home",
            "UserAppData": "data",
            "AppTempPath": "temp",
        }.items():
            if Path(App.ConfigGet(key)).resolve() != root / relative:
                raise ValueError("actual native configuration path differs")
        report["freecad_version"] = list(App.Version())
        report["opencascade_version"] = Part.OCC_VERSION
        owned = App.openDocument(str(root / "inputs/candidate.fcstd"), True)
        if {obj.Name: obj.TypeId for obj in owned.Objects} != types:
            raise ValueError("runtime identity differs from candidate XML")
        if [obj.Name for obj in owned.getObject("Body").Group] != report["ordered_body_members"]:
            raise ValueError("Body feature order differs")
        sheet = owned.getObject("Spreadsheet")
        if sheet.getAlias("B2") != "M3BoltBodyRadius" or float(sheet.get("B2")) != 1.7:
            raise ValueError("controlled radius input differs")
        baseline_structure = candidate_helper._structure(
            candidate_helper._constraint_records(owned)
        )
        expected_previous = 1.7
        for index, (label, radius) in enumerate(PHASES):
            if sheet.getAlias("B2") != "M3BoltBodyRadius":
                raise ValueError("controlled cell alias changed")
            before = candidate_helper._constraint_records(owned)
            cell_before = sheet.get("B2")
            if float(cell_before) != expected_previous:
                raise ValueError("controlled radius changed before the declared operation")
            if candidate_helper._structure(before) != baseline_structure:
                raise ValueError("expression/constraint structure changed")
            if index > 1:
                sheet.set("B2", str(radius))
            recompute_result = None if index == 0 else bool(owned.recompute(None, True))
            constraints = candidate_helper._constraint_records(owned)
            phase = {
                "phase": label,
                "radius_mm": radius,
                "cell_alias": sheet.getAlias("B2"),
                "cell_value_before_operation": cell_before,
                "cell_value": sheet.get("B2"),
                "recompute_requested": index != 0,
                "recompute_result": recompute_result,
                "pre_operation_constraints_and_expressions": before,
                "affected_constraints_and_expressions": constraints,
                "expression_and_constraint_structure_preserved": candidate_helper._structure(
                    constraints
                )
                == baseline_structure,
                "sketch004_circle_radius_mm": owned.getObject("Sketch004").Geometry[0].Radius,
                "objects": {
                    obj.Name: object_trace(
                        obj, probe["native_shape_metrics"], semantic, saved[obj.Name]
                    )
                    for obj in owned.Objects
                },
            }
            report["phases"].append(phase)
            checkpoint()
            if not math.isclose(
                phase["sketch004_circle_radius_mm"], radius, rel_tol=0, abs_tol=1e-12
            ):
                raise ValueError("native circle did not follow controlled radius")
            expected_previous = radius
        report["status"] = "diagnostic_completed_not_migration_acceptance"
    except Exception as error:
        report["status"] = "failed_diagnostic"
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        for name in set(App.listDocuments()) - previous:
            try:
                App.closeDocument(name)
            except Exception as error:
                report["status"] = "failed_diagnostic"
                report["errors"].append(
                    {"stage": "cleanup", "type": type(error).__name__, "message": str(error)}
                )
        report["open_documents_after_cleanup"] = sorted(App.listDocuments())
        report["owned_document_closed"] = set(App.listDocuments()) == previous
        try:
            validate_request(root, request)
            report["all_inputs_snapshots_and_protected_bytes_unchanged"] = True
        except (OSError, ValueError) as error:
            report["all_inputs_snapshots_and_protected_bytes_unchanged"] = False
            report["status"] = "failed_diagnostic"
            report["errors"].append({"type": type(error).__name__, "message": str(error)})
        checkpoint()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", required=True)
    for name in ("freecad", "source", "candidate", "run-directory"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_run(args.freecad, args.source, args.candidate, args.run_directory)
    print(json.dumps(result, indent=2))
    return 0


if os.environ.get(FLAG) == "1":
    # The console can retry a failed script import. Preserve one diagnostic
    # instead of throwing after its final failed checkpoint; inspect status.
    native_capture()
elif __name__ == "__main__":
    raise SystemExit(main())
