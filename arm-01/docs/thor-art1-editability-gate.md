# Art1 source-editability gate

The original Art1 history is **not repaired**. Keep the validated [static compatibility snapshot](thor-feature-compatibility.md) as the assembly-analysis baseline while migrating a separate copy of the editable source. The next useful migration step is a feature-by-feature semantic reference audit, rather than replacing the first failing sketch reference and accepting an apparently valid final solid.

The owning source is [Art1Body.fcstd at Thor revision 286b081fe6f056d87c379b884781ef77ff6a0159](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/Art1Body.fcstd), SHA-256 `8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a`. The [migration evidence](../hardware/cad/thor-art1-migration-evidence.json) records all 80 ordered Body members, 53 objects with subshape attachment dependencies, and all 25 unique object names consumed by AssemblyArt1. It includes source hashes and the failed isolated native probe. No source file was saved or changed.

## Contract to preserve

`Body.Tip` is `Pocket018`. AssemblyArt1 consumes `Body`, eight named `LCS_*` coordinate systems and sixteen `HoleAxis_*` objects. Preserve the object names, types and intended mechanical frames; labels alone are insufficient. The existing snapshot recipe preserves their saved placements by deactivating support mapping. That is suitable for the static reference, but it does not make those frames respond correctly to a later parametric edit.

The editable migration must establish how each frame is defined: motor seats, bearing seat/axis, bolt axes and mating planes must follow their intended geometry after a deliberate design edit. A new geometric feature numbering is acceptable if the external object-name/frame contract remains correct and each internal attachment has an explicit semantic replacement. A matching zero pose alone does not demonstrate editability.

The critical early dependency chain is:

| Object | Saved dependency or intent |
|---|---|
| `Groove` | `Sketch002` revolved 180° about its V axis; base `Pad001` |
| `Thickness` | `Groove.Face2`, 5 mm inward, Arc join, Intersection false |
| `Sketch003` | Support `Thickness.Face8`, external `Thickness.Edge18` |
| `Pad002` | Profile `Sketch003`, base `Thickness` |
| `Sketch004` | Support `Pad002.Face9`, external `Pad002.Edge22`; 1.7 mm circle radius from spreadsheet |
| `Pocket` | Profile `Sketch004`, base `Pad002` |
| `DatumPlane001` | Support `Pocket.Face7`, saved local attachment offset −20 mm |
| `Sketch005` | Support `DatumPlane001`, external `Pocket.Edge13`; circle center coincident with external center, radius 2.95 mm from spreadsheet |
| `Pocket001` | `Sketch005`, label `BoltHeadHousing`, reversed 12 mm pocket |
| `MultiTransform` | Replicates `Pad002`, `Pocket`, `Pocket001` using `Mirrored`/`Mirrored001` |

The evidence JSON supplies the later face/edge dependencies and exact AssemblyArt1 consumers. Do not assume that the first solver error is the first feature with changed engineering meaning.

## New isolated native result

A 2026-11-11 FreeCAD 1.1.4 probe opened only Art1 hidden with separate preferences, set `Thickness.Intersection=True` in memory and force-recomputed. This repeats the earlier thickness workaround while inspecting the saved and rebuilt subshapes more closely. It saves no native file and leaves the pinned source hash unchanged.

| Feature | Saved volume, mm³ | Rebuilt volume, mm³ | Result |
|---|---:|---:|---|
| `Groove` | 1,461,442.434248 | 1,461,439.570011 | Up-to-date, but changed geometry |
| `Thickness` | 320,854.874855 | 320,852.034330 | Up-to-date, but changed geometry |
| `Pad002` | 324,917.608210 | 324,914.758661 | Up-to-date, but changed geometry |
| `Pocket` | 324,798.225041 | 324,914.758661 | Up-to-date, yet volume equals rebuilt base `Pad002` |

The saved `Pocket` removes about 119.383169 mm³ from its saved base. In this rebuilt candidate its measured volume equals the base volume; its edge count changes from 51 to 48. The saved `Pocket.Edge13` is a 1.7 mm-radius circle centered at native `(-31.5,-55,8)` mm. The rebuilt `Edge13` is a BSpline, and no 1.7 mm-radius circular edge remains in that Pocket shape. `Sketch005` then reports its first Coincident constraint malformed, even though its `FullyConstrained` flag remains true. Its radius/circle geometry still exists as cached sketch data.

