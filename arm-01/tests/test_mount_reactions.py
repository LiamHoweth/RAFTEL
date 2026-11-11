"""Full-wrench balance, redundant allocation and evidence-boundary fixtures."""

import copy
import importlib.util
import json
import math
import random
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from raftel_arm01.engineering.mount_reactions import (
    ReactionChannel,
    SingularSupportLayout,
    Wrench,
    shift_wrench_reference,
    solve_reactions,
    transform_wrench,
)
from raftel_arm01.kinematics.thor_frames import compose

ROOT = Path(__file__).resolve().parents[1]
FRAME = "synthetic_plate"
POINTS = ((-0.1, -0.12, 0), (0.1, -0.12, 0), (0.1, 0.12, 0), (-0.1, 0.12, 0))


def channels(points=POINTS, *, normal_only=False):
    result = []
    for index, (x, y, z) in enumerate(points):
        transform = ((1, 0, 0, x), (0, 1, 0, y), (0, 0, 1, z), (0, 0, 0, 1))
        directions = ((0, 0, 1),) if normal_only else ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        for axis, direction in enumerate(directions):
            result.append(
                ReactionChannel(
                    f"{index}-{axis}",
                    transform,
                    direction,
                    1,
                    "bilateral",
                    FRAME,
                    "synthetic bilateral fixture, not real clamps",
                )
            )
    return tuple(result)


def solve(wrench, supports=None, **overrides):
    kwargs = {
        "allocation_evidence": "synthetic equal force-norm weights",
        "characteristic_length_m": 0.1,
        **overrides,
    }
    return solve_reactions(wrench, channels() if supports is None else supports, **kwargs)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def verify_balance_directly(wrench, rows):
    force = [sum(row["force_n"][i] for row in rows) + wrench.force_n[i] for i in range(3)]
    moments = [
        cross(
            tuple(row["point_m"][i] - wrench.reference_point_m[i] for i in range(3)), row["force_n"]
        )
        for row in rows
    ]
    moment = [sum(row[i] for row in moments) + wrench.moment_nm[i] for i in range(3)]
    assert force == pytest.approx((0, 0, 0), abs=1e-9)
    assert moment == pytest.approx((0, 0, 0), abs=1e-10)


def test_centered_vertical_load_known_reactions_and_qualification_boundaries():
    external = Wrench((0, 0, -100), (0, 0, 0), (0, 0, 0), FRAME)
    result = solve(external)
    vertical = [
        row["force_scalar_n"] for row in result["reactions"] if row["identifier"].endswith("-2")
    ]
    assert vertical == pytest.approx([25] * 4, abs=1e-12)
    assert all(
        abs(row["force_scalar_n"]) < 1e-12
        for row in result["reactions"]
        if not row["identifier"].endswith("-2")
    )
    assert result["diagnostic"]["numerical_rank"] == 6
    assert result["equilibrium"]["all_six_components_checked"]
    assert result["chosen_allocation_satisfies_allowed_signs"]
    assert not any(result["qualification"].values())
    verify_balance_directly(external, result["reactions"])


def test_arbitrary_six_component_wrenches_balance_and_virtual_work_agrees():
    randomizer = random.Random(692)
    supports = channels()
    for _ in range(60):
        external = Wrench(
            tuple(randomizer.uniform(-100, 100) for _ in range(3)),
            tuple(randomizer.uniform(-10, 10) for _ in range(3)),
            tuple(randomizer.uniform(-0.05, 0.05) for _ in range(3)),
            FRAME,
        )
        result = solve(external, supports)
        verify_balance_directly(external, result["reactions"])
        dt = tuple(randomizer.uniform(-0.001, 0.001) for _ in range(3))
        dr = tuple(randomizer.uniform(-0.01, 0.01) for _ in range(3))
        work = 0
        for row in result["reactions"]:
            offset = tuple(row["point_m"][i] - external.reference_point_m[i] for i in range(3))
            rotation = cross(dr, offset)
            displacement = tuple(dt[i] + rotation[i] for i in range(3))
            work += sum(row["force_n"][i] * displacement[i] for i in range(3))
        external_work = sum(
            external.force_n[i] * dt[i] + external.moment_nm[i] * dr[i] for i in range(3)
        )
        assert work + external_work == pytest.approx(0, abs=1e-10)


