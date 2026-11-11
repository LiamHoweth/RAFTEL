# Selected cached-BRep native export inputs

[The request](../hardware/print-planning/thor-native-export-inputs-v1.json)
prepares eight selected source shapes for the separately coordinated native
solid-properties worker. It is **read-only ZIP/XML evidence preparation**;
creating it does not validate a BRep, execute FreeCAD, rebuild procedural
history, produce inertia or export a mesh. The native-process coordinator
retains the one-process slot through the Art1 investigation.

The input baseline is [Thor revision
286b081fe6f056d87c379b884781ef77ff6a0159](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159).
Exact archive SHA256 pins come from the preserved source inspection and
printable-asset manifest. Six small missing archives were obtained at that pin;
the existing nominal-finger and wrist-assembly archives were reused byte for
byte. All eight are copied under ignored
`.work/print-planning/native-sources/freecad-src`. Original sources and prior
evidence are unchanged.

## Exact saved entries

The worker request selects the `Shape` property's actual named ZIP member,
rather than assuming that every object uses the first `PartShape.brp` entry.

| Selection | Source file / object | Exact cached Shape entry | Bytes |
| --- | --- | --- | --- |
| BaseTop | `BaseTop.fcstd` / `Body` | `PartShape.brp` | 19,656 |
| BaseBearingFix | `BaseBearingFix.fcstd` / `Body` | `PartShape.brp` | 23,528 |
| CommonBearingFix | `CommonBearingFix.fcstd` / `Body` | `PartShape.brp` | 24,234 |
| Art2BodyAWindow | `Art2BodyAWindow.fcstd` / `Body` | `PartShape.brp` | 100,176 |
| Art3TensionerBody | `Art3TensionerBody.fcstd` / `Body` | `PartShape.brp` | 25,920 |
| Art4TransmissionColumn | `Art4TransmissionColumn.fcstd` / `Body` | `PartShape1.brp` | 774,154 |
| Nominal finger | `GripperFinger.FCStd` / `Body` | `PartShape.brp` | 68,551 |
| Saved reflected finger | `AssemblyArt56.FCStd` / `Unnamed1_GripperFinger_mirrored` | `PartShape52.brp` | 69,252 |

All archive, Document.xml and selected-entry hashes are retained in the request.
The reflected finger is an actual nonempty saved entry, SHA256
`72569677844f3cc4632795cafcf3a98f7c60429723cf75de2aa64a27147e682d`,
inside pinned assembly archive
`a04836216dcae82eb033c15daba6e41dedb85b03f86ff21e56b77cdff835a473`.
That establishes a source entry worth probing, not a validated reflected export.
Its type is `Part::Mirroring`; the other seven selected objects are
`PartDesign::Body`.

The first three supply native counterparts for the initial upstream-STL draft
plates. The next three correspond to the upstream meshes with open/nonmanifold
findings. Both nominal and saved reflected fingers are included so a later
comparison can preserve the distinction between two geometry variants. No
replacement STL is made by guessing a reflection of the upstream nominal mesh.

## Frame contract

The selected geometry frame is:

> Raw saved BRep coordinates as stored in the selected archive entry. Apply no
> XML/object/ancestor/link placement while reading. Record the actual native
> Shape.Placement separately before any coordinate interpretation.

All eight selected objects have identity **own XML Placement** in these saved
archives. That observation is not permission to apply an identity or nonidentity
ancestor transform again. The request preserves raw placement attributes,
normalized XYZ-mm/quaternion-xyzw values, direct containing groups, Body tips,
attachment/Source/link/mirror properties and their saved expressions. XML is
metadata; none of those expressions or document proxies is executed.

For the mirror, the saved Source chain, X-normal plane through the origin and
identity own/containing placement remain distinct from the installed App::Link
placement. Full source-to-installed frame correspondence is still unknown.
COM or an envelope cannot recover a unique rigid transform.

Preserved **raw-source** bounds and volumes accompany nominal source Bodies.
Matching raw-source COM fields are unavailable in these selected preserved
captures, so they stay null. Installed/world zero-pose COM records are retained
separately with their original frame and a null source-to-installed transform.
They are never silently copied into the raw-source COM field.

Volume can be compared across rigid transforms/reflection without recovering
a placement. The request therefore records a frame-invariant volume reference
for each selection, including the installed reflected-shape volume, while
keeping the reflected raw-source bounds/COM unknown until native inspection.

## Native worker and mesh gates

The request matches the coordinated worker contract:

```text
schema_version = 1
evidence_class = selected_saved_BRep_properties_request
source_revision = pinned Thor revision
selections = eight exact archive/object/entry/hash records
```

`uniform_density` is null for every selection. Geometry preparation does not
invent a printed density, infill fraction or manufactured inertia. The native
worker may establish geometric centroidal tensor quantities; any later uniform
density interpretation must remain a separate explicit conditional study.

Each selection proposes draft tessellation inputs of **0.1 mm absolute linear
deflection, 0.2 rad angular deflection, `relative=false`**, with a distinct safe
filename. These are numerical inspection settings, not accepted fit or
manufacturing tolerances. A native export must preserve its exact source-entry
pin, runtime, shape validity/topology, raw Shape.Placement, bounds/COM/volume
and actual tessellation parameters.

After that native run, ordinary-host STL analysis can independently check the
export's finite coordinates, interpreted mm dimensions, exact-vertex edge/link
topology, winding and volume proxy against the native report. No automatic
weld/repair or second placement is allowed. Self-intersection, geometric
distance/tessellation fidelity and physical fit remain additional gates.

Native-derived candidate meshes and any later candidate 3MFs must be separate
artifacts from the preserved **upstream STL** drafts. Their provenance must say
that they came from selected saved BReps; they are not original upstream STLs,
repaired feature histories or approved print releases.

## Reproduction and current evidence boundary

From an installed development environment in `arm-01`:

```powershell
python -m pytest tests/test_prepare_thor_native_export_inputs.py
python tools/prepare_thor_native_export_inputs.py --source-root ../.work/print-planning/native-sources --output new-native-export-request.json
```

The preparation tool reuses the existing XML fingerprint helpers, validates
archive pins, rejects duplicate/oversized ZIP members, ambiguous/missing objects,
empty Shape entries and inconsistent source/asset pins, and writes only a new LF
JSON output. Its fixtures test a nonidentity XML placement without applying it,
the actual selected member rather than an unrelated first entry, missing mirror
Source context, separate installed COM and preservation of source bytes.

The frozen request's raw SHA256 is
`5835d9740e02324ca6ea8a1b012c78d013ab01d8749eef71fe1d62b395b20b01`.
The native-worker owner validated all eight archive/object/type/BRep/XML pin
records on the host before snapshotting. This document records preparation;
native results require their separately captured report and must not be inferred
from the presence of this request or a successful preparation exit code.
