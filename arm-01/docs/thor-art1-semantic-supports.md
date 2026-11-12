# Read-only Art1 support descriptor audit

This A3/A7 diagnostic preserves the full source reference census: **53 dependent
owner objects, 80 references, 69 face/edge references and 11 whole-datum or sketch
axis references**. Those are different counts. It does not change an attachment,
choose a new face number for CAD, or approve the unaccepted ThroughAll candidate.

The [worker](../tools/probe_thor_art1_semantic_supports.py) and its host tests reuse
the original migration ledger and source fingerprint implementation. Before any
native measurement, the ledger is independently decoded from the exact original
`Document.xml`; coherently editing the historical evidence cannot substitute a
different face while retaining the same source declaration.

## Geometry and matching contract

Supported analytical descriptor families are planes, cylinders, cones, spheres,
circles and lines. Unsupported surface/curve families remain explicit rows.
Each supported descriptor includes its trimmed centroid, numerical optimal
bounds, area or length, vertex/edge counts, topological orientation and neighboring
primitive-class signature. Unknown adjacency cannot produce a strict match.

Matching the primitive type or radius is insufficient. A strict descriptor match
must satisfy the support position/axis/radius or angle, trim, adjacency and
orientation checks. Candidate faces/edges are searched without a nearest-index
fallback. Zero, one and multiple strict matches are reported separately. The
meaning of the current literal `FaceN`/`EdgeN` is also checked independently of
the search result. A unique descriptor match remains an inspection candidate,
not proof of mechanical meaning, a complete topology match or an approved
attachment frame.

The declared comparison policy is 1e-6 mm for positions/radii/trim extrema,
1e-9 for directions and cone angles, and 1e-8 relative for area/length. These are
diagnostic settings, **not the existing exact-migration gates or manufacturing
tolerances**. The original Art1 volume/datum/edit-return failures remain intact.
Direction reversals and orientation changes remain visible even for geometrically
coincident supports.

## Native scope

The actual native audit uses original cached provider BReps from source archive
SHA `8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a`
and provider Shapes after restoring the existing unaccepted candidate archive
SHA `6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd`.
Among the supplied robot CAD archives, only the copied candidate is opened as a
CAD document. No candidate/source recompute is requested;
restoration and cached observations do not establish a fresh feature rebuild.
Saved consumer-property changes are retained separately, including deactivated
attachment modes, rather than hidden by a matching geometric descriptor.

Both Body frames must be identity before comparison. Provider raw Shape placement,
original XML placement and candidate object/Shape placement are recorded without
applying another own transform. Four native primitive fixtures must first verify
that the descriptor getters account for translated/rotated Shape placement exactly
once. Unknown common frames cannot produce a match.

The native entry point rejects conflicting helper execution flags before loading
helpers, requires a fresh isolated run and at least 50 GiB plus 512 MiB scratch,
checks all five actual FreeCAD paths, and closes only documents created by this
probe. Original source, input copies, worker/helper/request bytes and runtime
identity are preserved and checked by the retained outer launcher. It never saves
a native CAD file. Native execution requires the coordinator's serialized slot.

## Actual Run02 result

Run02 completed in **27.777 seconds** with all 80 rows captured and no errors.
The four primitive fixtures passed: maximum anchor error 4.441e-16 mm and axis
error 3.141e-16. All 19 providers had exactly zero recorded raw-Shape/XML and
candidate-Shape/object placement-matrix differences. The restored candidate's
90 objects reported Up-to-date, but no recomputation was requested. Original
57-file CAD hashes, source/candidate copies, runtime, launcher and retained
scripts stayed unchanged; zero documents remained open.

| Descriptor outcome | References |
| --- | ---: |
| Unique strict descriptor candidate | 62 |
| No strict match | 6 |
| Unsupported BSpline edge | 1 |
| Whole datum or sketch axis, outside this matcher | 11 |

Twenty-one unique descriptor candidates have a different raw index, including
the source `Pocket.Face7` descriptor matching candidate raw `Face6`. The current
raw `Face7` differs substantially. **This does not prove that 21 live attachments
are wrong:** Run02 indexes `Shape.Faces/Edges` directly and did not inspect
FreeCAD's persistent-name or `getSubObject` resolution. It performed no remapping.
The first bolt's source `Pocket.Edge13` descriptor matches candidate `Edge13`
exactly under this policy.

One unmatched support (`Sketch008` → `Pocket002.Face35`) differs only in the
recorded topological orientation flag while its geometric/trim checks agree.
Five later planar supports have trimmed-centroid differences of approximately
0.00086–0.00127 mm and area differences of 1.71e-5–2.28e-5 relative; their support
planes still match. These are numerical descriptor observations, not proof of
physical surface deviation or an attachment-frame error. The unsupported edge is
`Sketch022` → `Pocket016.Edge357` (`BSplineCurve`).

Saved consumer-property comparisons are structural XML comparisons: a difference
can reflect serialization/schema changes as well as changed values. They do not
automatically identify a mechanical edit. Explicitly unsupported and uncertain
reference meanings remain gates.