def test_known_pure_torsion_is_reacted_by_lateral_force_pairs():
    external = Wrench((0, 0, 0), (0, 0, 2), (0, 0, 0), FRAME)
    result = solve(external)
    verify_balance_directly(external, result["reactions"])
    assert any(
        abs(row["force_scalar_n"]) > 0.1
        for row in result["reactions"]
        if not row["identifier"].endswith("-2")
    )
    assert all(
        abs(row["force_scalar_n"]) < 1e-12
        for row in result["reactions"]
        if row["identifier"].endswith("-2")
    )


def test_weighted_allocation_is_stationary_and_minimal_along_balanced_null_motion():
    supports = tuple(
        replace(channel, relative_weight=1 + index * 0.2)
        for index, channel in enumerate(channels())
    )
    external = Wrench((2, -3, -70), (4, 1, 0.2), (0, 0, 0), FRAME)
    result = solve(external, supports)
    forces = [row["force_scalar_n"] for row in result["reactions"]]
    null = [0.0] * 12
    for point, sign in enumerate((1, -1, 1, -1)):
        null[point * 3 + 2] = sign
    derivative = sum(
        force * variation / channel.relative_weight
        for force, variation, channel in zip(forces, null, supports, strict=True)
    )
    assert derivative == pytest.approx(0, abs=1e-10)
    base_norm = sum(
        force**2 / channel.relative_weight for force, channel in zip(forces, supports, strict=True)
    )
    for delta in (-10, -1, 1, 10):
        changed = sum(
            (force + delta * variation) ** 2 / channel.relative_weight
            for force, variation, channel in zip(forces, null, supports, strict=True)
        )
        assert changed > base_norm
    scaled = tuple(
        replace(channel, relative_weight=channel.relative_weight * 1e8) for channel in supports
    )
    result2 = solve(external, scaled)
    assert [row["force_scalar_n"] for row in result2["reactions"]] == pytest.approx(
        forces, abs=1e-10
    )


def test_coordinate_rotation_translation_and_reference_shift_preserve_reactions():
    angle = 0.41
    c, s = math.cos(angle), math.sin(angle)
    transform = ((c, -s, 0, 0.17), (s, c, 0, -0.21), (0, 0, 1, 0.13), (0, 0, 0, 1))
    external = Wrench((17, -11, -80), (1.2, 3.1, -0.8), (0.01, 0.02, 0.03), FRAME)
    supports = channels()
    expected = [row["force_scalar_n"] for row in solve(external, supports)["reactions"]]
    rotated = transform_wrench(external, transform, "rotated_synthetic_plate")
    rotated_supports = tuple(
        replace(
            channel,
            common_from_support=compose(transform, channel.common_from_support),
            frame=rotated.frame,
        )
        for channel in supports
    )
    result = solve(rotated, rotated_supports)
    assert [row["force_scalar_n"] for row in result["reactions"]] == pytest.approx(
        expected, abs=1e-9
    )
    shifted = shift_wrench_reference(external, (-0.09, 0.17, 0.04))
    assert [
        row["force_scalar_n"] for row in solve(shifted, supports)["reactions"]
    ] == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize(
    "points,normal_only,rank",
    [
        (POINTS, True, 3),
        (POINTS[:1], False, 3),
        ((POINTS[0], POINTS[2]), False, 5),
        (((0, 0, 0), (0.1, 0, 0), (0.2, 0, 0)), False, 5),
    ],
)
def test_incomplete_layouts_reject_full_wrench_without_dropping_components(
    points, normal_only, rank
):
    external = Wrench((12, -7, -60), (3, -4, 1.2), (0, 0, 0), FRAME)
    with pytest.raises(SingularSupportLayout) as caught:
        solve(external, channels(points, normal_only=normal_only))
    diagnostic = caught.value.diagnostic
    assert diagnostic["numerical_rank"] == rank
    assert diagnostic["unsolved_external_wrench"] == asdict(external)
    assert diagnostic["condition_number"] is None
    assert not diagnostic["partial_reactions_accepted"]


