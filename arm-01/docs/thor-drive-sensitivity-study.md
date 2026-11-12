# Declared drive sensitivity study

This offline study fills a gap between the existing gravity sensitivity report,
ideal coupled rate map and single-point elbow load calculation. It varies
effective drum radius, moving gearbox efficiency and paired shoulder allocation
without changing those models or their historical reports. The new request is
`config/thor-drive-sensitivity-v1.json`; the deterministic candidate report is
`hardware/cad/thor-drive-sensitivity-study-v1.json`.

The report contains 63 explicitly selected numerical samples: nine parameter
points crossed with seven instantaneous operating points. It does not search a
continuous envelope or certify the endpoints of an uncertainty range. The radius
samples 30, 37 and 45 mm are unmeasured effective pitch radii, not CAD outer radii
or manufacturing dimensions. Efficiencies 0.6, 0.8 and 1.0 are declared moving
two-port assumptions. Shoulder B allocation 0, 0.5 and 1 is a chosen distribution
of branch output effort, not evidence that two motors balance that way. Two
combined parameter points expose interactions; the matched reference contrasts
vary exactly one named axis.

## Mechanical convention

The bound source is `hardware/cad/thor-scenario-study-v1.json`, specifically its
`shoulder_horizontal_saved` row. Its `required_ideal_holding_torque_nm` values are
required gravity-compensating **countertorques**, not gravity-applied torques:
`t2 = -5.843128346682769 N*m` and `t3 = -2.3498756418312166 N*m`. They are used
unchanged as instantaneous demands at hypothetical nonzero rates. This is a
quasi-static gravity contribution; inertia, startup, friction and full dynamic
actuator demand are absent. None of the declared rates are motion instructions,
collision checks, trajectory feasibility or measured calibration.

The existing `ElbowTransmission` defines `k = R/r`, belt sign `s`, carrier
coupling `c`, shoulder gearbox ratio `Ns` and elbow gearbox ratio `Ne`:

```text
thetaB_dot = thetaC_dot = Ns*q2_dot
thetaE_dot = Ne*(c*q2_dot + s*k*q3_dot)
TE = t3/(s*k)
TS = t2 - c*TE
TB = beta*TS; TC = (1-beta)*TS
```

Each gearbox output port uses its own effort and rate: `(TB,q2_dot)`,
`(TC,q2_dot)` and `(TE,c*q2_dot+s*k*q3_dot)`. These preserve output virtual work:
`TB*q2_dot + TC*q2_dot + TE*(c*q2_dot+s*k*q3_dot) = t2*q2_dot+t3*q3_dot`.
The carrier contribution is `c*TE`, based on the elbow gearbox **output** effort.
It must not be recomputed from the loss-scaled input effort using a lossless
transpose map.

For each independent gearbox, `Pout = Tout*omega_out` and
`omega_in = N*omega_out`. The existing `signed_lossy_input_effort` is reused:

| Declared flow | Required input effort | Modeled mechanical loss |
| --- | --- | --- |
| `Pout > 0`, motoring | `Tout/(N*eta)` | `Pout*(1/eta-1)` |
| `Pout < 0`, backdriving | `eta*Tout/N` | `Pout*(eta-1)` |

Input and output use the same positive shaft coordinate convention; backdriving
input mechanical power is negative. Negative input power does not qualify a
driver, electrical regeneration path, braking circuit or battery acceptance.
The report checks `Pin = Pjoint + sum(loss)` and retains the floating residual.
The belt/carrier stage is lossless in this declared model. Its sign conventions
and gearbox hypotheses have not been calibrated on hardware.

A nonzero output effort at zero port rate has **unknown input effort**, reported
as `null`; moving efficiency is not applied. Mechanical shaft power is zero,
while holding copper loss, frictional equilibrium, self-locking, heating and
thermal capacity remain unmodeled. Zero transmitted effort is explicitly a zero
contribution in this partial model, including a shoulder branch allocated zero
share. That does not prove a real energized motor draws zero current. Unrepresentable
nonzero input rates, efforts or powers are rejected rather than silently becoming
known zero values.

## Sampled results

The same source mass summary is copied without adding, removing or reweighting
any records: 518 native leaves, 517 mass records, seven whole motors totaling
2.120 kg, and modeled whole-arm mass 5.6547224855756 kg. Raw and canonical source
hashes, pinned CAD/ROS revisions, source class/SI units/qualification flags,
source case hashes, semantic request hash and executed model/tool byte hashes
are retained. These authenticate the declared report inputs; they do not turn
the underlying mass or geometry hypotheses into measurements.

| Input port | Maximum absolute known sampled effort, N*m | Witness parameter point | Unknown static samples |
| --- | ---: | --- | ---: |
| B | 0.286597450018833 | 30 mm, efficiency 0.6, all shoulder effort to B | 14 |
| C | 0.21874236480542295 | 37 mm, efficiency 0.8, all shoulder effort to C | 14 |
| E | 0.16044372546060848 | 30 mm, efficiency 0.6, all shoulder effort to B | 9 |

All three witnesses use `negative_rates`, `q2_dot=q3_dot=-0.05 rad/s`.
The C witness differs from the B witness because the sparse caller list does
not contain every combined corner. These are maxima among known sampled partial
efforts; unknown static cases are counted and never replaced by zero or bounded
by these maxima. Different port extrema need not occur together. Capacity
margins remain `null`.

At the reference point, reversing `[+0.05,+0.05]` to `[-0.05,-0.05]` changes
modeled total input mechanical power from -0.3277201595405595 W to
+0.5120627492821241 W for opposite gravity-power directions. The declared
`joint_power_cancellation` rate pair gives zero net joint power but nonzero
opposite port flows, +0.12237322856674576 W input power and
0.12237322856674579 W modeled loss. Applying one efficiency to net joint power
would miss this loss. This is an algebraic witness, not an observed motion.

## Reproduction and next evidence

From `arm-01`, use a **new output path**:

```powershell
.venv\Scripts\python.exe tools\thor_drive_sensitivity_study.py config\thor-drive-sensitivity-v1.json --output ..\.work\drive-sensitivity-new.json
.venv\Scripts\python.exe -m pytest tests\test_thor_drive_sensitivity_study.py tests\test_thor_elbow_loads.py tests\test_thor_transmission.py -q
.venv\Scripts\ruff.exe check tools\thor_drive_sensitivity_study.py tests\test_thor_drive_sensitivity_study.py
```

Output uses exclusive creation and LF newlines. Existing evidence cannot be
overwritten through this CLI; an I/O failure may leave a partial new output.
The exact-byte candidate reproduction test includes all model byte pins.
Inputs reject duplicate keys, nonfinite values, invalid booleans, schema/units,
stale source bytes, excessive sample products, missing evidence and ambiguous
point identities. A coherently rebound source must still satisfy its nominal
frame, revisions, units, whole-motor identities and conditional qualification
flags. Source symlinks and paths outside the selected project are rejected.

Next executable work is to (1) measure or otherwise justify effective belt pitch
radius and carrier signs using an approved evidence procedure, (2) obtain
direction-specific gearbox and paired shoulder sharing evidence at declared
nonzero ports, and (3) add separately justified inertia/duty/thermal and
electrical regeneration models before comparing with rated capacity. Current
gates remain unresolved; no native CAD, hardware, network, motor command,
fabrication or release action is performed by this study.
