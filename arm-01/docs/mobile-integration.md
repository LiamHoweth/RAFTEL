# Future mobile compatibility — interface study

The new [Thor geometry](thor-geometry.md) and [load study](thor-load-analysis.md) supersede generic examples as the basis for future Thor-specific mounting calculations. The current analytical mass scenarios and support wrenches do not validate any mobile chassis or mount.

**Status: analytical concept only; current mechanical direction is a Thor-first CAD study.** Liam approved eight actuators: seven arm steppers including the dual-motor shoulder, plus one gripper actuator, providing six independent arm axes. ARM-01 remains stationary. No mobile base, CAD interface, chassis collision model, or floor grasp has been built or validated. Preserve interfaces now without claiming desktop reach proves floor reach.

The 55 g servo masses, 400 mm reach sphere and numerical mount loads below belong to a retained **generic SO-101-like sensitivity example**. They are not Thor dimensions, mass properties, actuator loads or power requirements. Thor must receive a separate CAD-derived model before any mounting or mobile suitability decision.

## Removable mechanical interface proposal

A starting interface for CAD adaptation is a **120 × 120 × 6 mm aluminum adapter plate**, with four clearance holes for M5 fasteners on an **80 × 80 mm square** and a distinct keyed orientation feature. These dimensions, material choice, and fastener size are **unverified generic proposals**, not fabrication instructions. **They do not match any verified Thor bolt pattern, mount footprint or mass/load requirement.** Do not drill, scale holes or choose a plate from this example. First extract the original Thor base geometry and load path, preserve its mounting holes, and then design an adapter around that baseline. Mate the upper side to the selected existing arm's original bolt pattern; use a replaceable adapter rather than editing a proven base casting unnecessarily. Confirm edge distances, tool access, thread engagement, material grades, tolerances, and existing servo clearance in CAD.

At an assumed aluminum density of 2,700 kg/m³, an unperforated plate would weigh approximately **0.233 kg**. Hole removal and any key/clamp hardware change the actual mounting mass. A top plate and bench backing plate approximately double that plate mass before clamps or fasteners. Obtain a measured assembly mass after selecting the design.

The load path is arm base → original base fasteners → adapter → bolted/backed or positively restrained removable bench fixture → verified bench structure. Two commercial clamps with spreader/backing plates may be investigated; their published capacity must be applicable to the actual desk and load direction. A printed adapter or clamp must not be assumed structurally equivalent to metal.

With the generic non-Thor 400 mm/200 g load model, shoulder pitching moment is 2.139 N·m. A simplified 80 mm bolt-row couple corresponds to 26.7 N of total row tension from that moment, or 40.1 N at the provisional ×1.5 allowance. This **is not a fastener or clamp rating**: whole-arm offsets, base loads, torsion, shocks, prying, plate bending, friction/slip, cyclic loosening, bench crushing, and gravity fault transients remain unmodeled. Check the complete base reaction using the eventual CAD and trajectories.

## Mass and center of gravity

The generic servo example's illustrative downstream mass is 0.755 kg with a 0.200 kg payload. Its horizontal mass moment is 0.218125 kg·m, giving a distal assembly center of mass approximately **0.289 m forward of the shoulder** in the modeled extended pose. Add approximately 0.110 kg for the two assumed 55 g base/shoulder servos at x ≈ 0, giving roughly 0.252 m for those modeled components combined. This excludes base housing, fasteners, controller, wiring and mount; it is **not the whole robot's center of gravity**.

**Do not substitute these masses for Thor.** Its seven arm steppers, paired shoulder mechanism, printed structure, transmissions and gripper require actual CAD/BOM-derived masses followed by measurement.

The mobile system must combine measured arm, mount, chassis, battery and payload mass properties at all relevant joint configurations. Determine tipping stability from the actual wheel/support polygon, acceleration/braking, floor slopes, and object contact forces. No mobile stability claim follows from a rigid bench test.

## Coordinate and communication interfaces

Use right-handed SI frames: `bench` or future `map` → `base_link` (mobile chassis) → `arm_mount` (adapter center, +z upward, +x toward intended working side) → `arm_base` → calibrated joint chain → `tool0` → `tcp`. Mount height is a transform parameter, not a constant in sorting logic. Camera extrinsics and bins belong to the workstation/world frame and must be transformed using a current timestamped calibration.

