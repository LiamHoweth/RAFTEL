"""Seeded known object poses, never presented as camera observations."""

import random
from collections.abc import Sequence

from raftel_arm01.models import ObjectPose, Position


def generate_objects(
    seed: int,
    count: int = 10,
    unreachable: bool = False,
    categories: Sequence[str] = ("red", "green", "blue"),
) -> list[ObjectPose]:
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError("count must be integer 1..1000")
    if type(unreachable) is not bool:
        raise ValueError("unreachable must be boolean")
    if (
        not isinstance(categories, Sequence)
        or isinstance(categories, str)
        or not categories
        or any(not isinstance(c, str) or not c.strip() for c in categories)
    ):
        raise ValueError("categories must be nonempty strings")
    rng = random.Random(seed)
    objects = [
        ObjectPose(
            f"object-{i:02d}",
            categories[i % len(categories)],
            Position(rng.uniform(-0.12, 0.12), rng.uniform(0.14, 0.25), 0.02),
            rng.uniform(0.01, 0.05),
        )
        for i in range(count)
    ]
    if unreachable:
        objects.append(ObjectPose("outside", categories[0], Position(0, 0.7, 0.02), 0.02))
    return objects
