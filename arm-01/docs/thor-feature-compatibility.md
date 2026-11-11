# Thor native feature compatibility and static Art1 reference

Checked 2026-11-11 with FreeCAD 1.1.4R20260928 against the original [Thor revision `286b081fe6f056d87c379b884781ef77ff6a0159`](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159). All experiments used separate files and configuration paths. The original editable source was never saved or modified. This is CAD evidence, not physical validation.

## Isolated failure identification

There are three `PartDesign::Thickness` objects in the 57 original native documents. Their exact saved settings and isolated forced-recompute results are:

| Document | Feature input | Saved setting | FreeCAD 1.1.4 forced result |
|---|---|---|---|
| `Art1Body.fcstd` | `Groove.Face2` | 5 mm inward, Arc join, Intersection false | `Thickness` becomes Invalid; final Body remains Touched with its old cached shape |
| `Art2BodyB.fcstd` | `Pad.Face6` | 5 mm inward, Arc join, Intersection false | Thickness and Body Up-to-date; valid one-solid Body, volume approximately 257,430.427587 mm³ |
| `BaseBoxBody.FCStd` | `Pad.Face8` | 5 mm inward, Arc join, Intersection false | Thickness and Body Up-to-date; valid one-solid Body, volume approximately 341,664.498707 mm³ |

The report is [`thor-feature-compatibility-report.json`](../hardware/cad/thor-feature-compatibility-report.json). It includes the cached, immediately restored, and forced-recomputed measurements, feature states, and actual runtime version.

The original Art1 `Thickness` and final `Body` saved BReps are valid solids. **A valid cached shape is not proof of successful feature recomputation.** The failed feature retains its valid old shape, so checking `Shape.isValid()` alone would produce a false success. Read object states and dependency failures as well.

## Rebuild attempts that were not adopted

Direct OpenCascade thickness construction on both the exact cached Groove and regenerated Groove failed at tolerances 0.001, 0.0001 and 0.00001 mm. Retaining the original Groove shape did not by itself fix Thickness. The rebuilt Groove volume differs slightly from its saved input, but the cached-input failure means that difference alone does not explain the kernel failure.

Enabling `Thickness.Intersection` without changing its 5 mm dimension makes that feature Up-to-date. A full forced rebuild then exposes `Sketch005: Sketch with malformed constraints`, with downstream features still Touched and final Body still cached. The sketch uses the old external reference `Pocket.Edge13`; its original constraints/topology need a separate procedural migration investigation.

That Intersection candidate is **not a full repair**. Its rebuilt Thickness volume differs from the cached Thickness by approximately 2.840525 mm³. The kernel returned zero Boolean symmetric-difference volume despite that volume drift; this illustrates why a Boolean result alone is insufficient to claim exact geometric preservation. A test replacing only Thickness with a static feature likewise leaves the malformed downstream sketch unresolved. No such incomplete procedural modification is adopted into the reference snapshot.

## Usable static geometry reference

For assembly geometry extraction, `tools/prepare_thor_compatibility.py` produces a **fresh, separate static native document** from the exact original saved final Body BRep and saved datum placements. It does not repair or discard the original editable source.

The recipe:

- Accepts only the pinned original Art1 file SHA-256: `8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a`.
- Reads the saved Body BRep directly from the ZIP container, without executing the original feature history or third-party proxies. The BRep SHA-256 is `d0ed3dcd293f814b6db11e0e29a22e89a6aa4fe6c8d9f8e5c08e508baec2b9db`.
- Creates a new `PartDesign::Body` named `Body` with one static `FrozenSourceSolid` feature. It preserves all 24 original coordinate-system and hole-axis object names and saved placements; these plus `Body` cover all 25 Art1 targets referenced by `AssemblyArt1`.
- Sets the copied datum supports to Deactivated so obsolete face/edge attachments cannot silently move them during recompute. Their saved coordinate frames are reference data, not recalibrated mechanical axes.
- Rejects nonidentity source Body placement rather than guessing whether a transform has already been applied.
- Requires unused native-output and JSON-report paths and leaves the original source bytes unchanged.
- Saves, reopens and force-recomputes the new document, then checks every object state, solid validity/count, volume, bounds, datum matrices, and Boolean symmetric difference against the saved source shape.

The native result is a valid single solid with volume **298,648.10044680396 mm³**. Before/prepared/reopened volume and bounds match exactly in the measured run; symmetric difference is 0 mm³; all 24 datum matrices match; all objects are Up-to-date. The numeric matrix/bounds checks are computational comparison thresholds, **not manufacturing tolerances**. The source hash remains unchanged.

This establishes a usable **static shape and frame snapshot** for the original saved pose. It does not establish that the original 0.19 procedural model fully rebuilds in 1.1.4, nor validate mechanical loads, reach, physical fabrication, or arbitrary edits. Keep that distinction in any assembly report and model provenance.

## Reproduce the snapshot

From `arm-01`, choose an original source file and unused output/report paths. Run under the separate FreeCAD console with isolated configuration files:

```sh
export RAFTEL_PREPARE_THOR_COMPAT=1
export RAFTEL_THOR_SOURCE=/path/to/Thor-reference/freecad-src/Art1Body.fcstd
export RAFTEL_THOR_OUTPUT=/path/to/new-snapshot/Art1Body.fcstd
export RAFTEL_THOR_REPORT=/path/to/new-snapshot/report.json
/path/to/freecadcmd -u /path/to/task-user.cfg -s /path/to/task-system.cfg tools/prepare_thor_compatibility.py
```

The output's parent directory must already exist. Inspect the report's `validated_static_snapshot` value and recorded diagnostics; a process exit alone is not evidence. For a separate whole-assembly compatibility copy, substitute this one Art1 file only after preserving the original source, license/provenance and all sibling dependencies. Do not copy it over the upstream checkout. It carries no original procedural edit history; edit that original separately and repeat validation after any design change.

The first verified local candidate is `work/thor-feature-investigation/static-native-verified/Art1Body.fcstd` outside this repository. The repository contains its generator and factual report, rather than a duplicated native binary.

## Remaining procedural gate

The original Art1 editable feature history still needs migration of the thickness algorithm and downstream external sketch references under a compatible CAD/kernel version. That work must independently compare rebuilt final geometry against the saved source, including nonzero volume drift even when Boolean comparisons return zero. Until it passes, label the operational assembly's Art1 geometry as this static compatibility snapshot, not as a fully rebuilt original parametric part.
