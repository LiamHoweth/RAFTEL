"""Analytical invariants and provenance guards, not physical load qualification."""

import copy
import importlib.util
import math
import sys
from pathlib import Path

import pytest

from raftel_arm01.kinematics.thor_drive import joints_to_drive

_SPEC = importlib.util.spec_from_file_location(
    "thor_load_analysis", Path(__file__).parents[1] / "tools" / "thor_load_analysis.py"
)
loads = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = loads
_SPEC.loader.exec_module(loads)


def snapshot():
    return {
        "schema_version": 1,
        "coordinate_frame": "test_world",
        "sources": ["analytical fixture only"],
        "coverage": {"complete": False, "omitted_components": ["real robot"]},
        "bodies": [
            {
                "id": "distal",
                "instance_path": "fixture/distal",
                "mass_kg": 0.5,
                "com_m": [0, 0.2, 0.1],
                "mass_kind": "assumption",
                "com_kind": "fixture",
                "evidence": "test-only known point load",
            }
        ],
        "joints": [
            {
                "name": f"q{i}",
                "origin_m": [0, 0, 0],
                "axis_unit": [1, 0, 0],
                "downstream_body_ids": ["distal"],
            }
            for i in range(1, 7)
        ],
        "payload_position_m": [0, 0.35, 0.1],
    }


def test_payload_known_gravity_moment_and_holding_sign():
    joint = loads.Joint("pitch", (0, 0, 0), (1, 0, 0), ("payload",))
    body = loads.Body("payload", 0.2, (0, 0.35, 0.1))
    assert loads.gravity_torque_nm(joint, (body,)) == pytest.approx(-0.6864655)


def test_vertical_axis_has_no_gravity_torque_and_proximal_mass_excluded():
    bodies = (loads.Body("distal", 0.2, (0, 0.4, 0.1)), loads.Body("proximal", 100, (0, 0.2, 0)))
    yaw = loads.Joint("yaw", (0, 0, 0), (0, 0, 1), ("distal",))
    pitch = loads.Joint("pitch", (0, 0.3, 0), (1, 0, 0), ("distal",))
    assert loads.gravity_torque_nm(yaw, bodies) == 0
    assert loads.gravity_torque_nm(pitch, bodies) == pytest.approx(-0.196133)


def test_moment_agrees_with_finite_difference_of_gravitational_potential():
    y, z, mass = 0.21, 0.12, 0.38
    joint = loads.Joint("pitch", (0, 0, 0), (1, 0, 0), ("motor",))
    external = loads.gravity_torque_nm(joint, (loads.Body("motor", mass, (0, y, z)),))
    epsilon = 1e-6

    def potential(theta):
        return mass * loads.GRAVITY_M_S2 * (y * math.sin(theta) + z * math.cos(theta))

    derivative = (potential(epsilon) - potential(-epsilon)) / (2 * epsilon)
    assert external == pytest.approx(-derivative, rel=1e-9)


def test_virtual_work_matches_nominal_coupled_channels_for_unequal_sharing():
    holding = (1, 2, 3, 4, 5, 6)
    perturbation = (0.01, -0.02, 0.03, -0.04, 0.05, -0.06)
    channels = loads.nominal_channel_efforts(holding, 0.2)
    dq_drive = joints_to_drive(perturbation)
    joint_work = sum(t * dq for t, dq in zip(holding, perturbation, strict=True))
    drive_work = sum(t * dq for t, dq in zip(channels, dq_drive, strict=True))
    assert drive_work == pytest.approx(joint_work)
    assert channels[1] != channels[2]


def test_density_scenario_accounts_for_units_and_whole_part_fraction():
    # 1 cm^3 fully dense at 1000kg/m^3 weighs 1g.
    assert loads.dense_volume_mass_kg(1000, 1000, 1) == pytest.approx(0.001)
    assert loads.dense_volume_mass_kg(1000, 1000, 0.5) == pytest.approx(0.0005)


