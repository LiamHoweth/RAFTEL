# Thor wrist moving-mass closure

The motor and belt investigation supports a more complete **conditional gravity model**, with a concrete correction to the frozen mass baseline. It does not supply a measured internal motor mass partition or a dynamic inertia model. [The evidence record](../hardware/cad/thor-moving-mass-evidence.json) contains saved native BRep hashes, geometry, exact instance paths, motion declarations and assumptions. Original CAD and the original 516-leaf reports remain historical baselines.

## Two omitted belts and four rotating input leaves

The pinned `AssemblyArt4.FCStd` Model group contains `Belt_GT2_208mm` and `Belt_GT2_208mm001`. Both link a prototype `App::Part` containing `Pad046`, a `PartDesign::Pad`. The original selected-shape inventory did not retain that leaf. This was an extraction omission, not evidence that the belts have zero mass. Direct read-only inspection of its saved BRep finds one valid positive solid, volume **2013.989445 mm³**. The corrected inventory therefore has **518 installed leaves**, with all 516 earlier leaves preserved.

At the original **unmeasured 1200 kg/m³ belt density scenario**, these two belt leaves add **2.416787 g each**, or **4.833575 g total**. This changes the modeled mass; preserving the old total while declaring coverage complete would conceal omitted material. Actual belt mass, construction and density remain unknown. The geometry lane owns the separately versioned corrected inventory, and the load integration lane owns its new study. The new additions must not overwrite the original reports.

Four existing leaves also need a motion correction without any additional mass: the `Cut002001` pulley and `Pocket001` grub screw in each installed `Pulley_GT2x20001`/`Pulley_GT2x20002` group rotate about their own input shafts. Their source geometry is not perfectly axisymmetric. Their existing aluminum/steel density masses stay counted once. Leaving these leaves rigidly fixed in Art4 suppresses a small modeled phase-dependent gravity term.

| Input shaft | Common native axis | Zero-pose line point, m | Intended belt destination | Conditional angle about common +Y |
|---|---|---|---|---|
| `Pulley_GT2x20001` | +Y | `(0.024,-0.0279,0.4781)` | negative-Y 40T side pulley | `2*q5 + 4*s*q6` |
| `Pulley_GT2x20002` | +Y | `(-0.024,0.0279,0.4781)` | positive-Y 40T side pulley | `2*q5 - 4*s*q6` |

The source local +Z maps to native +Y for the first input and native −Y for the second. A local-axis implementation must transform the coefficients consistently. These relations assume an uncrossed no-slip 20/40 belt stage and use the side-shaft sign `s` from the [handedness study](thor-wrist-handedness.md). They are ideal geometric coordinates, not motor wiring polarity or calibrated controller commands.

## Why a circulating belt need not become another rotating rigid body

Under the **uniform continuous closed-belt approximation**, material flows around a fixed spatial path. Its gravitational potential is `U = integral_path lambda*g*z ds`. Reparameterizing material phase around that same path leaves the integral and spatial COM unchanged. The belt therefore follows upstream q1–q4 motion but has zero q5/q6 COM derivative under that hypothesis. Rotating the entire cached belt solid with a drive pulley would produce the wrong spatial path.

The drive and driven shaft centers are fixed in Art4: the two driven axes coincide with the wrist fold line, while the carrier folds around that line. Thus changing wrist phase need not move the belt path in this ideal model. Real tooth discreteness, joints/splices, nonuniform density, tension-dependent deflection, belt stretch and pulley misalignment can violate the uniform fixed-path approximation. This is a stated model assumption, not an experimentally established balance result.

The cached smooth strip is also **not a verified installed belt fit or pitch line**. Its cross-section is 6 mm × 1.5 mm; `volume/(6*1.5)` gives **223.776605 mm** of implied strip centerline length, while its label says 208 mm. It has no modeled tooth profile. The saved envelope is suitable as a declared geometry/COM sensitivity input, but cannot verify a purchased 208 mm belt's length, preload, tooth engagement or motor-stage calibration.

## Motor internals: retain total mass, declare balance

The 34 mm motor asset is a single saved solid (`Chamfer_solid`) combining the external motor envelope and exposed shaft. Its source contains no separate rotor, stator, magnets or winding mass. A motor's real internal materials have different densities; allocating the manufacturer's **0.230 kg whole-asset mass** by external CAD volume would invent a rotor mass. The tiny off-axis uniform-volume centroid of the fused asset is likewise not a physical rotor eccentricity measurement.

For static gravity, a **balanced internal rotor** offers a useful conditional closure: if its COM lies on its fixed shaft axis, spinning it changes orientation but not COM or gravitational potential. The housing and on-axis rotor can then retain their combined existing whole-asset mass and fixed aggregate COM proxy; no rotor fraction is required for this phase-invariance result. Both wrist motors remain 0.230 kg each, and all seven manufacturer motor assets remain **2.120 kg total**. Do not add rotor mass on top of an already counted whole motor.

This does not prove that the actual motors are balanced, or that the aggregate CAD COM equals the real combined COM. Without balance evidence, the unmodeled term is proportional to `m_rotor*eccentricity`, which remains unknown. A deliberately coarse sensitivity assumes all of each 0.230 kg asset could rotate within its CAD transverse half-box radius `sqrt(21.15²+21.15²) = 29.9106 mm`. With input phase-coefficient magnitudes 2 for q5 and 4 for q6, the triangle inequality gives summed two-motor magnitudes **0.269857 N·m for q5** and **0.539714 N·m for q6**. These bounds depend on the envelope, listed mass and ideal angle-map assumptions; they are not verified physical bounds or predicted real imbalance. A smaller bound requires evidence for the rotating mass times eccentricity, not a guessed rotor percentage.

Bearing whole-asset COM paths similarly suffice for a declared static gravity approximation when race COMs stay on their axes. Race/cage inertia, friction and contact forces remain unresolved. Jaw pose and servo/gripper internal motion are covered separately by the jaw study. A gravity-only closure must not be renamed complete rigid-body or dynamic closure.

## Reproduction and acceptance

[`probe_thor_moving_mass_freecad.py`](../tools/probe_thor_moving_mass_freecad.py) uses FreeCAD's Part kernel to read selected saved BReps directly from the pinned source ZIP. It opens no CAD document, performs no recomputation, saves no source and needs no workbench addon. It validates all four selected solids and emits their volume, centroid, bounds and hashes.

```sh
RAFTEL_PROBE_MOVING_MASS=1 \
RAFTEL_MASS_SOURCE=/path/to/pinned/AssemblyArt4.FCStd \
RAFTEL_MASS_OUTPUT=/path/to/new-native-mass-report.json \
/path/to/freecadcmd -u /path/to/new-user.cfg -s /path/to/new-system.cfg \
  tools/probe_thor_moving_mass_freecad.py
```

FreeCAD 1.1.4 completed this probe on 2026-11-11. The evidence JSON embeds its result and source SHA-256. New output paths are required; the tool refuses overwriting an existing report. Acceptance for the revised load study is: preserve every prior leaf once; add exactly these two belt leaves; keep all seven manufacturer motor totals; move the four input leaves without changing their masses; evaluate wrist phase through explicit Jacobians; retain full physical holding-demand qualification as unresolved. Internal rotor fractions and inertias remain null rather than fabricated.
