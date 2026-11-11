"""Conditional rigid-interface force allocation, never mount/clamp qualification.

Each scalar reaction acts along a declared local support direction. Redundant
reactions minimize an explicitly weighted force norm. These numerical weights
are an allocation assumption, not measured stiffness, preload or friction.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from raftel_arm01.kinematics.thor_frames import (
    Matrix,
    finite,
    rigid_transform,
    transform_point,
)
from raftel_arm01.kinematics.thor_jacobian import symmetric_eigenvalues

Vector = tuple[float, float, float]


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value


def _vector(value: Sequence[float]) -> Vector:
    if not isinstance(value, Sequence) or len(value) != 3:
        raise ValueError("expected three finite SI vector components")
    return tuple(finite(component) for component in value)


def _cross(left: Vector, right: Vector) -> Vector:
    x, y, z = left
    a, b, c = right
    return _vector((y * c - z * b, z * a - x * c, x * b - y * a))


def _sum(values) -> float:
    try:
        return finite(math.fsum(values))
    except OverflowError as error:
        raise ValueError("reaction calculation overflowed") from error


@dataclass(frozen=True)
class Wrench:
    """External wrench about an explicit point, expressed in one common frame."""

    force_n: Vector
    moment_nm: Vector
    reference_point_m: Vector
    frame: str

    def __post_init__(self):
        object.__setattr__(self, "force_n", _vector(self.force_n))
        object.__setattr__(self, "moment_nm", _vector(self.moment_nm))
        object.__setattr__(self, "reference_point_m", _vector(self.reference_point_m))
        _text(self.frame, "wrench frame")


@dataclass(frozen=True)
class ReactionChannel:
    """One force component at a support-frame origin, with an assumed allocation weight.

    ``common_from_support`` maps a local support point/direction into ``frame``.
    ``allowed_sign`` constrains the reported candidate only; the optimizer does
    not solve inequality constraints or establish preload/contact availability.
    """

    identifier: str
    common_from_support: Matrix
    local_direction_unit: Vector
    relative_weight: float
    allowed_sign: str
    frame: str
    provenance: str

    def __post_init__(self):
        _text(self.identifier, "reaction identifier")
        _text(self.frame, "reaction frame")
        _text(self.provenance, "reaction provenance")
        object.__setattr__(self, "common_from_support", rigid_transform(self.common_from_support))
        direction = _vector(self.local_direction_unit)
        if not math.isclose(math.hypot(*direction), 1, abs_tol=1e-10):
            raise ValueError("reaction direction must be a unit vector")
        object.__setattr__(self, "local_direction_unit", direction)
        weight = finite(self.relative_weight)
        if weight <= 0:
            raise ValueError("relative allocation weight must be positive")
        object.__setattr__(self, "relative_weight", weight)
        if not isinstance(self.allowed_sign, str) or self.allowed_sign not in {
            "bilateral",
            "nonnegative",
            "nonpositive",
        }:
            raise ValueError("allowed_sign must be bilateral, nonnegative or nonpositive")

    def direction_in_common_frame(self) -> Vector:
        return _vector(
            tuple(
                _sum(
                    self.common_from_support[i][j] * self.local_direction_unit[j] for j in range(3)
                )
                for i in range(3)
            )
        )

    def point_in_common_frame_m(self) -> Vector:
        return tuple(self.common_from_support[i][3] for i in range(3))


class SingularSupportLayout(ValueError):
    """No accepted arbitrary-six-component wrench model; retains the complete request."""

    def __init__(self, diagnostic: dict):
        self.diagnostic = diagnostic
        super().__init__(
            f"support map rank {diagnostic['numerical_rank']} < 6; full wrench remains unsolved"
        )


def shift_wrench_reference(wrench: Wrench, reference_point_m: Vector) -> Wrench:
    point = _vector(reference_point_m)
    offset = _vector(tuple(wrench.reference_point_m[i] - point[i] for i in range(3)))
    moment = _cross(offset, wrench.force_n)
    return Wrench(
        wrench.force_n,
        tuple(_sum((wrench.moment_nm[i], moment[i])) for i in range(3)),
        point,
        wrench.frame,
    )


def transform_wrench(wrench: Wrench, parent_from_common: Matrix, parent_frame: str) -> Wrench:
    """Rotate F/M and move the reference point together, preserving its physical meaning."""
    transform = rigid_transform(parent_from_common)
    return Wrench(
        tuple(_sum(transform[i][j] * wrench.force_n[j] for j in range(3)) for i in range(3)),
        tuple(_sum(transform[i][j] * wrench.moment_nm[j] for j in range(3)) for i in range(3)),
        transform_point(transform, wrench.reference_point_m),
        parent_frame,
    )


def _solve_six(matrix: Matrix, right: tuple[float, ...]) -> tuple[float, ...]:
    working = [list(row) + [right[i]] for i, row in enumerate(matrix)]
    ceiling = max(abs(component) for row in matrix for component in row)
    for column in range(6):
        pivot = max(range(column, 6), key=lambda i: abs(working[i][column]))
        if abs(working[pivot][column]) <= ceiling * 1e-14:
            raise ValueError("support solve is numerically singular")
        working[column], working[pivot] = working[pivot], working[column]
        scale = working[column][column]
        working[column] = [finite(value / scale) for value in working[column]]
        for row in range(6):
            if row == column:
                continue
            factor = working[row][column]
            working[row] = [_sum((working[row][j], -factor * working[column][j])) for j in range(7)]
    return tuple(working[row][6] for row in range(6))


def solve_reactions(
    wrench: Wrench,
    channels: Sequence[ReactionChannel],
    *,
    allocation_evidence: str,
    characteristic_length_m: float,
    relative_rank_tolerance: float = 1e-6,
    relative_equilibrium_tolerance: float = 1e-9,
    absolute_force_tolerance_n: float = 1e-9,
    absolute_moment_tolerance_nm: float = 1e-10,
) -> dict:
    """Allocate a full wrench under an explicit minimum weighted-force-norm assumption.

    For equilibrium matrix A=[u; r×u] and positive diagonal weights W, the
    candidate is f=W Aᵀ(A W Aᵀ)⁻¹(-external_wrench). Moment rows are scaled by
    an explicit characteristic length only for the numerical solve/diagnostics.
    Rank-deficient layouts are rejected even when one special load is reactable.

    Sign-violating minima do not prove no constrained solution exists: another
    force allocation may satisfy the bounds. That feasibility remains unknown.
    """
    if not isinstance(wrench, Wrench):
        raise ValueError("an explicit Wrench is required")
    if not isinstance(channels, Sequence) or not 1 <= len(channels) <= 128:
        raise ValueError("supply between 1 and 128 reaction channels")
    if any(not isinstance(channel, ReactionChannel) for channel in channels):
        raise ValueError("all support channels must be ReactionChannel models")
    identifiers = [channel.identifier for channel in channels]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate reaction channel identifier")
    if any(channel.frame != wrench.frame for channel in channels):
        raise ValueError("wrench and support frames must match explicitly")
    _text(allocation_evidence, "allocation evidence")
    length = finite(characteristic_length_m)
    rank_tolerance = finite(relative_rank_tolerance)
    equilibrium_tolerance = finite(relative_equilibrium_tolerance)
    force_tolerance = finite(absolute_force_tolerance_n)
    moment_tolerance = finite(absolute_moment_tolerance_nm)
    if length <= 0 or not 1e-6 <= rank_tolerance < 1:
        raise ValueError("positive characteristic length and rank tolerance in [1e-6,1) required")
    if not 0 < equilibrium_tolerance < 1 or force_tolerance <= 0 or moment_tolerance <= 0:
        raise ValueError("positive bounded equilibrium tolerances required")
    columns, locations, directions = [], [], []
    for channel in channels:
        location = channel.point_in_common_frame_m()
        direction = channel.direction_in_common_frame()
        relative = _vector(tuple(location[i] - wrench.reference_point_m[i] for i in range(3)))
        moment = _cross(relative, direction)
        columns.append(tuple(direction) + tuple(finite(value / length) for value in moment))
        locations.append(location)
        directions.append(direction)
    ceiling_weight = max(channel.relative_weight for channel in channels)
    weights = [finite(channel.relative_weight / ceiling_weight) for channel in channels]
    if any(weight <= 0 for weight in weights):
        raise ValueError("relative allocation weights are numerically disparate")
    gram = tuple(
        tuple(
            _sum(
                weight * column[i] * column[j]
                for weight, column in zip(weights, columns, strict=True)
            )
            for j in range(6)
        )
        for i in range(6)
    )
    eigenvalues = symmetric_eigenvalues(gram)
    highest = max(eigenvalues[0], 0)
    if any(value < -1e-12 * max(highest, 1e-30) for value in eigenvalues):
        raise ValueError("support Gram matrix lost positive semidefiniteness")
    singular = tuple(math.sqrt(max(value, 0)) for value in eigenvalues)
    rank = sum(value > singular[0] * rank_tolerance for value in singular) if singular[0] else 0
    diagnostic = {
        "characteristic_length_m": length,
        "relative_rank_tolerance": rank_tolerance,
        "scaled_support_singular_values": singular,
        "numerical_rank": rank,
        "condition_number": singular[0] / singular[-1] if rank == 6 else None,
    }
    if rank != 6:
        raise SingularSupportLayout(
            {
                **diagnostic,
                "evidence_class": "incomplete_support_model_not_a_load_capacity_result",
                "unsolved_external_wrench": asdict(wrench),
                "partial_reactions_accepted": False,
            }
        )
    target = tuple(-value for value in wrench.force_n) + tuple(
        finite(-value / length) for value in wrench.moment_nm
    )
    multiplier = _solve_six(gram, target)
    reactions = [
        finite(
            weight
            * _sum(component * value for component, value in zip(column, multiplier, strict=True))
        )
        for weight, column in zip(weights, columns, strict=True)
    ]
    reaction_forces = [
        _vector(tuple(finite(force * component) for component in direction))
        for force, direction in zip(reactions, directions, strict=True)
    ]
    reaction_moments = [
        _cross(_vector(tuple(point[i] - wrench.reference_point_m[i] for i in range(3))), force)
        for point, force in zip(locations, reaction_forces, strict=True)
    ]
    force_residual = tuple(
        _sum([wrench.force_n[i], *[f[i] for f in reaction_forces]]) for i in range(3)
    )
    moment_residual = tuple(
        _sum([wrench.moment_nm[i], *[m[i] for m in reaction_moments]]) for i in range(3)
    )
    force_limit = finite(force_tolerance + equilibrium_tolerance * math.hypot(*wrench.force_n))
    moment_limit = finite(moment_tolerance + equilibrium_tolerance * math.hypot(*wrench.moment_nm))
    if math.hypot(*force_residual) > force_limit or math.hypot(*moment_residual) > moment_limit:
        raise ValueError("allocated reactions fail the complete SI wrench residual check")
    sign_violations = [
        channel.identifier
        for channel, force in zip(channels, reactions, strict=True)
        if (
            (channel.allowed_sign == "nonnegative" and force < -force_tolerance)
            or (channel.allowed_sign == "nonpositive" and force > force_tolerance)
        )
    ]
    return {
        "schema_version": 1,
        "evidence_class": "conditional_rigid_interface_force_allocation_not_mount_qualification",
        "external_wrench": asdict(wrench),
        "allocation": {
            "method": "minimum_weighted_force_norm",
            "objective": "minimize norm(f_i/sqrt(relative_weight_i)) subject to full equilibrium",
            "assumption_evidence": allocation_evidence,
            "weights_are_measured_stiffness": False,
            "inequality_constrained_optimization_performed": False,
        },
        "diagnostic": diagnostic,
        "reactions": [
            {
                "identifier": channel.identifier,
                "point_m": location,
                "direction_unit_in_common_frame": direction,
                "force_scalar_n": force,
                "force_n": reaction_force,
                "moment_about_reference_nm": moment,
                "relative_weight": channel.relative_weight,
                "allowed_sign": channel.allowed_sign,
                "provenance": channel.provenance,
            }
            for channel, location, direction, force, reaction_force, moment in zip(
                channels,
                locations,
                directions,
                reactions,
                reaction_forces,
                reaction_moments,
                strict=True,
            )
        ],
        "equilibrium": {
            "force_residual_n": force_residual,
            "moment_residual_nm": moment_residual,
            "force_residual_tolerance_n": force_limit,
            "moment_residual_tolerance_nm": moment_limit,
            "all_six_components_checked": True,
        },
        "chosen_allocation_satisfies_allowed_signs": not sign_violations,
        "sign_violations": sign_violations,
        "constrained_feasibility": (
            "chosen_candidate_satisfies_declared_sign_constraints"
            if not sign_violations
            else "unknown_chosen_candidate_invalid_other_allocations_not_checked"
        ),
        "qualification": {
            "stiffness_or_preload_verified": False,
            "friction_slip_pullout_or_desk_crushing_checked": False,
            "plate_bending_or_material_strength_checked": False,
            "physical_mount_feasibility_established": False,
            "manufacturing_release": False,
        },
    }
