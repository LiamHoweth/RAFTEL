"""SI centroidal inertia algebra with explicit unknown-property propagation.

These helpers do not invent inertia from a purchased mass or printed fraction.
Native geometric captures are separate inputs; they do not supply a physical
density or nonuniform material distribution.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from raftel_arm01.engineering.scenarios import finite_number

Vector3 = tuple[float, float, float]
Matrix3 = tuple[tuple[float, float, float], ...]
IDENTITY: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _vector(value: Sequence[float]) -> Vector3:
    if not isinstance(value, Sequence) or len(value) != 3:
        raise ValueError("expected three finite SI coordinates")
    return tuple(finite_number(item) for item in value)


def _matrix(value: Sequence[Sequence[float]]) -> Matrix3:
    if not isinstance(value, Sequence) or len(value) != 3:
        raise ValueError("expected finite 3x3 matrix")
    return tuple(_vector(row) for row in value)


def _determinant(matrix: Matrix3) -> float:
    a, b, c = matrix
    return finite_number(
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def _positive_semidefinite(matrix: Matrix3) -> bool:
    scale = max(abs(value) for row in matrix for value in row)
    if scale == 0:
        return True
    # Principal-minor tolerances square away large eigenvalue defects near
    # rank deficiency. A bounded symmetric Jacobi solve tests eigenvalues
    # directly, normalized so microscopic SI tensors receive the same check.
    scaled = [
        [(matrix[i][j] / scale + matrix[j][i] / scale) / 2 for j in range(3)] for i in range(3)
    ]
    for _ in range(24):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda pair: abs(scaled[pair[0]][pair[1]]))
        off = scaled[p][q]
        if abs(off) <= 1e-15:
            break
        tau = (scaled[q][q] - scaled[p][p]) / (2 * off)
        tangent = math.copysign(1.0, tau) / (abs(tau) + math.hypot(1.0, tau))
        cosine = 1 / math.hypot(1.0, tangent)
        sine = tangent * cosine
        scaled[p][p] -= tangent * off
        scaled[q][q] += tangent * off
        scaled[p][q] = scaled[q][p] = 0.0
        for r in range(3):
            if r not in (p, q):
                old_p, old_q = scaled[r][p], scaled[r][q]
                scaled[r][p] = scaled[p][r] = cosine * old_p - sine * old_q
                scaled[r][q] = scaled[q][r] = sine * old_p + cosine * old_q
    if max(abs(scaled[i][j]) for i, j in ((0, 1), (0, 2), (1, 2))) > 1e-15:
        return False
    return (
        min(
            scaled[i][i] - math.fsum(abs(scaled[i][j]) for j in range(3) if j != i)
            for i in range(3)
        )
        >= -1e-12
    )


def validate_centroidal_inertia(value: Sequence[Sequence[float]]) -> Matrix3:
    """Validate symmetry, nonnegative principal moments and inertia inequalities."""
    matrix = _matrix(value)
    scale = max(abs(item) for row in matrix for item in row)
    tolerance = scale * 1e-12
    if any(abs(matrix[i][j] - matrix[j][i]) > tolerance for i in range(3) for j in range(3)):
        raise ValueError("inertia tensor must be symmetric")
    if not _positive_semidefinite(matrix):
        raise ValueError("inertia tensor must be positive semidefinite")
    normalized = tuple(tuple(item / scale if scale else 0.0 for item in row) for row in matrix)
    half_trace = math.fsum(normalized[i][i] / 2 for i in range(3))
    covariance = tuple(
        tuple((half_trace if i == j else 0) - normalized[i][j] for j in range(3)) for i in range(3)
    )
    if not _positive_semidefinite(covariance):
        raise ValueError("inertia principal moments violate triangle inequalities")
    return matrix


def validate_rotation(value: Sequence[Sequence[float]]) -> Matrix3:
    rotation = _matrix(value)
    if any(
        not math.isclose(
            math.fsum(rotation[i][k] * rotation[j][k] for k in range(3)),
            float(i == j),
            rel_tol=0,
            abs_tol=1e-10,
        )
        for i in range(3)
        for j in range(3)
    ) or not math.isclose(_determinant(rotation), 1.0, rel_tol=0, abs_tol=1e-10):
        raise ValueError("rotation must be proper orthonormal (determinant +1)")
    return rotation


@dataclass(frozen=True)
class MassProperties:
    """A mass, COM and optional centroidal tensor in one named frame.

    ``None`` means unknown, including nonuniform printed or purchased internal
    properties. An aggregate containing an unknown tensor remains unknown.
    """

    mass_kg: float
    com_m: Vector3
    centroidal_inertia_kg_m2: Matrix3 | None
    frame: str
    evidence: str

    def __post_init__(self) -> None:
        mass = finite_number(self.mass_kg)
        if mass <= 0:
            raise ValueError("mass properties require positive mass")
        if not isinstance(self.frame, str) or not self.frame.strip():
            raise ValueError("mass properties require an explicit frame")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("mass properties require evidence")
        object.__setattr__(self, "mass_kg", mass)
        object.__setattr__(self, "com_m", _vector(self.com_m))
        if self.centroidal_inertia_kg_m2 is not None:
            object.__setattr__(
                self,
                "centroidal_inertia_kg_m2",
                validate_centroidal_inertia(self.centroidal_inertia_kg_m2),
            )


def uniform_box(
    mass_kg: float, size_m: Sequence[float], *, frame: str, evidence: str
) -> MassProperties:
    """Centred, axis-aligned uniform solid box, not a nonuniform printed part."""
    mass, size = finite_number(mass_kg), _vector(size_m)
    if mass <= 0 or any(length <= 0 for length in size):
        raise ValueError("uniform box requires positive mass and dimensions")
    diagonal = tuple(
        mass * math.fsum(size[j] ** 2 for j in range(3) if j != i) / 12 for i in range(3)
    )
    tensor = tuple(tuple(diagonal[i] if i == j else 0.0 for j in range(3)) for i in range(3))
    return MassProperties(mass, (0.0, 0.0, 0.0), tensor, frame, evidence)


def uniform_cylinder(
    mass_kg: float, radius_m: float, length_m: float, *, frame: str, evidence: str
) -> MassProperties:
    """Centred uniform solid cylinder with its longitudinal axis along +Z."""
    mass, radius, length = map(finite_number, (mass_kg, radius_m, length_m))
    if mass <= 0 or radius <= 0 or length <= 0:
        raise ValueError("uniform cylinder requires positive mass, radius and length")
    transverse = mass * (3 * radius**2 + length**2) / 12
    axial = mass * radius**2 / 2
    return MassProperties(
        mass,
        (0.0, 0.0, 0.0),
        ((transverse, 0.0, 0.0), (0.0, transverse, 0.0), (0.0, 0.0, axial)),
        frame,
        evidence,
    )


def transform_mass_properties(
    properties: MassProperties,
    rotation_to_target: Sequence[Sequence[float]],
    translation_to_target_m: Sequence[float],
    *,
    target_frame: str,
    transform_evidence: str,
) -> MassProperties:
    """Apply p_target = R_target_source*p_source + t_target_source.

    Rotating a centroidal tensor requires no parallel-axis shift. Translation
    changes the COM coordinates only; aggregation handles displaced COMs.
    """
    if not isinstance(properties, MassProperties):
        raise ValueError("expected MassProperties")
    rotation = validate_rotation(rotation_to_target)
    translation = _vector(translation_to_target_m)
    if not isinstance(transform_evidence, str) or not transform_evidence.strip():
        raise ValueError("transform requires evidence")
    com = tuple(
        math.fsum(rotation[i][j] * properties.com_m[j] for j in range(3)) + translation[i]
        for i in range(3)
    )
    tensor = properties.centroidal_inertia_kg_m2
    if tensor is not None:
        tensor = tuple(
            tuple(
                math.fsum(
                    rotation[i][a] * tensor[a][b] * rotation[j][b]
                    for a in range(3)
                    for b in range(3)
                )
                for j in range(3)
            )
            for i in range(3)
        )
    return MassProperties(
        properties.mass_kg,
        com,
        tensor,
        target_frame,
        properties.evidence + "; transform: " + transform_evidence,
    )


def aggregate_mass_properties(
    components: Sequence[MassProperties], *, evidence: str
) -> MassProperties:
    """Conserve mass/COM and aggregate tensors using parallel-axis terms.

    Unknown constituent tensors propagate to an unknown aggregate tensor;
    point-mass approximations must be supplied explicitly, never by omission.
    """
    if not isinstance(components, Sequence) or not components:
        raise ValueError("at least one mass component is required")
    if any(not isinstance(item, MassProperties) for item in components):
        raise ValueError("all components must be MassProperties")
    frames = {item.frame for item in components}
    if len(frames) != 1:
        raise ValueError("all components must use the same frame")
    mass = finite_number(math.fsum(item.mass_kg for item in components))
    com = tuple(
        math.fsum(item.mass_kg * item.com_m[i] for item in components) / mass for i in range(3)
    )
    tensor = None
    if all(item.centroidal_inertia_kg_m2 is not None for item in components):
        terms = []
        for item in components:
            displacement = tuple(item.com_m[i] - com[i] for i in range(3))
            distance_squared = math.fsum(value**2 for value in displacement)
            terms.append(
                tuple(
                    tuple(
                        item.centroidal_inertia_kg_m2[i][j]
                        + item.mass_kg
                        * (
                            (distance_squared if i == j else 0.0)
                            - displacement[i] * displacement[j]
                        )
                        for j in range(3)
                    )
                    for i in range(3)
                )
            )
        tensor = tuple(
            tuple(math.fsum(term[i][j] for term in terms) for j in range(3)) for i in range(3)
        )
    return MassProperties(mass, com, tensor, frames.pop(), evidence)
