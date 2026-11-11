"""Native-probe guards and independent geometry/unit expectations, not a native run."""

import copy
import hashlib
import importlib.util
import json
import math
import struct
import zipfile
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

from raftel_arm01.engineering.inertia import (
    IDENTITY,
    aggregate_mass_properties,
    transform_mass_properties,
    uniform_box,
    validate_centroidal_inertia,
)

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "solid_properties_probe", ROOT / "tools/probe_thor_solid_properties_freecad.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def request():
    return {
        "schema_version": 1,
        "source_revision": probe.SOURCE_REVISION,
        "evidence_class": "selected_saved_BRep_properties_request",
        "selections": [
            {
                "selection_id": "fixture-body",
                "source_file": "freecad-src/Fixture.fcstd",
                "source_sha256": "0" * 64,
                "object_name": "Body",
                "object_type": "PartDesign::Body",
                "brep_entry": "PartShape.brp",
                "brep_sha256": "1" * 64,
                "xml_placement": {"position_mm": [0, 0, 0], "quaternion_xyzw": [0, 0, 0, 1]},
                "selection_evidence": "synthetic input-validation fixture, not native evidence",
                "uniform_density": None,
                "tessellation": {
                    "linear_deflection_mm": 0.1,
                    "angular_deflection_rad": 0.2,
                    "relative": False,
                    "filename": "fixture-draft.stl",
                },
            }
        ],
    }


def flatten(matrix):
    return tuple(value for row in matrix for value in row)


def fixture_records():
    return {
        name: {"aggregate": copy.deepcopy(expected)}
        for name, expected in probe.fixture_expectations().items()
    }


def test_primitive_expectations_have_independent_known_units_and_rotated_signs():
    expectations = probe.fixture_expectations()
    assert expectations["box"]["volume_mm3"] == 24
    assert expectations["box"]["com_mm"] == [1, 1.5, 2]
    assert flatten(expectations["box"]["centroidal_geometric_inertia_mm5"]) == (
        50,
        0,
        0,
        0,
        40,
        0,
        0,
        0,
        26,
    )
    cylinder = expectations["cylinder"]
    assert cylinder["volume_mm3"] == pytest.approx(20 * math.pi)
    assert cylinder["centroidal_geometric_inertia_mm5"][0][0] == pytest.approx(185 * math.pi / 3)
    assert cylinder["centroidal_geometric_inertia_mm5"][2][2] == pytest.approx(40 * math.pi)
    rotation = probe._rotation((0, 0, 1), 30)
    rotated = probe._transformed_expected(
        24,
        (1, 1.5, 2),
        expectations["box"]["centroidal_geometric_inertia_mm5"],
        rotation,
        (3, -2, 4),
    )
    assert rotated["centroidal_geometric_inertia_mm5"][0][0] == pytest.approx(47.5)
    assert rotated["centroidal_geometric_inertia_mm5"][1][1] == pytest.approx(42.5)
    assert rotated["centroidal_geometric_inertia_mm5"][0][1] == pytest.approx(5 * math.sqrt(3) / 2)


@pytest.mark.parametrize("name", list(probe.fixture_expectations()))
def test_native_fixture_validator_rejects_wrong_reference_units_or_frame(name):
    records = fixture_records()
    assert probe.verify_fixture_records(records)["verified"]
    records[name]["aggregate"]["centroidal_geometric_inertia_mm5"][0][0] *= 2
    with pytest.raises(ValueError, match=name):
        probe.verify_fixture_records(records)


def test_translation_and_missing_native_cases_are_not_silently_accepted():
    records = fixture_records()
    records["box_translated"]["aggregate"]["com_mm"] = [1, 1.5, 2]
    with pytest.raises(ValueError, match="box_translated"):
        probe.verify_fixture_records(records)
    records.pop("box_translated")
    with pytest.raises(ValueError, match="missing"):
        probe.verify_fixture_records(records)


