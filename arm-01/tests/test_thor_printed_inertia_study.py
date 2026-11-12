import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "printed_study", ROOT / "tools/thor_printed_inertia_study.py"
)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def fixture():
    probe = tool.frame_module()
    identity = [[float(i == j) for j in range(4)] for i in range(4)]
    vertices = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 4.0]]
    geo = {
        "volume_mm3": 24.0,
        "volume_m3": 24.0 * 1e-9,
        "com_mm": [1.0, 1.5, 2.0],
        "com_m": [0.001, 0.0015, 0.002],
        "centroidal_geometric_inertia_mm5": [[50.0, 0.0, 0.0], [0.0, 40.0, 0.0], [0.0, 0.0, 26.0]],
    }
    geo["centroidal_geometric_inertia_m5"] = [
        [v * 1e-15 for v in line] for line in geo["centroidal_geometric_inertia_mm5"]
    ]
    variants, rows, registry = [], [], []
    index = 0
    for i in range(47):
        selection = f"source-{i}"
        identifiers = []
        variants.append(
            {
                "selection_id": selection,
                "source_raw_placement_mm": identity,
                "source_vertices_mm": vertices,
                "cached_shape_properties": {"aggregate": geo},
            }
        )
        for _ in range(2 if i < 18 else 1):
            identifier = f"installed-{index}"
            identifiers.append(identifier)
            transform = copy.deepcopy(identity)
            transform[0][3] = index * 10.0
            target = [probe.point(transform, p) for p in vertices]
            metric = copy.deepcopy(geo)
            metric["com_mm"][0] += index * 10
            rows.append(
                {
                    "instance_id": identifier,
                    "selection_id": selection,
                    "root_subassembly": "test",
                    "status": "authenticated",
                    "ancestor_transform_mm": identity,
                    "source_raw_to_installed_raw_mm": transform,
                    "installed_raw_placement_mm": transform,
                    "source_raw_to_master_mm": transform,
                    "installed_vertices_mm": target,
                    "marker_check": probe.marker_check(vertices, target, transform),
                    "installed_raw_metrics": {"aggregate": metric},
                }
            )
            index += 1
        registry.append(
            {
                "selection_id": selection,
                "installed_instance_ids": identifiers,
                "quantity_required": len(identifiers),
            }
        )
    # Reuse the retained scope/preservation metadata while replacing geometry
    # with independently soluble boxes. This is a host test, not a native run.
    capture = json.loads(
        (ROOT / "hardware/cad/thor-printed-tensor-frames-v1.json").read_text(encoding="utf-8")
    )
    capture.update(variants=variants, instances=rows)
    return capture, {"variants": registry}


def test_65_uniform_boxes_match_closed_form_reduced_mass_parallel_axis():
    capture, registry = fixture()
    result = tool.study(capture, registry, 1240.0)
    aggregate = result["reference_uniform_solid_aggregate"]
    mass = 24e-9 * 1240
    assert aggregate["mass_kg"] == pytest.approx(65 * mass)
    assert aggregate["com_m"] == pytest.approx([0.321, 0.0015, 0.002])
    spread = mass * sum(((i - 32) * 0.01) ** 2 for i in range(65))
    # Each uniform 2x3x4mm box contributes its own centroidal tensor;
    # exact distributed COM offsets add only the Y/Z parallel-axis terms.
    expected = [
        [65 * 50e-15 * 1240, 0.0, 0.0],
        [0.0, 65 * 40e-15 * 1240 + spread, 0.0],
        [0.0, 0.0, 65 * 26e-15 * 1240 + spread],
    ]
    for actual, row in zip(aggregate["centroidal_inertia_kg_m2"], expected, strict=True):
        assert actual == pytest.approx(row, abs=1e-18)
    assert result["physical_printed_subset_inertia"] is None
    assert result["whole_arm_inertia"] is None
    assert result["default_native_geometric_integration_error_bound"] is None


def test_partial_native_authentication_never_aggregates_partial_subset_as_complete():
    capture, registry = fixture()
    capture["instances"][0]["status"] = "unverified"
    capture["complete_65_printed_coverage"] = False
    capture["authenticated_instance_count"] = 64
    capture["status"] = "partial_frame_authentication"
    result = tool.study(capture, registry)
    assert result["status"] == "blocked_incomplete_frames"
    assert result["reference_uniform_solid_aggregate"] is None
    assert result["components"] == []


@pytest.mark.parametrize(
    "change", ["duplicate", "wrongvariant", "transform", "marker", "units", "com_units"]
)
def test_changed_identity_frame_geometry_or_units_rejects_aggregation(change):
    capture, registry = fixture()
    if change == "duplicate":
        capture["instances"][1]["instance_id"] = capture["instances"][0]["instance_id"]
    elif change == "wrongvariant":
        capture["instances"][0]["selection_id"] = "source-46"
    elif change == "transform":
        capture["instances"][0]["source_raw_to_master_mm"][0][3] += 1
    elif change == "marker":
        capture["instances"][0]["installed_vertices_mm"][0][0] += 0.01
    elif change == "com_units":
        capture["variants"][0]["cached_shape_properties"]["aggregate"]["com_m"][0] *= 1000
    else:
        capture["variants"][0]["cached_shape_properties"]["aggregate"][
            "centroidal_geometric_inertia_m5"
        ][0][0] *= 1e15
    with pytest.raises(ValueError):
        tool.study(capture, registry)


@pytest.mark.parametrize("density", [True, 0, -1, float("nan"), float("inf")])
def test_reference_density_requires_explicit_finite_positive_number(density):
    capture, registry = fixture()
    with pytest.raises(ValueError):
        tool.study(capture, registry, density)


