"""Bounded local pose IK for the nominal source model only.

This pure numerical experiment uses explicit provisional joint boxes. A local
failure is not proof of global infeasibility, and a converged pose is not
collision-free, physically calibrated, dynamically feasible or safe to move to.
The solver is deliberately disconnected from the logical sorter and control.
"""

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass

from .thor_constraints import ConstraintSet, validate_joint_state
from .thor_frames import Matrix, finite, multiply, rigid_transform, transpose
from .thor_jacobian import spatial_jacobian
from .thor_model import (
    JOINT_Z_OFFSETS_M,
    SOURCE_REVISION,
    TOOL_Z_OFFSETS_M,
    _angles,
    forward_kinematics,
)


def rotation_error(target: Matrix, current: Matrix) -> tuple[float, float, float]:
    """Shortest SO(3) log of target_R current_R^T in source base_link.

    Quaternion extraction avoids the sin(theta) division that becomes singular
    near a half-turn. At exactly pi the shortest axis sign is nonunique.
    """
    desired, actual = rigid_transform(target), rigid_transform(current)
    rotation = multiply(
        tuple(tuple(row[:3]) for row in desired[:3]),
        transpose(tuple(tuple(row[:3]) for row in actual[:3])),
    )
    trace = sum(rotation[i][i] for i in range(3))
    if trace > 0:
        scale = 2 * math.sqrt(max(1 + trace, 0))
        w = scale / 4
        vector = (
            (rotation[2][1] - rotation[1][2]) / scale,
            (rotation[0][2] - rotation[2][0]) / scale,
            (rotation[1][0] - rotation[0][1]) / scale,
        )
    else:
        i = max(range(3), key=lambda k: rotation[k][k])
        j, k = (i + 1) % 3, (i + 2) % 3
        scale = 2 * math.sqrt(max(1 + rotation[i][i] - rotation[j][j] - rotation[k][k], 0))
        w = (rotation[k][j] - rotation[j][k]) / scale
        vector_list = [0.0] * 3
        vector_list[i] = scale / 4
        vector_list[j] = (rotation[j][i] + rotation[i][j]) / scale
        vector_list[k] = (rotation[k][i] + rotation[i][k]) / scale
        vector = tuple(vector_list)
    if w < 0:
        w, vector = -w, tuple(-component for component in vector)
    norm = math.hypot(*vector)
    if norm < 1e-14:
        return tuple(2 * component for component in vector)
    angle = 2 * math.atan2(norm, w)
    return tuple(component * angle / norm for component in vector)


def _linear_solve(matrix: Matrix, vector: Sequence[float]) -> tuple[float, ...]:
    """Pivoted tiny dense solve; called only for regularized 6x6 systems."""
    augmented = [list(row) + [value] for row, value in zip(matrix, vector, strict=True)]
    for i in range(6):
        pivot = max(range(i, 6), key=lambda k: abs(augmented[k][i]))
        augmented[i], augmented[pivot] = augmented[pivot], augmented[i]
        diagonal = augmented[i][i]
        if abs(diagonal) < 1e-20:
            raise ValueError("regularized IK linear system is singular")
        augmented[i] = [component / diagonal for component in augmented[i]]
        for j in range(i + 1, 6):
            coefficient = augmented[j][i]
            augmented[j] = [
                a - coefficient * b for a, b in zip(augmented[j], augmented[i], strict=True)
            ]
    result = [0.0] * 6
    for i in range(5, -1, -1):
        result[i] = augmented[i][-1] - math.fsum(
            augmented[i][j] * result[j] for j in range(i + 1, 6)
        )
    return tuple(finite(value) for value in result)


@dataclass(frozen=True)
class IKOptions:
    max_iterations: int = 160
    max_seconds: float = 2.0
    position_tolerance_m: float = 1e-6
    orientation_tolerance_rad: float = 1e-5
    characteristic_length_m: float = 0.3
    damping: float = 1e-3
    max_joint_step_rad: float = 0.25
    line_search_steps: int = 12

    def __post_init__(self) -> None:
        for field, lower, upper in (("max_iterations", 1, 10000), ("line_search_steps", 1, 20)):
            value = getattr(self, field)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"{field} must be an integer in [{lower},{upper}]")
        for field in (
            "max_seconds",
            "position_tolerance_m",
            "orientation_tolerance_rad",
            "characteristic_length_m",
            "damping",
            "max_joint_step_rad",
        ):
            value = finite(getattr(self, field))
            if value <= 0:
                raise ValueError(f"{field} must be positive")
            object.__setattr__(self, field, value)
        if self.max_seconds > 30 or not 1e-8 <= self.max_joint_step_rad <= math.pi:
            raise ValueError("IK requires <=30 seconds and a step in [1e-8,pi] rad")
        if not 1e-8 <= self.damping <= 1 or not 1e-9 <= self.characteristic_length_m <= 1e6:
            raise ValueError(
                "IK numeric scaling requires damping in [1e-8,1] and length in [1e-9,1e6]"
            )


