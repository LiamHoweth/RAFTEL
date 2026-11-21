"""Seeded logical sorter replays and layout-aware descriptive summaries."""

import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import asdict
from importlib.metadata import version
from importlib.resources import files

from raftel_arm01.config import Config, load_config
from raftel_arm01.control.mock import MockArm
from raftel_arm01.perception.synthetic import generate_objects
from raftel_arm01.planning.sorting import plan
from raftel_arm01.tasks.sorter import Sorter

from .replay import _integer, score_replay, wilson_interval


def implementation_fingerprint() -> dict:
    """Pin the installed Python sources affecting this logical benchmark."""
    paths = (
        "_validation.py",
        "config.py",
        "models.py",
        "defaults.json",
        "control/mock.py",
        "control/interface.py",
        "perception/synthetic.py",
        "safety/envelope.py",
        "planning/sorting.py",
        "tasks/sorter.py",
        "evaluation/replay.py",
        "evaluation/benchmark.py",
        "evaluation/cli.py",
    )
    package = files("raftel_arm01")
    return {
        "package_version": version("raftel-arm01"),
        "installed_file_sha256": {
            path: hashlib.sha256(package.joinpath(*path.split("/")).read_bytes()).hexdigest()
            for path in paths
        },
    }


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def logical_layout(
    seed: int,
    *,
    count: int = 10,
    unreachable: bool = False,
    failed_grasp_ids: Sequence[str] = (),
    config: Config | None = None,
) -> tuple[dict, list[dict], dict]:
    """Run existing logical task code and export an explicitly synthetic replay.

    Eligibility is computed before execution from the existing abstract point
    planner. No IK/collision or physical observation is added by this adapter.
    """
    _integer(seed, "seed", -(2**63), 2**63 - 1)
    _integer(count, "count", 1, 1000)
    if type(unreachable) is not bool:
        raise ValueError("unreachable must be boolean")
    config = config or load_config()
    objects = generate_objects(seed, count, unreachable, tuple(b.category for b in config.bins))
    if isinstance(failed_grasp_ids, str) or not isinstance(failed_grasp_ids, Sequence):
        raise ValueError("failed_grasp_ids must be a sequence of object IDs")
    if any(not isinstance(item, str) for item in failed_grasp_ids):
        raise ValueError("failed grasp IDs must be strings")
    failures = set(failed_grasp_ids)
    if not failures <= {obj.identifier for obj in objects}:
        raise ValueError("failed grasp injection references unknown objects")
    declared = []
    for obj in objects:
        try:
            plan(obj, config)
            eligible = True
        except ValueError:
            eligible = False
        declared.append({"id": obj.identifier, "expected_bin": obj.category, "eligible": eligible})
    inputs = {
        "seed": seed,
        "config": asdict(config),
        "objects": [asdict(obj) for obj in objects],
        "failed_grasp_ids": sorted(failures),
        "implementation": implementation_fingerprint(),
    }
    input_hash = canonical_sha256(inputs)
    manifest = {
        "schema_version": 1,
        "run_id": f"logical-{seed}-{input_hash[:16]}",
        "layout_id": f"synthetic-layout-{seed}",
        "evidence_class": "logical_only",
        "provenance": f"Existing seeded logical sorter; canonical input sha256:{input_hash}",
        "max_attempts": config.max_attempts,
        "objects": declared,
    }
    arm = MockArm(config.envelope, failures)
    result = Sorter(arm, config).run(objects)
    records = []

    def emit(identifier, kind, **fields):
        records.append({"sequence": len(records), "event": kind, "object_id": identifier, **fields})

    for obj in objects:
        emit(obj.identifier, "detected")
    active = {}
    for event in result.events:
        if event.state == "approach":
            if event.object_id in active:
                emit(
                    event.object_id,
                    "failed",
                    attempt=active[event.object_id],
                    detail="mock grasp returned false before retry",
                )
            active[event.object_id] = event.attempt
            emit(event.object_id, "attempted", attempt=event.attempt)
        elif event.state == "sorted":
            attempt = active.pop(event.object_id)
            position = arm.placements.get(event.object_id)
            observed_bin = config.bin_at(position) if position is not None else None
            if observed_bin is None:
                emit(
                    event.object_id,
                    "failed",
                    attempt=attempt,
                    detail="mock backend has no placement at a declared bin",
                )
            else:
                emit(
                    event.object_id,
                    "verified",
                    attempt=attempt,
                    observed_bin=observed_bin.category,
                    independent_verification=True,
                    detail="placement read from logical mock backend state",
                )
        elif event.state in {"failed", "aborted"} and event.object_id in active:
            emit(
                event.object_id, "failed", attempt=active.pop(event.object_id), detail=event.detail
            )
    score_replay(manifest, records)
    return (
        manifest,
        records,
        {
            "evidence_class": "logical_only",
            "inputs": inputs,
            "input_canonical_sha256": input_hash,
            "manifest_canonical_sha256": canonical_sha256(manifest),
            "events_canonical_sha256": canonical_sha256(records),
            "original_summary": result.summary(),
        },
    )