[The versioned receipt](../hardware/cad/thor-art1-semantic-supports-v1.json) retains
all rows, frame traces and selected/literal descriptors. The full 13.86 MB raw
provider arrays remain in ignored scratch, bound by SHA-256 and retained-code
pins. Curation removes those arrays while preserving their counts, kind census
and canonical hashes; it does not change native measurements. Host fixtures do
not substitute for this separately executed native evidence. Independent actual
data review independently accepted the declared Run02 scope.

## Executed public-getter follow-up

Run03 additionally captured `DocumentObject.getSubObject` and
`Shape.getElement` observations for each supported source selector, plus the
current consumer property's public target/subname entries where the API exposes
a recognized representation. A same-list-position witness is only an observed
ordinal, not proof of semantic correspondence. Getter return types, exceptions,
placements and native `isSame`/`isEqual` matches to raw provider indices remain
separate observations. A detached edge lacks its provider neighborhood; its
descriptor comparison must not be mistaken for a complete support match.

A fifth fixture uses one temporary synthetic `Part::Feature` document to test
the two public getters' coordinates. It performs no recompute and closes that
synthetic document before opening the copied candidate. This is distinct from
the four shape-only fixtures executed in Run02. Run03 completed in 29.913 seconds
on the same pinned FreeCAD runtime; all five fixtures passed. Its fresh contract
applied pre-read containment and bounded JSON guards. Run02 raw data and its
initial receipt remain byte-unchanged. All original fields of the 80 raw
reference rows agree between the two runs; descriptor counts remain unchanged.

Both public getters returned a shape for all 69 Face/Edge selectors. Each
returned shape was `isSame` and `isEqual` to the original selector's current raw
provider index. Thus `Pocket.getSubObject("Face7")` and
`Pocket.Shape.getElement("Face7")` returned raw `Face7`; the strict descriptor
candidate for the original source face is still raw `Face6`. This measures these
public calls in the restored copied candidate, not an attachment engine call.

Run03's owner-property read exposed recognized entries for 19 references and
could not read the original property name for 50. In particular its
`DatumPlane001.Support` read raised `AttributeError`. The error's Python wrapper
name `Part.Feature` does not establish a changed native feature type. The
candidate XML still declares `PartDesign::Plane` and stores `AttachmentSupport`
instead of the source's `Support`; Run03 did not query that renamed property or
inventory runtime TypeIds. Its current attachment target cannot be inferred
from a successful provider getter. Eleven whole-datum
or axis rows remain outside this geometric/getter scope. Detached edge getter
descriptors lack neighboring provider faces, so their strict comparison can fail
on adjacency even when geometry and trim agree.

[The supplemental getter receipt](../hardware/cad/thor-art1-semantic-supports-getters-v1.json)
retains all observations, unsupported reads and raw-array curation hashes. The
full raw report has SHA-256
`1c8689d48d8ecac3f8f0ad41c96006a1b9dbd04853648ae8b32608749af3f04b`.
All 57 original CAD files, both input copies, original candidate, retained code,
launcher and runtime passed preservation checks; zero documents remained open.
Independent actual Run03 data review accepted the declared cached/public-getter
and old-property-name scope, without a runtime TypeId or attachment-engine claim.

Run04 completed the follow-up in 32.003 seconds: **all 90 runtime TypeIds match
their saved XML types**. `DatumPlane001` is a native `PartDesign::Plane`; its
Python wrapper type is separately recorded as `Feature`. All 69 current-owner
property reads succeeded: 50 explicitly confirmed `Support` →
`AttachmentSupport` schema renames and 19 unchanged `ExternalGeometry` reads.
The alias is allowed only when saved XML lacks the old name and both XML and
runtime expose the new name. It does not guess arbitrary aliases. The
[FreeCAD 1.1 API implementation](https://github.com/FreeCAD/FreeCAD/blob/1.1.0/src/App/ApplicationPy.cpp)
defines the second `openDocument` argument as `hidden`, not partial loading;
Run03's native log also records loading both Sketcher and PartDesign modules.
These observations alone do not prove complete runtime feature capability.

For all 62 unique descriptor matches, the same-position current property target's
public getter returned the raw index selected by the strict descriptor audit.
For `DatumPlane001`, current `AttachmentSupport` reads `Pocket.Face6`; its public
getter matches the original source `Pocket.Face7` descriptor. The original
selector's public getter still returns current raw `Face7`. This resolves the
apparent raw-index discrepancy at the measured property/API level without
proving attachment-engine execution or repair acceptance. No references changed.

[The typed getter receipt](../hardware/cad/thor-art1-semantic-supports-typed-getters-v1.json)
records the type inventory, all property/getter witnesses and the unchanged
80-row descriptor findings. Its raw report SHA-256 is
`9d1533b2a463297781b0a876efcb88a80e7d927198e9713a8a6c636932af211e`.
Five fixtures passed, all preservation checks passed and zero documents remained
open. Initial Run02 and supplemental Run03 artifacts remain byte-unchanged.
Independent actual Run04 data review accepted the typed/schema-aware getter
scope, without attachment-engine execution or migration acceptance.

These public getters do not prove which path the attachment engine,
persistent-name resolver or LinkSubShadow machinery actually uses. Attachment,
migration and fabrication acceptance remain false.

The original source remains attributed to AngelLM/Thor at revision
`286b081fe6f056d87c379b884781ef77ff6a0159`. Existing repository/document license
metadata differences and physical/fabrication gates remain unresolved.
