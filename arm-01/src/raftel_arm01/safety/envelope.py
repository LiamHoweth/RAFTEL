"""Logical envelope guard only: not IK, joint limits, or collision checking."""

from dataclasses import dataclass

from raftel_arm01._validation import finite
from raftel_arm01.models import Position


@dataclass(frozen=True)
class Envelope:
    min_radius_m: float = 0.06
    max_radius_m: float = 0.40
    min_z_m: float = 0.0
    max_z_m: float = 0.35
    max_payload_kg: float = 0.10

    def __post_init__(self) -> None:
        for field in ("min_radius_m", "max_radius_m", "min_z_m", "max_z_m", "max_payload_kg"):
            finite(getattr(self, field), field)
        if not (
            0 <= self.min_radius_m < self.max_radius_m
            and 0 <= self.min_z_m < self.max_z_m
            and self.max_payload_kg > 0
        ):
            raise ValueError("invalid envelope bounds")

    def contains(self, position: Position) -> bool:
        if not isinstance(position, Position):
            raise ValueError("envelope position must be a Position in arm_base")
        radius = position.distance(Position(0, 0, 0))
        return (
            self.min_radius_m <= radius <= self.max_radius_m
            and self.min_z_m <= position.z <= self.max_z_m
        )

    def validate(self, position: Position) -> None:
        if not self.contains(position):
            raise ValueError("position outside logical envelope")
