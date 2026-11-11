# ARM-01 verification plan

Tests must show which claim was checked, with what configuration and evidence. Record executed commands, results, limitations and unavailable checks in [nextSteps.md](../../nextSteps.md). Preserve failures in run records; do not turn skipped or unreachable objects into successes.

## Initial software acceptance

From an isolated Python environment in `arm-01`:

```sh
python -m pip install -r requirements-dev.lock -e '.[dev]'
python -m pytest
ruff check .
ruff format --check .
python -m compileall -q src
raftel-sort --seed 42 --count 10
raftel-sort --seed 42 --unreachable
raftel-sort --seed 42 --fail-grasp object-00
python tools/engineering_analysis.py
```

Expected coverage:

- Valid three-bin configuration and rejection of invalid/non-finite or inconsistent inputs.
- Repeatable scene positions and outcomes for the same seed; changed layouts when seeds change.
- Correct category-to-bin routing without fixed pickup positions.
- Position/payload screening and boundary conditions.
- Failed-grasp handling, unreachable-object outcomes, and honest success/failure summaries.
- Backend failures do not silently become completed placements or permit unbounded retries.
- Structured event output is parseable and corresponds to task outcomes.
- Installed CLI and dependency-light package operation without hardware or ROS.
- Analytical load/floor-reach equations checked against independent simple cases.

CI should install the Python package and run unit/static checks plus a mock CLI smoke test. Record remote CI outcomes separately from local results. A configured workflow is not evidence of a passing remote run.

## Mechanical and electrical gates

| Claim | Evidence required before relying on it |
| --- | --- |
| Six independent arm axes and an allowed eight-actuator implementation | Thor-first source study, revisioned CAD joint tree, explicit mapping from seven arm motors (including coupled shoulder drive) to six arm coordinates plus separate gripper motor; independent powered tests after safe commissioning |
| Reach/orientation coverage | Joint-limited model, collision geometry, sampled task poses, measured endpoint checks |
| Payload and duty | Full downstream mass/COM calculation; actuator curves; supervised thermal/current/deflection tests across limiting poses |
| Rigid removable mounting | Reviewed load path, desk/clamp compatibility, fastener/preload details, restrained static test and repeatability after remount |
| Electrical compatibility | Exact model/variant datasheets, voltage and pinout checks, bus type, wire/connector/current ratings, fuse coordination |
| Fault protection | Safe start/calibration, stale feedback, communications loss, overcurrent/thermal, independent E-stop and gravity-collapse tests |

The eight-actuator allowance supersedes the original seven-total-actuator target; it does not establish Thor geometry, gripper parallelism, budget fit or suitability. Study the existing source before proposing fabrication. The exact test fixtures, stop conditions and safe loads must be reviewed before physical testing. Do not energize an unverified assembly to collect evidence.

## Vision and manipulation gates

Measure camera intrinsic/extrinsic calibration errors and validate camera-to-base transforms using known points. Hold out calibration/check points. Report pose error throughout the intended workspace, including occlusion and lighting conditions. Then evaluate grasp retention, transport and bin release separately before an end-to-end test.

The end-to-end physical benchmark should predeclare object set, masses/sizes, source/bin regions, lighting, camera settings, trial seeds/layout generation, permitted retries, timeout, and safety-stop rules. Use variable positions and log detected, eligible, attempted, successfully sorted, failed, unreachable, and human-assisted objects.

## Proposed 90% target protocol

Run at least ten independently reset ten-object layouts (100 presented objects) after commissioning. This is an initial benchmark size, not a reliability certification. Report:

- **Cycle success:** independently verified correct-bin placements divided by attempted object cycles; report first-attempt and after-permitted-retry results separately.
- **Coverage:** eligible/attempted objects divided by presented objects, with exclusions and unreachable objects listed.
- **End-to-end completion:** correct placements divided by presented eligible objects, including detection misses and timeouts.
- Trial-level completion, elapsed time, interventions, drops, misroutes and safety stops.

Target at least 90% observed successful physical cycles in the predefined operating envelope; include a binomial confidence interval and trial-level results. For example, 90/100 is an observed 90%, not proof that the underlying success probability exceeds 90%. Account for correlated objects within the same layout when interpreting uncertainty. Never substitute logical mock statistics for these measurements.

## Platform and integration checks

Record actual Python/OS versions tested. Intended macOS, Linux and Windows/WSL portability is not a cross-platform result until exercised. ROS, MoveIt, camera, IK, physics, CAD fit, mount strength and physical manipulation remain unverified until their specific setup and tests run; document the exact next prerequisite instead of marking them passed.
