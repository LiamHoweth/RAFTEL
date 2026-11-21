"""Reproduce mock scenes and check that exports reflect observed mock outcomes."""

import json
from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest

from raftel_arm01.cli import main
from raftel_arm01.config import load_config
from raftel_arm01.control.interface import ArmFault
from raftel_arm01.control.mock import MockArm
from raftel_arm01.demo import run_report
from raftel_arm01.perception.synthetic import generate_objects
from raftel_arm01.scene import load_scene, scene_data
from raftel_arm01.tasks.sorter import Sorter

FAILURE_SCENE = Path(__file__).resolve().parents[1] / "config" / "benchsort-failure.json"
SVG_NS = "{http://www.w3.org/2000/svg}"


def test_seeded_demo_is_byte_reproducible_and_routes_to_recorded_bins(tmp_path):
    reports, plots = [], []
    for index in range(2):
        report, plot = tmp_path / f"run-{index}.json", tmp_path / f"run-{index}.svg"
        assert main(["--seed", "42", "--report", str(report), "--svg", str(plot)]) == 0
        reports.append(report.read_bytes())
        plots.append(plot.read_bytes())
    assert reports[0] == reports[1] and plots[0] == plots[1]
    assert b"\r" not in reports[0] + plots[0]

    record = json.loads(reports[0])
    assert record["seed"] == 42 and record["evidence_class"] == "logical_only"
    assert record["scene"] == scene_data(generate_objects(42))
    assert record["summary"]["sorted"] == 10
    bins = {row["category"]: row["position"] for row in record["config"]["bins"]}
    for outcome in record["outcomes"]:
        assert outcome["terminal_state"] == "sorted" and outcome["attempts"] == 1
        assert outcome["mock_recorded_bin"] == outcome["target_bin"]
        assert outcome["mock_recorded_placement_m"] == bins[outcome["target_bin"]]

    plot = fromstring(plots[0])
    assert plot.tag == f"{SVG_NS}svg" and plot.attrib["role"] == "img"
    desc = plot.findtext(f"{SVG_NS}desc")
    assert "10 starting object poses" in desc and "10 confirmed mock placements" in desc


def test_mixed_scene_reports_three_outcomes_and_can_be_replayed(tmp_path):
    scene_copy, config = tmp_path / "scene.json", tmp_path / "config.json"
    reports = []
    for index in range(2):
        source = ["--scene", str(scene_copy if index else FAILURE_SCENE)]
        report, plot = tmp_path / f"failure-{index}.json", tmp_path / f"failure-{index}.svg"
        args = source + ["--report", str(report), "--svg", str(plot), "--fail-grasp", "red-retry"]
        if index:
            args += ["--config", str(config)]
        assert main(args) == 1
        reports.append(report.read_bytes())
        if not index:
            original = json.loads(reports[0])
            scene_copy.write_text(json.dumps(original["scene"]), encoding="utf-8")
            config.write_text(json.dumps(original["config"]), encoding="utf-8")
        plot_desc = fromstring(plot.read_bytes()).findtext(f"{SVG_NS}desc")
        assert "4 starting object poses and 1 confirmed mock placements" in plot_desc
    assert reports[0] == reports[1]
    assert original["seed"] is None
    assert original["summary"] == {
        "simulation": "logical_only",
        "sorted": 1,
        "skipped": 2,
        "failed": 1,
        "aborted": False,
        "pending": 0,
    }
    outcomes = {row["object_id"]: row for row in original["outcomes"]}
    assert outcomes["blue-at-edge"]["mock_recorded_bin"] == "blue"
    assert outcomes["green-overweight"]["detail"] == "payload exceeds logical limit"
    assert outcomes["red-outside"]["detail"] == "position outside logical envelope"
    failure = outcomes["red-retry"]
    assert failure["terminal_state"] == "failed" and failure["attempts"] == 2
    assert failure["mock_recorded_bin"] is None and failure["mock_recorded_placement_m"] is None


def test_report_distinguishes_abort_cause_from_pending_objects():
    class FailingArm(MockArm):
        def move_to(self, position):
            raise ArmFault("injected feedback timeout")

    config = load_config()
    arm = FailingArm(config.envelope)
    objects = generate_objects(42, 2)
    result = Sorter(arm, config).run(objects)
    report = run_report(config, objects, result, arm.placements, seed=42, failures=set())
    first, second = report["outcomes"]
    assert first["terminal_state"] == "aborted" and first["attempts"] == 1
    assert second["terminal_state"] == "pending" and second["attempts"] == 0
    assert first["detail"] == "injected feedback timeout" and report["summary"]["aborted"]


@pytest.mark.parametrize(
    ("source", "replacement"),
    [
        ('"arm_base"', '"camera"'),
        ('"schema_version": 1', '"schema_version": true'),
        ('"x": 0.28', '"x": NaN'),
        ('"x": 0.28', '"x": true'),
        ('"x": 0.28', '"x": 0.28, "x": 0.1'),
        ('"z": 0.02', '"height": 0.02'),
        ('"mass_kg": 0.02', '"mass_kg": 0.02, "note": "unexpected"'),
        ('"red-outside"', '"red-retry"'),
    ],
)
def test_scene_invalid_data_is_rejected_before_output(tmp_path, source, replacement):
    scene, output = tmp_path / "invalid.json", tmp_path / "must-not-exist.json"
    text = FAILURE_SCENE.read_text(encoding="utf-8").replace(source, replacement, 1)
    scene.write_text(text, encoding="utf-8")
    assert main(["--scene", str(scene), "--report", str(output)]) == 2
    assert not output.exists()


def test_scene_modes_and_output_paths_are_safe(tmp_path):
    scene, svg, report = [tmp_path / name for name in ("scene.json", "run.svg", "run.json")]
    initial = FAILURE_SCENE.read_bytes()
    scene.write_bytes(initial)
    args = ["--scene", str(scene)]
    assert load_scene(scene) == load_scene(FAILURE_SCENE)
    assert main(args + ["--seed", "42"]) == 2
    assert main(args + ["--log", str(scene)]) == 2
    assert scene.read_bytes() == initial
    assert main(args + ["--svg", str(report), "--report", str(report)]) == 2
    absent_parent = tmp_path / "absent" / "new.svg"
    assert main(args + ["--report", str(report), "--svg", str(absent_parent)]) == 2
    assert not report.exists()
    svg.write_bytes(b"prior")
    assert main(args + ["--svg", str(svg), "--report", str(report)]) == 2
    assert svg.read_bytes() == b"prior" and not report.exists()


def test_reading_excessively_nested_scene_returns_input_error(tmp_path):
    path = tmp_path / "deep.json"
    path.write_text("[" * 10_000 + "]" * 10_000, encoding="utf-8")
    assert main(["--scene", str(path)]) == 2


def test_svg_handles_rejected_extreme_coordinates_and_xml_markup(tmp_path):
    scene = scene_data(generate_objects(42, 2))
    scene["objects"][0]["identifier"] = "<seed & pose\x01>"
    scene["objects"][0]["position"]["x"] = 1.7e308
    scene["objects"][1]["position"]["x"] = -1.7e308
    path, svg = tmp_path / "edge.json", tmp_path / "edge.svg"
    path.write_text(json.dumps(scene), encoding="utf-8")
    assert main(["--scene", str(path), "--svg", str(svg)]) == 0
    markup = svg.read_text(encoding="utf-8")
    assert "&lt;seed &amp; pose" in markup
    plot = fromstring(markup)
    assert "0 confirmed mock placements" in plot.findtext(f"{SVG_NS}desc")
