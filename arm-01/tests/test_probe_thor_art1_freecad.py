"""Pure guard/semantic tests; no FreeCAD process or geometry kernel is exercised."""

import hashlib
import json
import math
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
PATH = ROOT / "tools" / "probe_thor_art1_freecad.py"
CONTRACT = json.loads(
    (ROOT / "hardware" / "cad" / "thor-art1-desktop-source-fingerprint.json").read_text()
)


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.delenv("RAFTEL_RUN_THOR_ART1_PROBE", raising=False)
    loaded = runpy.run_path(str(PATH))
    # Synthetic subprocess guards must not depend on CI runner disk capacity.
    # The explicit low-reserve test overrides this value to exercise rejection.
    monkeypatch.setattr(
        loaded["run_probe"].__globals__["shutil"],
        "disk_usage",
        lambda path: SimpleNamespace(free=64 * 1024**3),
    )
    return loaded


def descriptor(probe, kind="circle"):
    return probe["bolt_support_descriptor"](CONTRACT, kind=kind)


def candidate(probe, *, kind="circle", name="Edge402"):
    result = descriptor(probe, kind)
    result["subelement"] = name
    return result


def test_unique_geometric_circle_match_does_not_depend_on_edge_number(probe):
    result = probe["match_semantic_support"](descriptor(probe), [candidate(probe)])
    assert result["status"] == "unique"
    assert result["selected_subelement"] == "Edge402"
    assert not result["support_remapped"]


def test_no_match_is_not_replaced_by_nearest_edge(probe):
    circle = candidate(probe)
    circle["center_mm"][0] += 0.0001
    result = probe["match_semantic_support"](descriptor(probe), [circle])
    assert result["status"] == "no_match"
    assert result["selected_subelement"] is None


def test_multiple_geometric_matches_are_explicitly_ambiguous(probe):
    result = probe["match_semantic_support"](
        descriptor(probe), [candidate(probe), candidate(probe, name="Edge7")]
    )
    assert result["status"] == "ambiguous"
    assert result["selected_subelement"] is None


def test_cylinder_axis_line_allows_longitudinal_reference_origin_shift(probe):
    cylinder = candidate(probe, kind="cylinder", name="Face501")
    cylinder["center_mm"][1] += 60
    cylinder["axis"] = [-x for x in cylinder["axis"]]
    result = probe["match_semantic_support"](descriptor(probe, "cylinder"), [cylinder])
    assert result["status"] == "unique"


def test_cylinder_perpendicular_axis_line_offset_rejected(probe):
    cylinder = candidate(probe, kind="cylinder", name="Face501")
    cylinder["center_mm"][0] += 0.0001
    assert (
        probe["match_semantic_support"](descriptor(probe, "cylinder"), [cylinder])["status"]
        == "no_match"
    )


@pytest.mark.parametrize("change", ["radius", "axis", "arc", "kind"])
def test_wrong_semantic_support_is_rejected(probe, change):
    circle = candidate(probe)
    if change == "radius":
        circle["radius_mm"] += 0.001
    elif change == "axis":
        circle["axis"] = [1, 0, 0]
    elif change == "arc":
        circle["full_circle"] = False
    else:
        circle["kind"] = "cylinder"
    assert probe["match_semantic_support"](descriptor(probe), [circle])["status"] == "no_match"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True, "1.7"])
def test_invalid_candidate_numbers_fail_instead_of_matching(probe, value):
    circle = candidate(probe)
    circle["radius_mm"] = value
    with pytest.raises(ValueError, match="finite"):
        probe["match_semantic_support"](descriptor(probe), [circle])


def test_duplicate_candidate_identifiers_rejected(probe):
    with pytest.raises(ValueError, match="unique"):
        probe["match_semantic_support"](descriptor(probe), [candidate(probe), candidate(probe)])


def test_head_recess_and_body_hole_have_separate_source_descriptors(probe):
    body = descriptor(probe)
    head = probe["bolt_support_descriptor"](CONTRACT, head=True)
    assert body["radius_mm"] == 1.7
    assert head["radius_mm"] == 2.95
    assert head["center_mm"] == pytest.approx([-31.5, -75, 8])
    assert head["semantic_name"] != body["semantic_name"]


def test_first_drift_summary_uses_captured_metrics_and_keeps_unclean_shapes_separate(probe):
    shape = {
        "is_null": False,
        "valid": True,
        "solid_count": 1,
        "face_count": 3,
        "edge_count": 4,
        "volume_mm3": 30,
        "area_mm2": 20,
        "length_mm": 10,
        "bounds_mm": [0, 1, 0, 1, 0, 1],
        "center_of_mass_mm": [0.5, 0.5, 0.5],
    }
    saved = {name: {"shape": dict(shape)} for name in ("Pad", "Groove", "Thickness")}
    rebuilt = {name: {"shape": dict(shape), "states": ["Up-to-date"]} for name in saved}
    rebuilt["Groove"]["shape"]["volume_mm3"] -= 2.8
    rebuilt["Thickness"]["states"] = ["Touched", "Invalid"]
    result = probe["feature_drift_summary"](saved, rebuilt)
    assert result["first_changed_captured_feature"] == "Groove"
    assert result["first_own_state_unclean_feature"] == "Thickness"
    assert result["first_true_semantic_drift"] is None
    assert not result["full_shape_equivalence_verified"]
    assert not result["full_dependency_closure_checked"]
    assert all(not row["upstream_dependency_state_checked"] for row in result["features"])


