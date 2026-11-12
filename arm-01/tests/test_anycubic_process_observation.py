"""Bounded project settings observations keep software/physical evidence separate."""

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "anycubic_process_observation", ROOT / "tools/anycubic_process_observation.py"
)
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


class Archive:
    sha256 = "a" * 64
    size = 10000

    def __init__(self, settings=None, raw=None):
        self.data = raw if raw is not None else json.dumps(settings).encode()
        self.names = () if settings is None and raw is None else (observer.MEMBER, "private.json")
        self.reads = []

    def read(self, name, *, max_bytes):
        self.reads.append(name)
        assert name == observer.MEMBER
        assert max_bytes == observer.MAX_SETTINGS_BYTES
        return self.data


def test_existing_local_contract_and_secret_exclusion():
    baseline = json.loads((ROOT / "hardware/print-planning/local-profile-audit.json").read_bytes())
    selected = baseline["saved_selection"]["profile_fields"]
    settings = {
        "printer_settings_id": selected["machine"],
        "print_settings_id": selected["process"],
        "filament_settings_id": [selected["filament"]] * 5,
        "curr_bed_type": selected["curr_bed_type"],
        "account": {"PCID": "SECRET_SENTINEL"},
        "customGcode": "PRIVATE_GCODE_SENTINEL",
    }
    for group in baseline["profiles"].values():
        settings.update(
            {
                key: value
                for key, value in group["resolved_allowlisted_fields"].items()
                if key in observer.ALLOWED
            }
        )
    archive = Archive(settings)
    result = observer.observe_project_profiles(archive)
    assert archive.reads == [observer.MEMBER]
    assert result["saved_selection"]["profile_fields"] == {
        key: selected[key] for key in ("machine", "process", "curr_bed_type")
    }
    assert len(result["saved_selection"]["project_filament_entries"]) == 5
    assert result["saved_selection"]["project_filament_shape"] == "array"
    assert all(value is None for value in result["physical_confirmation"].values())
    assert result["saved_selection"]["is_live_gui_state"] is False
    assert result["saved_selection"]["is_physical_hardware_confirmation"] is False
    assert result["unknown_field_count"] == 2
    serialized = json.dumps(result)
    assert "SECRET_SENTINEL" not in serialized
    assert "PRIVATE_GCODE_SENTINEL" not in serialized
    assert "PCID" not in serialized
    assert result["settings_member_sha256"] == hashlib.sha256(archive.data).hexdigest()
    assert result["source_units"]["filament_density"] == "g/cm^3"


def test_missing_metadata_is_unknown_not_defaulted_to_previous_selection():
    archive = Archive()
    result = observer.observe_project_profiles(archive)
    assert archive.reads == []
    assert result["settings_status"] == "unknown_absent_member"
    assert result["saved_selection"]["profile_fields"] == {}
    assert result["settings_member_sha256"] is None
    assert all(not group["resolved_allowlisted_fields"] for group in result["profiles"].values())


@pytest.mark.parametrize(
    "raw",
    [
        b'{"layer_height":"0.2","layer_height":"0.3"}',
        b'{"unknown":{"PCID":1,"PCID":2}}',
        b'{"layer_height":NaN}',
        b'{"layer_height":Infinity}',
        b'{"unknown":1e999}',
        b"[]",
        b"{bad PRIVATE_SENTINEL}",
        b"\xff",
        b"[" * 33 + b"0" + b"]" * 33,
    ],
)
def test_malformed_settings_fail_without_echoing_content(raw):
    with pytest.raises(ValueError) as exc:
        observer.observe_project_profiles(Archive(raw=raw))
    assert "PRIVATE_SENTINEL" not in str(exc.value)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("nozzle_diameter", ["0"]),
        ("layer_height", "nan"),
        ("layer_height", "1e999"),
        ("layer_height", True),
        ("wall_loops", "2.5"),
        ("sparse_infill_density", "0.15"),
        ("sparse_infill_density", "101%"),
        ("enable_support", "false"),
        ("printer_settings_id", ["wrong shape"]),
        ("filament_settings_id", []),
        ("filament_settings_id", ["a"] * 17),
        ("print_settings_id", "multiline\nvalue"),
        ("print_settings_id", "a" * 257),
        ("printable_area", ["0xnan"]),
        ("printable_area", ["0x1x2"]),
        ("printable_area", "0x1"),
        ("nozzle_temperature", {"unknown": 210}),
    ],
)
def test_allowlisted_invalid_shapes_units_and_bounds_reject(key, value):
    with pytest.raises(ValueError):
        observer.observe_project_profiles(Archive({key: value}))


