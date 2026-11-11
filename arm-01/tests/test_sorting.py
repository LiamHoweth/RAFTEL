import json
import subprocess
import sys
from dataclasses import replace

import pytest

from raftel_arm01.cli import main
from raftel_arm01.config import load_config
from raftel_arm01.control.interface import ArmFault
from raftel_arm01.control.mock import MockArm
from raftel_arm01.models import Bin, ObjectPose, Position
from raftel_arm01.perception.synthetic import generate_objects
from raftel_arm01.planning.sorting import plan
from raftel_arm01.safety.envelope import Envelope
from raftel_arm01.tasks.sorter import Sorter


def test_ten_objects_verified_in_correct_bins():
    config = load_config()
    arm = MockArm(config.envelope)
    objects = generate_objects(42)
    result = Sorter(arm, config).run(objects)
    assert len(result.sorted_ids) == 10
    assert not result.failed_ids and not result.skipped_ids and not result.aborted
    for obj in objects:
        destination = next(b.position for b in config.bins if b.category == obj.category)
        assert arm.placements[obj.identifier] == destination
    assert arm.held is None
    assert result.events[-1].state == "complete"
    assert [e.sequence for e in result.events] == list(range(len(result.events)))


def test_seed_repeatability_and_variable_positions():
    config = load_config()
    first = generate_objects(42)
    assert first == generate_objects(42)
    assert first != generate_objects(43)
    one = Sorter(MockArm(config.envelope), config).run(first)
    two = Sorter(MockArm(config.envelope), config).run(list(reversed(first)))
    assert one == two
    assert one.summary()["simulation"] == "logical_only"


def test_unreachable_skipped_before_any_motion():
    config = load_config()
    arm = MockArm(config.envelope)
    obj = ObjectPose("far", "red", Position(0, 0.8, 0), 0.02)
    result = Sorter(arm, config).run([obj])
    assert result.skipped_ids == ("far",)
    assert arm.position is None
    assert not result.aborted


def test_failed_grasp_retries_bounded_and_next_object_continues():
    config = load_config()
    objects = generate_objects(1, 2)
    arm = MockArm(config.envelope, {"object-00"})
    result = Sorter(arm, config).run(objects)
    assert result.failed_ids == ("object-00",)
    assert result.sorted_ids == ("object-01",)
    attempts = [
        e.attempt for e in result.events if e.object_id == "object-00" and e.state == "grasp"
    ]
    assert attempts == [1, 2]
    assert arm.held is None and not arm.stopped


@pytest.mark.parametrize("case", ["overweight", "unknown", "approach_outside"])
def test_invalid_pick_plan_never_moves(case):
    config = load_config()
    obj = ObjectPose("bad", "red", Position(0, 0.2, 0.02), 0.02)
    if case == "overweight":
        obj = replace(obj, mass_kg=0.2)
    elif case == "unknown":
        obj = replace(obj, category="unclassified")
    else:
        obj = replace(obj, position=Position(0, 0.2, 0.34))
    arm = MockArm(config.envelope)
    result = Sorter(arm, config).run([obj])
    assert result.skipped_ids == ("bad",)
    assert arm.position is None


def test_motion_fault_latches_stop_and_aborts_remaining():
    class FaultArm(MockArm):
        def move_to(self, position):
            raise ArmFault("injected feedback timeout")

    config = load_config()
    arm = FaultArm(config.envelope)
    result = Sorter(arm, config).run(generate_objects(2, 2))
    assert result.aborted and arm.stopped
    assert not result.sorted_ids
    assert result.failed_ids == ("object-00",)
    assert result.pending_ids == ("object-01",)
    assert not any(e.object_id == "object-01" for e in result.events)
    with pytest.raises(ArmFault):
        arm.grasp(generate_objects(2, 1)[0])


def test_failed_placement_does_not_claim_sorted():
    class UncertainArm(MockArm):
        def verify_placement(self, obj, destination):
            return False

    config = load_config()
    arm = UncertainArm(config.envelope)
    result = Sorter(arm, config).run(generate_objects(3, 2))
    assert result.aborted and arm.stopped
    assert not result.sorted_ids
    assert "uncertain" in result.events[-1].detail


def test_transfer_fault_preserves_held_state():
    class TransferFault(MockArm):
        def move_to(self, position):
            if self.held:
                raise ArmFault("transfer blocked")
            super().move_to(position)

    config = load_config()
    arm = TransferFault(config.envelope)
    result = Sorter(arm, config).run(generate_objects(1, 1))
    assert result.aborted and arm.stopped and arm.held is not None
    assert not arm.placements


def test_success_after_transient_grasp_failure():
    class TransientArm(MockArm):
        failures = 0

        def grasp(self, obj):
            if self.failures == 0:
                self.failures += 1
                return False
            return super().grasp(obj)

    config = load_config()
    result = Sorter(TransientArm(config.envelope), config).run(generate_objects(1, 1))
    assert result.sorted_ids == ("object-00",)
    assert not result.failed_ids
    assert next(e.attempt for e in result.events if e.state == "sorted") == 2


def test_duplicate_ids_rejected_before_motion():
    config = load_config()
    arm = MockArm(config.envelope)
    obj = generate_objects(1, 1)[0]
    with pytest.raises(ValueError, match="duplicate"):
        Sorter(arm, config).run([obj, obj])
    assert arm.position is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_positions_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        Position(value, 0, 0)