@dataclass(frozen=True)
class IKResult:
    converged: bool
    reason: str
    joints_rad: tuple[float, ...]
    iterations: int
    position_residual_m: float
    orientation_residual_rad: float
    target: str
    constraint_revision: str
    constraint_family: str
    model_source_revision: str = SOURCE_REVISION
    validation_class: str = "nominal_local_kinematic_solution_not_collision_or_hardware_validation"


def solve_pose_ik(
    target_pose: Matrix,
    seed_rad: Sequence[float],
    constraints: ConstraintSet,
    *,
    target: str = "link_6",
    family: str = "study",
    options: IKOptions | None = None,
) -> IKResult:
    """Run a projected damped-least-squares local solve with finite work bounds.

    The caller chooses a seed and a declared source/study box. Success requires
    both independent position and orientation tolerances. Iterations, line
    search evaluations and wall time are bounded. No channel output is created.
    """
    desired, q = rigid_transform(target_pose), _angles(seed_rad)
    if not isinstance(constraints, ConstraintSet):
        raise ValueError("constraints must be a ConstraintSet")
    if not isinstance(family, str) or family not in {"source", "study"}:
        raise ValueError("nominal IK accepts source or study constraints only")
    if options is None:
        options = IKOptions()
    if not isinstance(options, IKOptions):
        raise ValueError("options must be IKOptions")
    violations = validate_joint_state(q, constraints, family=family)
    if violations:
        raise ValueError("seed violates declared constraints: " + "; ".join(violations))
    bounds = constraints.bounds(family)
    start = time.monotonic()

    def residual(angles: tuple[float, ...]) -> tuple[tuple[float, ...], float, float]:
        actual = forward_kinematics(angles, target)
        delta = tuple(desired[i][3] - actual[i][3] for i in range(3))
        orientation = rotation_error(desired, actual)
        return (
            (
                *tuple(component / options.characteristic_length_m for component in delta),
                *orientation,
            ),
            finite(math.hypot(*delta)),
            finite(math.hypot(*orientation)),
        )

    error, position_norm, orientation_norm = residual(q)

    def result(reason: str, iterations: int) -> IKResult:
        return IKResult(
            reason == "converged",
            reason,
            q,
            iterations,
            position_norm,
            orientation_norm,
            target,
            constraints.revision,
            family,
        )

    # Triangle inequality is a rejection bound only; inside does not prove IK.
    reach = sum(JOINT_Z_OFFSETS_M)
    if target in {"gripper_base", "gripper_mid_point"}:
        reach += TOOL_Z_OFFSETS_M[0]
    if target == "gripper_mid_point":
        reach += TOOL_Z_OFFSETS_M[1]
    if math.hypot(*(desired[i][3] for i in range(3))) > reach + options.position_tolerance_m:
        return result("outside_nominal_reach_bound", 0)

    for iteration in range(options.max_iterations + 1):
        if time.monotonic() - start >= options.max_seconds:
            return result("time_limit", iteration)
        if (
            position_norm <= options.position_tolerance_m
            and orientation_norm <= options.orientation_tolerance_rad
        ):
            return result("converged", iteration)
        if iteration == options.max_iterations:
            return result("iteration_limit", iteration)
        jacobian = spatial_jacobian(q, target)
        scaled = tuple(
            tuple(
                component / options.characteristic_length_m if i < 3 else component
                for component in row
            )
            for i, row in enumerate(jacobian)
        )
        gram = multiply(scaled, transpose(scaled))
        regularized = tuple(
            tuple(gram[i][j] + (options.damping**2 if i == j else 0) for j in range(6))
            for i in range(6)
        )
        dual = _linear_solve(regularized, error)
        direction = tuple(math.fsum(scaled[i][j] * dual[i] for i in range(6)) for j in range(6))
        largest = max(abs(value) for value in direction)
        factor = min(1.0, options.max_joint_step_rad / largest) if largest else 1.0
        objective = math.fsum(value * value for value in error)
        improved = False
        for step in range(options.line_search_steps):
            if time.monotonic() - start >= options.max_seconds:
                return result("time_limit", iteration)
            scale = factor * 0.5**step
            candidate = tuple(
                min(bound.upper_rad, max(bound.lower_rad, value + scale * delta))
                for value, delta, bound in zip(q, direction, bounds, strict=True)
            )
            candidate_error, candidate_position, candidate_orientation = residual(candidate)
            if math.fsum(value * value for value in candidate_error) < objective:
                q, error, position_norm, orientation_norm = (
                    candidate,
                    candidate_error,
                    candidate_position,
                    candidate_orientation,
                )
                improved = True
                break
        if not improved:
            at_limit = any(
                abs(value - bound.lower_rad) < 1e-10 or abs(value - bound.upper_rad) < 1e-10
                for value, bound in zip(q, bounds, strict=True)
            )
            return result("stalled_at_limits" if at_limit else "stalled", iteration + 1)
    raise AssertionError("bounded IK loop did not return")
