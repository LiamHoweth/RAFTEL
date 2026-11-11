"""Host-only adaptive-protocol guards; optional binary bindings are never imported."""

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).parents[1] / "tools/probe_thor_adaptive_properties.py"
spec = importlib.util.spec_from_file_location("adaptive_guard_fixture", SOURCE)
adaptive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adaptive)


def test_analytic_fixture_contract_covers_translation_rotation_and_centroidal_units():
    rows = adaptive.fixture_expected()
    assert len(rows) == 6
    assert rows["box_base"]["volume_mm3"] == 24
    assert rows["box_base"]["centroidal_inertia_mm5"] == [[50, 0, 0], [0, 40, 0], [0, 0, 26]]
    assert rows["cylinder_base"]["volume_mm3"] == pytest.approx(20 * math.pi)
    for name in ("box", "cylinder"):
        base = rows[name + "_base"]
        translated = rows[name + "_translated"]
        assert translated["centroidal_inertia_mm5"] == base["centroidal_inertia_mm5"]
        assert translated["com_mm"] == [
            a + b for a, b in zip(base["com_mm"], (10, -20, 30), strict=True)
        ]
        rotated = rows[name + "_rotated_translated"]
        assert sum(rotated["centroidal_inertia_mm5"][i][i] for i in range(3)) == pytest.approx(
            sum(base["centroidal_inertia_mm5"][i][i] for i in range(3))
        )
        assert adaptive.measurement_error(rotated, rotated)["verified"]


def test_new_GK_scope_keeps_original_three_method_failure_and_thresholds():
    fixtures = {
        name: [
            dict(copy.deepcopy(truth), algorithm=algorithm) for algorithm in adaptive.ALL_ALGORITHMS
        ]
        for name, truth in adaptive.fixture_expected().items()
    }
    fixtures["cylinder_base"][1]["centroidal_inertia_mm5"][0][0] += 0.001
    original = adaptive.fixture_gate_status(fixtures, list(adaptive.ALL_ALGORITHMS))
    narrowed = adaptive.fixture_gate_status(fixtures, ["default", "adaptive_gauss_kronrod"])
    assert original["original_all18_fixture_gate_passed"] is False
    assert original["selected_algorithm_fixture_gate_passed"] is False
    assert narrowed["original_all18_fixture_gate_passed"] is False
    assert narrowed["selected_algorithm_fixture_gate_passed"] is True
    assert narrowed["failed_fixture_measurements"] == original["failed_fixture_measurements"]
    fixtures["box_base"][2]["centroidal_inertia_mm5"][0][0] += 0.001
    assert (
        adaptive.fixture_gate_status(fixtures, ["default", "adaptive_gauss_kronrod"])[
            "selected_algorithm_fixture_gate_passed"
        ]
        is False
    )
    fixtures["box_base"].pop()
    with pytest.raises(ValueError, match="all three"):
        adaptive.fixture_gate_status(fixtures, ["default", "adaptive_gauss_kronrod"])


@pytest.mark.parametrize(
    "protocol_request",
    [
        {"protocol_version": True},
        {"protocol_version": 3},
        {"protocol_version": 2},
        {"protocol_version": 1, "complex_algorithms": ["default", "adaptive_gauss_kronrod"]},
        {"protocol_version": 2, "complex_algorithms": ["default"]},
    ],
)
def test_narrow_scope_must_be_new_explicit_protocol_not_retroactive_gate(protocol_request):
    with pytest.raises(ValueError):
        adaptive.protocol_algorithms(protocol_request)


def test_protocol_versions_declare_exact_complex_algorithm_families():
    assert adaptive.protocol_algorithms({}) == (1, list(adaptive.ALL_ALGORITHMS))
    assert adaptive.protocol_algorithms(
        {"protocol_version": 2, "complex_algorithms": ["default", "adaptive_gauss_kronrod"]}
    ) == (2, ["default", "adaptive_gauss_kronrod"])


