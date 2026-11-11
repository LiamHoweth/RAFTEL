"""Check the independent analytical expectations used by the native fixture."""

import runpy
from pathlib import Path

import pytest

FIXTURE = runpy.run_path(
    str(Path(__file__).parents[1] / "tools" / "verify_freecad_shape_frames.py")
)


def records():
    return [
        {"name": name, "shape_center_mm": list(center)}
        for name, center in FIXTURE["EXPECTED_CENTERS_MM"].items()
    ]


def test_fixture_requires_all_independent_native_cases():
    FIXTURE["verify_records"](records())
    with pytest.raises(ValueError, match="missing"):
        FIXTURE["verify_records"](records()[:-1])
    with pytest.raises(ValueError, match="duplicated"):
        FIXTURE["verify_records"](records() + [records()[0]])


@pytest.mark.parametrize(
    "name",
    [
        "Source",
        "LinkFalse",
        "LinkTrue",
        "Child",
        "GroupLinkFalse",
        "GroupLinkTrue",
        "NestedLink",
        "RotatedFalse",
        "RotatedTrue",
    ],
)
def test_fixture_detects_double_placement_or_wrong_native_frame(name):
    changed = records()
    record = next(record for record in changed if record["name"] == name)
    record["shape_center_mm"][0] += 10
    with pytest.raises(ValueError, match=name):
        FIXTURE["verify_records"](changed)


def test_recorded_native_fixture_matches_analytical_contract():
    import json

    path = Path(__file__).with_name("fixtures") / "freecad_shape_frames_native.json"
    report = json.loads(path.read_text())
    assert report["native_fixture_verified"] and not report["saved_cad_files"]
    assert report["freecad_version"][:3] == ["1", "1", "4"]
    FIXTURE["verify_records"](report["cases"])
