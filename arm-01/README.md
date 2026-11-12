# ARM-01 — BenchSort

BenchSort is RAFTEL's first stationary manipulation project. Proposed targets are six independent arm joints plus a parallel gripper, approximately 350–450 mm reach, 100–200 g payload, three destination boxes, and variable source-object positions. Liam has superseded the initial seven-total-actuator target with an allowance of up to eight actuators and asked us to study Thor first: its six arm axes use seven arm motors, including a coupled shoulder drive, plus a gripper motor. This is a CAD and feasibility study; final hardware selection, fabrication and purchases remain unapproved. A removable mount should support later integration with a mobile platform; building that platform is outside the current scope.

**Sorting runtime: logical task simulation.** Synthetic observations drive a mock arm through selection, grasp, placement, and outcome handling. Its reach envelope and waypoint checks do not prove that any physical arm can execute those motions. The sorter has no camera, IK, collision checker, physics simulator or hardware driver.

Separate offline engineering tools now provide nominal spatial frames/Jacobians, bounded local IK, declared-study trajectories, saved-zero box-pair screening, conditional loads and authenticated printed-copy inertia. These tools do not execute sorter motions or qualify physical paths. The [desktop evidence index](docs/desktop-evidence-index.md) maps implemented studies to their artifacts, checks and remaining gates; [nextSteps.md](../nextSteps.md) records current validation and publication.

The [desktop run record](../docs/arm01-desktop-run-2026-11-11.md) records the current 2,200-test implementation, refreshed offline wheel, native evidence scopes and pending live Anycubic inspection. The run was wrapped at the owner's request; no continuing background work is implied.

The later [thirty-agent nightly checkpoint](../docs/arm01-swarm-checkpoint-2026-11-11.md) records direct Art1 attachment/return diagnostics and a verified imposed nonzero wrist experiment. Live Anycubic import/save remains unfinished. All lanes stopped at the owner's request.

## Setup

Use Python 3.11 or newer. From this directory on macOS, Linux, or WSL:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.lock -e '.[dev]'
```

For native Windows, create the environment with `py -3 -m venv .venv` and activate it in PowerShell with `.venv\Scripts\Activate.ps1`, then run the same `python -m pip` command. Linux, macOS, native Windows, and WSL are intended portable environments for the standard-library core; only platforms actually run in a session may be reported as verified in [nextSteps.md](../nextSteps.md).

## Demonstrate repeatable sorting

```sh
raftel-sort --help
raftel-sort --seed 42 --count 10
raftel-sort --seed 42 --count 10 --log sorting-events.jsonl
raftel-sort --seed 42 --unreachable
raftel-sort --seed 42 --fail-grasp object-00
```

The seed controls synthetic object positions. The final two commands deliberately exercise exceptional outcomes; read their structured events and summary rather than counting every detected object as successfully sorted. Exit status `0` means no failed objects or task abort; skipped objects are allowed. Status `1` means a failed object or abort, and `2` means invalid configuration/input or a file error. Check `sorted`, `skipped`, `failed`, `pending`, and `aborted` in the summary rather than treating status `0` as proof that every object was sorted. `--config path/to/config.json` selects an alternate structured configuration. Inspect [`src/raftel_arm01/defaults.json`](src/raftel_arm01/defaults.json) for the packaged three-bin example and the CLI help for supported arguments.

On an abort, `pending` counts observations not attempted; the failed object is separate.

Pickup positions come from synthetic object observations, not a fixed list of hardcoded pickup locations. Bin positions and initial scenario bounds are configured. Grasp and placement are logical abstractions; a successful mock placement is not an observed physical result.

## Validate locally

```sh
python -m pytest
ruff check .
ruff format --check .
python -m compileall -q src
raftel-sort --seed 42
python tools/engineering_analysis.py
python tools/thor_load_analysis.py --cad-inventory hardware/cad/thor-mounted-geometry.json
```

Tests should require no hardware or ROS. The analysis script reproduces explicitly assumed static loads and geometric mobile-reach checks; it is not a dynamics model or a certification of actuator or mount suitability. Current executed results belong in [nextSteps.md](../nextSteps.md), including any skipped platform checks.

## Architecture and next integrations

The [architecture](docs/architecture.md) keeps observations, planning, task execution, and arm control separate. The first prototype intentionally has no runtime dependency on robotics middleware. NumPy/OpenCV, a measured robot model/URDF, ROS 2 Jazzy, MoveIt 2, LeRobot, and a physics environment are possible integration milestones, each requiring its own installation and acceptance tests.

The [compatible assembly](docs/thor-assembly-compatibility.md), [geometry/axis study](docs/thor-geometry.md), and [CAD-derived conditional loads](docs/thor-load-analysis.md) establish the current analytical baseline. A separate static Art1 snapshot preserves the published shape; the original procedural history is not repaired. Nominal source FK is available but is not connected to the mock sorter or physical hardware. The [corrected518-leaf inventory](docs/thor-geometry-completeness.md) supersedes the earlier516-leaf baseline by adding two omitted wrist belts. The revised [load study](docs/thor-load-analysis.md) uses source-supported ideal handedness and explicit moving-mass assumptions; full physical loads remain unqualified. The [controller audit](docs/thor-controller-compensation.md) establishes the pinned pipeline has no elbow carrier compensation; tested offline physical-coordinate utilities remain separate from commands.

The [Thor joint/motor map](docs/thor-joint-map.md) documents paired shoulder and differential wrist drives. A tested pure coordinate utility implements the pinned ROS convention; it does not establish physical calibration or spatial kinematics. The [Thor cost study](hardware/thor-cost-study.md) separates current listing subtotals from missing-cost allowances.

The [jaw model](docs/thor-gripper-kinematics.md), [actuator feasibility checkpoint](docs/thor-actuator-feasibility.md), [dimensioned fabrication plan](docs/thor-fabrication-gate.md) and [Art1 editability gate](docs/thor-art1-editability-gate.md) record the next design evidence and source defects.

The [Windows native foundation](docs/thor-windows-native-foundation.md) records the isolated portable runtime and preserved source copies. [Printed-copy frame authentication](docs/thor-printed-inertia-study.md) covers a conditional 65-copy printed subset, while [Art1 semantic support observations](docs/thor-art1-semantic-supports.md) distinguish current typed attachment targets from raw face/edge indices. [Full-print mesh review](docs/thor-full-print-mesh-audit.md) prepares generic inspection drafts; actual slicer inspection, process/fit qualification and fabrication release remain separate.

The mechanical direction is to adapt an existing, demonstrated design where licensing and editable source allow it, starting with a Thor CAD study. Extract and validate its actual geometry, mass, gripper mechanism, drive mapping and cost before proposing changes; upstream physical demonstrations do not verify RAFTEL performance. The reach, payload and budget targets remain unchanged and unverified. Stock SO-101 has five arm axes plus its gripper and does not satisfy the six-arm-axis requirement. Read the [CAD reuse plan](docs/cad-reuse.md) and [selection ADR](../docs/architecture-decisions/0001-mechanical-starting-point.md) before selecting or printing parts.

Do not energize an unverified arm or power system. See [safety](docs/safety.md), [workstation](docs/workstation.md), and the [candidate BOM](hardware/bom.md). Nothing in this repository is evidence that a household-safe robot has been built.