def test_special_vertical_wrench_does_not_make_normal_only_model_fully_constrained():
    with pytest.raises(SingularSupportLayout):
        solve(Wrench((0, 0, -10), (0, 0, 0), (0, 0, 0), FRAME), channels(normal_only=True))


def test_sign_violating_minimum_does_not_claim_no_feasible_alternative_exists():
    base = channels(POINTS[:3])
    duplicate = replace(base[2], identifier="one-sided-extra", allowed_sign="nonnegative")
    supports = (*base, duplicate)
    external = Wrench((0, 0, 12), (0, 0, 0), (0, 0, 0), FRAME)
    result = solve(external, supports)
    assert "one-sided-extra" in result["sign_violations"]
    assert not result["chosen_allocation_satisfies_allowed_signs"]
    assert result["constrained_feasibility"] == (
        "unknown_chosen_candidate_invalid_other_allocations_not_checked"
    )
    # Exhibit a distinct feasible allocation: solve the bilateral full-rank base
    # and set the extra nonnegative channel to zero. Hence the failed chosen
    # minimum cannot prove the constrained reaction set is empty.
    alternative = solve(external, base)
    witness = [
        *alternative["reactions"],
        {
            "identifier": duplicate.identifier,
            "point_m": duplicate.point_in_common_frame_m(),
            "force_n": (0, 0, 0),
            "force_scalar_n": 0,
        },
    ]
    verify_balance_directly(external, witness)
    assert alternative["chosen_allocation_satisfies_allowed_signs"]
    assert witness[-1]["force_scalar_n"] >= 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("relative_weight", 0),
        ("relative_weight", math.nan),
        ("relative_weight", True),
        ("local_direction_unit", (2, 0, 0)),
        ("local_direction_unit", (0, 0, 0)),
        ("common_from_support", ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1))),
        ("provenance", ""),
        ("allowed_sign", "unlimited_motor"),
        ("frame", ""),
    ],
)
def test_invalid_support_models_fail(field, value):
    with pytest.raises(ValueError):
        replace(channels()[0], **{field: value})


@pytest.mark.parametrize(
    "bad",
    [
        "duplicate",
        "wrong_frame",
        "missing_evidence",
        "length",
        "rank_tolerance",
        "bool_rank",
        "nonfinite_wrench",
    ],
)
def test_invalid_solver_inputs_fail(bad):
    supports = channels()
    external = Wrench((0, 0, -10), (0, 0, 0), (0, 0, 0), FRAME)
    kwargs = {}
    if bad == "duplicate":
        supports = (*supports, supports[0])
    elif bad == "wrong_frame":
        supports = (replace(supports[0], frame="unregistered_other_frame"), *supports[1:])
    elif bad == "missing_evidence":
        kwargs["allocation_evidence"] = ""
    elif bad == "length":
        kwargs["characteristic_length_m"] = 0
    elif bad == "rank_tolerance":
        kwargs["relative_rank_tolerance"] = 0
    elif bad == "bool_rank":
        kwargs["relative_rank_tolerance"] = True
    else:
        with pytest.raises(ValueError):
            Wrench((math.inf, 0, 0), (0, 0, 0), (0, 0, 0), FRAME)
        return
    with pytest.raises(ValueError):
        solve(external, supports, **kwargs)


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "thor_mount_reactions", ROOT / "tools/thor_mount_reactions.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_study_reproduces_source_holes_frozen_wrenches_and_report():
    tool = load_tool()
    result = tool.build_study()
    tracked = json.loads((ROOT / "hardware/cad/thor-mount-reaction-study-v1.json").read_text())
    assert json.loads(json.dumps(result)) == tracked
    source = json.loads((ROOT / "hardware/cad/thor-fabrication-interfaces.json").read_text())
    expected = [
        (*[value / 1000 for value in point], 0)
        for point in source["base_mount_summary"]["hole_centers_xy_mm"]
    ]
    assert result["layouts"]["source_bore_points_m"] == expected
    assert len(result["cases"]) == 6
    assert [
        row["diagnostic"]["numerical_rank"] for row in result["rejected_incomplete_support_models"]
    ] == [3, 5]
    for case in result["cases"]:
        payload = case["result"]
        external = Wrench(**payload["external_wrench"])
        verify_balance_directly(external, payload["reactions"])
        assert not any(payload["qualification"].values())
    preserved = json.loads((ROOT / "hardware/cad/thor-wrist-load-study-v2.json").read_text())
    load_case = next(
        case
        for case in preserved["cases"]
        if case["material_reference"]["family"] == "PLA"
        and case["scenario_name"] == "bevel_sign_positive"
    )
    for name, result_index in (("upright", 0), ("shoulder_horizontal", 2)):
        raw = next(
            row for row in load_case["poses"][name]["payload_cases"] if row["payload_kg"] == 0.2
        )["gravity_wrench_about_frame_origin"]
        transformed = result["cases"][result_index]["result"]["external_wrench"]
        fx, fy, fz = raw["external_force_n"]
        mx, my, mz = raw["external_moment_nm"]
        assert transformed["force_n"] == pytest.approx((-fy, fx, fz))
        assert transformed["moment_nm"] == pytest.approx((-my, mx, mz))


