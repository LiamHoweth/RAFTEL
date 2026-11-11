# Thor elbow controller compensation audit

The pinned ROS driver and official GRBL v1.0 source do **not** implement a shoulder-to-elbow compensation term in their ordinary linear command or position-report paths. This closes the source-code question for that pipeline; it does not calibrate the physical arm. If the [CAD-supported moving-carrier model](thor-elbow-mechanism.md) is confirmed, the upstream diagonal joint/channel map cannot directly represent relative elbow motion throughout shoulder travel.

The [machine-readable evidence](../hardware/cad/thor-controller-compensation.json) records 29 source-file hashes, immutable revisions, 15 findings and their line ranges. No firmware, upstream source, runtime controller or hardware connection was changed. This is a static source audit; no firmware build, flash or runtime test was performed.

## Pinned pipeline

The official downloads page retrieved on 2026-11-11 links GRBL v1.0, Asgard v1.0 and Fly configuration v1.0.0. Those tag names resolve to the revisions below. The current CAD revision and ROS revision are separately pinned; publication by the same project does not establish that all four releases were tested together on one physical arm.

| Source | Revision | Scope checked |
| --- | --- | --- |
| [Thor-ROS](https://github.com/AngelLM/Thor-ROS/tree/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952) | `e11a56b5aa0d89f0b68a3ea7bd084eab4a050952` | Joint definitions; controller write and both readback branches |
| [GRBL v1.0](https://github.com/AngelLM/grbl/tree/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff) | `1f6437a77e3abcb652d3f8ce718faf7e041ae6ff` | Selected configuration, parser, linear motion gateway, planner, stepper and reporting |
| [Asgard v1.0](https://github.com/AngelLM/Asgard/tree/30bf2f8850670f728a0f4c3e2e5d22db4f57d8c6) | `30bf2f8850670f728a0f4c3e2e5d22db4f57d8c6` | Manual shoulder/elbow movement functions |
| [Fly configuration v1.0.0](https://github.com/AngelLM/Thor-Fly-Super8Pro-config/tree/257ca3649422256bca653e269b22c3d32bb5fa1f) | `257ca3649422256bca653e269b22c3d32bb5fa1f` | Startup configuration and all shipped `.g` macros; RRF core/binary not audited |

The [ROS joint definition](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_urdf/urdf/thor.urdf.xacro#L314-L330) places joint3 between link2 and link3, with its angle relative to the upper arm. It is not declared as an independent world-frame forearm angle. In [write()](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_controller/src/thor_interface.cpp#L269-L309), shoulder and elbow command radians become independent integer-degree values. B/C receive the shoulder value and D receives the elbow value. The Fly branch similarly sends shoulder Y and elbow Z independently. Integer truncation and the offset-before-truncation expression mean this is only approximately the continuous `B=C=-q2, D=-q3` degree convention; no shoulder variable enters the elbow expression.

## No downstream GRBL term

In [gcode.c](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L367-L373), B, C and D select distinct array indices. At lines617–635, an omitted axis retains its target; a specified axis applies its own work/coordinate offsets and G90/G91 mode. These operations contain no shoulder/elbow mix. [motion_control.c](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/motion_control.c#L33-L75) passes the linear target to the planner unchanged.

The selected [configuration](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/config.h) enables Thor defaults and ATmega2560; COREXY is commented out. The active [planner branch](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/planner.c#L284-L310) rounds each target after multiplying by that channel's scalar step scale. The [stepper](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/stepper.c#L373-L405) advances B/C/D accumulators independently. Coordinating their timing for a straight line does not insert a cross-axis coordinate transform.

The [default scales](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/defaults/defaults_thor.h#L31-L37), including270 for B/C and265 for D, cannot encode a nonzero shoulder cross derivative. They are compile-time defaults, not observed EEPROM values or measured shaft calibration.

## Readback, modes and alternate controller

GRBL [system.c](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/system.c#L260-L285) divides each channel's own step count by its own scale. [report.c](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/report.c#L431-L470) reports these values as MPos and subtracts per-axis offsets for WPos. ROS independently negates shoulder/elbow degrees in both readback branches. None is an independent physical joint-angle encoder or an inverse carrier transform.

The ROS writes contain G0 but do not themselves establish G90 on every move. GRBL supports absolute/incremental modes; fixed offsets and mode changes operate within each channel. Even in the intended absolute mode, they cannot supply the missing position-dependent cross term. A future backend must explicitly validate mode, offsets, calibration and state interpretation instead of borrowing the upstream assumptions.

[Asgard's manual functions](https://github.com/AngelLM/Asgard/blob/30bf2f8850670f728a0f4c3e2e5d22db4f57d8c6/asgard.py#L197-L250) likewise move B/C without D or D without B/C. This supports interpreting it as a channel interface; its articulation labels do not establish relative elbow angle calibration.

The [Fly startup](https://github.com/AngelLM/Thor-Fly-Super8Pro-config/blob/257ca3649422256bca653e269b22c3d32bb5fa1f/sys/config.g#L8-L29) uses absolute mode, maps shoulder Y to drives1:2 and elbow Z to drive3, with separate scalar scales. No cross-axis mixing directive appears in the inspected startup or shipped macros. Homing uses sequential Y/Z movement and fixed offsets. This configuration finding does not establish all behavior inside the separate RRF binary/core or an owner's changed macros.

## Reconciliation boundary

Under the declared mechanical model `phi=c*q2+s*K*q3`, a nonzero carrier coefficient requires a shoulder term in both forward and inverse angle conversion. Here `phi` is the physical elbow gearbox output angle relative to Art1. It is **not** automatically the source D or Z degree coordinate. The [conditional elbow loads](thor-elbow-loads.md) use that physical-coordinate model; the nominal source drive map remains a historical source convention.

The evidence therefore identifies a source/mechanism mismatch to reconcile, rather than authorizing a silent firmware fix. Possible explanations include unmatched source/CAD generations or different intended channel semantics; no source evidence found here chooses one. Establish actual belt routing/pitch radius, channel-to-shaft scale/sign and zeros, then apply an explicit tested forward/inverse model in a future controller. Homing, limits, feedback, dynamics and independent stop behavior need their own commissioning evidence. No physical motion, calibrated correction value or safe operating configuration results from this audit.