def test_retained_uniform_solid_reference_reproduces_and_conserves_all65_instances():
    capture = ROOT / "hardware/cad/thor-printed-tensor-frames-v1.json"
    actual = tool.build(ROOT, capture)
    expected = json.loads(
        (ROOT / "hardware/cad/thor-printed-inertia-study-v1.json").read_text(encoding="utf-8")
    )

    # JSON converts immutable dataclass tuples to arrays; compare normalized trees.
    def compare(a, b):
        if isinstance(a, dict):
            assert a.keys() == b.keys()
            for key in a:
                compare(a[key], b[key])
        elif isinstance(a, list):
            assert len(a) == len(b)
            for left, right in zip(a, b, strict=True):
                compare(left, right)
        elif isinstance(a, float):
            assert a == pytest.approx(b, rel=1e-12, abs=1e-15)
        else:
            assert a == b and type(a) is type(b)

    compare(json.loads(json.dumps(actual)), expected)
    assert actual["status"] == "complete_conditional_printed_subset_only"
    assert len(actual["components"]) == actual["printed_instance_count"] == 65
    assert actual["geometry_variants"] == 47
    total = sum(row["uniform_solid_mass_properties"]["mass_kg"] for row in actual["components"])
    assert actual["reference_uniform_solid_aggregate"]["mass_kg"] == pytest.approx(total)
    printable = json.loads(
        (ROOT / "hardware/cad/thor-printable-assets-v1.json").read_text(encoding="utf-8")
    )
    assert actual["installed_printed_volume_m3"] == pytest.approx(
        printable["installed_printed_volume_mm3"] * 1e-9, rel=1e-12
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("evidence_class", "fabricated"),
        ("source_copy_bytes_unchanged", 1),
        ("source_copy_sha256_after", {}),
        ("cad_saved", True),
        ("source_assembly_recomputed", True),
        ("preexisting_documents_preserved", False),
        ("open_document_count_after", 1),
        ("open_document_count_before", False),
        ("installed_leaf_count", 517),
        ("complete_65_printed_coverage", 1),
        ("authenticated_instance_count", 64),
        ("physical_inertia", [[1]]),
        ("native_geometric_integration_uncertainty_quantified", True),
    ],
)
def test_canonical_native_gate_rejects_scope_and_preservation_fabrications(field, value):
    capture, registry = fixture()
    capture[field] = value
    with pytest.raises(ValueError):
        tool.study(capture, registry)


@pytest.mark.parametrize("change", ["runtime", "path", "fixture", "docsource"])
def test_canonical_native_gate_recomputes_isolation_fixture_and_source_paths(change):
    capture, registry = fixture()
    if change == "runtime":
        capture["runtime_isolation"]["verified"] = 1
    elif change == "path":
        capture["runtime_isolation"]["actual_paths"]["AppTempPath"] = "C:/external"
    elif change == "fixture":
        capture["synthetic_coordinate_fixture"]["cases"][0]["observed_world_optimal_bounds_mm"][0][
            0
        ] += 1
    else:
        capture["loaded_document_sources"][0]["sha256"] = "f" * 64
    with pytest.raises(ValueError):
        tool.study(capture, registry)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b"\xff", b"[]"])
def test_strict_host_evidence_reader_rejects_duplicate_nonfinite_or_non_utf8(tmp_path, raw):
    path = tmp_path / "evidence.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        tool.strict_json(path)


def test_strict_host_evidence_reader_bounds_before_decode(tmp_path):
    path = tmp_path / "huge.json"
    path.write_bytes(b" " * (16777216 + 1))
    with pytest.raises(ValueError, match="bound"):
        tool.strict_json(path)


@pytest.mark.parametrize("change", ["traversal", "relative", "doc_traversal"])
def test_native_runtime_and_document_paths_require_absolute_no_traversal(change):
    capture, registry = fixture()
    runtime = capture["runtime_isolation"]
    if change == "traversal":
        value = runtime["root"] + "\\..\\escaped"
        runtime["actual_paths"]["AppTempPath"] = value
        capture["expected_runtime_paths"]["AppTempPath"] = value
    elif change == "relative":
        old = runtime["root"]
        runtime["root"] = "run-03"
        for paths in [runtime["actual_paths"], capture["expected_runtime_paths"]]:
            for key, value in paths.items():
                paths[key] = value.replace(old, "run-03")
        for row in capture["loaded_document_sources"]:
            row["path"] = row["path"].replace(old, "run-03")
    else:
        row = capture["loaded_document_sources"][0]
        row["path"] = row["path"].replace("\\source\\", "\\source\\..\\source\\")
    with pytest.raises(ValueError, match="absolute|traversal"):
        tool.study(capture, registry)


@pytest.mark.parametrize(
    "field,value",
    [
        ("contract_sha256", "f" * 64),
        ("request_sha256", "not-a-digest"),
        ("timeout_s", -1),
        ("timeout_s", True),
        ("elapsed_seconds", 481),
    ],
)
def test_builder_rejects_contradictory_or_unbounded_launcher_receipt(monkeypatch, field, value):
    real_reader = tool.strict_json

    def reader(path):
        raw, data = real_reader(path)
        if "publication_provenance" in data:
            data["publication_provenance"]["actual_launch_result"][field] = value
        return raw, data

    monkeypatch.setattr(tool, "strict_json", reader)
    with pytest.raises(ValueError):
        tool.build(ROOT, ROOT / "hardware/cad/thor-printed-tensor-frames-v1.json")
