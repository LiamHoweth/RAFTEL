"""Full installed registry reconciliation; no FreeCAD runtime is imported."""

import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "tools"))
full = importlib.import_module("prepare_thor_full_print_exports")


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@pytest.fixture
def inputs():
    return (
        load("hardware/cad/thor-printable-assets-v1.json"),
        load("hardware/cad/thor-baseline-inspection.json"),
        load("hardware/cad/thor-mounted-geometry-v2.json"),
    )


@pytest.fixture
def export_request():
    return load("hardware/print-planning/thor-full-print-export-inputs-v1.json")


def test_complete_original_registry_has_exact_variant_and_instance_ownership(inputs):
    manifest, inspection, inventory = inputs
    rows = full.registry_rows(manifest, inventory, full.source_files(inspection))
    assert len(rows) == 47 and sum(r["quantity_required"] for r in rows) == 65
    assert len({r["asset_id"] for r in rows}) == 46
    members = [m["instance_id"] for r in rows for m in r["members"]]
    assert len(members) == len(set(members)) == 65
    mirrored = [r for r in rows if r["geometry_variant"] == "reflected"]
    assert len(mirrored) == 1
    assert mirrored[0]["source_file"] == "freecad-src/AssemblyArt56.FCStd"
    assert mirrored[0]["object_name"] == "Unnamed1_GripperFinger_mirrored"
    assert mirrored[0]["quantity_required"] == 1
    art1 = next(r for r in rows if r["asset_id"] == "Art1Body::Body")
    assert art1["source_sha256"] == full.ART1_SHA256


@pytest.mark.parametrize("version", [True, 2, None])
def test_unsupported_or_boolean_manifest_and_inspection_schemas_reject(inputs, version):
    manifest, inspection, inventory = inputs
    files = full.source_files(inspection)
    manifest["schema_version"] = version
    with pytest.raises(ValueError, match="manifest schema"):
        full.registry_rows(manifest, inventory, files)
    inspection["schema_version"] = version
    with pytest.raises(ValueError, match="inspection schema"):
        full.source_files(inspection)


@pytest.mark.parametrize(
    "fault",
    [
        "quantity_bool",
        "quantity_mismatch",
        "unknown_variant",
        "duplicate_asset",
        "duplicate_instance",
        "wrong_source_pin",
        "missing_instance",
        "wrong_nominal_reference",
        "wrong_mirror_reference",
        "wrong_com",
        "wrong_inventory_pin",
    ],
)
def test_registry_corruption_rejects(inputs, fault):
    manifest, inspection, inventory = inputs
    asset = manifest["assets"][0]
    member = asset["instances"][0]
    if fault == "quantity_bool":
        asset["quantity"] = True
    elif fault == "quantity_mismatch":
        asset["export_variants"][0]["quantity"] += 1
    elif fault == "unknown_variant":
        asset["export_variants"][0]["variant_id"] = "guessed_reflection"
    elif fault == "duplicate_asset":
        manifest["assets"][-1] = copy.deepcopy(asset)
    elif fault == "duplicate_instance":
        manifest["assets"][1]["instances"][0]["instance_id"] = member["instance_id"]
    elif fault == "wrong_source_pin":
        asset["source_sha256"] = "0" * 64
    elif fault == "missing_instance":
        asset["instances"] = []
    elif fault == "wrong_nominal_reference":
        member["linked_object"] = "GripperFinger::Body"
    elif fault == "wrong_mirror_reference":
        finger = next(a for a in manifest["assets"] if a["asset_id"] == "GripperFinger::Body")
        next(m for m in finger["instances"] if m["variant_id"] == "reflected")["linked_object"] = (
            "GripperFinger::Body"
        )
    elif fault == "wrong_com":
        member["zero_world_com_m"][0] += 0.01
    else:
        manifest["input_canonical_sha256"]["inventory"] = "0" * 64
    with pytest.raises(ValueError):
        full.registry_rows(manifest, inventory, full.source_files(inspection))


