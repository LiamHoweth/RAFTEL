import json
import runpy
from pathlib import Path

import pytest

resolve_aliases = runpy.run_path(
    str(Path(__file__).parents[1] / "tools" / "resolve_thor_case_aliases.py")
)["resolve_aliases"]


def inventory(tmp_path, alias="Part.FCStd", target="Part.fcstd"):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"reference_filename_case_mismatches": {alias: [target]}}))
    return path


def test_case_alias_preserves_original_and_is_idempotent(tmp_path):
    source = tmp_path / "Part.fcstd"
    source.write_bytes(b"source CAD")
    manifest = inventory(tmp_path)
    result = resolve_aliases(tmp_path, manifest, apply=True)
    assert result["unresolved_without_apply"] == 0
    assert (tmp_path / "Part.FCStd").read_bytes() == b"source CAD"
    assert source.read_bytes() == b"source CAD"
    assert not resolve_aliases(tmp_path, manifest, apply=True)["created_aliases"]


def test_dry_run_does_not_create_missing_alias(tmp_path):
    source = tmp_path / "Part.fcstd"
    source.write_bytes(b"source CAD")
    manifest = inventory(tmp_path)
    result = resolve_aliases(tmp_path, manifest)
    assert not result["created_aliases"]
    assert source.read_bytes() == b"source CAD"


def test_outside_directory_alias_rejected(tmp_path):
    (tmp_path / "Part.fcstd").write_bytes(b"source CAD")
    with pytest.raises(ValueError, match="sibling"):
        resolve_aliases(tmp_path, inventory(tmp_path, alias="../Part.FCStd"), apply=True)


def test_existing_different_file_is_never_replaced(tmp_path):
    (tmp_path / "Part.fcstd").write_bytes(b"source CAD")
    (tmp_path / "Different.FCStd").write_bytes(b"protected")
    with pytest.raises(ValueError, match="conflicts"):
        resolve_aliases(tmp_path, inventory(tmp_path, alias="Different.FCStd"), apply=True)
    assert (tmp_path / "Different.FCStd").read_bytes() == b"protected"
