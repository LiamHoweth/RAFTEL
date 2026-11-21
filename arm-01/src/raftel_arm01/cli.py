"""Offline demonstration entry point; deliberately offers no real hardware mode."""

import argparse
import json
import sys
from pathlib import Path

from raftel_arm01.config import load_config
from raftel_arm01.control.mock import MockArm
from raftel_arm01.demo import run_report
from raftel_arm01.demo_svg import render_svg
from raftel_arm01.perception.synthetic import generate_objects
from raftel_arm01.scene import load_scene
from raftel_arm01.tasks.sorter import Sorter


def _validate_paths(args: argparse.Namespace) -> None:
    inputs = [path for path in (args.config, args.scene) if path is not None]
    outputs = [path for path in (args.log, args.report, args.svg) if path is not None]
    try:
        resolved_outputs = {path.resolve() for path in outputs}
        resolved_inputs = {path.resolve() for path in inputs}
    except RuntimeError as exc:
        raise ValueError("could not resolve input/output paths") from exc
    if len(resolved_outputs) != len(outputs) or resolved_outputs & resolved_inputs:
        raise ValueError("output paths must be distinct from each other and all inputs")
    for path in outputs:
        if not path.parent.is_dir():
            raise ValueError(f"output directory does not exist: {path.parent}")
    if args.log is not None and args.log.exists():
        if any(path.exists() and args.log.samefile(path) for path in inputs):
            raise ValueError("event log path aliases an input file")
    for path in (args.report, args.svg):
        if path is not None and (path.exists() or path.is_symlink()):
            raise FileExistsError(f"refusing to overwrite output: {path}")


def _write_new(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAFTEL logical-only sorting simulation")
    parser.add_argument("--seed", type=int, help="synthetic layout seed (default: 42)")
    parser.add_argument("--count", type=int, help="synthetic object count (default: 10)")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--unreachable", action="store_true")
    parser.add_argument("--scene", type=Path, help="explicit arm_base object layout JSON")
    parser.add_argument("--fail-grasp", action="append", default=[], metavar="OBJECT_ID")
    parser.add_argument("--log", type=Path, help="write structured JSONL event records")
    parser.add_argument("--report", type=Path, help="create a logical run report JSON")
    parser.add_argument("--svg", type=Path, help="create an XY plot of the mock run")
    args = parser.parse_args(argv)
    try:
        if args.scene and (args.seed is not None or args.count is not None or args.unreachable):
            raise ValueError("--scene cannot be combined with --seed, --count or --unreachable")
        _validate_paths(args)
        config = load_config(args.config)
        seed = None
        if args.scene:
            objects = load_scene(args.scene)
        else:
            seed = 42 if args.seed is None else args.seed
            count = 10 if args.count is None else args.count
            objects = generate_objects(
                seed, count, args.unreachable, tuple(b.category for b in config.bins)
            )
        failures = set(args.fail_grasp)
        if not failures.issubset({obj.identifier for obj in objects}):
            raise ValueError("failure injection references unknown object IDs")
        arm = MockArm(config.envelope, failures)
        result = Sorter(arm, config).run(objects)
        if args.report:
            report = run_report(
                config, objects, result, arm.placements, seed=seed, failures=failures
            )
            _write_new(args.report, json.dumps(report, indent=2, allow_nan=False) + "\n")
        if args.svg:
            _write_new(args.svg, render_svg(config, objects, result, arm.placements))
        if args.log:
            args.log.write_text(
                "".join(json.dumps(record, allow_nan=False) + "\n" for record in result.records()),
                encoding="utf-8",
                newline="\n",
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
