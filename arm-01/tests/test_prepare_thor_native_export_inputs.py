"""Saved archive descriptors preserve pins/frames without native execution."""

import copy
import hashlib
import importlib.util
import json
import sys
import warnings
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
for name in ("thor_art1_diagnostics", "prepare_thor_native_export_inputs"):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
prep = sys.modules["prepare_thor_native_export_inputs"]


def native_fixture(path, *, mirror=False, empty=False, duplicate_entry=False, missing_source=False):
    object_name = "Mirror" if mirror else "Body"
    object_type = "Part::Mirroring" if mirror else "PartDesign::Body"
    placement = (
        '<Property name="Placement"><PropertyPlacement Px="10" Py="20" Pz="30" '
        'Q0="0" Q1="0" Q2="0" Q3="1"/></Property>'
    )
    source = (
        '<Property name="Source"><Link value="SourceLink"/></Property>'
        if mirror
        else '<Property name="Tip"><Link value="Pocket"/></Property>'
    )
    definitions = (
        f'<Object name="{object_name}" type="{object_type}"/>'
        '<Object name="Container" type="App::Part"/>'
    )
    linked = ""
    if mirror and not missing_source:
        definitions += '<Object name="SourceLink" type="App::Link"/>'
        linked = (
            '<Object name="SourceLink"><Properties><Property name="LinkedObject">'
            '<XLink file="GripperFinger.FCStd" value="Body"/></Property></Properties></Object>'
        )
    obj = (
        f'<Object name="{object_name}"><Properties>{placement}{source}'
        '<Property name="Shape"><Part file="SelectedShape.brp"/></Property></Properties></Object>'
    )
    parent = (
        f'<Object name="Container"><Properties>{placement}<Property name="Group">'
        f'<LinkList><Link value="{object_name}"/></LinkList></Property></Properties></Object>'
    )
    xml = (
        f"<Document><Objects>{definitions}</Objects>"
        f"<ObjectData>{obj}{parent}{linked}</ObjectData></Document>"
    ).encode()
    brep = b"" if empty else b"Synthetic opaque BRep-entry fixture; no native validity is claimed"
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Document.xml", xml)
        archive.writestr("OtherShape.brp", b"wrong entry must not be selected")
        archive.writestr("SelectedShape.brp", brep)
        if duplicate_entry:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr("SelectedShape.brp", brep)
    return hashlib.sha256(path.read_bytes()).hexdigest(), hashlib.sha256(brep).hexdigest()


@pytest.fixture
def request_inputs(tmp_path, monkeypatch):
    root = tmp_path / "sources"
    body = "freecad-src/BaseTop.fcstd"
    mirror = "freecad-src/AssemblyArt56.FCStd"
    body_hash, body_brep = native_fixture(root / body)
    mirror_hash, mirror_brep = native_fixture(root / mirror, mirror=True)
    targets = (
        ("base-top", "BaseTop::Body", body, "Body"),
        ("finger-reflected", "AssemblyArt56::Mirror", mirror, "Mirror"),
    )
    monkeypatch.setattr(prep, "TARGETS", targets)
    manifest = {
        "source_revision": prep.SOURCE_REVISION,
        "assets": [
            {
                "asset_id": "BaseTop::Body",
                "source_file": body,
                "source_sha256": body_hash,
                "source_geometry_frame": "Synthetic raw source Shape coordinates, mm",
                "source_bounds_mm": {
                    "XMin": 0,
                    "XMax": 1,
                    "YMin": 0,
                    "YMax": 2,
                    "ZMin": 0,
                    "ZMax": 3,
                },
                "source_volume_mm3": 42.0,
            }
        ],
    }
    inspection = {
        "revision": prep.SOURCE_REVISION,
        "files": [
            {"path": "BaseTop.fcstd", "sha256": body_hash},
            {"path": "AssemblyArt56.FCStd", "sha256": mirror_hash},
        ],
    }
    inventory = {
        "native_source_revision": prep.SOURCE_REVISION,
        "coordinate_frame": "Synthetic installed/world frame, metres",
        "mounted_bodies": [
            {
                "instance_id": "fixture/body",
                "linked_object": "BaseTop::Body",
                "volume_mm3": 42.0,
                "zero_world_com_m": [0.4, 0.5, 0.6],
            },
            {
                "instance_id": "fixture/mirror",
                "linked_object": "AssemblyArt56::Mirror",
                "volume_mm3": 37.0,
                "zero_world_com_m": [-0.4, 0.5, 0.6],
            },
        ],
    }
    slicer = {
        "source_revision": prep.SOURCE_REVISION,
        "mesh_audit": [
            {
                "installed_asset_id": "BaseTop::Body",
                "source_path": "stl/BaseTop.stl",
                "sha256": "1" * 64,
                "git_blob_sha1": "2" * 40,
                "comparison": {"scope": "synthetic source reference only"},
            }
        ],
    }
    return manifest, inspection, inventory, slicer, root, body_brep, mirror_brep