def test_size_key_and_nesting_limits_and_ignored_json_strings():
    with pytest.raises(ValueError, match="size bound"):
        observer.observe_project_profiles(Archive(raw=b" " * (observer.MAX_SETTINGS_BYTES + 1)))
    with pytest.raises(ValueError, match="field bound"):
        observer.observe_project_profiles(Archive({str(i): 1 for i in range(4097)}))
    result = observer.observe_project_profiles(Archive({"unknown": '[{"' * 100}))
    assert result["unknown_field_count"] == 1
    assert result["saved_selection"]["profile_fields"] == {}


def test_unknown_custom_selector_is_withheld_without_claiming_baseline_match():
    result = observer.observe_project_profiles(
        Archive({"printer_settings_id": "Other software profile", "filament_type": ["PETG"]})
    )
    assert "machine" not in result["saved_selection"]["profile_fields"]
    assert result["unknown_value_fields"] == ["printer_settings_id"]
    assert "Other software profile" not in json.dumps(result)
    assert result["profiles"]["filament"]["resolved_allowlisted_fields"] == {
        "filament_type": ["PETG"]
    }
    assert result["physical_confirmation"]["loaded_filament_material"] is None


def test_heterogeneous_filament_array_keeps_exact_indices_without_slot_aliases():
    materials = [f"Anycubic {material} @{observer.MACHINE}" for material in ("PLA", "PETG", "ABS")]
    result = observer.observe_project_profiles(Archive({"filament_settings_id": materials}))
    selected = result["saved_selection"]
    assert selected["project_filament_entries"] == [
        {"project_array_index": index, "profile_id": value} for index, value in enumerate(materials)
    ]
    assert selected["profile_fields"] == {}


def test_shared_archive_cli_output_preservation_and_sanitized_failure(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    project = tmp_path / "draft.3mf"
    output = tmp_path / "observation.json"
    with zipfile.ZipFile(project, "w") as archive:
        archive.writestr(observer.MEMBER, json.dumps({"printer_settings_id": observer.MACHINE}))
        archive.writestr("private.json", b"PRIVATE_SENTINEL")
    before = project.read_bytes()
    assert observer.main([str(project), "--output", str(output)]) == 0
    contents = output.read_bytes()
    assert b"\r" not in contents
    assert b"PRIVATE_SENTINEL" not in contents
    assert json.loads(contents)["saved_selection"]["profile_fields"]["machine"] == observer.MACHINE
    with pytest.raises(SystemExit) as exc:
        observer.main([str(project), "--output", str(output)])
    assert exc.value.code == 2
    assert output.read_bytes() == contents
    assert project.read_bytes() == before
    project.write_bytes(b"PRIVATE_SENTINEL not a ZIP")
    with pytest.raises(SystemExit) as exc:
        observer.main([str(project), "--output", str(tmp_path / "new.json")])
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "BadZipFile" in error
    assert "PRIVATE_SENTINEL" not in error
    assert str(project) not in error


def test_shared_archive_prechecks_settings_member_size(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    from audit_anycubic_draft_project import ProjectArchive

    project = tmp_path / "large-settings.3mf"
    with zipfile.ZipFile(project, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(observer.MEMBER, b" " * (observer.MAX_SETTINGS_BYTES + 1))
    with ProjectArchive(project) as archive:
        # No decompression/read is needed: directory size must reject first.
        def unexpected_open(*_args, **_kwargs):
            pytest.fail("oversized member must reject before opening it")

        monkeypatch.setattr(archive._archive, "open", unexpected_open)
        with pytest.raises(ValueError):
            observer.observe_project_profiles(archive)