def test_candidate_cannot_replace_Art1_even_if_supplied_metadata_pins_agree(inputs):
    manifest, inspection, inventory = inputs
    asset = next(a for a in manifest["assets"] if a["asset_id"] == "Art1Body::Body")
    asset["source_sha256"] = "6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd"
    source = next(s for s in inspection["files"] if s["path"].endswith("/Art1Body.fcstd"))
    source["sha256"] = asset["source_sha256"]
    with pytest.raises(ValueError, match="original pinned"):
        full.registry_rows(manifest, inventory, full.source_files(inspection))


def test_boolean_count_and_changed_original_archive_reject(inputs, tmp_path):
    manifest, inspection, inventory = inputs
    manifest["counts"]["reflected_installed_leaves"] = True
    with pytest.raises(ValueError, match="full 46"):
        full.registry_rows(manifest, inventory, full.source_files(inspection))
    path = tmp_path / "freecad-src/Test.fcstd"
    path.parent.mkdir()
    path.write_bytes(b"original opaque archive")
    expected = full.selected._sha(path.read_bytes())
    rows = {"test": dict(source_file="freecad-src/Test.fcstd", sha256=expected)}
    assert full.verify_archives(tmp_path, rows) == {"freecad-src/Test.fcstd": expected}
    path.write_bytes(b"changed original")
    with pytest.raises(ValueError, match="differs"):
        full.verify_archives(tmp_path, rows)
    assert path.read_bytes() == b"changed original"


@pytest.mark.parametrize("fault", ["count", "duplicate", "traversal", "revision"])
def test_incomplete_or_ambiguous_archive_set_rejects(inputs, fault):
    _, inspection, _ = inputs
    if fault == "count":
        inspection["files"].pop()
    elif fault == "duplicate":
        inspection["files"][-1] = copy.deepcopy(inspection["files"][0])
    elif fault == "traversal":
        inspection["files"][0]["path"] = "../outside.fcstd"
    else:
        inspection["revision"] = "0" * 40
    with pytest.raises(ValueError):
        full.source_files(inspection)


def test_raw_descriptor_builder_reuses_inspector_and_verifies_archive_set_twice(
    inputs, export_request, tmp_path, monkeypatch
):
    manifest, inspection, inventory = inputs
    by_identity = {(r["source_file"], r["object_name"]): r for r in export_request["selections"]}
    called = []
    verified = []

    def inspect(root, source, archive_sha, name):
        called.append((source, name))
        captured = by_identity[(source, name)]
        assert archive_sha == captured["source_sha256"]
        reference = captured["reference_capture"]
        # Opaque retained descriptor fixture. This does not exercise ZIP/native I/O.
        return dict(
            object_type=captured["object_type"],
            brep_entry=captured["brep_entry"],
            brep_sha256=captured["brep_sha256"],
            brep_bytes=reference["archive_shape_entry_bytes"],
            source_archive_bytes=reference["archive_bytes"],
            xml_placement=captured["xml_placement"],
            raw_xml_placement_attributes=reference["raw_xml_placement_attributes"],
            document_xml_sha256=reference["document_xml_sha256"],
            saved_context=reference["saved_xml_context"],
        )

    def verify(root, files):
        verified.append(len(files))
        return {r["source_file"]: r["sha256"] for r in files.values()}

    monkeypatch.setattr(full.selected, "inspect_selection", inspect)
    monkeypatch.setattr(full, "verify_archives", verify)
    generated = full.build_request(manifest, inspection, inventory, tmp_path)
    assert generated == export_request
    assert len(called) == 47 and len(set(called)) == 47 and verified == [57, 57]


def test_separate_batches_preserve_all_registry_bytes_and_respect_frozen_worker_limit(
    export_request, monkeypatch
):
    monkeypatch.delenv("RAFTEL_RUN_THOR_SOLID_PROPERTIES", raising=False)
    worker = importlib.import_module("probe_thor_solid_properties_freecad")
    assert worker.MAX_SELECTIONS == 8
    with pytest.raises(ValueError, match="1..8"):
        worker.validate_request(export_request)
    batches = full.worker_batches(export_request)
    assert [len(b["selections"]) for b in batches] == [8, 8, 8, 8, 8, 7]
    assert [r for b in batches for r in b["selections"]] == export_request["selections"]
    for batch in batches:
        worker.validate_request(batch)
    batches[0]["selections"][0]["reference_capture"]["quantity_required"] = 999
    assert export_request["selections"][0]["reference_capture"]["quantity_required"] != 999


