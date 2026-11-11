#!/usr/bin/env python3
"""Replay bounded local diagnostic fixtures; no serial or hardware operations."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from raftel_arm01.control.calibration_evidence import load_calibration
from raftel_arm01.control.thor_protocol_replay import DiagnosticReplay
from raftel_arm01.control.thor_source_conversion import source_write


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON script field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON script constant: {value}")


def replay_document(document: dict) -> dict:
    """Execute explicitly tagged synthetic operations, failing unknown fields."""
    if not isinstance(document, dict) or set(document) != {"schema_version", "events"}:
        raise ValueError("replay document requires schema_version and events only")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("unsupported replay schema")
    events = document["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= 10_000:
        raise ValueError("replay requires 1..10000 synthetic events")
    model = DiagnosticReplay()
    results = []
    previous = {"thor_pcb": (0,) * 7, "fly": (0,) * 7}
    for index, event in enumerate(events):
        if not isinstance(event, dict) or not isinstance(event.get("action"), str):
            raise ValueError(f"event {index} requires an action")
        action = event["action"]
        if action == "source_write":
            if set(event) != {"action", "board", "joints_rad"}:
                raise ValueError("source_write event requires board and joints_rad only")
            board = event["board"]
            if board not in previous:
                raise ValueError("unsupported source board")
            converted = source_write(
                event["joints_rad"], board=board, previous_angles_deg=previous[board]
            )
            previous[board] = converted.angles_deg
            result = asdict(converted)
            result["transmitted"] = False
        elif action == "submit":
            if set(event) != {"action", "line", "acknowledgment_received"}:
                raise ValueError("submit requires line and explicit synthetic acknowledgment flag")
            result = asdict(
                model.submit(
                    event["line"], acknowledgment_received=event["acknowledgment_received"]
                )
            )
        elif action == "complete_next":
            if set(event) != {"action"}:
                raise ValueError("complete_next event accepts no extra fields")
            result = asdict(model.complete_next())
        elif action == "acknowledge":
            if set(event) != {"action", "sequence"}:
                raise ValueError("acknowledge requires sequence only")
            result = asdict(model.acknowledge(event["sequence"]))
        elif action == "status":
            if set(event) != {"action", "timestamp_s"}:
                raise ValueError("status requires timestamp_s only")
            result = asdict(model.status(event["timestamp_s"]))
        elif action == "reset":
            if set(event) != {"action"}:
                raise ValueError("reset event accepts no extra fields")
            model.reset()
            result = {"fault": model.fault, "position_knowledge": "invalidated"}
        else:
            raise ValueError(f"unsupported replay action {action}")
        results.append({"event": index, "action": action, "result": result})
    return {
        "schema_version": 1,
        "evidence_class": "synthetic_protocol_replay_not_measured_pose",
        "events": results,
        "final_fault": model.fault,
        "receipts": [asdict(receipt) for receipt in model.receipts],
        "hardware_connection": False,
        "firmware_executed": False,
        "commissioned": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, help="bounded JSON replay events")
    parser.add_argument("--calibration", type=Path, help="offline calibration evidence JSON")
    parser.add_argument("--expected-calibration-sha256", help="expected evidence file byte hash")
    parser.add_argument(
        "--output", type=Path, help="new diagnostic report path; existing files refused"
    )
    args = parser.parse_args(argv)
    try:
        if args.expected_calibration_sha256 is not None and args.calibration is None:
            raise ValueError("an expected calibration hash requires --calibration")
        if args.script is None:
            document = {
                "schema_version": 1,
                "events": [
                    {"action": "source_write", "board": "thor_pcb", "joints_rad": [0] * 7},
                    {"action": "submit", "line": "G90", "acknowledgment_received": True},
                    {
                        "action": "submit",
                        "line": "G0 B10 C10 D20",
                        "acknowledgment_received": True,
                    },
                    {"action": "status", "timestamp_s": 0},
                    {"action": "complete_next"},
                    {"action": "complete_next"},
                    {"action": "status", "timestamp_s": 1},
                ],
            }
        else:
            if args.script.stat().st_size > 1_048_576:
                raise ValueError("replay document exceeds one MiB")
            document = json.loads(
                args.script.read_bytes(),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        report = replay_document(document)
        if args.calibration is not None:
            report["calibration"] = asdict(
                load_calibration(args.calibration, expected_sha256=args.expected_calibration_sha256)
            )
        output = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            print(output, end="")
        else:
            # Preserve historical evidence rather than silently overwrite it.
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(output)
    except (OSError, ValueError, TypeError, OverflowError) as error:
        print(f"controller replay: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