def test_derived_common_is_distinct_protocol_with_explicit_non_Git_scope():
    declared = dict(
        protocol_version=3,
        complex_algorithms=["default", "adaptive_gauss_kronrod"],
        input_scope="self_generated_wrist_common_only",
        derived_common={"provenance": "separately pinned"},
    )
    assert adaptive.protocol_algorithms(declared) == (3, ["default", "adaptive_gauss_kronrod"])
    for key in ("input_scope", "derived_common"):
        wrong = copy.deepcopy(declared)
        del wrong[key]
        with pytest.raises(ValueError, match="protocol3"):
            adaptive.protocol_algorithms(wrong)
    declared["protocol_version"] = 2
    with pytest.raises(ValueError, match="distinct protocol3"):
        adaptive.protocol_algorithms(declared)


@pytest.mark.parametrize("fault", ["volume", "COM", "tensor", "nan", "boolean"])
def test_wrong_fixture_measurements_cannot_pass(fault):
    expected = adaptive.fixture_expected()["box_base"]
    actual = copy.deepcopy(expected)
    if fault == "volume":
        actual["volume_mm3"] += 0.01
    elif fault == "COM":
        actual["com_mm"][0] += 0.01
    elif fault == "tensor":
        actual["centroidal_inertia_mm5"][0][0] += 0.01
    elif fault == "nan":
        actual["volume_mm3"] = math.nan
    else:
        actual["volume_mm3"] = True
    if fault in {"nan", "boolean"}:
        with pytest.raises(ValueError):
            adaptive.measurement_error(actual, expected)
    else:
        assert adaptive.measurement_error(actual, expected)["verified"] is False


def kernel_fixture(tmp_path):
    packages = tmp_path / "packages"
    path = packages / "cadquery_ocp.libs/TKernel-pinned.dll"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"opaque non-executable fixture")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "files": [dict(relative_path="cadquery_ocp.libs/TKernel-pinned.dll", sha256=digest)]
    }
    record = dict(path=str(path), sha256=digest, file_version="7.8.1")
    return packages, manifest, record


def test_observed_pinned_kernel_path_hash_and_version_are_required(tmp_path):
    packages, manifest, record = kernel_fixture(tmp_path)
    assert adaptive.validate_module_origins([record], packages, manifest) == [record]


@pytest.mark.parametrize("fault", ["outside", "hash", "version", "missing", "FreeCAD", "Part"])
def test_mixed_kernel_or_unobserved_identity_rejects(tmp_path, fault):
    packages, manifest, record = kernel_fixture(tmp_path)
    records = [record]
    if fault == "outside":
        record["path"] = str(tmp_path / "FreeCAD-bin/TKernel.dll")
    elif fault == "hash":
        record["sha256"] = "0" * 64
    elif fault == "version":
        record["file_version"] = "7.9.0"
    elif fault == "missing":
        records = []
    else:
        records.append(
            dict(path=str(tmp_path / ("FreeCADApp.dll" if fault == "FreeCAD" else "Part.pyd")))
        )
    with pytest.raises(ValueError):
        adaptive.validate_module_origins(records, packages, manifest)


@pytest.mark.parametrize("flag", adaptive.FORBIDDEN_FLAGS)
def test_other_CAD_worker_flags_reject_before_optional_import(monkeypatch, flag):
    monkeypatch.setenv(adaptive.FLAG, "1")
    monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match="no inherited"):
        adaptive.guarded_inputs()


def test_opt_in_and_python_isolation_are_required(monkeypatch):
    monkeypatch.delenv(adaptive.FLAG, raising=False)
    with pytest.raises(ValueError, match="opt-in"):
        adaptive.guarded_inputs()
    monkeypatch.setenv(adaptive.FLAG, "1")
    for flag in adaptive.FORBIDDEN_FLAGS:
        monkeypatch.delenv(flag, raising=False)
    monkeypatch.setattr(adaptive.sys, "flags", SimpleNamespace(isolated=0, no_site=0))
    with pytest.raises(ValueError, match="-I -S -B"):
        adaptive.guarded_inputs()


