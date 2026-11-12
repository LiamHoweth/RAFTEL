# Source-linked fabrication preparation

The initial checkpoint prepared reviewable source drawings, a printable-asset ledger and
offline observation imports. It does not export meshes, slice parts, qualify
material/fit, repair Art1 history or release fabrication. FreeCAD was unavailable
at that initial checkpoint. The later [Windows native foundation](thor-windows-native-foundation.md)
and [native mesh draft audit](thor-native-mesh-audit.md) provide separate evidence;
they do not qualify these drawings or release fabrication.

## Assets and export variants

[The manifest](../hardware/cad/thor-printable-assets-v1.json) maps **65 installed
printed leaves to 46 unique pinned source assets**. Reconciliation reuses
`thor_load_analysis.build_thor_snapshot` rather than reclassifying purchased
components. Every printed assignment appears exactly once. Source and installed
volumes agree within stated numerical tolerances, and each source file SHA-256
matches [the pinned source inspection](../hardware/cad/thor-baseline-inspection.json).
The manifest binds the v2 inventory, fabrication capture and inspection report by
canonical JSON hashes, so formatting-only changes do not invalidate it, while
changed data does. Its baseline PLA density/half-solid mass field is an analytical
comparison; a 50% whole-part solid fraction is not a slicer infill setting.

The reflected finger is one source asset with two geometry variants. There are
**47 export geometry variants**: 46 nominal source solids and one saved reflected
finger. The reflected installed leaf is
`AssemblyArt56::GripperFinger_sym001/AssemblyArt56::Unnamed1_GripperFinger_mirrored`
inside the complete instance path. Replacing it with a second nominal finger mesh
would silently lose the saved reflection. The manifest leaves exact installed
transform and export hashes unknown rather than inferring them from a COM.

Read-only ZIP/XML inspection of the pinned `AssemblyArt56.FCStd` (SHA-256
`a04836216dcae82eb033c15daba6e41dedb85b03f86ff21e56b77cdff835a473`) corroborates:

- `Unnamed1_GripperFinger_mirrored` takes
  `Unnamed1_GripperFinger_link` as `Source`; its saved mirror-plane base is
  `(0,0,0)` mm and normal `(1,0,0)`.
- That intermediate link points to `Unnamed1_GripperFinger`.
  The mirror and containing `GripperFinger_sym` have identity placements.
- The installed `GripperFinger_sym001` link has a separate saved attachment and
  placement. A proper rotation alone cannot represent the reflection operation.

Those properties establish source intent, not an independently rebuilt BRep.
The [jaw ownership reconciliation](thor-jaw-body-reconciliation.md) owns the
moving-body interpretation. The later [native mesh audit](thor-native-mesh-audit.md)
now captures the actual saved reflected solid separately, with its storage frame,
winding and topology checks. The [printed-copy frame study](thor-printed-inertia-study.md)
now authenticates all 65 cached printed copies in the native master saved-zero
frame, including the reflected finger. Physical bench/world calibration,
continuous surface fidelity, fit and process qualification remain open.

Art1Body is explicitly marked as **unrepaired original history**, with the exact
accepted static snapshot separate. Do not export the failed Intersection candidate
as an accepted repair. Preserve all original CAD and historical reports. The
existing [Art1 gate](thor-art1-editability-gate.md) still applies.

Every asset has an orientation comparison and inspection prompt. These are
unselected candidates, not machine profiles: inspect a real bed-contact face,
layer-sensitive bosses/teeth/retention, trapped support material and tool access.
The actual nozzle, usable area, filament formulation, support process and strength
remain unknown. The source envelope fit excludes supports, brims and keepouts.

## Dimensioned source views and frames

[Base interface drawing](../hardware/drawings/thor-base-interface-v1.svg) preserves
the asymmetric four-point source pattern. Black geometry and a dotted **bounding
envelope** describe `BaseBot::Body002`; the dotted rectangle is not a fabricated
outline. The blue dashed 300 × 320 mm blank is the existing separate proposal.
Plate thickness, clearance-hole selection, clamp spacing and load rating remain
unselected. Every source center is crosschecked against saved cylindrical faces,
and the SVG metadata contains source hashes, coordinates and the identity
`LCS_Bot` datum. Drawing coordinates use `x=source x`, `y=-source y`, placing source
+Y upward. The source hole table is not a square or a six-hole circle.

[Tool interface drawing](../hardware/drawings/thor-tool-interface-v1.svg) shows the
Ø30 male source diameter, Ø31 socket diameter, three Ø3.4 **radial** hole-axis lines
at 120°, source z=−38 mm hole plane and 4.5 mm distance from the −42.5 mm end. The
socket circle is a diameter comparison, **not an assembled clearance overlay**.
The side view is a source cylindrical envelope, not a mesh or reconstructed
cut-section. Both gripper halves form the socket.

The saved mating expression remains:

```text
plate.Placement * plate.LCS_Gripper * AttachmentOffset * gripper.LCS_GripperBot^-1
```

The tool generator converts source datum translations from mm to m, decodes the
saved FreeCAD quaternion as x/y/z/w, and uses the shared `thor_frames` rigid
composition/inverse functions. With the source plate placement factored out,
`plate_source_from_gripper_source` is approximately:

```text
[-0.497641579   0.000000000  -0.867382764   0.014875614]
[ 0.867382764   0.000000000  -0.497641579   0.008534553]
[ 0.000000000  -1.000000000   0.000000000  -0.035000000]
[ 0.000000000   0.000000000   0.000000000   1.000000000]
```

