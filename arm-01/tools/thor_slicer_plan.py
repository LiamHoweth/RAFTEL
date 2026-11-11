"""Audit pinned upstream STL meshes and prepare an unreleased draft plate queue.

STL does not encode units. Coordinates here are explicitly interpreted as mm
for comparison with preserved native captures. Topology checks do not establish
native-solid fidelity, self-intersection freedom, printability or part strength.
No slicer/printer/cloud interface or machine output is implemented here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from raftel_arm01.engineering.fabrication_records import _instances
from raftel_arm01.engineering.scenarios import _strict_json, canonical_sha256, finite_number

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "286b081fe6f056d87c379b884781ef77ff6a0159"
SOURCE_REPOSITORY = "https://github.com/AngelLM/Thor"
PINNED_TREE_CANONICAL_SHA256 = "a58151d5204ff5f00fbbc907b11f285cf00774507ee0708be82feea3571848f4"
MAX_MESH_BYTES = 100 * 1024 * 1024
MAX_TRIANGLES = 1_000_000
Vector3 = tuple[float, float, float]
Triangle = tuple[Vector3, Vector3, Vector3]


def _vector(values: Sequence[float]) -> Vector3:
    if len(values) != 3:
        raise ValueError("mesh vector needs three finite coordinates")
    return tuple(finite_number(value) for value in values)


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return _vector(
        (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    )


def _minus(a: Vector3, b: Vector3) -> Vector3:
    return _vector(tuple(x - y for x, y in zip(a, b, strict=True)))


def parse_stl(contents: bytes) -> tuple[str, tuple[tuple[Vector3, Triangle], ...], int]:
    """Read exact-size binary STL (even a 'solid' header) or strict ASCII STL.

    Bounds reject giant/empty/truncated inputs before geometry evaluation.
    Binary attribute words are retained as an opaque warning count; some
    exporters encode color in them, so they are not interpreted as geometry.
    """
    if not isinstance(contents, bytes) or not 1 <= len(contents) <= MAX_MESH_BYTES:
        raise ValueError("STL byte size outside the allowed bound")
    if len(contents) >= 84:
        count = struct.unpack_from("<I", contents, 80)[0]
        if len(contents) == 84 + 50 * count:
            if not 1 <= count <= MAX_TRIANGLES:
                raise ValueError("binary STL triangle count outside the allowed bound")
            facets = []
            attributes = 0
            for record in struct.iter_unpack("<12fH", contents[84:]):
                facets.append(
                    (
                        _vector(record[:3]),
                        (_vector(record[3:6]), _vector(record[6:9]), _vector(record[9:12])),
                    )
                )
                attributes += int(record[12] != 0)
            return "binary", tuple(facets), attributes
    try:
        lines = [line.strip() for line in contents.decode("ascii").splitlines() if line.strip()]
    except UnicodeDecodeError as error:
        raise ValueError("binary STL length/count mismatch or non-ASCII content") from error
    if (
        len(lines) < 2
        or not re.fullmatch(r"solid(?:\s.*)?", lines[0])
        or not re.fullmatch(r"endsolid(?:\s.*)?", lines[-1])
    ):
        raise ValueError("invalid ASCII STL structure or binary length/count mismatch")
    facets = []
    index = 1

    def values(line: str, prefix: str) -> Vector3:
        tokens = line.split()
        expected = prefix.split()
        if tokens[: len(expected)] != expected or len(tokens) != len(expected) + 3:
            raise ValueError("invalid ASCII STL facet/vector grammar")
        try:
            return _vector(tuple(float(value) for value in tokens[len(expected) :]))
        except (ValueError, OverflowError) as error:
            raise ValueError("ASCII STL contains invalid/nonfinite coordinates") from error

    while index < len(lines) - 1:
        if len(facets) >= MAX_TRIANGLES or index + 6 >= len(lines) - 1:
            raise ValueError("ASCII STL triangle count/structure invalid")
        normal = values(lines[index], "facet normal")
        if (
            lines[index + 1] != "outer loop"
            or lines[index + 5] != "endloop"
            or lines[index + 6] != "endfacet"
        ):
            raise ValueError("invalid ASCII STL facet grammar")
        triangle = tuple(values(lines[index + offset], "vertex") for offset in (2, 3, 4))
        facets.append((normal, triangle))
        index += 7
    if not facets:
        raise ValueError("STL contains no triangles")
    return "ascii", tuple(facets), 0


def analyze_stl(contents: bytes) -> dict:
    """Check exact-vertex topology, winding and bounds; no automatic repair/weld.

    The vertex-link test catches two closed shells meeting at one vertex,
    which a two-facets-per-edge test alone would incorrectly call manifold.
    Exact coordinate equality is deliberate. A near-coincident gap is not
    silently welded or accepted using a guessed manufacturing tolerance.
    """
    encoding, facets, attributes = parse_stl(contents)
    vertices = {}
    points = []
    faces = []
    areas = []
    edge_count = Counter()
    edge_direction = Counter()
    duplicate_faces = Counter()
    incidence = defaultdict(list)
    normal_zero = normal_opposed = degenerate = 0
    for normal, triangle in facets:
        indices = []
        for point in triangle:
            if point not in vertices:
                vertices[point] = len(points)
                points.append(point)
            indices.append(vertices[point])
        face = tuple(indices)
        faces.append(face)
        duplicate_faces[tuple(sorted(face))] += 1
        for index in set(face):
            incidence[index].append(face)
        a, b, c = triangle
        geometric_normal = _cross(_minus(b, a), _minus(c, a))
        double_area = finite_number(math.hypot(*geometric_normal))
        areas.append(double_area / 2)
        degenerate += int(double_area == 0)
        if math.hypot(*normal) == 0:
            normal_zero += 1
        elif (
            double_area
            and math.fsum(x * y for x, y in zip(normal, geometric_normal, strict=True)) < 0
        ):
            normal_opposed += 1
        for first, second in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge = tuple(sorted((first, second)))
            edge_count[edge] += 1
            edge_direction[edge] += 1 if first < second else -1
    minimum = tuple(min(point[i] for point in points) for i in range(3))
    maximum = tuple(max(point[i] for point in points) for i in range(3))
    center = tuple(a + (b - a) / 2 for a, b in zip(minimum, maximum, strict=True))
    volumes = []
    for _, triangle in facets:
        a, b, c = (_minus(point, center) for point in triangle)
        volumes.append(
            finite_number(math.fsum(x * y for x, y in zip(a, _cross(b, c), strict=True)) / 6)
        )
    signed_volume = finite_number(math.fsum(volumes))
    nonmanifold_vertices = 0
    for vertex, incident in incidence.items():
        link = defaultdict(set)
        invalid = False
        for face in incident:
            others = [index for index in face if index != vertex]
            if len(others) != 2 or others[0] == others[1]:
                invalid = True
                continue
            link[others[0]].add(others[1])
            link[others[1]].add(others[0])
        visited = set()
        pending = [next(iter(link))] if link else []
        while pending:
            current = pending.pop()
            if current not in visited:
                visited.add(current)
                pending.extend(link[current] - visited)
        degrees = [len(neighbors) for neighbors in link.values()]
        valid_cycle = bool(degrees) and all(degree == 2 for degree in degrees)
        valid_boundary_path = degrees.count(1) == 2 and all(degree in (1, 2) for degree in degrees)
        nonmanifold_vertices += int(
            invalid or len(visited) != len(link) or not (valid_cycle or valid_boundary_path)
        )
    # Mesh components use shared vertices, not a proximity weld.
    parent = list(range(len(points)))

    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    for face in faces:
        for vertex in face[1:]:
            parent[find(vertex)] = find(face[0])
    boundary_edges = sum(count == 1 for count in edge_count.values())
    nonmanifold_edges = sum(count > 2 or edge[0] == edge[1] for edge, count in edge_count.items())
    inconsistent_edges = sum(
        count == 2 and abs(edge_direction[edge]) != 0 for edge, count in edge_count.items()
    )
    duplicates = sum(count - 1 for count in duplicate_faces.values())
    closed = not (
        boundary_edges
        or nonmanifold_edges
        or nonmanifold_vertices
        or inconsistent_edges
        or duplicates
        or degenerate
    )
    return {
        "encoding": encoding,
        "triangle_count": len(facets),
        "exact_vertex_count": len(points),
        "connected_components_by_vertex": len({find(i) for i in range(len(points))}),
        "bounds_interpreted_mm": {"min": minimum, "max": maximum},
        "envelope_xyz_interpreted_mm": tuple(
            finite_number(b - a) for a, b in zip(minimum, maximum, strict=True)
        ),
        "surface_area_interpreted_mm2": finite_number(math.fsum(areas)),
        "algebraic_signed_volume_interpreted_mm3": signed_volume,
        "absolute_signed_volume_interpreted_mm3": abs(signed_volume),
        "topology": {
            "boundary_edges": boundary_edges,
            "nonmanifold_edges": nonmanifold_edges,
            "nonmanifold_vertices": nonmanifold_vertices,
            "inconsistent_winding_edges": inconsistent_edges,
            "duplicate_facets": duplicates,
            "zero_area_facets": degenerate,
            "closed_consistently_oriented_two_manifold": closed,
            "exact_vertex_matching_no_weld": True,
        },
        "stored_normal_warnings": {
            "zero_normals": normal_zero,
            "opposed_to_winding": normal_opposed,
        },
        "nonzero_binary_attribute_words": attributes,
        "self_intersections": "not_checked",
        "units": "STL_unitless_coordinates_explicitly_interpreted_as_mm_not_encoded_units",
        "solid_fidelity": "not_established_by_topology_bounds_or_volume",
    }


def _safe_source_path(raw: str) -> str:
    if not isinstance(raw, str) or "\\" in raw or ":" in raw:
        raise ValueError("source path must be a safe repository-relative POSIX path")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {".", "..", ""} for part in raw.split("/")):
        raise ValueError("source path must be a safe repository-relative POSIX path")
    return path.as_posix()


def _bounded_read(path: Path) -> bytes:
    with path.open("rb") as handle:
        contents = handle.read(MAX_MESH_BYTES + 1)
    if len(contents) > MAX_MESH_BYTES:
        raise ValueError("source file exceeds the bounded read size")
    return contents


def compare_asset_mesh(asset: dict, mesh: dict) -> dict:
    """Report dimensional differences, never infer matching geometry from them."""
    native = tuple(finite_number(value) for value in asset["source_envelope_xyz_mm"])
    mesh_extents = tuple(mesh["envelope_xyz_interpreted_mm"])
    source_volume = finite_number(asset["source_volume_mm3"])
    return {
        "source_envelope_xyz_mm": native,
        "mesh_envelope_xyz_interpreted_mm": mesh_extents,
        "axis_aligned_extent_delta_mm": tuple(
            b - a for a, b in zip(native, mesh_extents, strict=True)
        ),
        "sorted_extent_absolute_delta_mm": tuple(
            abs(b - a) for a, b in zip(sorted(native), sorted(mesh_extents), strict=True)
        ),
        "source_volume_mm3": source_volume,
        "mesh_absolute_signed_volume_proxy_mm3": mesh["absolute_signed_volume_interpreted_mm3"],
        "relative_volume_proxy_delta": (
            mesh["absolute_signed_volume_interpreted_mm3"] - source_volume
        )
        / source_volume,
        "comparison_scope": "extent/volume diagnostics only; source STL may use a different "
        "frame or geometry revision; not native final-solid equivalence",
        "native_source_hash": asset["source_sha256"],
    }


def installed_profile_scenario(audit: dict) -> dict:
    """Reconcile the audited Kobra profile's outline/exclusions for draft AABBs.

    This intentionally handles the one identified installed profile, failing
    on unfamiliar internal keepouts instead of pretending to be a general
    packing/slicer engine. Physical nozzle/material fields remain independent.
    """
    if (
        not isinstance(audit, dict)
        or type(audit.get("schema_version")) is not int
        or audit["schema_version"] != 1
    ):
        raise ValueError("installed profile audit needs schema version1")
    machine = audit["profiles"]["machine"]
    fields = machine["resolved_allowlisted_fields"]
    if (
        machine["selected_name"] != "Anycubic Kobra 3 Max 0.4 nozzle"
        or fields["printer_model"] != "Anycubic Kobra 3 Max"
    ):
        raise ValueError("draft plan requires the audited installed Kobra3Max profile")
    chain = machine["inheritance_chain_leaf_first"]
    if (
        len(chain) != 1
        or chain[0]["sha256"] != "6bfe04a34c1c2d1ff6930bd11e698c2d7721bb42e64aceefda7795a7d8ff0c7e"
    ):
        raise ValueError("installed machine profile hash changed; re-audit required")

    def points(raw):
        if not isinstance(raw, list):
            raise ValueError("profile points must be a list")
        result = []
        for value in raw:
            if not isinstance(value, str) or len(value.split("x")) != 2:
                raise ValueError("invalid profile coordinate")
            result.append(tuple(finite_number(float(component)) for component in value.split("x")))
        return result

    outline = points(fields["printable_area"])
    if outline != [(0.0, 0.0), (426.0, 0.0), (426.0, 420.0), (0.0, 420.0)]:
        raise ValueError("unfamiliar installed outline; explicit draft review required")
    exclusions = points(fields["bed_exclude_area"])
    if len(exclusions) != 16:
        raise ValueError("unfamiliar bed exclusion format")
    left, right = 0.0, 426.0
    exclusion_rectangles = []
    for offset in range(0, 16, 4):
        polygon = exclusions[offset : offset + 4]
        lo = tuple(min(point[i] for point in polygon) for i in range(2))
        hi = tuple(max(point[i] for point in polygon) for i in range(2))
        if lo[0] == hi[0] or lo[1] == hi[1]:
            continue
        if (
            set(polygon) != {(lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])}
            or lo[1] != 0
            or hi[1] != 420
        ):
            raise ValueError("unfamiliar internal bed keepout")
        if lo[0] == 0:
            left = max(left, hi[0])
        elif hi[0] == 426:
            right = min(right, lo[0])
        else:
            raise ValueError("unfamiliar internal bed keepout")
        exclusion_rectangles.append([lo, hi])
    if (left, right) != (3.0, 423.0):
        raise ValueError("installed profile edge exclusions changed")
    height = finite_number(float(fields["printable_height"]))
    if height != 501:
        raise ValueError("installed profile height changed")
    interpreted = audit["profile_numeric_interpretation"]["candidate_exclusion_interpretation"]
    if (
        interpreted["candidate_inner_rectangle_mm"] != [[3, 0], [423, 420]]
        or interpreted["conservative_draft_height_mm"] != 500
    ):
        raise ValueError("profile interpretation contradicts raw allowlisted machine fields")
    selected = audit["saved_selection"]
    if (
        selected["is_live_gui_state"] is not False
        or selected["is_physical_hardware_confirmation"] is not False
    ):
        raise ValueError("saved software selection must not claim physical/live confirmation")
    return {
        "evidence_class": "saved_software_profile_draft_scenario_not_physical_confirmation",
        "application_version": audit["installed_application"]["file_version"],
        "selected_profiles": selected["profile_fields"],
        "source_profile_chains": {
            role: record["inheritance_chain_leaf_first"]
            for role, record in audit["profiles"].items()
        },
        "outline_mm": outline,
        "excluded_rectangles_mm": exclusion_rectangles,
        "candidate_inner_rectangle_mm": [[left, 0.0], [right, 420.0]],
        "conservative_height_mm": 500.0,
        "physical_confirmation": audit["physical_confirmation"],
        "configured_brim_width_mm": audit["profile_numeric_interpretation"][
            "configured_brim_width_mm"
        ],
        "process_defaults_are_not_accepted_Thor_settings": True,
    }


def centered_draft_placement(mesh: dict, profile: dict, *, margin_mm: float = 10.0) -> dict:
    margin = finite_number(margin_mm)
    if margin < 0:
        raise ValueError("draft placement margin cannot be negative")
    low, high = profile["candidate_inner_rectangle_mm"]
    minimum, maximum = mesh["bounds_interpreted_mm"]["min"], mesh["bounds_interpreted_mm"]["max"]
    extent = mesh["envelope_xyz_interpreted_mm"]
    fit = (
        all(extent[i] + 2 * margin <= high[i] - low[i] for i in range(2))
        and extent[2] <= profile["conservative_height_mm"]
    )
    return {
        "orientation_candidate": "source_STL_Z_up_unselected_unqualified",
        "rotation_degrees_xyz": [0.0, 0.0, 0.0],
        "translation_mm": [(low[i] + high[i] - minimum[i] - maximum[i]) / 2 for i in range(2)]
        + [-minimum[2]],
        "aabb_fit_in_provisional_inner_rectangle": fit,
        "draft_xy_margin_mm": margin,
        "margin_scope": "numerical spacing proposal including configured brim allowance; "
        "support geometry and actual printer clearance unknown",
        "stable_contact_face_or_layer_strength_verified": False,
    }


def build_plan(
    manifest: dict, tree: dict, upstream_root: Path, *, profile: dict | None = None
) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("printable asset manifest must be an object")
    if manifest.get("source_revision") != SOURCE_REVISION or manifest.get("counts") != {
        "installed_printed_leaves": 65,
        "unique_source_assets": 46,
        "export_geometry_variants": 47,
        "reflected_installed_leaves": 1,
    }:
        raise ValueError(
            "printable asset baseline revision/counts do not match the expected checkpoint"
        )
    if any(type(value) is not int for value in manifest["counts"].values()):
        raise ValueError("printable manifest counts must be integers")
    if (
        not isinstance(tree, dict)
        or tree.get("truncated") is not False
        or not isinstance(tree.get("tree"), list)
        or tree.get("sha") != SOURCE_REVISION
        or tree.get("url")
        != f"https://api.github.com/repos/AngelLM/Thor/git/trees/{SOURCE_REVISION}"
        or canonical_sha256(tree) != PINNED_TREE_CANONICAL_SHA256
    ):
        raise ValueError("a complete pinned Git tree capture is required")
    entries = {}
    for entry in tree["tree"]:
        path = _safe_source_path(entry["path"])
        if path in entries:
            raise ValueError("duplicate source tree path")
        entries[path] = entry
    instances = _instances(manifest)
    instance_variants = Counter(
        (asset["asset_id"], instance["variant_id"]) for asset, instance in instances.values()
    )
    assets = manifest.get("assets")
    if (
        not isinstance(assets, list)
        or len(assets) != 46
        or sum(asset["quantity"] for asset in assets) != 65
    ):
        raise ValueError("asset quantities do not reconcile")
    if len({asset["asset_id"] for asset in assets}) != len(assets):
        raise ValueError("duplicate asset identity")
    declared_variants = Counter()
    for asset in assets:
        if type(asset["quantity"]) is not int or asset["quantity"] <= 0:
            raise ValueError("asset quantity must be a positive integer")
        variants = asset.get("export_variants")
        if not isinstance(variants, list) or len(
            {variant["variant_id"] for variant in variants}
        ) != len(variants):
            raise ValueError("duplicate or missing geometry variants")
        for variant in variants:
            if (
                variant["variant_id"] not in {"nominal", "reflected"}
                or type(variant["quantity"]) is not int
                or variant["quantity"] <= 0
            ):
                raise ValueError("variant quantity/id is invalid")
            declared_variants[(asset["asset_id"], variant["variant_id"])] = variant["quantity"]
        if sum(variant["quantity"] for variant in variants) != asset["quantity"]:
            raise ValueError("asset quantity does not match its variants")
    if declared_variants != instance_variants:
        raise ValueError("export variants do not match installed instance identities")
    by_name = {asset["source_file"].split("/")[-1].rsplit(".", 1)[0]: asset for asset in assets}
    if len(by_name) != 46:
        raise ValueError("ambiguous source asset names")
    nominal_paths = sorted(
        path for path in entries if path.startswith("stl/") and path.lower().endswith(".stl")
    )
    mod_paths = sorted(
        path for path in entries if path.startswith("mods/") and path.lower().endswith(".stl")
    )
    audit = []
    asset_mesh = {}
    resolved_root = upstream_root.resolve()
    for source_path in nominal_paths + ["LICENSE"]:
        entry = entries.get(source_path)
        if (
            not entry
            or entry.get("type") != "blob"
            or not isinstance(entry.get("sha"), str)
            or re.fullmatch(r"[0-9a-f]{40}", entry["sha"]) is None
            or type(entry.get("size")) is not int
        ):
            raise ValueError("missing/invalid pinned source blob metadata")
        local = (upstream_root / source_path).resolve()
        if not local.is_relative_to(resolved_root):
            raise ValueError("source path escapes the upstream source root")
        contents = _bounded_read(local)
        blob = hashlib.sha1(b"blob " + str(len(contents)).encode() + b"\0" + contents).hexdigest()
        if blob != entry["sha"] or entry.get("size") != len(contents):
            raise ValueError(f"pinned source blob mismatch: {source_path}")
        row = {
            "source_path": source_path,
            "source_url": f"{SOURCE_REPOSITORY}/blob/{SOURCE_REVISION}/{source_path}",
            "git_blob_sha1": blob,
            "sha256": hashlib.sha256(contents).hexdigest(),
            "bytes": len(contents),
        }
        if source_path != "LICENSE":
            mesh = analyze_stl(contents)
            row["mesh"] = mesh
            asset = by_name.get(PurePosixPath(source_path).stem)
            row["installed_asset_id"] = None if asset is None else asset["asset_id"]
            row["disposition"] = (
                "source_only_not_in_installed_ledger"
                if asset is None
                else "upstream_mesh_candidate_not_native_export"
            )
            row["comparison"] = None if asset is None else compare_asset_mesh(asset, mesh)
            if asset is not None:
                asset_mesh[asset["asset_id"]] = row
        audit.append(row)
    profile_summary = None if profile is None else installed_profile_scenario(profile)
    plates = []
    for asset in assets:
        for variant in asset["export_variants"]:
            source = (
                asset_mesh.get(asset["asset_id"]) if variant["variant_id"] == "nominal" else None
            )
            stage = "blocked_missing_reflected_native_export"
            blockers = ["missing_native_reflected_variant"]
            if source is not None:
                stage = "source_mesh_audited_waiting_profile_orientation_and_fidelity_review"
                blockers = [
                    "native_geometry_fidelity_unverified",
                    "orientation_support_fit_review_pending",
                ]
                if not source["mesh"]["topology"]["closed_consistently_oriented_two_manifold"]:
                    stage = "blocked_source_mesh_topology"
                    blockers.append("source_mesh_fails_exact_vertex_manifold_or_winding_checks")
                if asset["asset_id"].startswith("Art1Body::"):
                    blockers.append("Art1_exact_final_solid_and_unrepaired_history_gate")
            plates.append(
                {
                    "plate_group_id": f"draft-{len(plates) + 1:03d}",
                    "asset_id": asset["asset_id"],
                    "geometry_variant": variant["variant_id"],
                    "one_part_per_plate": True,
                    "repeat_plate_count": variant["quantity"],
                    "source_mesh_path": None if source is None else source["source_path"],
                    "source_mesh_sha256": None if source is None else source["sha256"],
                    "mesh_kind": None
                    if source is None
                    else "pinned_upstream_STL_not_RAFTEL_native_final_solid_export",
                    "stage": stage,
                    "unresolved_gates": blockers,
                    "orientation": None,
                    "placement_mm": None,
                    "draft_placement_proposal": None
                    if source is None
                    or profile_summary is None
                    or not source["mesh"]["topology"]["closed_consistently_oriented_two_manifold"]
                    else centered_draft_placement(source["mesh"], profile_summary),
                    "supports": None,
                    "material": None,
                    "machine_profile": None
                    if profile_summary is None
                    else profile_summary["selected_profiles"]["machine"],
                    "fit_coupon_dependencies": [
                        "actual_nozzle_and_filament_profile",
                        "bearing_shaft_bolt_socket_fit_measurements_as_applicable",
                        "Art1_exact_final_solid_gate"
                        if asset["asset_id"].startswith("Art1Body::")
                        else "native_final_solid_or_justified_source_mesh_acceptance",
                    ],
                    "inspection_candidates": asset["orientation_and_inspection"],
                }
            )
    if sum(plate["repeat_plate_count"] for plate in plates) != 65 or len(plates) != 47:
        raise ValueError("draft plate variants/quantities do not conserve the installed ledger")
    return {
        "schema_version": 1,
        "evidence_class": "pinned_upstream_STL_audit_and_unreleased_draft_queue",
        "source_revision": SOURCE_REVISION,
        "source_repository": SOURCE_REPOSITORY,
        "input_canonical_sha256": {
            "printable_asset_manifest": canonical_sha256(manifest),
            "pinned_tree_capture": canonical_sha256(tree),
            "installed_profile_audit": None if profile is None else canonical_sha256(profile),
        },
        "counts": {
            "nominal_upstream_meshes_audited": len(nominal_paths),
            "unselected_mod_mesh_paths": len(mod_paths),
            "source_only_nominal_meshes": sum(
                row.get("disposition") == "source_only_not_in_installed_ledger" for row in audit
            ),
            "installed_assets_with_named_upstream_mesh": len(asset_mesh),
            "installed_printed_leaves": 65,
            "geometry_variant_groups": len(plates),
            "nominal_plate_instances": sum(
                plate["repeat_plate_count"]
                for plate in plates
                if plate["source_mesh_path"] is not None
            ),
            "missing_variant_plate_instances": sum(
                plate["repeat_plate_count"] for plate in plates if plate["source_mesh_path"] is None
            ),
            "topology_blocked_plate_instances": sum(
                plate["repeat_plate_count"]
                for plate in plates
                if plate["stage"] == "blocked_source_mesh_topology"
            ),
            "blocked_plate_instances": sum(
                plate["repeat_plate_count"]
                for plate in plates
                if plate["stage"].startswith("blocked_")
            ),
            "eligible_for_draft_planning_instances": sum(
                plate["repeat_plate_count"]
                for plate in plates
                if not plate["stage"].startswith("blocked_")
            ),
        },
        "installed_profile": profile_summary,
        "mesh_audit": audit,
        "unselected_mod_mesh_paths": mod_paths,
        "upstream_3mf_paths": sorted(path for path in entries if path.lower().endswith(".3mf")),
        "draft_plate_groups": plates,
        "attribution": manifest["attribution"],
        "qualification": {
            "native_final_solid_exports_created": False,
            "source_mesh_geometry_equivalence_verified": False,
            "self_intersections_checked": False,
            "actual_nozzle_confirmed": False,
            "actual_filament_profile_confirmed": False,
            "supports_or_orientations_selected": False,
            "slicer_project_created": False,
            "sliced": False,
            "printer_contacted": False,
            "manufacturing_release": False,
        },
        "next_gates": [
            "Audit installed Kobra 3 Max machine profile and preserve its exact bytes/hash",
            "Confirm actual nozzle and material before process-dependent choices",
            "Independently compare source STL discrepancies with accepted native final solids",
            "Export and validate the reflected finger as a distinct geometry variant",
            "Inspect stable bed faces, layer loads, supports, brims and fit coupons "
            "before selecting draft orientations",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "hardware/cad/thor-printable-assets-v1.json"
    )
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument(
        "--profile-audit",
        type=Path,
        help="Optional allowlisted installed/saved profile audit; never physical confirmation",
    )
    parser.add_argument(
        "--output", type=Path, help="New JSON report path; existing evidence is preserved"
    )
    args = parser.parse_args(argv)
    try:
        manifest = _strict_json(_bounded_read(args.manifest))
        tree = _strict_json(_bounded_read(args.tree))
        profile = (
            None if args.profile_audit is None else _strict_json(_bounded_read(args.profile_audit))
        )
        report = build_plan(manifest, tree, args.upstream_root, profile=profile)
        encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            sys.stdout.write(encoded)
        else:
            with args.output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
            print(f"Wrote source mesh audit and unreleased plate queue: {args.output}")
        return 0
    except (ValueError, OSError, OverflowError, KeyError, TypeError) as error:
        print(f"Draft slicer planning failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
