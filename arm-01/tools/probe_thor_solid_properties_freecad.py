"""Worker-only, isolated FreeCAD capture of selected hash-pinned cached BReps.

This opens no CAD documents and rebuilds no feature history. Native fixtures
must establish centroidal MatrixOfInertia semantics before source capture.
The coordinator owns the single native-process queue and isolated launcher.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
PROBE_FLAG = "RAFTEL_RUN_THOR_SOLID_PROPERTIES"
FRAME = "saved_BRep_storage_frame_as_read_mm; no extra XML/object/link placement applied"
MAX_SELECTIONS = 8
MAX_BREP_BYTES = 128 * 1024**2
MAX_TRIANGLES = 1_000_000
BOUNDS = ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")


def _finite(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected finite real numeric input")
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("expected finite real numeric input") from error
    if not math.isfinite(result):
        raise ValueError("expected finite real numeric input")
    return result


def _vector(value, length=3) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f"expected {length} finite coordinates")
    return [_finite(item) for item in value]


def _matrix(value) -> list[list[float]]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("expected finite 3x3 geometric inertia tensor")
    result = [_vector(row) for row in value]
    scale = max(abs(item) for row in result for item in row)
    if any(abs(result[i][j] - result[j][i]) > scale * 1e-10 for i in range(3) for j in range(3)):
        raise ValueError("geometric inertia must be symmetric")
    if any(result[i][i] < -scale * 1e-10 for i in range(3)):
        raise ValueError("geometric inertia diagonal must be nonnegative")

    def positive_semidefinite(matrix):
        magnitude = max(abs(item) for row in matrix for item in row)
        if magnitude == 0:
            return True
        # Standalone worker mirrors the core's bounded symmetric eigenvalue
        # check; no editable package import is required by the native snapshot.
        m = [
            [(matrix[i][j] / 2 + matrix[j][i] / 2) / magnitude for j in range(3)] for i in range(3)
        ]
        for _ in range(24):
            p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda pair: abs(m[pair[0]][pair[1]]))
            off = m[p][q]
            if abs(off) <= 1e-15:
                break
            tau = (m[q][q] - m[p][p]) / (2 * off)
            tangent = math.copysign(1.0, tau) / (abs(tau) + math.hypot(1.0, tau))
            cosine = 1 / math.hypot(1.0, tangent)
            sine = tangent * cosine
            m[p][p] -= tangent * off
            m[q][q] += tangent * off
            m[p][q] = m[q][p] = 0.0
            for r in range(3):
                if r not in (p, q):
                    old_p, old_q = m[r][p], m[r][q]
                    m[r][p] = m[p][r] = cosine * old_p - sine * old_q
                    m[r][q] = m[q][r] = sine * old_p + cosine * old_q
        return (
            max(abs(m[i][j]) for i, j in ((0, 1), (0, 2), (1, 2))) <= 1e-15
            and min(m[i][i] - math.fsum(abs(m[i][j]) for j in range(3) if j != i) for i in range(3))
            >= -1e-12
        )

    half_trace = math.fsum(result[i][i] / 2 for i in range(3))
    covariance = [
        [(half_trace if i == j else 0) - result[i][j] for j in range(3)] for i in range(3)
    ]
    if not positive_semidefinite(result) or not positive_semidefinite(covariance):
        raise ValueError(
            f"nonphysical geometric inertia (PSD/triangle violation); raw matrix={result}"
        )
    return result


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} requires explicit nonempty text")
    return value


def _digest(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("expected lowercase SHA-256 hex")
    return value


def _relative(value):
    raw = _text(value, "relative path")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or "\\" in raw or ":" in raw or str(path) != raw:
        raise ValueError("source and archive paths must be normalized relative POSIX paths")
    return raw


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) <= set(required) | set(
        optional
    ):
        raise ValueError(f"expected keys {sorted(required)} with optional {sorted(optional)}")
    return value


def validate_request(request: dict) -> dict:
    json.dumps(request, allow_nan=False)
    _keys(request, {"schema_version", "source_revision", "evidence_class", "selections"})
    if type(request["schema_version"]) is not int or request["schema_version"] != 1:
        raise ValueError("unsupported solid-properties request schema")
    if request["source_revision"] != SOURCE_REVISION:
        raise ValueError("request must declare the pinned Thor source revision")
    if request["evidence_class"] != "selected_saved_BRep_properties_request":
        raise ValueError("request must remain selected saved-BRep evidence")
    selections = request["selections"]
    if not isinstance(selections, list) or not 1 <= len(selections) <= MAX_SELECTIONS:
        raise ValueError("request requires 1..8 bounded selected BReps")
    ids, objects, outputs = set(), set(), set()
    for row in selections:
        _keys(
            row,
            {
                "selection_id",
                "source_file",
                "source_sha256",
                "object_name",
                "object_type",
                "brep_entry",
                "brep_sha256",
                "xml_placement",
                "selection_evidence",
                "uniform_density",
                "tessellation",
            },
            {"reference_capture", "upstream_stl_reference"},
        )
        identifier = _text(row["selection_id"], "selection ID")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", identifier) is None or identifier in ids:
            raise ValueError("selection IDs must be unique safe identifiers")
        ids.add(identifier)
        source = _relative(row["source_file"])
        if PurePosixPath(source).suffix.lower() != ".fcstd":
            raise ValueError("source must be a native FCStd archive")
        _relative(row["brep_entry"])
        _digest(row["source_sha256"])
        _digest(row["brep_sha256"])
        name = _text(row["object_name"], "source object name")
        _text(row["object_type"], "source object type")
        if (source, name) in objects:
            raise ValueError("source object selections must be unique")
        objects.add((source, name))
        _text(row["selection_evidence"], "selection evidence")
        placement = row["xml_placement"]
        if placement is not None:
            _keys(placement, {"position_mm", "quaternion_xyzw"})
            _vector(placement["position_mm"])
            quaternion = _vector(placement["quaternion_xyzw"], 4)
            if not math.isclose(math.hypot(*quaternion), 1, abs_tol=1e-8, rel_tol=0):
                raise ValueError("XML quaternion must be unit length")
        density = row["uniform_density"]
        if density is not None:
            _keys(density, {"density_kg_m3", "effective_uniform_fraction", "evidence"})
            if (
                _finite(density["density_kg_m3"]) <= 0
                or not 0 < _finite(density["effective_uniform_fraction"]) <= 1
            ):
                raise ValueError("uniform density requires positive density/fraction in (0,1]")
            _text(density["evidence"], "uniform density evidence")
        mesh = row["tessellation"]
        if mesh is not None:
            _keys(mesh, {"linear_deflection_mm", "angular_deflection_rad", "relative", "filename"})
            if (
                not 0 < _finite(mesh["linear_deflection_mm"]) <= 5
                or not 0 < _finite(mesh["angular_deflection_rad"]) <= math.pi / 2
            ):
                raise ValueError("draft tessellation requires bounded positive deflections")
            if mesh["relative"] is not False:
                raise ValueError("this probe requires absolute linear deflection in mm")
            filename = _relative(mesh["filename"])
            if (
                PurePosixPath(filename).name != filename
                or not filename.endswith(".stl")
                or filename in outputs
                or PurePosixPath(filename).stem.upper()
                in {
                    "CON",
                    "PRN",
                    "AUX",
                    "NUL",
                    *(f"COM{i}" for i in range(1, 10)),
                    *(f"LPT{i}" for i in range(1, 10)),
                }
            ):
                raise ValueError("draft STL filenames must be new unique basenames")
            outputs.add(filename)
    return request


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_selected_brep(source_root: Path, selection: dict) -> tuple[bytes, dict]:
    """Verify the archive, XML object/type/entry and raw BRep before native import."""
    root = source_root.resolve(strict=True)
    source = (root / selection["source_file"]).resolve(strict=True)
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError("source copy escapes the isolated source root")
    if not 1 <= source.stat().st_size <= 512 * 1024**2:
        raise ValueError("source archive outside the bounded selected-probe size")
    if _sha(source) != selection["source_sha256"]:
        raise ValueError("source archive differs from its pinned SHA-256")
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate native archive entries are ambiguous")
        if archive.getinfo("Document.xml").file_size > MAX_BREP_BYTES:
            raise ValueError("native XML outside the selected-probe size bound")
        xml = ET.fromstring(archive.read("Document.xml"))
        matches = [
            item
            for item in xml.findall("./ObjectData/Object")
            if item.get("name") == selection["object_name"]
        ]
        types = [
            item.get("type")
            for item in xml.findall("./Objects/Object")
            if item.get("name") == selection["object_name"]
        ]
        if len(matches) != 1 or types != [selection["object_type"]]:
            raise ValueError("native selected object/type differs or is ambiguous")
        obj = matches[0]
        shape = obj.find('./Properties/Property[@name="Shape"]/Part')
        if shape is None or shape.get("file") != selection["brep_entry"]:
            raise ValueError("native object Shape entry differs from the pinned selection")
        if not 1 <= archive.getinfo(selection["brep_entry"]).file_size <= MAX_BREP_BYTES:
            raise ValueError("selected cached BRep outside the size bound")
        raw = archive.read(selection["brep_entry"])
        if hashlib.sha256(raw).hexdigest() != selection["brep_sha256"]:
            raise ValueError("selected cached BRep differs from pinned SHA-256")
        node = obj.find('./Properties/Property[@name="Placement"]/PropertyPlacement')
        placement = (
            None
            if node is None
            else {
                "position_mm": [float(node.get(key)) for key in ("Px", "Py", "Pz")],
                "quaternion_xyzw": [float(node.get(key)) for key in ("Q0", "Q1", "Q2", "Q3")],
            }
        )
        if placement != selection["xml_placement"]:
            raise ValueError("saved XML placement differs from the selection descriptor")
    return raw, {
        "source_file": selection["source_file"],
        "source_sha256": selection["source_sha256"],
        "object_name": selection["object_name"],
        "object_type": selection["object_type"],
        "brep_entry": selection["brep_entry"],
        "brep_sha256": selection["brep_sha256"],
        "xml_placement_not_applied": placement,
    }


def aggregate_geometric_solids(records: list[dict]) -> dict:
    """Aggregate solids ONLY within their one already-common BRep storage frame."""
    if not isinstance(records, list) or not records:
        raise ValueError("at least one same-frame positive solid is required")
    volumes = [_finite(row["volume_mm3"]) for row in records]
    if any(volume <= 0 for volume in volumes):
        raise ValueError("geometric volume must be positive")
    centers = [_vector(row["com_mm"]) for row in records]
    tensors = [_matrix(row["centroidal_geometric_inertia_mm5"]) for row in records]
    volume = _finite(math.fsum(volumes))
    com = [
        _finite(math.fsum(v * c[i] for v, c in zip(volumes, centers, strict=True)) / volume)
        for i in range(3)
    ]
    terms = []
    for v, c, tensor in zip(volumes, centers, tensors, strict=True):
        r = [c[i] - com[i] for i in range(3)]
        r2 = math.fsum(x * x for x in r)
        terms.append(
            [
                [tensor[i][j] + v * ((r2 if i == j else 0) - r[i] * r[j]) for j in range(3)]
                for i in range(3)
            ]
        )
    result = _matrix(
        [[math.fsum(term[i][j] for term in terms) for j in range(3)] for i in range(3)]
    )
    return {
        "volume_mm3": volume,
        "volume_m3": volume * 1e-9,
        "com_mm": com,
        "com_m": [x * 1e-3 for x in com],
        "centroidal_geometric_inertia_mm5": result,
        "centroidal_geometric_inertia_m5": [[x * 1e-15 for x in row] for row in result],
        "solid_count": len(records),
        "aggregation_scope": "solids within this one BRep storage frame only",
        "inter_solid_overlap_check_performed": False,
        "member_sum_is_union_volume_proven": len(records) == 1,
    }


def uniform_density_properties(geometric: dict, density: dict | None) -> dict | None:
    if density is None:
        return None
    rho, fraction = (
        _finite(density["density_kg_m3"]),
        _finite(density["effective_uniform_fraction"]),
    )
    if rho <= 0 or not 0 < fraction <= 1:
        raise ValueError("uniform density/fraction must be positive and bounded")
    _text(density["evidence"], "density evidence")
    return {
        "evidence_class": "conditional_uniform_density_not_measured_or_nonuniform_print_inertia",
        **density,
        "mass_kg": _finite(geometric["volume_mm3"] * 1e-9 * rho * fraction),
        "com_m": geometric["com_m"],
        "centroidal_inertia_kg_m2": [
            [_finite(x * 1e-15 * rho * fraction) for x in row]
            for row in geometric["centroidal_geometric_inertia_mm5"]
        ],
        "effective_uniform_fraction_is_slicer_infill": False,
    }


def _native_metrics(shape) -> dict:
    records = []
    for index, solid in enumerate(shape.Solids):
        matrix = solid.MatrixOfInertia
        records.append(
            {
                "solid_index": index,
                "volume_mm3": _finite(solid.Volume),
                "com_mm": _vector(list(solid.CenterOfMass)),
                "centroidal_geometric_inertia_mm5": _matrix(
                    [[getattr(matrix, f"A{i}{j}") for j in range(1, 4)] for i in range(1, 4)]
                ),
                "native_valid": bool(solid.isValid()),
                "native_closed_flag": bool(solid.isClosed()),
            }
        )
    if not shape.isValid() or any(not row["native_valid"] for row in records):
        raise ValueError("selected cached shape/solid fails native validity")
    if any(not row["native_closed_flag"] for row in records):
        raise ValueError(f"selected cached Solid is not closed; raw solid metrics={records}")
    return {
        "aggregate": aggregate_geometric_solids(records),
        "solids": records,
        "native_shape_valid": True,
        "native_bounds_mm": {key: _finite(getattr(shape.BoundBox, key)) for key in BOUNDS},
        "raw_shape_placement_matrix_not_reapplied": [
            _finite(x) for x in shape.Placement.toMatrix().A
        ],
        "full_self_intersection_analysis_performed": False,
    }


def _rotation(axis, angle_deg):
    unit = [x / math.hypot(*axis) for x in axis]
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    x, y, z = unit
    skew = [[0, -z, y], [z, 0, -x], [-y, x, 0]]
    return [
        [c * (i == j) + (1 - c) * unit[i] * unit[j] + s * skew[i][j] for j in range(3)]
        for i in range(3)
    ]


def _transformed_expected(volume, com, tensor, rotation, translation):
    return {
        "volume_mm3": volume,
        "com_mm": [
            math.fsum(rotation[i][j] * com[j] for j in range(3)) + translation[i] for i in range(3)
        ],
        "centroidal_geometric_inertia_mm5": [
            [
                math.fsum(
                    rotation[i][a] * tensor[a][b] * rotation[j][b]
                    for a in range(3)
                    for b in range(3)
                )
                for j in range(3)
            ]
            for i in range(3)
        ],
    }


def fixture_expectations() -> dict:
    box = {
        "volume_mm3": 24.0,
        "com_mm": [1.0, 1.5, 2.0],
        "centroidal_geometric_inertia_mm5": [[50, 0, 0], [0, 40, 0], [0, 0, 26]],
    }
    cylinder_volume = 20 * math.pi
    cylinder = {
        "volume_mm3": cylinder_volume,
        "com_mm": [0, 0, 2.5],
        "centroidal_geometric_inertia_mm5": [
            [cylinder_volume * 37 / 12, 0, 0],
            [0, cylinder_volume * 37 / 12, 0],
            [0, 0, cylinder_volume * 2],
        ],
    }
    compound = {
        "volume_mm3": 30.0,
        "com_mm": [2.3, 0.6, 2.3],
        "centroidal_geometric_inertia_mm5": [
            [164.5, 140.4, -46.8],
            [140.4, 258.6, 32.4],
            [-46.8, 32.4, 328.5],
        ],
    }
    identity = [[float(i == j) for j in range(3)] for i in range(3)]
    result = {"box": box, "cylinder": cylinder, "compound": compound}
    for name, base, axis, angle, translation in (
        ("box_translated", box, (0, 0, 1), 0, (10, -20, 30)),
        ("box_rotated_translated", box, (1, 2, 3), 37, (10, -20, 30)),
        ("cylinder_rotated_translated", cylinder, (2, -1, 3), 41, (-7, 9, 12)),
        ("compound_rotated_translated", compound, (2, -1, 3), 41, (11, 17, -5)),
    ):
        result[name] = _transformed_expected(
            base["volume_mm3"],
            base["com_mm"],
            base["centroidal_geometric_inertia_mm5"],
            _rotation(axis, angle),
            translation,
        )
    for name, scale in (("box_scale_0p01", 0.01), ("box_scale_10", 10)):
        result[name] = _transformed_expected(
            box["volume_mm3"] * scale**3,
            [x * scale for x in box["com_mm"]],
            [[x * scale**5 for x in row] for row in box["centroidal_geometric_inertia_mm5"]],
            identity,
            (0, 0, 0),
        )
    return result


def verify_fixture_records(records: dict) -> dict:
    expected = fixture_expectations()
    if set(records) != set(expected):
        raise ValueError("native inertia fixtures missing, extra or duplicated cases")
    worst_relative_tensor = worst_relative_volume = worst_com = 0.0
    for name, target in expected.items():
        actual = records[name]["aggregate"]
        volume_error = (
            abs(_finite(actual["volume_mm3"]) - target["volume_mm3"]) / target["volume_mm3"]
        )
        com_error = max(
            abs(a - b) for a, b in zip(_vector(actual["com_mm"]), target["com_mm"], strict=True)
        )
        try:
            tensor = _matrix(actual["centroidal_geometric_inertia_mm5"])
        except ValueError as error:
            raise ValueError(f"native fixture {name}: {error}") from error
        scale = max(abs(x) for row in target["centroidal_geometric_inertia_mm5"] for x in row)
        tensor_error = (
            max(
                abs(tensor[i][j] - target["centroidal_geometric_inertia_mm5"][i][j])
                for i in range(3)
                for j in range(3)
            )
            / scale
        )
        if volume_error > 1e-9 or com_error > 1e-8 or tensor_error > 1e-8:
            raise ValueError(f"native centroidal/unit/frame fixture differs: {name}")
        worst_relative_volume = max(worst_relative_volume, volume_error)
        worst_relative_tensor = max(worst_relative_tensor, tensor_error)
        worst_com = max(worst_com, com_error)
    return {
        "verified": True,
        "case_count": len(expected),
        "maximum_relative_volume_error": worst_relative_volume,
        "maximum_com_error_mm": worst_com,
        "maximum_relative_tensor_error": worst_relative_tensor,
        "contract": (
            "Solid.MatrixOfInertia is centroidal geometric mm^5 in parallel storage-frame axes; "
            "aggregate solids in their one common BRep frame"
        ),
    }


def run_native_fixtures(App, Part) -> dict:
    box = Part.makeBox(2, 3, 4)
    cylinder = Part.makeCylinder(2, 5)
    small = Part.makeBox(1, 2, 3)
    small.translate(App.Vector(7, -4, 2))
    compound = Part.makeCompound([box, small])
    shapes = {
        "box": box,
        "cylinder": cylinder,
        "compound": compound,
        "box_scale_0p01": Part.makeBox(0.02, 0.03, 0.04),
        "box_scale_10": Part.makeBox(20, 30, 40),
    }
    for name, source, axis, angle, translation in (
        ("box_translated", box, (0, 0, 1), 0, (10, -20, 30)),
        ("box_rotated_translated", box, (1, 2, 3), 37, (10, -20, 30)),
        ("cylinder_rotated_translated", cylinder, (2, -1, 3), 41, (-7, 9, 12)),
        ("compound_rotated_translated", compound, (2, -1, 3), 41, (11, 17, -5)),
    ):
        shape = source.copy()
        shape.Placement = App.Placement(
            App.Vector(*translation), App.Rotation(App.Vector(*axis), angle)
        )
        shapes[name] = shape
    records = {name: _native_metrics(shape) for name, shape in shapes.items()}
    try:
        summary = verify_fixture_records(records)
    except ValueError as error:
        summary = {"verified": False, "error": str(error)}
    return {
        "summary": summary,
        "records": records,
        "independent_expectations": fixture_expectations(),
    }


def binary_stl(vertices, facets) -> bytes:
    if not 1 <= len(facets) <= MAX_TRIANGLES:
        raise ValueError("draft tessellation outside bounded triangle count")
    points = [_vector(list(point)) for point in vertices]
    header = b"Thor/AngelLM CC-BY-SA-4.0; cached BRep draft; units mm; NOT PRINT QUALIFIED".ljust(
        80, b"\0"
    )
    result = bytearray(header + struct.pack("<I", len(facets)))
    for face in facets:
        if len(face) != 3 or any(
            type(index) is not int or not 0 <= index < len(points) for index in face
        ):
            raise ValueError("invalid native tessellation triangle index")
        a, b, c = [points[index] for index in face]
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        norm = math.hypot(*normal)
        normal = [x / norm for x in normal] if norm else [0.0] * 3
        result.extend(struct.pack("<12fH", *normal, *a, *b, *c, 0))
    return bytes(result)


def _export_draft_mesh(shape, settings: dict, directory: Path) -> dict:
    import MeshPart

    mesh = MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=settings["linear_deflection_mm"],
        AngularDeflection=settings["angular_deflection_rad"],
        Relative=False,
    )
    vertices, facets = mesh.Topology
    raw = binary_stl(vertices, facets)
    path = directory / settings["filename"]
    with path.open("xb") as stream:
        stream.write(raw)
    return {
        "filename": settings["filename"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "units": "mm",
        "frame": FRAME,
        "encoding": "binary_STL",
        "vertex_count_before_STL_unindexing": len(vertices),
        "triangle_count": len(facets),
        "tessellation": settings,
        "mesh_manifoldness_or_winding_independently_verified": False,
        "mesh_self_intersections_checked": False,
        "print_or_fit_qualification": False,
    }


def _isolated_paths() -> tuple[Path, Path, Path, Path, dict]:
    if os.environ.get(PROBE_FLAG) != "1":
        raise ValueError("native solid-properties worker requires explicit environment opt-in")
    root = Path(os.environ["RAFTEL_SOLID_RUN_DIR"]).resolve(strict=True)
    request = Path(os.environ["RAFTEL_SOLID_REQUEST"]).resolve(strict=True)
    source = Path(os.environ["RAFTEL_SOLID_SOURCE_ROOT"]).resolve(strict=True)
    output = Path(os.environ["RAFTEL_SOLID_REPORT"]).resolve()
    if not root.is_dir() or any(
        not path.is_relative_to(root) for path in (request, source, output)
    ):
        raise ValueError("request, copied sources and new report must stay inside isolated run")
    if output.suffix.lower() != ".json" or output.exists() or output.is_relative_to(source):
        raise ValueError("native report must be a new .json outside the copied source tree")
    paths = {
        "UserParameter": Path(os.environ["RAFTEL_SOLID_USER_CFG"]).resolve(),
        "SystemParameter": Path(os.environ["RAFTEL_SOLID_SYSTEM_CFG"]).resolve(),
        "UserHomePath": Path(os.environ["FREECAD_USER_HOME"]).resolve(strict=True),
        "UserAppData": Path(os.environ["FREECAD_USER_DATA"]).resolve(strict=True),
        "AppTempPath": Path(os.environ["FREECAD_USER_TEMP"]).resolve(strict=True),
    }
    if any(not path.is_relative_to(root) for path in paths.values()) or any(
        not paths[key].is_dir() for key in ("UserHomePath", "UserAppData", "AppTempPath")
    ):
        raise ValueError("native preferences/home/data/temp must be isolated inside run")
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise ValueError("native worker requires PYTHONNOUSERSITE=1")
    if shutil.disk_usage(root).free < 50 * 1024**3 + 128 * 1024**2:
        raise ValueError("native probe requires 50 GiB reserve plus scratch budget")
    return root, request, source, output, paths


def native_capture() -> dict:
    root, request_path, source_root, output, paths = _isolated_paths()
    request = validate_request(
        json.loads(request_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    )
    verified = [(row, *read_selected_brep(source_root, row)) for row in request["selections"]]
    report = {
        "schema_version": 1,
        "evidence_class": (
            "native_selected_cached_BRep_geometric_properties_not_history_or_physical_validation"
        ),
        "audit_status": "starting",
        "source_revision": SOURCE_REVISION,
        "declared_revision_not_independently_authenticated_by_worker": True,
        "source_authentication_boundary": (
            "Worker checks requested archive/BRep/XML pins; launcher and independent audit "
            "must authenticate those hashes against the declared upstream revision."
        ),
        "request_sha256": _sha(request_path),
        "request": request,
        "capture_script_sha256": _sha(Path(__file__)),
        "runner_declared_executable_sha256": os.environ.get("RAFTEL_SOLID_EXECUTABLE_SHA256"),
        "full_runtime_bundle_verified_by_worker": False,
        "coordinate_frame": FRAME,
        "cross_asset_aggregation_performed": False,
        "upstream_attribution": {
            "project": "Thor / AngelLM and contributors",
            "repository": "https://github.com/AngelLM/Thor",
            "revision": SOURCE_REVISION,
            "license": "CC-BY-SA-4.0",
            "license_url": f"https://github.com/AngelLM/Thor/blob/{SOURCE_REVISION}/LICENSE",
        },
        "document_opened_or_recomputed": False,
        "native_document_saved": False,
        "source_copy_sha256_before": {
            row["source_file"]: row["source_sha256"] for row in request["selections"]
        },
        "selections": [],
        "errors": [],
    }
    try:
        import FreeCAD as App
        import Part

        report["open_document_count_before"] = len(App.listDocuments())
        if report["open_document_count_before"]:
            raise ValueError("native worker requires an isolated console with zero open documents")
        actual = {key: App.ConfigGet(key) for key in paths}
        report["actual_runtime_paths"] = actual
        report["expected_isolated_paths"] = {key: str(path) for key, path in paths.items()}
        if any(Path(actual[key]).resolve() != path for key, path in paths.items()):
            raise ValueError(
                "native runtime preference/home/data/temp paths differ from isolated request"
            )
        report.update(
            freecad_version=list(App.Version()),
            python_version=sys.version,
            opencascade_version=getattr(Part, "OCC_VERSION", None),
            runtime_isolated_paths_verified=True,
        )
        report["primitive_fixtures"] = run_native_fixtures(App, Part)
        if report["primitive_fixtures"]["summary"]["verified"] is not True:
            raise ValueError("native primitive fixtures did not establish the required contract")
        breps, meshes = root / "saved-breps", root / "draft-stl"
        breps.mkdir(exist_ok=False)
        if any(row["tessellation"] is not None for row in request["selections"]):
            meshes.mkdir(exist_ok=False)
        for row, raw, binding in verified:
            path = breps / (row["selection_id"] + ".brep")
            with path.open("xb") as stream:
                stream.write(raw)
            shape = Part.Shape()
            shape.read(str(path))
            metrics = _native_metrics(shape)
            report["selections"].append(
                {
                    "selection_id": row["selection_id"],
                    "coordinate_frame_id": (
                        f"saved-brep:{row['source_file']}::{row['object_name']}@{row['brep_sha256']}"
                    ),
                    "source_binding": binding,
                    "coordinate_frame": FRAME,
                    "cached_shape_properties": metrics,
                    "uniform_density_scenario": uniform_density_properties(
                        metrics["aggregate"], row["uniform_density"]
                    ),
                    "physical_or_purchased_internal_or_nonuniform_print_inertia_kg_m2": None,
                    "draft_stl": None
                    if row["tessellation"] is None
                    else _export_draft_mesh(shape, row["tessellation"], meshes),
                    "upstream_STL_is_not_this_native_export": True,
                }
            )
        report["open_document_count_after"] = len(App.listDocuments())
        if report["open_document_count_after"]:
            raise ValueError("native worker unexpectedly acquired CAD documents")
        report["audit_status"] = "complete_selected_cached_geometry_only"
    except Exception as error:
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
        report["audit_status"] = "failed_native_probe"
    report["source_copy_sha256_after"] = {
        row["source_file"]: _sha(source_root / row["source_file"]) for row in request["selections"]
    }
    report["input_copy_bytes_unchanged"] = (
        report["source_copy_sha256_after"] == report["source_copy_sha256_before"]
    )
    if not report["input_copy_bytes_unchanged"]:
        report["audit_status"] = "failed_source_copy_changed"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("RAFTEL_SOLID_PROPERTIES_REPORT", report["audit_status"], str(output))
    return report


if __name__ == "__main__" or os.environ.get(PROBE_FLAG) == "1":
    native_capture()
