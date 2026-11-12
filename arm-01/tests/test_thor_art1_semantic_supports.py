"""Reference census and conservative matching guards; no native CAD is run."""

import copy
import hashlib
import importlib.util
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).parents[1] / "tools/probe_thor_art1_semantic_supports.py"
SPEC = importlib.util.spec_from_file_location("semantic_supports_tested", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EVIDENCE = Path(__file__).parents[1] / "hardware/cad/thor-art1-migration-evidence.json"


def sample(kind="circle", sub="Edge1"):
    result = {
        "subelement": sub,
        "kind": kind,
        "anchor_mm": [0.0, 0.0, 0.0],
        "orientation": "Forward",
        "trim": {
            "center_mm": [0, 0, 0],
            "bounds_mm": [-2, -2, 0, 2, 2, 0],
            "measure": 4 * 3.141592653589793,
            "vertex_count": 1,
            "edge_count": 1,
        },
        "adjacency": ["Plane"],
    }
    if kind != "sphere":
        result["axis"] = [0, 0, 1]
    if kind in {"circle", "cylinder", "sphere"}:
        result["radius_mm"] = 2.0
    if kind == "cone":
        result["semi_angle_rad"] = 0.4
    return result


def test_actual_committed_census_is_53_owners_80_references_69_subshapes():
    rows = MODULE.ledger(json.loads(EVIDENCE.read_text()))
    assert len(rows) == 80
    assert len({row["owner"] for row in rows}) == 53
    assert sum(row["geometric_reference"] for row in rows) == 69
    assert len({row["reference_id"] for row in rows}) == 80
    assert next(r for r in rows if r["owner"] == "Sketch005")["original_selector"] == "Edge13"


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "0" * 64),
        ("schema_version", True),
        ("source_revision", "main"),
        ("validation_class", "physical"),
    ],
)
def test_census_rejects_unsupported_source_contract(field, value):
    evidence = json.loads(EVIDENCE.read_text())
    evidence[field] = value
    with pytest.raises(ValueError):
        MODULE.ledger(evidence)


def test_census_rejects_missing_owner_duplicate_and_unsafe_selector():
    evidence = json.loads(EVIDENCE.read_text())
    missing = copy.deepcopy(evidence)
    missing["all_subshape_attachment_dependencies"].pop("Sketch")
    with pytest.raises(ValueError):
        MODULE.ledger(missing)
    for invalid in ("Face0", "../Face1", "Face1;anything", 1):
        changed = copy.deepcopy(evidence)
        changed["all_subshape_attachment_dependencies"]["Sketch001"][0]["links"][0]["sub"] = invalid
        with pytest.raises(ValueError):
            MODULE.ledger(changed)


@pytest.mark.parametrize("kind", sorted(MODULE.SUPPORTED))
def test_all_supported_primitives_can_match_only_the_unique_descriptor(kind):
    value = sample(kind, "Face1" if kind in {"plane", "cylinder", "cone", "sphere"} else "Edge1")
    matched = MODULE.match_reference(value, [copy.deepcopy(value)], value["subelement"])
    assert matched["status"] == "unique_descriptor_match"
    assert matched["selected"] == value["subelement"]
    assert matched["literal"]["strict_match"]
    assert not matched["support_remapped"]
    assert not matched["attachment_approved"]


def test_equal_supports_are_ambiguous_never_choose_nearest_or_first():
    value = sample()
    other = copy.deepcopy(value)
    other["subelement"] = "Edge42"
    result = MODULE.match_reference(value, [value, other], "Edge1")
    assert result["status"] == "ambiguous"
    assert result["selected"] is None
    assert result["strict_matches"] == ["Edge1", "Edge42"]


