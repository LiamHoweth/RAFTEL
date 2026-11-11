"""Partial offline rate/acceleration demand through declared constant maps.

Continuous source coordinates and conditional physical rotor coordinates stay
separate. Quantized source command strings have no smooth derivative here.
This module makes no capacity rating: inertia, friction, losses, motor curves,
thermal duty, backlash, cable limits and calibrated shaft references are absent.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

from raftel_arm01.kinematics.thor_constraints import ConstraintSet, validate_joint_state
from raftel_arm01.kinematics.thor_drive import joints_to_drive
from raftel_arm01.kinematics.thor_frames import finite
from raftel_arm01.kinematics.thor_trajectory import TimedJointState
from raftel_arm01.kinematics.thor_transmission import ElbowTransmission, WristDifferential

EVIDENCE_CLASS = "conditional_offline_coupled_demand_not_actuator_capacity"


@dataclass(frozen=True)
class CoupledDemandScenario:
    revision: str
    evidence_class: str
    evidence: str
    elbow: ElbowTransmission
    wrist: WristDifferential

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise ValueError("demand scenario requires a revision")
        if not isinstance(self.evidence_class, str) or self.evidence_class not in {
            "assumed",
            "synthetic",
        }:
            raise ValueError("demand mechanism must be explicitly assumed or synthetic")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("demand scenario requires mechanism provenance")
        if not isinstance(self.elbow, ElbowTransmission) or not isinstance(
            self.wrist, WristDifferential
        ):
            raise ValueError("demand scenario requires existing elbow and wrist models")


@dataclass(frozen=True)
class ProjectedMotion:
    coordinate_names: tuple[str, ...]
    coordinates_rad: tuple[float, ...]
    velocities_rad_s: tuple[float, ...]
    accelerations_rad_s2: tuple[float, ...]
    coordinate_interpretation: str


@dataclass(frozen=True)
class CoupledMotionDemand:
    time_s: float
    scenario_revision: str
    constraint_revision: str
    source_continuous: ProjectedMotion
    conditional_elbow_rotors: ProjectedMotion
    conditional_wrist_rotors: ProjectedMotion
    study_rate_evidence: tuple[str, ...]
    mechanism_scenario: dict
    evidence_class: str = EVIDENCE_CLASS
    complete_actuator_capacity: bool = False
    remaining_gates: tuple[str, ...] = (
        "joint1_joint4_and_gripper_physical_transmission_maps_unknown",
        "shaft_coordinate_rates_not_total_carried_body_angular_velocities",
        "constant_local_routing_radius_and_ratio_assumptions",
        "inertia_friction_efficiency_duty_and_motor_curves_missing",
        "no_cable_collision_feedback_or_calibrated_shaft_limits",
    )


@dataclass(frozen=True)
class LinearBoxExtremum:
    minimum: float
    maximum: float
    minimizing_joint_vector: tuple[float, ...]
    maximizing_joint_vector: tuple[float, ...]


@dataclass(frozen=True)
class ProjectedRateBox:
    coordinate_names: tuple[str, ...]
    constant_jacobian: tuple[tuple[float, ...], ...]
    velocity_extrema_rad_s: tuple[LinearBoxExtremum, ...]
    acceleration_extrema_rad_s2: tuple[LinearBoxExtremum, ...]
    coordinate_interpretation: str


@dataclass(frozen=True)
class CoupledRateBoxes:
    scenario_revision: str
    constraint_revision: str
    joint_velocity_abs_limits_rad_s: tuple[float, ...]
    joint_acceleration_abs_limits_rad_s2: tuple[float, ...]
    study_rate_evidence: tuple[str, ...]
    source_continuous: ProjectedRateBox
    conditional_elbow_rotors: ProjectedRateBox
    conditional_wrist_rotors: ProjectedRateBox
    mechanism_scenario: dict
    evidence_class: str = EVIDENCE_CLASS
    extrema_scope: str = (
        "exact_per_output_row_for_declared_independent_symmetric_joint_rate_boxes_"
        "different_rows_have_different_witness_states_not_path_or_capacity_extrema"
    )
    complete_actuator_capacity: bool = False


def _bounds(
    constraints: ConstraintSet,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[str, ...]]:
    if not isinstance(constraints, ConstraintSet):
        raise ValueError("explicit study constraints are required")
    bounds = constraints.bounds("study")
    if any(
        item.max_velocity_rad_s is None or item.max_acceleration_rad_s2 is None for item in bounds
    ):
        raise ValueError("every study velocity and acceleration bound must be explicitly known")
    return (
        tuple(item.max_velocity_rad_s for item in bounds),
        tuple(item.max_acceleration_rad_s2 for item in bounds),
        tuple(item.evidence for item in bounds),
    )


def _maps(scenario: CoupledDemandScenario) -> tuple[tuple[tuple[str, ...], str, Callable], ...]:
    if not isinstance(scenario, CoupledDemandScenario):
        raise ValueError("an explicit coupled demand scenario is required")
    return (
        (
            ("A", "B", "C", "D", "X", "Y", "Z"),
            "pinned_continuous_source_channel_coordinates_not_raw_rotor_angles",
            joints_to_drive,
        ),
        (
            ("shoulder_B", "shoulder_C", "elbow_E"),
            "conditional_physical_rotor_angles_not_source_B_C_D_or_Z_addresses",
            lambda q: scenario.elbow.rotor_coordinates(q[1], q[2]),
        ),
        (
            ("wrist_negative_y", "wrist_positive_y"),
            "conditional_physical_rotor_angles_not_source_Y_Z_addresses",
            lambda q: scenario.wrist.rotor_angles(q[4], q[5]),
        ),
    )


def project_motion(
    state: TimedJointState,
    constraints: ConstraintSet,
    *,
    scenario: CoupledDemandScenario,
) -> CoupledMotionDemand:
    """Project a T1 state only after explicit provisional scalar rate checks.

    Constant local transmission Jacobians map q, qdot and qddot with the same
    functions. Missing study acceleration limits fail; source URDF velocity
    limits alone never become a complete demand/capacity specification.
    """
    if not isinstance(state, TimedJointState):
        raise ValueError("state must reuse the offline TimedJointState contract")
    _, _, evidence = _bounds(constraints)
    violations = validate_joint_state(
        state.joints_rad,
        constraints,
        family="study",
        velocities_rad_s=state.velocities_rad_s,
        accelerations_rad_s2=state.accelerations_rad_s2,
    )
    if violations:
        raise ValueError("joint state violates declared study bounds: " + "; ".join(violations))
    projections = []
    for names, interpretation, function in _maps(scenario):
        projections.append(
            ProjectedMotion(
                names,
                tuple(function(state.joints_rad)),
                tuple(function(state.velocities_rad_s)),
                tuple(function(state.accelerations_rad_s2)),
                interpretation,
            )
        )
    return CoupledMotionDemand(
        state.time_s,
        scenario.revision,
        constraints.revision,
        projections[0],
        projections[1],
        projections[2],
        evidence,
        asdict(scenario),
    )


def _linear_matrix(
    function: Callable[[Sequence[float]], Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    columns = []
    for axis in range(6):
        basis = [0.0] * 6
        basis[axis] = 1.0
        columns.append(tuple(finite(value) for value in function(basis)))
    return tuple(tuple(column[row] for column in columns) for row in range(len(columns[0])))


def _extrema(row: Sequence[float], limits: Sequence[float]) -> LinearBoxExtremum:
    try:
        radius = finite(math.fsum(abs(a) * b for a, b in zip(row, limits, strict=True)))
    except OverflowError as error:
        raise ValueError("coupled rate extremum exceeds finite diagnostic range") from error
    witness = tuple(b if a > 0 else -b if a < 0 else 0.0 for a, b in zip(row, limits, strict=True))
    return LinearBoxExtremum(-radius, radius, tuple(-v for v in witness), witness)


def project_rate_boxes(
    constraints: ConstraintSet, *, scenario: CoupledDemandScenario
) -> CoupledRateBoxes:
    """Tight linear extrema with a separate witness for each output coordinate.

    Symmetric, independently selectable joint rates/accelerations are a declared
    study box, not a physically certified feasible set. The witnesses make each
    bound reviewable. Maxima of different coordinates need not occur together.
    """
    velocities, accelerations, evidence = _bounds(constraints)
    boxes = []
    for names, interpretation, function in _maps(scenario):
        matrix = _linear_matrix(function)
        boxes.append(
            ProjectedRateBox(
                names,
                matrix,
                tuple(_extrema(row, velocities) for row in matrix),
                tuple(_extrema(row, accelerations) for row in matrix),
                interpretation,
            )
        )
    return CoupledRateBoxes(
        scenario.revision,
        constraints.revision,
        velocities,
        accelerations,
        evidence,
        boxes[0],
        boxes[1],
        boxes[2],
        asdict(scenario),
    )