Translation is in metres. This includes the saved +1 mm mating-local z offset and
180° tilt, rather than merely aligning cylinder axes. An independent point-chain
check uses the earlier saved-quaternion evaluator and direct datum operations:
the socket source center `(0,0,17.15)` mm maps to `(0,0,−35)` mm in the plate source
frame; the gripper mating datum `(0,8.5,17.15)` mm maps to `(0,0,−43.5)` mm. These
are saved rigid-frame identities, not measured fit, seating/retention or TCP
calibration. Full-precision source datum matrices and the composed transform are
embedded in SVG metadata.

The drawings were rendered with an isolated local headless Chrome profile and
visually checked for legibility, clipping and overlaps. That is SVG layout QA,
not native CAD, a final exported mesh or physical acceptance.

## Blank measurement records and import validation

[The blank form](../hardware/measurements/thor-fabrication-template.json) contains
one record for each of the 65 installed prints. Slicer/weighing fields are `null`
and fit observations are `[]`; actual profiles and measurements are not invented.
Mass uses kg, dimensions m and density kg/m³. Each row binds an installed ID,
source SHA-256 and nominal/reflected variant. The complete manifest hash prevents
reuse against a different source/model revision.

The runtime module `engineering.fabrication_records` exposes
`measurement_template(manifest)` and
`validate_fabrication_records(data, manifest)`. A partial import is permitted;
the summary reports unreported instances. Each supplied subsection requires an
explicit `evidence_state` (`synthetic` or `observed`) and provenance with
`source`, timezone-bearing ISO-8601 `captured_at`, and `conditions`. Subsections
have independent evidence states, so synthetic weight cannot be compared as an
observed discrepancy against real slicer output.

| Section | Required supplied fields |
| --- | --- |
| `slicer` | Slicer name/version; machine/material-profile and export SHA-256; density; nozzle diameter and layer height; orientation/support description; separate `model_mass_kg`, `support_mass_kg`, `purge_mass_kg` |
| `weighing` | Unique `sample_id`, instrument ID, positive resolution, positive cleaned-part mass, repeat count and `supports_and_purge_removed=true` |
| each `fit` | Distinct feature/location ID, instrument ID, nominal/measured dimension and resolution; sourced minimum/maximum interval or all three requirement fields left `null` |

The validator separates observed slicer **estimates**, cleaned observed masses and
synthetic test values. Support/purge estimates never enter installed mass. One
sample cannot be reused to claim multiple installed parts were weighed; repeated
readings use `repeat_count` on one sample. Partial source hashes, numeric strings,
booleans as schema/numbers, nonfinite values, duplicate IDs, purchased assets,
wrong geometry variants, coarse instruments and incomplete provenance fail.
Fit comparisons near a boundary remain unresolved at recorded resolution.
An interval comparison is not retention, structural or material qualification.

No import modifies the load ledger or grants fabrication/hardware permission.
Changing analytical mass assumptions later requires a separate accepted scenario
with those per-instance observations linked, while historical reports remain
reproducible.

## Reproduction

From `arm-01`, after the normal editable development install:

```powershell
New-Item -ItemType Directory -Path ../.work/fabrication-repro-001
python tools/thor_fabrication_assets.py --output ../.work/fabrication-repro-001/assets.json --svg ../.work/fabrication-repro-001/base.svg --tool-svg ../.work/fabrication-repro-001/tool.svg --measurement-template ../.work/fabrication-repro-001/template.json
python tools/thor_fabrication_assets.py --validate-records hardware/measurements/thor-fabrication-template.json --output ../.work/fabrication-repro-001/blank-validation.json
python -m pytest tests/test_thor_fabrication_assets.py tests/test_fabrication_records.py
```

Choose a previously unused run-directory name. The generation command creates
new candidate artifacts from preserved JSON inputs without FreeCAD or internet;
compare them with the tracked checkpoint rather than replacing old evidence.
All output destinations are resolved and checked together for aliases, input
collisions and existing entries, then created exclusively in UTF-8 with LF lines.
A file created after preflight also causes failure. An I/O failure can leave
partial new outputs; a nonzero exit is an incomplete run and never removes old
evidence. The validation command correctly leaves observed/synthetic masses
unknown. Tests contain explicitly
synthetic filled records and independently check source quantities, volumes,
hashes, coordinate overlays, saved transforms, negative imports and reproduction.

Generated asset/drawing attribution retains AngelLM/Thor contributors, immutable
source revision and CC-BY-SA-4.0 link. Reflection/annotation changes are identified.
The repository-license versus embedded-document-metadata conflict remains an
attribution review gate before derived CAD/export publication. This checkpoint
does not choose a company-wide RAFTEL license.

## Next acceptance gates

1. Reuse the [full 47-variant cached export](thor-full-print-export-plan.md) and
   [host mesh/61-draft review](thor-full-print-mesh-audit.md), including the saved
   reflected finger. Resolve the coarse-native Art23Optodisk boundary and
   transmission-column nonmanifold findings; preserve the separate optodisk
   source-mode drafts. Refresh exports only for changed, accepted geometry.
   Art1 history acceptance remains separate.
2. Supply the real machine/nozzle/material profile and bench/clamp geometry; use
   those inputs for slicing/orientation and full-wrench mount checks. Leave the
   present blank observation form unknown until actual outputs exist.
3. After separate owner authorization for physical work, record coupon/part
   measurements with instruments, resolution, conditions and sourced acceptance
   requirements. No computational result here releases printing or motion.