def test_same_brep_solid_aggregation_and_mm5_conversion_match_independent_si_utility():
    rows = [
        {
            "volume_mm3": 1,
            "com_mm": [x, 0, 0],
            "centroidal_geometric_inertia_mm5": [[1 / 6, 0, 0], [0, 1 / 6, 0], [0, 0, 1 / 6]],
        }
        for x in (-5, 5)
    ]
    geometric = probe.aggregate_geometric_solids(rows)
    assert geometric["volume_mm3"] == 2
    assert geometric["com_mm"] == [0, 0, 0]
    assert flatten(geometric["centroidal_geometric_inertia_mm5"]) == pytest.approx(
        (1 / 3, 0, 0, 0, 50 + 1 / 3, 0, 0, 0, 50 + 1 / 3)
    )
    density = {
        "density_kg_m3": 1240,
        "effective_uniform_fraction": 0.5,
        "evidence": "uniform analytical scenario only",
    }
    result = probe.uniform_density_properties(geometric, density)
    cuboid = uniform_box(
        1e-9 * 1240 * 0.5, (0.001,) * 3, frame="fixture-m", evidence="independent SI cube"
    )
    independent = aggregate_mass_properties(
        tuple(
            transform_mass_properties(
                cuboid,
                IDENTITY,
                (x, 0, 0),
                target_frame="world-m",
                transform_evidence="known analytical cube COM",
            )
            for x in (-0.005, 0.005)
        ),
        evidence="independent SI aggregation",
    )
    assert result["mass_kg"] == pytest.approx(independent.mass_kg)
    assert flatten(result["centroidal_inertia_kg_m2"]) == pytest.approx(
        flatten(independent.centroidal_inertia_kg_m2), rel=1e-12, abs=1e-25
    )
    assert not result["effective_uniform_fraction_is_slicer_infill"]
    assert probe.uniform_density_properties(geometric, None) is None
    validate_centroidal_inertia(geometric["centroidal_geometric_inertia_m5"])


@pytest.mark.parametrize(
    "tensor",
    [
        [[1, 2, 0], [2, 1, 0], [0, 0, 1]],
        [[10, 0, 0], [0, 1, 0], [0, 0, 1]],
    ],
)
def test_nonphysical_tensors_rejected_without_confusing_si_scale(tensor):
    for scale in (1e-18, 1, 1e18):
        with pytest.raises(ValueError, match="PSD/triangle.*raw matrix"):
            probe._matrix([[value * scale for value in row] for row in tensor])


@pytest.mark.parametrize("epsilon", [1e-7, 1e-6])
def test_worker_near_rank_defect_rejected_in_rotated_and_scaled_bases(epsilon):
    tensor = [[1, -epsilon, 0], [-epsilon, 1, 0], [0, 0, 0]]
    rotated = probe._transformed_expected(
        1, (0, 0, 0), tensor, probe._rotation((1, 2, 3), 37), (0, 0, 0)
    )["centroidal_geometric_inertia_mm5"]
    for scale in (1e-24, 1, 1e24):
        for candidate in (tensor, rotated):
            with pytest.raises(ValueError, match="PSD/triangle"):
                probe._matrix([[value * scale for value in row] for row in candidate])
        assert probe._matrix([[scale, 0, 0], [0, scale, 0], [0, 0, 0]])


def test_worker_finite_large_valid_tensor_does_not_overflow_half_trace():
    tensor = [[1.7e308, 0, 0], [0, 1.7e308, 0], [0, 0, 1.7e308]]
    assert probe._matrix(tensor) == tensor


def test_worker_subnormal_tensor_checks_keep_sign_and_triangle_constraints():
    tiny = math.ulp(0.0)
    tensor = [[tiny, 0, 0], [0, tiny, 0], [0, 0, tiny]]
    assert probe._matrix(tensor) == tensor
    with pytest.raises(ValueError, match="nonnegative|PSD/triangle"):
        probe._matrix([[-tiny, 0, 0], [0, -tiny, 0], [0, 0, -tiny]])
    with pytest.raises(ValueError, match="PSD/triangle"):
        probe._matrix([[tiny, 0, 0], [0, tiny, 0], [0, 0, 3 * tiny]])


def test_selected_worker_rejects_conflicting_generic_entry_before_paths_or_native_import(
    monkeypatch,
):
    monkeypatch.setenv("RAFTEL_RUN_FREECAD_AUDIT", "1")
    monkeypatch.setenv(probe.PROBE_FLAG, "1")
    with pytest.raises(ValueError, match="generic audit entry flag conflicts"):
        probe.native_capture()


