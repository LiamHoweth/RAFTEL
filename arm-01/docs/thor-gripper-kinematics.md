# Thor jaw linkage and parallelism gate

The pinned source supports an **intended symmetric parallelogram gripper**, with a conditional ideal motion model. The saved assembly is not a solved closed linkage: the driven-arm tips miss their corresponding finger pivot axes by **0.17144 mm left and 0.15272 mm right** in the jaw plane. The auxiliary-arm pivots coincide to numerical precision. Consequently, neither its valid static solids nor this ideal model proves physical jaw parallelism, usable stroke, servo calibration or payload retention.

The [native extraction](../hardware/cad/thor-gripper-kinematics.json) records exact source hashes, datum positions, cached contact-face geometry and those residuals. It uses Thor revision [286b081](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src), read without recomputing or saving. Measurements below are CAD source dimensions, not measurements of manufactured parts.

## Geometry and source frame

Use `GripperBot::Body` local XYZ, millimetres in the source. Jaw motion lies in XY with revolute axes parallel to Z. This frame differs from world wrist/ROS frames; transform it explicitly before using jaw positions in whole-arm loads.

| Source item | Native evidence | Consequence |
| --- | --- | --- |
| Auxiliary base pivots | `GripperBot/LCS_Arm1`, `LCS_Arm2`: `(±6,51,14.5)` | Two fixed base axes. |
| Passive driven pivot | `GripperBot/LCS_PassiveArm`: `(14.5,32.5,14.5)` | Nominal right geared-arm pivot. |
| Active pivot | Saved active assembly axis transformed into this frame: `(-14.515,32.5)` in XY | The servo/horn chain differs by 0.015 mm from symmetric `-14.5`. This is preserved, not silently repaired. |
| Auxiliary links | `GripperArm/LCS_GripperArm` to `LCS_GripperArm_1`: 35 mm in XY | Equal links on both sides. |
| Driven links | Active tip `(35,0)`; passive tip `(34.7391153,4.2654270)` relative to its pivot | Both have 35 mm planar length; passive part has a built-in 7° tip direction. |
| Finger pivot axes | `GripperFinger/HoleAxis_1`, `HoleAxis_2`: `(4,4)` and `(12.5,22.5)`; duplicate axes on the opposite face | Pivot separation vector `(8.5,18.5)`, length 20.359 mm. |
| Geared arms | Both `involutegear` definitions have 26 teeth, module 1.1, saved pitch diameter 28.6 mm | Ideal external mesh has opposite equal angular increments about common +Z; installed mesh/zero phase remains unverified. |
| Contact plane | Cached `GripperFinger/Body` Face1: x=18.5, normal +X, area 679.658 mm² | Mirrored fingers have opposing parallel flat contact planes at the saved pose. This is an identified face, not proof the whole jaw is collision free. |

The nominal right base vector from driven to auxiliary pivot is `(-8.5,18.5)`; the mirrored finger pivot vector is identical. Together with equal 35 mm links, this defines an uncrossed parallelogram branch. The left side mirrors it. The source assembly manually places fingers and links; its `AttachedTo` expressions do not enforce both loop closures. The active saved phase is about 0.2796° away from outward horizontal, while the passive arm's transformed tip is about 0.2500° away. Their tip errors therefore cannot be interpreted as actual clearances or elastic preload.

## Explicit ideal motion

[`IdealThorGripper`](../src/raftel_arm01/kinematics/thor_gripper.py) chooses **nominal symmetric** driven pivots `(±14.5,32.5)` and auxiliary pivots `(±6,51)`, equal links `L=35 mm` and constant finger orientation. Its `q` is a mathematical closing coordinate from outward-horizontal links. It is not an MG995 shaft angle, command polarity, pulse width or calibrated installed zero.

For side `s=-1` left and `s=+1` right:

```text
A_s(q) = (s*(14.5 + 35*cos(q)), 32.5 + 35*sin(q))  # driven endpoint, mm
B_s(q) = (s*( 6.0 + 35*cos(q)), 51.0 + 35*sin(q))  # auxiliary endpoint, mm
finger translation from nominal q=0 = (s*35*(cos(q)-1), 35*sin(q)) mm
gap(q) = 70*cos(q) mm
```

Both finger-pivot vectors are constant, so the identified contact planes remain parallel **within this ideal branch**. The gap is 70 mm at q=0 and 35 mm at q=60°. These are analytical geometry examples, not usable opening ratings. The source's saved parallel contact planes are also 70 mm apart even though the driven tips are misaligned; matching that one gap does not solve the actual linkage.

The implementation evaluates `0 <= q < pi/2`, an explicit study interval that avoids the parallelogram's collinear toggle and excludes nominal face coincidence. This is not a physical travel limit. It returns gap, gap derivative, finger translations/derivatives and both endpoint pairs. With equal tooth counts, the two driven arms rotate in opposite common-Z senses as q increases. An actual servo-to-q relationship still needs horn phase, meshing and range/stop evidence. Finite-difference derivatives and virtual-work checks verify the declared mathematical coordinate only.

Changing jaw opening moves finger masses by the above translations and rotates link/gear masses. The existing wrist load report continues to freeze the saved jaw pose; this jaw model is not silently inserted into its mass ledger. Before doing that, reconcile each pivot/phase and the ownership of horns, screws, nuts and bearing races. No mass is removed or counted twice by this new standalone evaluator.

## Reproduction and acceptance

`tools/probe_thor_gripper_freecad.py` reads six pinned native files and inspects only five cached source Body shapes. It rejects an existing output path and never saves CAD. In the separately installed FreeCAD console, set:

```sh
RAFTEL_RUN_THOR_GRIPPER_PROBE=1
RAFTEL_THOR_GRIPPER_SOURCE=/path/to/pinned/freecad-src
RAFTEL_THOR_GRIPPER_REPORT=/path/to/new-report.json
```

Run that script with the pinned historical Gears addon registered through `-M`, as described in the [compatibility study](thor-assembly-compatibility.md). Its source hashes and full local data let another probe reproduce the result without depending on transient face indices alone. Face indices refer to this exact pinned BREP.

The acceptance gate is to reconcile the source axes/phases in a derived working copy, enforce both closed loops and the equal/opposite gear relation, then check multiple jaw positions against independent geometry. Preserve originals and record any altered dimensions. Test parallelism across the proposed stroke, joint/gear/body interference, physical stops, actual pad contact, servo range/current/thermal duty and gripping force before fabrication or powered operation. No jaw stroke or force is released by this analysis.