The future arm controller interface should carry timestamped joint observations, commands with explicit units, sequence identifiers, faults, arming state and feedback freshness. Keep object/task planning above this interface. The current mock prototype does not implement a physical bus, base localization, synchronization, or calibration.

## Electrical interface proposal

- Put the power distribution and bus controller on a serviceable fixed bracket near the mount, outside moving links and the source region. Record actual added mass in the CAD/BOM.
- Use a keyed locking motor-power connector, a separately identified communication connector, cable strain relief, and a documented pinout/voltage label. Select a connector only after current/voltage and wire-gauge analysis; no connector model is approved yet.
- Select one exact actuator voltage family or separately protected rails. Never connect 12 V to a 7.4 V C001 bus.
- For historical comparison only, a C001 seven-servo example gives **17.5 A aggregate catalog stall current at 7.4 V**, approximately 129.5 W; this is an electrical bounding scenario, not required continuous operating power or a recommended supply. Shared harness/connectors may have lower limits. Current transients, distribution losses and duty factors require measurement. **This is not the approved eight-actuator Thor configuration.** Thor supply, wiring and disconnect sizing must come from its exact stepper/driver topology and gripper rail; motor phase current cannot simply be summed as DC supply current.
- Keep compute power separate from the independently interruptible motor-energy rail. An emergency stop must cut motor energy through appropriately rated hardware while accounting for gravity collapse. A future battery needs its own protection and isolation review.
- Disconnect only under the eventual validated power-down/lockout procedure. No hot-plug operation is authorized or proven.

## Floor-reach geometry at 150–300 mm mounting heights

`tools/engineering_analysis.py` retains a generic comparison and computes an optimistic outer sphere for 400 mm reach, a hypothetical shoulder 60 mm above the mount, and a TCP 25 mm above floor level:

`r_horizontal,max = sqrt(reach² − (shoulder_height − tcp_height)²)`.

| Mount height above floor | Shoulder height | Optimistic maximum floor-plane horizontal radius |
| --- | --- | --- |
| 150 mm | 210 mm | 354.6 mm |
| 225 mm | 285 mm | 304.0 mm |
| 300 mm | 360 mm | 218.6 mm |

The 400 mm reach and 60 mm offset are **not extracted from Thor**. Recompute this table only after its baseline geometry and actual mounting frame are known. These are **necessary outer bounds only**, not kinematic simulation or validated grasps. Joint limits, minimum reach, wrist orientation, finger length, floor clearance, approach trajectory, cables, arm/chassis self-collision, and any base overhang will reduce usable space.

For example, if a hypothetical chassis extends 200 mm forward of the shoulder and requires 50 mm additional margin, targets must have x ≥ 250 mm. Under these assumptions the 300 mm mount-height case has **no possible target beyond that front boundary even in the optimistic sphere**. The 225 mm case leaves only about 54 mm of maximum radial extent beyond it, before any wrist/joint/collision restrictions. A front-edge mounting position, smaller chassis overhang, lower mount, different geometry, or revised floor task may be needed.

Do not encode this hypothetical chassis into a robot specification. When chassis dimensions are known, run FK/IK using the actual reused arm geometry and sample constrained floor grasps, then check complete swept volumes of the arm, held object and chassis. A point-target test cannot demonstrate collision avoidance.

## Integration gate before a mobile project

- [ ] Complete the [Thor baseline extraction gate](mechanical-analysis.md#prioritized-thor-baseline-extraction-gate), including seven arm motors, dual shoulder drive, gripper, masses and base reactions.
- [ ] Preserve/pin Thor's original mounting and base geometry; extract the real bolt pattern before designing any adapter or changing plate holes.
- [ ] Approve adapter CAD and load analysis; verify dimensional fit and physical rigidity on the bench.
- [ ] Measure whole-arm mass/CoG and reaction loads across representative tasks.
- [ ] Freeze connector voltage, current, pinout, protocol and stop behavior.
- [ ] Model the proposed chassis and perform constrained floor reach plus collision analysis.
- [ ] Complete tipping, gravity-collapse, guarding, power and supervised-operation reviews.

No mobile-base implementation is part of ARM-01's initial scope.
