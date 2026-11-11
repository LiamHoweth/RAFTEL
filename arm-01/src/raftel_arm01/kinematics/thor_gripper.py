"""Conditional nominal Thor parallelogram jaws, not a calibrated servo model.

The saved assembly is not a solved linkage. This evaluator deliberately uses
an explicit ideal symmetric geometry rather than silently repairing that CAD.
Coordinates are in the source GripperBot frame; metres and radians throughout.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real


def _finite(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("expected a finite real number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("expected a finite real number") from error
    if not math.isfinite(result):
        raise ValueError("expected a finite real number")
    return result


@dataclass(frozen=True)
class JawState:
    """Ideal jaw geometry, with derivatives with respect to common closing q."""

    closing_angle_rad: float
    gap_m: float
    gap_derivative_m_rad: float
    finger_translation_m: tuple[tuple[float, float], tuple[float, float]]
    finger_translation_derivative_m_rad: tuple[tuple[float, float], tuple[float, float]]
    driven_endpoints_m: tuple[tuple[float, float], tuple[float, float]]
    auxiliary_endpoints_m: tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True)
class IdealThorGripper:
    """Explicit assumed parallelogram, with the pinned source's nominal dimensions.

    This chooses the uncrossed parallelogram branch with constant finger
    orientation. q is a mathematical closing coordinate from outward-horizontal
    links; it is NOT MG995 shaft position, pulse width or an installed zero.
    """

    link_length_m: float = 0.035
    driven_half_spacing_m: float = 0.0145
    auxiliary_half_spacing_m: float = 0.006
    driven_base_y_m: float = 0.0325
    auxiliary_base_y_m: float = 0.051
    contact_offset_from_driven_tip_m: float = 0.0145

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, _finite(getattr(self, name)))
        if not (
            self.link_length_m > 0
            and self.driven_half_spacing_m > self.auxiliary_half_spacing_m > 0
            and self.auxiliary_base_y_m > self.driven_base_y_m
            and 0 <= self.contact_offset_from_driven_tip_m <= self.driven_half_spacing_m
        ):
            raise ValueError("geometry must define the stated uncrossed study branch")

    def state(self, closing_angle_rad: float) -> JawState:
        """Evaluate 0 <= q < pi/2, a study interval, not a physical travel limit.

        At its excluded upper endpoint the default nominal faces touch. Interference,
        contact deformation, stops and servo travel are not evaluated here.
        """
        q = _finite(closing_angle_rad)
        if not 0 <= q < math.pi / 2:
            raise ValueError("angle outside declared analytical study interval [0,pi/2)")
        length, c, s = self.link_length_m, math.cos(q), math.sin(q)
        # side order is left(-X), right(+X). Finger orientation stays constant.
        translation = tuple((side * length * (c - 1), length * s) for side in (-1, 1))
        derivative = tuple((-side * length * s, length * c) for side in (-1, 1))
        driven = tuple(
            (side * (self.driven_half_spacing_m + length * c), self.driven_base_y_m + length * s)
            for side in (-1, 1)
        )
        auxiliary = tuple(
            (
                side * (self.auxiliary_half_spacing_m + length * c),
                self.auxiliary_base_y_m + length * s,
            )
            for side in (-1, 1)
        )
        gap = 2 * (self.driven_half_spacing_m + length * c - self.contact_offset_from_driven_tip_m)

        def checked_pairs(values):
            return tuple(tuple(_finite(component) for component in pair) for pair in values)

        return JawState(
            q,
            _finite(gap),
            _finite(-2 * length * s),
            checked_pairs(translation),
            checked_pairs(derivative),
            checked_pairs(driven),
            checked_pairs(auxiliary),
        )
