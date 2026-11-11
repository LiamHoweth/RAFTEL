# Thor transmission source study

Source inspection on 2026-11-11, using native CAD pinned to Thor `286b081fe6f056d87c379b884781ef77ff6a0159`. The [machine-readable extraction](../hardware/cad/thor-transmission-source.json) records ten saved gear definitions and twenty selected assembly attachments. These establish intended component chains and tooth counts; they do **not** establish manufactured fit, loss, backlash, strength, homing, or physical angle calibration.

## Evidence-backed transmission chains

| Joint | Saved geometry and attachment evidence | Ideal ratio or unresolved quantity |
|---|---|---|
| `q1` base yaw | [Art1GearMotor](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/Art1GearMotor.fcstd) has 10 teeth, module 2, saved pitch diameter 20 mm. AssemblyBase attaches it to the base stepper's `LCS_Gear2`. [Art1Bot](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/Art1Bot.fcstd) has the corresponding 50-tooth, module 2 feature in the rotating lower body. | Intended tooth-count reduction **5:1**. Sign/actual contact require the assembled axis and mesh check; do not infer direction from tooth count. |
| `q2` paired shoulder | [AssemblyArt1](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/AssemblyArt1.FCStd) attaches geared motor instances001/002 at `LCS_Motor2A`/`LCS_Motor2V`; each `LCS_Nema17_Gear` carries an Art2MotorGear 10-tooth pinion. The driven [Art2BodyA](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/Art2BodyA.fcstd) defines 60teeth, module 2, saved pitch diameter 120 mm. | Intended printed-stage reduction **6:1 per branch**. With supplier-declared PG5 ratio5.18, nominal rotor/joint reduction is **31.08:1 per motor**. This does not verify equal load sharing. |
| `q3` remote elbow | The **third** geared motor is also in AssemblyArt1, attached at `LCS_Motor3`, carrying `Pulley_GT2x20_Modified001`. The upper-arm AssemblyArt2 includes the long `GT2_Belt_Art3` and tensioners. [AssemblyArt3](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/AssemblyArt3.FCStd) attaches Art3Pulley at Art3Body's `LCS_Pulley`. | **Exact reduction remains open.** Art3Pulley is a smooth drum/belt clamp geometry, not a saved tooth-counted gear. Its revolved sketch contains a37 mm body radius and40 mm flange radius; neither is automatically the belt pitch-line radius. |
| `q4` forearm roll | AssemblyArt3 attaches Art4MotorGear to the bare stepper's `LCS_Gear`; it defines 10 teeth, module 1.8, pitch diameter 18 mm. [Art4TransmissionColumn](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/Art4TransmissionColumn.fcstd), used as AssemblyArt4's proximal rotating column, defines 20 teeth, module 1.8, pitch diameter 36 mm. | Intended reduction **2:1**. Verify shaft axes and mesh before treating it as a calibrated stage. |
| `q5`/`q6` wrist | [AssemblyArt4](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/AssemblyArt4.FCStd) attaches one 20-tooth GT2 pulley to each of its two bare motor shafts and one 208 mm belt to each pulley. [AssemblyArt56](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/AssemblyArt56.FCStd) attaches two 40-tooth pulleys directly to the two Art56SmallGear `LCS_Pulley` frames. Those small bevel features have 15 teeth; the central Art56GearPlate has 30 teeth. | **2:1 belt stage per driven side shaft**, followed by a **2:1 bevel tooth-count relation inside a differential**. The two wrist joints must be mapped together; multiplying stages into one independent ratio for each joint is insufficient. |
| Gripper | AssemblyArt56 attaches GripperActiveArm to the servo horn's `LCS_ActiveArm`, and GripperPassiveArm to the gripper base's `LCS_PassiveArm`. Both saved involute definitions have 26 teeth, module 1.1 and pitch diameter 28.6 mm; two passive links and finger instances are also present. | Intended equal26/26 gear phase coupling. This alone does not establish jaw parallelism, opening range, contact geometry or gripping force; those require the full linkage model. |

These are assembly-intent checks, stronger than matching unrelated tooth counts, but still short of a mesh-contact or kinematic calibration test. Geared motor instances are source prototypes/links, so counting every motor-looking CAD object would overcount the actual seven arm motors.

## Gearbox ratio and torque terminology

