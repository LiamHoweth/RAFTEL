# Art23 optodisk mesh diagnostic

The full cached-native print audit blocks `Art23Optodisk::Body`, used by two
installed instances, because its selected tessellation has four boundary edges.
The preserved upstream STL passes the declared exact-vertex topology checks.
Neither fact establishes that the two meshes represent identical source surfaces.

The [diagnostic receipt](../hardware/print-planning/thor-optodisk-mesh-diagnostics-v1.json)
binds the exact host inputs, actual native comparison, retained arrays/scripts
and separate draft outputs. The older full 47 export/audit is preserved.

## Exact boundary observation

The native export has 1,378 triangles and 688 exact vertices. All four boundary
edges lie at z=5 mm near x=-28 mm and y=3.5–5.3 mm, in the saved-BRep storage
frame. They form one graph cycle with four degree-two vertices. One edge is
approximately 1.76819922 mm long, opposing a three-edge chain of approximately
0.12358750, 0.29409061 and 1.35170260 mm.

This graph cycle is **not a geometrically simple polygon**. Exact rational
predicates on the supplied binary32 coordinates find a proper crossing between
the long chord and middle chain edge at approximately
`(-27.9234264234, 3.8759642307, 5)` mm. The oriented vector-area magnitude,
approximately 0.000271564 mm², includes cancellation across this bow-tie; it is
not an inferred patch area or an instruction to fill the boundary.

There are no declared duplicate facets, zero-area facets or nonmanifold edges
in this native STL. The boundary-segment crossing is a local geometric finding,
separate from a complete triangle self-intersection test, which is unperformed.
No edge is welded, collapsed or filled. The source/BRep, full 47 request, actual
batch export and upstream STL remain separately hash-bound.

The crossing checker uses exact rational arithmetic on the finite supplied
floating-point coordinates. It checks small, exactly axis-aligned planar graph
cycles only (at most 128 vertices), records unchecked cases explicitly, and
distinguishes a proper interior crossing from endpoint contact or collinearity.
Its predicates do not establish a physical surface location or print tolerance.

## Bounded native comparison

The guarded worker prepares three separately labeled routes, each reading a
fresh copy of the same pinned cached BRep:

| Route | Requested linear deflection | Angular input | Boundary of comparison |
| --- | --- | --- | --- |
| MeshPart original | 0.1 mm | 0.2 rad | Same requested settings as the blocked full 47 export |
| Part linear only | 0.1 mm | API default | Different angular/default meshing path; not a precision-only control |
| MeshPart refined | 0.025 mm | 0.1 rad | Explicitly different tessellation candidate; not a CAD repair |

Raw indexed points/faces and separate binary32 topology diagnostics are retained.
Each route can write only a new `DRAFT_NOT_QUALIFIED` STL inside its isolated run.
No existing native/STL/draft file is replaced, and no geometry repair operation
or CAD history recomputation occurs. A closed alternative, if observed, would
still require surface-fidelity, units/frame, self-intersection and physical fit
review before any further acceptance.

The coordinator controls the serialized native queue. Native probes require
explicit opt-in, a verified executable, pinned original/copy inputs and retained
worker/helper/launcher snapshots. Actual five configuration/data/temp paths and
zero open documents are checked, alongside the 50 GiB free-space reserve.
Conflicting helper opt-in flags are rejected before importing native modules or
loading helpers. With the coordinator's permission, native attempt 02 completed
in approximately **1.20 seconds** on 2026-11-11 at 22:51UTC, exit zero, no errors,
and zero documents before/after. All 57 original CAD source files, the copied
BRep and four retained worker/helper snapshots plus launcher stayed unchanged.
All five actual runtime paths were inside the fresh run. Attempt01 remains an
unlaunched preparation; no earlier evidence was overwritten.

| Actual route | Points / triangles | Raw boundary edges | Binary-STL boundary edges | Exact-vertex topology result |
| --- | --- | --- | --- | --- |
| MeshPart original | 688 / 1,378 | 4 | 4 | Blocked; original bow-tie reproduced |
| Part linear only | 1,332 / 2,668 | 0 | 0 | Closed, consistently oriented two-manifold under declared checks |
| MeshPart refined | 1,332 / 2,668 | 0 | 0 | Closed, consistently oriented two-manifold under declared checks |

The original route reproduces the earlier blocked export's **exact file SHA**,
including its boundary crossing before final STL serialization. Both alternatives
remain closed after binary32 serialization, with no declared duplicate/zero-area
facets or nonmanifold edges/vertices. They are separate tessellation candidates,
not repairs to original CAD or automatic substitutes in the full 47 audit.

The Part linear-only result matches the preserved upstream STL **exactly as an
oriented cyclic-triangle multiset and unindexed-vertex multiset**, including
multiplicities. Header/stored-normal differences keep their byte hashes distinct.
The refined MeshPart mesh differs by 12 oriented facets in each direction; it is
not labeled an identical export. This is an exact discrete mesh correspondence,
not a proof that every continuous BRep surface is faithfully approximated or
that either file is printable. The two alternative settings do not isolate a
single causal meshing parameter.

The later host-side summary recomputes every retained point/index boundary
diagnostic, binds each exported STL to the rounded oriented triangle geometry,
and checks capture/launcher/source/scope flags. Current-file host comparison
helpers were added after execution; the executed native 02 snapshot and original
raw capture retain their own hashes. No runtime evidence was retroactively edited.

## Reproduction and scope

From `arm-01`, the normal CLI performs host analysis without launching FreeCAD:

```powershell
python -m pytest tests/test_thor_optodisk_mesh.py
python tools/diagnose_thor_optodisk_mesh.py --native-stl ../.work/cad/full-print-export-native/batch-01-run-01/draft-stl/print-06-art23optodisk-body-nominal-cached-native-draft.stl --upstream-stl ../.work/print-planning/upstream/stl/Art23Optodisk.stl --full-audit hardware/print-planning/thor-full-print-mesh-audit-v1.json --full-request hardware/print-planning/thor-full-print-export-inputs-v1.json --output new-optodisk-diagnostic.json
```

For the separate native summary, import `summarize_native` from the same tool
and supply raw `native-02/probe.json`, `launch-result.json`, `launch-contract.json`,
a filename-to-bytes dictionary of its three `draft-stl` files, and the preserved
upstream STL bytes. The combined receipt wraps that recalculated summary and
the ordinary CLI host diagnostic with local raw-evidence hashes.

The existing bounded STL parser and generic column precision/topology helpers
are reused. Boundary topology and local segment crossings cannot identify the
underlying BRep/mesher cause or establish source-solid equivalence. Thor source
attribution and the embedded-license metadata discrepancy remain unchanged.
No slicing, cloud/printer communication or fabrication release is performed.

The 44 focused tests cover graph cycles versus geometric crossings, exact planar
predicates, topology/byte/source/quantity failures, pre-import native guards,
and coherent-hash tampering of scope flags, raw arrays, settings and STL geometry.
Tests also distinguish cyclic triangle permutations from reversal and preserve
facet multiplicities. These host fixtures are separate from actual native execution.

Recorded native evidence validation also rejects relative/outside/dot-segment
configuration paths using the recorded platform path semantics, and requires
the exact pinned upstream STL bytes before labeling discrete correspondence.
These host guard refinements do not alter native 02 raw evidence.

## Two separate source-mode inspection projects

After independent core review, the unchanged existing `thor_draft_3mf.py`
composer prepared two additional one-part generic 3MF files from the **original
upstream source-STL plan**, under local ignored
`.work/optodisk-mesh-diagnostics/source-projects`:

- `DRAFT_unqualified_SOURCE_Art23Optodisk_01-of-02.3mf`, SHA-256
  `3ac7bd7a81b975027608562144fbed8a5a6d5c528589596f3ddbca8e0bb5c482`.
- `DRAFT_unqualified_SOURCE_Art23Optodisk_02-of-02.3mf`, SHA-256
  `2698e9fce6b8acf6a27319441bab2f4db48c0062fd7cb120bb2cd7f8bd98a08b`.

Each has 1,332 vertices, 2,668 triangles, millimetre units and one build item.
Together they represent the two already-counted installed instances; no new
installed assets are added. The full upstream license text is embedded in the
model's `LicenseTerms` metadata, alongside source/provenance and false
qualification flags. Their identity-rotation build translation is only the
existing unqualified source-plan placement proposal.

Adjacent per-file receipts and `delivery-manifest.json` bind project/source/
license/composer hashes and the separate native correspondence receipt. These
are **source-origin packages**; no native-origin metadata is spoofed. The 61
full-native inspection drafts and older 6/11 campaigns remain separate and
unchanged. The older coarse-native optodisk audit is not unblocked by this
delivery. Actual Anycubic import, slicing, process settings, fit, strength and
fabrication release remain unverified; no printer/cloud action was taken.
