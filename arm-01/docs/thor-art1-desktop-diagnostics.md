# Art1 desktop source diagnostics and comparison tooling

The editable Art1 history remains unresolved. This Windows run performed ZIP/XML
source inspection and reanalysis of earlier native measurements. No FreeCAD
executable was found in PATH, and no native recompute, save/reopen, contact check
or repaired CAD candidate was performed. The accepted static snapshot and all
historical evidence remain unchanged.

## Source fingerprint and saved bolt frames

The read-only source is [Art1Body.fcstd at Thor
286b081fe6f056d87c379b884781ef77ff6a0159](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/freecad-src/Art1Body.fcstd),
accessed 2026-11-11. Its SHA-256 is
`8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a`.
It was downloaded to task scratch, checked before inspection and checked again
after inspection. No upstream native asset is vendored or changed.
The pinned [Thor repository license](https://github.com/AngelLM/Thor/blob/286b081fe6f056d87c379b884781ef77ff6a0159/LICENSE)
is retained beside that local source copy. Source geometry/property data in these
reports is attributed to AngelLM/Thor at that revision. Its repository declaration
is CC-BY-SA-4.0; the existing native-metadata discrepancy remains documented in
[the CAD reference manifest](../hardware/cad/references.json). No RAFTEL-wide
license or fabrication/export release is selected by this work.

[The source fingerprint](../hardware/cad/thor-art1-desktop-source-fingerprint.json)
records the 80 ordered Body members, saved shape-member hashes, reference and
expression fingerprints, the early chain's actual saved property values, 24 datum
placements, the 25 AssemblyArt1 target names/types, and the source spreadsheet
cells. Saved numeric enumeration values are preserved as values rather than
guessed modern FreeCAD meanings.

Two independent saved descriptions of the first bolt axis agree:

| Evidence | Local center, mm | Native center, mm | Native normal/axis | Radius, mm |
| --- | --- | --- | --- | --- |
| Sketch004 saved circle and placement | (31.5, 8, 0) | (-31.5, -55, 8) | (0, 1, 0) | 1.7 |
| Earlier native `Pocket.Edge13` capture | Not applicable | (-31.5, -55, 8) | (0, 1, 0) | 1.7 |
| Sketch005 saved circle and placement | (31.5, 8, 0) | (-31.5, -75, 8) | (0, 1, 0) | 2.95 |

The tool computes those placements with quaternion-vector multiplication from
saved XML; it never imports FreeCAD. This corroborates saved design intent and
provides a semantic fingerprint for a future native remapping experiment. It does
not demonstrate that either rebuilt pocket removes the intended material.

Sketch004 still derives radius from `Spreadsheet.M3BoltBodyRadius`, with center
offset constraints referencing `Pad002.Edge22` and support `Pad002.Face9`.
Sketch005 derives radius from `Spreadsheet.M3BoltHeadRadius` and uses the old
`Pocket.Edge13`. Pocket stores `Type=2` and `Length=5`; a reconstruction that
assumes a simple 5 mm dimensional cut from Length alone would discard the saved
operation mode. This report does not assign a new meaning to that enum.

## What the earlier capture establishes

[The historical reanalysis](../hardware/cad/thor-art1-desktop-historical-check.json)
is generated solely from
[the existing migration evidence](../hardware/cad/thor-art1-migration-evidence.json).
It binds that input's SHA-256 and computes:

- Saved `Pad002` minus saved `Pocket`: **119.3831686751 mm³** removed.
- Rebuilt `Pad002` minus rebuilt `Pocket`: **0 mm³** removed.
- The earliest feature *captured by that probe* with volume drift is `Groove`,
  with -2.8642369062 mm³. Earlier Sketch/Pad stages were not captured in that
  probe, so the earliest true drift remains unknown.

The first reported invalid solver state is still `Sketch005`. The root cause of
the disappearing preceding cut has not been isolated. A changed edge index and a
valid final cached solid cannot close that gap.

## Offline capture checker

`tools/thor_art1_diagnostics.py compare` implements the numerical/contract portion
of A7 for an explicitly supplied capture. It requires three candidate stages:
`rebuilt`, `reopened` and `restored` (nominal restored after a separate edit
experiment). Each stage must have:

- A valid, single-solid Body; matching volume, six bounds and COM coordinates;
  both measured Boolean difference directions and a surface-distance comparison.
- Explicit Up-to-date states for Body and all 80 members; the complete 25 external
  names with their source types; all 24 datum matrices.
- Semantic bolt-hole/recess centers, axes, radii, depths and actual nonzero
  `Pocket`/`Pocket001` removed volumes. Merely supplying matching totals is
  insufficient when another checked metric disagrees.

Saved datum matrices must match the source fingerprint's placements; saved hole
centers/axes/radii must match its sketch fingerprints. A malformed transform,
reflection, nonfinite number, omitted measurement, missing collection member,
duplicate JSON key, absent evidence class, cached/Touched state or empty cut is
rejected. JSON output paths must be new, protecting historical evidence.

The thresholds come from [the existing migration gate](thor-art1-editability-gate.md):
volume below `1e-6 mm³`, bounds/COM/hole dimensions/surface distance below
`1e-9 mm`, datum elements and hole-axis components below `1e-12`, and zero
bidirectional difference volumes. COM, hole and surface thresholds are explicit
computational comparison settings. They are not manufacturing or fit tolerances.

The checker compares supplied numbers. It cannot prove a capture was produced by
a native process, validate unmeasured feature semantics, independently infer solid
COM from a BRep, or authenticate runtime/addon hashes. A passing synthetic
fixture never becomes native evidence. A passing capture tagged native becomes
`eligible_for_native_manual_review`; **`migration_accepted` always remains false**.
The capture must identify the saved tip BRep hash from the pinned source
fingerprint. Its saved Body measurements and hole depths still require
independent native authentication; the output explicitly records
`saved_body_geometry_independently_authenticated=false`. Matching a declared
hash does not prove that supplied measurements were taken from those bytes.
A3–A6 semantic support/expression migration, reversible-edit behavior, actual
native capture authentication and A8 assembly/downstream revalidation remain
separate requirements. No complete passing native capture exists in this run.

The input contract is intentionally explicit: `schema_version=1`,
`evidence_class` of `native_geometry_capture` or `synthetic_geometry_fixture`,
source/candidate/capture-script and saved-tip-BRep SHA-256 values, runtime version,
`candidate_path_kind="separate_copy"`, source-unchanged and save/reopen/recompute
flags, `object_states`, `assembly_target_types`, `body`, `datums`, `bolt_holes`,
and `cut_effects_mm3`. The test's `complete_capture()` is a **synthetic schema
example**, with deliberately invented Body dimensions and depths. It must never
be published as a native result or used as the native reference geometry.

## Reproduction

From `arm-01` with the development environment installed:

```powershell
python tools/thor_art1_diagnostics.py source C:\path\to\Art1Body.fcstd `
  --evidence hardware/cad/thor-art1-migration-evidence.json `
  --output C:\new-evidence\art1-source.json
python tools/thor_art1_diagnostics.py history `
  hardware/cad/thor-art1-migration-evidence.json `
  --output C:\new-evidence\art1-history.json
python tools/thor_art1_diagnostics.py compare C:\native-evidence\capture.json `
  --source-contract hardware/cad/thor-art1-desktop-source-fingerprint.json `
  --output C:\new-evidence\art1-comparison.json
python -m pytest tests/test_thor_art1_diagnostics.py
```

The source and history commands do not require FreeCAD. `compare` exits 1 with
a written diagnostic report for numerical/contract failures; malformed inputs
exit 2. Neither exit 0 nor a passing synthetic test authorizes a CAD substitution.

The next native task is bounded: on a host with the pinned runtime/addons, open
only a new Art1 copy with isolated preferences, capture the saved early chain,
force-recompute it before Thickness, and record geometry plus support/solver
changes at each stage. Then vary one Thickness/attachment/operation property per
candidate and require actual bolt material removal before touching Sketch005.
Follow the [full migration gate](thor-art1-editability-gate.md); no index-only
reference replacement or source save is justified by this desktop audit.

## Prepared native probe and semantic support candidates

`tools/probe_thor_art1_freecad.py` now prepares that next selected-document
experiment. **Its FreeCAD branch has not been executed on this host.** Ordinary
Python tests cover its launch/preservation/timeout/completion guards and pure
geometric matcher. Mocked subprocess records test the runner contract; they are
not native evidence.

The runner requires a supplied FreeCAD executable, the exact pinned source and a
new run directory. It checks the 50 GiB disk reserve plus 128 MiB scratch budget,
creates an exact-byte source copy, launches with dedicated `-u user.cfg` and
`-s system.cfg` paths, and sets an explicit native opt-in environment flag. The
native branch independently verifies both hashes, the runtime's actual parameter
paths and an empty document session before loading the copied document. It never
calls a document-save API, and it checks original/copy bytes again after the run.
The configurable timeout is bounded by 600 seconds; logs, the source copy,
checkpoint and runner metadata remain available after a timeout/failure.
The runner records the supplied executable's SHA-256. An independently known
binary pin can be enforced with `--expected-executable-sha256`. That identifies
the executable only; shared libraries, addons and the entire portable bundle
remain separately unaudited by this runner, and its report says so explicitly.

For the early Sketch/Pad chain, its supporting DatumPlane, Thickness and the
first two bolt pockets, the planned capture distinguishes:

1. Exact saved BRep members imported directly from the pinned archive, before
   restoring feature history, with each BRep hash and shape placement recorded.
2. Objects immediately after restoring the copied document, including states,
   object placement, shape metrics, sketch geometry and expressions.
3. A forced-rebuild attempt, with the same metrics/states and actual base-minus-cut
   volumes. A changed captured metric is an inspection lead; a Touched/Invalid
   dependency leaves cached geometry possible. No unchanged metric set is called
   full shape equivalence, and saved/restored coordinate placements must be
   reconciled before diagnosing a solver/kernel cause.

Two separate experiments are allowed: `unchanged` and `intersection`. The latter
changes only `Thickness.Intersection=True` in memory. Each uses a fresh directory
and copied document; neither accepts a repair. The report identifies the first
changed captured feature and first captured object whose own state is unclean,
keeping true semantic first-drift unknown. An own-object Up-to-date state does
not prove clean upstream dependencies: dependency closure is explicitly unchecked,
and even an apparently unchanged/downstream Up-to-date shape may be cached.
A complete diagnostic report can contain a failed CAD
recompute; process completion does not establish CAD validity.

[Semantic descriptors](../hardware/cad/thor-art1-desktop-semantic-supports.json)
derive the two bolt circles and cylinder axis lines from pinned saved sketch
centers, normals and radii. The pure matcher compares geometry, allowing opposite
axis signs and longitudinal shifts of a cylinder's reference axis origin. It
requires full circles when matching a circle support, and checks perpendicular
axis-line distance, radius and direction. Zero candidates return `no_match`;
multiple candidates return `ambiguous` with no selection. A unique match is only
a geometric candidate for manual mechanical review. No support is remapped, no
nearest-edge fallback exists, and no historical `Edge13` index is substituted.

From `arm-01`, regenerate offline descriptors without any native dependency:

```powershell
python tools/probe_thor_art1_freecad.py `
  --describe-source-contract hardware/cad/thor-art1-desktop-source-fingerprint.json `
  --output C:\new-evidence\art1-support-descriptors.json
```

On a native-capable host, run the two bounded experiments with separate new
directories (replace paths with actual local pinned inputs):

```powershell
python tools/probe_thor_art1_freecad.py `
  --freecad C:\pinned-FreeCAD\bin\FreeCADCmd.exe `
  --source C:\preserved-Thor\freecad-src\Art1Body.fcstd `
  --run-directory C:\new-evidence\art1-unchanged --experiment unchanged --timeout 180
python tools/probe_thor_art1_freecad.py `
  --freecad C:\pinned-FreeCAD\bin\FreeCADCmd.exe `
  --source C:\preserved-Thor\freecad-src\Art1Body.fcstd `
  --run-directory C:\new-evidence\art1-intersection --experiment intersection --timeout 180
```

On macOS/Linux, the same Python arguments accept the platform's native FreeCAD
console path and POSIX paths. The host must supply and verify its runtime; no
toolchain is installed by this runner. Inspect `probe.json` and `runner.json`.
Zero exit without matching source/script identity and complete capture coverage
does not set `native_probe_completed`. This probe is an A1/A2/A7 diagnostic input,
not the complete `compare` capture contract: it does not save/reopen/restore a
candidate, measure full final-body surface differences, or prove A3–A8 acceptance.
