"""Conditional swept AABBs under explicitly declared linear translation only.

This does not interpolate robot joints, rotate boxes, authenticate source-body
bindings, qualify enclosure or establish physical collision-free motion.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .thor_collision import AABB, BoxProxy
from .thor_frames import finite

LINEAR_TRANSLATION_ASSUMPTION = "fixed_orientation_axis_aligned_box_linear_center_translation"


def _axis_aligned(proxy: BoxProxy) -> None:
    if not isinstance(proxy, BoxProxy):
        raise ValueError("sweeps require validated BoxProxy inputs")
    # No approximation/projection of near-axis rotations is performed.
    rotation = tuple(row[:3] for row in proxy.frame_from_box[:3])
    if any(value not in (-1.0, 0.0, 1.0) for row in rotation for value in row):
        raise ValueError("only exact axis-aligned box orientations are supported")


def _validate_motion(start, end, assumption, motion_evidence, numerical_tolerance_m):
    if assumption != LINEAR_TRANSLATION_ASSUMPTION:
        raise ValueError("explicit fixed-orientation linear-translation assumption is required")
    if (
        not isinstance(motion_evidence, str)
        or not motion_evidence.strip()
        or len(motion_evidence) > 2048
    ):
        raise ValueError("motion requires bounded nonempty declaration evidence")
    _axis_aligned(start)
    _axis_aligned(end)
    if start.proxy_id != end.proxy_id or start.frame_id != end.frame_id:
        raise ValueError("moving identity and expression frame must be unchanged")
    if start.half_extents_m != end.half_extents_m or tuple(
        row[:3] for row in start.frame_from_box[:3]
    ) != tuple(row[:3] for row in end.frame_from_box[:3]):
        raise ValueError("resizing and rotating boxes are unsupported")
    tolerance = finite(numerical_tolerance_m)
    if tolerance < 0:
        raise ValueError("numerical padding must be nonnegative")
    _checked_bounds(start)
    _checked_bounds(end)
    return tolerance


def _axis_interval(start: float, end: float, low: float, high: float) -> tuple[float, float] | None:
    """Clip one linear coordinate to one closed slab without infinite quotients."""
    displacement = finite(end - start)
    if displacement == 0:
        return (0.0, 1.0) if low <= start <= high else None
    if displacement < 0:
        start, end, low, high, displacement = -start, -end, -high, -low, -displacement
    if start > high or end < low:
        return None
    # Divisions only occur when the corresponding crossing lies on this segment,
    # bounding both quotients to [0,1] without representing +/-infinity in JSON.
    entry = 0.0 if start >= low else finite(low - start) / displacement
    leave = 1.0 if end <= high else finite(high - start) / displacement
    if (start < low < end and not 0 < entry < 1) or (start < high < end and not 0 < leave < 1):
        raise ValueError("slab crossing parameter cannot be resolved in floating point")
    return finite(entry), finite(leave)


def _world_half_widths(proxy: BoxProxy) -> tuple[float, ...]:
    # Axis-aligned proper signed permutations select exactly one source half
    # extent per world axis; do not infer size by subtracting rounded corners.
    return tuple(
        proxy.half_extents_m[next(j for j in range(3) if abs(proxy.frame_from_box[i][j]) == 1)]
        for i in range(3)
    )


def _checked_bounds(proxy: BoxProxy) -> AABB:
    bounds = proxy.aabb()
    if any(
        half > 0 and bounds.minimum_m[i] == bounds.maximum_m[i]
        for i, half in enumerate(_world_half_widths(proxy))
    ):
        raise ValueError("positive box width cannot be resolved at its centre coordinates")
    return bounds


@dataclass(frozen=True)
class SweptProxyIntersection:
    moving_id: str
    obstacle_id: str
    frame_id: str
    relation: str
    overlap_parameter_interval: tuple[float, float] | None
    axis_parameter_intervals: tuple[tuple[float, float] | None, ...]
    assumption: str
    motion_evidence: str
    numerical_padding_m: float
    physical_collision_free: None = None
    robot_path_clearance: None = None


def sweep_linear_translation(
    start: BoxProxy,
    end: BoxProxy,
    obstacle: BoxProxy,
    *,
    assumption: str,
    motion_evidence: str,
    numerical_tolerance_m: float = 0.0,
) -> SweptProxyIntersection:
    """Return inclusive overlap/contact parameter intervals for a declared sweep.

    Centre(u)=(1-u)*start+u*end for u in [0,1], fixed axis-aligned orientation
    and extents. Static obstacle slabs are Minkowski-expanded by the moving box
    half width and optional numerical padding. The three closed slab intervals
    are intersected analytically, without endpoint-only or sampled acceptance.
    This is floating-point evaluation of that model, not certified interval
    arithmetic. Padding is a declared numerical dilation, not a physical margin.
    """
    tolerance = _validate_motion(start, end, assumption, motion_evidence, numerical_tolerance_m)
    _axis_aligned(obstacle)
    if start.frame_id != obstacle.frame_id:
        raise ValueError("moving and obstacle expression frames differ")
    if start.proxy_id == obstacle.proxy_id:
        raise ValueError("moving and static obstacle identities must be distinct")
    # Existing AABB/BoxProxy geometry services own orientation and corner handling.
    static = _checked_bounds(obstacle)
    widths = _world_half_widths(start)
    intervals = []
    for axis in range(3):
        low = finite(static.minimum_m[axis] - widths[axis] - tolerance)
        high = finite(static.maximum_m[axis] + widths[axis] + tolerance)
        intervals.append(_axis_interval(start.center_m[axis], end.center_m[axis], low, high))
    overlap = None
    if all(interval is not None for interval in intervals):
        entry = max(interval[0] for interval in intervals)
        leave = min(interval[1] for interval in intervals)
        if entry <= leave:
            overlap = (entry, leave)
    return SweptProxyIntersection(
        start.proxy_id,
        obstacle.proxy_id,
        start.frame_id,
        "no_proxy_overlap_on_declared_linear_sweep"
        if overlap is None
        else "proxy_overlap_or_contact_during_declared_linear_sweep",
        overlap,
        tuple(intervals),
        assumption,
        motion_evidence,
        tolerance,
    )


def sweep_against_static_boxes(
    start: BoxProxy,
    end: BoxProxy,
    obstacles: Sequence[BoxProxy],
    *,
    assumption: str,
    motion_evidence: str,
    numerical_tolerance_m: float = 0.0,
    max_obstacles: int = 1000,
) -> tuple[SweptProxyIntersection, ...]:
    """Bounded per-obstacle results, with no automatic exclusions or robot claim."""
    _validate_motion(start, end, assumption, motion_evidence, numerical_tolerance_m)
    if type(max_obstacles) is not int or not 0 <= max_obstacles <= 10000:
        raise ValueError("obstacle budget must be an integer from zero to 10000")
    if (
        not isinstance(obstacles, Sequence)
        or len(obstacles) > max_obstacles
        or any(not isinstance(obstacle, BoxProxy) for obstacle in obstacles)
    ):
        raise ValueError("static obstacle sequence exceeds budget or contains invalid boxes")
    if len({box.proxy_id for box in obstacles}) != len(obstacles):
        raise ValueError("static obstacle IDs must be unique")
    return tuple(
        sweep_linear_translation(
            start,
            end,
            obstacle,
            assumption=assumption,
            motion_evidence=motion_evidence,
            numerical_tolerance_m=numerical_tolerance_m,
        )
        for obstacle in obstacles
    )