def test_no_captured_metrics_does_not_establish_equivalence(probe):
    result = probe["feature_drift_summary"]({}, {})
    assert result["first_changed_captured_feature"] is None
    assert not result["full_shape_equivalence_verified"]


def fixture_paths(tmp_path, probe):
    source = tmp_path / "upstream" / "Art1Body.fcstd"
    source.parent.mkdir()
    source.write_bytes(b"synthetic source bytes")
    fixture_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    # Only these fake-runtime guard tests substitute the immutable fixture hash.
    # Production code has no command-line hash override.
    probe["run_probe"].__globals__["SOURCE_SHA256"] = fixture_sha
    executable = tmp_path / "fake-freecadcmd.exe"
    executable.write_bytes(b"not executed")
    return source, executable, tmp_path / "new-run"


def test_wrong_source_hash_rejected_before_creating_output_or_launch(probe, tmp_path):
    source = tmp_path / "Art1Body.fcstd"
    source.write_bytes(b"untrusted document")
    executable = tmp_path / "freecadcmd.exe"
    executable.write_bytes(b"not executed")
    output = tmp_path / "new-run"
    with pytest.raises(ValueError, match="SHA-256"):
        probe["run_probe"](executable, source, output)
    assert not output.exists()
    assert source.read_bytes() == b"untrusted document"


def test_existing_run_is_never_overwritten(probe, tmp_path):
    source, executable, output = fixture_paths(tmp_path, probe)
    output.mkdir()
    report = output / "probe.json"
    report.write_text("retained evidence")
    with pytest.raises(ValueError, match="never overwritten"):
        probe["run_probe"](executable, source, output)
    assert report.read_text() == "retained evidence"


def test_runner_uses_fresh_copy_isolated_preferences_and_explicit_opt_in(
    probe, tmp_path, monkeypatch
):
    source, executable, output = fixture_paths(tmp_path, probe)

    def fake_run(command, **kwargs):
        env = kwargs["env"]
        assert env["RAFTEL_RUN_THOR_ART1_PROBE"] == "1"
        assert command[1:5] == [
            "-u",
            str((output / "user.cfg").resolve()),
            "-s",
            str((output / "system.cfg").resolve()),
        ]
        assert Path(env["RAFTEL_THOR_ART1_COPY"]).read_bytes() == source.read_bytes()
        assert Path(env["RAFTEL_THOR_ART1_COPY"]).resolve() != source.resolve()
        assert kwargs["timeout"] == 12
        assert kwargs["input"] == ""
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        native = {
            "schema_version": 1,
            "evidence_class": "native_single_document_drift_probe_attempt",
            "audit_status": "complete_probe_not_migration_acceptance",
            "source_and_copy_bytes_unchanged": True,
            "source_sha256_before": digest,
            "copied_source_sha256_before": digest,
            "source_sha256_after": digest,
            "copied_source_sha256_after": digest,
            "capture_script_sha256": hashlib.sha256(PATH.read_bytes()).hexdigest(),
            "native_document_saved": False,
            "migration_accepted": False,
            "freecad_version": ["synthetic subprocess fixture"],
            "source_saved_brep_measurements": dict.fromkeys(probe["FEATURES"], {}),
            "restored_document_measurements": dict.fromkeys(probe["FEATURES"], {}),
            "force_rebuild_attempt_measurements": dict.fromkeys(probe["FEATURES"], {}),
        }
        Path(env["RAFTEL_THOR_ART1_REPORT"]).write_text(json.dumps(native))
        return SimpleNamespace(returncode=0, stdout="synthetic process", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    executable_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
    result = probe["run_probe"](
        executable,
        source,
        output,
        timeout_s=12,
        expected_executable_sha256=executable_sha256,
    )
    assert result["native_probe_completed"]
    assert not result["migration_accepted"]
    assert result["source_and_copy_bytes_unchanged"]
    assert result["native_executable_sha256"] == executable_sha256
    assert result["executable_matches_caller_pin"]
    assert not result["full_runtime_and_addon_bundle_verified"]
    assert (output / "runner.json").is_file()


def test_zero_process_exit_without_completed_native_report_is_not_success(
    probe, tmp_path, monkeypatch
):
    source, executable, output = fixture_paths(tmp_path, probe)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    result = probe["run_probe"](executable, source, output)
    assert not result["native_probe_completed"]
    assert not result["migration_accepted"]


def test_status_label_without_capture_identity_and_coverage_is_not_completion(probe):
    assert not probe["native_report_is_complete"](
        {"audit_status": "complete_probe_not_migration_acceptance"}, "a" * 64
    )


def test_timeout_preserves_copy_logs_and_failure_metadata(probe, tmp_path, monkeypatch):
    source, executable, output = fixture_paths(tmp_path, probe)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0], kwargs["timeout"], output=b"partial native output", stderr=b"diagnostic"
        )

    monkeypatch.setattr(subprocess, "run", timeout)
    result = probe["run_probe"](executable, source, output, timeout_s=0.5)
    assert result["outcome"] == "timed_out"
    assert not result["native_probe_completed"]
    assert (output / "stdout.log").read_text() == "partial native output"
    assert (output / "Art1Body.fcstd").read_bytes() == source.read_bytes()


