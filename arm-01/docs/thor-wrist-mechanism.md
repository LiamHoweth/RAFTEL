# Thor wrist moving-body membership

**Current analysis:** the [v2 inventory](thor-geometry-completeness.md) and [moving-mass correction](thor-moving-mass-closure.md) supersede this historical516-leaf ledger with518 leaves, adding two belts and four input-shaft motion assignments. The66 Art56 assignments below remain applicable.

The pinned native assembly supports a **component-specific conditional gravity model**, not a verified articulated mechanism. The [membership ledger](../hardware/cad/thor-wrist-membership.json) accounts for all 516 mounted leaves: 450 upstream leaves retain their existing joint assignments; the 66 Art56 leaves separate into 7 fold-carrier leaves, 47 tool/roll leaves, 10 side-shaft rotor leaves and 2 bearing COM approximations. No original CAD placement or geometry is changed.

## Evidence and frame

The owning source is [AssemblyArt56.FCStd at Thor revision 286b081](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/AssemblyArt56.FCStd). The ledger records its SHA-256, the mounted-geometry SHA-256, every exact instance ID and the saved `AttachedTo` string for every Art56 leaf. Attachment strings and recursive placement expressions establish mounting intent; Assembly4 static attachments are not revolute or differential constraints. Shape validity and zero-pose axis evidence come from the existing native audit and [geometry study](thor-geometry.md).

All coordinates here are native CAD world coordinates in metres. The fold axis is +Y through `(0,0,0.556)`. The roll axis at zero pose is +Z through `(0,0,0.5775)`, carried by fold motion. Native-to-ROS conversion is `Rz(-pi/2)`, giving `(x,y,z)_ROS=(y,-x,z)_CAD`. These are unsigned geometric axis lines with an explicitly chosen positive coordinate; command polarity is uncalibrated.

## Actual attachment chains

| Model class | Exact mounted roots / supporting attachment |
|---|---|
| Fold carrier, 7 leaves | `Art56MotorCoverRing_Art56MotorCoverRing`; `CommonBearingFixThrough_CommonBearingFixThrough` attaches to its `LCS_BearingFix`; `Nut001`, `Nut002`, `Nut005` attach to ring hole axes; `Screw002`, `Screw003` attach to the bearing fix. |
| Roll/tool, 47 leaves | `Art56GearPlate_Art56GearPlate` attaches to ring `LCS_BigGear`. `GripperBot_GripperBot` attaches to plate `LCS_Gripper`; top, servo, horn, active/passive arms, two links, fingers and their hardware descend from the plate. Plate nuts `Nut`, `Nut003`, `Nut004` and central `Screw` are included. The source jaw configuration is held fixed. |
| Negative-Y rotor, 5 leaves | `Art56SmallGear_Art56SmallGear` attaches to ring `LCS_SmallGear2`; `Screw001` attaches to its hole axis; the two mounted `Collar5mm` leaves attach through `LCS_Collar`; `GT2x40PulleyM4` through `LCS_Pulley`. |
| Positive-Y rotor, 5 leaves | `Art56SmallGear_Art56SmallGear001` attaches to ring `LCS_SmallGear1`; `Screw004`, the two `Collar5mm001` leaves and `GT2x40PulleyM005` form the corresponding shaft stack. |
| Bearing COM only, 2 leaves | `Bearing_625ZZ001/Compound001` attaches to plate `LCS_Bearing`, with COM on roll axis at z=0.580. `Bearing_625ZZ002/Compound001` attaches to ring `LCS_Bearing`, with COM on fold axis at y=-0.0005,z=0.556. Whole compound orientation is not resolved into races/cage. |

The complete exact IDs are in the ledger, including `Group003/Screw026` and both collar leaves. There are no unmatched Art56 leaves. Assigning every Art56 leaf to the same roll body would wrongly move the ring, clamps and side shafts with q6.

## Ideal handedness selected; physical calibration remains open

The [transmission study](thor-transmission-study.md) establishes 15/30 bevel teeth and 20/40 belt teeth. The two small bevel gears spin about the fold-axis line; their CAD attachment parent does not make them rigid parts of the carrier. Each attached pulley, collar and locking screw follows its side shaft. Their CAD COMs have small eccentricities, so preserving their saved zero phase matters even for gravity.

For a conventional ideal 15/30 bevel differential, expressed about a **common native +Y axis**, a consistent candidate relation is:

```text
alpha_negative_y = q5 + s*2*q6
alpha_positive_y = q5 - s*2*q6
s = +1 is source-supported ideal arrangement; -1 retained as alternate-sign sensitivity
```

At q6=0 both side shafts advance by q5: rigidly rotating the entire differential is a necessary consistency case. The controller convention `u=-q5+2*q6`, `v=q5+2*q6` uses opposed shaft coordinates or another sign convention; treating both u and v as native +Y rotations fails that case. The physical motor belt stage adds a magnitude factor 2 but does not establish shaft assignment, polarity or routing. Preserve the existing conditional rotor-to-joint map until these references are reconciled.

The [native handedness diagnostic](thor-wrist-handedness.md) now supports `s=+1` for the intended source arrangement; `s=-1` remains sensitivity. Existing interference and inferred pitch-apex offsets prevent exact conjugate-mesh acceptance. Neither phase verifies backlash, manufactured geometry or firmware calibration. A mass total can be complete while a full articulated gravity result remains conditional.

The central bearing COM follows fold motion and is unchanged by roll because its COM is on the roll axis. The fold bearing COM lies on the fold axis and is unchanged by either wrist coordinate. This supports a whole-bearing **COM approximation for gravity**, not rigid race ownership, rotational inertia, friction or contact analysis. The central screw is assigned to the plate by its saved attachment; its essentially on-axis COM makes roll phase immaterial to this gravity approximation.

## Scope limits and next evidence

The upstream motor bodies retain their existing assembly mass membership. Motor-internal rotors, bearing races and belt material circulation are not extracted into new inertia bodies. A belt circulating along a fixed path has a fixed spatial COM under the uniform-belt approximation. The gripper servo and all jaw links remain at the saved jaw pose; varying jaw opening requires another linkage model.

The wrist-lane request for the official [assembly instructions](http://thor.angel-lm.com/documentation/assembly/) failed to fetch (timeout/TLS handshake failure), so this wrist classification adds no website-derived mechanism evidence. A separate request succeeded in the elbow lane; the [elbow mechanism study](thor-elbow-mechanism.md) records that limited website evidence and its version differences from the pinned CAD. The native wrist mounting evidence remains reproducible without that page. The [handedness probe](thor-wrist-handedness.md), [moving-mass closure](thor-moving-mass-closure.md) and [jaw study](thor-gripper-kinematics.md) provide the subsequent source/ideal-model evidence. Exact gear contact, saved jaw-loop closure, race separation for inertia and physical calibration remain open. No actuation or manufacturing qualification is claimed.