This rejects the candidate. It also shows why merely replacing `Sketch005`'s old `Edge13` number is insufficient: the intended preceding hole is absent from the regenerated Pocket. The loss of that cut has not been isolated to a single property; inspect the early attachment/profile/operation chain before choosing a repair. The final Body remains cached after the solver failure and is not rebuilt-result evidence. Earlier Boolean symmetric differences of zero likewise did not establish equivalence when volumes differed.

## Bounded migration sequence

1. **Freeze the comparison inputs.** Record source and addon/runtime pins; extract the saved BReps, sketch constraints/expressions, Body sequence, spreadsheet values and 24 datum matrices. Use a fresh working document and separate preference files for every candidate. Preserve the untouched source and operational snapshot.
2. **Isolate early numerical drift.** Compare saved and recomputed `Sketch`, `Pad`, `Sketch001`, `Pad001`, `Sketch002`, `Groove` before thickness. Record the first changed feature and whether solver, attachment or kernel geometry caused it. Do not silently propagate an unexplained discrepancy.
3. **Evaluate one thickness change per branch.** Keep the recorded 5 mm inward design value. Test the existing Intersection workaround separately from any explicit shell reconstruction. Measure geometry against the saved Thickness; reject merely valid but different outputs as exact migrations. A shell redesign belongs to a separately documented design change.
4. **Recover the bolt support/cut semantically.** Inspect the source `Thickness.Face8/Edge18`, `Pad002.Face9/Edge22` and original hole center/axis using their cached geometric fingerprints. Establish the intended planes and projected construction geometry using named datums or spreadsheet-driven dimensions where justified. Recompute `Sketch003→Pad002→Sketch004→Pocket` alone and require the intended hole/cut before proceeding. Do not replace an external circle reference with the nearest edge number.
5. **Recover the head recess and pattern.** After the hole exists, remap `DatumPlane001` and the center of `Sketch005` to that same intended bolt axis while retaining its spreadsheet-linked radius. Rebuild `Pocket001` and both mirror operations. Compare their cut volumes, symmetry and bolt locations before advancing through later pockets/fillet.
6. **Migrate later references in order.** Use the complete support/external-geometry list in the evidence JSON. At each step compare solids and engineering features, then rebuild downstream dependents. For any failed reference, retain its old geometric meaning and identify the new support explicitly; do not accept a cached or empty cut.
7. **Prove behavior after saving.** Save to a new path, close, reopen, force-recompute and check every object's state. Demonstrate a small reversible change to an existing spreadsheet-driven bolt dimension and a relevant frame-driving design dimension, verify the expected dependent feature/frame changes, then restore nominal values and repeat the equivalence checks. The test increments are modeling fixtures, not printer tolerances or approved design changes.
8. **Revalidate assembly and downstream evidence.** Only after single-part acceptance, substitute the candidate into a new sibling-compatible assembly copy. Check all 25 target names and actual installed transforms before whole-assembly recalculation. Regenerate installed geometry and mass/load reports if any accepted geometry changes; preserve earlier reports as prior baselines.

## Acceptance and allowed deviations

For an **exact compatibility migration**, use the snapshot recipe's comparison thresholds as the starting computational gate: one valid non-null solid; no Invalid/Touched states after reopening/forced rebuild; Body volume difference below `1e-6 mm³`; each bounding coordinate below `1e-9 mm`; each datum matrix element below `1e-12`; and both-direction Boolean cut volumes zero in the measured comparison. Also compare COM, intended hole/cylinder axes and feature-operation effects, and inspect a geometric distance/surface comparison where kernel results conflict. These numerical thresholds are comparison settings, not manufacturing tolerances; passing one test cannot override failure of another. No candidate in this study passes the complete gate.

Object/edge numbering changes and updated native property schemas can be accepted when they preserve the semantic geometry, expressions and AssemblyArt1 contract. Do not require an identical ZIP hash, BRep serialization or number of internal faces after a different-kernel rebuild. Record those changes, rather than equating serialization differences with mechanical differences.

An **intentional design revision** may change dimensions, wall geometry or datum positions only with a stated engineering purpose and explicit changed-interface list. Record its geometry deviation, update downstream assembly/frame/mass/load evidence, and assess fit/structural consequences before adoption. It must not be labeled an exact migration. Small unapproved volume drift, a missing cut, deactivated critical datum dependencies, relaxed numerical thresholds, or arbitrary constraint deletion are not acceptable silent deviations.

Neither route establishes printed strength, fastener fit or a fabrication release. The mount/gripper and slicing requirements are handled in the [fabrication gate](thor-fabrication-gate.md); static source editability remains a separate gate.