@pytest.mark.parametrize("mass", [0, -1, float("nan"), float("inf")])
def test_invalid_mass_rejected(mass):
    with pytest.raises(ValueError):
        ObjectPose("test", "red", Position(0, 0.2, 0), mass)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_radius_m": -1},
        {"max_payload_kg": 0},
        {"min_z_m": 1},
        {"max_radius_m": float("nan")},
    ],
)
def test_invalid_envelopes_rejected(kwargs):
    with pytest.raises(ValueError):
        Envelope(**kwargs)


@pytest.mark.parametrize(
    "change",
    [
        {"max_attempts": 0},
        {"max_attempts": True},
        {"max_attempts": 1.5},
        {"clearance_m": -1},
        {"clearance_m": float("nan")},
        {"bins": ()},
    ],
)
def test_invalid_config_rejected(change):
    with pytest.raises(ValueError):
        replace(load_config(), **change)


def test_bin_approach_checked():
    config = load_config()
    invalid_bins = (Bin("red", Position(0, 0.2, 0.34)), *config.bins[1:])
    with pytest.raises(ValueError):
        replace(config, bins=invalid_bins)


def test_config_roundtrip_and_frame_validation(tmp_path):
    from importlib.resources import files

    data = json.loads(files("raftel_arm01").joinpath("defaults.json").read_text())
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    assert load_config(path) == load_config()
    data["frame"] = "camera"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="frame"):
        load_config(path)


def test_plan_tracks_changed_object_pose():
    config = load_config()
    obj = generate_objects(2, 1)[0]
    shifted = replace(obj, position=Position(0.05, 0.22, 0.02))
    assert plan(obj, config).pickup != plan(shifted, config).pickup
    assert plan(shifted, config).pickup == shifted.position


def test_cli_structured_log_and_summary(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    assert main(["--seed", "42", "--unreachable", "--log", str(path)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "simulation": "logical_only",
        "sorted": 10,
        "skipped": 1,
        "failed": 0,
        "aborted": False,
        "pending": 0,
    }
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[0]["state"] == "observe" and records[-1]["state"] == "complete"
    assert all(set(r) == {"sequence", "state", "object_id", "attempt", "detail"} for r in records)


def test_cli_failure_and_invalid_input_exit_codes(capsys):
    assert main(["--fail-grasp", "object-00"]) == 1
    assert main(["--count", "0"]) == 2
    assert main(["--fail-grasp", "typo"]) == 2
    assert "unknown object" in capsys.readouterr().err


def test_installed_module_entry_point():
    result = subprocess.run(
        [sys.executable, "-m", "raftel_arm01.cli", "--count", "1"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout.splitlines()[-1])["sorted"] == 1


def test_custom_categories_drive_synthetic_detection(tmp_path, capsys):
    from importlib.resources import files

    data = json.loads(files("raftel_arm01").joinpath("defaults.json").read_text())
    for b, category in zip(data["bins"], ("metal", "wood", "plastic"), strict=True):
        b["category"] = category
    path = tmp_path / "custom.json"
    path.write_text(json.dumps(data))
    assert main(["--config", str(path), "--count", "3"]) == 0
    summary = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert summary["sorted"] == 3 and summary["skipped"] == 0


@pytest.mark.parametrize("count", [-1, 0, 1001])
def test_synthetic_count_limits(count):
    with pytest.raises(ValueError):
        generate_objects(1, count)


def test_empty_scene_finishes_without_motion():
    config = load_config()
    arm = MockArm(config.envelope)
    result = Sorter(arm, config).run([])
    assert not result.sorted_ids and not result.aborted
    assert arm.position is None and result.events[-1].state == "complete"


def test_unexpected_backend_exception_stops_then_surfaces():
    class BrokenArm(MockArm):
        def move_to(self, position):
            raise RuntimeError("unexpected driver bug")

    config = load_config()
    arm = BrokenArm(config.envelope)
    with pytest.raises(RuntimeError, match="driver bug"):
        Sorter(arm, config).run(generate_objects(1, 1))
    assert arm.stopped


@pytest.mark.parametrize(
    "position,expected",
    [
        (Position(0, 0.06, 0), True),
        (Position(0, 0.4, 0), True),
        (Position(0, 0.059999, 0), False),
        (Position(0, 0.400001, 0), False),
        (Position(0, 0.1, -0.000001), False),
        (Position(0, 0.1, 0.350001), False),
    ],
)
def test_envelope_boundaries(position, expected):
    assert Envelope().contains(position) is expected


def test_exact_payload_limit_allowed():
    config = load_config()
    obj = replace(generate_objects(1, 1)[0], mass_kg=config.envelope.max_payload_kg)
    result = Sorter(MockArm(config.envelope), config).run([obj])
    assert result.sorted_ids == (obj.identifier,)


@pytest.mark.parametrize(
    "identifier,category", [(42, "red"), ("test", 42), (" ", "red"), ("test", " ")]
)
def test_invalid_object_labels(identifier, category):
    with pytest.raises(ValueError):
        ObjectPose(identifier, category, Position(0, 0.2, 0), 0.02)


def test_unknown_config_keys_rejected(tmp_path):
    from importlib.resources import files

    data = json.loads(files("raftel_arm01").joinpath("defaults.json").read_text())
    data["hardware"] = True
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unexpected"):
        load_config(path)
