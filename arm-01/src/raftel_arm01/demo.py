"""Run reports derived from the mock task's inputs, events, and placements."""

from dataclasses import asdict

from raftel_arm01.config import Config
from raftel_arm01.models import ObjectPose, Position
from raftel_arm01.scene import SCENE_FRAME, scene_data
from raftel_arm01.tasks.sorter import Result, State


def run_report(
    config: Config,
    objects: list[ObjectPose],
    result: Result,
    placements: dict[str, Position],
    *,
    seed: int | None,
    failures: set[str],
) -> dict:
    terminals = {State.SORTED, State.SKIPPED, State.FAILED, State.ABORTED}
    final_events = {event.object_id: event for event in result.events if event.state in terminals}
    attempts = {
        event.object_id: event.attempt for event in result.events if event.state == State.APPROACH
    }
    destinations = {item.category for item in config.bins}
    outcomes = []
    for obj in sorted(objects, key=lambda item: item.identifier):
        terminal = final_events.get(obj.identifier)
        placement = placements.get(obj.identifier)
        recorded_bin = config.bin_at(placement) if placement is not None else None
        outcomes.append(
            {
                "object_id": obj.identifier,
                "target_bin": obj.category if obj.category in destinations else None,
                "terminal_state": terminal.state if terminal else "pending",
                "attempts": attempts.get(obj.identifier, 0),
                "detail": terminal.detail if terminal else "task aborted before selection",
                "mock_recorded_bin": recorded_bin.category if recorded_bin else None,
                "mock_recorded_placement_m": asdict(placement) if placement is not None else None,
            }
        )
    return {
        "schema_version": 1,
        "evidence_class": "logical_only",
        "seed": seed,
        "config": {"frame": SCENE_FRAME, **asdict(config)},
        "scene": scene_data(objects),
        "failed_grasp_ids": sorted(failures),
        "summary": result.summary(),
        "outcomes": outcomes,
    }
