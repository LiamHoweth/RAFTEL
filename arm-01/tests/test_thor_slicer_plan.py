"""STL topology and draft quantity checks, without native/export/print claims."""

import copy
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "thor_slicer_plan", ROOT / "tools/thor_slicer_plan.py"
)
plan = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = plan
SPEC.loader.exec_module(plan)

POINTS = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
FACES = ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))


def binary_stl(points=POINTS, faces=FACES, header=b"source-fixture", normal=(0.0, 0.0, 0.0)):
    return (
        header.ljust(80, b" ")
        + struct.pack("<I", len(faces))
        + b"".join(
            struct.pack(
                "<12fH", *normal, *(coordinate for index in face for coordinate in points[index]), 0
            )
            for face in faces
        )
    )


def ascii_stl():
    rows = ["solid fixture"]
    for face in FACES:
        rows.extend(["facet normal 0 0 0", "outer loop"])
        rows.extend("vertex " + " ".join(map(str, POINTS[index])) for index in face)
        rows.extend(["endloop", "endfacet"])
    rows.append("endsolid fixture")
    return ("\n".join(rows) + "\n").encode()


def test_binary_and_ascii_tetrahedron_independent_volume_bounds_and_manifold():
    for contents in (binary_stl(), ascii_stl(), binary_stl(header=b"solid binary-looking-ascii")):
        report = plan.analyze_stl(contents)
        assert report["triangle_count"] == 4
        assert report["exact_vertex_count"] == 4
        assert report["bounds_interpreted_mm"] == {"min": (0, 0, 0), "max": (1, 1, 1)}
        assert report["absolute_signed_volume_interpreted_mm3"] == pytest.approx(1 / 6)
        assert report["surface_area_interpreted_mm2"] == pytest.approx(1.5 + 3**0.5 / 2)
        assert report["topology"]["closed_consistently_oriented_two_manifold"]
        assert report["self_intersections"] == "not_checked"


def test_unit_scale_and_translated_volume_covariance():
    points = tuple(
        tuple(10 * x + offset for x, offset in zip(point, (1e6, -2e6, 3e6), strict=True))
        for point in POINTS
    )
    report = plan.analyze_stl(binary_stl(points))
    assert report["envelope_xyz_interpreted_mm"] == (10, 10, 10)
    assert report["absolute_signed_volume_interpreted_mm3"] == pytest.approx(1000 / 6)


def test_open_duplicate_reversed_and_degenerate_mesh_failures():
    cases = [
        (FACES[:-1], "boundary_edges", 3),
        ((*FACES, FACES[0]), "duplicate_facets", 1),
        ((tuple(reversed(FACES[0])), *FACES[1:]), "inconsistent_winding_edges", 3),
        (((0, 0, 1),), "zero_area_facets", 1),
    ]
    for faces, field, expected in cases:
        report = plan.analyze_stl(binary_stl(faces=faces))
        assert report["topology"][field] == expected
        assert not report["topology"]["closed_consistently_oriented_two_manifold"]


def test_vertex_link_catches_two_shells_touching_at_one_vertex():
    points = POINTS + ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))
    other = ((0, 5, 4), (0, 4, 6), (0, 6, 5), (4, 5, 6))
    report = plan.analyze_stl(binary_stl(points, FACES + other))
    assert report["topology"]["boundary_edges"] == 0
    assert report["topology"]["nonmanifold_edges"] == 0
    assert report["topology"]["nonmanifold_vertices"] == 1
    assert not report["topology"]["closed_consistently_oriented_two_manifold"]


@pytest.mark.parametrize(
    "contents",
    [
        b"",
        binary_stl()[:-1],
        binary_stl() + b"x",
        b"solid empty\nendsolid empty\n",
        b"solid a\nfacet normal 0 0 0\nendsolid a\n",
        ascii_stl().replace(b"vertex 0.0", b"vertex nan", 1),
        binary_stl(points=((*POINTS[0][:2], float("inf")), *POINTS[1:])),
    ],
)
def test_malformed_nonfinite_and_truncated_stl_reject(contents):
    with pytest.raises(ValueError):
        plan.analyze_stl(contents)


@pytest.fixture
def source_fixture(tmp_path, monkeypatch):
    # Small synthetic STL bytes exercise planning against real ledger identities.
    # This does not claim fixture meshes match Thor geometry or the real pin.
    manifest = json.loads((ROOT / "hardware/cad/thor-printable-assets-v1.json").read_bytes())
    rows = []
    for asset in manifest["assets"]:
        name = Path(asset["source_file"]).stem
        path = f"stl/{name}.stl"
        contents = binary_stl()
        destination = tmp_path / path
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(contents)
        rows.append(
            {
                "path": path,
                "type": "blob",
                "size": len(contents),
                "sha": hashlib.sha1(
                    b"blob " + str(len(contents)).encode() + b"\0" + contents
                ).hexdigest(),
            }
        )
    contents = b"Synthetic source license fixture, not upstream license text"
    (tmp_path / "LICENSE").write_bytes(contents)
    rows.append(
        {
            "path": "LICENSE",
            "type": "blob",
            "size": len(contents),
            "sha": hashlib.sha1(
                b"blob " + str(len(contents)).encode() + b"\0" + contents
            ).hexdigest(),
        }
    )
    tree = {
        "sha": plan.SOURCE_REVISION,
        "url": f"https://api.github.com/repos/AngelLM/Thor/git/trees/{plan.SOURCE_REVISION}",
        "truncated": False,
        "tree": rows,
    }
    monkeypatch.setattr(plan, "PINNED_TREE_CANONICAL_SHA256", plan.canonical_sha256(tree))
    return manifest, tree, tmp_path