def test_exact_shape_entry_and_xml_placement_are_described_not_applied(request_inputs):
    manifest, inspection, inventory, slicer, root, body_brep, mirror_brep = request_inputs
    request = prep.build_request(manifest, inspection, inventory, slicer, root)
    assert set(request) == {"schema_version", "source_revision", "evidence_class", "selections"}
    assert len(request["selections"]) == 2
    body, mirror = request["selections"]
    assert body["brep_entry"] == "SelectedShape.brp"
    assert body["brep_sha256"] == body_brep and mirror["brep_sha256"] == mirror_brep
    assert body["xml_placement"] == {"position_mm": [10, 20, 30], "quaternion_xyzw": [0, 0, 0, 1]}
    capture = body["reference_capture"]
    assert capture["preserved_raw_source_shape_reference"]["center_of_mass_mm"] is None
    assert capture["preserved_installed_references"][0]["zero_world_com_m"] == [0.4, 0.5, 0.6]
    assert capture["preserved_installed_references"][0]["source_to_installed_transform"] is None
    assert capture["frame_invariant_volume_reference_mm3"] == 42
    assert mirror["reference_capture"]["preserved_raw_source_shape_reference"] is None
    assert mirror["reference_capture"]["frame_invariant_volume_reference_mm3"] == 37
    assert mirror["upstream_stl_reference"] is None
    assert mirror["object_type"] == "Part::Mirroring"
    assert (
        mirror["reference_capture"]["saved_xml_context"]["saved_Source_link_context"][0]["name"]
        == "SourceLink"
    )
    assert all(row["uniform_density"] is None for row in request["selections"])
    assert body["tessellation"] == {
        "linear_deflection_mm": 0.1,
        "angular_deflection_rad": 0.2,
        "relative": False,
        "filename": "base-top-cached-native-draft.stl",
    }


def test_wrong_archive_pin_missing_shape_or_duplicate_zip_reject(tmp_path):
    path = tmp_path / "freecad-src/BaseTop.fcstd"
    digest, _ = native_fixture(path)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        prep.inspect_selection(tmp_path, "freecad-src/BaseTop.fcstd", "0" * 64, "Body")
    with pytest.raises(ValueError, match="missing or duplicated"):
        prep.inspect_selection(tmp_path, "freecad-src/BaseTop.fcstd", digest, "MissingBody")
    digest, _ = native_fixture(path, empty=True)
    with pytest.raises(ValueError, match="empty"):
        prep.inspect_selection(tmp_path, "freecad-src/BaseTop.fcstd", digest, "Body")
    digest, _ = native_fixture(path, duplicate_entry=True)
    with pytest.raises(ValueError, match="duplicate ZIP"):
        prep.inspect_selection(tmp_path, "freecad-src/BaseTop.fcstd", digest, "Body")


def test_missing_mirror_source_is_not_silently_reconstructed(tmp_path):
    path = tmp_path / "freecad-src/AssemblyArt56.FCStd"
    digest, _ = native_fixture(path, mirror=True, missing_source=True)
    with pytest.raises(ValueError, match="Source object is missing"):
        prep.inspect_selection(tmp_path, "freecad-src/AssemblyArt56.FCStd", digest, "Mirror")


def test_revision_asset_pin_and_missing_installed_counterpart_reject(request_inputs):
    manifest, inspection, inventory, slicer, root, *_ = request_inputs
    bad = copy.deepcopy(manifest)
    bad["source_revision"] = "0" * 40
    with pytest.raises(ValueError, match="revisions"):
        prep.build_request(bad, inspection, inventory, slicer, root)
    bad = copy.deepcopy(manifest)
    bad["assets"][0]["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="pins disagree"):
        prep.build_request(bad, inspection, inventory, slicer, root)
    bad = copy.deepcopy(inventory)
    bad["mounted_bodies"] = bad["mounted_bodies"][1:]
    with pytest.raises(ValueError, match="no preserved installed counterpart"):
        prep.build_request(manifest, inspection, bad, slicer, root)


@pytest.mark.parametrize(
    "source",
    [
        "../outside.fcstd",
        "freecad-src/../outside.fcstd",
        "C:/source.fcstd",
        "freecad-src\\source.fcstd",
        "/source.fcstd",
    ],
)
def test_source_path_traversal_reject(source):
    with pytest.raises(ValueError):
        prep._safe_path(source)


def test_cli_new_lf_output_without_source_mutation_or_overwrite(request_inputs, tmp_path):
    manifest, inspection, inventory, slicer, root, *_ = request_inputs
    inputs = []
    for name, data in [
        ("manifest", manifest),
        ("inspection", inspection),
        ("inventory", inventory),
        ("slicer", slicer),
    ]:
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
        inputs.append(path)
    before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*.fcstd")}
    # Include the mixed-case assembly extension too.
    before.update(
        {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*.FCStd")}
    )
    output = tmp_path / "request.json"
    args = [
        "--source-root",
        str(root),
        "--manifest",
        str(inputs[0]),
        "--source-inspection",
        str(inputs[1]),
        "--inventory",
        str(inputs[2]),
        "--slicer-plan",
        str(inputs[3]),
        "--output",
        str(output),
    ]
    assert prep.main(args) == 0
    saved = output.read_bytes()
    assert b"\r\n" not in saved
    assert prep.main(args) == 2
    assert output.read_bytes() == saved
    assert all((root / name).read_bytes() == contents for name, contents in before.items())