def summarize_runs(
    runs: Sequence[tuple[dict, Sequence[dict]]],
    *,
    bootstrap_seed: int = 42,
    bootstrap_resamples: int = 2000,
) -> dict:
    """Score raw replays and resample whole layouts, preserving denominators.

    The bootstrap interval is descriptive and assumes independent reset
    layouts. A distinct layout ID cannot establish that physical independence.
    """
    if not isinstance(runs, Sequence) or not 1 <= len(runs) <= 1000:
        raise ValueError("provide 1..1000 independent declared layout replays")
    _integer(bootstrap_seed, "bootstrap_seed", -(2**63), 2**63 - 1)
    _integer(bootstrap_resamples, "bootstrap_resamples", 100, 20_000)
    reports = [score_replay(manifest, events) for manifest, events in runs]
    for key in ("run_id", "layout_id"):
        if len({report[key] for report in reports}) != len(reports):
            raise ValueError(f"duplicate {key}; do not double-count a layout")
    evidence = {report["evidence_class"] for report in reports}
    if len(evidence) != 1:
        raise ValueError("different evidence classes must be summarized separately")
    totals = {key: sum(report["counts"][key] for report in reports) for key in reports[0]["counts"]}
    rates = {}
    rng = random.Random(bootstrap_seed)
    # Keep only resampled sufficient counts, rather than O(layouts * resamples) references.
    samples = []
    if len(reports) > 1:
        for _ in range(bootstrap_resamples):
            sample = {key: 0 for key in ("correct", "attempted", "eligible", "presented")}
            for _ in reports:
                selected = reports[rng.randrange(len(reports))]["counts"]
                for key in sample:
                    sample[key] += selected[key]
            samples.append(sample)
    for name, numerator, denominator in (
        ("after_retry_cycle_success", "correct", "attempted"),
        ("eligible_end_to_end_completion", "correct", "eligible"),
        ("presented_end_to_end_completion", "correct", "presented"),
    ):
        values = []
        undefined = 0
        for sample in samples:
            count = sample[denominator]
            if count:
                values.append(sample[numerator] / count)
            else:
                undefined += 1
        values.sort()
        interval = None
        if values and not undefined:
            interval = [
                values[int(0.025 * (len(values) - 1))],
                values[int(0.975 * (len(values) - 1))],
            ]
        rates[name] = {
            "pooled_observed_proportion": totals[numerator] / totals[denominator]
            if totals[denominator]
            else None,
            "layout_bootstrap_percentile_95": interval,
            "undefined_resamples": undefined,
        }
    return {
        "schema_version": 1,
        "evidence_class": reports[0]["evidence_class"],
        "layout_count": len(reports),
        "totals": totals,
        "rates": rates,
        "object_level_cycle_wilson_95": wilson_interval(totals["correct"], totals["attempted"]),
        "bootstrap": {
            "seed": bootstrap_seed,
            "resamples": bootstrap_resamples,
            "unit": "whole_layout",
        },
        "layouts": reports,
        "limitations": [
            "Layouts must be independently reset; unique IDs do not prove independence.",
            "Bootstrap interval requires at least two layouts and no zero-denominator resamples.",
            "Object-level Wilson interval ignores within-layout correlation.",
            "Observed simulated proportions do not establish physical reliability.",
        ],
    }