def test_draft_ledger_quantity_reflection_and_no_process_assumptions(source_fixture):
    manifest, tree, directory = source_fixture
    report = plan.build_plan(manifest, tree, directory)
    assert report["counts"]["nominal_plate_instances"] == 64
    assert report["counts"]["blocked_plate_instances"] == 1
    assert len(report["draft_plate_groups"]) == 47
    reflected = [
        plate for plate in report["draft_plate_groups"] if plate["geometry_variant"] == "reflected"
    ]
    assert len(reflected) == 1
    assert reflected[0]["source_mesh_path"] is None
    assert reflected[0]["stage"] == "blocked_missing_reflected_native_export"
    assert all(
        plate["material"] is None
        and plate["orientation"] is None
        and plate["machine_profile"] is None
        for plate in report["draft_plate_groups"]
    )
    assert not any(report["qualification"].values())
    assert "CC-BY-SA-4.0" == report["attribution"]["declared_repository_license"]


def test_source_pin_changed_blob_and_tree_mutation_reject(source_fixture):
    manifest, tree, directory = source_fixture
    stale = copy.deepcopy(tree)
    stale["sha"] = "0" * 40
    with pytest.raises(ValueError, match="complete pinned"):
        plan.build_plan(manifest, stale, directory)
    stale = copy.deepcopy(tree)
    stale["tree"][0]["sha"] = "0" * 40
    with pytest.raises(ValueError, match="complete pinned"):
        plan.build_plan(manifest, stale, directory)
    (directory / tree["tree"][0]["path"]).write_bytes(binary_stl() + b"changed")
    with pytest.raises(ValueError, match="blob mismatch"):
        plan.build_plan(manifest, tree, directory)


def test_manifest_variant_and_quantity_contradictions_reject(source_fixture):
    manifest, tree, directory = source_fixture
    for mutate in (
        lambda data: data["counts"].update(reflected_installed_leaves=True),
        lambda data: data["assets"][0]["export_variants"][0].update(quantity=True),
        lambda data: data["assets"][0].update(quantity=2),
    ):
        bad = copy.deepcopy(manifest)
        mutate(bad)
        with pytest.raises(ValueError):
            plan.build_plan(bad, tree, directory)


@pytest.mark.parametrize(
    "path",
    [
        "../outside.stl",
        "stl/../outside.stl",
        "C:/part.stl",
        "stl\\part.stl",
        "/part.stl",
        "stl//part.stl",
    ],
)
def test_source_paths_reject_traversal_or_platform_ambiguity(path):
    with pytest.raises(ValueError):
        plan._safe_source_path(path)


def test_cli_negative_pin_and_preserved_output(source_fixture, tmp_path):
    manifest, tree, directory = source_fixture
    manifest_path = tmp_path / "manifest.json"
    tree_path = tmp_path / "tree.json"
    output = tmp_path / "output.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")
    tree_path.write_text(json.dumps(tree), encoding="utf-8", newline="\n")
    args = [
        "--manifest",
        str(manifest_path),
        "--tree",
        str(tree_path),
        "--upstream-root",
        str(directory),
        "--output",
        str(output),
    ]
    assert plan.main(args) == 0
    original = output.read_bytes()
    assert b"\r\n" not in original
    assert plan.main(args) == 2
    assert output.read_bytes() == original


def test_installed_profile_is_saved_scenario_with_independent_exclusion_reconciliation():
    audit = json.loads((ROOT / "hardware/print-planning/local-profile-audit.json").read_bytes())
    profile = plan.installed_profile_scenario(audit)
    assert profile["candidate_inner_rectangle_mm"] == [[3, 0], [423, 420]]
    assert profile["conservative_height_mm"] == 500
    assert profile["physical_confirmation"]["installed_nozzle_mm"] is None
    mesh = plan.analyze_stl(binary_stl())
    placement = plan.centered_draft_placement(mesh, profile)
    assert placement["translation_mm"] == [212.5, 209.5, 0]
    assert placement["aabb_fit_in_provisional_inner_rectangle"]
    assert not placement["stable_contact_face_or_layer_strength_verified"]


@pytest.mark.parametrize(
    "change", ["machine_hash", "inner_rectangle", "raw_outline", "physical_claim"]
)
def test_stale_or_contradictory_profile_evidence_rejects(change):
    audit = json.loads((ROOT / "hardware/print-planning/local-profile-audit.json").read_bytes())
    if change == "machine_hash":
        audit["profiles"]["machine"]["inheritance_chain_leaf_first"][0]["sha256"] = "0" * 64
    elif change == "inner_rectangle":
        audit["profile_numeric_interpretation"]["candidate_exclusion_interpretation"][
            "candidate_inner_rectangle_mm"
        ] = [[0, 0], [426, 420]]
    elif change == "raw_outline":
        audit["profiles"]["machine"]["resolved_allowlisted_fields"]["printable_area"][1] = "500x0"
    else:
        audit["saved_selection"]["is_physical_hardware_confirmation"] = True
    with pytest.raises(ValueError):
        plan.installed_profile_scenario(audit)
