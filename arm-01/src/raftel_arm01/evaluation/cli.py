"""Installed offline replay scorer and seeded logical benchmark entry point."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from raftel_arm01.config import load_config

from .benchmark import canonical_sha256, logical_layout, summarize_runs
from .replay import read_jsonl, read_manifest, score_replay


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline outcome scoring; no robot/camera access")
    commands = parser.add_subparsers(dest="command", required=True)
    replay = commands.add_parser("score", help="score predeclared objects and observed event JSONL")
    replay.add_argument("--manifest", type=Path, required=True)
    replay.add_argument("--events", type=Path, required=True)
    replay.add_argument("--output", type=Path)
    benchmark = commands.add_parser(
        "benchmark", help="run existing logical sorter across seed layouts"
    )
    benchmark.add_argument("--seed", type=int, default=42)
    benchmark.add_argument("--layouts", type=int, default=10)
    benchmark.add_argument("--count", type=int, default=10)
    benchmark.add_argument("--config", type=Path)
    benchmark.add_argument("--unreachable", action="store_true")
    benchmark.add_argument("--fail-grasp", action="append", default=[], metavar="OBJECT_ID")
    benchmark.add_argument("--bootstrap-resamples", type=int, default=2000)
    benchmark.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "score":
            manifest = read_manifest(args.manifest)
            events = read_jsonl(args.events)
            report = score_replay(manifest, events)
            report["input_provenance"] = {
                "manifest_model_canonical_sha256": canonical_sha256(asdict(manifest)),
                "events_canonical_sha256": canonical_sha256(events),
            }
            failed = (
                report["counts"]["unsuccessful_attempted_objects"]
                or report["counts"]["unresolved"]
                or report["counts"]["failed"]
            )
        else:
            if not 1 <= args.layouts <= 1000:
                raise ValueError("layouts must be 1..1000")
            if (
                not 1 <= args.count <= 1000
                or args.layouts * (args.count + args.unreachable) > 100_000
            ):
                raise ValueError(
                    "benchmark requires count1..1000 and at most100000 presented objects"
                )
            config = load_config(args.config)
            runs, provenance = [], []
            for seed in range(args.seed, args.seed + args.layouts):
                manifest, events, metadata = logical_layout(
                    seed,
                    count=args.count,
                    unreachable=args.unreachable,
                    failed_grasp_ids=args.fail_grasp,
                    config=config,
                )
                runs.append((manifest, events))
                provenance.append(metadata)
            report = summarize_runs(
                runs, bootstrap_seed=args.seed, bootstrap_resamples=args.bootstrap_resamples
            )
            report["run_provenance"] = provenance
            failed = (
                report["totals"]["unsuccessful_attempted_objects"]
                or report["totals"]["unresolved"]
                or report["totals"]["failed"]
            )
        output = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(output)
        else:
            print(output, end="")
        return int(bool(failed))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        print(f"evaluation input/output error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
