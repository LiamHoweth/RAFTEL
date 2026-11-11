# Thor remote elbow transmission evidence

The elbow is driven remotely from **Art1**, through a 20-tooth GT2 pulley and an open belt to the smooth Art3 drum. The upper arm carries the tensioners. Consequently, an ideal elbow drive model must include shoulder motion; a standalone constant rotor-to-q3 ratio omits the moving carrier. The exact effective drum pitch radius, installed routing sign and available belt force remain unverified.

This is source CAD inspection and a conditional mechanical model, not physical validation. The pinned source is Thor `286b081fe6f056d87c379b884781ef77ff6a0159`. Object paths, source hashes, extracted surfaces, attachments and uncertainties are recorded in [thor-elbow-evidence.json](../hardware/cad/thor-elbow-evidence.json). See [thor-transmission-study.md](thor-transmission-study.md) for the other axes and supplier limitations.

## Source-supported geometry

| Item | Evidence | Interpretation |
|---|---|---|
| Input motor | `AssemblyArt1/Nema17_GearBox003` attaches to `Art1Body#LCS_Motor3` | Motor housing remains on Art1 when the shoulder moves. |
| Input pulley | `AssemblyArt1/Pulley_GT2x20_Modified001` attaches to that motor's `LCS_Nema17_Gear` | 20 teeth, GT2 nominal 2 mm pitch; nominal pitch radius `r_m = 20×0.002/(2π) = 0.006366197724 m`. The native solid's 6.1 mm tooth-envelope arcs are not its pitch radius. |
| Shoulder/input alignment | Art1Body motor3 and shoulder-bearing datums both have local `x=0, z=98 mm` | Source intent is input pulley coaxial with shoulder. Restored compatible Art1 pulley axis differs from nominal by about 0.0004 mm radially and 6e-7 in axis-vector components. These CAD residuals are not installed alignment tolerances. |
| Drum | `Art3Pulley/Sketch` revolution has radial side at 37 mm, flange at 40 mm | Smooth surface, not a tooth-counted output timing pulley. |
| Output attachment | `AssemblyArt3/Art3Pulley_Art3Pulley` attaches to `Art3Body#LCS_Pulley` | Drum follows the elbow moving body. |
| Tensioners | Two `Art3TensionerBody` links attach to `Art2BodyA#LCS_Tensioner1` / `LCS_Tensioner001`; pulleys attach to their `LCS_TopShaft` | Idlers belong to the rotating upper-arm carrier, not Art1. Saved body attachment offsets are -15 and +15 mm along their respective attachment-local x axes. These are nominal settings, not verified adjustment range or pretension. |
| Belt | Cached `AssemblyArt2/Fusion154001`, linked as `GT2_Belt_Art3001` | Raw belt-model axes at `(x,z)=(0,201)` and `(0,361)` mm give 160 mm center spacing. Envelope is 6 mm wide and 1.5 mm thick; drum annulus spans 37–38.5 mm, motor annulus 5.5–7 mm. |

