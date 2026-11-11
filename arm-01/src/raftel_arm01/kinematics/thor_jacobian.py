"""Nominal Thor geometric Jacobian and explicitly scaled singularity study.

The returned spatial/geometric Jacobian is expressed in source ``base_link``
at the chosen target point: top rows linear metres/radian, bottom rows angular
radians/radian. It is not the derivative of Euler angles or a body twist at
the base origin. No calibration, dynamics or collision claims are made.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .thor_frames import Matrix, finite, matrix, multiply, transform_point, transpose
from .thor_model import chain, forward_kinematics


def spatial_jacobian(
    joints_rad: Sequence[float],
    target: str = "link_6",
    *,
    point_offset_m: Sequence[float] = (0.0, 0.0, 0.0),
) -> Matrix:
    """Map joint rates to target point velocity and base-frame angular velocity.

    ``point_offset_m`` is fixed in the selected target frame. Supplying a
    scenario offset does not establish the physical TCP or contact location.
    """
    frames, _ = chain(joints_rad)
    point = transform_point(forward_kinematics(joints_rad, target), point_offset_m)
    columns = []
    for frame in frames:
        x, y, z = frame.axis_unit
        dx, dy, dz = (point[i] - frame.origin_m[i] for i in range(3))
        columns.append((y * dz - z * dy, z * dx - x * dz, x * dy - y * dx, x, y, z))
    return matrix(transpose(tuple(columns)), 6, 6)


def symmetric_eigenvalues(value: Matrix) -> tuple[float, ...]:
    """Small symmetric 6x6 Jacobi eigensolve for offline diagnostics.

    No external numerical dependency is needed. Eigenvectors are not returned;
    the implementation is intentionally limited to these tiny real matrices.
    """
    checked = matrix(value, 6, 6)
    scale = max(abs(component) for row in checked for component in row)
    tolerance = max(1e-15 * scale, 1e-30)
    if any(abs(checked[i][j] - checked[j][i]) > tolerance for i in range(6) for j in range(6)):
        raise ValueError("eigenvalue input must be symmetric")
    working = [list(row) for row in checked]
    for _ in range(180):
        p, q = max(
            ((i, j) for i in range(6) for j in range(i + 1, 6)),
            key=lambda pair: abs(working[pair[0]][pair[1]]),
        )
        if abs(working[p][q]) <= tolerance:
            break
        tau = (working[q][q] - working[p][p]) / (2 * working[p][q])
        t = math.copysign(1.0, tau) / (abs(tau) + math.hypot(1.0, tau))
        c, s = 1 / math.hypot(1, t), t / math.hypot(1, t)
        app, aqq, apq = working[p][p], working[q][q], working[p][q]
        working[p][p], working[q][q] = app - t * apq, aqq + t * apq
        working[p][q] = working[q][p] = 0.0
        for k in range(6):
            if k in (p, q):
                continue
            akp, akq = working[k][p], working[k][q]
            working[k][p] = working[p][k] = c * akp - s * akq
            working[k][q] = working[q][k] = s * akp + c * akq
    else:
        raise ValueError("symmetric eigenvalue iteration failed to converge")
    return tuple(sorted((finite(working[i][i]) for i in range(6)), reverse=True))


@dataclass(frozen=True)
class SingularityDiagnostic:
    characteristic_length_m: float
    relative_rank_tolerance: float
    singular_values: tuple[float, ...]
    numerical_rank: int
    condition_number: float | None
    validation_class: str = "nominal_scaled_jacobian_not_physical_clearance"


def singularity_diagnostic(
    jacobian: Matrix,
    *,
    characteristic_length_m: float,
    relative_rank_tolerance: float = 1e-6,
) -> SingularityDiagnostic:
    """Scale linear rows by an explicit length before dimensionless SVD metrics.

    A rank-deficient condition number is null, suitable for strict JSON. The
    threshold defines a numerical study, never a calibrated singularity margin.
    """
    length, tolerance = finite(characteristic_length_m), finite(relative_rank_tolerance)
    if length <= 0 or not 1e-6 <= tolerance < 1:
        raise ValueError("length must be positive; rank tolerance must be in [1e-6,1)")
    checked = matrix(jacobian, 6, 6)
    scaled = tuple(
        tuple(component / length if i < 3 else component for component in row)
        for i, row in enumerate(checked)
    )
    gram = multiply(scaled, transpose(scaled))
    eigenvalues = symmetric_eigenvalues(gram)
    ceiling = max(eigenvalues[0], 0.0)
    if any(value < -1e-12 * max(ceiling, 1e-30) for value in eigenvalues):
        raise ValueError("Jacobian Gram matrix lost positive semidefiniteness")
    values = tuple(math.sqrt(max(value, 0.0)) for value in eigenvalues)
    rank = sum(value > tolerance * values[0] for value in values) if values[0] else 0
    condition = values[0] / values[-1] if rank == 6 else None
    return SingularityDiagnostic(length, tolerance, values, rank, condition)
