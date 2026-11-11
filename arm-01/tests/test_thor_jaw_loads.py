"""Whole-ledger conservation and independent seven-coordinate energy checks."""

import copy
import importlib.util
import math
import random
import sys
from pathlib import Path

import pytest

from raftel_arm01.engineering.jaw_loads import (
    apply_jaw_overlay,
    carry_jaw_derivatives,
    jaw_gravity_torque_nm,
)
from raftel_arm01.engineering.scenarios import load_scenario_manifest, verify_scenario_inputs
from raftel_arm01.kinematics.thor_jaw_bodies import validate_jaw_ledger

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "thor_load_analysis", ROOT / "tools/thor_load_analysis.py"
)
loads = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = loads
SPEC.loader.exec_module(loads)


@pytest.fixture(scope="module")
def model():
    manifest = load_scenario_manifest(ROOT / "config/thor-scenario-v1.json")
    inputs = verify_scenario_inputs(manifest, ROOT)
    inventory, membership, jaw = (inputs[key] for key in ("inventory", "membership", "jaw_bodies"))
    validate_jaw_ledger(jaw, inventory, membership)
    snapshot = loads.expand_mass_assignments(
        loads.build_thor_snapshot(
            inventory, instance_mass_overrides=membership["instance_mass_overrides"]
        ),
        membership,
    )
    snapshot["wrist_conditional_gravity_closure"] = membership["conditional_gravity_closure"]
    return snapshot, membership, jaw


def test_saved_and_ideal_overlay_preserve_all_mass_ids_and_motor_totals(model):
    snapshot, membership, jaw = model
    before = copy.deepcopy(snapshot)
    masses = {body["id"]: body["mass_kg"] for body in snapshot["bodies"]}
    saved = apply_jaw_overlay(snapshot, jaw, mode="saved")
    assert [body["com_m"] for body in saved["bodies"]] == [
        body["com_m"] for body in snapshot["bodies"]
    ]
    changed_ideal_zero = False
    for q in (0, 0.4, 1.2):
        overlay = apply_jaw_overlay(snapshot, jaw, q)
        assert {body["id"]: body["mass_kg"] for body in overlay["bodies"]} == masses
        assert len(masses) == 517
        motors = [
            body
            for body in overlay["bodies"]
            if body["mass_assignment"]["category"].startswith("manufacturer_motor_mass_")
        ]
        assert len(motors) == 7
        assert math.fsum(body["mass_kg"] for body in motors) == pytest.approx(2.120, abs=1e-14)
        assert overlay["payload_position_m"] == snapshot["payload_position_m"]
        if q == 0:
            changed_ideal_zero = any(
                original["com_m"] != transformed["com_m"]
                for original, transformed in zip(snapshot["bodies"], overlay["bodies"], strict=True)
            )
    assert changed_ideal_zero  # explicit phase/pivot normalization, not saved CAD
    assert snapshot == before


def test_all_seven_external_gravity_efforts_match_negative_potential_gradient(model):
    snapshot, membership, jaw = model
    rng = random.Random(710061)

    def evaluate(values, classes):
        overlay = apply_jaw_overlay(snapshot, jaw, values[6])
        posed = loads.articulate_wrist_snapshot(overlay, tuple(values[:6]), classes)
        return overlay, posed

    def potential(values, classes):
        _, posed = evaluate(values, classes)
        # Independent potential sum includes all masses and the fixed-roll-tool payload.
        return 9.80665 * math.fsum(
            [body["mass_kg"] * body["com_m"][2] for body in posed["bodies"]]
            + [0.2 * posed["payload_position_m"][2]]
        )

    for sign_name in membership["motion_scenarios"]:
        classes = loads.wrist_motion_classes(membership, sign_name)
        for _ in range(4):
            values = [rng.uniform(-0.8, 0.8) for _ in range(6)] + [rng.uniform(0.1, 1.3)]
            overlay, posed = evaluate(values, classes)
            report = loads.analyze(posed, payloads_kg=(0.2,))
            analytic = []
            for row in report["scenarios"][0]["joints"]:
                self_effort = row["arm_gravity_torque_nm"]
                if self_effort is None:
                    self_effort = row["conditional_modeled_wrist_gravity_contribution_nm"]
                analytic.append(self_effort + row["payload_gravity_torque_nm"])
            analytic.append(
                jaw_gravity_torque_nm(overlay, carry_jaw_derivatives(overlay, values[:6], classes))
            )
            for coordinate in range(7):
                h = 1e-6
                before, after = list(values), list(values)
                before[coordinate] -= h
                after[coordinate] += h
                measured = -(potential(after, classes) - potential(before, classes)) / (2 * h)
                assert analytic[coordinate] == pytest.approx(measured, rel=2e-7, abs=2e-8)


def test_jaw_velocity_rotation_agrees_with_transformed_com_difference(model):
    snapshot, membership, jaw = model
    angles, q, h = (0.2, 0.8, -0.5, 0.6, -0.4, 0.7), 0.9, 1e-6
    classes = loads.wrist_motion_classes(membership, "bevel_sign_positive")
    zero = apply_jaw_overlay(snapshot, jaw, q)
    analytic = carry_jaw_derivatives(zero, angles, classes)
    before = loads.articulate_wrist_snapshot(
        apply_jaw_overlay(snapshot, jaw, q - h), angles, classes
    )
    after = loads.articulate_wrist_snapshot(
        apply_jaw_overlay(snapshot, jaw, q + h), angles, classes
    )
    for first, last in zip(before["bodies"], after["bodies"], strict=True):
        numeric = tuple((last["com_m"][i] - first["com_m"][i]) / (2 * h) for i in range(3))
        assert analytic[first["id"]] == pytest.approx(numeric, rel=2e-6, abs=2e-10)


def test_missing_duplicate_stale_or_posed_load_records_fail(model):
    snapshot, membership, jaw = model
    for mutate in (
        lambda data: data["bodies"].append(copy.deepcopy(data["bodies"][0])),
        lambda data: data.update(coordinate_frame="native_CAD_world_m"),
        lambda data: data["bodies"].pop(),
    ):
        bad = copy.deepcopy(snapshot)
        mutate(bad)
        with pytest.raises(ValueError):
            apply_jaw_overlay(bad, jaw, 0.2)
    overlay = apply_jaw_overlay(snapshot, jaw, 0.7)
    with pytest.raises(ValueError, match="saved COM"):
        apply_jaw_overlay(overlay, jaw, 0.8)
    classes = loads.wrist_motion_classes(membership, "bevel_sign_positive")
    bad = copy.deepcopy(overlay)
    bad["joints"][1]["axis_unit"] = [0, 0, 1]
    with pytest.raises(ValueError, match="unposed nominal"):
        carry_jaw_derivatives(bad, (0,) * 6, classes)
    derivatives = carry_jaw_derivatives(overlay, (0,) * 6, classes)
    derivatives.pop(next(iter(derivatives)))
    with pytest.raises(ValueError, match="every expanded body"):
        jaw_gravity_torque_nm(overlay, derivatives)
