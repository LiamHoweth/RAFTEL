# Preliminary mechanical analysis

**Current Thor analysis:** see [CAD-derived loads](thor-load-analysis.md) and [geometry](thor-geometry.md). The lightweight-servo example below remains a separate preliminary sensitivity calculation.

**Status: Thor-first CAD study approved; no mechanical design released.** Liam approved eight actuators: **seven arm steppers, including the dual-motor shoulder, plus one gripper actuator**, for six independently controlled arm axes. The priority is to extract and reproduce the existing Thor baseline before adapting it. See [CAD reuse](cad-reuse.md) for the source-design investigation.

**The calculations below are a retained generic SO-101-like sensitivity example, not a Thor load model.** Its assumed 55 g servos, link lengths, torque results and mounting loads must not be used to size Thor motors, reductions, plates, power supplies or payload limits. No Thor CAD dimensions, moving masses, load sharing, joint limits or thermal behavior have been validated here. No fabrication or energizing is justified by these calculations.

## Joint arrangement and geometry

The ARM-01 requirement is six independent arm axes and one gripper actuator; it now permits the Thor baseline's eight total actuators. Six axes and eight motors are compatible because the shoulder uses two motors for one axis. Do not assume the two shoulder motors split load equally without verifying the original transmission, synchronization and fault behavior.

For the historical sensitivity example only, a candidate SO-101-derived ordering is base yaw, shoulder pitch, elbow pitch, added forearm/elbow roll, wrist pitch, wrist roll, then gripper opening. Stock SO-101 alone does not meet the six-arm-axis requirement. The added joint must have mechanically supported bearings, defined travel, cable clearance, and evidence of physical reliability. Listing six axes does not prove an arbitrary Cartesian orientation is reachable; a Jacobian/singularity assessment is still required.

For sensitivity analysis only, use upper-arm 180 mm, forearm 140 mm, and wrist-to-TCP 80 mm, totaling an optimistic 400 mm horizontal extension. These are **not dimensions extracted from SO-101 or its modification**. No joint travel or physical zero offsets have been selected: derive them from the reused CAD, then measure interference limits on the unpowered assembly before calibrating software limits with clearance margins. Do not copy a servo's unrestricted rotation claim into robot joint limits.

The full 800 × 600 mm bench is not automatically reachable. A rear-center shoulder at y = 0 would need 600 mm just to reach its front-center edge; even an ideal 400 mm sphere cannot cover that. Keep the source region and three bins inside a smaller measured workspace, or revise the task layout. A sphere test only rejects impossible targets; it cannot certify IK, gripper orientation, self-collision, or swept paths. Overhead grasps further reduce useful reach because the wrist and jaws must remain above the object before descending.

## Reproducible generic static load model — not Thor

Run from `arm-01`:

```sh
python tools/engineering_analysis.py
python -m pytest tests/test_engineering_analysis.py
```

`tools/engineering_analysis.py` uses `g = 9.80665 m/s²` and the horizontal-pose moment `τ = g Σ mᵢ (xᵢ − x_joint)` for downstream masses. Horizontal offsets are measured from the shoulder axis. Model masses are **unmeasured planning assumptions**; the script does not inspect CAD, calculate inertia, or integrate dynamics.

| Downstream component | Mass estimate (kg) | Shoulder offset (m) |
| --- | ---: | ---: |
| Upper link | 0.120 | 0.090 |
| Elbow-flex servo | 0.055 | 0.180 |
| Forearm link | 0.100 | 0.250 |
| Added forearm-roll servo | 0.055 | 0.210 |
| Wrist-pitch servo | 0.055 | 0.320 |
| Wrist-roll servo | 0.055 | 0.350 |
| Gripper servo | 0.055 | 0.375 |
| Gripper jaws/hardware | 0.060 | 0.390 |
| Payload | 0.000 / 0.100 / 0.200 | 0.400 |

The shoulder-pan and shoulder-lift servos are assumed at the base/shoulder and do not contribute to this shoulder pitching moment. Their mass still contributes to mounting and mobile stability loads. Elbow pitching torque uses a joint at 0.180 m. Components exactly at an axis add zero gravitational moment about that axis. Local shaft bearing and radial loads require separate checks.

| Nominal extension | Payload | Shoulder static | Elbow static | Shoulder × 1.5 | Elbow × 1.5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 400 mm | 0 g | 1.355 N·m | 0.481 N·m | 2.032 N·m | 0.721 N·m |
| 400 mm | 100 g | 1.747 N·m | 0.697 N·m | 2.620 N·m | 1.045 N·m |
| 400 mm | 200 g | 2.139 N·m | 0.912 N·m | 3.209 N·m | 1.368 N·m |
| 300 mm | 0 g | 1.016 N·m | 0.361 N·m | 1.524 N·m | 0.541 N·m |
| 300 mm | 100 g | 1.310 N·m | 0.522 N·m | 1.965 N·m | 0.784 N·m |
| 300 mm | 200 g | 1.604 N·m | 0.684 N·m | 2.406 N·m | 1.026 N·m |

The 300 mm variant uniformly scales offsets by 0.75 while retaining masses; it is a comparative hypothetical design, **not a validated pose of the same arm**. The ×1.5 column is an initial uncertainty allowance only. Dynamic torque needs `Iα`, mass-dependent trajectories, friction, transmission efficiency, load reversals, and transient acceleration limits. No acceleration capability or final safety factor has been established.

For comparison, payload alone at 350 mm and 200 g gives only **0.686 N·m**. Omitting the rest of the arm materially understates actuator load.

## Generic servo comparison and thermal gate — not Thor sizing

