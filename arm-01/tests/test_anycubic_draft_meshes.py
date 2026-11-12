"""Synthetic format/geometry witnesses; no Anycubic/native acceptance."""

import hashlib
import importlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

TOOLS = Path(__file__).parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
compare = importlib.import_module("compare_anycubic_draft_meshes")

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
IDENTITY = "1 0 0 0 1 0 0 0 1 0 0 0"


def package(
    *,
    points=None,
    faces=None,
    unit="millimeter",
    transform=IDENTITY,
    identifier="1",
    repeat=1,
    component_transform=None,
    printable="1",
):
    points = points or [("0", "0", "0"), ("1", "0", "0"), ("0", "1", "0")]
    faces = faces or [(0, 1, 2)]
    vertices = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in points)
    triangles = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
    obj = (
        f'<object id="{identifier}" type="model"><mesh><vertices>{vertices}</vertices>'
        f"<triangles>{triangles}</triangles></mesh></object>"
    )
    build_id = identifier
    if component_transform is not None:
        obj += (
            '<object id="99" type="model"><components>'
            f'<component objectid="{identifier}" transform="{component_transform}"/>'
            "</components></object>"
        )
        build_id = "99"
    items = "".join(
        f'<item objectid="{build_id}" transform="{transform}" printable="{printable}"/>'
        for _ in range(repeat)
    )
    model = (
        f'<model xmlns="{CORE}" unit="{unit}"><resources>{obj}</resources>'
        f"<build>{items}</build></model>"
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="model" '
            'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="r" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" '
            'Target="/3D/3dmodel.model"/></Relationships>',
        )
        archive.writestr("3D/3dmodel.model", model)
    return stream.getvalue()


def row(report):
    return report["copies"][0]


def test_exact_and_representation_only():
    source = package()
    exact = compare.compare_projects(source, source)
    assert exact["placed_oriented_facet_multisets_exactly_preserved"]
    assert row(exact)["local_mesh"]["classification"] == "exact_indexed_mesh"
    lexical = package(points=[("0.0", "0e0", "-0"), ("1.000", "0", "0"), ("0", "1e0", "0")])
    result = compare.compare_projects(source, lexical)
    assert result["placed_oriented_facet_multisets_exactly_preserved"]
    assert row(result)["local_mesh"]["classification"] == "numeric_representation_only"
    assert not result["continuous_surface_equivalence_proven"]


def test_float_collapsed_decimal_is_not_exact():
    saved = package(points=[("0", "0", "0"), ("1.00000000000000001", "0", "0"), ("0", "1", "0")])
    result = compare.compare_projects(package(), saved, coordinate_bound_mm=1e-15)
    assert not result["placed_oriented_facet_multisets_exactly_preserved"]
    local = row(result)["local_mesh"]
    assert local["classification"] == "bounded_coordinate_difference"
    assert local["max_ordered_coordinate_component_residual_mm_exact"] == "1/100000000000000000"


def test_reindexed_and_cyclic_order_preserve_oriented_facets():
    saved = package(
        points=[("0", "1", "0"), ("0", "0", "0"), ("1", "0", "0")],
        faces=[(0, 1, 2)],
        identifier="9",
    )
    result = compare.compare_projects(package(), saved)
    assert result["placed_oriented_facet_multisets_exactly_preserved"]
    assert row(result)["local_mesh"]["classification"] == "exact_oriented_facet_multiset"
    assert not row(result)["same_resource_id"]
    assert not row(result)["copy_identity_proven_by_geometry"]


@pytest.mark.parametrize(
    "saved", [package(faces=[(0, 2, 1)]), package(faces=[(0, 1, 2), (0, 1, 2)])]
)
def test_reversed_winding_and_facet_multiplicity_fail(saved):
    result = compare.compare_projects(package(), saved)
    assert not result["placed_oriented_facet_multisets_exactly_preserved"]
    assert (
        row(result)["placed_mesh"]["source_only_oriented_facets"]
        or row(result)["placed_mesh"]["saved_only_oriented_facets"]
    )


def test_baked_translation_keeps_placed_geometry_but_changes_local():
    source = package(transform="1 0 0 0 1 0 0 0 1 7 2 0")
    saved = package(points=[("7", "2", "0"), ("8", "2", "0"), ("7", "3", "0")])
    result = compare.compare_projects(source, saved)
    assert result["placed_oriented_facet_multisets_exactly_preserved"]
    assert row(result)["local_mesh"]["classification"] == "different_discrete_geometry"
    assert not row(result)["same_transform_chain"]


def test_component_order_and_exact_units():
    # Local x translation, then quarter turn around z, then y translation.
    source = package(
        component_transform="1 0 0 0 1 0 0 0 1 2 0 0", transform="0 1 0 -1 0 0 0 0 1 0 3 0"
    )
    baked = package(points=[("0", "5", "0"), ("0", "6", "0"), ("-1", "5", "0")])
    assert compare.compare_projects(source, baked)[
        "placed_oriented_facet_multisets_exactly_preserved"
    ]
    inches = package(unit="inch")
    mm = package(points=[("0", "0", "0"), ("25.4", "0", "0"), ("0", "25.4", "0")])
    result = compare.compare_projects(inches, mm)
    assert result["placed_oriented_facet_multisets_exactly_preserved"]
    assert not row(result)["same_unit"]


