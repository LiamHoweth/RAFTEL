"""SI-unit task models; positions are in the stationary arm_base frame."""

from dataclasses import dataclass
from math import dist, isfinite


@dataclass(frozen=True)
class Position:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.x, self.y, self.z)):
            raise ValueError("position must contain finite metres")

    def distance(self, other: "Position") -> float:
        return dist((self.x, self.y, self.z), (other.x, other.y, other.z))

    def above(self, clearance: float) -> "Position":
        return Position(self.x, self.y, self.z + clearance)


@dataclass(frozen=True)
class ObjectPose:
    identifier: str
    category: str
    position: Position
    mass_kg: float

    def __post_init__(self) -> None:
        if (
            not isinstance(self.identifier, str)
            or not isinstance(self.category, str)
            or not self.identifier.strip()
            or not self.category.strip()
        ):
            raise ValueError("object ID and category must be nonempty")
        if not isfinite(self.mass_kg) or self.mass_kg <= 0:
            raise ValueError("mass must be finite and positive")


@dataclass(frozen=True)
class Bin:
    category: str
    position: Position