@pytest.mark.parametrize(
    "change",
    [
        "radius",
        "trim_center",
        "trim_bounds",
        "trim_area",
        "adjacency",
        "orientation",
        "axis_direction",
        "unknown_adjacency",
    ],
)
def test_type_and_radius_alone_do_not_establish_attachment_meaning(change):
    value, other = sample(), sample(sub="Edge99")
    if change == "radius":
        other["radius_mm"] += 1e-3
    elif change == "trim_center":
        other["trim"]["center_mm"][0] += 0.01
    elif change == "trim_bounds":
        other["trim"]["bounds_mm"][3] += 0.01
    elif change == "trim_area":
        other["trim"]["measure"] *= 1.01
    elif change == "adjacency":
        other["adjacency"] = ["Cylinder"]
    elif change == "orientation":
        other["orientation"] = "Reversed"
    elif change == "axis_direction":
        other["axis"] = [0, 0, -1]
    else:
        other["adjacency"] = None
    result = MODULE.match_reference(value, [other], "Edge1")
    assert result["status"] == "no_match"
    assert result["selected"] is None
    assert not result["literal_exists"]


def test_cylinder_axis_origin_can_move_along_axis_but_trim_must_match():
    first, second = sample("cylinder", "Face1"), sample("cylinder", "Face3")
    second["anchor_mm"] = [0, 0, 100]
    assert MODULE.comparison(first, second)["strict_match"]
    second["trim"]["center_mm"][2] = 100
    assert not MODULE.comparison(first, second)["strict_match"]


def test_plane_support_point_can_move_within_plane_but_trim_must_match():
    first, second = sample("plane", "Face1"), sample("plane", "Face4")
    second["anchor_mm"] = [100, -50, 0]
    assert MODULE.comparison(first, second)["strict_match"]
    second["anchor_mm"][2] = 0.01
    assert not MODULE.comparison(first, second)["strict_match"]


def test_unsupported_geometry_is_preserved_and_never_matches_bbox_only():
    value = {"subelement": "Face1", "kind": "unsupported", "native_type": "BSplineSurface"}
    result = MODULE.match_reference(value, [value], "Face1")
    assert result["status"] == "unsupported"
    assert result["selected"] is None


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), True, "2"])
def test_descriptor_rejects_nonfinite_or_non_numeric_radii(invalid):
    value = sample()
    value["radius_mm"] = invalid
    with pytest.raises(ValueError):
        MODULE.descriptor(value)


def test_duplicate_candidate_names_reject_even_when_geometry_differs():
    first, second = sample(), sample()
    second["radius_mm"] = 3
    with pytest.raises(ValueError, match="duplicate"):
        MODULE.match_reference(first, [first, second], "Edge1")


@pytest.mark.parametrize(
    "flag",
    [
        "RAFTEL_RUN_FREECAD_AUDIT",
        "RAFTEL_RUN_THOR_ART1_PROBE",
        "RAFTEL_PREPARE_THOR_ART1_CANDIDATE",
    ],
)
def test_conflicting_flag_rejects_before_native_import_or_paths(monkeypatch, flag):
    monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match="conflicting"):
        MODULE.native_capture()


def test_containment_precedes_request_read(monkeypatch, tmp_path):
    monkeypatch.setenv(MODULE.FLAG, "1")
    monkeypatch.setenv("RAFTEL_SEMANTIC_SUPPORT_ROOT", str(tmp_path))
    for flag in (
        "RAFTEL_RUN_FREECAD_AUDIT",
        "RAFTEL_RUN_THOR_ART1_PROBE",
        "RAFTEL_PREPARE_THOR_ART1_CANDIDATE",
    ):
        monkeypatch.delenv(flag, raising=False)

    def reject(root):
        raise ValueError("mock escaped path rejected")

    def unexpected(*args):
        pytest.fail("request read before containment check")

    monkeypatch.setattr(MODULE, "contained_input_paths", reject)
    monkeypatch.setattr(MODULE, "strict_json", unexpected)
    with pytest.raises(ValueError, match="mock escaped"):
        MODULE.native_capture()


