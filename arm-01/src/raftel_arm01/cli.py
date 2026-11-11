"""Offline demonstration entry point; deliberately offers no real hardware mode."""

import argparse
import json
import sys
from pathlib import Path

from raftel_arm01.config import load_config
from raftel_arm01.control.mock import MockArm
from raftel_arm01.perception.synthetic import generate_objects
from raftel_arm01.tasks.sorter import Sorter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAFTEL logical-only sorting simulation")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--unreachable", action="store_true")
    parser.add_argument("--fail-grasp", action="append", default=[], metavar="OBJECT_ID")
    parser.add_argument("--log", type=Path, help="write structured JSONL event records")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        objects = generate_objects(
            args.seed, args.count, args.unreachable, tuple(b.category for b in config.bins)
        )
        failures = set(args.fail_grasp)
        if not failures.issubset({obj.identifier for obj in objects}):
            raise ValueError("failure injection references unknown object IDs")
        result = Sorter(MockArm(config.envelope, failures), config).run(objects)
        if args.log:
            args.log.write_text(
                "".join(json.dumps(record, allow_nan=False) + "\n" for record in result.records())
            )
        else:
            for record in result.records():
                print(json.dumps(record, allow_nan=False))
        print(json.dumps(result.summary(), allow_nan=False))
        return int(result.aborted or bool(result.failed_ids))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"configuration/input error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
