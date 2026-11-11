"""Independent geometry/coverage/energy checks for the conditional jaw overlay."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from raftel_arm01.kinematics.thor_jaw_bodies import (
    canonical_sha256,
    jaw_body_states,
    validate_jaw_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
CAD = ROOT / "hardware/cad"
LEDGER = CAD / "thor-jaw-body-ledger.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def ledger():
    return _load(LEDGER)


def _local(frame, value, *, vector=False):
    point = value if vector else tuple(value[i] - frame[i][3] for i in range(3))
    return tuple(sum(frame[j][i] * point[j] for j in range(3)) for i in range(3))


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "jaw_load_tool", ROOT / "tools/thor_load_analysis.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _expanded():
    inventory = _load(CAD / "thor-mounted-geometry-v2.json")
    membership = _load(CAD / "thor-wrist-membership-v2.json")
    tool = _load_tool()
    snapshot = tool.build_thor_snapshot(
        inventory, instance_mass_overrides=membership["instance_mass_overrides"]
    )
    return tool.expand_mass_assignments(snapshot, membership)


def test_complete_jaw_scope_and_existing_mass_record_ids(ledger):
    inventory = _load(CAD / "thor-mounted-geometry-v2.json")
    membership = _load(CAD / "thor-wrist-membership-v2.json")
    validate_jaw_ledger(ledger, inventory, membership)
    records = ledger["records"]
    assert len(records) == 66
    assert ledger["motion_counts"] == {
        "finger_translation": 10,
        "jaw_fixed": 48,
        "link_rotation": 8,
    }
    mass = _expanded()
    assert len(mass["bodies"]) == 517
    by_id = {body["id"]: body for body in mass["bodies"]}
    saved = jaw_body_states(ledger, mode="saved")
    for identifier, state in saved.items():
        assert identifier in by_id
        x, y, z = state.position_m
        assert by_id[identifier]["com_m"] == pytest.approx((y, -x, z), abs=1e-14)
        assert state.derivative_m_rad == (0, 0, 0)
    servo = [
        record for record in records if record["source_object"] == "AssemblyArt56::Compound002"
    ]
    assert len(servo) == 1
    assert by_id[servo[0]["mass_record_id"]]["mass_kg"] == 0.055
    assert servo[0]["jaw_motion_class"] == "jaw_fixed"
    motor_total = sum(
        b["mass_kg"]
        for b in mass["bodies"]
        if b["mass_assignment"]["category"].startswith("manufacturer_motor_mass_")
    )
    assert motor_total == pytest.approx(2.120)


def test_saved_and_ideal_zero_are_explicitly_different(ledger):
    saved = jaw_body_states(ledger, mode="saved")
    ideal = jaw_body_states(ledger, 0)
    frame = ledger["native_from_gripper_bot"]
    normalizations = ledger["ideal_zero_normalizations"]
    active = normalizations["active_driven"]
    assert active["ideal_pivot_bot_m"][0] - active["saved_pivot_bot_m"][0] == pytest.approx(15e-6)
    assert math.degrees(active["saved_closing_phase_rad"]) == pytest.approx(0.279637283, abs=1e-9)
    assert math.degrees(
        normalizations["passive_driven"]["saved_closing_phase_rad"]
    ) == pytest.approx(0.25, abs=1e-10)
    active_id = next(
        r["mass_record_id"]
        for r in ledger["records"]
        if r["source_object"].endswith("::GripperActiveArm_GripperActiveArm")
    )
    assert math.dist(saved[active_id].position_m, ideal[active_id].position_m) > 1e-5
    for record in ledger["records"]:
        key = record["mass_record_id"]
        if record["jaw_motion_class"] == "finger_translation":
            assert ideal[key].position_m == saved[key].position_m
        if record["jaw_motion_class"] == "link_rotation":
            local_saved = _local(frame, saved[key].position_m)
            local_ideal = _local(frame, ideal[key].position_m)
            old_radius = math.dist(local_saved, record["saved_pivot_bot_m"])
            new_radius = math.dist(local_ideal, record["ideal_pivot_bot_m"])
            assert new_radius == pytest.approx(old_radius, abs=1e-13)


def test_independent_finger_displacements_and_axis_rotation(ledger):
    q = math.pi / 3
    states = jaw_body_states(ledger, q)
    saved = jaw_body_states(ledger, mode="saved")
    frame = ledger["native_from_gripper_bot"]
    for record in ledger["records"]:
        key = record["mass_record_id"]
        delta = tuple(states[key].position_m[i] - saved[key].position_m[i] for i in range(3))
        if record["jaw_motion_class"] == "finger_translation":
            assert _local(frame, delta, vector=True) == pytest.approx(
                (-record["side"] * 0.0175, 0.035 * math.sqrt(3) / 2, 0), abs=1e-13
            )
            assert math.hypot(*states[key].derivative_m_rad) == pytest.approx(0.035)
        elif record["jaw_motion_class"] == "jaw_fixed":
            assert delta == (0, 0, 0)


def test_all_com_derivatives_match_finite_differences(ledger):
    rng = random.Random(104)
    step = 1e-6
    for _ in range(25):
        q = rng.uniform(0.001, math.pi / 2 - 0.001)
        state = jaw_body_states(ledger, q)
        lower = jaw_body_states(ledger, q - step)
        upper = jaw_body_states(ledger, q + step)
        for key, value in state.items():
            finite_difference = tuple(
                (upper[key].position_m[i] - lower[key].position_m[i]) / (2 * step) for i in range(3)
            )
            assert value.derivative_m_rad == pytest.approx(finite_difference, abs=1e-10)


def test_independent_mass_weighted_potential_and_virtual_work(ledger):
    by_id = {body["id"]: body["mass_kg"] for body in _expanded()["bodies"]}
    gravity = (-2.5, 3.25, -8.75)  # An arbitrary frame orientation exercises every component.
    step = 1e-6

    def potential(q):
        return -sum(
            by_id[key] * sum(gravity[i] * state.position_m[i] for i in range(3))
            for key, state in jaw_body_states(ledger, q).items()
        )

    for q in (0.01, 0.3, 0.8, 1.4):
        torque = sum(
            by_id[key] * sum(gravity[i] * state.derivative_m_rad[i] for i in range(3))
            for key, state in jaw_body_states(ledger, q).items()
        )
        assert torque == pytest.approx(
            -(potential(q + step) - potential(q - step)) / (2 * step), abs=2e-9
        )
    assert sum(by_id[key] for key in jaw_body_states(ledger, 0)) == sum(
        by_id[key] for key in jaw_body_states(ledger, 1.4)
    )


@pytest.mark.parametrize("angle", [True, None, "0", math.nan, math.inf, -0.1, math.pi / 2])
def test_invalid_ideal_coordinates_rejected(ledger, angle):
    with pytest.raises(ValueError):
        jaw_body_states(ledger, angle)


def test_saved_coordinate_cannot_be_silently_relabelled(ledger):
    with pytest.raises(ValueError, match="no solved closing"):
        jaw_body_states(ledger, 0, mode="saved")
    with pytest.raises(ValueError, match="saved or ideal"):
        jaw_body_states(ledger, 0, mode="physical")


def test_boolean_schema_version_rejected(ledger):
    ledger["schema_version"] = True
    with pytest.raises(ValueError, match="schema"):
        jaw_body_states(ledger, 0)


@pytest.mark.parametrize("input_name", ["inventory", "membership"])
def test_stale_provenance_rejected(ledger, input_name):
    inventory = _load(CAD / "thor-mounted-geometry-v2.json")
    membership = _load(CAD / "thor-wrist-membership-v2.json")
    (inventory if input_name == "inventory" else membership)["stale"] = True
    with pytest.raises(ValueError, match="stale jaw"):
        validate_jaw_ledger(ledger, inventory, membership)


@pytest.mark.parametrize(
    "corruption", ["duplicate", "missing", "frame", "reflection", "com", "motion"]
)
def test_malformed_ownership_and_frames_rejected(ledger, corruption):
    inventory = _load(CAD / "thor-mounted-geometry-v2.json")
    membership = _load(CAD / "thor-wrist-membership-v2.json")
    if corruption == "duplicate":
        ledger["records"].append(copy.deepcopy(ledger["records"][0]))
    elif corruption == "missing":
        ledger["records"].pop()
        ledger["geometry_leaf_count"] -= 1
        ledger["mass_record_count"] -= 1
    elif corruption == "frame":
        ledger["native_from_gripper_bot"][0][0] += 0.1
    elif corruption == "reflection":
        ledger["native_from_gripper_bot"][0][:3] = [
            -v for v in ledger["native_from_gripper_bot"][0][:3]
        ]
    elif corruption == "com":
        ledger["records"][0]["saved_com_native_m"][2] += 0.001
    elif corruption == "motion":
        ledger["records"][0]["jaw_motion_class"] = "unknown"
    with pytest.raises(ValueError):
        validate_jaw_ledger(ledger, inventory, membership)


def test_hash_is_content_based_and_nonfinite_json_rejected():
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})
    with pytest.raises(ValueError):
        canonical_sha256({"a": math.nan})


def test_offline_ledger_cli_and_overwrite_guard(tmp_path):
    command = [sys.executable, str(ROOT / "tools/thor_jaw_reconciliation.py")]
    result = subprocess.run(
        command + ["--check-ledger", str(LEDGER)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["mass_record_count"] == 66
    output = tmp_path / "existing.json"
    output.write_text("preserve", encoding="utf-8")
    failed = subprocess.run(
        command + ["--source-dir", str(tmp_path), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert failed.returncode != 0
    assert "new file" in failed.stderr
    assert "Traceback" not in failed.stderr
    assert output.read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize(
    "content", ['{"schema_version": 1,"schema_version": 1}', '{"x": NaN}', '{"x": 1e999}']
)
def test_cli_rejects_ambiguous_and_nonfinite_json(tmp_path, content):
    evidence = tmp_path / "bad.json"
    evidence.write_text(content, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/thor_jaw_reconciliation.py"),
            "--check-ledger",
            str(evidence),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_cli_evidence_reports_clean_error(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/thor_jaw_reconciliation.py"),
            "--check-ledger",
            str(tmp_path / "missing.json"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr
