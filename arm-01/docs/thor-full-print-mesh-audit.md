# Full printed-registry host mesh audit and generic drafts

All **47 saved geometry variants / 65 installed printed instances** now have
separately captured native cached-BRep STLs. The
[native aggregate](../hardware/print-planning/thor-full-print-export-native-v1.json)
records six actual bounded native runs, while the
[host audit](../hardware/print-planning/thor-full-print-mesh-audit-v1.json) checks
their provenance and **325,810 STL facets** with ordinary Python. This lane did
not launch FreeCAD, repair geometry, open Anycubic, slice or contact a printer.

## Results and separate gates

| Scope | Variants | Installed instances | Meaning |
| --- | ---: | ---: | --- |
| Native cached export coverage | 47 | 65 | Original saved BReps read/tessellated in six batches, not feature history rebuilt |
| Host mesh-screen candidates | 45 | 62 | Declared exact-vertex topology, winding/normal, native-bounds and gross-unit checks pass |
| Generic 3MF composer candidates | 44 | 61 | Host candidates also pass the unchanged existing composer gates |
| Host topology blocked | 2 | 3 | Optical disk and transmission column remain blocked |
| Additional composer block | 1 | 1 | Original Art1Body cached mesh passes screens; its existing exact-solid/history gate remains unaccepted |

The two topology witnesses are:

- `Art23Optodisk::Body`: **four boundary edges**, affecting two installed instances.
- `Art4TransmissionColumn::Body`: **three nonmanifold edges and four nonmanifold
  vertices**, affecting one installed instance.

These are failures under exact exported-coordinate matching. No proximity weld,
automatic repair, global rescaling or source substitution was applied. A valid
cached BRep does not guarantee an acceptable particular tessellation. The failures
need a bounded source/tessellation investigation before re-entering the queue.

The actual saved nominal/reflected finger meshes match by exact float32 vertex
multiset under X reflection. The reflected mesh is the separately read saved
`AssemblyArt56::Unnamed1_GripperFinger_mirrored` BRep, not a new guessed reflection
of the nominal exported file. Point correspondence does not recover its installed
link transform or establish surface/fit equivalence.

## Actual evidence joins

`audit_thor_full_print_meshes.py` checks the full prepared registry against the
preserved printable manifest, source inspection and 518-leaf inventory. It reuses
the registry preparation logic and verifies **65 unique installed IDs**, exact
source archive/body or mirrored-object identity, variant quantities and explicit
unknown source-to-installed transforms.

The actual raw runner schema differs from the earlier selected-eight launcher.
It is validated directly; no old-format runner, request or capture is fabricated
to satisfy the older audit API. Every selection retains its own batch's actual
raw capture, raw runner, request, worker and launcher-snapshot SHA-256 bindings.
The six requests remain eight-or-fewer selections each, with no overlap or gaps.

Checks include all 57 original archive before/after maps, copied archive pins,
retained worker/request snapshots, successful process/status fields, five distinct
isolated paths under the actual batch directory, zero open documents, no source
save/recompute, nine primitive fixtures per batch, geometric tensor validity and
mm/SI conversions. Unsupported physical/density/inertia and qualification claims
fail rather than being silently accepted.

All actual native runs used the retained worker snapshot
`3175d54684cca3b7eb4fad4490845f926b9c125060afa6d9ad2a64d7fe1d5d34`.
Later host-side/source validation hardening is not claimed to have run inside
those earlier native processes. The full operating-system/library bundle remains
unverified, as explicitly recorded in the native evidence.

The original selected-eight capture is hash-checked and its source bindings,
cached properties and STL hashes are compared with the overlapping current
selections. A direct `validate_full_metadata` call without that separately supplied
historical capture explicitly reports its repeatability check as unverified and
cannot be promoted to a full payload audit. `load_evidence` supplies it from the
preserved tracked file. Metadata-only checking validates records/pins, not mesh
payloads or native execution on the current host.

## Mesh screens and limitations

The existing STL parser/analyzer is reused. Each actual binary export must match
its native filename/hash/size/triangle count, mm declaration, storage-frame label
and tessellation request. Native-export metadata must still state that independent
topology, self-intersection and fit qualification were not performed by the
native worker. Upstream source STLs remain a separate origin.

The host screens inspect exact edge incidence, vertex links, duplicate/degenerate
facets, consistent winding, positive winding volume and stored zero/opposed
normals. Bounds must lie within the recorded native bounds using a declared
float32 serialization comparison allowance. The winding-volume ratio must lie in
the explicit **0.9–1.1 gross-unit sanity band**. That broad band is not a geometric,
manufacturing or fit tolerance: lost features, surface error and intersections can
remain undetected by these screens.

Raw BRep coordinates are retained without reapplying XML/object/link placements.
Each part keeps its own storage frame. Centroidal geometric tensors remain
mm⁵/m⁵, with no invented physical density or purchased/nonuniform-print inertia.
Quantity-weighted scalar component volume can be reconciled; COM/inertia are not
aggregated across unrelated frames or described as an assembled union.

## New generic projects

`compose_thor_full_print_drafts.py` builds a new full-registry queue using the
existing honest native-cached queue type and the new full host-audit hash. Each
row preserves its actual batch pins; there is no fictional whole-run capture.
The **existing 3MF writer and inspector remain unchanged**, including their Art1
block. The new builder does not relabel the full host audit as the old eight-part
audit or silently weaken source/history checks.
Every constructed candidate passes that unchanged composer's strict preflight
before the builder returns a plan or creates output directories, including in
queue-only mode. Coherently edited host eligibility flags cannot publish a queue
that the existing topology/source gate would reject later.

The current separate local package is:

```text
.work/full-print-native-drafts/run-001/
  draft-queue.json
  receipt.json
  DRAFT_full_native_*.3mf    (61 one-part projects)
```

The full local run created and round-trip inspected all **61** generic 3MFs, each
containing one required copy. The receipt reports `complete_queue_export=true`
for this **61-candidate queue**, not all 65 installed parts or a fabrication job.
The earlier six upstream-source and eleven selected-native projects, along with
preview directories, remain separate and preserved. Do not add historical and
current project counts as if they represented additional required physical parts.

Each project uses source-Z-up mesh geometry with an identity rotation and a
separate centering translation into the saved software-profile scenario. The
saved Kobra 3 Max/0.4 mm/0.20 mm/Anycubic PLA selection is software evidence;
actual nozzle/spool/bed, orientation, supports, process and enclosure suitability
remain unqualified. No settings are applied to Anycubic by this tool. Standard
3MF Core round-trip checks do not establish Anycubic GUI compatibility.

Source/license attribution and explicit modification/origin metadata are retained
inside each project. No company-wide license, print release, physical fit,
strength/capacity or safe-motion claim follows from a generated project.

## Reproduction

From `arm-01`, choose unused output paths:

```powershell
python tools/audit_thor_full_print_meshes.py --metadata-only --output ../.work/full-print-metadata-check-003.json
python tools/audit_thor_full_print_meshes.py --output ../.work/full-print-host-check-003.json
python tools/compose_thor_full_print_drafts.py --output-dir ../.work/full-print-native-drafts/repro-002
python -m pytest tests/test_thor_full_print_meshes.py tests/test_compose_thor_full_print_drafts.py
```

The metadata check uses tracked JSON only. The full host check additionally needs
the preserved `.work/cad/full-print-export-native/batch-XX-run-01/draft-stl/`
payloads. Composition needs those payloads and the preserved source LICENSE bytes.
Use `--queue-only` for portable plan preparation, or `--max-projects N` for a
bounded preview whose receipt explicitly remains partial. Neither option implies
that files were sliced or that a printer was used.

All output paths/directories must be new; exclusive creation preserves existing
evidence. JSON writes use UTF-8/LF. A failure can leave partial new output, and a
nonzero run is incomplete. CI exercises the actual metadata contracts, negative
joins, synthetic STL counterexamples and queue provenance; local native/STL/3MF
evidence remains distinct from CI or physical acceptance.

The next ready work is to investigate the two blocked tessellations without
altering originals, close Art1's separate semantic gate, and inspect candidate
orientation/support/source fidelity in an awake accessible slicer. Physical
printing and fabrication remain separately gated.