def test_low_disk_reserve_rejected_before_copy_or_launch(probe, tmp_path, monkeypatch):
    source, executable, output = fixture_paths(tmp_path, probe)
    monkeypatch.setattr(
        probe["run_probe"].__globals__["shutil"],
        "disk_usage",
        lambda path: SimpleNamespace(free=49 * 1024**3),
    )
    with pytest.raises(ValueError, match="50 GiB"):
        probe["run_probe"](executable, source, output)
    assert not output.exists()


@pytest.mark.parametrize("value", [0, -1, 601, math.nan, math.inf, True])
def test_unbounded_or_invalid_timeout_rejected(probe, tmp_path, value):
    source, executable, output = fixture_paths(tmp_path, probe)
    with pytest.raises(ValueError, match="timeout|finite"):
        probe["run_probe"](executable, source, output, timeout_s=value)
    assert not output.exists()


def test_native_mode_requires_explicit_opt_in_before_native_import(probe):
    with pytest.raises(ValueError, match="opt-in"):
        probe["native_capture"]()


def test_wrong_native_executable_pin_rejected_before_copy_or_launch(probe, tmp_path):
    source, executable, output = fixture_paths(tmp_path, probe)
    with pytest.raises(ValueError, match="expected SHA-256"):
        probe["run_probe"](executable, source, output, expected_executable_sha256="a" * 64)
    assert not output.exists()


def test_offline_descriptor_cli_emits_source_only_report_and_never_overwrites(probe, tmp_path):
    output = tmp_path / "support-descriptors.json"
    contract_path = ROOT / "hardware" / "cad" / "thor-art1-desktop-source-fingerprint.json"
    arguments = ["--describe-source-contract", str(contract_path), "--output", str(output)]
    assert probe["main"](arguments) == 0
    result = json.loads(output.read_text())
    assert len(result["supports"]) == 4
    assert not result["native_capture_executed"]
    assert not result["support_remapped"]
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        probe["main"](arguments)
    assert output.read_bytes() == original


def test_copy_hash_mismatch_and_source_alias_are_rejected(probe, tmp_path):
    source, _, output = fixture_paths(tmp_path, probe)
    output.mkdir()
    copied = output / "Art1Body.fcstd"
    copied.write_bytes(b"changed copy")
    report, user, system = output / "probe.json", output / "user.cfg", output / "system.cfg"
    with pytest.raises(ValueError, match="both match"):
        probe["validate_probe_paths"](source, copied, report, user, system)
    with pytest.raises(ValueError, match="all differ"):
        probe["validate_probe_paths"](source, source, report, user, system)


def test_global_preferences_outside_run_directory_are_rejected(probe, tmp_path):
    source, _, output = fixture_paths(tmp_path, probe)
    output.mkdir()
    copied = output / "Art1Body.fcstd"
    copied.write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match="inside"):
        probe["validate_probe_paths"](
            source, copied, output / "probe.json", tmp_path / "user.cfg", output / "system.cfg"
        )


def test_native_existing_session_rejected_without_touching_open_documents(
    probe, tmp_path, monkeypatch
):
    source, _, output = fixture_paths(tmp_path, probe)
    output.mkdir()
    copied = output / "Art1Body.fcstd"
    copied.write_bytes(source.read_bytes())
    env = {
        "RAFTEL_RUN_THOR_ART1_PROBE": "1",
        "RAFTEL_THOR_ART1_SOURCE": str(source),
        "RAFTEL_THOR_ART1_COPY": str(copied),
        "RAFTEL_THOR_ART1_REPORT": str(output / "probe.json"),
        "RAFTEL_THOR_ART1_USER_CFG": str(output / "user.cfg"),
        "RAFTEL_THOR_ART1_SYSTEM_CFG": str(output / "system.cfg"),
        "RAFTEL_THOR_ART1_EXPERIMENT": "unchanged",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    globals_ = probe["native_capture"].__globals__
    monkeypatch.setitem(globals_["DIAGNOSTICS"], "source_fingerprint", lambda *args: {})
    monkeypatch.setitem(
        sys.modules, "FreeCAD", SimpleNamespace(listDocuments=lambda: {"UserOpenDoc": object()})
    )
    monkeypatch.setitem(sys.modules, "Part", SimpleNamespace())
    with pytest.raises(ValueError, match="probe failed"):
        probe["native_capture"]()
    result = json.loads((output / "probe.json").read_text())
    assert result["audit_status"] == "failed_probe"
    assert "no documents already open" in result["errors"][0]["message"]
    assert not result["native_document_saved"]
    assert result["source_and_copy_bytes_unchanged"]
