# Preliminary motor-power and control architecture

**Research design only. No wiring drawing or energization authorization.** Liam permits eight actuators and selected Thor for initial CAD investigation: seven arm steppers drive six independent arm axes, with a separate gripper servo. Exact motors, controller revision, supply topology and safety hardware remain unqualified. The C001 section below is retained only as a comparison; its voltage/current figures do not size Thor.

## Primary provisional architecture — Thor

Use the [pinned Thor source](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159), [BOM](http://thor.angel-lm.com/documentation/bom/) and [electronics guide](http://thor.angel-lm.com/documentation/electronics/) together. Upstream describes a custom control PCB and an alternative controller; it lists stepper drivers and an MG995 gripper servo. These names are not evidence of the exact build's current limits, safe voltage, thermal margin or reliable feedback. Sources accessed 2026-11-11 over HTTP where HTTPS failed.

Before release, trace each of the seven motor channels to its physical transmission and six-axis kinematic effect. Coupled motors must not receive inconsistent commands, home independently into a bind, or lose synchronization unnoticed. The future hardware abstraction must map joint-space commands through a tested motor-space coupling model; motor count and arm-axis count differ.

```text
Qualified enclosed DC source(s), output ratings TBD
  → coordinated source/branch protection
  → independent DC-rated motor-energy interrupt system
  → stepper driver motor-power branches → seven arm steppers
  → separately qualified gripper regulator/feed → gripper servo

Host → verified controller/firmware → stepper drivers + gripper command
Homing/limit/optional actual-position sensors → controller + fault monitoring
Independent physical stop → energy interrupt + manual reset/arming permission
```

This is a review aid, not a wiring diagram. Select exact motor winding currents, driver current-setting method, cooling, voltage headroom, controller power domains, regenerative-energy management and gripper supply only after reading their manufacturer data. Do not multiply the seven stepper phase-current ratings and call that the required DC supply current: switching-driver behavior, winding resistance/inductance, simultaneous motion and duty cycle matter. Do not substitute the C001 servo-bus budget below.

Homing switches and commanded step counts are not continuous measured joint positions. Qualify a feedback approach and determine what can detect lost steps, belt slip, motor desynchronization and jams. Servo PWM command alone also does not establish gripper position or grasp success. No Thor firmware/driver integration or hardware response was tested in this bootstrap.

Removing motor energy may release stepper holding torque and permit gravity-driven motion; belt reduction or gearing is not a certified brake. Stop design must include restraints/counterbalance/catch geometry and retained bus-energy assessment. Logic/USB power may remain only if it cannot bypass the motor interrupt or backfeed actuator power. Every gripper motor-energy feed is part of this review.

## Comparison only — C001 evidence and compatibility

The [manufacturer STS3215 specification](https://www.feetechrc.com/Data/feetechrc/upload/file/20200611/6372749961523760249976542.pdf) identifies a three-conductor TTL interface. Treat the six-axis modification's “RS485” wording as unresolved documentation inconsistency; TTL and RS485 transceivers are not interchangeable. Match the exact actuator suffix, pinout, connector orientation, ground reference and interface electrical levels before any connection.

The [Waveshare Adapter (A) FAQ](https://docs.waveshare.com/Bus_Servo_Adapter_A/FAQ) states **5 A maximum** and **no voltage regulation**. Its [description](https://docs.waveshare.com/Bus_Servo_Adapter_A) advertises 9–12.6 V and also mentions lower-voltage input. Confirm the exact board revision's behavior at the selected C001 voltage; never use the advertised 12 V input as permission to apply 12 V to C001 servos. Accessed 2026-11-11.

## Comparison only — C001 arithmetic, not a Thor supply specification

For seven reference C001s at 7.4 V, the published rated-current sum is 7 × 0.65 = **4.55 A**, and simultaneous locked-rotor sum is 7 × 2.5 = **17.5 A**, approximately **129.5 W**. Neither sum predicts a real trajectory's continuous demand. Allow for startup, acceleration, holding, current-limit response, connector heating and cable drop. A supply's fault-current limit can exceed its normal operating current. Regenerative deceleration may require an absorber/clamp or compatible supply; this is unverified.

A 5 A adapter is therefore **not an approved whole-arm power distributor**, even if normal current seems below 5 A. Do not size the system by copying a stock five-arm-axis kit's supply.

## Comparison only — C001 topology for later review

```text
Certified enclosed AC/DC supply (exact regulated output TBD)
  → source-proximate overcurrent protection
  → independent, DC-rated motor-energy interrupt device
  → protected distribution with separately rated motor branches
  → actuators

Host USB → verified TTL bus interface → signal bus
                       common reference ground as required
Independent stop circuit → motor-energy interrupt device
                       → monitored reset/arming permission (future)
```

This block diagram does not establish a safe circuit. Separate motor-current paths must not backfeed the adapter, host USB or bypass the emergency stop. Verify signal isolation/power-domain behavior and discharge time. Daisy-chain servo power connectors require their own current qualification; low-cost stock harnesses cannot be assumed to carry 17.5 A. Controller placement should be on the stationary base plate, with keyed detachable power and separate communication connectors for future mobility.

## Required for either architecture before schematic or harness release

1. Record exact actuator/driver variants, supplier datasheets, connector ratings, cable lengths, duty cycle and measured current traces under controlled restraints. For Thor, reconcile winding currents, microstepping/current settings, motor coupling and controller revision; for C001, reconcile servo voltage/bus suffixes.
2. Derive conductor area from allowable voltage drop (`ΔV = 2ρLI/A` for a two-wire branch), insulation temperature, bundling, flex duty and ampacity. Select high-flex joint cable and strain relief; leave service loops clear of all joint limits.
3. Coordinate main/branch fuses with the weakest conductor/connector, fuse time-current curves, supply fault behavior and DC interrupt rating. Select final fuse values after normal transients are measured; no arbitrary “20 A fuse” approval follows from the stall sum.
4. Select independent stop switching for DC voltage/current and expected inrush; add appropriate suppression where required. Prove all motor-energy feeds are interrupted, retained energy dissipates safely, and reset cannot restart motion.
5. Keep the arm mechanically supported on loss of motor power. Counterbalance, restraint, guarded catch volume and brake needs must be resolved before emergency-stop testing.
6. Verify grounding, polarity, insulation, fusing, torque-free startup and sensor/feedback validation without energizing an unsupported arm. Write a supervised commissioning procedure first.

No hardware driver is implemented by this milestone. Future arming requires validated calibration, travel/velocity/current limits, sufficient actual-state feedback, fault latching, operator clearance and an independent physical stop. Software alone does not provide the emergency-stop function.
