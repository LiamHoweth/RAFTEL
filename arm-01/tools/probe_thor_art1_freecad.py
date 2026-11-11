"""Run a bounded, copied-document Art1 drift/cut probe in isolated FreeCAD.

The default Python entry point only launches a separately supplied native
executable. The native branch requires an explicit environment opt-in, pinned
source/copy hashes, isolated user/system parameter paths and no open documents.
The default probe never saves a CAD document or remaps a support. A separate
explicit candidate entry point can supply its guarded once-save callback.
Native execution is optional.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import runpy
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DIAGNOSTICS = runpy.run_path(str(Path(__file__).with_name("thor_art1_diagnostics.py")))
SOURCE_SHA256 = DIAGNOSTICS["SOURCE_SHA256"]
PROBE_FLAG = "RAFTEL_RUN_THOR_ART1_PROBE"
FEATURES = (
    "Sketch",
    "Pad",
    "Sketch001",
    "Pad001",
    "DatumPlane",
    "Sketch002",
    "Groove",
    "Thickness",
    "Sketch003",
    "Pad002",
    "Sketch004",
    "Pocket",
    "DatumPlane001",
    "Sketch005",
    "Pocket001",
    "Body",
)
BOUNDS = ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
EXPERIMENTS = {
    "unchanged": {},
    "intersection": {"Thickness.Intersection": True},
    "intersection_freeze_bolt_frame": {
        "Thickness.Intersection": True,
        "Sketch004.MapMode": "Deactivated",
        "Sketch004.Placement": "exact_pinned_saved_placement",
    },
    "intersection_pocket_length": {"Thickness.Intersection": True, "Pocket.Type": "Length"},
    "intersection_pocket_through_all": {
        "Thickness.Intersection": True,
        "Pocket.Type": "ThroughAll",
    },
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def _vector(value: object, field: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{field} must contain three finite coordinates")
    return [_finite(item, field) for item in value]


def _axis(value: object) -> list[float]:
    axis = _vector(value, "axis")
    norm = math.sqrt(sum(x * x for x in axis))
    if abs(norm - 1) > 1e-10:
        raise ValueError("axis must have unit norm")
    return axis


def bolt_support_descriptor(contract: dict, *, head: bool = False, kind: str = "circle") -> dict:
    """Describe geometry, never an edge index; head and body remain distinct."""
    if contract.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("support descriptor requires the pinned source fingerprint")
    if kind not in {"circle", "cylinder"}:
        raise ValueError("support kind must be circle or cylinder")
    sketch = "Sketch005" if head else "Sketch004"
    circles = [item for item in contract["saved_circle_frames"] if item["sketch"] == sketch]
    if len(circles) != 1:
        raise ValueError("saved source sketch does not identify exactly one bolt circle")
    circle = circles[0]
    return {
        "kind": kind,
        "semantic_name": "first_bolt_head_recess" if head else "first_bolt_body_hole",
        "source_sketch": sketch,
        "source_sha256": SOURCE_SHA256,
        "center_mm": _vector(circle["center_in_native_mm"], "source center"),
        "axis": _axis(circle["normal_in_native"]),
        "radius_mm": _finite(circle["radius_mm"], "source radius"),
        "full_circle": kind == "circle",
        "coordinate_frame": "native_Art1_Body_identity_mm",
    }


def match_semantic_support(
    expected: dict,
    candidates: list[dict],
    *,
    position_tolerance_mm: float = 1e-7,
    radius_tolerance_mm: float = 1e-7,
    axis_tolerance: float = 1e-10,
) -> dict:
    """Return only a unique geometric match; no nearest-edge fallback or mutation.

    Circle centers must match in 3D; cylinder centers define axis lines, so their
    longitudinal coordinate may differ. Axis sign is immaterial for these geometric
    supports. A unique match is a diagnostic candidate, not an attachment approval.
    """
    for tolerance in (position_tolerance_mm, radius_tolerance_mm, axis_tolerance):
        if not 0 < _finite(tolerance, "tolerance") <= 0.001:
            raise ValueError("matching tolerances must be positive and bounded by 0.001")
    kind = expected.get("kind")
    if kind not in {"circle", "cylinder"}:
        raise ValueError("expected kind must be circle or cylinder")
    center = _vector(expected.get("center_mm"), "expected center")
    axis = _axis(expected.get("axis"))
    radius = _finite(expected.get("radius_mm"), "expected radius")
    if radius <= 0:
        raise ValueError("expected radius must be positive")
    if not isinstance(candidates, list):
        raise ValueError("support candidates must be a list")
    names = [item.get("subelement") for item in candidates]
    if any(not isinstance(name, str) or not name for name in names) or len(names) != len(
        set(names)
    ):
        raise ValueError("support candidate names must be nonempty and unique")
    matches = []
    diagnostics = []
    for candidate in candidates:
        if candidate.get("kind") not in {"circle", "cylinder"}:
            raise ValueError("unsupported candidate geometry type")
        actual_center = _vector(candidate.get("center_mm"), "candidate center")
        actual_axis = _axis(candidate.get("axis"))
        actual_radius = _finite(candidate.get("radius_mm"), "candidate radius")
        if actual_radius <= 0:
            raise ValueError("candidate radius must be positive")
        dot = sum(a * b for a, b in zip(axis, actual_axis, strict=True))
        axis_error = min(
            math.sqrt(sum((a - b) ** 2 for a, b in zip(axis, actual_axis, strict=True))),
            math.sqrt(sum((a + b) ** 2 for a, b in zip(axis, actual_axis, strict=True))),
        )
        delta = [a - b for a, b in zip(actual_center, center, strict=True)]
        along = sum(a * b for a, b in zip(delta, axis, strict=True))
        distance = math.sqrt(
            sum(
                (component - along * direction if kind == "cylinder" else component) ** 2
                for component, direction in zip(delta, axis, strict=True)
            )
        )
        matched = (
            candidate["kind"] == kind
            and distance <= position_tolerance_mm
            and abs(actual_radius - radius) <= radius_tolerance_mm
            and axis_error <= axis_tolerance
            and (kind != "circle" or candidate.get("full_circle") is True)
        )
        diagnostics.append(
            {
                "subelement": candidate["subelement"],
                "position_or_axis_line_error_mm": distance,
                "radius_error_mm": abs(actual_radius - radius),
                "unoriented_axis_error": axis_error,
                "axis_dot": dot,
                "matches": matched,
            }
        )
        if matched:
            matches.append(candidate["subelement"])
    return {
        "status": "unique" if len(matches) == 1 else "no_match" if not matches else "ambiguous",
        "selected_subelement": matches[0] if len(matches) == 1 else None,
        "matching_subelements": matches,
        "candidate_diagnostics": diagnostics,
        "support_remapped": False,
        "interpretation": "Geometric diagnostic only; confirm mechanical meaning before any remap.",
    }


def validate_probe_paths(
    source: Path, copied: Path, report: Path, user_cfg: Path, system_cfg: Path
) -> None:
    """Guard an already prepared run before native document loading."""
    paths = [
        source.resolve(),
        copied.resolve(),
        report.resolve(),
        user_cfg.resolve(),
        system_cfg.resolve(),
    ]
    if len(paths) != len(set(paths)):
        raise ValueError("source, copy, report and preference paths must all differ")
    if source.suffix.casefold() != ".fcstd" or copied.suffix.casefold() != ".fcstd":
        raise ValueError("source and copy must be native FreeCAD files")
    if report.suffix.casefold() != ".json" or report.exists():
        raise ValueError("report must be a new JSON path")
    if user_cfg.name != "user.cfg" or system_cfg.name != "system.cfg":
        raise ValueError("use the dedicated user.cfg and system.cfg run preferences")
    run_directory = copied.parent.resolve()
    if any(path.parent != run_directory for path in paths[2:]):
        raise ValueError("report and isolated preferences must be inside the copy's run directory")
    if source.resolve().is_relative_to(run_directory):
        raise ValueError("upstream source must remain outside the new run directory")
    if _sha(source) != SOURCE_SHA256 or _sha(copied) != SOURCE_SHA256:
        raise ValueError("source and copied document must both match the pinned Art1 SHA-256")


def feature_drift_summary(saved: dict, rebuilt: dict) -> dict:
    """Rank captured metric changes without claiming full geometric equivalence."""
    rows = []
    for name in FEATURES:
        if name not in saved or name not in rebuilt:
            continue
        before = saved[name]["shape"]
        after = rebuilt[name].get("shape")
        states = rebuilt[name].get("states")
        clean = states == ["Up-to-date"]
        changes = {}
        unmeasured = []
        if after is None or before.get("is_null") or after.get("is_null"):
            changes["null_or_missing_shape"] = True
        elif before.get("unbounded_construction_geometry") or after.get(
            "unbounded_construction_geometry"
        ):
            unmeasured.append("unbounded_construction_geometry_metrics")
        else:
            for field, tolerance in (
                ("volume_mm3", 1e-6),
                ("area_mm2", 1e-6),
                ("length_mm", 1e-9),
                ("bounds_mm", 1e-9),
                ("center_of_mass_mm", 1e-9),
            ):
                first, second = before[field], after[field]
                if first is None or second is None:
                    unmeasured.append(field)
                    continue
                if isinstance(first, list):
                    if len(first) != len(second):
                        raise ValueError("metric vector dimensions differ")
                    error = max(
                        abs(_finite(a, field) - _finite(b, field))
                        for a, b in zip(first, second, strict=True)
                    )
                else:
                    error = abs(_finite(first, field) - _finite(second, field))
                if error >= tolerance:
                    changes[field] = error
            for field in ("valid", "solid_count", "face_count", "edge_count"):
                if before[field] != after[field]:
                    changes[field] = {"saved": before[field], "attempted": after[field]}
        rows.append(
            {
                "name": name,
                "own_state_clean": clean,
                "upstream_dependency_state_checked": False,
                "states": states,
                "changed_metrics": changes,
                "unmeasured_metric_fields": unmeasured,
                "interpretation": "own state Up-to-date; upstream dependencies remain unverified"
                if clean
                else "cached or failed dependency shape possible",
            }
        )
    return {
        "features": rows,
        "first_changed_captured_feature": next(
            (r["name"] for r in rows if r["changed_metrics"] and r["own_state_clean"]), None
        ),
        "first_own_state_unclean_feature": next(
            (r["name"] for r in rows if not r["own_state_clean"]), None
        ),
        "first_true_semantic_drift": None,
        "full_shape_equivalence_verified": False,
        "full_dependency_closure_checked": False,
        "interpretation": (
            "Metric drift localizes the next inspection; unchanged metrics are not "
            "full shape equivalence."
        ),
    }


def native_shape_metrics(shape) -> dict:
    """Measure generic imported BReps without assuming a Solid-only COM property.

    For solids, centroid is volume-weighted from native Solid subshapes. Non-solid
    sketch/datum geometry has no volumetric COM and remains explicitly unknown.
    """
    if shape.isNull():
        return {"is_null": True, "valid": False}
    solids = list(shape.Solids)
    volume = math.fsum(solid.Volume for solid in solids)
    centroid = None
    if volume > 0:
        centers = [getattr(solid, "CenterOfMass", None) for solid in solids]
        if all(center is not None for center in centers):
            centroid = [
                math.fsum(
                    solid.Volume * list(center)[i]
                    for solid, center in zip(solids, centers, strict=True)
                )
                / volume
                for i in range(3)
            ]
    bounds = [getattr(shape.BoundBox, key) for key in BOUNDS]
    return {
        "is_null": False,
        "valid": bool(shape.isValid()),
        "solid_count": len(solids),
        "face_count": len(shape.Faces),
        "edge_count": len(shape.Edges),
        "volume_mm3": volume if solids else None,
        "raw_native_volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "length_mm": shape.Length,
        "bounds_mm": bounds,
        "unbounded_construction_geometry": any(abs(value) >= 1e50 for value in bounds),
        "center_of_mass_mm": centroid,
        "centroid_measurement": "volume_weighted_native_solid_centroids"
        if centroid is not None
        else "unmeasured_no_available_volumetric_centroid",
        "shape_placement_matrix": list(shape.Placement.toMatrix().A),
    }


def _checkpoint(report_path: Path, report: dict, *, first: bool = False) -> None:
    data = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if first:
        with report_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
    else:
        temporary = report_path.with_suffix(".checkpoint.tmp")
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
        temporary.replace(report_path)


def native_capture(*, after_capture=None) -> None:
    """Capture saved BReps and a forced-rebuild attempt; never save CAD files."""
    if os.environ.get(PROBE_FLAG) != "1" and not (
        after_capture is not None and os.environ.get("RAFTEL_PREPARE_THOR_ART1_CANDIDATE") == "1"
    ):
        raise ValueError("native Art1 probe requires explicit environment opt-in")
    source = Path(os.environ["RAFTEL_THOR_ART1_SOURCE"])
    copied = Path(os.environ["RAFTEL_THOR_ART1_COPY"])
    report_path = Path(os.environ["RAFTEL_THOR_ART1_REPORT"])
    user_cfg = Path(os.environ["RAFTEL_THOR_ART1_USER_CFG"])
    system_cfg = Path(os.environ["RAFTEL_THOR_ART1_SYSTEM_CFG"])
    experiment = os.environ["RAFTEL_THOR_ART1_EXPERIMENT"]
    if experiment not in EXPERIMENTS:
        raise ValueError("unsupported diagnostic experiment")
    validate_probe_paths(source, copied, report_path, user_cfg, system_cfg)
    isolated_data = {
        key: Path(os.environ[variable]).resolve()
        for key, variable in (
            ("UserHomePath", "FREECAD_USER_HOME"),
            ("UserAppData", "FREECAD_USER_DATA"),
            ("AppTempPath", "FREECAD_USER_TEMP"),
        )
    }
    if any(
        not path.is_dir() or not path.is_relative_to(copied.parent.resolve())
        for path in isolated_data.values()
    ):
        raise ValueError(
            "native user home/data/temp directories must exist inside the isolated run"
        )
    evidence_path = (
        Path(__file__).parents[1] / "hardware" / "cad" / "thor-art1-migration-evidence.json"
    )
    contract = DIAGNOSTICS["source_fingerprint"](source, DIAGNOSTICS["_load"](evidence_path))
    report = {
        "schema_version": 1,
        "evidence_class": "native_single_document_drift_probe_attempt",
        "source_revision": DIAGNOSTICS["SOURCE_REVISION"],
        "source_sha256_before": SOURCE_SHA256,
        "copied_source_sha256_before": SOURCE_SHA256,
        "capture_script_sha256": _sha(Path(__file__)),
        "diagnostic_helper_sha256": _sha(Path(__file__).with_name("thor_art1_diagnostics.py")),
        "migration_evidence_sha256": _sha(evidence_path),
        "runner_declared_native_executable_sha256": os.environ.get(
            "RAFTEL_THOR_ART1_EXECUTABLE_SHA256"
        ),
        "full_runtime_and_addon_bundle_verified": False,
        "experiment": experiment,
        "changed_properties": EXPERIMENTS[experiment],
        "audit_status": "starting",
        "native_document_saved": False,
        "migration_accepted": False,
        "source_saved_brep_measurements": {},
        "restored_document_measurements": {},
        "force_rebuild_attempt_measurements": {},
        "semantic_supports": {},
        "errors": [],
    }
    _checkpoint(report_path, report, first=True)
    try:
        import FreeCAD as App
        import Part
    except ImportError as error:
        report.update(
            audit_status="failed_probe",
            source_sha256_after=_sha(source),
            copied_source_sha256_after=_sha(copied),
        )
        report["source_and_copy_bytes_unchanged"] = (
            report["source_sha256_after"] == report["copied_source_sha256_after"] == SOURCE_SHA256
        )
        report["errors"].append({"stage": "native_import", "message": str(error)})
        _checkpoint(report_path, report)
        raise ValueError(
            "FreeCAD/Part runtime unavailable; native capture was not executed"
        ) from error

    previous = set(App.listDocuments())
    document = None

    def geometry_candidates(shape) -> list[dict]:
        candidates = []
        for index, edge in enumerate(shape.Edges, 1):
            curve = edge.Curve
            if type(curve).__name__ == "Circle":
                candidates.append(
                    {
                        "kind": "circle",
                        "subelement": f"Edge{index}",
                        "center_mm": list(curve.Center),
                        "axis": list(curve.Axis),
                        "radius_mm": curve.Radius,
                        "full_circle": abs(edge.Length - 2 * math.pi * curve.Radius) <= 1e-7,
                    }
                )
        for index, face in enumerate(shape.Faces, 1):
            surface = face.Surface
            if type(surface).__name__ == "Cylinder":
                candidates.append(
                    {
                        "kind": "cylinder",
                        "subelement": f"Face{index}",
                        "center_mm": list(surface.Center),
                        "axis": list(surface.Axis),
                        "radius_mm": surface.Radius,
                        "bounds_mm": [getattr(face.BoundBox, key) for key in BOUNDS],
                        "surface_area_mm2": face.Area,
                    }
                )
        return candidates

    def object_info(obj) -> dict:
        item = {"states": list(obj.State), "placement_matrix": list(obj.Placement.toMatrix().A)}
        if hasattr(obj, "Shape"):
            item["shape"] = native_shape_metrics(obj.Shape)
        if hasattr(obj, "Geometry"):
            item["sketch_geometry"] = [str(value) for value in obj.Geometry]
            item["fully_constrained"] = bool(obj.FullyConstrained)
            item["expressions"] = [list(value) for value in obj.ExpressionEngine]
            item["constraints_repr"] = [str(value) for value in obj.Constraints]
            item["external_geometry_repr"] = str(obj.ExternalGeometry)
            circles = []
            for geometry in obj.Geometry:
                if type(geometry).__name__ != "Circle":
                    continue
                circles.append(
                    {
                        "center_in_sketch_mm": list(geometry.Center),
                        "center_in_document_mm": list(obj.Placement.multVec(geometry.Center)),
                        "axis_in_document": list(obj.Placement.Rotation.multVec(geometry.Axis)),
                        "radius_mm": geometry.Radius,
                    }
                )
            item["sketch_circle_frames"] = circles
        if hasattr(obj, "MapMode"):
            item["attachment_parameters"] = {
                "map_mode": str(obj.MapMode),
                "map_reversed": bool(obj.MapReversed),
                "offset_matrix": list(obj.AttachmentOffset.toMatrix().A),
            }
        item["selected_operation_property_repr"] = {
            key: str(getattr(obj, key))
            for key in (
                "Type",
                "Length",
                "Length2",
                "Reversed",
                "SideType",
                "Profile",
                "BaseFeature",
                "Support",
            )
            if hasattr(obj, key)
        }
        return item

    def face9_info(shape) -> dict:
        face = shape.Faces[8]
        result = {
            "surface_type": type(face.Surface).__name__,
            "bounds_mm": [getattr(face.BoundBox, key) for key in BOUNDS],
        }
        if result["surface_type"] == "Plane":
            result["point_mm"] = list(face.CenterOfMass)
            result["normal"] = list(face.normalAt(0, 0))
            center = bolt_support_descriptor(contract)["center_mm"]
            result["bolt_center_to_plane_distance_mm"] = abs(
                math.fsum(
                    (a - b) * n
                    for a, b, n in zip(center, result["point_mm"], result["normal"], strict=True)
                )
            )
        return result

    try:
        if previous:
            raise ValueError("run in an isolated native console with no documents already open")
        actual_configs = {key: App.ConfigGet(key) for key in ("UserParameter", "SystemParameter")}
        report["runtime_parameter_paths"] = actual_configs
        if (
            Path(actual_configs["UserParameter"]).resolve() != user_cfg.resolve()
            or Path(actual_configs["SystemParameter"]).resolve() != system_cfg.resolve()
        ):
            raise ValueError("runtime did not select the dedicated user/system preference paths")
        actual_data = {key: App.ConfigGet(key) for key in isolated_data}
        report["runtime_data_paths"] = actual_data
        if any(Path(actual_data[key]).resolve() != path for key, path in isolated_data.items()):
            raise ValueError("runtime did not select the dedicated user home/data/temp directories")
        report["freecad_version"] = list(App.Version())
        report["python_version"] = sys.version
        report["opencascade_version"] = getattr(Part, "OCC_VERSION", None)
        report["external_addon_paths_requested"] = False
        # Load exact saved BRep members independently of restoring feature history.
        saved_shapes = {}
        brep_directory = copied.parent / "saved-breps"
        brep_directory.mkdir(exist_ok=False)
        with zipfile.ZipFile(source) as archive:
            for name in FEATURES:
                if name == "Body":
                    xml = DIAGNOSTICS["ET"].fromstring(archive.read("Document.xml"))
                    member = xml.find(
                        './ObjectData/Object[@name="Body"]/Properties/Property[@name="Shape"]/Part'
                    ).attrib["file"]
                else:
                    record = next(item for item in contract["members"] if item["name"] == name)
                    member = record.get("saved_brep", {}).get("member")
                if member is None:
                    continue
                data = archive.read(member)
                brep_path = brep_directory / f"{name}.brep"
                with brep_path.open("xb") as stream:
                    stream.write(data)
                shape = Part.Shape()
                shape.read(str(brep_path))
                saved_shapes[name] = shape
                report["source_saved_brep_measurements"][name] = {
                    "saved_brep_member": member,
                    "saved_brep_sha256": hashlib.sha256(data).hexdigest(),
                    "shape": native_shape_metrics(shape),
                }
        _checkpoint(report_path, report)
        document = App.openDocument(str(copied.resolve()), True)
        if len(set(App.listDocuments()) - previous) != 1:
            raise ValueError("unexpected extra document loaded; this is a single-Art1 probe")
        for name in FEATURES:
            obj = document.getObject(name)
            if obj is None:
                raise ValueError(f"pinned document is missing feature {name}")
            report["restored_document_measurements"][name] = object_info(obj)
        _checkpoint(report_path, report)
        if experiment.startswith("intersection"):
            document.getObject("Thickness").Intersection = True
        if experiment == "intersection_freeze_bolt_frame":
            sketch = document.getObject("Sketch004")
            saved = next(item for item in contract["members"] if item["name"] == "Sketch004")[
                "placement_mm_xyzw"
            ]
            sketch.MapMode = "Deactivated"
            sketch.Placement = App.Placement(App.Vector(*saved[:3]), App.Rotation(*saved[3:]))
        if "Pocket.Type" in EXPERIMENTS[experiment]:
            document.getObject("Pocket").Type = EXPERIMENTS[experiment]["Pocket.Type"]
        try:
            report["force_recompute_return"] = document.recompute(None, True)
        except Exception as error:
            report["errors"].append(
                {"stage": "force_recompute", "type": type(error).__name__, "message": str(error)}
            )
        for name in FEATURES:
            report["force_rebuild_attempt_measurements"][name] = object_info(
                document.getObject(name)
            )
        report["all_document_object_states"] = {
            obj.Name: {"type": obj.TypeId, "states": list(obj.State)} for obj in document.Objects
        }
        source_types = {
            obj.attrib["name"]: obj.attrib["type"] for obj in xml.findall("./Objects/Object")
        }
        report["source_document_object_count"] = len(source_types)
        report["object_name_type_contract_matches_source"] = {
            name: item["type"] for name, item in report["all_document_object_states"].items()
        } == source_types
        report["all_document_objects_report_up_to_date"] = all(
            item["states"] == ["Up-to-date"]
            for item in report["all_document_object_states"].values()
        )
        report["datum_matrix_comparisons"] = {}
        for member in contract["members"]:
            if member["type"] not in DIAGNOSTICS["DATUM_TYPES"]:
                continue
            saved_matrix = DIAGNOSTICS["_matrix_from_placement"](member["placement_mm_xyzw"])
            actual_matrix = list(
                document.getObject(member["name"]).getGlobalPlacement().toMatrix().A
            )
            report["datum_matrix_comparisons"][member["name"]] = {
                "saved_matrix": saved_matrix,
                "attempted_matrix": actual_matrix,
                "maximum_absolute_element_error": max(
                    abs(a - b) for a, b in zip(saved_matrix, actual_matrix, strict=True)
                ),
            }
        report["feature_drift_summary"] = feature_drift_summary(
            report["source_saved_brep_measurements"],
            report["force_rebuild_attempt_measurements"],
        )
        for stage, get_shape in (
            ("source_saved_brep", lambda name: saved_shapes[name]),
            ("force_rebuild_attempt", lambda name: document.getObject(name).Shape),
        ):
            probe_shapes = {name: get_shape(name) for name in ("Pad002", "Pocket", "Pocket001")}
            report.setdefault("pad002_face9", {})[stage] = face9_info(probe_shapes["Pad002"])
            report.setdefault("material_removal_mm3", {})[stage] = {
                "Pocket": probe_shapes["Pad002"].Volume - probe_shapes["Pocket"].Volume,
                "Pocket001": probe_shapes["Pocket"].Volume - probe_shapes["Pocket001"].Volume,
            }
            candidates = geometry_candidates(probe_shapes["Pocket"])
            report["semantic_supports"][stage] = {
                kind: {
                    "descriptor": bolt_support_descriptor(contract, kind=kind),
                    "match": match_semantic_support(
                        bolt_support_descriptor(contract, kind=kind), candidates
                    ),
                }
                for kind in ("circle", "cylinder")
            }

        def compare_native_shapes(saved_shape, attempted_shape) -> dict:
            comparison = {
                "saved": native_shape_metrics(saved_shape),
                "attempted": native_shape_metrics(attempted_shape),
                "source_minus_attempted_mm3": None,
                "attempted_minus_source_mm3": None,
                "maximum_surface_distance_mm": None,
                "equivalence_accepted": False,
            }
            try:
                comparison["source_minus_attempted_mm3"] = saved_shape.cut(attempted_shape).Volume
                comparison["attempted_minus_source_mm3"] = attempted_shape.cut(saved_shape).Volume
            except Exception as error:
                comparison["boolean_error"] = {"type": type(error).__name__, "message": str(error)}
            return comparison

        report["body_geometry_comparison"] = compare_native_shapes(
            saved_shapes["Body"], document.getObject("Body").Shape
        )
        try:
            saved_removed = saved_shapes["Pad002"].cut(saved_shapes["Pocket"])
            attempted_removed = document.getObject("Pad002").Shape.cut(
                document.getObject("Pocket").Shape
            )
            report["removed_bolt_solid_comparison"] = compare_native_shapes(
                saved_removed, attempted_removed
            )
        except Exception as error:
            report["removed_bolt_solid_comparison"] = {
                "error": {"type": type(error).__name__, "message": str(error)},
                "equivalence_accepted": False,
            }
        report["forced_cut_selected_object_states_clean"] = all(
            report["force_rebuild_attempt_measurements"][name]["states"] == ["Up-to-date"]
            for name in ("Sketch003", "Pad002", "Sketch004", "Pocket", "Sketch005", "Pocket001")
        )
        report["full_dependency_closure_checked"] = False
        if after_capture is not None:
            after_capture(App, document, contract, report, report_path)
        report["audit_status"] = "complete_probe_not_migration_acceptance"
    except Exception as error:
        report["audit_status"] = "failed_probe"
        report["errors"].append(
            {"stage": "probe", "type": type(error).__name__, "message": str(error)}
        )
    finally:
        for name in set(App.listDocuments()) - previous:
            App.closeDocument(name)
        report["source_sha256_after"] = _sha(source)
        report["copied_source_sha256_after"] = _sha(copied)
        report["source_and_copy_bytes_unchanged"] = (
            report["source_sha256_after"] == report["copied_source_sha256_after"] == SOURCE_SHA256
        )
        if not report["source_and_copy_bytes_unchanged"]:
            report["audit_status"] = "failed_probe"
            report["errors"].append(
                {"stage": "preservation", "message": "source/copy hash changed"}
            )
        _checkpoint(report_path, report)
    if report["audit_status"] != "complete_probe_not_migration_acceptance":
        raise ValueError("Art1 probe failed; retain the diagnostic report and inspect its errors")


def native_report_is_complete(report: dict, script_sha256: str) -> bool:
    """Process metadata requires identity and capture coverage, not merely exit 0."""
    expected_hashes = (
        "source_sha256_before",
        "copied_source_sha256_before",
        "source_sha256_after",
        "copied_source_sha256_after",
    )
    if (
        report.get("schema_version") != 1
        or report.get("evidence_class") != "native_single_document_drift_probe_attempt"
        or report.get("audit_status") != "complete_probe_not_migration_acceptance"
        or any(report.get(key) != SOURCE_SHA256 for key in expected_hashes)
        or report.get("capture_script_sha256") != script_sha256
        or report.get("native_document_saved") is not False
        or report.get("migration_accepted") is not False
        or report.get("source_and_copy_bytes_unchanged") is not True
        or not isinstance(report.get("freecad_version"), list)
        or not report["freecad_version"]
    ):
        return False
    return all(
        isinstance(report.get(key), dict) and set(FEATURES) <= set(report[key])
        for key in (
            "source_saved_brep_measurements",
            "restored_document_measurements",
            "force_rebuild_attempt_measurements",
        )
    )


def run_probe(
    freecad: Path,
    source: Path,
    run_directory: Path,
    *,
    experiment: str = "unchanged",
    timeout_s: float = 180,
    expected_executable_sha256: str | None = None,
    candidate_output: Path | None = None,
) -> dict:
    """Create a fresh source copy, preferences and bounded native subprocess."""
    if not freecad.is_file() or not source.is_file():
        raise ValueError("native executable and pinned Art1 source must exist")
    executable_sha256 = _sha(freecad)
    if expected_executable_sha256 is not None:
        DIAGNOSTICS["_digest"](expected_executable_sha256, "expected executable SHA-256")
        if executable_sha256 != expected_executable_sha256:
            raise ValueError("native executable differs from the caller's expected SHA-256")
    if _sha(source) != SOURCE_SHA256:
        raise ValueError("source does not match pinned Art1 SHA-256")
    if run_directory.exists():
        raise ValueError("run directory must be new; previous evidence is never overwritten")
    if source.resolve().is_relative_to(run_directory.resolve()):
        raise ValueError("source cannot be inside the new run directory")
    if experiment not in EXPERIMENTS:
        raise ValueError("unsupported experiment")
    if candidate_output is not None:
        allowed = Path(__file__).parents[2] / ".work" / "cad" / "candidates"
        if (
            not candidate_output.resolve().is_relative_to(allowed.resolve())
            or candidate_output.exists()
        ):
            raise ValueError(
                "candidate output must be a new file under this checkout's .work/cad/candidates"
            )
        if experiment != "intersection_pocket_through_all":
            raise ValueError("candidate study requires the explicit ThroughAll diagnostic")
    if not 0 < _finite(timeout_s, "timeout") <= 600:
        raise ValueError("timeout must be positive and at most 600 seconds")
    existing_parent = run_directory.resolve().parent
    while not existing_parent.exists():
        existing_parent = existing_parent.parent
    free_before = shutil.disk_usage(existing_parent).free
    if free_before < 50 * 1024**3 + 128 * 1024**2:
        raise ValueError(
            "native probing requires the 50 GiB free-space reserve plus scratch budget"
        )
    run_directory.mkdir(parents=True, exist_ok=False)
    copied, report = run_directory / "Art1Body.fcstd", run_directory / "probe.json"
    with copied.open("xb") as stream:
        stream.write(source.read_bytes())
    user_cfg, system_cfg = run_directory / "user.cfg", run_directory / "system.cfg"
    isolated_data = {
        "FREECAD_USER_HOME": run_directory / "user-home",
        "FREECAD_USER_DATA": run_directory / "user-data",
        "FREECAD_USER_TEMP": run_directory / "user-temp",
    }
    for directory in isolated_data.values():
        directory.mkdir(exist_ok=False)
    snapshot_root = run_directory / "capture-tool"
    snapshot_tools = snapshot_root / "tools"
    snapshot_evidence = snapshot_root / "hardware" / "cad"
    snapshot_tools.mkdir(parents=True, exist_ok=False)
    snapshot_evidence.mkdir(parents=True, exist_ok=False)
    snapshot_pairs = [
        (Path(__file__), snapshot_tools / Path(__file__).name),
        (
            Path(__file__).with_name("thor_art1_diagnostics.py"),
            snapshot_tools / "thor_art1_diagnostics.py",
        ),
        (
            Path(__file__).parents[1] / "hardware" / "cad" / "thor-art1-migration-evidence.json",
            snapshot_evidence / "thor-art1-migration-evidence.json",
        ),
    ]
    entry_name = Path(__file__).name
    if candidate_output is not None:
        entry_name = "prepare_thor_art1_candidate.py"
        snapshot_pairs.append((Path(__file__).with_name(entry_name), snapshot_tools / entry_name))
    for original, snapshot in snapshot_pairs:
        with snapshot.open("xb") as stream:
            stream.write(original.read_bytes())
    snapshot_hashes = {str(snapshot.resolve()): _sha(snapshot) for _, snapshot in snapshot_pairs}
    capture_script = snapshot_tools / entry_name
    validate_probe_paths(source, copied, report, user_cfg, system_cfg)
    command = [
        str(freecad.resolve()),
        "-u",
        str(user_cfg.resolve()),
        "-s",
        str(system_cfg.resolve()),
        str(capture_script.resolve()),
    ]
    env = os.environ.copy()
    env.update(
        {
            PROBE_FLAG: "1",
            "RAFTEL_THOR_ART1_SOURCE": str(source.resolve()),
            "RAFTEL_THOR_ART1_COPY": str(copied.resolve()),
            "RAFTEL_THOR_ART1_REPORT": str(report.resolve()),
            "RAFTEL_THOR_ART1_USER_CFG": str(user_cfg.resolve()),
            "RAFTEL_THOR_ART1_SYSTEM_CFG": str(system_cfg.resolve()),
            "RAFTEL_THOR_ART1_EXPERIMENT": experiment,
            "RAFTEL_THOR_ART1_EXECUTABLE_SHA256": executable_sha256,
            "PYTHONNOUSERSITE": "1",
        }
    )
    env.update({key: str(path.resolve()) for key, path in isolated_data.items()})
    if candidate_output is not None:
        env.pop(PROBE_FLAG, None)
        env["RAFTEL_PREPARE_THOR_ART1_CANDIDATE"] = "1"
        env["RAFTEL_THOR_ART1_CANDIDATE_OUTPUT"] = str(candidate_output.resolve())
    metadata = {
        "schema_version": 1,
        "evidence_class": "native_probe_process_metadata_only",
        "experiment": experiment,
        "timeout_s": timeout_s,
        "command": command,
        "source_sha256_before": SOURCE_SHA256,
        "free_bytes_before": free_before,
        "isolated_user_directories": {
            key: str(path.resolve()) for key, path in isolated_data.items()
        },
        "capture_snapshot_sha256_before": snapshot_hashes,
        "native_executable_sha256": executable_sha256,
        "expected_native_executable_sha256": expected_executable_sha256,
        "executable_matches_caller_pin": None if expected_executable_sha256 is None else True,
        "full_runtime_and_addon_bundle_verified": False,
        "outcome": "starting",
        "native_probe_completed": False,
        "migration_accepted": False,
    }
    stdout, stderr = "", ""
    try:
        completed = subprocess.run(
            command,
            input="",
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_s,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        metadata.update(outcome="process_completed", process_returncode=completed.returncode)
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as error:
        metadata.update(outcome="timed_out", process_returncode=None)
        stdout, stderr = error.stdout or "", error.stderr or ""
    except OSError as error:
        metadata.update(outcome="launch_failed", process_returncode=None, launch_error=str(error))
    for name, value in (("stdout.log", stdout), ("stderr.log", stderr)):
        text = value.decode(errors="replace") if isinstance(value, bytes) else value
        with (run_directory / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    metadata["source_sha256_after"] = _sha(source)
    metadata["copy_sha256_after"] = _sha(copied)
    metadata["capture_snapshot_sha256_after"] = {
        str(snapshot.resolve()): _sha(snapshot) for _, snapshot in snapshot_pairs
    }
    metadata["capture_snapshot_bytes_unchanged"] = (
        metadata["capture_snapshot_sha256_after"] == snapshot_hashes
    )
    metadata["source_and_copy_bytes_unchanged"] = (
        metadata["source_sha256_after"] == metadata["copy_sha256_after"] == SOURCE_SHA256
    )
    if report.exists():
        try:
            native = DIAGNOSTICS["_load"](report)
            metadata["native_audit_status"] = native.get("audit_status")
            metadata["native_probe_completed"] = (
                metadata.get("process_returncode") == 0
                and native_report_is_complete(native, _sha(capture_script))
                and metadata["source_and_copy_bytes_unchanged"]
                and metadata["capture_snapshot_bytes_unchanged"]
            )
        except (OSError, ValueError) as error:
            metadata["report_error"] = str(error)
    with (run_directory / "runner.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe-source-contract", type=Path, help="Offline descriptors only")
    parser.add_argument("--output", type=Path, help="New offline descriptor JSON path")
    parser.add_argument("--freecad", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--run-directory", type=Path)
    parser.add_argument("--experiment", choices=tuple(EXPERIMENTS), default="unchanged")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument(
        "--expected-executable-sha256", help="Optional independently obtained binary pin"
    )
    args = parser.parse_args(argv)
    try:
        if args.describe_source_contract:
            if args.freecad or args.source or args.run_directory:
                raise ValueError("offline descriptor mode cannot be mixed with native run paths")
            contract = DIAGNOSTICS["_load"](args.describe_source_contract)
            result = {
                "schema_version": 1,
                "evidence_class": "source_geometry_descriptors_only",
                "source_sha256": SOURCE_SHA256,
                "input_source_fingerprint_sha256": _sha(args.describe_source_contract),
                "coordinate_frame": "native_Art1_Body_identity_mm",
                "supports": {
                    f"{'head' if head else 'body'}_{kind}": bolt_support_descriptor(
                        contract, head=head, kind=kind
                    )
                    for head in (False, True)
                    for kind in ("circle", "cylinder")
                },
                "native_capture_executed": False,
                "support_remapped": False,
                "migration_accepted": False,
            }
            data = json.dumps(result, indent=2, allow_nan=False) + "\n"
            if args.output:
                with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(data)
            else:
                print(data, end="")
            return 0
        if args.output:
            raise ValueError(
                "--output is only for offline descriptors; native reports use the run directory"
            )
        if not args.freecad or not args.source or not args.run_directory:
            raise ValueError("native runs require --freecad, --source and --run-directory")
        result = run_probe(
            args.freecad,
            args.source,
            args.run_directory,
            experiment=args.experiment,
            timeout_s=args.timeout,
            expected_executable_sha256=args.expected_executable_sha256,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["native_probe_completed"] else 1


if os.environ.get(PROBE_FLAG) == "1":
    native_capture()
elif __name__ == "__main__":
    raise SystemExit(main())
