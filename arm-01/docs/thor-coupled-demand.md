# Offline coupled rate and acceleration demand

[`thor_coupled_demand.py`](../src/raftel_arm01/control/thor_coupled_demand.py)
projects declared joint coordinates, rates and accelerations through the
existing constant transmission maps. It implements C6's offline projection and
exact linear study-box extrema. It does not establish motor capacity, physical
shaft limits, dynamics or a complete actuator-demand package.

Three coordinate families stay separate:

| Family | Meaning |
| --- | --- |
| Continuous source A,B,C,D,X,Y,Z | The pinned continuous [`thor_drive.py`](../src/raftel_arm01/kinematics/thor_drive.py) channel convention, in radian coordinates; not raw motor angles |
| Conditional shoulder B/C and elbow E rotors | The declared [`ElbowTransmission`](../src/raftel_arm01/kinematics/thor_transmission.py) with an explicit carrier coefficient, pitch-radius ratio, signs and gearbox ratios; not source D/Z coordinates |
| Conditional negative-Y/positive-Y wrist rotors | The declared `WristDifferential` with explicit handedness and signed rotor scales; not source Y/Z coordinates |

The source's **quantized integer command conversion** has no smooth derivative
here. It remains in the [source conversion/replay study](thor-controller-replay.md).
The conditional maps describe shaft coordinates relative to their declared
references, not the total spatial angular velocity of a rotor carried by a
moving link. Joint 1, joint 4 and gripper physical transmission demands remain
unmodeled. The source/mechanism mismatch is not silently corrected.

## Motion and constraints

`project_motion` reuses the existing offline `TimedJointState` from
[`thor_trajectory.py`](../src/raftel_arm01/kinematics/thor_trajectory.py): time,
six joint radians, six joint rad/s and six joint rad/s². It requires a
`ConstraintSet` with **explicit study velocity and acceleration bounds plus
evidence on every axis**, checks the supplied position/rates against those
bounds, and rejects missing/violating inputs. The tracked source/study baseline
has unknown accelerations; that baseline alone is rejected.

For a constant linear map `theta = J*q`, the projected derivatives are:

```text
theta_dot = J*q_dot
theta_ddot = J*q_ddot

elbow_E_dot = N_elbow * (carrier*q2_dot + belt_sign*K*q3_dot)
wrist_minus_dot = signed_scale_minus * (q5_dot + handedness*r*q6_dot)
wrist_plus_dot = signed_scale_plus * (q5_dot - handedness*r*q6_dot)
```

The same relations apply to acceleration under the **constant local routing,
radius and ratio assumptions**. A pose-dependent radius, changing ratio,
compliance, backlash or slip requires a different model and additional terms.
These scalar rates do not replace rigid-body angular Jacobians for dynamics.

Results bind scenario and constraint revisions, all six study evidence strings
and the complete declared transmission parameters. Mechanism scenarios must be
explicitly `assumed` or `synthetic`. They are never loaded as commissioned
controller settings.

## Exact independent-box extrema

`project_rate_boxes` constructs the constant map matrices using the existing
map implementations. For an independent symmetric input box `|q_dot_i| <= v_i`,
each output-row interval is:

```text
minimum_j = -sum_i(abs(J[j,i]) * v_i)
maximum_j = +sum_i(abs(J[j,i]) * v_i)
```

Acceleration uses the analogous explicit `a_i` bounds. Each row carries its
own minimizing/maximizing six-joint witness vector. Tests exhaustively compare
the intervals to all 64 box corners and evaluate those witnesses directly.
“Exact” means the analytical linear-box extrema, subject to floating-point
arithmetic; these are not certified outward-rounded interval bounds.

Different rows generally have different witness states. A list of per-row
maxima is not a simultaneous operating point. The independent box also does
not encode trajectory compatibility, cable/contact limits, coupled feasible
regions, physical rates or motor capacity. A sampled T1 path is reported
separately; its samples do not prove intersample clearance or load extrema.

## Reproduction with explicit scenarios

The CLI reuses T1's `load_rate_study`, `load_waypoints` and path planner. It
requires a rate-study JSON and transmission-study JSON. Neither file overwrites
the tracked baseline. For a **synthetic example only**, save this as
`rate-study.json`:

```json
{
  "schema_version": 1,
  "revision": "synthetic-rate-example-v1",
  "units": {"velocity": "rad/s", "acceleration": "rad/s^2"},
  "evidence_class": "synthetic",
  "evidence": "Numerical example; not qualified physical limits",
  "velocity_limits_rad_s": [0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
  "acceleration_limits_rad_s2": [0.2, 0.2, 0.2, 0.2, 0.2, 0.2]
}
```

Save this separately as `transmission-study.json`. Its round-number ratios and
signed scales are synthetic fixtures, not measured Thor parameters:

```json
{
  "schema_version": 1,
  "revision": "synthetic-transmission-example-v1",
  "evidence_class": "synthetic",
  "evidence": "Numerical constant-ratio fixture; not calibrated shafts",
  "elbow": {
    "driver_radius_m": 0.01,
    "drum_radius_m": 0.05,
    "elbow_gearbox_ratio": 5,
    "shoulder_branch_ratio": 4,
    "carrier_coupling": 1,
    "belt_sign": -1
  },
  "wrist": {
    "bevel_ratio": 2,
    "handedness": 1,
    "negative_y_rotor_scale": -4,
    "positive_y_rotor_scale": 3
  }
}
```

Then run from the installed development environment in `arm-01`:

```powershell
python tools/thor_coupled_demand.py --rate-study rate-study.json --transmission-study transmission-study.json --box-only
python tools/thor_coupled_demand.py --rate-study rate-study.json --transmission-study transmission-study.json
python -m pytest tests/test_thor_coupled_demand.py
```

For those inputs the conditional elbow E absolute rate-box maximum is
`5*(0.1 + 5*0.1) = 3 rad/s`; acceleration maximum is 6 rad/s². The two wrist
maxima are 1.2 and 0.9 rad/s. These are scenario demands, not achievable or safe
motor ratings. The source D maximum remains 0.1 rad/s in its separate nominal
coordinate map, illustrating why source and conditional shaft values cannot be
interchanged.

Without `--box-only`, the report includes the existing labeled numerical T1
waypoints (or a supplied revisioned `--waypoints` file), sampled partial demands
and input byte hashes. `--max-samples` and duration bounds limit work. The tool
refuses to overwrite existing output evidence. Invalid/missing/unknown required
parameters, unsupported evidence states, duplicate transmission fields,
nonfinite values and overflowing results fail with exit 2.

## Validation and unresolved gates

Tests cover 100 seeded finite-difference rate/acceleration comparisons across
both signs/handedness alternatives, explicit joint/rotor virtual power, exact
corner extrema and witness states, simultaneous shoulder/elbow carrier demand,
T1 sample integration, source/study separation, unknown acceleration rejection,
overflow and deterministic/negative CLI paths. These verify declared linear
math and software contracts; they are not physical measurements.

The complete capacity margin remains null. Inertia, gravity/dynamic torque,
friction, efficiency, backlash, duty/thermal history, matching motor curves,
actual reference scales/zeros and calibrated shaft limits remain missing.
Source URDF scalar rates do not qualify physical motion. No controller command,
port, arming path, hardware backend or physical recovery behavior is added.
