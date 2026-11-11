# Art4 column mesh diagnostic

The Art4 transmission column remains blocked for print-draft packaging. This
diagnostic locates its exact mesh defect; it does not weld vertices, repair
geometry, waive topology checks or release fabrication.

The [combined receipt](../hardware/print-planning/thor-column-mesh-diagnostics-v1.json)
binds the host diagnostic, actual native precision capture, eight primary-source
files and exact local evidence hashes. Retained raw arrays/logs remain ignored
scratch evidence; the tracked receipt carries compact recalculated summaries.

## Host observations

The preserved upstream STL has 42,604 triangles, while the selected native
cached-BRep export has 14,016. Both have exactly the same three nonmanifold
edges and four defect coordinates. Each edge has **four distinct incident
triangles**. Their lengths are approximately 0.00296994, 0.00297027 and
0.00296979 mm; together they form a 0.0089100037 mm chain at z=17 mm and radius
approximately 10 mm in the recorded saved-BRep storage frame.

The native mesh has no boundary edges, duplicate facets or zero-area facets.
Its four bad-vertex findings from the existing parser remain separate from the
edge-incidence diagnostic. Four incident facets per edge cannot be accepted as
a two-manifold surface merely because the native BRep reports one valid,
closed solid. Full geometric self-intersection analysis is unperformed.

The incident triangles include an approximately upward-facing sliver, two
approximately radial cylindrical strips extending below/above the chain, and
a downward-facing triangle. These are descriptions of computed triangle normals
and coordinates, not recovered CAD face identities or proof of a source-design
error. The detailed report retains every incident triangle and its index.

## Precision boundary

The exact binary STL coordinate count is 6,988, equal to the native capture's
reported indexed point count before final STL unindexing. Equal counts alone
cannot exclude earlier point consolidation or quantization within MeshPart.
The STL cannot reveal distinct coordinates already discarded earlier.

The exact reported FreeCAD source revision has an explicit earlier storage
boundary: [Mesher.cpp line 158](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/MeshPart/App/Mesher.cpp#L158)
casts extracted double coordinates to float before mesh-kernel adoption.
[MeshPoint](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Mesh/App/Core/Elements.h#L106)
inherits a float vector. The
[Topology accessor](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Mesh/App/MeshPyImp.cpp#L2347)
returns promoted double-point containers; this cannot recover earlier precision.
Thus “before final STL serialization” does not mean “before float storage.”
Eight exact-commit source files are hash-bound in local audit scratch, including
the two reused metric-audit sources. Reported source identity is not a complete
independent reconstruction of the distributed binaries or patches, and these
definitions do not establish this column's defect cause.

At z=17 mm, adjacent binary32 values are approximately 1.90735e-6 mm apart.
The report records adjacent representable values for every defect coordinate;
these are serialization spacings, not a maximum geometric tessellation error
or an accepted manufacturing tolerance. Analytic fixtures demonstrate that two
distinct closed meshes can acquire a four-facet shared edge after binary32
rounding without producing zero-area triangles. This is a possible mechanism,
not proof of the mechanism in this column.

## Bounded native follow-up

`diagnose_thor_column_mesh.py` has a separately opted-in native entry point.
The coordinator owns the native queue. Its prepared contract uses the exact
cached `PartShape1.brp` from the pinned original column archive, fresh isolated
preferences, retained worker/helper/launcher snapshots, an outer 180-second
timeout, and before/after source/copy hashes. It opens, recomputes and saves no
CAD documents. The normal CLI is host-only and never launches this entry point.

The intended native routes are:

1. `MeshPart.meshFromShape`, with the same requested 0.1 mm linear/0.2 rad angular
   inputs as Run03. Inspect raw indexed topology before final binary STL
   serialization, then compute a separate binary32 coordinate-rounding view.
2. A freshly read BRep through `Part.Shape.tessellate(0.1)`. This has a linear
   argument only and **does not hold angular/default meshing behavior constant**.
   Differences between these routes cannot be assigned solely to precision.

Both routes retain original points and triangle indices for independent checks.
No repaired output mesh is generated. With the coordinator's queue permission,
native attempt 02 completed in approximately **5.53 seconds**, exit zero, with
no errors, five actual isolated paths and zero open documents before/after.
All 57 original source files, the copied BRep and retained worker/helper/launcher
snapshots remained unchanged. Preparation attempt 01 was never launched and is
preserved separately.

| Actual route | Points / triangles | Binary32-exact coordinate components | Raw nonmanifold edges | Edges after explicit binary32 rounding |
| --- | --- | --- | --- | --- |
| MeshPart, same requested settings | 6,988 / 14,016 | 20,964 of 20,964 | 3 | 3 |
| Part.tessellate, linear argument only | 20,772 / 41,584 | 3,506 of 62,316 | 3 | 3 |

Both raw indexed topologies already have three four-facet edges. The first
route reproduces the binary STL defect coordinates before final STL packing.
The second route has distinct double-coordinate values and still has the
three edges before explicit rounding. Its raw chain length is approximately
0.0089104645 mm; rounding yields the same recorded binary32 defect coordinates.
No distinct points are lost by the explicit rounding step in either capture.
Host-side recalculation from both retained point/index arrays independently
reproduces all these incidence and coordinate-count findings.

Thus final STL packing is not required to observe this defect. This does not
prove where the defect first enters: source geometry, OCC meshing and earlier
domain/vertex merging remain possible avenues. The two route settings differ,
so their triangle counts cannot isolate a precision-only cause. Native validity
and zero boundary-edge count do not waive the nonmanifold finding.

Independent review found an additional future-run guard requirement: a conflicting
`RAFTEL_RUN_FREECAD_AUDIT=1` could auto-run the reused helper. The current worker
rejects that flag before any native import or helper load, with a negative test.
This fix was added after native attempt 02; its executed snapshot is retained
under its original hash rather than retrospectively relabeled. The actual run's
zero-document/isolation observations remain the evidence for that run.

## Reproduction

From `arm-01`:

```powershell
python -m pytest tests/test_thor_column_mesh_diagnostics.py
python tools/diagnose_thor_column_mesh.py --native-mesh ../.work/native-solid-properties/run-03/draft-stl/art4-transmission-column-cached-native-draft.stl --upstream-mesh ../.work/print-planning/upstream/stl/Art4TransmissionColumn.stl --capture hardware/cad/thor-native-solid-properties-v1.json --host-audit hardware/print-planning/thor-native-mesh-audit-v1.json --output new-column-diagnostic.json
```

To include independently recalculated native precision evidence, add all three
options together: `--native-precision-report ../.work/column-mesh-diagnostics/native-02/probe.json`,
`--native-precision-launcher ../.work/column-mesh-diagnostics/native-02/launch-result.json`
and `--native-precision-contract ../.work/column-mesh-diagnostics/native-02/launch-contract.json`.
The combined tracked receipt wraps this generated diagnostic with the separately
inspected source-definition receipt and local raw-evidence hashes.

The tool checks raw STL/capture bindings and reuses the existing bounded STL
parser. Coherent supplied receipts do not independently authenticate native
execution or upstream revisions. The source/capture pins and independent review
provide those separate evidence links. Thor geometry retains its existing
source attribution and unresolved embedded-license metadata boundary.

The 54 focused tests include analytic edge incidence, a controlled float32 edge
collapse, serialization neighbors, source/capture pin failures, input/output
preservation, isolation/reserve/conflicting-opt-in guards, and coherent-hash
tampering of native arrays, scope flags and runtime/source bindings. These are
host software tests; the actual native capture and independent raw-array review
remain separate evidence.
