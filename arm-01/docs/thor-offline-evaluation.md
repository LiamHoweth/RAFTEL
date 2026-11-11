# Offline outcome replay and logical benchmarks

`raftel-evaluate` scores predeclared objects and ordered observation records. It
also runs the existing logical sorter across seeded layouts. It neither commands
hardware nor adds vision, IK, collision checking or physical outcome verification.

```powershell
raftel-evaluate benchmark --seed 42 --layouts 10 --count 10 --output logical-benchmark.json
raftel-evaluate benchmark --layouts 3 --unreachable --fail-grasp object-00 --output logical-faults.json
raftel-evaluate score --manifest presented.json --events observations.jsonl --output scored.json
```

Output paths must be new. Exit 0 means no unsuccessful attempted, failed or
unresolved objects in the declared eligible run; exclusions remain visible.
Exit 1 preserves a valid report containing those outcomes. Exit 2 means invalid
input or output failure. A successful command never upgrades the evidence class.

## Predeclared inputs and event contract

A version-1 manifest contains `run_id`, `layout_id`, `evidence_class`, nonempty
`provenance`, `max_attempts` (1–20), and 1–10,000 `objects`. Each object has `id`,
`expected_bin` and a boolean `eligible`. Eligibility is declared before replay,
so missed detections and truncated logs cannot shrink the denominator. Supported
classes are `logical_only`, `kinematic_simulation`, `physics_simulation` and
`physical`. These are input claims; this tool cannot authenticate a physical trial.

Each UTF-8 JSONL event has a contiguous zero-based `sequence`, `object_id` and
`event`. Duplicate keys, unknown fields, nonfinite numbers and undeclared IDs are
rejected. Event-specific fields are:

| Event | Required extra fields and meaning |
| --- | --- |
| `detected` | One detection per object, before an attempt |
| `attempted` | Consecutive `attempt`, with declared eligibility and detection |
| `verified` | Matching active `attempt`, `observed_bin`, and explicit `independent_verification: true` |
| `failed` | Matching active `attempt` and nonempty `detail`; permits a bounded retry |
| `timed_out` | Terminal unsuccessful outcome, including when detection never occurred |
| `assisted` | Nonempty `detail`; must precede a terminal placement observation |

An incorrect observed bin closes a failed attempt and records a misroute. Another
attempt requires that prior closure and cannot exceed the manifest limit. A
correct placement or timeout terminates the object. Assisted placements never
count as autonomous correct placements, while their objects remain in the
predeclared denominators. A detection, command or attempted grasp is insufficient
for success. An unfinished attempt or remaining unattempted eligible object stays
unresolved rather than disappearing from the report.

`failed_attempts`, terminal `failed` objects, `unsuccessful_attempted_objects`,
timeouts, misses, assistance and unresolved objects are separate counts. They are
not disjoint categories to sum into an invented total. The report also separates
first-attempt success, success after retries, attempted/presented coverage,
correct/eligible completion and correct/presented completion.

The reader bounds each line to 1 MiB, the event file to 64 MiB and the event count
to one million. The benchmark CLI bounds presented objects to 100,000. It rejects
oversized requests before generating scenes. Valid parsing alone does not prove
record provenance or correct observations.

## Logical adapter and uncertainty

The adapter reuses `generate_objects`, the existing point-envelope planner,
`MockArm` and `Sorter`; it does not introduce another task controller. All
synthetic objects are detected, eligibility is computed before execution, and
existing retry/terminal outcomes become explicitly logical replay observations.
Input hashes cover the expanded configuration, scene, injected faults and exact
installed source-file hashes; manifest/event canonical hashes accompany each run.
The scorer CLI hashes its validated manifest model and parsed event list, avoiding
reopening a mutable input file to claim a mismatched byte digest.

Layout summaries pool numerators and denominators instead of averaging unequal
layout proportions. A 95% object-level Wilson interval is descriptive and ignores
within-layout correlation. Seeded bootstrap intervals resample whole layouts;
they require at least two distinct layouts and no undefined denominator resamples.
Undefined resamples remain counted. Unique layout IDs do not establish independent
physical resets. Neither interval converts simulated success into physical
reliability or proves that an underlying success probability exceeds 90%.

## Installed-wheel reproduction

```powershell
python -m pip wheel --no-deps --wheel-dir wheel-output .
python tools/verify_installed_wheel.py --wheel wheel-output/raftel_arm01-0.1.0-py3-none-any.whl --run-dir wheel-check-new
```

Wheel building may obtain the pinned build backend. The separate verification
installs the exact bounded, inspected wheel bytes with `--isolated --no-index
--no-deps` into a new retained virtual environment. It clears Python source-path
overrides, verifies every imported module origin within that environment, and
checks installed success/failure/invalid-input paths for both CLIs. A fresh
workspace may be inside ignored repository scratch; the evidence is import-origin
isolation and offline installation, not a claim about its directory ancestry or
a network sandbox. No robot/CAD runtime is exercised.

Tests include hand-counted mixed outcomes, invalid histories, provenance/parser
guards, unequal layout denominators and output preservation. See the separate
[independent review](evaluation-independent-review.md) and
[current handoff](../../nextSteps.md) for actually executed results and exact CI.
