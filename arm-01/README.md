# ARM-01 BenchSort

BenchSort tests the sequence from object observation through pick, transport and bin placement for a stationary, removable bench arm. The physical design targets six independent arm axes, a parallel gripper, 350–450 mm reach and a 100–200 g payload. The Thor-first study permits up to eight actuators, with seven arm motors including a coupled shoulder and one gripper motor. The [requirements](docs/requirements.md) and [safety gates](docs/safety.md) govern fabrication, purchases and commissioning.

The runnable experiment uses synthetic or supplied object coordinates and a mock arm. Its positions are in metres in the logical `arm_base` frame. The workspace envelope, clearance waypoint and payload screens evaluate the logical task. Nominal Thor FK, IK and study trajectories run separately.

## Run the demo

Install the package using the [quick start](../README.md#quick-start). Activate the environment or use the full path to its executables. Run the following examples from `arm-01`, choosing fresh paths for JSON reports and SVGs.

```sh
raftel-sort --seed 42 --count 10 --log sorting-events.jsonl --report benchsort.json --svg benchsort.svg
```

Seed 42 produces ten successful mock placements with zero skips, failures or pending objects. Open the SVG to see an XY projection of object origins and recorded bin destinations. Segments represent logical assignments. The JSON report preserves the expanded configuration, object data, outcome and mock placement for each object. The JSONL log preserves the task-state sequence and retry details.

### Supplied scenes and failure injection

```sh
raftel-sort --scene config/benchsort-failure.json --fail-grasp red-retry --report failure.json --svg failure.svg
```

The [four-object fixture](config/benchsort-failure.json) completes one placement, skips one out-of-envelope pickup and one overweight object, and exhausts the configured grasp attempts for `red-retry`. Expected status is `1`. The report and SVG remain available to inspect.

To make your own scene, copy the fixture and keep `schema_version` as `1` and `frame` as `arm_base`. Supply unique object identifiers, category labels, finite `position` values in metres and `mass_kg` values. Unknown categories can be supplied to exercise a planning rejection. Use `--config` with a copy of the [packaged defaults](src/raftel_arm01/defaults.json) to change the envelope, bin positions, clearance or retry limit.

To replay a report, save its `scene` and `config` fields as separate JSON files and pass them to `--scene` and `--config`. Pass the same `--fail-grasp` IDs to reproduce injected faults.

| Status | Meaning |
| --- | --- |
| `0` | Task completed without a failed object or abort. Skips are possible. |
| `1` | One or more objects failed or the run aborted. Pending observations were never attempted. |
| `2` | Invalid configuration, command arguments, scene or output path. |

For an existing seeded fault workflow, `--unreachable` places an observation outside the envelope and `--fail-grasp object-00` causes a grasp failure. Run `raftel-sort --help` for argument combinations.

## Evaluate a batch

```sh
raftel-evaluate benchmark --seed 42 --layouts 10 --count 10 --output logical-benchmark.json
```

The benchmark retains per-layout evidence and distinguishes detection, eligibility, attempts, correct placements and failures. Its replay input has a separate manifest and event schema. See [offline evaluation](docs/thor-offline-evaluation.md) for metrics, hashes, uncertainty and exit codes.

## Investigate and extend

- Use the [contributor guide](../CONTRIBUTING.md) for a pinned development environment, tests and offline wheel checks.
- Follow the [software architecture](docs/architecture.md) for task, planning, control and coordinate-frame boundaries.
- Run the [learning experiment](docs/learning-research.md) to compare a fitted screen/defer classifier with exact and trivial baselines on held-out synthetic layouts.
- Find individual CAD, load, actuator, fabrication and kinematics studies with the [engineering documentation index](../docs/README.md) and [evidence index](docs/desktop-evidence-index.md).
- Use [nextSteps.md](../nextSteps.md) for current decisions and the [desktop record](../docs/arm01-desktop-run-2026-11-11.md) for historical native evidence.