@pytest.mark.parametrize("axis", [(0, 0, 0), (2, 0, 0), (math.nan, 0, 0)])
def test_invalid_axis_rejected(axis):
    with pytest.raises(ValueError):
        loads.Joint("bad", (0, 0, 0), axis, ())


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True, "0.2"])
def test_invalid_mass_input_rejected(value):
    with pytest.raises(ValueError):
        loads.Body("bad", value, (0, 0, 0))


def test_duplicate_and_missing_body_guards():
    body = loads.Body("same", 0.2, (0, 0.2, 0))
    joint = loads.Joint("joint", (0, 0, 0), (1, 0, 0), ("same",))
    with pytest.raises(ValueError, match="duplicate"):
        loads.gravity_torque_nm(joint, (body, body))
    with pytest.raises(ValueError, match="absent"):
        loads.gravity_torque_nm(joint, ())
    with pytest.raises(ValueError, match="twice"):
        loads.Joint("joint", (0, 0, 0), (1, 0, 0), ("same", "same"))


def test_snapshot_partial_mass_coverage_is_preserved_and_payload_not_hidden():
    result = loads.analyze(snapshot())
    assert not result["coverage"]["complete"] and not result["actuator_qualification"]
    no_payload = result["scenarios"][0]["joints"][0]
    payload = result["scenarios"][2]["joints"][0]
    assert no_payload["required_ideal_holding_torque_nm"] == pytest.approx(0.980665)
    assert payload["required_ideal_holding_torque_nm"] == pytest.approx(0.980665 + 0.6864655)


@pytest.mark.parametrize("field", ["mass_kind", "com_kind", "evidence", "instance_path"])
def test_mass_and_com_provenance_required(field):
    model = snapshot()
    del model["bodies"][0][field]
    with pytest.raises(ValueError, match="provenance"):
        loads.analyze(model)


def test_duplicate_mounted_instance_and_false_completeness_rejected():
    model = snapshot()
    duplicate = copy.deepcopy(model["bodies"][0])
    duplicate["id"] = "other"
    model["bodies"].append(duplicate)
    with pytest.raises(ValueError, match="instance"):
        loads.analyze(model)
    model = snapshot()
    model["coverage"]["complete"] = True
    with pytest.raises(ValueError, match="complete"):
        loads.analyze(model)


@pytest.mark.parametrize("fraction", [-0.1, 1.1, math.nan])
def test_invalid_shoulder_share_rejected(fraction):
    with pytest.raises(ValueError):
        loads.nominal_channel_efforts((0, 1, 0, 0, 0, 0), fraction)


def test_rigid_articulation_preserves_input_and_rotates_body_and_tool():
    original = snapshot()
    saved = copy.deepcopy(original)
    posed = loads.articulate_snapshot(original, (math.pi / 2, 0, 0, 0, 0, 0))
    assert original == saved
    assert posed["bodies"][0]["com_m"] == pytest.approx((0, -0.1, 0.2))
    assert posed["payload_position_m"] == pytest.approx((0, -0.1, 0.35))
    assert not posed["pose"]["physical_zero_or_limits_validated"]


def test_articulation_rotates_later_axis_lines_and_excludes_proximal_body():
    model = snapshot()
    model["bodies"].append(
        {
            **model["bodies"][0],
            "id": "proximal",
            "instance_path": "fixture/proximal",
            "com_m": [0, 0.1, 0],
        }
    )
    for joint in model["joints"]:
        joint["axis_unit"] = [0, 0, 1]
    model["joints"][1]["origin_m"] = [0, 0.1, 0]
    model["joints"][1]["axis_unit"] = [1, 0, 0]
    posed = loads.articulate_snapshot(model, (math.pi / 2, 0, 0, 0, 0, 0))
    assert posed["joints"][1]["origin_m"] == pytest.approx((-0.1, 0, 0), abs=1e-15)
    assert posed["joints"][1]["axis_unit"] == pytest.approx((0, 1, 0), abs=1e-15)
    assert posed["bodies"][1]["com_m"] == [0, 0.1, 0]


