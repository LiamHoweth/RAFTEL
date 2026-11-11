# Art1 desktop source diagnostics and comparison tooling

The editable Art1 history remains unresolved. The initial Windows pass performed
ZIP/XML inspection and historical reanalysis without a preinstalled CAD runtime.
A later bounded capability lane acquired the official portable FreeCAD 1.1.4 and
ran selected copied-Art1 experiments. The new
[native evidence ledger](../hardware/cad/thor-art1-desktop-native-evidence-v1.json)
records those actual runs separately from source-only inspection. No original CAD
was saved or changed, no exact migration was accepted, and the accepted static
snapshot and historical evidence remain unchanged.

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
operation mode. The later native runtime identifies that saved enum as
`UpToFirst`; the source fingerprint itself preserves its serialized value.

## What the earlier capture establishes

[The historical reanalysis](../hardware/cad/thor-art1-desktop-historical-check.json)
is generated solely from
[the existing migration evidence](../hardware/cad/thor-art1-migration-evidence.json).
It binds that input's SHA-256 and computes:

- Saved `Pad002.Volume` minus saved `Pocket.Volume`: **119.3831686751 mm³**
  algebraic volume difference, not a Boolean removed-solid measurement.
- Rebuilt `Pad002.Volume` minus rebuilt `Pocket.Volume`: **0 mm³** algebraic difference.
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

`tools/probe_thor_art1_freecad.py` runs selected-document experiments. Its native
branch has now been exercised using the portable runtime recorded below.
Ordinary Python tests independently cover launch/preservation/timeout/completion
guards and the pure geometric matcher; mocked subprocess records remain host
tests and are not native evidence.

The runner requires a supplied FreeCAD executable, the exact pinned source and a
new run directory. It checks the 50 GiB disk reserve plus 128 MiB scratch budget,
creates an exact-byte source copy, launches with dedicated `-u user.cfg` and
`-s system.cfg` paths, and sets an explicit native opt-in environment flag. The
native branch independently verifies both hashes, the runtime's actual parameter
paths and an empty document session before loading the copied document. The
default probe never calls a document-save API and checks original/copy bytes
again after the run; the separate guarded candidate entry point is described below.
The configurable timeout is bounded by 600 seconds; logs, the source copy,
checkpoint and runner metadata remain available after a timeout/failure.
Every new run also retains and invokes an exact snapshot of its probe, helper
and migration-evidence inputs. Their hashes are checked again after execution.
The early exploratory runs without those snapshots remain local preliminary
diagnostics; they are not substituted for the six pinned captures in the ledger.
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
3. A forced-rebuild attempt, with the same metrics/states and base-minus-cut
   algebraic volume differences. Boolean removed-solid measurements are recorded
   separately in expanded captures. A changed metric is an inspection lead; a Touched/Invalid
   dependency leaves cached geometry possible. No unchanged metric set is called
   full shape equivalence, and saved/restored coordinate placements must be
   reconciled before diagnosing a solver/kernel cause.

The base experiments are `unchanged` and `intersection`; the latter changes only
`Thickness.Intersection=True`. Three controls compare against the Intersection
baseline: freezing Sketch004 at its exact saved placement with mapping deactivated,
changing only Pocket.Type to Length (keeping 5 mm), and changing only Pocket.Type
to ThroughAll. Every experiment uses a fresh directory and copied document, and
none accepts a repair. The report identifies the first
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

## Actual portable native experiments

The official [FreeCAD 1.1.4 release](https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4)
provided `FreeCAD_1.1.4-Windows-x86_64-py311.7z` (418,088,341 bytes). Its raw SHA-256
`4828741fc91ee37fafcdb97a1abacb18b04ba451ac4372d9ff7a7349b36f4d6d` matched both
the official sidecar and GitHub asset digest. The archive was extracted only under
ignored `.work/cad/runtime`; the existing Unity-bundled 7z executable was reused
read-only after the Windows tar reader reported an unsupported LZMA codec. No
installer or global configuration change was used.

The actual console reports FreeCAD 1.1.4R20260928, Git
`4fd3bf320d9566a27e60069fc8387448aaa3a094`, Python 3.11.14 and OpenCascade 7.8.1.
`freecadcmd.exe` SHA-256 is
`1692e54224b48989974e8b91d3ac7a38d1d502d3db4dee1d4cf79ba91356e42d`; Windows
Authenticode verified its FreeCAD project association AISBL signature. The raw
portable archive identifies the acquired bundle, while the executable hash does
not independently authenticate every loaded OS library or addon.

All actual user/system parameter, user-home/data/temp paths were inside each new
run directory. The documented [portable environment variables](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Start_up_and_Configuration.md)
were set only in child-process environments, with existing run-local directories.
No global FreeCAD user directory was created. No external addons, GUI automation,
network/cloud action from CAD, whole-assembly run or source save was requested.
Approximately 673 GiB remained free after the native series.

The first native probe exposed an API distinction that host-only guard tests
could not establish: a generic imported non-solid `Part.Shape` does not provide
the Solid-only COM property. The probe now derives volumetric COM from actual
Solid subshapes, leaves non-solid COM/volume unmeasured, and excludes unbounded
construction-plane pseudo-volumes from first-drift ranking. Its failed first run
and early runs before retained script snapshots remain local historical evidence.

The six preserved captures and raw report hashes are listed in
[the new ledger](../hardware/cad/thor-art1-desktop-native-evidence-v1.json).
Every pinned run retained exact probe/helper/evidence snapshots, unchanged source
and input-copy hashes, and its actual configuration paths. No old report was
overwritten. These are single-document native recompute diagnostics, not physical
tests or accepted source migrations.

