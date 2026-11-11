# Thor wrist differential handedness

The pinned CAD arrangement supports **`s=+1` as the intended ideal phase** when both side-shaft angles are expressed about common native **+Y** and positive tool roll is about native **+Z**. The [native diagnostic](../hardware/cad/thor-wrist-handedness.json) and the read-only [probe](../tools/probe_thor_wrist_contact.py) establish arrangement and small-angle interference evidence. They do not establish exact conjugate meshing, command polarity, backlash or manufactured performance.

Using the [membership study's](thor-wrist-mechanism.md) coordinates:

```text
alpha_negative_y = q5 + 2*q6
alpha_positive_y = q5 - 2*q6
```

The `+q5` term is the common carrier rotation. At zero roll both side shafts must follow a rigid fold of the entire differential. The opposed upstream controller coordinates must be reconciled separately; a signed CAD axis convention is not motor wiring calibration.

## Direction from the actual arrangement

The source is [Thor revision 286b081](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src). The diagnostic records byte hashes for the master assembly, wrist assembly and both gear source files. Native raw link shapes were carried through the master wrist placement, using the established [shape-frame rule](thor-geometry.md). Source files were neither recomputed nor saved.

The central gear/plate final solid lies entirely above the fold-axis plane: world `z=567.3…620.0 mm`, versus the fold line at `z=556 mm`. The negative-side pinion occupies negative Y, `y=-39.4…-27.0 mm`; the positive-side pinion occupies `y=27.0…39.4 mm`. All nearest-shape witness locations are therefore above the fold plane, at negative or positive Y respectively. The native report contains the point pairs and supporting shape entities. A zero shape distance alone cannot distinguish touching from intersecting solids.

At an ideal pitch point relative to the fold/roll intersection, let `r=(0,y,z)` with `z>0`. For unit positive roll, the plate's local tangential X velocity is `(+Z × r)_x=-y`. For positive common-Y side rotation, the pinion's tangential X velocity is `(+Y × r)_x=z`. Consequently the negative-Y pinion must rotate in positive common Y, and the positive-Y pinion in negative common Y. The saved 15/30 tooth intent gives magnitude 2 in the ideal differential. The earlier `s=-1` alternative reverses these contact velocities.

This selects an ideal sign from spatial arrangement and external meshing. It does not infer an exact 2:1 velocity ratio from arbitrary tooth-envelope witness points: those points are not established pitch points.

## Native small-angle interference diagnostic

The probe copies saved shapes in memory and rotates the plate about +Z through `(0,0,556) mm`. Each pinion is rotated about the common +Y line through that same point. It compares `s=+1` and `s=-1` for `q6=±0.25°`, with `q5=0`. A point on the roll axis can be chosen anywhere along that line; using z=556 rather than z=577.5 produces the same rotation.

| Plate roll | Phase candidate | Negative-Y intersection mm³ | Positive-Y intersection mm³ |
| --- | --- | ---: | ---: |
| 0° | saved pose | 0.180303 | 0.307374 |
| +0.25° | `s=+1` | 0.177545 | 0.305113 |
| −0.25° | `s=+1` | 0.182120 | 0.209115 |
| +0.25° | `s=-1` | 9.231727 | 0.153965 |
| −0.25° | `s=-1` | 0.239906 | 9.973732 |

The intended sign preserves roughly the existing small interference in both directions. The reversed sign produces a large penetration on one side for each direction; considering both sides and both directions prevents selecting a sign from one favorable separation. These are local diagnostics, not an optimization, full rotation sweep, clearance acceptance test or contact-force calculation. Individual overlapping-volume values are kernel-dependent geometry calculations, not manufacturing tolerances.

## Why exact gear closure remains open

The saved pitch angles are complementary, 26.565° and 63.435°, but pinion and plate modules are 2.59 and 2.85 mm. In the pinned [legacy Gears generator](https://github.com/looooo/freecad.gears/blob/ffe86c85e8061546a3fbaa598993d8e1be2b0de2/freecad/gears/features.py), `reset_origin=True` puts the inferred pitch apex at local `z=module*teeth/(2*tan(pitch_angle))`. Applying the saved body/link/world transforms gives approximate apices:

| Source instance | Inferred pitch apex in native world mm |
| --- | --- |
| Negative-Y small gear | `(−0.000066, −0.549913, 555.999985)` |
| Positive-Y small gear | `(−0.000068, +0.549913, 556.000000)` |
| Central gear/plate | `(0, 0, 556.125048)` |

The inferred apices do not coincide, and the saved solids already intersect. These facts prevent claiming a validated exact conjugate mesh from the source alone. Module values at different bevel cross-sections also should not be compared as if they were two coplanar spur gears. Retain the intended 15/30 ideal relation for conditional analysis, and inspect or revise the detailed tooth geometry before deriving contact loads or releasing fabrication.

The wrist mass study may select `s=+1` as the source-supported intended arrangement and retain `s=-1` as an alternate-sign sensitivity. Full holding demands remain unresolved where motor internals, traveling belts, race motion or jaw configuration are not modeled; selecting a phase does not fill those missing physical inputs.

## Reproduction

Use the already documented isolated FreeCAD 1.1.4 environment, pinned Fasteners and legacy Gears addon, and a compatible copied master with its sibling files. Set these environment variables before passing `tools/probe_thor_wrist_contact.py` to `freecadcmd`:

```text
PYTHONNOUSERSITE=1
RAFTEL_RUN_THOR_WRIST_CONTACT=1
RAFTEL_THOR_WRIST_SOURCE=/path/to/compatible-copy/freecad-src/Assembly.FCStd
RAFTEL_THOR_WRIST_REPORT=/path/to/new-report.json
```

Pass unique `-u`, `-s` and `--log-file` paths, and the two addon directories via `-M`; provide empty stdin. The script rejects pre-existing open documents to prevent native document-name collisions, refuses to overwrite an existing report, checkpoints progress after each native operation, closes only documents it opened, and reports `audit_status=complete` only after all ten Boolean comparisons. A process exit alone does not establish completion. The JSON's `errors` must be empty. Native startup can emit historical inertia-frame warnings; those do not replace the explicit selected-shape validity checks recorded in the report.