def test_duplicate_across_batches_cannot_hide_in_global_registry(export_request):
    export_request["selections"][-1] = copy.deepcopy(export_request["selections"][0])
    with pytest.raises(ValueError, match="complete 47"):
        full.worker_batches(export_request)


def test_request_retains_unknown_frames_and_no_release_or_density(export_request):
    for row in export_request["selections"]:
        context = row["reference_capture"]
        assert row["uniform_density"] is None
        assert row["upstream_stl_reference"] is None
        assert all(v is False for v in context["qualification"].values())
        assert context["original_archive_count_verified"] == 57
        assert (
            full.canonical_sha256(context["saved_xml_context"])
            == context["saved_xml_context_canonical_sha256"]
        )
        assert all(
            m["source_to_installed_transform"] is None for m in context["installed_instances"]
        )


def test_cli_preserves_existing_output_and_creates_lf_requests_only(
    tmp_path, inputs, export_request, monkeypatch
):
    files = []
    for name, value in zip(("manifest", "inspection", "inventory"), inputs, strict=True):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value), encoding="utf-8")
        files.append(path)
    source = tmp_path / "sources"
    source.mkdir()
    original = source / "original.fcstd"
    original.write_bytes(b"preserved opaque input")
    monkeypatch.setattr(full, "build_request", lambda *args: copy.deepcopy(export_request))
    output = tmp_path / "full.json"
    batches = tmp_path / "batches"
    args = [
        "--source-root",
        str(source),
        "--manifest",
        str(files[0]),
        "--source-inspection",
        str(files[1]),
        "--inventory",
        str(files[2]),
        "--output",
        str(output),
        "--batch-directory",
        str(batches),
    ]
    assert full.main(args) == 0
    retained = output.read_bytes()
    assert b"\r\n" not in retained and len(list(batches.glob("*.json"))) == 6
    assert full.main(args) == 2
    assert output.read_bytes() == retained and original.read_bytes() == b"preserved opaque input"


def test_actual_six_batch_evidence_has_complete_exact_registry_without_release(export_request):
    series = load("hardware/print-planning/thor-full-print-export-native-v1.json")
    assert series["audit_status"] == "complete_six_batches_47_cached_geometry_variants_only"
    request_path = ROOT.parent / series["full_request_path"]
    assert hashlib.sha256(request_path.read_bytes()).hexdigest() == series["full_request_sha256"]
    assert len(series["batches"]) == 6 and len(series["variants"]) == 47
    actual_ids = []
    for batch in series["batches"]:
        raw_capture = (ROOT.parent / batch["raw_capture_path"]).read_bytes()
        raw_runner = (ROOT.parent / batch["raw_runner_path"]).read_bytes()
        assert hashlib.sha256(raw_capture).hexdigest() == batch["raw_capture_sha256"]
        assert hashlib.sha256(raw_runner).hexdigest() == batch["raw_runner_sha256"]
        capture, runner = json.loads(raw_capture), json.loads(raw_runner)
        assert capture["request"] == full.worker_batches(export_request)[batch["batch_index"] - 1]
        assert runner["capture_completed"] and runner["original57_sha256_unchanged"]
        assert len(runner["original57_sha256_after"]) == 57
        assert capture["open_document_count_before"] == capture["open_document_count_after"] == 0
        assert not capture["document_opened_or_recomputed"] and not capture["native_document_saved"]
        actual_ids.extend(row["selection_id"] for row in capture["selections"])
    assert actual_ids == [row["selection_id"] for row in export_request["selections"]]
    assert actual_ids == [row["selection_id"] for row in series["variants"]]
    assert len(set(actual_ids)) == 47
    members = [name for row in series["variants"] for name in row["installed_instance_ids"]]
    assert len(members) == len(set(members)) == 65
    assert sum(row["quantity_required"] for row in series["variants"]) == 65
    assert sum(row["draft_stl"]["triangle_count"] for row in series["variants"]) == 325810
    assert series["cross_asset_inertia_aggregation_performed"] is False
    assert series["source_to_installed_transforms_inferred"] is False
    assert series["density_or_physical_inertia"] is None
    assert all(value is False for value in series["qualification"].values())
