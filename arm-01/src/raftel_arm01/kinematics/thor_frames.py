"""Revisioned, evidence-bearing frame transforms for offline Thor analysis.

``parent_from_child`` maps child coordinates into the parent, in metres. Unknown
mount, camera and TCP transforms remain unknown; this is not a calibration API
or permission to operate hardware. Covariances use [translation, rotation]
small left-perturbations and are propagated assuming independent inputs.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Real
from pathlib import Path

from .thor_model import SOURCE_PATH, SOURCE_REVISION, forward_kinematics

Matrix = tuple[tuple[float, ...], ...]
NOMINAL_SOURCE_SHA256 = "19b83e26f86aae15fda5c21418f768d0e3ed1b0d1daa6d149abd9b45ceccd8b9"
EVIDENCE_CLASSES = frozenset({"source", "assumed", "synthetic", "physical", "unknown"})
IDENTITY = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)


def finite(value: float) -> float:
    """Accept finite real scalars, rejecting booleans and numeric strings."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("expected a finite real number")
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("expected a finite real number") from error
    if not math.isfinite(result):
        raise ValueError("expected a finite real number")
    return result


def matrix(value: Sequence[Sequence[float]], rows: int, columns: int) -> Matrix:
    if not isinstance(value, Sequence) or len(value) != rows:
        raise ValueError(f"expected a {rows} by {columns} matrix")
    if any(not isinstance(row, Sequence) or len(row) != columns for row in value):
        raise ValueError(f"expected a {rows} by {columns} matrix")
    return tuple(tuple(finite(component) for component in row) for row in value)


def multiply(left: Matrix, right: Matrix) -> Matrix:
    try:
        return tuple(
            tuple(
                finite(math.fsum(a * b for a, b in zip(row, column, strict=True)))
                for column in zip(*right, strict=True)
            )
            for row in left
        )
    except OverflowError as error:
        raise ValueError("matrix calculation overflowed") from error


def transpose(value: Matrix) -> Matrix:
    return tuple(zip(*value, strict=True))


def rigid_transform(value: Sequence[Sequence[float]]) -> Matrix:
    """Validate a finite proper SE(3) matrix, without silently projecting it."""
    result = matrix(value, 4, 4)
    if any(abs(result[3][i] - IDENTITY[3][i]) > 1e-10 for i in range(4)):
        raise ValueError("transform must have homogeneous last row [0,0,0,1]")
    rotation = tuple(tuple(row[:3]) for row in result[:3])
    product = multiply(rotation, transpose(rotation))
    if any(abs(product[i][j] - float(i == j)) > 1e-9 for i in range(3) for j in range(3)):
        raise ValueError("transform rotation must be orthonormal")
    a, b, c = rotation
    determinant = (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )
    if abs(determinant - 1) > 1e-9:
        raise ValueError("transform rotation must have determinant +1")
    return result


def compose(parent_from_middle: Matrix, middle_from_child: Matrix) -> Matrix:
    return rigid_transform(
        multiply(rigid_transform(parent_from_middle), rigid_transform(middle_from_child))
    )


def inverse(parent_from_child: Matrix) -> Matrix:
    value = rigid_transform(parent_from_child)
    rotation = tuple(tuple(value[j][i] for j in range(3)) for i in range(3))
    return rigid_transform(
        tuple(
            (*rotation[i], -math.fsum(rotation[i][j] * value[j][3] for j in range(3)))
            for i in range(3)
        )
        + (IDENTITY[3],)
    )


def transform_point(parent_from_child: Matrix, point_m: Sequence[float]) -> tuple[float, ...]:
    value = rigid_transform(parent_from_child)
    if not isinstance(point_m, Sequence) or len(point_m) != 3:
        raise ValueError("point requires three coordinates in metres")
    point = tuple(finite(component) for component in point_m)
    result = tuple(
        math.fsum(value[i][j] * point[j] for j in range(3)) + value[i][3] for i in range(3)
    )
    return tuple(finite(component) for component in result)


def adjoint(parent_from_child: Matrix) -> Matrix:
    """SE(3) adjoint for [linear, angular] left perturbations, in SI units."""
    value = rigid_transform(parent_from_child)
    x, y, z = (row[3] for row in value[:3])
    skew = ((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0))
    rotation = tuple(tuple(row[:3]) for row in value[:3])
    cross_rotation = multiply(skew, rotation)
    return tuple((*rotation[i], *cross_rotation[i]) for i in range(3)) + tuple(
        (0.0, 0.0, 0.0, *rotation[i]) for i in range(3)
    )


def covariance(value: Sequence[Sequence[float]]) -> Matrix:
    """Validate a symmetric positive-semidefinite 6x6 SI covariance."""
    result = matrix(value, 6, 6)
    scale = max(max(abs(component) for component in row) for row in result)
    tolerance = 1e-12 * max(scale, 1e-30)
    if any(abs(result[i][j] - result[j][i]) > tolerance for i in range(6) for j in range(6)):
        raise ValueError("covariance must be symmetric")
    # Pivoted Schur complement handles PSD matrices with zero variance exactly.
    remaining = [list(row) for row in result]
    while remaining:
        pivot = max(range(len(remaining)), key=lambda i: remaining[i][i])
        remaining[0], remaining[pivot] = remaining[pivot], remaining[0]
        for row in remaining:
            row[0], row[pivot] = row[pivot], row[0]
        diagonal = remaining[0][0]
        if diagonal < -tolerance:
            raise ValueError("covariance must be positive semidefinite")
        if diagonal <= tolerance:
            if any(abs(component) > tolerance for row in remaining for component in row):
                raise ValueError("covariance must be positive semidefinite")
            break
        remaining = [
            [
                remaining[i][j] - remaining[i][0] * remaining[0][j] / diagonal
                for j in range(1, len(remaining))
            ]
            for i in range(1, len(remaining))
        ]
    return result


