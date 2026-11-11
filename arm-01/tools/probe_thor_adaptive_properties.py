"""Isolated optional OCP adaptive-property study; never imports FreeCAD.

Only the coordinator may launch this worker after runtime review/queue grant.
It reads exact cached BReps, not CAD documents. Adaptive estimates do not prove
exact geometry equivalence or establish manufacturing acceptance tolerances.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

FLAG = "RAFTEL_RUN_THOR_ADAPTIVE_PROPERTIES"
EPSILONS = (1e-4, 1e-6, 1e-8)
BREPS = {
    "source": "d0ed3dcd293f814b6db11e0e29a22e89a6aa4fe6c8d9f8e5c08e508baec2b9db",
    "candidate": "190d3f1560664eea784ae7edabed8442768d7c65ce4a8c040e1b9f3f5529016c",
}
ARCHIVES = {
    "source": "8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a",
    "candidate": "6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd",
}
FORBIDDEN_FLAGS = (
    "RAFTEL_RUN_THOR_ART1_PROBE",
    "RAFTEL_PREPARE_THOR_ART1_CANDIDATE",
    "RAFTEL_RUN_THOR_METRIC_SEMANTICS",
    "RAFTEL_RUN_THOR_SOLID_PROPERTIES",
)
ALL_ALGORITHMS = ("default", "adaptive_gauss", "adaptive_gauss_kronrod")
COMMON_SHA256 = "f6a8a4f48a7c13f75fbde9a6e57aefb26fce268fc52d43278c589d934fea0678"
COMMON_CONTEXT_SHA256 = "5141144ed1d338b0b083254a168c481772c9c2aa13a89eac8d6a7c9e7e0243ad"


def protocol_algorithms(request):
    version = request.get("protocol_version", 1)
    if type(version) is not int or version not in (1, 2, 3):
        raise ValueError("unsupported adaptive protocol version")
    expected = list(ALL_ALGORITHMS if version == 1 else ("default", "adaptive_gauss_kronrod"))
    declared = request.get("complex_algorithms", list(ALL_ALGORITHMS))
    if declared != expected:
        raise ValueError("complex algorithms must match the explicit protocol scope")
    if version == 3 and (
        request.get("input_scope") != "self_generated_wrist_common_only"
        or "derived_common" not in request
    ):
        raise ValueError("protocol3 requires explicit derived-common scope/provenance")
    if version != 3 and "derived_common" in request:
        raise ValueError("derived common requires its distinct protocol3")
    return version, expected


def fixture_gate_status(fixtures, selected_algorithms):
    if selected_algorithms not in (list(ALL_ALGORITHMS), ["default", "adaptive_gauss_kronrod"]):
        raise ValueError("fixture gate requires a declared supported algorithm scope")
    expected = fixture_expected()
    if set(fixtures) != set(expected):
        raise ValueError("all six analytic fixture cases are required")
    failures = []
    for name, rows in fixtures.items():
        if len(rows) != 3 or {r["algorithm"] for r in rows} != set(ALL_ALGORITHMS):
            raise ValueError("all three method rows per fixture must remain recorded")
        for row in rows:
            comparison = measurement_error(row, expected[name])
            if not comparison["verified"]:
                failures.append(dict(case=name, algorithm=row["algorithm"], comparison=comparison))
    return dict(
        original_all18_fixture_gate_passed=not failures,
        selected_algorithm_fixture_gate_passed=not any(
            r["algorithm"] in selected_algorithms for r in failures
        ),
        selected_algorithms=selected_algorithms,
        failed_fixture_measurements=failures,
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("finite numeric measurement required")
    return float(value)


def rotation_rows(axis=(1, 2, 3), degrees=37):
    norm = math.sqrt(sum(x * x for x in axis))
    x, y, z = (a / norm for a in axis)
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    d = 1 - c
    return [
        [c + x * x * d, x * y * d - z * s, x * z * d + y * s],
        [y * x * d + z * s, c + y * y * d, y * z * d - x * s],
        [z * x * d - y * s, z * y * d + x * s, c + z * z * d],
    ]


def fixture_expected():
    result = {}
    for name, volume, com, inertia in (
        ("box", 24.0, [1.0, 1.5, 2.0], [[50.0, 0.0, 0.0], [0.0, 40.0, 0.0], [0.0, 0.0, 26.0]]),
        (
            "cylinder",
            20 * math.pi,
            [0.0, 0.0, 2.5],
            [
                [20 * math.pi * 37 / 12, 0.0, 0.0],
                [0.0, 20 * math.pi * 37 / 12, 0.0],
                [0.0, 0.0, 40 * math.pi],
            ],
        ),
    ):
        for mode in ("base", "translated", "rotated_translated"):
            matrix = (
                rotation_rows()
                if mode == "rotated_translated"
                else [[float(i == j) for j in range(3)] for i in range(3)]
            )
            translation = [10.0, -20.0, 30.0] if mode != "base" else [0.0, 0.0, 0.0]
            result[name + "_" + mode] = dict(
                volume_mm3=volume,
                com_mm=[
                    sum(matrix[i][j] * com[j] for j in range(3)) + translation[i] for i in range(3)
                ],
                centroidal_inertia_mm5=[
                    [
                        sum(
                            matrix[i][k] * inertia[k][column] * matrix[j][column]
                            for k in range(3)
                            for column in range(3)
                        )
                        for j in range(3)
                    ]
                    for i in range(3)
                ],
            )
    return result


def measurement_error(actual, expected):
    volume_error = (
        abs(finite(actual["volume_mm3"]) - expected["volume_mm3"]) / expected["volume_mm3"]
    )
    com_error = max(
        abs(finite(a) - b) for a, b in zip(actual["com_mm"], expected["com_mm"], strict=True)
    )
    scale = max(abs(v) for row in expected["centroidal_inertia_mm5"] for v in row)
    inertia_error = max(
        abs(
            finite(actual["centroidal_inertia_mm5"][i][j])
            - expected["centroidal_inertia_mm5"][i][j]
        )
        / scale
        for i in range(3)
        for j in range(3)
    )
    return dict(
        relative_volume_error=volume_error,
        com_error_mm=com_error,
        relative_tensor_error=inertia_error,
        verified=volume_error < 1e-10 and com_error < 1e-9 and inertia_error < 1e-9,
    )


def validate_module_origins(records, package_root, file_manifest):
    """Reject mixed FreeCAD kernels using observed Windows module filenames."""
    expected = {r["relative_path"]: r["sha256"] for r in file_manifest["files"]}
    kernels = []
    for record in records:
        path = Path(record["path"]).resolve()
        name = path.name.casefold()
        if "freecad" in name or name in {"part.pyd", "part.dll", "partd.dll"}:
            raise ValueError("FreeCAD/Part DLL unexpectedly loaded in independent process")
        if name.startswith("tk") and name.endswith(".dll"):
            if not path.is_relative_to((package_root / "cadquery_ocp.libs").resolve()):
                raise ValueError("loaded TK DLL is outside the pinned OCP wheel root")
            relative = path.relative_to(package_root.resolve()).as_posix()
            if record.get("sha256") != expected.get(relative):
                raise ValueError("loaded TK DLL hash differs from verified wheel")
            kernels.append(record)
    if not kernels or not any(
        Path(r["path"]).name.casefold().startswith("tkernel-") and r.get("file_version") == "7.8.1"
        for r in kernels
    ):
        raise ValueError("observed pinned TKernel version7.8.1 is required")
    return kernels


def module_inventory():
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not powershell.is_file():
        raise ValueError("explicit System32 PowerShell inventory tool is unavailable")
    command = (
        f"@(Get-Process -Id {os.getpid()} | ForEach-Object {{$_.Modules}} | "
        "ForEach-Object {[pscustomobject]@{path=$_.FileName; "
        "file_version=$_.FileVersionInfo.FileVersion;"
        "product_version=$_.FileVersionInfo.ProductVersion}}) "
        "| ConvertTo-Json -Depth 3 -Compress"
    )
    result = subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    records = json.loads(result.stdout)
    if not isinstance(records, list):
        raise ValueError("expected an observed process module inventory")
    for record in records:
        try:
            record["sha256"] = sha(Path(record["path"]))
        except OSError:
            record["sha256"] = None
    return records


def guarded_inputs():
    if os.environ.get(FLAG) != "1" or any(os.environ.get(k) == "1" for k in FORBIDDEN_FLAGS):
        raise ValueError("explicit independent-worker opt-in and no inherited CAD flags required")
    if not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
        raise ValueError("worker requires Python -I -S -B isolation")
    root = Path(os.environ["RAFTEL_ADAPTIVE_RUN_DIR"]).resolve(strict=True)
    request_path = Path(os.environ["RAFTEL_ADAPTIVE_REQUEST"]).resolve(strict=True)
    output = root / "probe.json"
    if (
        not request_path.is_relative_to(root)
        or output.exists()
        or shutil.disk_usage(root).free < 50 * 1024**3 + 500_000_000
    ):
        raise ValueError("fresh request/output and 50 GiB reserve required")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if type(request.get("schema_version")) is not int or request["schema_version"] != 1:
        raise ValueError("unsupported adaptive request schema")
    protocol_algorithms(request)
    worker = Path(__file__).resolve()
    package_root = Path(request["package_root"]).resolve(strict=True)
    manifest_path = Path(request["package_manifest"]).resolve(strict=True)
    if (
        not worker.is_relative_to(root / "capture-tool")
        or sha(worker) != request["worker_sha256"]
        or package_root != root.parent / "packages"
        or manifest_path != root.parent / "packages-manifest.json"
        or sha(manifest_path) != request["package_manifest_sha256"]
        or sha(Path(sys.executable)) != request["python_executable_sha256"]
        or sha(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
        != request["powershell_executable_sha256"]
    ):
        raise ValueError("worker/interpreter/package snapshot identity differs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in manifest["files"]:
        path = (package_root / row["relative_path"]).resolve()
        if not path.is_relative_to(package_root) or sha(path) != row["sha256"]:
            raise ValueError("extracted package bytes differ from wheel manifest")
    for name in BREPS:
        row = request["inputs"][name]
        for key, pin in (("brep", BREPS[name]), ("archive", ARCHIVES[name])):
            path = Path(row[key + "_path"]).resolve(strict=True)
            if not path.is_relative_to(root / "inputs") or sha(path) != pin:
                raise ValueError("source/candidate raw input pin differs")
    if request.get("protocol_version") == 3:
        common = request["derived_common"]
        brep = Path(common["brep_path"]).resolve(strict=True)
        context = Path(common["reference_capture_path"]).resolve(strict=True)
        if (
            any(not p.is_relative_to(root / "inputs") for p in (brep, context))
            or sha(brep) != COMMON_SHA256
            or brep.stat().st_size != 900661
            or common["reference_capture_sha256"] != COMMON_CONTEXT_SHA256
            or sha(context) != COMMON_CONTEXT_SHA256
        ):
            raise ValueError("derived common BRep/context pin differs")
        captured = json.loads(context.read_text(encoding="utf-8"))
        if (
            captured["debug_BRep"]["sha256"] != COMMON_SHA256
            or captured["source_bytes_unchanged"] is not True
            or len(captured["source_sha256_before"]) != 57
            or captured["source_sha256_before"] != captured["source_sha256_after"]
            or captured["coordinate_frame"] != "native_CAD_world_mm"
        ):
            raise ValueError("derived common context does not bind the unchanged input")
    return root, request_path, request, package_root, manifest, output


def native_capture():
    root, request_path, request, package_root, manifest, output = guarded_inputs()
    protocol_version, complex_algorithms = protocol_algorithms(request)
    report = dict(
        schema_version=1,
        evidence_class="independent_OCCT_distributor_adaptive_metric_study_not_equivalence",
        audit_status="starting",
        request_sha256=sha(request_path),
        worker_sha256=sha(Path(__file__)),
        package_manifest_sha256=request["package_manifest_sha256"],
        python_executable=str(sys.executable),
        python_version=sys.version,
        module_inventory_tool_sha256=request["powershell_executable_sha256"],
        freecad_imported=False,
        CAD_document_open_recompute_or_save=False,
        same_binary_kernel_as_FreeCAD=False,
        full_OS_library_bundle_verified=False,
        migration_accepted=False,
        candidate_accepted=False,
        manufacturing_released=False,
        fixtures={},
        measurements={},
        errors=[],
        protocol_version=protocol_version,
        complex_algorithms=complex_algorithms,
        regular_gauss_tensor_scope_accepted=False,
    )
    checkpoint_index = 0
    checkpoint_sha = None

    def checkpoint():
        nonlocal checkpoint_index, checkpoint_sha
        contents = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if checkpoint_sha is None:
            with output.open("xb") as stream:
                stream.write(contents)
            checkpoint_sha = hashlib.sha256(contents).hexdigest()
            return
        if sha(output) != checkpoint_sha:
            raise ValueError("own checkpoint changed externally")
        temporary = root / f"checkpoint-{checkpoint_index:03d}.json.tmp"
        checkpoint_index += 1
        with temporary.open("xb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
        checkpoint_sha = hashlib.sha256(contents).hexdigest()

    checkpoint()
    started = time.monotonic()
    handles = []
    try:
        for name in ("cadquery_ocp.libs", "vtk.libs"):
            handles.append(os.add_dll_directory(str(package_root / name)))
        sys.path.insert(0, str(package_root))
        import OCP
        from OCP.BRep import BRep_Builder
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.BRepGProp import BRepGProp
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
        from OCP.BRepTools import BRepTools
        from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
        from OCP.GProp import GProp_GProps
        from OCP.TopoDS import TopoDS_Shape

        if any(n == "FreeCAD" or n == "Part" or n.startswith("FreeCAD.") for n in sys.modules):
            raise ValueError("FreeCAD/Part module unexpectedly imported")
        report["binding_version"] = OCP.__version__
        report["binding_module_path"] = OCP.__file__
        report["native_binding_module_path"] = OCP.OCP.__file__
        report["native_binding_module_sha256"] = sha(Path(OCP.OCP.__file__))
        expected_files = {r["relative_path"]: r["sha256"] for r in manifest["files"]}
        native_path = Path(OCP.OCP.__file__).resolve()
        if (
            Path(OCP.__file__).resolve() != package_root / "OCP/__init__.py"
            or not native_path.is_relative_to(package_root / "OCP")
            or report["native_binding_module_sha256"]
            != expected_files.get(native_path.relative_to(package_root).as_posix())
        ):
            raise ValueError("imported binding differs from verified wheel root")
        report["api_docstrings"] = {
            k: getattr(BRepGProp, k).__doc__ for k in ("VolumeProperties_s", "VolumePropertiesGK_s")
        }
        report["loaded_modules_before_measurements"] = module_inventory()
        report["verified_kernel_modules_before"] = validate_module_origins(
            report["loaded_modules_before_measurements"], package_root, manifest
        )
        if not str(OCP.__version__).startswith("7.8.1"):
            raise ValueError("independent binding is not version7.8.1-compatible")

        def measure(shape, algorithm, epsilon=None, only_closed=False, record_failure=False):
            props = GProp_GProps()
            estimate = None
            if algorithm == "default":
                BRepGProp.VolumeProperties_s(
                    shape, props, OnlyClosed=only_closed, SkipShared=False, UseTriangulation=False
                )
            elif algorithm == "adaptive_gauss":
                estimate = BRepGProp.VolumeProperties_s(
                    shape, props, Eps=epsilon, OnlyClosed=False, SkipShared=False
                )
            else:
                estimate = BRepGProp.VolumePropertiesGK_s(
                    shape,
                    props,
                    Eps=epsilon,
                    OnlyClosed=only_closed,
                    IsUseSpan=True,
                    CGFlag=True,
                    IFlag=True,
                    SkipShared=False,
                )
            if estimate is not None and finite(estimate) < 0:
                if record_failure:
                    return dict(
                        algorithm=algorithm,
                        requested_relative_epsilon=epsilon,
                        returned_relative_error_estimate=estimate,
                        only_closed=only_closed,
                        integration_failure_reported=True,
                        volume_mm3=None,
                        com_mm=None,
                        centroidal_inertia_mm5=None,
                        estimate_is_rigorous_geometry_error_bound=False,
                    )
                raise ValueError("native integration returned failure estimate")
            com = props.CentreOfMass()
            inertia = props.MatrixOfInertia()
            return dict(
                algorithm=algorithm,
                requested_relative_epsilon=epsilon,
                returned_relative_error_estimate=estimate,
                volume_mm3=finite(props.Mass()),
                com_mm=[finite(com.X()), finite(com.Y()), finite(com.Z())],
                centroidal_inertia_mm5=[
                    [finite(inertia.Value(i + 1, j + 1)) for j in range(3)] for i in range(3)
                ],
                estimate_is_rigorous_geometry_error_bound=False,
                only_closed=only_closed,
            )

        expected = fixture_expected()
        report["analytic_fixture_expectations"] = expected
        for name, truth in expected.items():
            shape = (
                BRepPrimAPI_MakeBox(2, 3, 4).Shape()
                if name.startswith("box")
                else BRepPrimAPI_MakeCylinder(2, 5).Shape()
            )
            if not name.endswith("_base"):
                transform = gp_Trsf()
                if "rotated" in name:
                    transform.SetRotation(
                        gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 2, 3)), math.radians(37)
                    )
                transform.SetTranslationPart(gp_Vec(10, -20, 30))
                shape = BRepBuilderAPI_Transform(shape, transform, True).Shape()
            records = []
            report["fixtures"][name] = records
            for algorithm in ("default", "adaptive_gauss", "adaptive_gauss_kronrod"):
                row = measure(shape, algorithm, None if algorithm == "default" else 1e-8)
                row["analytic_fixture_comparison"] = measurement_error(row, truth)
                records.append(row)
                checkpoint()
        gates = fixture_gate_status(report["fixtures"], complex_algorithms)
        report.update(gates)
        report["fixture_first_gate_passed"] = gates["selected_algorithm_fixture_gate_passed"]
        report["fixture_first_gate_scope"] = complex_algorithms
        checkpoint()
        if not gates["selected_algorithm_fixture_gate_passed"]:
            raise ValueError("independent analytic fixture gate failed; retained method residuals")
        for name in () if protocol_version == 3 else BREPS:
            shape = TopoDS_Shape()
            if not BRepTools.Read_s(shape, request["inputs"][name]["brep_path"], BRep_Builder()):
                raise ValueError("pinned cached BRep could not be read")
            if not BRepCheck_Analyzer(shape).IsValid():
                raise ValueError("pinned cached BRep is invalid in independent kernel")
            report["measurements"][name] = [measure(shape, "default")]
            checkpoint()
            for epsilon in EPSILONS:
                for algorithm in [a for a in complex_algorithms if a != "default"]:
                    if time.monotonic() - started > 150:
                        raise ValueError("bounded integration budget exhausted")
                    report["measurements"][name].append(measure(shape, algorithm, epsilon))
                    checkpoint()
        if protocol_version == 3:
            from OCP.TopAbs import TopAbs_ShapeEnum
            from OCP.TopExp import TopExp_Explorer

            def children(shape, kind):
                explorer = TopExp_Explorer(shape, kind)
                result = []
                while explorer.More():
                    result.append(explorer.Current())
                    explorer.Next()
                return result

            binding = request["derived_common"]
            common = TopoDS_Shape()
            if not BRepTools.Read_s(common, binding["brep_path"], BRep_Builder()):
                raise ValueError("derived common cannot be read")
            context = json.loads(
                Path(binding["reference_capture_path"]).read_text(encoding="utf-8")
            )
            solids = children(common, TopAbs_ShapeEnum.TopAbs_SOLID)
            faces = children(common, TopAbs_ShapeEnum.TopAbs_FACE)
            if len(solids) != 3 or len(faces) != 11:
                raise ValueError("derived common topology count differs from retained context")
            study = dict(
                evidence_class="self_generated_BooleanCommon_not_upstream_Git_body",
                brep_sha256=sha(Path(binding["brep_path"])),
                reference_capture_sha256=binding["reference_capture_sha256"],
                coordinate_frame=context["coordinate_frame"],
                pose=context["pose"],
                source_sha256_before=context["source_sha256_before"],
                source_sha256_after=context["source_sha256_after"],
                native_shape_valid=BRepCheck_Analyzer(common).IsValid(),
                compound_orientation=str(common.Orientation()),
                faces=[],
                contexts={},
                sums={},
            )
            report["derived_common_study"] = study
            owner_faces = [children(s, TopAbs_ShapeEnum.TopAbs_FACE) for s in solids]
            study["solid_face_counts"] = [len(items) for items in owner_faces]
            for index, face in enumerate(faces, 1):
                owners = []
                for solid_index, items in enumerate(owner_faces, 1):
                    for local_index, owned in enumerate(items, 1):
                        if face.IsSame(owned):
                            owners.append(
                                dict(
                                    solid_index=solid_index,
                                    local_face_index=local_index,
                                    owner_solid_orientation=str(
                                        solids[solid_index - 1].Orientation()
                                    ),
                                    owner_face_orientation=str(owned.Orientation()),
                                    IsSame=True,
                                    IsEqual_including_orientation=face.IsEqual(owned),
                                )
                            )
                study["faces"].append(
                    dict(
                        face_index=index,
                        compound_face_orientation=str(face.Orientation()),
                        owners=owners,
                    )
                )
            shapes = [("aggregate", common)] + [(f"solid-{i}", s) for i, s in enumerate(solids, 1)]
            for label, shape in shapes:
                study["contexts"][label] = [
                    measure(shape, "default", only_closed=False),
                    measure(shape, "default", only_closed=True),
                ]
                checkpoint()
            for label, shape in shapes:
                if time.monotonic() - started > 150:
                    raise ValueError("derived study integration budget exhausted")
                try:
                    row = measure(shape, "adaptive_gauss_kronrod", 1e-8, record_failure=True)
                except Exception as error:
                    row = dict(
                        algorithm="adaptive_gauss_kronrod",
                        requested_relative_epsilon=1e-8,
                        error=dict(type=type(error).__name__, message=str(error)),
                        integration_accepted=False,
                    )
                study["contexts"][label].append(row)
                checkpoint()
            for position, setting in enumerate(
                ("default_open", "default_only_closed", "GK_1e_minus8")
            ):
                rows = [study["contexts"][f"solid-{i}"][position] for i in range(1, 4)]
                aggregate = study["contexts"]["aggregate"][position]
                study["sums"][setting] = (
                    None
                    if (
                        "error" in aggregate
                        or aggregate.get("integration_failure_reported")
                        or any("error" in r or r.get("integration_failure_reported") for r in rows)
                    )
                    else dict(
                        aggregate_volume_mm3=aggregate["volume_mm3"],
                        per_solid_volume_sum_mm3=math.fsum(r["volume_mm3"] for r in rows),
                        aggregate_minus_solid_sum_mm3=aggregate["volume_mm3"]
                        - math.fsum(r["volume_mm3"] for r in rows),
                    )
                )
            study["absolute_values_or_healing_or_orientation_changes_applied"] = False
            study["geometric_overlap_accepted"] = False
            checkpoint()
        report["loaded_modules_after_measurements"] = module_inventory()
        report["verified_kernel_modules_after"] = validate_module_origins(
            report["loaded_modules_after_measurements"], package_root, manifest
        )
        report["audit_status"] = "complete_independent_adaptive_diagnostic_not_equivalence"
    except Exception as error:
        report["audit_status"] = "failed_independent_adaptive_diagnostic"
        report["errors"].append(dict(type=type(error).__name__, message=str(error)))
    report["input_sha256_after"] = {
        name: {kind: sha(Path(row[kind + "_path"])) for kind in ("archive", "brep")}
        for name, row in request["inputs"].items()
    }
    report["source_candidate_input_bytes_unchanged"] = all(
        report["input_sha256_after"][n]["brep"] == BREPS[n]
        and report["input_sha256_after"][n]["archive"] == ARCHIVES[n]
        for n in BREPS
    )
    report["worker_request_bytes_unchanged"] = (
        sha(Path(__file__)) == report["worker_sha256"]
        and sha(request_path) == report["request_sha256"]
    )
    if protocol_version == 3:
        binding = request["derived_common"]
        report["derived_common_input_sha256_after"] = sha(Path(binding["brep_path"]))
        report["derived_context_sha256_after"] = sha(Path(binding["reference_capture_path"]))
        report["derived_input_bytes_unchanged"] = (
            report["derived_common_input_sha256_after"] == COMMON_SHA256
            and report["derived_context_sha256_after"] == binding["reference_capture_sha256"]
        )
        if not report["derived_input_bytes_unchanged"]:
            report["audit_status"] = "failed_derived_input_preservation"
    report["extracted_package_bytes_unchanged"] = all(
        sha(package_root / row["relative_path"]) == row["sha256"] for row in manifest["files"]
    )
    if not all(
        report[k]
        for k in (
            "worker_request_bytes_unchanged",
            "extracted_package_bytes_unchanged",
            "source_candidate_input_bytes_unchanged",
        )
    ):
        report["audit_status"] = "failed_preservation_gate"
    report["elapsed_seconds"] = time.monotonic() - started
    checkpoint()
    print("RAFTEL_ADAPTIVE_REPORT", report["audit_status"], str(output))
    return report


if __name__ == "__main__":
    native_capture()