def test_symlinked_request_outside_run_rejects_without_reading(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    try:
        (root / "request.json").symlink_to(outside)
    except OSError:
        pytest.skip("host does not permit test file symlinks")
    with pytest.raises(ValueError, match="escaped"):
        MODULE.contained_input_paths(root)


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', "[]"])
def test_strict_json_rejects_invalid_documents(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text)
    with pytest.raises(ValueError):
        MODULE.strict_json(path)


def test_source_xml_decoder_covers_both_native_link_representations():
    document = ET.fromstring(
        '<Document><ObjectData><Object name="A"><Properties>'
        '<Property name="Support"><LinkSubList count="1"><Link obj="Pad" sub="Face3"/>'
        '</LinkSubList></Property><Property name="MirrorPlane"><LinkSub value="Sketch" count="1">'
        '<Sub value="V_Axis"/></LinkSub></Property></Properties></Object></ObjectData></Document>'
    )
    assert MODULE.xml_reference_identities(document, ["A"]) == [
        ("A", "Support", "Pad", "Face3"),
        ("A", "MirrorPlane", "Sketch", "V_Axis"),
    ]
    document.find(".//LinkSubList").set("count", "2")
    with pytest.raises(ValueError, match="count"):
        MODULE.xml_reference_identities(document, ["A"])


def test_provider_placement_trace_reports_real_difference_and_rejects_nonfinite():
    first = MODULE.IDENTITY
    second = list(first)
    second[3] = 1.0
    assert MODULE.placement_error(first, first) == 0
    assert MODULE.placement_error(first, second) == 1
    second[3] = float("nan")
    with pytest.raises(ValueError):
        MODULE.placement_error(first, second)
    with pytest.raises(ValueError):
        MODULE.placement_error(first, first[:15])


def test_coherently_changed_evidence_cannot_substitute_another_source_face(tmp_path, monkeypatch):
    evidence = json.loads(EVIDENCE.read_text())
    root = ET.Element("Document")
    data = ET.SubElement(root, "ObjectData")
    body = ET.SubElement(data, "Object", name="Body")
    props = ET.SubElement(body, "Properties")
    group = ET.SubElement(ET.SubElement(props, "Property", name="Group"), "LinkList")
    for name in evidence["ordered_body_members"]:
        ET.SubElement(group, "Link", value=name)
        node = ET.SubElement(data, "Object", name=name)
        properties = ET.SubElement(node, "Properties")
        for prop in evidence["all_subshape_attachment_dependencies"].get(name, []):
            target = ET.SubElement(properties, "Property", name=prop["property"])
            links = prop["links"]
            if "obj" in links[0]:
                container = ET.SubElement(target, "LinkSubList", count=str(len(links)))
                for link in links:
                    ET.SubElement(container, "Link", **link)
            else:
                assert len(links) == 1
                link = links[0]
                container = ET.SubElement(
                    target, "LinkSub", value=link["value"], count=str(len(link["subelements"]))
                )
                for sub in link["subelements"]:
                    ET.SubElement(container, "Sub", value=sub)
    path = tmp_path / "source.fcstd"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Document.xml", ET.tostring(root))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(MODULE, "SOURCE_SHA256", digest)
    evidence["source_sha256"] = digest
    assert len(MODULE.authenticate_ledger(path, evidence)) == 80
    evidence["all_subshape_attachment_dependencies"]["Sketch001"][0]["links"][0]["sub"] = "Face4"
    with pytest.raises(ValueError, match="exact source XML"):
        MODULE.authenticate_ledger(path, evidence)


def test_public_reference_properties_keep_targets_subnames_and_order():
    target = SimpleNamespace(Name="Pocket")
    assert MODULE.current_property_entries([(target, ("Face7", "Edge13"))]) == [
        {"target": "Pocket", "selector": "Face7"},
        {"target": "Pocket", "selector": "Edge13"},
    ]
    assert MODULE.current_property_entries(("Pad", "Face3")) == [
        {"target": "Pad", "selector": "Face3"}
    ]
    for bad in (123, [("../Pad", "Face3")], [(target, 5)]):
        with pytest.raises(ValueError):
            MODULE.current_property_entries(bad)


def test_current_property_alias_requires_saved_xml_and_runtime_presence():
    assert MODULE.current_property_name("Support", {"Support"}, {"Support"}) == "Support"
    assert (
        MODULE.current_property_name("Support", {"AttachmentSupport"}, {"AttachmentSupport"})
        == "AttachmentSupport"
    )
    for original, saved, runtime in [
        ("Support", {"AttachmentSupport"}, {"Support"}),
        ("Support", {"Support", "AttachmentSupport"}, {"AttachmentSupport"}),
        ("ExternalGeometry", {"AttachmentSupport"}, {"AttachmentSupport"}),
        ("Support", set(), {"AttachmentSupport"}),
    ]:
        with pytest.raises(ValueError):
            MODULE.current_property_name(original, saved, runtime)


def test_public_getter_witness_can_differ_from_raw_index_without_approval(monkeypatch):
    class Face:
        ShapeType = "Face"
        Placement = SimpleNamespace(toMatrix=lambda: SimpleNamespace(A=MODULE.IDENTITY))

        def __init__(self, token, orientation="Forward"):
            self.token, self.orientation = token, orientation

        def isSame(self, other):
            return self.token == other.token

        def isEqual(self, other):
            return self.isSame(other) and self.orientation == other.orientation

    first, second = Face("one"), Face("two")
    raw = SimpleNamespace(Faces=[first, second], Edges=[], getElement=lambda selector: first)
    obj = SimpleNamespace(Shape=raw, getSubObject=lambda selector: Face("two", "Reversed"))
    monkeypatch.setattr(MODULE, "native_descriptors", lambda shape: [sample("plane", "Face1")])
    observed = MODULE.observe_native_getter(obj, "Face1", sample("plane", "Face1"))
    assert observed["status"] == "observed_public_getter"
    assert observed["raw_provider_isSame_indices"] == ["Face2"]
    assert observed["raw_provider_isEqual_indices"] == []
    assert not observed["attachment_engine_resolution_proven"]
    literal = MODULE.observe_native_getter(obj, "Face1", None, shape_getter=True)
    assert literal["raw_provider_isEqual_indices"] == ["Face1"]


def test_native_getter_none_unknown_and_exception_remain_unresolved():
    for value, status in [
        (None, "returned_none"),
        (("not", "a shape"), "unsupported_getter_result"),
    ]:
        obj = SimpleNamespace(Shape=object(), getSubObject=lambda selector, value=value: value)
        assert MODULE.observe_native_getter(obj, "Face1", None)["status"] == status

    def fail(selector):
        raise RuntimeError("unknown persistent name")

    obj = SimpleNamespace(Shape=object(), getSubObject=fail)
    result = MODULE.observe_native_getter(obj, "Face1", None)
    assert result["status"] == "getter_unresolved"
    assert result["error_type"] == "RuntimeError"
    assert not result["attachment_engine_resolution_proven"]


def test_published_native_census_keeps_unresolved_scopes_and_no_remaps():
    path = Path(__file__).parents[1] / "hardware/cad/thor-art1-semantic-supports-v1.json"
    report = json.loads(path.read_text())
    assert report["status"] == "complete_descriptor_diagnostic_not_migration"
    assert report["census"] == {
        "owner_objects": 53,
        "references": 80,
        "face_edge_references": 69,
        "whole_datum_or_axis_references": 11,
        "providers": 19,
    }
    assert report["result_counts"] == {
        "unsupported_whole_datum_or_sketch_axis": 11,
        "unique_descriptor_match": 62,
        "no_match": 6,
        "unsupported": 1,
    }
    assert report["source_copy_unchanged"] and report["candidate_copy_unchanged"]
    assert report["open_document_count_after"] == 0
    assert not report["recompute_requested"] and not report["document_saved"]
    assert not report["migration_accepted"] and not report["attachment_approved"]
    assert report["derived_counts"]["different_raw_index_candidates"] == 21
    for row in report["references"]:
        assert not row["attachment_approved"]
        assert not row["native_mapped_reference_resolution_inspected"]
        if row["status"] == "unique_descriptor_match":
            assert MODULE.comparison(
                row["source_descriptor"], row["selected_candidate_descriptor"]
            )["strict_match"]
    assert all(p["provider_coordinate_trace_verified"] for p in report["providers"].values())


def test_public_getter_receipt_preserves_original_audit_and_attachment_unknowns():
    folder = Path(__file__).parents[1] / "hardware/cad"
    original_path = folder / "thor-art1-semantic-supports-v1.json"
    assert hashlib.sha256(original_path.read_bytes()).hexdigest() == (
        "778d7e4d84fdaa903f481a0d68f698c72ce96e549334372dae1e328cf7e61c3e"
    )
    original = json.loads(original_path.read_text())
    report = json.loads((folder / "thor-art1-semantic-supports-getters-v1.json").read_text())
    assert report["census"] == original["census"]
    assert report["result_counts"] == original["result_counts"]
    assert report["fixture"]["passed"]
    assert len(report["fixture"]["cases"]) == 5
    assert not report["recompute_requested"] and not report["document_saved"]
    assert report["open_document_count_after"] == 0
    assert not report["migration_accepted"] and not report["attachment_approved"]
    assert len(report["references"]) == 80
    observed_properties = []
    for initial, row in zip(original["references"], report["references"], strict=True):
        # Initial diagnostic facts survive; the old explicitly uninspected getter
        # field and wording are intentionally not propagated as current evidence.
        for key, value in initial.items():
            if key not in (
                "native_mapped_reference_resolution_inspected",
                "literal_index_interpretation",
            ):
                assert row[key] == value
        assert not row["attachment_engine_resolution_proven"]
        if not row["geometric_reference"]:
            assert "public_getter_observations" not in row
            continue
        for getter in row["public_getter_observations"].values():
            assert getter["status"] == "observed_public_getter"
            assert not getter["attachment_engine_resolution_proven"]
            assert getter["raw_provider_isEqual_indices"] == [row["original_selector"]]
        observation = row["current_owner_property_observation"]
        observed_properties.append(observation["status"])
        if observation["status"] == "observed_public_property":
            assert observation["ordinal_is_not_semantic_correspondence_proof"]
    assert observed_properties.count("observed_public_property") == 19
    assert observed_properties.count("unsupported_public_property") == 50
    datum = next(row for row in report["references"] if row["owner"] == "DatumPlane001")
    assert datum["selected"] == "Face6"
    assert datum["original_selector"] == "Face7"
    assert datum["current_owner_property_observation"]["status"] == "unsupported_public_property"


def test_typed_current_property_receipt_distinguishes_schema_from_attachment_execution():
    folder = Path(__file__).parents[1] / "hardware/cad"
    report = json.loads((folder / "thor-art1-semantic-supports-typed-getters-v1.json").read_text())
    assert report["all_candidate_runtime_types_match_saved_xml"]
    inventory = report["candidate_runtime_type_inventory"]
    assert len(inventory) == len({entry["name"] for entry in inventory}) == 90
    assert all(entry["runtime_type_id"] == entry["saved_type_id"] for entry in inventory)
    assert not report["recompute_requested"] and not report["document_saved"]
    assert not report["migration_accepted"] and not report["attachment_approved"]
    assert report["open_document_count_after"] == 0
    geometric = [row for row in report["references"] if row["geometric_reference"]]
    assert len(geometric) == 69
    names = []
    for row in geometric:
        assert not row["attachment_engine_resolution_proven"]
        observation = row["current_owner_property_observation"]
        assert observation["status"] == "observed_public_property"
        assert observation["runtime_owner_type_id"] == observation["saved_owner_type_id"]
        assert observation["ordinal_is_not_semantic_correspondence_proof"]
        assert observation["schema_alias_is_not_attachment_engine_proof"]
        names.append(observation["current_property_name"])
        getter = observation["same_ordinal_target_getter"]
        assert getter["status"] == "observed_public_getter"
        assert not getter["attachment_engine_resolution_proven"]
        if row["status"] == "unique_descriptor_match":
            assert getter["raw_provider_isEqual_indices"] == [row["selected"]]
    assert names.count("AttachmentSupport") == 50
    assert names.count("ExternalGeometry") == 19
    datum = next(row for row in geometric if row["owner"] == "DatumPlane001")
    assert datum["current_owner_property_observation"]["same_ordinal_entry"] == {
        "target": "Pocket",
        "selector": "Face6",
    }
    assert (
        datum["current_owner_property_observation"]["runtime_owner_type_id"] == "PartDesign::Plane"
    )