The [manufacturer listing for 17HS13-0404S-PG5](https://www.omc-stepperonline.com/nema-17-stepper-motor-bipolar-l-33mm-w-gear-ratio-5-1-planetary-gearbox-17hs13-0404s-pg5) declares **5.18:1**, despite the shorter “5:1” product title. It lists 90% gearbox efficiency, bare-motor holding torque 0.25N·m, gearbox maximum permissible torque 3 N·m and momentary permissible torque 5 N·m. These are distinct quantities: none supplies a verified ARM-01 continuous running torque at a selected speed/temperature. Use the exact purchased drawing/revision and torque-speed curves before calibration or sizing; 31.08 above uses the listing's rounded ratio.

For a simple stage with rotor angle `theta = r*q`, ideal virtual work gives `tau_joint = r*tau_rotor`. Losses reduce available output, while backlash, printed teeth, bearings and the gearbox can impose lower limits. For the paired shoulder, a load-share parameter is needed; assigning half the load to each branch is an optimistic assumption unless synchronization and load sharing are demonstrated. Check each gearbox output shaft before the printed 6:1 stage, not only the final joint moment.

## Elbow quantity that still needs measurement

For an ideal20-tooth, 2 mm-pitch driving pulley and a constant effective elbow drum pitch radius `R_p`, the nominal rotor/elbow ratio would be:

```text
r_elbow = 5.18 * (2*pi*R_p) / (20*2 mm)
```

Using37 mm merely as an **illustrative** pitch radius gives about 30.106:1. It is not an extracted exact ratio: belt thickness, pitch line, wrap/clamp behavior, tension and possible shoulder/elbow coupling remain unresolved. The [elbow mechanism study](thor-elbow-mechanism.md) now derives the conditional moving-carrier relation `phi=q2+s*(R_p/r_m)*q3` from source mounting and routing evidence. The [elbow load model](thor-elbow-loads.md) includes its shoulder reaction; physical signs, pitch radius and controller compensation remain open. Trace the actual belt centerline and fixing method before motion calibration. The40 mm flange is not a substitute pitch radius. Do not reuse the shoulder's60/10 ratio for the elbow simply because both motors are PG5 units.

## Keep differential coordinates separate from physical rotor coordinates

The [Thor joint map](thor-joint-map.md) documents the pinned controller's nominal wrist convention:

```text
u = -q5 + 2*q6
v =  q5 + 2*q6
```

Its address values are nominal drive coordinates, not a measured motor-shaft angle. **If** the reconstructed model confirms that `u,v` are the driven bevel-side-shaft angles and the 20-to-40 belt stage maps physical rotor angles to `theta6=2*u`, `theta7=2*v`, then the ideal physical mapping would be:

```text
[theta6]   [-2  4] [q5]
[theta7] = [ 2  4] [q6]

[tau_q5]   [-2  2] [tau_rotor6]
[tau_q6] = [ 4  4] [tau_rotor7]
```

The torque map is the transpose of the angle Jacobian, from virtual work. This is a **conditional mechanical hypothesis**, not a calibrated hardware mapping or a completed transmission proof. Confirm joint axes, signs, carrier references, belt routing, actual motor shaft coordinates and losses before adopting it. Never apply the nominal controller-coordinate torque map directly to a physical motor torque limit without that distinction.

The [wrist membership study](thor-wrist-mechanism.md) expresses both side shafts about common native +Y and enforces the pure-fold consistency case. Its conditional signs must be reconciled with the opposed controller coordinates above before interpreting this hypothesis as physical rotor motion. The [COM trajectory evaluator](thor-wrist-model.md) supports those explicit alternatives without choosing a calibrated motor convention.

The live [official firmware guide](http://thor.angel-lm.com/documentation/firmware/) publishes example step scales 44.5/270/270/265/20/250/250 and says they assume original hardware. Those figures are not independent proof of this pinned CAD's reduction or calibration; they must be reconciled with actual motor steps, microstepping, firmware revision and the reconstructed transmission.

## Remaining gates for load sizing

1. Close the elbow's actual pitch-line radius, belt fixing and any coupled motion; record an explicit motor-to-joint Jacobian.
2. Verify the mesh/shaft relationships in the restored native assembly and compare an input rotation to an output rotation without changing geometry.
3. Obtain running torque-speed and thermal evidence, gearbox allowable-load conditions, belt efficiency/tension and printed-gear strength. Preserve holding/momentary/continuous distinctions.
4. Combine the verified transmission map with CAD-derived downstream mass/COM and gravity/dynamic moments. Report optimistic load-sharing and efficiency cases separately from conservative cases.
5. Validate gripper linkage motion and force lever arms before claiming a parallel jaw or payload retention capability. No hardware actuation or purchase is authorized by this source study.
