# Thor joint and motor coupling map

**Status: read-only upstream source study, 2026-11-11.** This map separates six arm coordinates from seven arm stepper motors and the separate gripper actuator. It is evidence for software/model planning; no serial commands, hardware motion, calibration, native CAD recompute or physical measurements were performed for this study. It does not establish joint-axis positions or safe operating limits.

## Source revisions inspected

- [Thor native CAD and README, 286b081fe6f056d87c379b884781ef77ff6a0159](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159). Read `Document.xml` inside local `.FCStd`/`.fcstd` ZIP archives without modifying them.
- [Official firmware documentation](http://thor.angel-lm.com/documentation/firmware/), [BOM](http://thor.angel-lm.com/documentation/bom/), and [assembly documentation](http://thor.angel-lm.com/documentation/assembly/), accessed 2026-11-11. These live pages are not revision-pinned. HTTPS fetches failed in this study; HTTP pages were successfully retrieved and inspected as reference material.
- [Thor-ROS hardware interface, e11a56b5aa0d89f0b68a3ea7bd084eab4a050952](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_controller/src/thor_interface.cpp), particularly lines 164–171, 194–201 and 269–309.
- [Legacy Asgard, 30bf2f8850670f728a0f4c3e2e5d22db4f57d8c6](https://github.com/AngelLM/Asgard/blob/30bf2f8850670f728a0f4c3e2e5d22db4f57d8c6/asgard.py), especially `FKMoveArt2`, `FKMoveArt5`, `FKMoveArt6` and `FKMoveAll`.

## Six coordinates, seven stepper motors

Use neutral names `q1`…`q6` until coordinate frames have been validated. Thor's README describes the sequence as yaw–roll–roll–yaw–roll–yaw; those words do not define a transform tree or a world-axis convention.

| Arm coordinate | Upstream articulation | Arm motor number(s) in official GRBL documentation | GRBL address(es) | Coupling evidence |
| --- | --- | --- | --- | --- |
| `q1` | Articulation 1 | 1 | `A` | One channel for the first articulation. |
| `q2` | Articulation 2 / shoulder | 2 and 3 | `B`, `C` | Official instructions require equal `B` and `C` coordinates; Thor-ROS emits both from one `art2` value. |
| `q3` | Articulation 3 | 4 | `D` | One channel for the third articulation. |
| `q4` | Articulation 4 | 5 | `X` | One channel for the fourth articulation. |
| `q5`, `q6` together | Articulations 5 and 6 / wrist | 6 and 7 | `Y`, `Z` | Two motor coordinates mix both wrist coordinates; neither channel is an independent one-to-one wrist joint. |

The gripper is an additional servo/tool channel, outside these six arm coordinates. The BOM lists seven arm steppers in three groups: one 40 mm motor for articulation 1; three 34 mm motors with 5:1 mechanical reduction for articulations 2/3; three 34 mm motors for articulations 4/5/6. It separately lists one MG995 servo. This supports the **eight-actuator baseline**; it does not verify current part availability or motor running torque.

Equality of shoulder command coordinates does not prove equal physical shaft direction, current, torque sharing, or position. Wiring orientation, mirrored mounting, driver direction settings, transmission backlash and any lost steps must be resolved. A single failed shoulder drive may leave the shared mechanism in an unsafe state; seven command channels must not be modeled as seven independent spatial axes.

## Wrist differential: observed software convention

The pinned Thor-ROS `write()` implementation converts six joint commands in radians to intermediate integer degree values. It negates `q2`, `q3` and `q5` through its source expressions and mixes its wrist intermediates before emitting commands. For the wrist, **ignoring integer truncation**, its observed mapping in degree units is:

```text
motor-coordinate 6 = -q5 + 2*q6
motor-coordinate 7 =  q5 + 2*q6

q5 = (motor-coordinate 7 - motor-coordinate 6) / 2
q6 = (motor-coordinate 6 + motor-coordinate 7) / 4
```

The sum/difference inverse appears in both feedback parsing paths. Thus, in this source convention, a pure `q5` change produces opposite channel changes; a pure `q6` change produces equal channel changes. These statements concern **firmware command coordinates**, not raw motor shaft angles or pulses. Do not infer gear tooth counts or motor torque multiplication from the coefficient `2` alone. The integer-degree conversion loses precision and is not a recommended RAFTEL trajectory implementation.

The same source emits `A,B,C,D,X,Y,Z` for `thor_pcb`, duplicating the shoulder coordinate. Its alternate board path emits `X,Y,Z,U,V,W`, with already mixed wrist values in `V,W`. The board-specific motor/driver assignment and configuration must be inspected before adopting that path; address letters are not portable between boards.

Legacy Asgard is insufficient evidence for an independent-joint wrist implementation: the pinned functions for articulations 5/6 and all-joint motion explicitly leave coupled-motion calculation as future work, while sending the displayed values directly to the two wrist channels. Do not copy that behavior into the new backend. The [official kinematics page](http://thor.angel-lm.com/documentation/kinematics/) contained only a future-content placeholder when inspected.

## Implemented continuous-coordinate utility

`src/raftel_arm01/kinematics/thor_drive.py` provides dependency-free `joints_to_drive()` and `drive_to_joints()` for this **nominal software convention only**. Both use radians. The full continuous map, in address order `A,B,C,D,X,Y,Z`, is:

```text
(q1, -q2, -q2, -q3, q4, -q5 + 2*q6, q5 + 2*q6)
```

The pinned source's `-90 + (q1 + 90)` and `90 - (q2/q3 + 90)` intermediates cancel to these expressions before integer truncation; the utility preserves continuous values instead of copying source quantization. The inverse rejects shoulder-channel disagreement beyond a numerical absolute tolerance of `1e-9 rad`, rejects invalid lengths/nonfinite or nonnumeric values, and preserves the documented coordinate distinction. That tolerance is not a physical synchronization specification. No configured hardware limits are implied by accepting a finite model coordinate.

Tests in `tests/test_thor_drive.py` cover known channel values, pure wrist modes, 100 seeded round trips, small-angle precision, shoulder mismatch, invalid input and overflow handling. These verify algebra and input handling, not CAD zero, joint-axis orientation, transmissions or physical behavior. The module has no driver, G-code output, arming or hardware calls; it is not connected to the mock sorting system.

## What the native CAD XML supports

Selected archive inspection found:

- [Top assembly](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/Assembly.FCStd): distinct `AssemblyBase`, `AssemblyArt1`, `AssemblyArt2`, `AssemblyArt3`, `AssemblyArt4`, and `AssemblyArt56` assembly links. These are assembly placements, not a six-joint calibrated robot model.
- [AssemblyArt1](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/AssemblyArt1.FCStd): gearbox-motor objects and two links to `Art2MotorGear.FCStd`, consistent with the paired shoulder-drive investigation.
- [AssemblyArt4](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/AssemblyArt4.FCStd): multiple 34 mm stepper objects, Art56 motor holders, and GT2 pulley objects.
- [AssemblyArt56](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/AssemblyArt56.FCStd): gear plate, two links to the small-gear source, pulley and gripper-servo objects. The document contains external-link placement expressions referencing sibling files and local coordinate systems.

This is structural corroboration, not a solver result. Documents may contain source prototypes and assembly instances simultaneously; counting matching object labels is not a reliable physical motor count. Some external references use `.FCStd` capitalization while sibling filenames use `.fcstd`; verify resolution on the chosen filesystem and CAD version before trusting a loaded assembly. No listed XML placement has been promoted to a joint-origin specification.

## Required resolution before a Thor hardware model

1. Recompute the full native assembly, resolve dependency and naming issues, and distinguish source objects from installed instances. Record the exact CAD/assembly workbench versions.
2. Extract actual revolute axis lines and parent/child transforms; compare against the upstream ROS description instead of assuming assembly origins are joints. Define signs, SI units, and a reproducible zero pose.
3. Reconcile the pinned Thor-ROS coupling with the chosen firmware, motor/driver pin map, direction inversion, gearbox/belt/gear ratios, and microstepping. Record source-derived constants separately from physically calibrated ones.
4. Establish individual shoulder-motor synchronization, homing/offset treatment, fault detection and acceptable load sharing. Derive motor loads from the actual mechanism; do not divide shoulder torque by two by assumption.
5. Determine wrist travel as a **coupled feasible region** in joint and motor space, including cable and collision limits. Independent min/max boxes alone may allow impossible channel combinations.
6. Establish gripper aperture geometry and whether its jaws meet the required parallel motion. PWM/tool values are not measured jaw position or force.
7. Validate hard stops, software margins, feedback freshness, velocity/acceleration/current limits and gravity-safe stop behavior before any armed operation.

The upstream firmware page includes disabled limit settings and generic travel fields. They are evidence of an example configuration, not ARM-01 safety limits. This study intentionally produces no executable hardware mapping, URDF, calibrated geometry or motion instructions.