def test_nominal_payload_increment_report_is_explicitly_incomplete():
    report = loads.nominal_payload_increment_report()
    horizontal = report["poses"]["shoulder_horizontal"]
    rows = horizontal["scenarios"][2]["joints"]
    assert abs(rows[1]["required_ideal_holding_torque_nm"]) == pytest.approx(0.2 * 9.80665 * 0.4855)
    assert abs(rows[2]["required_ideal_holding_torque_nm"]) == pytest.approx(0.2 * 9.80665 * 0.3255)
    assert not horizontal["coverage"]["complete"]
    assert horizontal["modeled_mass_kg"] == 0
    assert "ALL" in report["meaning"]


def test_payload_increment_cli_runs_without_a_fake_robot_mass_model():
    import json
    import subprocess

    script = Path(__file__).parents[1] / "tools" / "thor_load_analysis.py"
    process = subprocess.run(
        [sys.executable, str(script), "--nominal-payload-increments"],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(process.stdout)
    assert "increments_only" in report["validation_class"]
    assert len(report["poses"]) == 4


def test_unresolved_joint_self_mass_is_null_rather_than_false_zero():
    model = snapshot()
    model["joints"][5]["body_membership_resolved"] = False
    row = loads.analyze(model)["scenarios"][2]["joints"][5]
    assert row["arm_gravity_torque_nm"] is None
    assert row["required_ideal_holding_torque_nm"] is None
    assert row["payload_gravity_torque_nm"] != 0
    assert not row["body_membership_resolved"]


def test_gravity_wrench_and_center_of_mass_give_known_support_reaction():
    bodies = (loads.Body("one", 1, (0.2, 0.3, 0.1)), loads.Body("two", 1, (0, 0, 0.3)))
    wrench = loads.gravity_wrench(bodies)
    assert wrench["external_force_n"] == pytest.approx((0, 0, -19.6133))
    assert wrench["external_moment_nm"] == pytest.approx((-0.3 * 9.80665, 0.2 * 9.80665, 0))
    assert wrench["ideal_support_moment_nm"] == pytest.approx((0.3 * 9.80665, -0.2 * 9.80665, 0))
    assert loads.center_of_mass(bodies) == pytest.approx((0.1, 0.15, 0.2))
    assert loads.center_of_mass(()) is None


def test_unknown_wrist_membership_cannot_silently_articulate_body_motion():
    model = snapshot()
    model["joints"][5]["body_membership_resolved"] = False
    with pytest.raises(ValueError, match="unresolved body membership"):
        loads.articulate_snapshot(model, (0, 0, 0, 0, 0, 0.01))
    assert loads.articulate_snapshot(model, (0, 0, 0, 0, 0, 0))["bodies"] == model["bodies"]


def test_serial_articulation_rejects_nonnested_downstream_sets():
    model = snapshot()
    model["joints"][0]["downstream_body_ids"] = []
    with pytest.raises(ValueError, match="nested downstream"):
        loads.articulate_snapshot(model, (0, 0, 0, 0, 0, 0))


def native_inventory_fixture():
    leaves = []

    def leaf(group, asset, source="Imported", label="component", suffix="shape"):
        record = {
            "instance_id": f"Assembly::Model/Assembly::{group}/{group}::{asset}/{group}::{suffix}",
            "root_subassembly": group,
            "object_reference": f"{group}::{suffix}",
            "linked_object": f"{source}::Body" if source != "Imported" else f"{group}::{suffix}",
            "label": label,
            "volume_mm3": 1000,
            "solid_count": 1,
            "zero_world_com_m": [0.01, 0.02, 0.3],
            "native_state": ["Up-to-date"],
        }
        leaves.append(record)

    leaf("AssemblyBase", "Stepper_Nema17x40001")
    for i in (1, 2, 3):
        leaf("AssemblyArt1", f"Nema17_GearBox00{i}")
    leaf("AssemblyArt2", "PrintedPart", "Art2BodyA")
    leaf("AssemblyArt3", "Stepper_Nema17x34001")
    for i in (1, 2):
        leaf("AssemblyArt4", f"Stepper_Nema17x3400{i}")
    leaf("AssemblyArt56", "Servomotor001")
    return {
        "mounted_bodies": leaves,
        "missing_object_records": [],
        "errors": [],
        "validation_class": "synthetic positive-solid fixture, not a Thor CAD result",
    }


def test_mass_builder_counts_whole_motor_once_and_changes_cad_frame():
    inventory = native_inventory_fixture()
    duplicate_component = copy.deepcopy(inventory["mounted_bodies"][1])
    duplicate_component["instance_id"] += "second-leaf"
    inventory["mounted_bodies"].append(duplicate_component)
    model = loads.build_thor_snapshot(inventory, 0.5)
    assert sum(b["mass_kg"] for b in model["bodies"]) == pytest.approx(2.120 + 0.055 + 0.000620)
    group = next(b for b in model["bodies"] if b["id"] == "AssemblyArt1")
    assert group["mass_kg"] == pytest.approx(3 * 0.380)
    assert group["com_m"] == pytest.approx((0.02, -0.01, 0.3))
    assert model["payload_position_m"] == pytest.approx([0, 0, 0.7025242557054092])
    assert not model["joints"][4]["body_membership_resolved"]
    assert not model["joints"][5]["body_membership_resolved"]


def test_unclassified_mass_is_omitted_explicitly_and_duplicates_fail():
    inventory = native_inventory_fixture()
    unknown = copy.deepcopy(inventory["mounted_bodies"][0])
    unknown["instance_id"] = "Assembly::Model/Assembly::AssemblyBase/AssemblyBase::Unknown/Shape"
    inventory["mounted_bodies"].append(unknown)
    model = loads.build_thor_snapshot(inventory)
    assert (
        model["mass_assignment_summary"]["omitted_unclassified_instances"][0]["instance_path"]
        == unknown["instance_id"]
    )
    inventory["mounted_bodies"].append(unknown)
    with pytest.raises(ValueError, match="duplicate installed"):
        loads.build_thor_snapshot(inventory)


def test_conditional_wrist_bounds_do_not_cancel_opposed_mass_offsets():
    model = loads.build_thor_snapshot(native_inventory_fixture())
    wrist = next(b for b in model["bodies"] if b["id"] == "AssemblyArt56")
    wrist["mass_assignments"] = [
        {"mass_kg": 1, "com_m": [0.1, 0, 0.5695]},
        {"mass_kg": 1, "com_m": [-0.1, 0, 0.5695]},
    ]
    bound = loads.conditional_wrist_bounds(model)
    assert bound["joints"]["joint_6"]["modeled_self_mass_magnitude_bound_nm"] == pytest.approx(
        2 * 0.1 * 9.80665
    )
    assert not bound["physical_load_bound_or_actuator_qualification"]


def test_servo_horn_is_not_misclassified_as_a_second_servo():
    inventory = native_inventory_fixture()
    horn = copy.deepcopy(inventory["mounted_bodies"][-1])
    horn["instance_id"] = (
        "Assembly::Model/Assembly::AssemblyArt56/AssemblyArt56::ServomotorWheelHorn001/Shape"
    )
    horn["label"] = "WheelHorn"
    inventory["mounted_bodies"].append(horn)
    model = loads.build_thor_snapshot(inventory)
    wrist = next(b for b in model["bodies"] if b["id"] == "AssemblyArt56")
    assert wrist["mass_kg"] == pytest.approx(0.055 + 0.001150)
    categories = [row["category"] for row in wrist["mass_assignments"]]
    assert categories.count("whole_asset_mass_allowance_Servomotor") == 1
    assert categories.count("polymer_horn_density_assumption") == 1


@pytest.mark.parametrize("density", [0, -1, math.nan, math.inf, -math.inf])
def test_material_density_override_rejects_nonpositive_nonfinite_values(density):
    with pytest.raises(ValueError):
        loads.build_thor_snapshot(
            native_inventory_fixture(),
            material="PETG",
            material_density_kg_m3=density,
            material_density_source="explicit test estimate",
        )


def test_custom_density_requires_provenance_and_changes_only_printed_mass():
    inventory = native_inventory_fixture()
    with pytest.raises(ValueError, match="provenance"):
        loads.build_thor_snapshot(inventory, material_density_kg_m3=2480)
    original = loads.build_thor_snapshot(inventory)
    custom = loads.build_thor_snapshot(
        inventory, material_density_kg_m3=2480, material_density_source="test-only doubled density"
    )
    old = {b["id"]: b for b in original["bodies"]}
    new = {b["id"]: b for b in custom["bodies"]}
    assert new["AssemblyArt2"]["mass_kg"] == pytest.approx(2 * old["AssemblyArt2"]["mass_kg"])
    for group in set(old) - {"AssemblyArt2"}:
        assert new[group]["mass_kg"] == old[group]["mass_kg"]
    assert (
        custom["mass_assignment_summary"]["printed_material_reference"]["source"]
        == "test-only doubled density"
    )


def test_material_references_are_specific_filaments_and_not_user_brand_claims():
    for family, density in [("PLA", 1240), ("PETG", 1270), ("ABS", 1040)]:
        reference = loads.material_reference(family)
        assert reference["density_kg_m3"] == density
        assert not reference["actual_user_brand_or_density_verified"]
        assert reference["source"].startswith("https://")
    with pytest.raises(ValueError, match="PLA, PETG or ABS"):
        loads.material_reference("unknown")


def test_material_change_keeps_motor_and_separate_horn_mass_unchanged():
    inventory = native_inventory_fixture()
    horn = copy.deepcopy(inventory["mounted_bodies"][-1])
    horn["instance_id"] = (
        "Assembly::Model/Assembly::AssemblyArt56/AssemblyArt56::ServomotorWheelHorn001/Shape"
    )
    horn["label"] = "WheelHorn"
    inventory["mounted_bodies"].append(horn)
    records = []
    for material in ("PLA", "PETG", "ABS"):
        model = loads.build_thor_snapshot(inventory, material=material)
        records.append(
            {
                row["instance_path"]: row["mass_kg"]
                for body in model["bodies"]
                for row in body["mass_assignments"]
                if not row["category"].startswith("printed_")
            }
        )
    assert records[0] == records[1] == records[2]


def test_original_PLA_default_report_remains_reproducible():
    import json

    root = Path(__file__).parents[1]
    inventory = json.loads((root / "hardware/cad/thor-mounted-geometry.json").read_text())
    baseline = json.loads((root / "hardware/cad/thor-load-study.json").read_text())
    assert json.loads(json.dumps(loads.cad_load_study(inventory))) == baseline


def test_material_comparison_explicitly_does_not_validate_structural_performance():
    comparison = loads.material_comparison_report(native_inventory_fixture())
    assert len(comparison["cases"]) == 3
    assert not comparison["actual_user_filament_brand_or_density_verified"]
    assert not comparison["printed_material_stiffness_creep_or_strength_validated"]


def wrist_inputs():
    import json

    root = Path(__file__).parents[1]
    inventory = json.loads((root / "hardware/cad/thor-mounted-geometry.json").read_text())
    memberships = json.loads((root / "hardware/cad/thor-wrist-membership.json").read_text())
    baseline = loads.build_thor_snapshot(inventory)
    expanded = loads.expand_mass_assignments(baseline, memberships)
    classes = loads.wrist_motion_classes(memberships, "bevel_sign_positive")
    return baseline, expanded, classes, memberships


def test_wrist_mass_expansion_conserves_full_ledger_and_manufacturer_mass():
    baseline, expanded, _, _ = wrist_inputs()
    assert len(expanded["bodies"]) == 515
    assert len({b["instance_path"] for b in expanded["bodies"]}) == 515
    assert sum(b["mass_kg"] for b in expanded["bodies"]) == pytest.approx(
        sum(b["mass_kg"] for b in baseline["bodies"]), abs=1e-14
    )
    assert sum(
        b["mass_kg"]
        for b in expanded["bodies"]
        if b["mass_assignment"]["category"].startswith("manufacturer_motor_mass_")
    ) == pytest.approx(2.120)


def test_wrist_expansion_rejects_duplicate_and_cross_class_asset_memberships():
    baseline, _, _, memberships = wrist_inputs()
    invalid = copy.deepcopy(memberships)
    invalid["memberships"].append(invalid["memberships"][0])
    with pytest.raises(ValueError, match="duplicate"):
        loads.expand_mass_assignments(baseline, invalid)
    consolidated = next(
        a
        for b in baseline["bodies"]
        for a in b["mass_assignments"]
        if a.get("geometry_leaf_count", 1) > 1
    )
    invalid = copy.deepcopy(memberships)
    member = next(
        row
        for row in invalid["memberships"]
        if row["instance_id"].startswith(consolidated["instance_path"] + "/")
    )
    member["motion_class"] = "roll_tool"
    with pytest.raises(ValueError, match="multiple wrist motion classes"):
        loads.expand_mass_assignments(baseline, invalid)


def test_wrist_paths_preserve_zero_wrist_proximal_baseline_and_unknown_totals():
    baseline, expanded, classes, _ = wrist_inputs()
    angles = (0.2, 0.6, -0.3, 0.4, 0, 0)
    original = loads.analyze(loads.articulate_snapshot(baseline, angles))
    traced = loads.analyze(loads.articulate_wrist_snapshot(expanded, angles, classes))
    for a, b in zip(original["scenarios"], traced["scenarios"], strict=True):
        for old, new in zip(a["joints"][:4], b["joints"][:4], strict=True):
            assert new["arm_gravity_torque_nm"] == pytest.approx(old["arm_gravity_torque_nm"])
        for row in b["joints"][4:]:
            assert row["arm_gravity_torque_nm"] is None
            assert row["required_ideal_holding_torque_nm"] is None
            assert math.isfinite(row["conditional_modeled_wrist_gravity_contribution_nm"])


@pytest.mark.parametrize("scenario", ["bevel_sign_positive", "bevel_sign_negative"])
def test_wrist_and_proximal_moments_match_full_COM_potential_gradient(scenario):
    _, expanded, _, memberships = wrist_inputs()
    classes = loads.wrist_motion_classes(memberships, scenario)
    angles = (0.2, 0.6, -0.3, 0.4, -0.5, 0.7)
    result = loads.analyze(loads.articulate_wrist_snapshot(expanded, angles, classes), (0,))
    epsilon = 1e-6

    def potential(coordinates):
        posed = loads.articulate_wrist_snapshot(expanded, tuple(coordinates), classes)
        return math.fsum(b["mass_kg"] * loads.GRAVITY_M_S2 * b["com_m"][2] for b in posed["bodies"])

    for index, row in enumerate(result["scenarios"][0]["joints"]):
        plus, minus = list(angles), list(angles)
        plus[index] += epsilon
        minus[index] -= epsilon
        gradient = (potential(plus) - potential(minus)) / (2 * epsilon)
        external = (
            row["arm_gravity_torque_nm"]
            if index < 4
            else row["conditional_modeled_wrist_gravity_contribution_nm"]
        )
        assert external == pytest.approx(-gradient, abs=1e-8)


def test_carried_roll_payload_point_follows_fold_and_not_fixed_world_roll():
    _, expanded, classes, _ = wrist_inputs()
    pose = loads.articulate_wrist_snapshot(expanded, (0, 0, 0, 0, math.pi / 2, 0.7), classes)
    # Original axis-centred payload is invariant under its roll, then folds about +ROS X.
    assert pose["payload_position_m"] == pytest.approx([0, -(0.7025242557054092 - 0.556), 0.556])


@pytest.mark.parametrize(
    "bad_override",
    [
        {"mass_kg": 0, "evidence": "test"},
        {"mass_kg": 0.1},
        {"mass_kg": math.nan, "evidence": "test"},
    ],
)
def test_explicit_leaf_mass_scenario_requires_positive_mass_and_provenance(bad_override):
    inventory = native_inventory_fixture()
    path = inventory["mounted_bodies"][-1]["instance_id"]
    with pytest.raises(ValueError):
        loads.build_thor_snapshot(inventory, instance_mass_overrides={path: bad_override})


def test_leaf_mass_override_cannot_replace_a_manufacturer_whole_motor_mass():
    inventory = native_inventory_fixture()
    path = next(
        row["instance_id"]
        for row in inventory["mounted_bodies"]
        if "Stepper_Nema17" in row["instance_id"]
    )
    with pytest.raises(ValueError, match="whole purchased-asset"):
        loads.build_thor_snapshot(
            inventory, instance_mass_overrides={path: {"mass_kg": 0.01, "evidence": "test-only"}}
        )
    with pytest.raises(ValueError, match="installed geometry"):
        loads.build_thor_snapshot(
            inventory,
            instance_mass_overrides={"absent": {"mass_kg": 0.01, "evidence": "test-only"}},
        )


def test_missing_explicit_revised_belt_mass_is_not_silently_replaced_by_density():
    with pytest.raises(ValueError, match="explicit masses"):
        loads.wrist_load_study(
            {},
            {
                "schema_version": 2,
                "required_instance_mass_overrides": ["belt"],
                "instance_mass_overrides": {},
            },
        )


def test_original_wrist_and_material_reports_remain_reproducible():
    import json

    root = Path(__file__).parents[1] / "hardware/cad"
    inventory = json.loads((root / "thor-mounted-geometry.json").read_text())
    membership = json.loads((root / "thor-wrist-membership.json").read_text())
    assert json.loads(json.dumps(loads.wrist_load_study(inventory, membership))) == json.loads(
        (root / "thor-wrist-load-study.json").read_text()
    )
    assert loads.material_comparison_report(inventory) == json.loads(
        (root / "thor-material-comparison.json").read_text()
    )


def revised_wrist_inputs():
    import json

    root = Path(__file__).parents[1] / "hardware/cad"
    inventory = json.loads((root / "thor-mounted-geometry-v2.json").read_text())
    membership = json.loads((root / "thor-wrist-membership-v2.json").read_text())
    model = loads.build_thor_snapshot(
        inventory, instance_mass_overrides=membership["instance_mass_overrides"]
    )
    expanded = loads.expand_mass_assignments(model, membership)
    expanded["wrist_conditional_gravity_closure"] = membership["conditional_gravity_closure"]
    return inventory, membership, expanded


def test_revised_coverage_preserves_all_old_masses_and_adds_only_explicit_belts():
    baseline, _, _, _ = wrist_inputs()
    inventory, membership, expanded = revised_wrist_inputs()
    previous = {
        a["instance_path"]: a["mass_kg"]
        for body in baseline["bodies"]
        for a in body["mass_assignments"]
    }
    current = {b["instance_path"]: b["mass_kg"] for b in expanded["bodies"]}
    assert len(inventory["mounted_bodies"]) == len(membership["memberships"]) == 518
    assert len(expanded["bodies"]) == 517
    assert {path: current[path] for path in previous} == previous
    assert set(current) - set(previous) == set(membership["instance_mass_overrides"])
    belt_delta = sum(v["mass_kg"] for v in membership["instance_mass_overrides"].values())
    assert belt_delta == pytest.approx(0.004833574668562413)
    assert sum(current.values()) == pytest.approx(sum(previous.values()) + belt_delta)
    motors = [
        b
        for b in expanded["bodies"]
        if b["mass_assignment"]["category"].startswith("manufacturer_motor_mass_")
    ]
    assert len(motors) == 7
    assert sum(b["mass_kg"] for b in motors) == pytest.approx(2.120)
    assert not membership["conditional_gravity_closure"]["rotor_stator_mass_split_invented"]


@pytest.mark.parametrize("scenario_name", ["bevel_sign_positive", "bevel_sign_negative"])
def test_revised_input_pulleys_follow_actual_own_axes_at_twice_side_angle(scenario_name):
    inventory, membership, expanded = revised_wrist_inputs()
    classes = loads.wrist_motion_classes(membership, scenario_name)
    q5, q6 = 0.31, -0.43
    posed = loads.articulate_wrist_snapshot(expanded, (0, 0, 0, 0, q5, q6), classes)
    points = {b["id"]: b["com_m"] for b in posed["bodies"]}
    sign = membership["motion_scenarios"][scenario_name]["side_rotor_sign_s"]
    checked = 0
    for leaf in inventory["mounted_bodies"]:
        path = leaf["instance_id"]
        if "/AssemblyArt4::Pulley_GT2x20001/" in path:
            origin, angle = (0.024, -0.0279, 0.4781), 2 * (q5 + 2 * sign * q6)
        elif "/AssemblyArt4::Pulley_GT2x20002/" in path:
            origin, angle = (-0.024, 0.0279, 0.4781), 2 * (q5 - 2 * sign * q6)
        elif "/AssemblyArt4::Belt_GT2_208mm" in path:
            x, y, z = leaf["zero_world_com_m"]
            assert points[path] == pytest.approx([y, -x, z])
            continue
        else:
            continue
        x, y, z = [leaf["zero_world_com_m"][i] - origin[i] for i in range(3)]
        # Independent common-native-Y point rotation; second motor's actual -Y
        # axis is represented equivalently by the negated angle in the ledger.
        moved_x = origin[0] + x * math.cos(angle) + z * math.sin(angle)
        moved_z = origin[2] - x * math.sin(angle) + z * math.cos(angle)
        assert points[path] == pytest.approx([y + origin[1], -moved_x, moved_z], abs=1e-12)
        checked += 1
    assert checked == 4


@pytest.mark.parametrize("scenario_name", ["bevel_sign_positive", "bevel_sign_negative"])
def test_revised_conditional_holding_matches_total_COM_potential_gradient(scenario_name):
    _, membership, expanded = revised_wrist_inputs()
    classes = loads.wrist_motion_classes(membership, scenario_name)
    angles = (0.2, 0.6, -0.3, 0.4, -0.5, 0.7)
    posed = loads.articulate_wrist_snapshot(expanded, angles, classes)
    rows = loads.analyze(posed, (0.2,))["scenarios"][0]["joints"]

    def potential(coordinates):
        moved = loads.articulate_wrist_snapshot(expanded, tuple(coordinates), classes)
        return loads.GRAVITY_M_S2 * (
            math.fsum(b["mass_kg"] * b["com_m"][2] for b in moved["bodies"])
            + 0.2 * moved["payload_position_m"][2]
        )

    epsilon = 1e-6
    for index, row in enumerate(rows):
        plus, minus = list(angles), list(angles)
        plus[index] += epsilon
        minus[index] -= epsilon
        gradient = (potential(plus) - potential(minus)) / (2 * epsilon)
        if index < 4:
            holding = row["required_ideal_holding_torque_nm"]
        else:
            holding = row["conditional_modeled_holding_torque_nm"]
            assert row["required_ideal_holding_torque_nm"] is None
            assert row["arm_gravity_torque_nm"] is None
        assert holding == pytest.approx(gradient, abs=1e-8)


def test_revised_report_reproduces_and_distinguishes_intended_phase_from_sensitivity():
    import json

    inventory, membership, _ = revised_wrist_inputs()
    report = loads.wrist_load_study(inventory, membership)
    path = Path(__file__).parents[1] / "hardware/cad/thor-wrist-load-study-v2.json"
    assert json.loads(json.dumps(report)) == json.loads(path.read_text())
    assert report["chosen_intended_phase"]["side_rotor_sign_s"] == 1
    for case in report["cases"]:
        if case["side_rotor_sign_s"] == 1:
            assert case["phase_evidence_class"].startswith("chosen intended")
        else:
            assert "sensitivity only" in case["phase_evidence_class"]


def test_conditional_holding_requires_nonempty_explained_assumptions():
    _, membership, expanded = revised_wrist_inputs()
    classes = loads.wrist_motion_classes(membership, "bevel_sign_positive")
    expanded["wrist_conditional_gravity_closure"]["assumptions"] = [""]
    posed = loads.articulate_wrist_snapshot(expanded, (0, 0, 0, 0, 0, 0), classes)
    with pytest.raises(ValueError, match="assumptions/evidence"):
        loads.analyze(posed)
