"""Task waypoint proposals, with point envelope checks; no path clearance claim."""

from dataclasses import dataclass

from raftel_arm01.config import Config
from raftel_arm01.models import ObjectPose, Position


@dataclass(frozen=True)
class PickPlace:
    approach: Position
    pickup: Position
    lift: Position
    transit: Position
    placement: Position
    retreat: Position


def plan(obj: ObjectPose, config: Config) -> PickPlace:
    if obj.mass_kg > config.envelope.max_payload_kg:
        raise ValueError("payload exceeds logical limit")
    bins = {b.category: b for b in config.bins}
    if obj.category not in bins:
        raise ValueError("unknown category")
    target = bins[obj.category].position
    pickup_top = obj.position.above(config.clearance_m)
    target_top = target.above(config.clearance_m)
    result = PickPlace(pickup_top, obj.position, pickup_top, target_top, target, target_top)
    for point in (
        result.approach,
        result.pickup,
        result.lift,
        result.transit,
        result.placement,
        result.retreat,
    ):
        config.envelope.validate(point)
    return result
