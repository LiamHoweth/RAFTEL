"""Bounded offline rest-to-rest joint quintics with explicit study rate limits.

These trajectories describe nominal joint coordinates only. They do not check
IK branches, intersample collision, coupled shafts, cable routing, dynamics or
physical safety and are never connected to a controller or the logical sorter.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass, field

from .thor_constraints import ConstraintSet, validate_joint_state
from .thor_frames import finite
from .thor_model import _angles

PEAK_QUINTIC_VELOCITY = 15 / 8
PEAK_QUINTIC_ACCELERATION = 10 * math.sqrt(3) / 3


@dataclass(frozen=True)
class TimedJointState:
    time_s: float
    joints_rad: tuple[float, ...]
    velocities_rad_s: tuple[float, ...]
    accelerations_rad_s2: tuple[float, ...]

    def __post_init__(self) -> None:
        value = finite(self.time_s)
        if value < 0:
            raise ValueError("sample time cannot be negative")
        object.__setattr__(self, "time_s", value)
        for attribute in ("joints_rad", "velocities_rad_s", "accelerations_rad_s2"):
            object.__setattr__(self, attribute, _angles(getattr(self, attribute)))


@dataclass(frozen=True)
class QuinticSegment:
    """One mathematical rest-to-rest segment; use plan_quintic_path for checks."""

    start_rad: tuple[float, ...]
    end_rad: tuple[float, ...]
    duration_s: float

    def __post_init__(self) -> None:
        start, end = _angles(self.start_rad), _angles(self.end_rad)
        duration = finite(self.duration_s)
        if duration <= 0:
            raise ValueError("segment duration must be positive")
        object.__setattr__(self, "start_rad", start)
        object.__setattr__(self, "end_rad", end)
        object.__setattr__(self, "duration_s", duration)
        # Check derivative scaling once, including constant/stationary segments.
        self.peak_rates()

    def peak_rates(self) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Exact per-axis absolute speed/acceleration maxima, not sample maxima."""
        displacement = tuple(
            finite(abs(b - a)) for a, b in zip(self.start_rad, self.end_rad, strict=True)
        )
        velocity = tuple(
            finite(PEAK_QUINTIC_VELOCITY * (value / self.duration_s)) for value in displacement
        )
        acceleration = tuple(
            finite(PEAK_QUINTIC_ACCELERATION * ((value / self.duration_s) / self.duration_s))
            for value in displacement
        )
        return velocity, acceleration

    def sample(self, time_s: float) -> TimedJointState:
        t = finite(time_s)
        if not 0 <= t <= self.duration_s:
            raise ValueError("sample time must be inside the segment")
        if t == 0 or t == self.duration_s:
            return TimedJointState(
                t, self.start_rad if t == 0 else self.end_rad, (0.0,) * 6, (0.0,) * 6
            )
        u = t / self.duration_s
        if u <= 0.5:
            s = u**3 * (10 + u * (-15 + 6 * u))
        else:
            remaining = 1 - u
            s = 1 - remaining**3 * (10 + remaining * (-15 + 6 * remaining))
        ds = 30 * u * u * (1 - u) * (1 - u)
        dds = 60 * u * (1 - u) * (1 - 2 * u)
        delta = tuple(b - a for a, b in zip(self.start_rad, self.end_rad, strict=True))
        return TimedJointState(
            t,
            tuple(
                min(max(a, b), max(min(a, b), a + d * s))
                for a, b, d in zip(self.start_rad, self.end_rad, delta, strict=True)
            ),
            tuple((d / self.duration_s) * ds for d in delta),
            tuple(((d / self.duration_s) / self.duration_s) * dds for d in delta),
        )