def test_transform_decimal_collapse_and_reflection_fail():
    changed = package(transform="1 0 0 0 1 0 0 0 1 0.00000000000000001 0 0")
    assert not compare.compare_projects(package(), changed)[
        "placed_oriented_facet_multisets_exactly_preserved"
    ]
    reflected = package(transform="-1 0 0 0 1 0 0 0 1 0 0 0")
    assert not compare.compare_projects(package(), reflected)[
        "placed_oriented_facet_multisets_exactly_preserved"
    ]
    source = package(transform="1 0 0 0 1 0 0 0 1 1 0 0")
    distinct = package(transform="1 0 0 0 1 0 0 0 1 1.00000000000000001 0 0")
    assert not row(compare.compare_projects(source, distinct))["same_transform_chain"]
    lexical = package(transform="1 0 0 0 1 0 0 0 1 1.0 0 0")
    same = row(compare.compare_projects(source, lexical))
    assert same["same_transform_chain"]
    assert not same["same_transform_tokens_chain"]


def test_missing_extra_duplicates_and_printable_are_visible():
    a = compare.compare_projects(package(repeat=2), package())
    assert a["copies"][1]["correspondence"] == "missing_saved_leaf"
    b = compare.compare_projects(package(), package(repeat=2))
    assert len(b["unmatched_saved_leaves"]) == 1
    assert row(b)["exact_match_candidate_count_at_assignment"] == 2
    assert not b["placed_oriented_facet_multisets_exactly_preserved"]
    c = compare.compare_projects(package(), package(printable="0"))
    assert not c["placed_oriented_facet_multisets_exactly_preserved"]


@pytest.mark.parametrize("bound", [-1, float("nan"), float("inf"), True, 1.1])
def test_invalid_diagnostic_bound(bound):
    with pytest.raises(ValueError, match="bound"):
        compare.compare_projects(package(), package(), coordinate_bound_mm=bound)


def test_numeric_exponent_and_expanded_geometry_bounds(monkeypatch):
    extreme = package(points=[("1e-10000", "0", "0"), ("1", "0", "0"), ("0", "1", "0")])
    with pytest.raises(ValueError, match="exponent"):
        compare.compare_projects(package(), extreme)
    monkeypatch.setattr(compare, "MAX_EXPANDED_FACETS", 2)
    with pytest.raises(ValueError, match="expanded"):
        compare.compare_projects(package(), package())


def test_excessive_coordinates_rejected_by_shared_loader():
    huge = package(
        points=[("1e308", "0", "0"), ("0", "1", "0"), ("0", "0", "1")],
        transform="1e308 0 0 0 1 0 0 0 1 0 0 0",
    )
    with pytest.raises(ValueError, match="out-of-range"):
        compare.compare_projects(package(), huge)


def test_invalid_input_delegates_to_bounded_shared_parser():
    with pytest.raises(ValueError):
        compare.compare_projects(package(faces=[(0, 1, 10)]), package())
    with pytest.raises(ValueError):
        compare.compare_projects(package(points=[("nan", "0", "0")] * 3), package())


def test_receipt_binding_and_exclusive_cli_output(tmp_path):
    source, saved, output = [tmp_path / x for x in ("source.3mf", "saved.3mf", "report.json")]
    source.write_bytes(package())
    saved.write_bytes(package())
    args = ["--source", str(source), "--saved", str(saved), "--output", str(output)]
    assert compare.main(args) == 0
    raw = output.read_bytes()
    assert b"\r" not in raw
    assert json.loads(raw)["placed_oriented_facet_multisets_exactly_preserved"]
    assert compare.main(args) == 2
    assert output.read_bytes() == raw
    receipt = tmp_path / "source.json"
    receipt.write_text(json.dumps({"package_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256"):
        compare.compare_projects(source, saved, source_receipt=receipt)


def test_positive_receipt_identity_and_cli_negative_paths(tmp_path):
    source, saved, output = [tmp_path / x for x in ("a.3mf", "b.3mf", "r.json")]
    source.write_bytes(package())
    saved.write_bytes(package(faces=[(0, 2, 1)]))
    receipt = tmp_path / "source.json"
    receipt.write_text(
        json.dumps(
            {
                "package_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "copies": [
                    {
                        "object_id": 1,
                        "vertex_count": 3,
                        "triangle_count": 1,
                        "asset_id": "synthetic",
                        "geometry_variant": "nominal",
                        "copy_index": 1,
                        "installed_instance_id": "synthetic::copy1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = compare.compare_projects(source, saved, source_receipt=receipt)
    assert result["source_receipt"]["copies"][0]["installed_instance_id"] == "synthetic::copy1"
    args = ["--source", str(source), "--saved", str(saved), "--output", str(output)]
    assert compare.main(args) == 1
    original = source.read_bytes()
    assert compare.main(args[:-1] + [str(source)]) == 2
    assert source.read_bytes() == original
    saved.write_bytes(b"not a zip")
    assert compare.main(args[:-1] + [str(tmp_path / "invalid.json")]) == 2
    assert not (tmp_path / "invalid.json").exists()
