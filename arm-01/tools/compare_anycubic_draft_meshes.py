"""Compare saved 3MF discrete meshes with a source draft without modifying either.

Exact oriented facets retain winding and multiplicity. A coordinate residual is
only a bounded numerical diagnostic: it never proves continuous surface/solid
equivalence, self-intersection freedom, slicer behavior, or print qualification.
Archive/XML validation is shared with audit_anycubic_draft_project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

from audit_anycubic_draft_project import load_project

from raftel_arm01.engineering.scenarios import _strict_json

UNIT_MM = {
    "micron": 0.001,
    "millimeter": 1.0,
    "centimeter": 10.0,
    "inch": 25.4,
    "foot": 304.8,
    "meter": 1000.0,
}
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_EXPANDED_FACETS = 1_000_000


def _rational(token):
    # Bound lexical arithmetic before constructing large integer denominators.
    if not isinstance(token, str) or len(token) > 80:
        raise ValueError("coordinate/transform numeric token exceeds comparison bound")
    try:
        number = Decimal(token)
    except InvalidOperation as error:
        raise ValueError("invalid decimal numeric token") from error
    if not number.is_finite() or abs(number.as_tuple().exponent) > 400:
        raise ValueError("coordinate/transform decimal exponent exceeds comparison bound")
    return Fraction(number)


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str
    ).encode()


def _facets(vertices, triangles):
    """Same cyclic-oriented Counter rule as diagnose_thor_optodisk_mesh.

    No coordinate welding or reversed-winding normalization is performed.
    """
    result = Counter()
    for face in triangles:
        triangle = tuple(tuple(vertices[index]) for index in face)
        result[min(triangle, triangle[1:] + triangle[:1], triangle[2:] + triangle[:2])] += 1
    return result


def _compare_mesh(a, b, bound_mm):
    av, af = a["vertices_mm"], a["triangles"]
    bv, bf = b["vertices_mm"], b["triangles"]
    ac, bc = a["facets"], b["facets"]
    indexed_equal = av == bv and af == bf
    facets_equal = ac == bc
    # Only ordered, identical indices supply a numerical correspondence witness.
    # Do not nearest-neighbor match or infer correspondence from a small residual.
    comparable = len(av) == len(bv) and af == bf
    residual = (
        max(abs(x - y) for p, q in zip(av, bv, strict=True) for x, y in zip(p, q, strict=True))
        if comparable
        else None
    )
    if indexed_equal:
        classification = "exact_indexed_mesh"
    elif facets_equal:
        classification = "exact_oriented_facet_multiset"
    elif residual is not None and residual <= Fraction(str(bound_mm)):
        classification = "bounded_coordinate_difference"
    else:
        classification = "different_discrete_geometry"
    return {
        "classification": classification,
        "exact_indexed_vertices_and_triangles": indexed_equal,
        "exact_oriented_cyclic_facet_multiset": facets_equal,
        "source_only_oriented_facets": sum((ac - bc).values()),
        "saved_only_oriented_facets": sum((bc - ac).values()),
        "ordered_index_correspondence_available": comparable,
        "max_ordered_coordinate_component_residual_mm": (
            float(residual) if residual is not None and residual <= sys.float_info.max else None
        ),
        "max_ordered_coordinate_component_residual_mm_exact": str(residual)
        if residual is not None
        else None,
        "declared_coordinate_diagnostic_bound_mm": bound_mm,
        "full_surface_equivalence_proven": False,
    }


def _leaves(project):
    models = {model["path"]: model for model in project["models"]}
    objects = {
        (model["path"], obj["id"]): obj for model in project["models"] for obj in model["objects"]
    }
    leaves = []
    expanded = 0
    expanded_vertices = 0
    for index, instance in enumerate(project["instances"]):
        model = models[instance["model_path"]]
        obj = objects[(instance["model_path"], instance["objectid"])]
        unit = model["unit"]
        if unit not in UNIT_MM:
            raise ValueError("unsupported 3MF unit")
        expanded += len(obj["triangles"])
        expanded_vertices += len(obj["vertices"])
        if max(expanded, expanded_vertices) > MAX_EXPANDED_FACETS:
            raise ValueError("expanded mesh instance geometry limit exceeded")
        scale = Fraction(str(UNIT_MM[unit]))
        raw_vertices = tuple(
            tuple(_rational(token) for token in point) for point in obj["vertex_tokens"]
        )
        vertices = tuple(tuple(value * scale for value in point) for point in raw_vertices)
        if "transform_tokens_chain" not in instance:
            raise ValueError("exact mesh comparison requires lexical transform tokens")
        chain = [
            tuple(_rational(value) for value in row) for row in instance["transform_tokens_chain"]
        ]
        transformed = []
        for point in raw_vertices:
            p = tuple(point)
            for t in chain:
                p = tuple(sum(p[k] * t[3 * k + j] for k in range(3)) + t[9 + j] for j in range(3))
            transformed.append(tuple(value * scale for value in p))
        if any(abs(x) > sys.float_info.max for point in (*vertices, *transformed) for x in point):
            raise ValueError("transformed coordinate overflow")
        faces = tuple(tuple(face) for face in obj["triangles"])
        local = {"vertices_mm": vertices, "triangles": faces}
        world = {"vertices_mm": tuple(transformed), "triangles": faces}
        local["facets"] = _facets(vertices, faces)
        world["facets"] = _facets(transformed, faces)
        leaves.append(
            {
                "identity": {
                    "leaf_index": index,
                    "model_path": instance["model_path"],
                    "objectid": instance["objectid"],
                    "build_index": instance["build_index"],
                    "printable": instance["printable"],
                    "unit": unit,
                    "transform_chain": instance["transform_chain"],
                    "transform_tokens_chain": instance["transform_tokens_chain"],
                    "vertex_count": len(vertices),
                    "triangle_count": len(faces),
                    "local_indexed_mesh_sha256": hashlib.sha256(
                        _canonical([vertices, faces])
                    ).hexdigest(),
                    "vertex_tokens_sha256": hashlib.sha256(
                        _canonical(obj["vertex_tokens"])
                    ).hexdigest(),
                },
                "local": local,
                "world": world,
            }
        )
    return leaves


def _receipt_check(path, source, leaves):
    if path is None:
        return None
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_RECEIPT_BYTES + 1)
    if len(raw) > MAX_RECEIPT_BYTES:
        raise ValueError("source receipt exceeds size bound")
    receipt = _strict_json(raw)
    if not isinstance(receipt, dict):
        raise ValueError("source receipt must be a JSON object")
    if receipt.get("package_sha256") != source["sha256"]:
        raise ValueError("source receipt package SHA256 mismatch")
    copies = receipt.get("copies", [])
    if not isinstance(copies, list) or any(not isinstance(row, dict) for row in copies):
        raise ValueError("source receipt copies must be object rows")
    if len(copies) != len(leaves):
        raise ValueError("source receipt copy count mismatch")
    by_id = {str(row["object_id"]): row for row in copies}
    if len(by_id) != len(copies):
        raise ValueError("source receipt has duplicate object IDs")
    for leaf in leaves:
        identity = leaf["identity"]
        row = by_id.get(identity["objectid"])
        if row is None or any(
            row[key] != identity[key] for key in ("vertex_count", "triangle_count")
        ):
            raise ValueError("source receipt object identity/count mismatch")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "authenticated_copy_count": len(copies),
        "copies": [
            {
                key: row[key]
                for key in (
                    "object_id",
                    "asset_id",
                    "geometry_variant",
                    "copy_index",
                    "installed_instance_id",
                )
            }
            for row in copies
        ],
    }


def compare_projects(source_path, saved_path, *, source_receipt=None, coordinate_bound_mm=0.0):
    """Bounded read-only comparison. Unmatched identities stay explicitly unknown.

    Match exact world facets first, then exact local facets; this can witness a
    changed placement. Remaining leaves are compared by ordinal only, explicitly
    unverified as identities. Duplicate identical geometry cannot prove copy ID.
    """
    if (
        isinstance(coordinate_bound_mm, bool)
        or not isinstance(coordinate_bound_mm, (int, float))
        or not math.isfinite(coordinate_bound_mm)
        or coordinate_bound_mm < 0
        or coordinate_bound_mm > 1.0
    ):
        raise ValueError("coordinate diagnostic bound must be finite in [0, 1] mm")
    source, saved = load_project(source_path), load_project(saved_path)
    a, b = _leaves(source), _leaves(saved)
    receipt = _receipt_check(source_receipt, source, a)
    remaining = set(range(len(b)))
    matches = {}
    for domain in ("world", "local"):
        for i, leaf in enumerate(a):
            if i in matches:
                continue
            candidates = [
                j for j in sorted(remaining) if leaf[domain]["facets"] == b[j][domain]["facets"]
            ]
            if candidates:
                j = candidates[0]
                matches[i] = (j, "exact_" + domain + "_facets", len(candidates))
                remaining.remove(j)
    for i in range(len(a)):
        if i not in matches and remaining:
            j = i if i in remaining else min(remaining)
            matches[i] = (j, "ordinal_diagnostic_identity_unverified", 0)
            remaining.remove(j)
    rows = []
    for i, leaf in enumerate(a):
        if i not in matches:
            rows.append(
                {"source": leaf["identity"], "saved": None, "correspondence": "missing_saved_leaf"}
            )
            continue
        j, rule, candidates = matches[i]
        ai, bi = leaf["identity"], b[j]["identity"]
        local = _compare_mesh(leaf["local"], b[j]["local"], coordinate_bound_mm)
        if local["exact_indexed_vertices_and_triangles"]:
            if ai["unit"] != bi["unit"]:
                local["classification"] = "unit_representation_only"
            elif ai["vertex_tokens_sha256"] != bi["vertex_tokens_sha256"]:
                local["classification"] = "numeric_representation_only"
        rows.append(
            {
                "source": ai,
                "saved": bi,
                "correspondence": rule,
                "exact_match_candidate_count_at_assignment": candidates,
                "copy_identity_proven_by_geometry": False,
                "same_resource_id": ai["objectid"] == bi["objectid"],
                "same_unit": ai["unit"] == bi["unit"],
                "same_transform_chain": [
                    [_rational(token) for token in transform]
                    for transform in ai["transform_tokens_chain"]
                ]
                == [
                    [_rational(token) for token in transform]
                    for transform in bi["transform_tokens_chain"]
                ],
                "same_transform_tokens_chain": (
                    ai["transform_tokens_chain"] == bi["transform_tokens_chain"]
                ),
                "same_printable_flag": ai["printable"] == bi["printable"],
                "local_mesh": local,
                "placed_mesh": _compare_mesh(leaf["world"], b[j]["world"], coordinate_bound_mm),
            }
        )
    exact = len(a) == len(b) and all(
        row.get("placed_mesh", {}).get("exact_oriented_cyclic_facet_multiset", False)
        and row.get("same_printable_flag", False)
        for row in rows
    )
    return {
        "schema": "raftel.anycubic_draft_mesh_comparison.v1",
        "evidence_class": "host_discrete_mesh_comparison_not_native_or_manufacturing_acceptance",
        "source": {"sha256": source["sha256"], "size": source["size"], "leaf_count": len(a)},
        "saved": {"sha256": saved["sha256"], "size": saved["size"], "leaf_count": len(b)},
        "source_receipt": receipt,
        "copies": rows,
        "unmatched_saved_leaves": [b[j]["identity"] for j in sorted(remaining)],
        "placed_oriented_facet_multisets_exactly_preserved": exact,
        "exact_coordinate_arithmetic": "rational XML decimal tokens including units and transforms",
        "resource_ids_and_copy_identity_independently_verified": False,
        "continuous_surface_equivalence_proven": False,
        "slicing_observed": False,
        "manufacturing_release": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--saved", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path)
    parser.add_argument("--coordinate-bound-mm", type=float, default=0.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.resolve() in {
            path.resolve()
            for path in (args.source, args.saved, args.source_receipt)
            if path is not None
        }:
            raise ValueError("output must be a fresh path distinct from inputs")
        report = compare_projects(
            args.source,
            args.saved,
            source_receipt=args.source_receipt,
            coordinate_bound_mm=args.coordinate_bound_mm,
        )
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        return 0 if report["placed_oriented_facet_multisets_exactly_preserved"] else 1
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        OverflowError,
        ET.ParseError,
        zipfile.BadZipFile,
    ) as error:
        print(f"3MF mesh comparison failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
