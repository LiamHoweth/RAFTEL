# ARM-01 safety and commissioning gates

ARM-01 is an unvalidated bench R&D prototype. Logical sorting tests establish software behavior only. They do not establish physical accuracy, force limits, electrical safety, collision avoidance or household suitability. No real motor backend is enabled in this foundation.

## Thor-specific study requirements

Liam permits eight total actuators: Thor's seven arm steppers plus one gripper servo still provide six independent arm axes plus gripper. This is permission to investigate an existing design, not hardware qualification or commissioning approval. Preserve the upstream geometry for baseline study before modifying it.

- Verify the mapping from six arm coordinates to seven motor channels. Coupled channels require coordinated homing and motion; a single stalled motor must not silently distort the mechanism.
- Qualify belt tension, pulley retention, bearing support and printed transmission housings. Belt slip or lost steps can invalidate a position estimate without a command error.
- Treat stepper holding torque as energized behavior, not a power-off brake. Test gravity retention and safe drop containment with restraints before stop/power-loss experiments.
- Determine how actual joint state and grasp outcomes will be observed. Commanded step counts, homing switches and gripper PWM alone are insufficient evidence of a successful physical cycle.
- Obtain exact motor/driver/gripper models and manufacturer limits; the upstream generic NEMA sizes and MG995 label are not qualified specifications. The previous C001 voltage/current exercise does not apply to Thor.

## Principal hazards and required controls

| Hazard | Preliminary control | Evidence required before motion |
|---|---|---|
| Arm/gripper pinch, crushing and impact | Restricted and clearly marked swept volume; supervised operation; low-energy commissioning; no people or pets in reach | Measured travel, speed, stopping behavior and clearance for selected geometry |
| Arm falls when torque is removed | Mechanical support/counterbalance or rated retention; clear catch volume; protected payload area | Controlled power-loss and stop tests with the arm restrained; no assumption that gearing, belts or de-energized steppers hold |
| Mount slips, desk fails or printed part creeps | Metal load-transfer interface; rated clamps/bolts; strain-relieved harness; inspect prints | Desk survey, load calculations, proof procedure, slip/deflection checks, inspection interval |
| Short, overheating or cable failure | Protected regulated motor supply, coordinated fuses, rated wiring/connectors, guarded distribution | Exact-item datasheets, schematic review, polarity/insulation checks, protected-load tests |
| Overload, thermal loss or gear damage | Full downstream-load sizing, duty derating, current/temperature monitoring where supported | Static/dynamic calculations and supervised worst-case thermal runs; stall ratings are not operating ratings |
| Lost steps, belt slip or coupled-motor disagreement | Actual-position/coupling checks, conservative load/speed bounds and fault latching | Restricted tests with independent pose measurement; detection and recovery demonstrated |
| Software crash, lost communication or stale feedback | Future watchdog, fault latch, bounded commands, explicit arming, controlled recovery | Fault-injection tests at hardware interface; documented response to every loss of state |
| Unintended startup after reconnect/reset | Disarmed startup; validate homing/calibration, limits and feedback before explicit manual arming | Reboot, reconnection, stop-reset and calibration-failure tests |
| Dropped object or failed grasp | Lightweight test pieces, guarded drop area, outcome verification, bounded retries | Measured grip capability and independent object-presence/outcome checks |

## Independent emergency stop

An accessible latching physical stop must remove motor energy independently of the computer and application. It must use DC-rated hardware appropriate to the selected circuit, cover every motor-energy source, and require deliberate reset followed by separate arming. A graphical stop, serial command, USB disconnect or Python exception handler does not meet this requirement. The host may remain powered for diagnosis only if no electrical path can energize motors.

Removing power can cause gravity-driven collapse. Resolve mechanical restraint and safe catch geometry before testing interruption. A stop circuit cannot be described as protective until its wiring, switching ratings, retained energy, stop behavior and restart prevention are inspected and tested. The preliminary electronics notes are not a fabrication drawing.

## Staged commissioning; all physical gates remain open

- [ ] **Mechanical review:** selected CAD revision and license captured; six arm axes counted separately from seven Thor motor channels and gripper; masses, joint limits, reach and clearance measured; mount and bench verified.
- [ ] **Electrical review without motion:** exact motor, driver and gripper variants matched to qualified supply domains; controller/command interfaces and motor-channel mapping confirmed; fuses, conductor/connector ratings, grounding, stop circuit and strain relief inspected.
- [ ] **Supported single joint:** written supervised procedure; motor torque initially off; valid calibration and conservative limits; emergency stop and power-loss response tested with restraint.
- [ ] **Supported full arm:** actual-state feedback, coupled-channel behavior, current/temperature bounds, startup/reconnect behavior and fault latching tested; no payload initially.
- [ ] **Restricted manipulation:** low speed and lightweight objects; independent grip and placement checks; documented thermal duty envelope and failure recovery.
- [ ] **Autonomous bench trial:** controlled workspace and supervised evaluation protocol; physical cycle success recorded separately from logical demo results.

These gates define future work; they are not instructions to energize the present unverified assembly. Liam must inspect physical construction and approve the commissioning procedure. Applicable standards, university/lab requirements and professional review must be identified for the actual deployment before claiming compliance. No certification or safety rating is asserted here.

## Fault and recovery policy for future hardware

On unknown pose, stale feedback, limit/thermal/current fault, stop activation or failed controller communication: stop issuing motion commands, latch the fault, record the last verified state and require operator intervention. The actual energy-removal/holding response must be determined from gravity hazards. Do not automatically retry uncertain grasps, placements or motion when object/arm state is unknown. A software retry must never clear a physical fault.

Prototype-only restrictions: dry indoor bench, lightweight inert objects, trained supervising operator and controlled access. Household use around children, pets or unattended occupants requires substantially more mechanical, electrical, functional-safety and human-interaction engineering.
