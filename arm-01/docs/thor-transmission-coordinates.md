# Physical and source transmission coordinates

[`thor_transmission.py`](../src/raftel_arm01/kinematics/thor_transmission.py) evaluates explicitly declared ideal physical coordinates. The existing [`thor_drive.py`](../src/raftel_arm01/kinematics/thor_drive.py) continues to reproduce the pinned Thor-ROS nominal continuous channel algebra unchanged. These are different layers: neither module emits commands, chooses wiring polarities or calibrates motor steps. Angles are radians; conjugate efforts are N·m.

## Elbow: a relative joint and a normalized drive proxy

The [elbow mechanism evidence](thor-elbow-mechanism.md) supports the conditional local relation

```text
phi = c*q2 + s*K*q3
K = effective_drum_pitch_radius / input_pulley_pitch_radius
```

Here `q2` is shoulder angle relative to Art1, `q3` is elbow angle relative to Art2, and `phi` is the remote gearbox-output angle relative to Art1. Coaxial, fixed-routing, no-slip geometry gives the candidate `c=1`. `s` is an explicit routing sign; `K` requires an actual effective pitch radius. The module requires these quantities and gearbox/shoulder ratios rather than silently choosing a calibrated mechanism.

The `ElbowTransmission` class previously defined in the elbow analysis tool now lives in the core module; the tool imports the same class, retaining its public imported name, reports and CLI. Its coordinate inverse and virtual-work effort transpose still include shoulder reaction. The tool's static report output is unchanged.

To compare with an uncoupled elbow coordinate, define the dimensionless angular proxy

```text
d = phi/(s*K) = q3 + c*q2/(s*K)
q3 = d - c*q2/(s*K)
```

`elbow_proxy_coordinate(q2,q3)` and `relative_elbow_from_proxy(q2,d)` evaluate those equations. They do not identify `d` with a source GRBL address. That comparison additionally assumes an independently calibrated diagonal address-to-output scale. Under that explicit hypothesis, the source's normalized negative elbow address would need the shoulder term as well as the relative elbow angle. The [controller audit](thor-controller-compensation.md) traces whether such a term exists in the inspected source chain; the math module does not alter that chain.

If an otherwise calibrated diagonal drive holds `d` fixed while the shoulder changes by `delta_q2`, the conditional relative-elbow error is `-c*delta_q2/(s*K)`. At the **illustrative**, unmeasured 37 mm effective drum pitch radius, nominal 20-tooth/2 mm driver pitch radius, `c=1`, `s=+1`, a 90° shoulder change gives approximately −15.485° relative elbow change. This is an analytical mismatch prediction, not a measured robot error or an instruction to operate the arm.

## Wrist: common shaft axes and opposed references

Both physical side angles use a common native +Y reference; roll uses carried native +Z:

```text
alpha_negative_y = q5 + h*r*q6
alpha_positive_y = q5 - h*r*q6
```

`WristDifferential` requires bevel magnitude `r`, handedness `h` of ±1, both signed rotor/side-angle scales and an evidence or assumption string. No default selects a physical sign. The [handedness study](thor-wrist-handedness.md) owns the geometric evidence and its mesh limitations. The existing [membership study](thor-wrist-mechanism.md) owns component motion; this algebra does not by itself validate conjugate contact or moving masses.

Pure fold has both side shafts turning by `q5` about common +Y. The source formula `Y=-q5+2*q6`, `Z=q5+2*q6` instead uses opposed coordinate references. With `r=2`, it can be reproduced in two ways:

| Declared common-axis handedness | Negative-reference coordinate Y | Positive-reference coordinate Z |
| --- | --- | --- |
| `h=+1` | `-alpha_positive_y` | `alpha_negative_y` |
| `h=-1` | `-alpha_negative_y` | `alpha_positive_y` |

`opposed_references(q5,q6,y_side)` requires that side assignment explicitly. The method returns an abstract coordinate pair; selecting the row is not proof of which actual motor cable or source address drives that physical side. Signed belt stages must be reconciled separately. Treating both source Y/Z values as positive common-axis side angles fails pure-fold consistency.

`side_angles` and `joint_angles` are inverses. `rotor_angles` includes the two caller-declared signed scales, while `joints_from_rotors` inverts them. `joint_efforts` implements the transpose of that same rotor-angle Jacobian; `rotor_efforts` inverts it. Consequently joint and rotor virtual power agree for the declared lossless mechanism. No efficiency, speed-dependent torque, belt slip, backlash, preload, physical zero or capacity follows from this identity.

## Verification and scope

Tests check both handedness alternatives, pure-fold consistency, explicit opposed side assignment, seeded randomized angle/effort inverses and virtual power, finite-difference rotor velocities, carrier compensation and proxy inverses. Invalid evidence, zero scales, nonfinite values and machine-precision singularities are rejected. Existing elbow load tests continue to exercise the imported class and committed baseline.

This module is an offline analytical utility. It supplies no serial API, motion backend, arming, collision checks, safe limits or physical performance claim. Source inspection and ideal geometry can establish a mathematical discrepancy while physical pitch/sign calibration and installed firmware remain open.