def explicit_case():
    return {
        "schema_version": 1,
        "evidence_class": "conditional_mount_input",
        "units": {"force": "N", "moment": "N*m", "length": "m"},
        "wrench": asdict(Wrench((0, 0, -10), (1, -2, 0.2), (0, 0, 0), FRAME)),
        "channels": [asdict(channel) for channel in channels()],
        "allocation": {
            "method": "minimum_weighted_force_norm",
            "evidence": "synthetic fixtures, not real support properties",
            "characteristic_length_m": 0.1,
        },
    }


@pytest.mark.parametrize(
    "bad", ["bool_schema", "unit", "missing_wrench", "unknown_option", "method"]
)
def test_external_case_schema_rejects_incomplete_or_ambiguous_inputs(bad):
    case = copy.deepcopy(explicit_case())
    if bad == "bool_schema":
        case["schema_version"] = True
    elif bad == "unit":
        case["units"]["length"] = "mm"
    elif bad == "missing_wrench":
        del case["wrench"]
    elif bad == "unknown_option":
        case["allocation"]["stiffness_measured"] = True
    else:
        case["allocation"]["method"] = "split_weight_equally"
    with pytest.raises(ValueError):
        load_tool().analyze_case(case)


def test_installed_cli_succeeds_and_singular_case_fails_without_writing_success(tmp_path):
    tool = ROOT / "tools/thor_mount_reactions.py"
    case = explicit_case()
    path, output = tmp_path / "case.json", tmp_path / "result.json"
    path.write_text(json.dumps(case))
    run = subprocess.run(
        [sys.executable, str(tool), "--case-file", str(path), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert b"\r\n" not in output.read_bytes()
    assert json.loads(output.read_text())["equilibrium"]["all_six_components_checked"]
    case["channels"] = [asdict(channel) for channel in channels(normal_only=True)]
    path.write_text(json.dumps(case))
    output.unlink()
    run = subprocess.run(
        [sys.executable, str(tool), "--case-file", str(path), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 2
    assert json.loads(run.stderr)["numerical_rank"] == 3
    assert not output.exists()


def test_mount_cli_preserves_existing_output_and_input_case(tmp_path):
    command = [sys.executable, str(ROOT / "tools/thor_mount_reactions.py")]
    case, output = tmp_path / "case.json", tmp_path / "historical.json"
    original_case = json.dumps(explicit_case()).encode()
    case.write_bytes(original_case)
    output.write_bytes(b"preserved historical bytes\n")
    run = subprocess.run(
        command + ["--case-file", str(case), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "already exists" in run.stderr
    assert output.read_bytes() == b"preserved historical bytes\n"
    run = subprocess.run(
        command + ["--case-file", str(case), "--output", str(case)], capture_output=True, text=True
    )
    assert run.returncode != 0 and "cannot replace an input" in run.stderr
    assert case.read_bytes() == original_case


def test_mount_cli_rejects_duplicate_json_keys(tmp_path):
    case, output = tmp_path / "bad.json", tmp_path / "new-result.json"
    case.write_text('{"schema_version": 1, "schema_version": 1}')
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/thor_mount_reactions.py"),
            "--case-file",
            str(case),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "duplicate JSON key" in run.stderr
    assert not output.exists()