| Experiment | Algebraic `Pad002.Volume − Pocket.Volume`, mm³ | Interpretation |
| --- | ---: | --- |
| Saved source | 119.383168675 | Cached intended reference; distinct from Boolean removed-solid measurement |
| Unchanged forced attempt | 119.383168675 | Thickness Invalid; downstream Pocket is cached/Touched, so no rebuilt-cut proof |
| Intersection only, UpToFirst | 0 | Pocket reports Up-to-date yet removes no volume and has no intended hole circle/cylinder |
| Intersection + frozen exact bolt frame | 0 | Deactivating attachment mapping and preserving the exact frame does not recover the cut |
| Intersection + Type Length, unchanged 5 mm | 45.497757130 | Actual partial cut; not the saved intent or an exact repair |
| Intersection + Type ThroughAll | 119.386256152 | Intended 1.7 mm circle/cylinder reappear; remaining differences still reject exact migration |

Saved and rebuilt `Pad002.Face9` are the same measured plane: source Y = −55 mm,
normal +Y, matching bounds and zero distance to the intended bolt center.
Sketch004's center `(-31.5,-55,8)` mm, axis, radius, three constraints and
spreadsheet expression remain unchanged in the freeze experiment. The Type-only
controls therefore localize the empty-cut behavior to this UpToFirst operation
under the rebuilt chain. They do not establish a fully diagnosed kernel defect
or authorize a different machining/cutting extent.

The first significant bounded captured metric drift is `Groove`:
approximately −2.864236 mm³, with area/COM changes. Earlier captured sketches/pads
remain within the stated numeric thresholds; that does not establish all-surface
equivalence or rule out smaller solver changes. The cause of the Groove drift
remains unresolved.

The [expanded ThroughAll audit](../hardware/cad/thor-art1-desktop-native-through-all-audit-v1.json)
records 90 runtime objects, all own states Up-to-date: all 89 original names/types
remain, with one automatically added `App::Origin` named `Origin001`. All 25
AssemblyArt1 target names/types remain. This is not validation of all 53 subshape
reference meanings or a complete dependency/engineering audit.

The full final Body is a valid single solid, but its volume is
298,644.443967768 mm³ versus saved 298,648.100446804 mm³ (about −3.656479 mm³).
Its maximum source Z bound changes by −0.056547211 mm. Fourteen of 24 datum matrix
comparisons exceed the unchanged `1e-12` threshold; the largest error is about
`1.05516e-11`. No numerical threshold was relaxed.

Both directed Body Boolean difference volumes nevertheless return zero. The
Boolean removed-bolt solids likewise report zero both-direction differences,
while their measured volumes/bounds/COMs differ. Their actual Boolean volumes are
118.555755904 and 118.555756131 mm³, distinct from the algebraic 119.383/119.386 mm³
differences in the table. These conflicting kernel metrics remain explicit gates;
neither zero Boolean output nor Up-to-date state overrides the other failures.
Maximum surface distance has not been measured.

No diagnostic candidate is adopted into the accepted source, assembly, mass/load
ledger or fabrication workflow. Semantic reference migration, surface comparisons
and downstream revalidation remain open.

## Once-saved unaccepted candidate and partial A6

The separate [candidate worker](../tools/prepare_thor_art1_candidate.py) reuses the
same copied-document isolation and retains its exact worker/helper/contract bytes.
It requires a fresh, visibly `UNACCEPTED` filename under ignored
`.work/cad/candidates`, saves that new path exactly once, closes/reopens it, and
tests `Spreadsheet.B2` (`M3BoltBodyRadius`) at 1.69, 1.71 and restored 1.70 mm.
It never saves the original or input-copy path and never overwrites a candidate.
The default probe's no-save completion checker intentionally rejects this evidence
class; separate procedural completion establishes recorded coverage only.

The [actual candidate capture](../hardware/cad/thor-art1-desktop-candidate-study-v1.json)
and [runner metadata](../hardware/cad/thor-art1-desktop-candidate-runner-v1.json)
retain all five phases, actual aliases/values/radii, five affected sketches'
constraints/expressions, all 90 own-state lists, Body metrics and filenames.
Source/input-copy raw hashes stayed pinned before and after. The one saved binary
has SHA-256 `6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd`
and is preserved locally as
`.work/cad/candidates/Art1Body-UNACCEPTED-through-all-v1.FCStd`; its hash stayed
unchanged through reopen and all subsequent unsaved perturbations. Source-saved
is false; new-candidate-saved is true. The failed first opt-in dispatch attempt
and its fresh logs are preserved separately, before any CAD save.

| Phase | Actual B2 / Sketch004 radius, mm | Body volume, mm³ |
| --- | ---: | ---: |
| Before new candidate save | 1.70 | 298644.443967783 |
| Reopened, forced nominal | 1.70 | 298644.443967783 |
| Radius minus 0.01 mm | 1.69 | 298655.643521503 |
| Radius plus 0.01 mm | 1.71 | 298633.153372289 |
| Restored nominal radius | 1.70 | 298644.426247260 |

All five affected expression sets and constraint structures were preserved;
independent review found no uncontrolled constraint-value changes. All measured
own states report Up-to-date. The first reopen changes volume by approximately
`1.746e-10 mm³`, but the radius roundtrip leaves **0.01772052329 mm³** Body-volume
error. The unchanged `1e-6 mm³` roundtrip gate therefore fails. This is useful
partial A6 diagnostic evidence, not reversible parametric equivalence, an accepted
repair, complete reference migration or a fabrication release. No tolerance was
relaxed and no candidate binary is added to the accepted source tree.