@dataclass(frozen=True)
class TimedJointPath:
    segments: tuple[QuinticSegment, ...]
    constraint_revision: str
    study_rate_evidence: tuple[str, ...]
    validation_class: str = (
        "offline_scalar_joint_path_not_collision_dynamics_or_hardware_validation"
    )
    _end_times_s: tuple[float, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.segments, Sequence)
            or not 1 <= len(self.segments) <= 999
            or any(not isinstance(segment, QuinticSegment) for segment in self.segments)
        ):
            raise ValueError("a path needs 1..999 QuinticSegment values")
        segments = tuple(self.segments)
        if any(a.end_rad != b.start_rad for a, b in zip(segments, segments[1:], strict=False)):
            raise ValueError("consecutive segments must share an exact waypoint")
        if not isinstance(self.constraint_revision, str) or not self.constraint_revision.strip():
            raise ValueError("path needs a constraint revision")
        if (
            not isinstance(self.study_rate_evidence, Sequence)
            or isinstance(self.study_rate_evidence, str)
            or len(self.study_rate_evidence) != 6
            or any(
                not isinstance(value, str) or not value.strip()
                for value in self.study_rate_evidence
            )
        ):
            raise ValueError("path needs six study rate evidence records")
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "study_rate_evidence", tuple(self.study_rate_evidence))
        ends = tuple(
            finite(math.fsum(segment.duration_s for segment in segments[:i]))
            for i in range(1, len(segments) + 1)
        )
        if any(a >= b for a, b in zip(ends, ends[1:], strict=False)):
            raise ValueError("segment durations cannot be resolved on the path timeline")
        object.__setattr__(self, "_end_times_s", ends)

    @property
    def duration_s(self) -> float:
        return self._end_times_s[-1]

    def sample(self, time_s: float) -> TimedJointState:
        t = finite(time_s)
        if not 0 <= t <= self.duration_s:
            raise ValueError("sample time must be inside the path")
        if t == self.duration_s:
            local = self.segments[-1].sample(self.segments[-1].duration_s)
        else:
            index = bisect_left(self._end_times_s, t)
            segment = self.segments[index]
            elapsed = self._end_times_s[index - 1] if index else 0.0
            local = segment.sample(
                segment.duration_s
                if t == self._end_times_s[index]
                else min(segment.duration_s, max(0.0, t - elapsed))
            )
        return TimedJointState(
            t, local.joints_rad, local.velocities_rad_s, local.accelerations_rad_s2
        )

    def sample_uniform(
        self, period_s: float, *, max_samples: int = 10000
    ) -> tuple[TimedJointState, ...]:
        """Sample requested spacing plus the exact endpoint, with a size budget."""
        period = finite(period_s)
        if period <= 0 or type(max_samples) is not int or not 2 <= max_samples <= 100000:
            raise ValueError("sampling needs positive period and 2..100000 max_samples")
        quotient = self.duration_s / period
        if not math.isfinite(quotient) or quotient > max_samples - 1:
            raise ValueError("uniform sample budget exceeded")
        intervals = max(1, math.ceil(quotient))
        return tuple(
            self.sample(t) for index in range(intervals) if (t := index * period) < self.duration_s
        ) + (self.sample(self.duration_s),)


def plan_quintic_path(
    waypoints_rad: Sequence[Sequence[float]],
    constraints: ConstraintSet,
    *,
    segment_durations_s: Sequence[float] | None = None,
    min_segment_duration_s: float = 0.01,
    max_total_duration_s: float = 300,
) -> TimedJointPath:
    """Plan scalar-coordinate C2 rest-to-rest segments under an explicit study.

    Every study bound must contain a positive velocity and acceleration limit
    with evidence. Unknown source acceleration is never filled automatically.
    Requested durations are checked against exact analytic derivative maxima;
    omitted durations are conservatively computed from those same maxima.
    """
    if not isinstance(waypoints_rad, Sequence) or not 2 <= len(waypoints_rad) <= 1000:
        raise ValueError("provide 2..1000 six-joint waypoints")
    if not isinstance(constraints, ConstraintSet):
        raise ValueError("constraints must be a ConstraintSet")
    waypoints = tuple(_angles(waypoint) for waypoint in waypoints_rad)
    bounds = constraints.bounds("study")
    for joint, bound in zip(constraints.joints, bounds, strict=True):
        if bound.max_velocity_rad_s is None or bound.max_acceleration_rad_s2 is None:
            raise ValueError(
                f"{joint.name}: explicit study velocity and acceleration limits required"
            )
    for index, waypoint in enumerate(waypoints):
        violations = validate_joint_state(waypoint, constraints)
        if violations:
            raise ValueError(
                f"waypoint {index} violates study position limits: {'; '.join(violations)}"
            )
    minimum, maximum = finite(min_segment_duration_s), finite(max_total_duration_s)
    if minimum <= 0 or maximum <= 0 or minimum > maximum:
        raise ValueError("duration bounds must be positive and ordered")
    if segment_durations_s is not None:
        if (
            not isinstance(segment_durations_s, Sequence)
            or len(segment_durations_s) != len(waypoints) - 1
        ):
            raise ValueError("one requested duration per segment is required")
        requested = tuple(finite(value) for value in segment_durations_s)
    else:
        requested = None
    segments = []
    for index, (start, end) in enumerate(zip(waypoints, waypoints[1:], strict=False)):
        duration = minimum
        for a, b, bound in zip(start, end, bounds, strict=True):
            displacement = finite(abs(b - a))
            duration = max(
                duration,
                finite(PEAK_QUINTIC_VELOCITY * displacement / bound.max_velocity_rad_s),
                finite(
                    math.sqrt(
                        PEAK_QUINTIC_ACCELERATION * displacement / bound.max_acceleration_rad_s2
                    )
                ),
            )
        if requested is None:
            # Round away from the derivative boundary so libm roundoff cannot
            # turn a computed exact-rate solution into an accidental violation.
            duration = math.nextafter(duration, math.inf)
        else:
            if requested[index] < minimum:
                raise ValueError(f"segment {index}: requested duration is below minimum")
            duration = requested[index]
        segment = QuinticSegment(start, end, duration)
        velocities, accelerations = segment.peak_rates()
        if any(
            v > bound.max_velocity_rad_s * (1 + 1e-12)
            or a > bound.max_acceleration_rad_s2 * (1 + 1e-12)
            for v, a, bound in zip(velocities, accelerations, bounds, strict=True)
        ):
            raise ValueError(
                f"segment {index}: analytic velocity or acceleration exceeds study limit"
            )
        segments.append(segment)
        if math.fsum(item.duration_s for item in segments) > maximum:
            raise ValueError("path exceeds the total duration budget")
    return TimedJointPath(
        tuple(segments), constraints.revision, tuple(bound.evidence for bound in bounds)
    )
