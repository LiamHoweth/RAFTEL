# Offline scalar joint trajectories

This separate T1 tool builds **nominal joint-coordinate numerical paths**
under explicit study limits. It follows the [frame/Jacobian/IK
checkpoint](thor-spatial-kinematics.md), but does not integrate IK, collision
checking or a backend. The logical sorter and its point-envelope semantics
remain unchanged. A generated path is not permission for motion.

## Required inputs

`plan_quintic_path(waypoints,constraints,...)` accepts 2–1000 waypoints of six
nominal source joint angles in radians. It uses `ConstraintSet`'s **study**
bounds only. Every study joint must explicitly provide positive velocity and
acceleration limits with evidence. The baseline
[source/study constraints](../config/thor-constraints-v1.json) intentionally
contain no acceleration limits, so the planner rejects them until a caller
supplies an explicit separate study. It never fills unknown acceleration from
a source velocity, holding torque, motor label or guessed hardware rating.

`tools/thor_trajectory_study.py` requires a separate rate-study JSON file. It
accepts `synthetic` or `assumed` evidence and a study revision. For example,
this is a **synthetic numerical fixture**, not recommended physical settings:

```json
{
  "schema_version": 1,
  "revision": "synthetic-example-v1",
  "units": {"velocity": "rad/s", "acceleration": "rad/s^2"},
  "evidence_class": "synthetic",
  "evidence": "Numerical fixture only; physical capacity is unknown",
  "velocity_limits_rad_s": [0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
  "acceleration_limits_rad_s2": [0.2, 0.2, 0.2, 0.2, 0.2, 0.2]
}
```

The tool preserves the source position box, creates a separate study value
with the supplied rates, and retains the original source/calibrated records.
No file in `config/` is modified. Source velocity bounds still bound the
numerical study; they do not become calibrated physical limits.

## Quintic construction and exact derivative checks

Each segment starts and ends at rest. For duration T, local time t and
u=t/T in [0,1], the interpolation is

```text
s(u) = 10u^3 - 15u^4 + 6u^5
q(t) = q0 + (q1-q0) s(u)
dq/dt = (q1-q0) 30u^2(1-u)^2 / T
d2q/dt2 = (q1-q0) 60u(1-u)(1-2u) / T^2
```

The exact per-axis absolute maxima are

```text
peak speed        = (15/8) |q1-q0| / T
peak acceleration = (10 sqrt(3)/3) |q1-q0| / T^2
```

Speed peaks at u=1/2. Acceleration magnitude peaks at
u=(3±sqrt(3))/6. The planner computes the duration needed for **both** maxima
on every axis, then takes their maximum and an explicit positive minimum
segment duration. If the caller supplies durations instead, the planner
checks those exact analytic peaks. It does not substitute sampled peaks for
an intersample derivative bound. Comparisons allow only 1e-12 relative
arithmetic tolerance, not a physical margin. Computed durations round upward
by one representable float at the limiting numerical boundary.

The interpolation is monotonic between each pair of scalar endpoints, so
endpoints inside the study position box keep that whole scalar segment
inside the same box. Near an endpoint, a symmetric polynomial and numerical
interval clipping avoid tiny floating-point overshoot of the mathematical
endpoint interval. This scalar property is not collision clearance.

Concatenation shares exact waypoints and has zero velocity and acceleration
on both sides. The resulting path is C2 and pauses at every waypoint. Jerk
can jump at a boundary; no jerk bound or continuous-through waypoint blending
is claimed. No Cartesian straight line, branch continuity, motor-current or
dynamic-capacity statement follows from a scalar joint polynomial.

## Work bounds and sampling

The planner rejects out-of-box waypoints, nonfinite inputs, missing required
limits, inconsistent requested durations and paths exceeding an explicit
total duration budget (default 300 s of **modeled time**, not executed time).
The path contains at most 999 segments. Timeline boundaries use compensated
sums; segment durations too small to resolve on the cumulative floating-point
timeline fail instead of creating ambiguous time intervals.

`TimedJointPath.sample(t)` returns time, six angles, six velocities and six
accelerations. Times outside the modeled path fail; they are not extrapolated
or silently clamped to a different path. `sample_uniform(period,max_samples=...)`
adds the exact final endpoint, and rejects a sample count beyond the explicit
budget (default 10,000, permitted maximum 100,000). Positive sample spacing
does not establish collision or rate feasibility for coupled transmissions.

## Reproduction

With the explicit rate fixture saved to a new scratch file, run from an
installed environment in `arm-01`:

```powershell
python -m pytest tests/test_thor_trajectory.py
python tools/thor_trajectory_study.py --rate-study /path/to/synthetic-rates.json --output new-trajectory-study.json
```

Without `--waypoints`, the tool uses a labeled three-waypoint numerical
example. To supply points, provide a JSON object with exactly
`schema_version: 1`, `model_source_revision:
"e11a56b5aa0d89f0b68a3ea7bd084eab4a050952"`, `joint_order:
["joint_1","joint_2","joint_3","joint_4","joint_5","joint_6"]`, `units:
"rad"` and `waypoints_rad: [[...six values...], ...]`.

The report binds source revision, constraints/rate-study/waypoint hashes,
explicit rate assumptions, segment durations, analytic maxima and sampled
states. It carries `offline_scalar_joint_path_not_collision_dynamics_or_hardware_validation`
as its evidence class. Existing report paths are never overwritten. CLI
input/provenance failures produce a nonzero result; no serial/device output,
real-motion flag or hardware backend exists.

Tests compare derivatives to independent central differences, check extrema
at their analytic witness times and against dense samples, validate C2
boundaries, exercise source-box endpoint roundoff, and reject unknown limits,
unbounded sample requests, stale/wrong units and invalid evidence classes.
The native CAD geometry, cable/gear interference, coupled shaft rates,
actuator/dynamic demand, payload retention and physical execution remain
separate unresolved gates.
