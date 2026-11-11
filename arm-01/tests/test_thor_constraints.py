"""Provisional bounds are source records, never motion authorization."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from raftel_arm01.kinematics.thor_constraints import (
    ConstraintSet,
    JointConstraint,
    audit_source_constraints,
    load_constraints,
    validate_joint_state,
)

ROOT = Path(__file__).parents[1]


@pytest.fixture
def constraints():
    return load_constraints(ROOT / "config/thor-constraints-v1.json")


def test_exact_source_limits_and_unknown_calibration(constraints):
    bounds = constraints.bounds("source")
    assert [bound.upper_rad for bound in bounds] == pytest.approx(
        [2.967, 3.14159265359 / 2, 3.14159265359 / 2, 2.967, 3.14159265359 / 2, 2.967]
    )
    assert [bound.max_velocity_rad_s for bound in bounds] == [0.58, 0.23, 0.23, 0.58, 1.45, 1.45]
    assert all(bound.max_acceleration_rad_s2 is None for bound in bounds)
    with pytest.raises(ValueError, match="unknown required calibrated"):
        constraints.bounds("calibrated")


def test_positions_rates_endpoints_and_explicit_violations(constraints):
    endpoint = tuple(bound.upper_rad for bound in constraints.bounds())
    assert not validate_joint_state(endpoint, constraints)
    assert not validate_joint_state(
        (0,) * 6, constraints, velocities_rad_s=(0.58, 0.23, 0.23, 0.58, 1.45, 1.45)
    )
    result = validate_joint_state(
        (4, 0, 0, 0, 0, 0), constraints, velocities_rad_s=(0, -0.24, 0, 0, 0, 0)
    )
    assert result == (
        "joint_1: position outside study bounds",
        "joint_2: velocity outside study bounds",
    )
    with pytest.raises(ValueError, match="acceleration limit is unknown"):
        validate_joint_state((0,) * 6, constraints, accelerations_rad_s2=(0,) * 6)


def test_unknown_required_position_bound_fails(constraints):
    joints = (replace(constraints.joints[0], study=None), *constraints.joints[1:])
    partial = ConstraintSet("partial-study", joints)
    with pytest.raises(ValueError, match="unknown required study"):
        validate_joint_state((0,) * 6, partial)


@pytest.mark.parametrize(
    "bad",
    [(), (0,) * 7, (0, 0, 0, 0, 0, True), (0, 0, 0, 0, 0, float("inf")), (0, 0, 0, 0, 0, "1")],
)
def test_invalid_coordinates_reject(bad, constraints):
    with pytest.raises(ValueError):
        validate_joint_state(bad, constraints)


def test_contradictions_nonfinite_and_rate_rejection(constraints):
    good = constraints.bounds()[0]
    for changes in (
        {"lower_rad": good.upper_rad},
        {"upper_rad": float("nan")},
        {"max_velocity_rad_s": 0},
        {"max_acceleration_rad_s2": True},
        {"evidence": ""},
    ):
        with pytest.raises(ValueError):
            replace(good, **changes)
    with pytest.raises(ValueError, match="subset"):
        JointConstraint("joint_1", good, replace(good, upper_rad=4), None)
    with pytest.raises(ValueError, match="rate"):
        JointConstraint("joint_1", good, replace(good, max_velocity_rad_s=1), None)
    with pytest.raises(ValueError, match="ordered"):
        ConstraintSet("bad-order", tuple(reversed(constraints.joints)))
    with pytest.raises(ValueError, match="family"):
        constraints.bounds("safe")
    with pytest.raises(ValueError, match="unknown nominal"):
        JointConstraint("joint_7", good, None, None)


def test_constraint_loader_invalid_and_duplicate_fields(tmp_path):
    path = tmp_path / "bounds.json"
    path.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_constraints(path)
    data = json.loads((ROOT / "config/thor-constraints-v1.json").read_text())
    del data["joints"][0]["study"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="fields"):
        load_constraints(path)


@pytest.mark.parametrize(
    "field,value",
    [("schema_version", True), ("schema_version", 1.0), ("source", None), ("revision", "")],
)
def test_constraint_manifest_schema_and_provenance_reject(tmp_path, field, value):
    data = json.loads((ROOT / "config/thor-constraints-v1.json").read_text())
    data[field] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_constraints(path)


def test_unknown_constraint_fields_and_stale_source_reject(tmp_path, constraints):
    data = json.loads((ROOT / "config/thor-constraints-v1.json").read_text())
    data["joints"][0]["safe_limit"] = {"upper_rad": 3}
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="fields"):
        load_constraints(path)
    path.write_text("changed source bytes", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256"):
        audit_source_constraints(path, constraints)


def test_source_audit_parser_fixture_and_declared_mismatch(tmp_path, constraints, monkeypatch):
    # A generated XML fixture exercises parser/comparison without network or
    # vendoring source. Pin monkeypatch is confined to this synthetic test.
    properties = '<xacro:property name="PI" value="3.14159265359"/>'
    joints = []
    for i, bound in enumerate(constraints.bounds("source"), 1):
        lower, upper = ("-2.967", "2.967") if i in (1, 4, 6) else ("-${PI / 2}", "${PI / 2}")
        joints.append(
            f'<joint name="joint_{i}"><limit lower="{lower}" upper="{upper}" '
            f'velocity="{bound.max_velocity_rad_s}"/></joint>'
        )
    content = f'<robot xmlns:xacro="http://www.ros.org/wiki/xacro">{properties}{"".join(joints)}</robot>'.encode()
    path = tmp_path / "synthetic.xacro"
    path.write_bytes(content)
    monkeypatch.setattr(
        "raftel_arm01.kinematics.thor_constraints.SOURCE_XACRO_SHA256",
        hashlib.sha256(content).hexdigest(),
    )
    report = audit_source_constraints(path, constraints)
    assert len(report["joints"]) == 6
    assert all(item["effort_adopted"] is False for item in report["joints"])
    changed = ConstraintSet(
        "changed-source",
        (
            replace(
                constraints.joints[0], source=replace(constraints.joints[0].source, upper_rad=2.98)
            ),
            *constraints.joints[1:],
        ),
    )
    with pytest.raises(ValueError, match="differ"):
        audit_source_constraints(path, changed)
