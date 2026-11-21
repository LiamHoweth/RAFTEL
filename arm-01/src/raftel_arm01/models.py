"""SI-unit task models; positions are in the stationary arm_base frame."""

from dataclasses import dataclass
from math import dist

from raftel_arm01._validation import finite


@dataclass(frozen=True)
class Position:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        for coordinate in (self.x, self.y, self.z):
            finite(coordinate, "position coordinate in metres")

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
        if not isinstance(self.position, Position):
            raise ValueError("object position must be a Position in arm_base")
        if finite(self.mass_kg, "mass in kilograms") <= 0:
            raise ValueError("mass must be positive")


@dataclass(frozen=True)
class Bin:
    category: str
    position: Position

    def __post_init__(self) -> None:
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("bin category must be a nonempty string")
        if not isinstance(self.position, Position):
            raise ValueError("bin position must be a Position in arm_base")
