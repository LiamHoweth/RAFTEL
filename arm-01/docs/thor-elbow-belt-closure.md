# Elbow belt termination and pitch-line closure

The pinned CAD now establishes the **intended belt-end route and radial screw clamp** more precisely. It still does not establish the actual belt pitch line or a secure physical termination. The [native cached-BRep report](../hardware/cad/thor-elbow-belt-closure.json) preserves those distinctions. No source document was opened, recomputed or saved by the reproducible probe, and no hardware was operated.

## Source and coordinate checks

The owning source is [Thor revision 286b081](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src). SHA-256 guards cover `Assembly.FCStd`, `AssemblyArt2.FCStd`, `AssemblyArt3.FCStd` and `Art3Pulley.fcstd`, plus each inspected BRep. The probe imports the saved final drum, belt and screw shapes; it composes their saved ancestor placements once. The source links have `LinkTransform=False` and identity target `Model` placements.

The following dimensions use the **Art3Pulley Body local frame**, with local Z along the drum axis. This differs from the assembled native +Y pitch-axis convention. The transformed world COMs reproduce the existing installed inventory: belt approximately `(0.034598,-45.000000,313.746006)` mm and drum `(-0.000011,-44.052404,365.355614)` mm. That cross-check guards against applying the link placement twice.

| Feature | Saved source evidence | Meaning |
| --- | --- | --- |
| Drum running surface | Revolution of `Sketch`, radius 37 mm, axial interval z=3..18 mm | Smooth surface; no output teeth or cord pitch line are modeled. Flange radius is 40 mm. |
| Belt-end entry channels | `Sketch001` and 13 mm pocket: channels between x=2.5..5 and x=−5..−2.5 mm from y=29.5 mm toward the rim; tapered portions lead inward | Each straight channel is 2.5 mm wide. This is CAD free space, not a fit tolerance or material allowance. |
| Inner terminal chamber | Same profile opens across x=−11.5..11.5 mm at y=19.5..23 mm | Supports two ends turning inward and overlapping in projection. |
| Cached belt ends | Width occupies z=5..11 mm; terminal strips occupy y≈19.610445..21.110445 and y≈21.298464..22.798464 mm | Two 1.5 mm modeled strips are stacked radially with a nominal gap. The envelope does not show individual GT2 teeth or reinforcement cords. |
| Radial clamp bore | `Sketch002` circle radius 1.7 mm, axis x=0,z=6.5 mm through the +Y rim | Aligned with the stacked ends. This is not an M3 tapped-hole or thread-strength specification. |
| Nut pocket | `Sketch003`/`Pocket002`, hexagon circumradius 3.35 mm, center x=0,z=6.5 mm at y=25.85 mm; 3 mm pocket | Nut insertion/retention intent; actual fit and printed strength unverified. |
| Installed clamp fasteners | `AssemblyArt3::Screw010`, labeled M3x16, and `Nut010`, labeled M3, both attach through drum `HoleAxis_3` | The screw's nominal local Y extent is 21.35..40.35 mm, placing its tip in the outer modeled belt strip. Other drum screws and nuts are not silently reclassified as belt clamps. |

The zero-pose belt/drum Boolean common volume is **0 mm³**, with minimum separation about `1.3e-14 mm` (numerical contact). The screw/belt common volume is **9.825485 mm³**. This undeformed overlap supports a pressing-clamp interpretation; it is **not** solved compression, clearance, preload, tooth engagement or proof of retention. Moving the saved screw or assuming that this interference establishes a safe tightening torque would go beyond the evidence.

The source geometry therefore supports the route: belt wraps around the smooth drum, both ends enter the narrow channels, bend into the inner chamber, and are pressed by the radial screw against the termination region. Actual end preparation, tooth-facing orientation, installation sequence and secure clamping still require inspection. The earlier [belt/idler mismatch](thor-elbow-mechanism.md) remains: fitting the drum at this saved pose does not establish exact idler wrap, route length, changing contact or travel clearance.

## Pitch line and load implications

No exact belt manufacturer or part number, reinforcement-cord position or tooth-contact orientation is encoded in these solids. The 1.5 mm rectangular envelope has no distinguished neutral/pitch line. Consequently `R_pitch` remains **null** in the report. A 37 mm surface or the arithmetic midpoint 37.75 mm cannot be promoted to a verified pitch radius. Even the previously studied 37..38.5 mm interval is conditional on the actual pitch line lying inside that source envelope; it is not a measured tolerance.

Use the existing [parameterized elbow equations](thor-elbow-loads.md) with explicit assumptions. In the no-slip constant-radius candidate, `K=R_pitch/r_driver` and `phi=q2+s*K*q3`. The scenario `R_pitch=37 mm` predicts a 63.306 N **tension difference** for the baseline horizontal 200 g load; it does not establish either individual strand tension or the force carried by each folded end. Do not divide this difference by two to select a clamp. Pretension, contact directions, belt-to-belt friction, tooth engagement, screw contact pressure and the printed chamber's reaction all remain missing inputs.

The most direct later measurement is geometric rather than a guessed cord offset: with shoulder fixed, compare small unpowered drum-relative increments `Δq3` to gearbox-output increments `Δphi`, giving `R_eff=r_driver*abs(Δphi/Δq3)` under the declared no-slip model. Repeat in both directions and several poses to expose backlash, slip or a varying effective radius. A separate fixed-relative-elbow test checks `Δphi/Δq2` for the carrier term. Record actual belt specification, end route, screw setting and tensioner position first; include angular measurement uncertainty. These are proposed supervised measurements, not tests performed here or permission to energize an arm.

Before releasing a clamp or belt load rating, use the actual printed material/profile and belt to establish repeatable end retention, inspect damage/creep, and justify tightening and load conditions. A representative coupon can reproduce the channels, chamber and radial fastener before a full arm print. Acceptance must be tied to a documented strand-load envelope and duty case; this study supplies neither a qualified safety factor nor a pass load.

## Reproduction and limits

From the repository root, use the existing portable FreeCAD runtime, isolated settings and a new report path:

```sh
RAFTEL_RUN_THOR_BELT_PROBE=1 \
RAFTEL_THOR_BELT_SOURCE=/path/to/pinned/Thor/freecad-src \
RAFTEL_THOR_BELT_REPORT=/path/to/new-belt-report.json \
/path/to/FreeCAD.app/Contents/Resources/bin/freecadcmd \
  -u /path/to/isolated-user.cfg -s /path/to/isolated-system.cfg \
  arm-01/tools/probe_thor_elbow_belt_freecad.py
```

The probe requires no addons, rejects changed source hashes and existing output paths, verifies solid validity, and checks source bytes again before writing. This is saved-shape analysis, not parametric-history rebuild or an articulated-contact solver. The official BOM and assembly pages were requested on 2026-11-11 in this lane but timed out; no new website-derived belt specification is asserted. Earlier successful website inspection remains recorded in the companion mechanism study. Physical route polarity, controller compensation and moving actuator capacity remain separate gates.
