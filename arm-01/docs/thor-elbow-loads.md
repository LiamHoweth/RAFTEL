# Thor remote elbow loads

This is a conditional, lossless analytical transmission model. It consumes the CAD-derived static joint demands in `hardware/cad/thor-load-study.json`. It does not qualify a motor, belt, printed part, safe payload, pretension or moving performance.

## Geometry and coordinates

The pinned Thor assembly places the elbow PG5 motor on Art1; its shaft is nominally coaxial with the shoulder. The open GT2 belt runs through the Art2 carrier to the smooth Art3 drum. Native cached geometry supports an uncrossed, same-sense route. The input datum is within approximately 0.0004 mm of the nominal shoulder axis; this is CAD alignment evidence, not a physical alignment measurement. The belt model has schematic idler contacts and open ends; clamp details, actual wrap and slip remain unresolved. See the companion elbow mechanism evidence for extraction details.

Let `q2` be shoulder rotation and `q3` be elbow rotation relative to Art2. Let `phi` be elbow gearbox output rotation relative to Art1. In the ideal coaxial, constant-radius no-slip carrier model:

```
k = R_pitch / r_driver_pitch
phi = c*q2 + s*k*q3
(theta_B, theta_C, theta_E) = (N_s*q2, N_s*q2, N_e*phi)
```

Here `c=1` and `s=+1` are the geometry-supported candidate; the tool requires callers to specify both. These are declared physical angle conventions, not GRBL address commands or calibrated motor wiring signs. A route whose belt path changes with pose may require a pose-dependent Jacobian; constant `c` is an assumption. The 20-tooth, 2 mm pitch driver has nominal pitch radius `20*0.002/(2*pi) = 0.00636620 m`. `N_e=5.18` and `N_s=6*5.18=31.08` use supplier nominal PG5 ratio and the printed 60/10 shoulder reduction.

The saved drum body radius is 37 mm and the cached belt envelope extends to 38.5 mm. Neither is a calibrated effective pitch radius. Treating pitch as lying inside that envelope is a separate sensitivity assumption, not an established physical bound.

## Effort transpose and redundant shoulder branches

With `theta_dot = J*q_dot`, virtual work requires `tau_joint = Jᵀ*tau_rotor`:

```
J = [[N_s, 0], [N_s, 0], [N_e*c, N_e*s*k]]
tau_E = tau3 / (N_e*s*k)
shoulder_branch_total = tau2 - c*tau3/(s*k)
tau_B = lambda*shoulder_branch_total/N_s
tau_C = (1-lambda)*shoulder_branch_total/N_s
```

The remote elbow drive therefore also contributes a shoulder effort. Dividing `tau2` equally between shoulder motors before including this carrier reaction omits a term. `lambda` is an explicit scenario input in 0..1; equal current, step commands or identical motors do not establish equal physical torque sharing. The model excludes preload/circulating internal torque between shoulder branches, which could make individual branch demands exceed the lambda scenarios.

## Reproduced CAD load case

For the illustrative 50% whole-part PLA density factor, shoulder-horizontal pose and 0.2 kg payload, the committed CAD study gives ideal static holding demands `tau2=-5.827993 N·m` and `tau3=-2.342324 N·m`. Printed masses, hardware mass estimates, payload location and upstream CAD assumptions remain those of the source study.

The following values are demands under `c=1`, `s=+1`, nominal gearbox ratios and the stated pitch assumption. Signs follow the declared coordinates.

| Conditional scenario | Elbow rotor E | Elbow gearbox output | Shoulder branches total at joint | Each shoulder rotor, only if 50/50 | Belt tension difference magnitude |
| --- | ---: | ---: | ---: | ---: | ---: |
| `R_pitch=37 mm` endpoint scenario | -0.077803 N·m | -0.403019 N·m | -5.424974 N·m | -0.087274 N·m | 63.306 N |
| `R_pitch=38.5 mm` envelope sensitivity | -0.074772 N·m | -0.387317 N·m | -5.440676 N·m | -0.087527 N·m | 60.840 N |

If one shoulder branch supplies the whole residual, that branch's ideal demand doubles relative to the table's 50/50 assumption. This is a load-sharing scenario, not proof of fail-operational behavior. These values are not margins against rated capability.

## Belt loads and loss direction

With all elbow joint torque transmitted tangentially at the assumed pitch circle, oriented span difference is `T_plus-T_minus=tau3/R_pitch`, where positive resultant produces positive `q3` torque. Its magnitude is tight minus slack. A symmetric mean span tension must be at least half that magnitude merely to keep both spans nonnegative. This is not a pretension recommendation: clamp security, teeth engagement at the driver, smooth-drum slip, belt strength, actual wrap, tensioner reactions, bearing radial forces and printed drum strength require separate evidence. Summing scalar tensions does not establish the bearing load vector. No capstan friction coefficient or continuous-belt traction model is invented for this open-ended belt.

Static holding has zero velocity and zero mechanical power; a quoted efficiency cannot establish its friction or holding limit. `signed_lossy_input_effort` is a separate two-port sensitivity utility with explicitly selected power direction: motoring uses `tau_out/(N*eta)`; backdriving uses `eta*tau_out/N`. It does not automatically apply losses to the coupled static map. Motion analysis still needs per-port velocities, inertia/acceleration, friction, belt compliance, cable loading, speed-dependent motor torque, drive current and thermal duty. Supplier bare holding torque, gearbox permissible output and momentary output are different limits and do not establish continuous moving capacity.

## Reproduction and checks

From `arm-01`, the committed report is reproducible with the following explicit assumptions (use a new output path; the CLI refuses overwrite):

```sh
python tools/thor_elbow_loads.py --load-study hardware/cad/thor-load-study.json \
  --drum-pitch-radius-mm 37 --carrier-coupling 1 --belt-sign 1 \
  --shoulder-b-fraction 0.5 \
  --geometry-evidence 'Conditional CAD body-radius endpoint; pitch radius unmeasured; coaxial open-belt carrier and 50/50 shoulder split assumed; see docs/thor-elbow-mechanism.md and docs/thor-elbow-loads.md' \
  --output hardware/cad/thor-elbow-loads.json
```

The JSON hashes its input load study, stores all assumed transmission parameters and explicitly marks physical pitch, sharing, traction and motor capacity unqualified. Tests cover seeded random virtual work for both signs and several carrier coefficients, coordinate inverse and finite-difference carrier derivatives, known carrier reaction, explicit shoulder-sharing endpoints, power direction, input/overflow/underflow validation, and the committed CAD baseline.
