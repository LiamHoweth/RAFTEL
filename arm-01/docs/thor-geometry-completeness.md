# Installed geometry completeness correction

The current source-CAD inventory is [thor-mounted-geometry-v2.json](../hardware/cad/thor-mounted-geometry-v2.json), with **518 installed solid leaves**. It supersedes the historical 516-leaf inventory for current analysis without modifying that inventory or its reports. The two added leaves are the two closed wrist belts; all 516 historical rows are preserved exactly, including their IDs, volumes, centroids and recorded native states.

## Cause and evidence

`AssemblyArt4::Model` installs `Belt_GT2_208mm` and `Belt_GT2_208mm001`. Each links the same source `App::Part`, whose physical terminal is `AssemblyArt4::Pad046` (`PartDesign::Pad`), alongside a sketch and datum. The previous walker only reported missing shape observations for `Part::` or leaf `App::Link` types. It silently ignored a directly installed `PartDesign::Pad` whose shape was not in the manually selected native capture. The native auditor itself can select that Pad; the error was in coverage detection and the resulting selection list.

The [supplemental FreeCAD capture](../hardware/cad/thor-wrist-belt-native-validation.json) restored the compatible assembly with the unchanged pinned `AssemblyArt4.FCStd`, inspected only `AssemblyArt4::Pad046`, and checked topology. It completed with no errors, no source saves and no recompute. The Pad is a valid non-null single solid with volume **2013.9894452343387 mm³** and raw Shape COM `(-13.32021940479536, -2.9999999999999853, 42.95770758036233)` mm. Its `Touched` state is retained. A separate read of the exact saved BREP in the [moving-mass evidence](../hardware/cad/thor-moving-mass-evidence.json) independently agrees; neither observation proves editable history or manufactured belt dimensions.

The existing verified Shape-frame rule applies: the raw Pad COM already includes its own Placement, so only link/group ancestor transforms are applied. The two native-CAD world COMs are approximately `(0.010777360, -0.0235, 0.521087843)` m and `(-0.012285669, 0.0235, 0.521523120)` m. There is one source solid and two physical installed instances, not a new source solid for each belt.

## Coverage after correction

The walker now records terminal-type counts and distinguishes known support objects from missing geometric evidence. It recognizes datum coordinate systems/lines/planes/points, sketches and Assembly4's specifically named `Variables` object. Every other terminal without shape observations is reported as an error, including unfamiliar types. It still stops at Bodies instead of counting their entire history, preserves repeated link instances and deduplicates editor-group aliases.

| Reachable terminal category | Count | Treatment |
| --- | ---: | --- |
| Installed positive-solid leaves | 518 | Geometry retained once per physical instance |
| Observed zero-solid `Part::Part2DObjectPython` wire | 1 | No physical volume assigned |
| Datum coordinate systems | 128 | Explicit support exclusion |
| Datum lines | 87 | Explicit support exclusion |
| Sketches | 4 | Explicit support exclusion |
| Assembly4 Variables | 7 | Explicit support exclusion |

The same 14 hidden procedural inputs are excluded beside their installed outputs. The corrected traversal has no missing object records or unhandled geometric terminals. Independent root-to-leaf traversal corroborated these counts and found no additional omitted terminal solids. This establishes coverage of the pinned assembly's installed CAD tree under the stated grouping rules; it does not prove the CAD contains every manufactured component, cable, lubricant or accessory.

## Reproduction and regression checks

The extractor accepts repeated shape supplements, so the complete prior metadata, prior selected-topology capture and belt capture can be combined without a new full-assembly run:

```sh
python tools/extract_thor_geometry.py /path/to/Thor-reference/freecad-src \
  --native-report /path/to/compatible-metadata.json \
  --shape-report /path/to/compatible-selected-topology.json \
  --shape-report hardware/cad/thor-wrist-belt-native-validation.json \
  > /path/to/new-geometry-extraction.json
```

The resulting `native_installed_instances` has 518 leaves, empty missing/error lists and explicit terminal-type counts. The compact v2 artifact preserves the historical rows and carries the old inventory hash, both prior-capture hashes, the supplemental capture hash and a canonical merged-report hash in its provenance. Runtime/master identity checks guard each overlay; the unchanged source-manifest requirement still applies.

Regression tests exercise a directly installed Pad missing its shape, a retained positive-volume Pad, datum exclusions, unknown types, the narrowly identified Variables object, exact historical row preservation and both new belt IDs against the native validation report. The [moving-mass study](thor-moving-mass-closure.md) owns belt mass/material assumptions; a CAD volume alone does not supply belt mass or its dynamic model.