def test_native_closed_solid_guard_does_not_treat_valid_open_shape_as_accepted():
    matrix = SimpleNamespace(
        **{f"A{i}{j}": 1 / 6 if i == j else 0 for i in range(1, 4) for j in range(1, 4)}
    )
    solid = SimpleNamespace(
        Volume=1.0,
        CenterOfMass=[0.5] * 3,
        MatrixOfInertia=matrix,
        isValid=lambda: True,
        isClosed=lambda: False,
    )
    shape = SimpleNamespace(Solids=[solid], isValid=lambda: True)
    with pytest.raises(ValueError, match="Solid is not closed.*raw solid metrics"):
        probe._native_metrics(shape)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: row.update(source_file="../Fixture.fcstd"),
        lambda row: row.update(brep_entry="../PartShape.brp"),
        lambda row: row.update(source_sha256="main"),
        lambda row: row["xml_placement"].update(quaternion_xyzw=[0, 0, 0, 2]),
        lambda row: row["tessellation"].update(relative=True),
        lambda row: row["tessellation"].update(linear_deflection_mm=math.nan),
        lambda row: row["tessellation"].update(angular_deflection_rad=0),
        lambda row: row["tessellation"].update(filename="../unsafe.stl"),
        lambda row: row["tessellation"].update(filename="NUL.stl"),
        lambda row: row.update(
            uniform_density={
                "density_kg_m3": 1240,
                "effective_uniform_fraction": 1.1,
                "evidence": "fixture",
            }
        ),
    ],
)
def test_invalid_or_ambiguous_selected_inputs_fail_before_native_import(mutate):
    data = request()
    mutate(data["selections"][0])
    with pytest.raises(ValueError):
        probe.validate_request(data)


def synthetic_archive(tmp_path):
    root = tmp_path / "sources"
    source = root / "freecad-src/Fixture.fcstd"
    source.parent.mkdir(parents=True)
    raw = b"synthetic cached BRep bytes; not a native geometry fixture"
    xml = b"""<Document><Objects><Object name="Body" type="PartDesign::Body" /></Objects>
    <ObjectData><Object name="Body"><Properties>
    <Property name="Shape"><Part file="PartShape.brp" /></Property>
    <Property name="Placement"><PropertyPlacement Px="0" Py="0" Pz="0"
    Q0="0" Q1="0" Q2="0" Q3="1" /></Property>
    </Properties></Object></ObjectData></Document>"""
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("Document.xml", xml)
        archive.writestr("PartShape.brp", raw)
    data = request()
    row = data["selections"][0]
    row["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    row["brep_sha256"] = hashlib.sha256(raw).hexdigest()
    return root, row, source, raw


def test_cached_archive_pin_xml_entry_and_placement_checks_without_native_import(tmp_path):
    root, selection, source, expected = synthetic_archive(tmp_path)
    before = source.read_bytes()
    raw, binding = probe.read_selected_brep(root, selection)
    assert raw == expected and source.read_bytes() == before
    assert binding["xml_placement_not_applied"] == selection["xml_placement"]
    for key, value in (
        ("source_sha256", "f" * 64),
        ("brep_sha256", "f" * 64),
        ("object_type", "Part::Feature"),
        ("brep_entry", "different.brp"),
    ):
        bad = copy.deepcopy(selection)
        bad[key] = value
        with pytest.raises(ValueError):
            probe.read_selected_brep(root, bad)
    bad = copy.deepcopy(selection)
    bad["xml_placement"]["position_mm"][0] = 1
    with pytest.raises(ValueError, match="XML placement"):
        probe.read_selected_brep(root, bad)


def test_worker_requires_optin_and_does_not_touch_existing_report(tmp_path, monkeypatch):
    monkeypatch.delenv(probe.PROBE_FLAG, raising=False)
    with pytest.raises(ValueError, match="opt-in"):
        probe.native_capture()
    root = tmp_path / "run"
    root.mkdir()
    source = root / "sources"
    source.mkdir()
    config = root / "request.json"
    config.write_text(json.dumps(request()))
    report = root / "report.json"
    report.write_text("preserved evidence")
    for key, value in {
        probe.PROBE_FLAG: "1",
        "RAFTEL_SOLID_RUN_DIR": str(root),
        "RAFTEL_SOLID_SOURCE_ROOT": str(source),
        "RAFTEL_SOLID_REQUEST": str(config),
        "RAFTEL_SOLID_REPORT": str(report),
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="new .json"):
        probe.native_capture()
    assert report.read_text() == "preserved evidence"


def test_binary_draft_stl_has_exact_layout_units_label_and_outward_tetrahedron():
    vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
    raw = probe.binary_stl(vertices, faces)
    assert len(raw) == 84 + 50 * 4
    assert struct.unpack_from("<I", raw, 80) == (4,)
    assert b"units mm" in raw[:80] and b"NOT PRINT QUALIFIED" in raw[:80]
    spec = importlib.util.spec_from_file_location("stl_review", ROOT / "tools/thor_slicer_plan.py")
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)
    result = analyzer.analyze_stl(raw)
    assert result["absolute_signed_volume_interpreted_mm3"] == pytest.approx(1 / 6)
    assert result["topology"]["closed_consistently_oriented_two_manifold"]
    assert result["self_intersections"] == "not_checked"