@pytest.fixture
def isolated_guard(tmp_path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    request = run / "request.json"
    request.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    monkeypatch.setenv(adaptive.FLAG, "1")
    for flag in adaptive.FORBIDDEN_FLAGS:
        monkeypatch.delenv(flag, raising=False)
    monkeypatch.setenv("RAFTEL_ADAPTIVE_RUN_DIR", str(run))
    monkeypatch.setenv("RAFTEL_ADAPTIVE_REQUEST", str(request))
    monkeypatch.setattr(adaptive.sys, "flags", SimpleNamespace(isolated=1, no_site=1))
    monkeypatch.setattr(adaptive.sys, "dont_write_bytecode", True)
    monkeypatch.setattr(adaptive.shutil, "disk_usage", lambda _: SimpleNamespace(free=64 * 1024**3))
    return run, request


@pytest.mark.parametrize("schema", [True, 2, None])
def test_unsupported_request_schema_rejects_before_package_load(isolated_guard, schema):
    _, request = isolated_guard
    request.write_text(json.dumps({"schema_version": schema}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        adaptive.guarded_inputs()


def test_existing_evidence_and_low_reserve_are_preserved(isolated_guard, monkeypatch):
    run, _ = isolated_guard
    output = run / "probe.json"
    output.write_text("preserved earlier evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="fresh"):
        adaptive.guarded_inputs()
    assert output.read_text() == "preserved earlier evidence"
    monkeypatch.setattr(adaptive.shutil, "disk_usage", lambda _: SimpleNamespace(free=49 * 1024**3))
    with pytest.raises(ValueError, match="50 GiB"):
        adaptive.guarded_inputs()


def test_curated_actual_study_preserves_failed_history_and_scoped_results():
    path = Path(__file__).parents[1] / "hardware/cad/thor-adaptive-metric-study-v1.json"
    study = json.loads(path.read_text(encoding="utf-8"))
    assert study["acquisition"]["downloaded_bytes"] == 104002483
    assert study["acquisition"]["wheel_RECORD_entries_verified"] == 932
    assert study["kernel_boundary"]["same_binary_build_as_FreeCAD"] is False
    assert study["kernel_boundary"]["verified_loaded_TK_DLLs_before"] == 46
    assert study["kernel_boundary"]["verified_loaded_TK_DLLs_after"] == 46
    assert study["prepared_only_run_indices"] == [4]
    assert [r["run_index"] for r in study["runs"]] == [1, 2, 3, 5]
    for run in study["runs"]:
        encoded = (json.dumps(run["capture"], indent=2, allow_nan=False) + "\n").encode("utf-8")
        assert hashlib.sha256(encoded).hexdigest() == run["raw_capture_sha256"]
        capture = run["capture"]
        assert capture["source_candidate_input_bytes_unchanged"]
        assert capture["extracted_package_bytes_unchanged"]
        assert capture["same_binary_kernel_as_FreeCAD"] is False
        assert capture["migration_accepted"] is False and capture["manufacturing_released"] is False
    assert all(
        r["capture"]["audit_status"] == "failed_independent_adaptive_diagnostic"
        for r in study["runs"][:2]
    )
    art1 = study["runs"][2]["capture"]
    assert art1["original_all18_fixture_gate_passed"] is False
    assert art1["selected_algorithm_fixture_gate_passed"] is True
    assert all(
        r["algorithm"] != "adaptive_gauss" for rows in art1["measurements"].values() for r in rows
    )
    assert study["comparisons"][-1]["candidate_minus_source_volume_mm3"] == pytest.approx(
        -1.0069504927960224
    )
    common = study["derived_common_summary"]
    assert common["reference_capture_sha256"] == adaptive.COMMON_CONTEXT_SHA256
    assert common["all_faces_have_owner_IsSame_and_IsEqual"]
    assert common["solid_face_counts"] == [3, 4, 4]
    assert common["signed_volume_comparisons"]["default_open"]["aggregate_volume_mm3"] < 0
    assert (
        abs(
            common["signed_volume_comparisons"]["default_only_closed"][
                "aggregate_minus_solid_sum_mm3"
            ]
        )
        < 1e-15
    )
    assert common["geometric_overlap_accepted"] is False
    assert study["conclusions"]["discrepancy_fully_explained"] is False
    assert study["conclusions"]["migration_accepted"] is False
