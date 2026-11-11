"""Task-level arm contract, intentionally independent of actuator commands."""

from typing import Protocol

from raftel_arm01.models import ObjectPose, Position


class ArmFault(RuntimeError):
    """Motion or feedback fault: stop the task, do not blindly retry."""


class Arm(Protocol):
    """Backends normalize command/feedback failures to ArmFault.

    stop() must be idempotent and latch further movement without releasing a
    held object. A future physical backend needs independent commissioning;
    this task interface alone cannot establish motion safety.
    """

    def move_to(self, position: Position) -> None: ...
    def grasp(self, obj: ObjectPose) -> bool: ...
    def release(self) -> None: ...
    def verify_placement(self, obj: ObjectPose, destination: Position) -> bool: ...
    def stop(self) -> None: ...