The [manufacturer's 2024 catalog](https://www.feetech.cn/Data/feetechrc/upload/file/20240706/2024%E9%A3%9E%E7%89%B9%E5%AE%A3%E4%BC%A0%E5%86%8C.pdf) lists ST-3215-C001 at 7.4 V with 5 kgf·cm rated torque (0.490 N·m), 19.5 kgf·cm stall torque (1.912 N·m), 650 mA rated current, and 2.5 A stall current. These are manufacturer claims, not RAFTEL measurements. The older [STS3215 product specification A/0](https://www.feetechrc.com/Data/feetechrc/upload/file/20200611/6372749961523760249976542.pdf) is a distinct document; reconcile revision and exact SKU before selecting limits. Neither publication is a thermal qualification of the proposed arm, enclosure, duty cycle, and ambient environment. Accessed 2026-11-11.

**Conclusion for the generic servo example only:** a uniform C001 direct-drive layout cannot be justified for 400 mm extension and 100–200 g payload. The assumed 200 g shoulder load exceeds even the catalog stall figure; the no-payload shoulder estimate exceeds catalog rated torque. Do not buy servos on the basis of this model. Thor uses a different stepper/transmission architecture and requires a separate calculation; stepper holding torque is not available running torque at the operating speed.

The following alternatives explain the earlier generic servo feasibility study; they do not supersede the approved Thor-first investigation:

1. Reuse a shorter proven mechanism with a modest initial payload and smaller source region; derive actual loads from its CAD before setting the requirement.
2. Preserve the source geometry while adding supported shoulder/elbow reduction or counterbalance. Check gear/belt efficiency, backlash, mounting loads, stored spring energy, and gravity behavior; this is an engineering change requiring validation.
3. Use stronger shoulder/elbow actuators with separately verified continuous-duty data. A 12 V STS3215 variant is not interchangeable with C001 without exact electrical and thermal review, and its stall rating is still not continuous torque.
4. Raise the budget for a more mature six-axis design if the reach/payload requirements are firm.

Before motor selection is complete, obtain vendor duty/thermal data, measure link and tool masses, characterize holding current and winding/case temperature under restrained controlled tests, define ambient/duty limits, and verify shutdown and gravity protection. No hardware tests occurred in this bootstrap.

## Structure, gripper, and serviceability

- **Stiffness:** derive section properties and material/print orientation from the reused CAD. First-order cantilever deflection `δ = FL³/(3EI)` is useful for a single ideal link, but joint backlash, bearing compliance, fastener slip, and print creep must be measured separately. No `E`, section dimensions, or repeatability is assumed here.
- **Payload:** task mass is a software screening limit only until the mechanical envelope is verified. Characterize every allowed pose, acceleration, gripping force, and object center of gravity. A single maximum payload number does not cover all configurations.
- **Parallel gripper:** confirm that the selected existing gripper actually has parallel jaw motion. Preserve editable geometry, replaceable jaw pads, and an accessible motor/horn. Measure aperture, pinch force, object slip, and release reliability. A servo angle does not establish contact force.
- **Cables:** route a service loop for each joint; validate full travel with power off. Use strain relief on both sides of a moving span. The added roll joint needs a hard cable travel limit or a validated rotary interface; do not assume continuous rotation.
- **Heat:** maintain ventilation and thermally compatible material near actuators. Servo protection may disable torque and let the arm drop; protection is not a substitute for restraint.
- **Replaceability:** retain individual bolted modules, standard fasteners, accessible connectors, and an asset manifest with source revision and modification records. Avoid embedding wiring inside permanently bonded parts.
- **Base:** see [mobile integration](mobile-integration.md) for a provisional removable interface. The desk mount must transfer moment into a sufficiently stiff bench through a verified load path, not thin printed flanges alone.

## Prioritized Thor baseline extraction gate

1. Preserve the complete native CAD dependency layout from [Thor revision 286b081fe6f056d87c379b884781ef77ff6a0159](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159); record source/license provenance, including the metadata discrepancy described in the CAD reuse study. Open and recompute the assembly with compatible FreeCAD tooling and document missing links or errors. Source-file inspection alone does not satisfy this gate.
2. Extract actual joint axes/transforms, gear and belt ratios, physical stops, bearings, fasteners, original motor/driver part numbers, mount footprint and hole pattern. Identify all seven arm steppers, the dual shoulder drive relationship and the separate gripper actuator. Keep the baseline dimensions and drivetrain unchanged during extraction.
3. Extract moving-part volumes/materials, motor/tool masses, centers of mass and inertias; label CAD-derived material assumptions separately from measured masses. Obtain credible motor torque-speed/current and driver thermal data. Model both shoulder motors and transmission losses without assuming ideal equal load sharing.
4. Recalculate pose-dependent static loads, acceleration torque, base reactions, stiffness, gravity-fault behavior and power needs. Validate the baseline workspace and gripper motion before proposing smaller links or another gripper.
5. Only after the baseline is coherent, review adaptations against explicit requirements and document what upstream evidence no longer transfers. **Do not scale motor mounting holes, bearing fits, gears, plate holes or link dimensions before extracting the baseline.** A scaled mesh is not an engineered derivative.

## Required next mechanical evidence

- [x] Select Thor as the first existing six-axis CAD baseline to investigate; eight actuators approved by Liam. This is study approval, not approval to purchase or fabricate.
- [ ] Complete the prioritized Thor CAD/load-model extraction gate above.
- [ ] Produce a six-axis FK model and workspace sampling with actual joint limits.
- [ ] Add collision geometry and grasp-orientation constraints; validate approach and retreat paths.
- [ ] Calculate full-body static and dynamic loads; choose actuators against continuous-duty evidence.
- [ ] Analyze mount plate, fasteners, clamp/bench interface, and gravity-fault behavior.
- [ ] Perform supervised unpowered inspection and restrained load/thermal tests before motion.
