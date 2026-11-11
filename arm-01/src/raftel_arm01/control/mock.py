"""Discrete logical state, with injected grasp failures. No joint/physics model."""

from raftel_arm01.control.interface import ArmFault
from raftel_arm01.models import ObjectPose, Position
from raftel_arm01.safety.envelope import Envelope


class MockArm:
    def __init__(self, envelope: Envelope, failed_grasps: set[str] | None = None):
        self.envelope = envelope
        self.failed_grasps = set(failed_grasps or ())
        self.position: Position | None = None
        self.held: ObjectPose | None = None
        self.placements: dict[str, Position] = {}
        self.stopped = False

    def _ready(self) -> None:
        if self.stopped:
            raise ArmFault("mock arm is stopped")

    def move_to(self, position: Position) -> None:
        self._ready()
        try:
            self.envelope.validate(position)
        except ValueError as exc:
            raise ArmFault(str(exc)) from exc
        self.position = position

    def grasp(self, obj: ObjectPose) -> bool:
        self._ready()
        if self.held is not None or self.position != obj.position:
            raise ArmFault("invalid mock grasp state")
        if obj.mass_kg > self.envelope.max_payload_kg:
            raise ArmFault("payload exceeds logical limit")
        if obj.identifier in self.failed_grasps:
            return False
        self.held = obj
        return True

    def release(self) -> None:
        self._ready()
        if self.held is None or self.position is None:
            raise ArmFault("nothing held for release")
        self.placements[self.held.identifier] = self.position
        self.held = None

    def verify_placement(self, obj: ObjectPose, destination: Position) -> bool:
        self._ready()
        return self.held is None and self.placements.get(obj.identifier) == destination

    def stop(self) -> None:
        # A logical stop latches movement; it does not release a held object.
        self.stopped = True
