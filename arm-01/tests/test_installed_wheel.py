"""Wheel identity/resource guards; the actual isolated install is a CI smoke."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "verify_installed_wheel", Path(__file__).parents[1] / "tools/verify_installed_wheel.py"
)
wheel_check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(wheel_check)


def fixture(tmp_path, *, mutation=None):
    prefix = "raftel_arm01-0.1.0.dist-info/"
    files = {
        prefix + "METADATA": (
            'Name: raftel-arm01\nVersion: 0.1.0\nRequires-Dist: pytest==9.0.3; extra == "dev"\n'
        ),
        prefix + "entry_points.txt": (
            "[console_scripts]\nraftel-sort = raftel_arm01.cli:main\n"
            "raftel-evaluate = raftel_arm01.evaluation.cli:main\n"
        ),
        **{
            name: ""
            for name in (
                "raftel_arm01/defaults.json",
                "raftel_arm01/cli.py",
                "raftel_arm01/evaluation/cli.py",
                "raftel_arm01/kinematics/thor_model.py",
                "raftel_arm01/engineering/scenarios.py",
            )
        },
    }
    if mutation:
        mutation(files)
    path = tmp_path / "fixture.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def test_identity_and_resources_inspected_without_importing_wheel(tmp_path):
    report = wheel_check.inspect_wheel(fixture(tmp_path))
    assert report["name"] == "raftel-arm01"
    assert report["runtime_dependencies"] == []
    assert len(report["wheel_sha256"]) == 64


@pytest.mark.parametrize(
    "mutation",
    [
        lambda files: files.update({"../outside.py": ""}),
        lambda files: files.update({"unrelated/__init__.py": ""}),
        lambda files: files.update({"raftel_arm01/cli.py:stream": ""}),
        lambda files: files.update(
            {"C:/unexpected.dist-info/METADATA": "Name: raftel-arm01\nVersion: 0.1.0\n"}
        ),
        lambda files: files.pop("raftel_arm01/defaults.json"),
        lambda files: files.update(
            {"raftel_arm01-0.1.0.dist-info/METADATA": "Name: unrelated\nVersion: 0.1.0\n"}
        ),
        lambda files: files.update(
            {
                "raftel_arm01-0.1.0.dist-info/METADATA": (
                    "Name: raftel-arm01\nVersion: 0.1.0\nRequires-Dist: hardware-driver\n"
                )
            }
        ),
        lambda files: files.update({"raftel_arm01-0.1.0.dist-info/entry_points.txt": "not ini"}),
        lambda files: files.update(
            {
                "raftel_arm01-0.1.0.dist-info/METADATA": (
                    "Name: raftel-arm01\nName: conflicting\nVersion: 0.1.0\n"
                )
            }
        ),
        lambda files: files.update(
            {
                "raftel_arm01-0.1.0.dist-info/entry_points.txt": (
                    "[console_scripts]\narm-real-motion = secret:main\n"
                )
            }
        ),
    ],
)
def test_unexpected_identity_dependency_path_or_entrypoints_reject_before_install(
    tmp_path, mutation
):
    with pytest.raises(ValueError):
        wheel_check.inspect_wheel(fixture(tmp_path, mutation=mutation))


def test_existing_scratch_and_invalid_timeout_preserve_files(tmp_path):
    wheel = fixture(tmp_path)
    existing = tmp_path / "retained"
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("retained evidence")
    with pytest.raises(FileExistsError):
        wheel_check.verify_wheel(wheel, existing)
    assert marker.read_text() == "retained evidence"
    for timeout in (True, 0, 601):
        with pytest.raises(ValueError):
            wheel_check.verify_wheel(wheel, tmp_path / "new", timeout_s=timeout)
    assert not (tmp_path / "new").exists()
