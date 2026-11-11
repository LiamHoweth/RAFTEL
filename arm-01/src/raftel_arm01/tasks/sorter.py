"""Bounded, deterministic task transitions with explicit terminal outcomes."""

from dataclasses import asdict, dataclass
from enum import Enum

from raftel_arm01.config import Config
from raftel_arm01.control.interface import Arm, ArmFault
from raftel_arm01.models import ObjectPose
from raftel_arm01.planning.sorting import plan


class State(str, Enum):
    OBSERVE = "observe"
    SELECT = "select"
    APPROACH = "approach"
    GRASP = "grasp"
    TRANSFER = "transfer"
    RELEASE = "release"
    VERIFY = "verify"
    RETREAT = "retreat"
    SORTED = "sorted"
    SKIPPED = "skipped"
    FAILED = "failed"
    ABORTED = "aborted"
    COMPLETE = "complete"


@dataclass(frozen=True)
class Event:
    sequence: int
    state: str
    object_id: str | None
    attempt: int
    detail: str


@dataclass(frozen=True)
class Result:
    sorted_ids: tuple[str, ...]
    skipped_ids: tuple[str, ...]
    failed_ids: tuple[str, ...]
    aborted: bool
    events: tuple[Event, ...]
    pending_ids: tuple[str, ...] = ()

    def summary(self) -> dict:
        return {
            "simulation": "logical_only",
            "sorted": len(self.sorted_ids),
            "skipped": len(self.skipped_ids),
            "failed": len(self.failed_ids),
            "aborted": self.aborted,
            "pending": len(self.pending_ids),
        }

    def records(self) -> list[dict]:
        return [asdict(event) for event in self.events]


class Sorter:
    def __init__(self, arm: Arm, config: Config):
        self.arm = arm
        self.config = config

    def run(self, objects: list[ObjectPose]) -> Result:
        ids = [obj.identifier for obj in objects]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate object IDs")
        events: list[Event] = []
        sorted_ids: list[str] = []
        skipped: list[str] = []
        failed: list[str] = []

        def emit(
            state: State, obj: ObjectPose | None = None, attempt: int = 0, detail: str = ""
        ) -> None:
            events.append(
                Event(len(events), state.value, obj.identifier if obj else None, attempt, detail)
            )

        emit(State.OBSERVE, detail="synthetic input poses in arm_base")
        # Stable ID order means identical observations produce identical actions.
        for obj in sorted(objects, key=lambda item: item.identifier):
            emit(State.SELECT, obj)
            try:
                motion = plan(obj, self.config)
            except ValueError as exc:
                skipped.append(obj.identifier)
                emit(State.SKIPPED, obj, detail=str(exc))
                continue
            try:
                for attempt in range(1, self.config.max_attempts + 1):
                    emit(State.APPROACH, obj, attempt)
                    self.arm.move_to(motion.approach)
                    self.arm.move_to(motion.pickup)
                    emit(State.GRASP, obj, attempt)
                    if not self.arm.grasp(obj):
                        self.arm.move_to(motion.approach)
                        if attempt == self.config.max_attempts:
                            failed.append(obj.identifier)
                            emit(State.FAILED, obj, attempt, "grasp attempts exhausted")
                        continue
                    emit(State.TRANSFER, obj, attempt)
                    self.arm.move_to(motion.lift)
                    self.arm.move_to(motion.transit)
                    self.arm.move_to(motion.placement)
                    emit(State.RELEASE, obj, attempt)
                    self.arm.release()
                    emit(State.VERIFY, obj, attempt)
                    if not self.arm.verify_placement(obj, motion.placement):
                        raise ArmFault("placement verification failed; location uncertain")
                    emit(State.RETREAT, obj, attempt)
                    self.arm.move_to(motion.retreat)
                    sorted_ids.append(obj.identifier)
                    emit(State.SORTED, obj, attempt, "mock placement confirmed")
                    break
            except ArmFault as exc:
                self.arm.stop()
                failed.append(obj.identifier)
                emit(State.ABORTED, obj, detail=str(exc))
                accounted = set(sorted_ids + skipped + failed)
                pending = tuple(
                    sorted(identifier for identifier in ids if identifier not in accounted)
                )
                return Result(
                    tuple(sorted_ids), tuple(skipped), tuple(failed), True, tuple(events), pending
                )
            except Exception:
                # Unexpected backend/programming errors remain visible, but first
                # latch a stop; implementations must normalize expected I/O faults.
                self.arm.stop()
                raise
        emit(State.COMPLETE, detail="all observations processed; see skipped/failed outcomes")
        return Result(tuple(sorted_ids), tuple(skipped), tuple(failed), False, tuple(events))
