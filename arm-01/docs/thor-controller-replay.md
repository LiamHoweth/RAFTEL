# Pinned controller conversion and offline protocol replay

The controller study now reproduces the **integer expressions** in the pinned
Thor-ROS write/read paths and a bounded subset of the GRBL channel-coordinate
pipeline. These are source-conversion and synthetic protocol fixtures. They do
not run ROS, the complete firmware, a planner/stepper timing model or hardware.
The existing continuous [`thor_drive.py`](../src/raftel_arm01/kinematics/thor_drive.py)
and ideal physical [`thor_transmission.py`](../src/raftel_arm01/kinematics/thor_transmission.py)
retain their separate meanings and behavior.

## Exact source expressions and observable discrepancies

[`thor_source_conversion.py`](../src/raftel_arm01/control/thor_source_conversion.py)
uses the arithmetic order of Thor-ROS
[`thor_interface.cpp` lines 269–350](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_controller/src/thor_interface.cpp#L269-L350),
revision `e11a56b5aa0d89f0b68a3ea7bd084eab4a050952`. The fetched bytes match
the previous audit's SHA-256
`c2bd16032e43db1e30fc48a2c00a7ef2b0c4943c7018234ca56aaed11102f690`.
This source was rechecked on 2026-11-11; no upstream source or installed
controller was changed.

- The first three coordinates add 90° **before** casting to an integer. At
  −0.1°, the source produces arm1 = −1° and arm2/arm3 = +1°; simply truncating
  the continuous map produces zero. Around −90° the distinction changes again.
- Each wrist joint is truncated first, then the two integer values are mixed.
  The source's discrete map is not a rounding operation on the continuous
  differential. In particular, +0.9° in both wrist joints yields zero in both
  integer channels while the continuous pair is (+0.9°, +2.7°).
- PCB output order is A,B,C,D,X,Y,Z, with B=C. Fly output order is X,Y,Z,U,V,W.
  The gripper uses a separate M3/S integer expression or M280/P0/S expression.
  No emitted diagnostic string includes G90, matching the source.
- `source_write` takes the previous successful source-angle vector explicitly.
  It exposes arm/gripper suppression independently. The default previous vector
  matches source activation: the first all-zero joint command produces only
  the hypothetical gripper line `M3 S255`. A caller modeling send failure must
  retain the old previous vector. The returned strings are never transmitted.
- The PCB
  [read loop lines 150–173](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_controller/src/thor_interface.cpp#L150-L173)
  consumes B and then consumes C at index 1, so it **uses C and discards B**.
  `read_grbl_report` preserves that historical result and separately reports
  whether B and C agree. The Fly branch has six independent reported fields.
  Both branches derive gripper state from the last command, even when Fly
  supplies a seventh `pos` value. Neither is measured physical joint feedback.

These functions implement complete finite input paths. They reject incomplete
reports atomically instead of reproducing the upstream partially mutated state.
Source signed-integer overflow/undefined conversions are rejected, including
intermediate multiplication and negation. Only the two documented boards are
accepted. This is deliberately stricter than the source's catch-all else path.

The [binary64 C++ fixture](../tests/fixtures/thor-controller-conversion.json)
contains 12 boundary cases plus its complete small reference generator. The
generator was compiled with Windows g++ 16.1.0, `-std=c++17 -O0`; its output
matches Python's implementation. This is a host expression check, not a ROS
build or a firmware build. Near exact integer boundaries, compiler arithmetic
choices remain part of the fixture's explicit host model.

## Bounded channel replay

[`DiagnosticReplay`](../src/raftel_arm01/control/thor_protocol_replay.py) supports
G0, G90, G91, G92, G92.1 and the seven PCB channel words. An explicit synthetic
origin, absolute mode and supplied work offsets initialize each replay. Omitted
axes hold their parser targets. G92 changes the coordinate offset, while G91
increments the previous unrounded parser target. Fixed offsets and independent
scalar scales cannot add the missing shoulder term to D.

The modeled source is GRBL revision
`1f6437a77e3abcb652d3f8ce718faf7e041ae6ff`:

| Behavior | Pinned primary source |
| --- | --- |
| Eight-digit decimal accumulation/truncation | [`nuts_bolts.c` lines 24–110](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/nuts_bolts.c#L24-L110) |
| Per-channel targets and G90/G91/offsets | [`gcode.c` lines 595–635](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/gcode.c#L595-L635) |
| Scalar target-to-step rounding | [`planner.c` lines 284–310](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/planner.c#L284-L310) |
| Compile-time scalar defaults | [`defaults_thor.h` lines 31–37](https://github.com/AngelLM/grbl/blob/1f6437a77e3abcb652d3f8ce718faf7e041ae6ff/grbl/defaults/defaults_thor.h#L31-L37) |

`source_decimal` models eight digits **including leading zeros**, not Python's
correctly rounded decimal parser. For example `0.000000001` becomes zero and
`123456789` becomes 123456784 in the declared AVR float32 model. Scaling uses
float32 arithmetic throughout, including the selected default AVR ABI's
float32 `double` constants; scalar rounding is half away from zero. The
[independent host float32 fixture](../tests/fixtures/thor-controller-decimal.json)
contains 12 cases and a reproducible reference generator. The fetched decimal
source hash is
`b0231ef219c3235af94c93cecae50e5deef9bd0c0e3824ef7fdb04bc98f6833c`.
These are analytical ABI fixtures, not proof of a particular compiled binary.

The subset rejects unsupported commands, scientific notation, duplicate axes,
conflicting modes, malformed words, more than 64 digits in a numeric word,
nonfinite/overflowing calculations and step targets/deltas outside the
conservative symmetric range [−2147483647, +2147483647]. Lines, total commands
and pending queues are bounded. There is no EEPROM, timing, acceleration,
homing, travel-limit or collision emulation. A compile-time step scale is not an
observed controller setting or a physical calibration.

Accepted, acknowledged, planned and completed are separate fields. `submit`
changes parser/planned state; only `complete_next` advances command-derived
synthetic completed steps in FIFO order. A lost acknowledgment does not prevent
synthetic execution. Retrying an incremental line can duplicate its effect.
`acknowledgment_received` supplies **per-line synthetic ground truth**, not an
attribution algorithm for untagged real GRBL `ok` bytes. Stream fixtures should
submit unacknowledged lines and call `acknowledge` in FIFO order. Neither an
acknowledgment nor synthetic completion verifies physical motion.

Status observations require a complete ordered, fresh, finite synthetic record.
Partial/stale/future/out-of-order inputs and B/C disagreement latch a fault.
B/C comparison is in modeled source degrees using each channel's own scale;
its numerical equality threshold is not an allowable physical mismatch.
Reset invalidates pending commands and knowledge of mode/offsets/position.
Further commands remain rejected; reset/status cannot silently recover the
model. A new replay needs explicitly declared synthetic initial conditions.

## Calibration evidence and reproduction

[`thor-calibration-template.json`](../config/thor-calibration-template.json)
keeps ratios, signs, carrier coefficient, signed wrist scales, seven channel
scales/zeros and installed firmware/settings hashes **unknown/null**.
[`calibration_evidence.py`](../src/raftel_arm01/control/calibration_evidence.py)
validates separate unknown/source/assumed/synthetic/physical states. Known
values require state-specific provenance; physical records require instruments,
conditions, UTC timestamps, hashes and uncertainty. Immutable source revisions,
units, numeric bounds and channel order are checked. Optional exact document
hash checking detects stale evidence bytes. Embedded evidence references/hashes
are format contracts; this validator does not authenticate instruments or
independently verify that physical observations occurred.

All documents must retain `commissioning_status: not_commissioned`; validation
always returns `commissioned: false`, even for a complete physical-format
record. Completing analysis inputs cannot approve motion, limits, independent
stop behavior or commissioning. No driver/firmware settings export exists.

From an installed development environment in `arm-01`:

```powershell
python tools/thor_controller_replay.py --calibration config/thor-calibration-template.json
python tools/thor_controller_replay.py --script tests/fixtures/thor-controller-replay.json
python -m pytest tests/test_thor_source_conversion.py tests/test_thor_protocol_replay.py tests/test_calibration_evidence.py
```

The CLI uses bounded local JSON only, writes no hardware, and refuses to
overwrite existing report paths. Malformed scripts/evidence fail with exit 2
and no report. The tracked script demonstrates pending/completed separation,
lost acknowledgment and reset invalidation deterministically. Its reset is an
intentionally recorded final fault, not recovery success.

C2/C3/C4/C8 now have tested offline implementations. C1 release-to-core pairing,
C5 synthetic identification, C6 rate/acceleration propagation and a pinned AVR
firmware build remain separate follow-up work. Installed firmware, actual
signs/scales/zeros, effective elbow pitch radius, limits, feedback and physical
motion remain unqualified. See the [earlier source audit](thor-controller-compensation.md)
and [coordinate reconciliation](thor-transmission-coordinates.md).

Upstream references retain their original license obligations. Thor-ROS uses
its upstream repository license; the referenced GRBL source carries GPL-3.0-or-later
notices. The included reference generators are small RAFTEL-written expression/
algorithm checks, not imports of whole source files or a firmware distribution.
No RAFTEL company-wide license is selected here.
