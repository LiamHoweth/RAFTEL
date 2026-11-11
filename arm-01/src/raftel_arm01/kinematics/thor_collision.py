"""Declared box-proxy intersections, never physical collision clearance.

All dimensions are metres. Boxes require one explicit expression frame. Source
geometry enclosure, installed-body ownership and swept paths are separate input
evidence, and are not inferred from this mathematical separating-axis test.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

from .thor_frames import IDENTITY, Matrix, compose, finite, rigid_transform, transform_point

Vector3 = tuple[float, float, float]


def _vector(value: Sequence[float]) -> Vector3:
    if not isinstance(value, Sequence) or len(value) != 3:
        raise ValueError("expected three finite coordinates")
    return tuple(finite(component) for component in value)


def _text(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ValueError("proxy identifiers and evidence require bounded nonempty text")
    return value


def _dot(a: Vector3, b: Vector3) -> float:
    try:
        return finite(math.fsum(x * y for x, y in zip(a, b, strict=True)))
    except OverflowError as error:
        raise ValueError("proxy projection overflowed") from error


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return _vector(
        (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    )


def _projection_radius(box: BoxProxy, axis: Vector3) -> float:
    try:
        return finite(
            math.fsum(
                h * abs(_dot(axis, direction))
                for h, direction in zip(box.half_extents_m, box.axes, strict=True)
            )
        )
    except OverflowError as error:
        raise ValueError("proxy radius overflowed") from error


@dataclass(frozen=True)
class AABB:
    """An axis-aligned declared box; zero-width geometric boxes are permitted."""

    minimum_m: Vector3
    maximum_m: Vector3

    def __post_init__(self) -> None:
        low, high = _vector(self.minimum_m), _vector(self.maximum_m)
        if any(a > b for a, b in zip(low, high, strict=True)):
            raise ValueError("AABB minimum exceeds maximum")
        object.__setattr__(self, "minimum_m", low)
        object.__setattr__(self, "maximum_m", high)

    def proxy(
        self, proxy_id: str, frame_id: str, evidence: str, *, enclosure_status="unknown"
    ) -> BoxProxy:
        half = _vector(
            tuple((b - a) / 2 for a, b in zip(self.minimum_m, self.maximum_m, strict=True))
        )
        center = _vector(tuple(a + h for a, h in zip(self.minimum_m, half, strict=True)))
        transform = tuple((*IDENTITY[i][:3], center[i]) for i in range(3)) + (IDENTITY[3],)
        return BoxProxy(proxy_id, frame_id, half, transform, evidence, enclosure_status)


@dataclass(frozen=True)
class BoxProxy:
    """An oriented study box centred at its own frame origin.

    ``frame_from_box`` is a proper SE(3) transform in metres. Enclosure status is
    intentionally limited to unknown source enclosure or exact synthetic box
    geometry. Neither value certifies a physical body or complete scene.
    """

    proxy_id: str
    frame_id: str
    half_extents_m: Vector3
    frame_from_box: Matrix
    evidence: str
    enclosure_status: str = "unknown"

    def __post_init__(self) -> None:
        _text(self.proxy_id)
        _text(self.frame_id)
        _text(self.evidence)
        half = _vector(self.half_extents_m)
        if any(value < 0 for value in half):
            raise ValueError("box half extents must be nonnegative")
        if not isinstance(self.enclosure_status, str) or self.enclosure_status not in {
            "unknown",
            "synthetic_exact_box",
        }:
            raise ValueError("unsupported geometry enclosure assertion")
        object.__setattr__(self, "half_extents_m", half)
        object.__setattr__(self, "frame_from_box", rigid_transform(self.frame_from_box))

    @property
    def center_m(self) -> Vector3:
        return tuple(row[3] for row in self.frame_from_box[:3])

    @property
    def axes(self) -> tuple[Vector3, ...]:
        return tuple(tuple(self.frame_from_box[i][j] for i in range(3)) for j in range(3))

    def corners_m(self) -> tuple[Vector3, ...]:
        return tuple(
            transform_point(
                self.frame_from_box, tuple(sign[i] * self.half_extents_m[i] for i in range(3))
            )
            for sign in itertools.product((-1, 1), repeat=3)
        )

    def aabb(self) -> AABB:
        corners = self.corners_m()
        return AABB(
            tuple(min(p[i] for p in corners) for i in range(3)),
            tuple(max(p[i] for p in corners) for i in range(3)),
        )


def transform_proxy(proxy: BoxProxy, target_from_frame: Matrix, target_frame_id: str) -> BoxProxy:
    """Apply only a caller-declared known transform; unknown frames are not identity."""
    if not isinstance(proxy, BoxProxy):
        raise ValueError("expected BoxProxy")
    return BoxProxy(
        proxy.proxy_id,
        target_frame_id,
        proxy.half_extents_m,
        compose(target_from_frame, proxy.frame_from_box),
        proxy.evidence,
        proxy.enclosure_status,
    )


@dataclass(frozen=True)
class ProxyIntersection:
    left_id: str
    right_id: str
    relation: str
    contact_classification: str
    maximum_axis_gap_m: float
    witness_axis_unit: Vector3
    axes_tested: int
    numerical_tolerance_m: float
    physical_clearance_established: bool = False


def intersect_boxes(
    left: BoxProxy, right: BoxProxy, *, numerical_tolerance_m=1e-12
) -> ProxyIntersection:
    """OBB separating-axis test on 3+3 face axes and 9 edge cross products.

    An axis gap is |axis dot centre_delta| minus both projected half widths.
    Positive gaps separate boxes; contact and gaps within the declared numerical
    tolerance remain overlap/contact candidates. The maximum projection gap is
    a witness diagnostic, not an exact Euclidean clearance or penetration depth.
    This is floating-point arithmetic, not a certified interval computation.
    """
    if not isinstance(left, BoxProxy) or not isinstance(right, BoxProxy):
        raise ValueError("intersection requires BoxProxy values")
    if left.frame_id != right.frame_id:
        raise ValueError("box expression frames differ; supply a known transform first")
    tolerance = finite(numerical_tolerance_m)
    if tolerance < 0:
        raise ValueError("numerical tolerance must be nonnegative")
    delta = _vector(tuple(b - a for a, b in zip(left.center_m, right.center_m, strict=True)))
    axes = (*left.axes, *right.axes, *(_cross(a, b) for a in left.axes for b in right.axes))
    gaps = []
    for raw_axis in axes:
        norm = finite(math.hypot(*raw_axis))
        if norm == 0:
            continue  # Exactly parallel edge pairs add no separating direction.
        axis = _vector(tuple(value / norm for value in raw_axis))
        left_radius = _projection_radius(left, axis)
        right_radius = _projection_radius(right, axis)
        gap = finite(abs(_dot(axis, delta)) - left_radius - right_radius)
        gaps.append((gap, axis))
    maximum_gap, witness = max(gaps, key=lambda row: row[0])
    separated = maximum_gap > tolerance
    classification = (
        "separated"
        if separated
        else "within_numerical_tolerance"
        if maximum_gap >= -tolerance
        else "interior_overlap"
    )
    return ProxyIntersection(
        left.proxy_id,
        right.proxy_id,
        "no_proxy_overlap" if separated else "proxy_overlap_or_contact",
        classification,
        maximum_gap,
        witness,
        len(gaps),
        tolerance,
    )


@dataclass(frozen=True)
class PairExclusion:
    """An exact pair policy declaration; its geometry result remains visible."""

    left_id: str
    right_id: str
    reason: str
    evidence: str

    def __post_init__(self) -> None:
        for value in (self.left_id, self.right_id, self.reason, self.evidence):
            _text(value)
        if self.left_id == self.right_id:
            raise ValueError("an exclusion requires two distinct proxy identities")

    @property
    def key(self) -> tuple[str, str]:
        return tuple(sorted((self.left_id, self.right_id)))


def screen_proxies(
    proxies: Sequence[BoxProxy],
    exclusions: Sequence[PairExclusion] = (),
    *,
    numerical_tolerance_m=1e-12,
    max_pairs=10000,
) -> dict:
    """Evaluate all explicit pairs, including raw results of policy exclusions.

    There is no adjacency rule. Coverage of actual geometry, obstacles, held
    objects, wiring and intersample swept volumes remains unverified.
    """
    if not isinstance(proxies, Sequence) or any(not isinstance(p, BoxProxy) for p in proxies):
        raise ValueError("proxies must be a sequence of BoxProxy values")
    tolerance = finite(numerical_tolerance_m)
    if tolerance < 0:
        raise ValueError("numerical tolerance must be nonnegative")
    if type(max_pairs) is not int or not 0 <= max_pairs <= 1_000_000:
        raise ValueError("max_pairs must be an integer from zero to one million")
    pair_count = len(proxies) * (len(proxies) - 1) // 2
    if pair_count > max_pairs:
        raise ValueError("proxy pair budget exceeded")
    ids = {p.proxy_id for p in proxies}
    if len(ids) != len(proxies) or len({p.frame_id for p in proxies}) > 1:
        raise ValueError("proxy IDs must be unique and expression frame shared")
    if not isinstance(exclusions, Sequence) or any(
        not isinstance(e, PairExclusion) for e in exclusions
    ):
        raise ValueError("exclusions must be PairExclusion declarations")
    by_pair = {exclusion.key: exclusion for exclusion in exclusions}
    if len(by_pair) != len(exclusions) or any(not set(key) <= ids for key in by_pair):
        raise ValueError("exclusions must be unique exact pairs of present proxy IDs")
    from dataclasses import asdict

    rows = []
    for left, right in itertools.combinations(proxies, 2):
        result = intersect_boxes(left, right, numerical_tolerance_m=tolerance)
        excluded = by_pair.get(tuple(sorted((left.proxy_id, right.proxy_id))))
        rows.append(
            {
                "intersection": asdict(result),
                "policy_exclusion": None if excluded is None else asdict(excluded),
                "screening_policy": "evaluate"
                if excluded is None
                else "excluded_raw_intersection_retained",
            }
        )
    return {
        "evidence_class": "declared_box_proxy_mathematics_not_physical_collision_screening",
        "proxy_count": len(proxies),
        "pair_count": pair_count,
        "explicit_exclusion_count": len(exclusions),
        "automatic_adjacency_exclusions": False,
        "pairs": rows,
        "source_geometry_enclosure_verified": False,
        "complete_robot_obstacle_or_swept_coverage": False,
        "physical_collision_free": None,
    }