def transform_covariance(parent_from_child: Matrix, child_covariance: Matrix) -> Matrix:
    a = adjoint(parent_from_child)
    return covariance(multiply(multiply(a, covariance(child_covariance)), transpose(a)))


def compose_covariance(
    parent_from_middle: Matrix, parent_covariance: Matrix, middle_covariance: Matrix
) -> Matrix:
    carried = transform_covariance(parent_from_middle, middle_covariance)
    initial = covariance(parent_covariance)
    return covariance(
        tuple(tuple(initial[i][j] + carried[i][j] for j in range(6)) for i in range(6))
    )


@dataclass(frozen=True)
class FrameRecord:
    parent: str
    child: str
    parent_from_child: Matrix | None
    evidence_class: str
    evidence: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(name, str) or not name.strip()
            for name in (self.parent, self.child, self.evidence)
        ):
            raise ValueError("frame names and evidence must be nonempty strings")
        if self.parent == self.child:
            raise ValueError("a frame cannot parent itself")
        if not isinstance(self.evidence_class, str) or self.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError("unknown frame evidence class")
        if (self.parent_from_child is None) != (self.evidence_class == "unknown"):
            raise ValueError("unknown frame transform must be null; known transform needs evidence")
        if self.parent_from_child is not None:
            object.__setattr__(self, "parent_from_child", rigid_transform(self.parent_from_child))


class FrameGraph:
    """Acyclic static frame records. Resolving an unknown edge fails closed."""

    def __init__(self, records: Sequence[FrameRecord]):
        if not isinstance(records, Sequence) or any(
            not isinstance(record, FrameRecord) for record in records
        ):
            raise ValueError("records must be FrameRecord values")
        self.records = tuple(records)
        self._by_child = {record.child: record for record in self.records}
        if len(self._by_child) != len(self.records):
            raise ValueError("each child frame must have one parent")
        self.frames = frozenset(
            name for record in records for name in (record.parent, record.child)
        )
        for name in self.frames:
            visited = set()
            while name in self._by_child:
                if name in visited:
                    raise ValueError("frame graph contains a cycle")
                visited.add(name)
                name = self._by_child[name].parent

    def transform(self, target: str, source: str) -> Matrix:
        """Return target_from_source; no unknown extrinsic becomes identity."""
        if (
            not isinstance(target, str)
            or not isinstance(source, str)
            or target not in self.frames
            or source not in self.frames
        ):
            raise ValueError("requested frame is absent")
        if target == source:
            return IDENTITY
        adjacency: dict[str, list[tuple[str, Matrix | None]]] = {name: [] for name in self.frames}
        for record in self.records:
            adjacency[record.child].append((record.parent, record.parent_from_child))
            adjacency[record.parent].append(
                (
                    record.child,
                    None if record.parent_from_child is None else inverse(record.parent_from_child),
                )
            )
        pending = [(source, IDENTITY, False)]
        visited = set()
        while pending:
            current, current_from_source, unknown = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            if current == target:
                if unknown:
                    raise ValueError(
                        "requested transform depends on unknown calibration or extrinsic"
                    )
                return current_from_source
            for neighbor, neighbor_from_current in adjacency[current]:
                pending.append(
                    (
                        neighbor,
                        current_from_source
                        if neighbor_from_current is None
                        else compose(neighbor_from_current, current_from_source),
                        unknown or neighbor_from_current is None,
                    )
                )
        raise ValueError("requested frames are disconnected")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_nominal_source(reference: object) -> None:
    """Reject manifests bound to a source different from this implementation.

    This validates the declared pin only. ``audit_source_constraints`` checks
    separately supplied actual source bytes against the SHA256.
    """
    expected = {
        "repository": "https://github.com/AngelLM/Thor-ROS",
        "revision": SOURCE_REVISION,
        "path": SOURCE_PATH,
        "sha256": NOMINAL_SOURCE_SHA256,
    }
    if not isinstance(reference, Mapping) or dict(reference) != expected:
        raise ValueError("manifest source provenance does not match the pinned nominal model")


def load_frame_graph(path: str | Path) -> FrameGraph:
    data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if (
        not isinstance(data, Mapping)
        or type(data.get("schema_version")) is not int
        or data.get("schema_version") != 1
        or data.get("units") != "m_rad"
    ):
        raise ValueError("frame manifest requires schema_version 1 and m_rad units")
    if not isinstance(data.get("revision"), str) or not data["revision"].strip():
        raise ValueError("frame manifest requires an explicit revision")
    validate_nominal_source(data.get("source"))
    records = data.get("frames")
    if not isinstance(records, list):
        raise ValueError("frame manifest requires frame records")
    try:
        return FrameGraph(tuple(FrameRecord(**record) for record in records))
    except TypeError as error:
        raise ValueError("invalid frame record fields") from error


def with_nominal_pose(graph: FrameGraph, joints_rad: Sequence[float]) -> FrameGraph:
    """Attach the declared source FK at one pose without filling calibration.

    The static manifest deliberately omits base_link→link_6. This returns a
    separate graph for the supplied configuration, retaining every unknown
    bench/mount/camera/TCP edge and the original unmodified static graph.
    """
    if not isinstance(graph, FrameGraph):
        raise ValueError("graph must be a FrameGraph")
    return FrameGraph(
        (
            *graph.records,
            FrameRecord(
                "base_link",
                "link_6",
                forward_kinematics(joints_rad),
                "source",
                f"Nominal FK at supplied model angles; Thor-ROS {SOURCE_REVISION}; "
                "no physical articulation validation",
            ),
        )
    )