def test_retained_actual_native_capture_replays_units_fixtures_and_source_contract():
    report = json.loads((ROOT / "hardware/cad/thor-native-solid-properties-v1.json").read_text())
    assert report["audit_status"] == "complete_selected_cached_geometry_only"
    assert report["freecad_version"][:3] == ["1", "1", "4"]
    assert report["opencascade_version"] == "7.8.1"
    assert report["open_document_count_before"] == report["open_document_count_after"] == 0
    assert not report["document_opened_or_recomputed"] and not report["native_document_saved"]
    assert not report["cross_asset_aggregation_performed"]
    assert report["input_copy_bytes_unchanged"]
    assert report["source_copy_sha256_before"] == report["source_copy_sha256_after"]
    assert report["declared_revision_not_independently_authenticated_by_worker"]
    expected_keys = {
        "UserParameter",
        "SystemParameter",
        "UserHomePath",
        "UserAppData",
        "AppTempPath",
    }
    assert (
        set(report["actual_runtime_paths"])
        == set(report["expected_isolated_paths"])
        == expected_keys
    )
    for key in expected_keys:
        assert PureWindowsPath(report["actual_runtime_paths"][key]) == PureWindowsPath(
            report["expected_isolated_paths"][key]
        )
    summary = probe.verify_fixture_records(report["primitive_fixtures"]["records"])
    assert summary == report["primitive_fixtures"]["summary"]
    request_path = ROOT / "hardware/print-planning/thor-native-export-inputs-v1.json"
    assert report["request_sha256"] == hashlib.sha256(request_path.read_bytes()).hexdigest()
    descriptors = {row["selection_id"]: row for row in report["request"]["selections"]}
    assert len(report["selections"]) == len(descriptors) == 8
    frame_ids = set()
    for row in report["selections"]:
        frame_ids.add(row["coordinate_frame_id"])
        selection = descriptors[row["selection_id"]]
        binding, metrics = row["source_binding"], row["cached_shape_properties"]
        assert binding["source_sha256"] == selection["source_sha256"]
        assert binding["brep_sha256"] == selection["brep_sha256"]
        assert binding["xml_placement_not_applied"] == selection["xml_placement"]
        assert metrics["native_shape_valid"]
        assert all(
            item["native_valid"] and item["native_closed_flag"] for item in metrics["solids"]
        )
        geometric = metrics["aggregate"]
        assert geometric["solid_count"] == 1
        assert geometric["volume_m3"] == geometric["volume_mm3"] * 1e-9
        assert geometric["centroidal_geometric_inertia_m5"] == [
            [value * 1e-15 for value in items]
            for items in geometric["centroidal_geometric_inertia_mm5"]
        ]
        validate_centroidal_inertia(geometric["centroidal_geometric_inertia_m5"])
        assert row["uniform_density_scenario"] is None
        assert row["physical_or_purchased_internal_or_nonuniform_print_inertia_kg_m2"] is None
        assert row["draft_stl"]["units"] == "mm"
        assert not row["draft_stl"]["mesh_self_intersections_checked"]
        assert not row["draft_stl"]["print_or_fit_qualification"]
    assert len(frame_ids) == 8


def test_normalized_worker_native_replay_preserves_prior_geometry_and_matches_current_code():
    original = json.loads((ROOT / "hardware/cad/thor-native-solid-properties-v1.json").read_text())
    replay = json.loads(
        (ROOT / "hardware/cad/thor-native-solid-properties-normalized-v1.json").read_text()
    )
    assert (
        replay["capture_script_sha256"]
        == hashlib.sha256(
            (ROOT / "tools/probe_thor_solid_properties_freecad.py").read_bytes()
        ).hexdigest()
    )
    assert replay["capture_script_sha256"] != original["capture_script_sha256"]
    for key in (
        "request",
        "request_sha256",
        "selections",
        "primitive_fixtures",
        "source_copy_sha256_before",
        "source_copy_sha256_after",
    ):
        assert replay[key] == original[key]
    assert replay["audit_status"] == "complete_selected_cached_geometry_only"
    assert replay["errors"] == []
    assert replay["open_document_count_before"] == replay["open_document_count_after"] == 0
    for key in replay["actual_runtime_paths"]:
        assert PureWindowsPath(replay["actual_runtime_paths"][key]) == PureWindowsPath(
            replay["expected_isolated_paths"][key]
        )