The [official BOM](http://thor.angel-lm.com/documentation/bom/) lists one 1000 mm **open** GT2 belt, 6 mm wide, in addition to the two closed wrist belts. Purchase length is not installed free length. The [official assembly page](http://thor.angel-lm.com/documentation/assembly/) identifies its interactive manual as a test-version Thor v2 guide and notes that videos may show older versions; those guides do not override the pinned native geometry.

The cached belt wraps below the motor, bends near two tensioners, follows the outer sides of the drum and terminates near the drum top. No crossed strand appears in the cached envelope, supporting a same-sense route as the initial analytical candidate. However, the exact clamp/termination and real routing sign need confirmation. The cached belt's deflection arcs have centers around `x=±17.73797 mm`; the placed idler axes are around `x=±14.5 mm` in the upper-arm frame. Their arc radii also differ from the native idler's 6 mm body radius. This envelope is therefore unsuitable for exact wrap-angle, tangency, contact-pressure or pretension calculations.

## Moving-carrier relation

Use consistent positive physical axes for both pitch joints. Let `q2` be shoulder rotation relative to Art1, `q3` the drum/elbow rotation relative to the upper arm, and `phi` the elbow gearbox output-pulley rotation relative to Art1. Let `R_p` be the actual effective drum pitch radius and `s` the routing sign (`+1` is the same-sense candidate).

Under a constant-radius, fixed-routing, no-slip idealization, angular increments satisfy:

```text
K = R_p / r_m
phi - q2 = s K q3 + constant
phi = q2 + s K q3 + constant
alpha_rotor = g3 phi + constant, with supplier nominal g3 = 5.18
```

The shoulder term comes from observing the input pulley in the upper-arm carrier: its relative rotation is `phi-q2`. Coaxial input and shoulder axes make this ideal velocity relation independent of absolute shoulder angle. A fixed elbow requires the remote output pulley to follow shoulder increments, `dphi=dq2`; holding the remote output fixed instead gives `dq3=-s dq2/K`. This is not evidence that upstream controller coordinates already implement that compensation. Controller joint labels, homing signs, gear direction and physical relative joint angles must be reconciled before using these equations for commands.

The pinned [Thor-ROS `write()` implementation](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_controller/src/thor_interface.cpp) independently forms `art2` from joint command 2 and `art3` from joint command 3, then sends `B=C=art2`, `D=art3`; that function contains no shoulder-to-elbow compensation. Likewise [legacy Asgard](https://github.com/AngelLM/Asgard/blob/30bf2f8850670f728a0f4c3e2e5d22db4f57d8c6/asgard.py) sends B/C only in `FKMoveArt2` and D only in `FKMoveArt3`. This source-code cross-check does not establish firmware behavior or mechanical coordinate semantics. It leaves a concrete reconciliation gate instead of silently treating controller degree values as relative physical elbow angles.

The ideal static mapping follows virtual work. For actuator coordinates `(q2, phi)` and physical generalized gravity loads `(tau2, tau3)`:

```text
T_phi = s tau3 / K
T_shoulder = tau2 - s tau3 / K
belt tension difference magnitude = abs(tau3) / R_p
```

These are signed, lossless transmission efforts. They neither determine load sharing between the two shoulder motors nor belt pretension, peak strand tension, bearing load, clamp capacity, tooth-jump limit or available running torque. Rotor-side ideal elbow effort is `T_phi/g3`; directional efficiency must be handled separately and must not be fabricated from a holding-torque number.

## Effective radius and remaining gates

`37 mm` is the CAD contact-surface radius, **not** an established belt pitch radius. Belt cord position, tooth/contact orientation, belt compression and clamp geometry affect `R_p`. A sensitivity calculation can place `R_p` within the modeled 37–38.5 mm annulus only under the explicit assumption that the installed pitch line lies inside that envelope. That is an analytical scenario range, not a measured tolerance. The nominal 5.18 gearbox multiplied by the radius ratio is therefore conditional, never a verified fixed reduction.

Before selecting a motor, belt, clamp or printed part, identify the actual belt specification and pitch-line location; inspect both terminations and route; establish tensioner position, pretension and wrap; then measure small unpowered angular increments across multiple shoulder/elbow poses. That later physical work is not performed or authorized by this analysis. Torque-speed, thermal, fatigue, material anisotropy and friction/efficiency inputs remain separate missing capacity evidence.

## Extraction check

FreeCAD 1.1.4 read only the saved belt BREP and separately restored/recomputed compatible `AssemblyArt1` with the already pinned Fasteners and legacy Gears addons. The inspected remote motor and pulley were `Up-to-date`. No original CAD was saved and no whole-assembly recomputation was needed. Raw BREP surface radii, axes, endpoints and hashes are included in the evidence JSON so the schematic routing limitations remain inspectable.
