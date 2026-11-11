# Native CAD metric semantics and unresolved Art1 differences

The Art1 discrepancy remains unresolved. Volume integration, conservative bounds,
Boolean topology and minimum-distance queries compute different things. Their
definitions make some apparently conflicting results plausible; source inspection
alone does not explain this candidate's measured differences or establish exact
equivalence. The existing volume, bounds, datum and roundtrip gates remain intact.

[The source receipt](../hardware/cad/thor-native-metric-semantics.json) binds 21
primary-source files by raw SHA-256 to FreeCAD commit
`4fd3bf320d9566a27e60069fc8387448aaa3a094` and OCCT commit
`bd2a789f15235755ce4d1a3b07379a2e062fdc2e` (the observed `V7_8_1` tag target).
Each retained source was checked again through its exact commit URL. This matches
the runtime's reported FreeCAD Git/OCC version identities; it does not independently
reconstruct distributor patches, compiler behavior or every loaded library.

FreeCAD, OCCT and Thor retain their own license/attribution boundaries. Original
headers remain in ignored source audit scratch; no third-party source is copied
into RAFTEL tools or relabeled under a repository-wide license. Thor-derived
geometry remains subject to the existing source-license discrepancy notes.

## Volume and inertia

FreeCAD's [generic Shape volume property](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/TopoShapePyImp.cpp#L2848)
calls `BRepGProp::VolumeProperties(shape, props)` and returns its mass field.
The [Solid COM and inertia properties](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/TopoShapeSolidPyImp.cpp#L111)
use the same volume-property computation. No caller-specified integration accuracy
or returned integration error estimate is exposed by these properties.

In OCCT 7.8.1, [that overload](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepGProp/BRepGProp.cxx#L310)
prefers the geometry route with the internal epsilon set to 1.0, invoking
[non-adaptive Gauss integration](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepGProp/BRepGProp_Vinert.cxx#L224).
This is not a declaration of 100% measured error. It selects the non-adaptive
algorithm; it supplies no useful measured error bound for the returned number.
Faces lacking geometric surfaces can use a triangulation fallback; the inspected
Art1 Bodies have geometric surface classes recorded in the capture.
Integration can depend on surface representation, trimming and face decomposition.
An unchanged enclosed region need not produce bit-identical numerical integrals.
That possibility does not prove the actual Art1 surfaces enclose the same region.

OCCT also provides [adaptive volume integration and Gauss–Kronrod APIs](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepGProp/BRepGProp.hxx#L199),
with requested error controls and reported estimates. The inspected FreeCAD Python
volume/inertia properties do not call them. No new native C++ binding, SDK install
or alternate kernel build is introduced here.

[GProp inertia](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/GProp/GProp_GProps.hxx#L205)
is centroidal, with axes parallel to the storage XYZ axes. For geometry expressed
in millimetres at unit density, volume has units mm³ and geometric inertia mm⁵.
Physical kg·m² requires an explicit density/distribution model and validated frames;
this source audit adds none. The separate native solid-property lane's box/cylinder
fixtures remain the observed runtime evidence for that API behavior.

## Bounds and triangulation

The [default FreeCAD bound computation](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/TopoShape.cpp#L1126)
uses `BRepBndLib::Add` and then clears the output box's gap. OCCT's
[Add implementation](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepBndLib/BRepBndLib.cxx#L75)
can use cached face triangulations; otherwise it bounds surfaces/curves. Its
[documented contract](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepBndLib/BRepBndLib.hxx#L37)
permits an oversized box. In particular, its
[B-spline/Bezier surface branch](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BndLib/BndLib_AddSurface.cxx#L332)
can bound a selected control-pole convex hull rather than tight surface extrema.
Changed poles or trimming can change such a box without proving a surface changed
by the same amount. Meshing/cache state can also alter the chosen bounding route.

The existing Python [optimalBoundingBox method](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/TopoShapePyImp.cpp#L2502)
accepts two booleans. `shape.optimalBoundingBox(False, False)` requests OCCT
`AddOptimal` without triangulation or shape-tolerance expansion. This is a tighter
numerical geometry bound, not an exact-arithmetic oracle. Its algorithm still has
numerical tolerances. The worker records it separately and does not replace or
retroactively relabel old default bounds.

## Boolean and distance evidence

Python [Shape.cut](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/TopoShapePyImp.cpp#L716)
defaults its extra tolerance argument to zero. Its
[Boolean builder](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/TopoShapeExpansion.cpp#L5960)
sets an explicit fuzzy value only for positive caller tolerance, or its automatic
helper for negative tolerance. The default empty constructor uses the existing
OCCT algorithm/tolerances; this audit does not assert a hidden enlarged automatic
fuzzy tolerance. The [FreeCAD wrapper](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/FCBRepAlgoAPI_BooleanOperation.cpp#L40)
also enables non-destructive operation. No fuzzy tolerance is increased here.

Zero integrated difference volume is insufficient by itself: a result can have no
solids, or contain lower-dimensional/non-volumetric topology. Even an empty result
reflects the algorithm's classification at existing tolerances; it is not a proof
in exact arithmetic. The follow-up records nullness plus solid/face/edge counts
alongside both Boolean volumes, preserving failed operations as failures.

[distToShape](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Part/App/TopoShapePyImp.cpp#L2350)
wraps OCCT's [minimum-distance computation](https://github.com/Open-Cascade-SAS/OCCT/blob/bd2a789f15235755ce4d1a3b07379a2e062fdc2e/src/BRepExtrema/BRepExtrema_DistShapeShape.hxx#L39).
A zero whole-solid minimum distance does not measure maximum surface separation.
An interior point can also have zero distance to a solid. The prepared experiment
therefore compares selected tessellation vertices to a compound of target **faces**,
with no solids in that distance target. A translated-box corner control and an
interior-point closed-form nearest-face control verify this distinction.

## Bounded cached-geometry experiment

[The worker](../tools/probe_thor_metric_semantics_freecad.py) imports only the exact
cached source Body BRep and the once-saved **unaccepted** candidate Body BRep. It
opens no CAD document and does no history recomputation or CAD save. It reuses the
solid-properties worker's strict archive/XML/entry pin validation and native metric
implementation from a retained helper snapshot. Its separate opt-in prevents
accidental execution of the helper's native entry point.

Three mesh levels tighten absolute linear/angular deflection together:
`(0.5 mm, 0.4 rad)`, `(0.1 mm, 0.2 rad)`, `(0.02 mm, 0.1 rad)`. Every level freshly
imports its raw BRep, and records native metrics before/after meshing to expose
cache dependence. The oriented triangle-volume integral remains a mesh diagnostic;
it does not prove closed topology, self-intersection absence or a manufacturing
tolerance. Each directed distance uses at most 96 deterministic mesh vertices,
including coordinate extrema. Finite samples cannot establish a continuous
maximum distance or an upper Hausdorff bound. No existing gate is relaxed.

The initial run remains prepared-only. After the root assembly lane released the
native slot, Run02 executed once from its retained script/helper/request snapshot
between **21:38:22 and 21:39:48 UTC**, taking **86.655 seconds**. Original source,
original unaccepted candidate, both input copies and all retained tool/request
hashes stayed unchanged. Five actual configuration/data paths were run-local;
zero CAD documents were open before or after. No CAD document was opened,
recomputed or saved. The [raw capture](../hardware/cad/thor-native-metric-semantics-capture-v1.json)
and [runner receipt](../hardware/cad/thor-native-metric-semantics-runner-v1.json)
are exact byte copies, bound by the source receipt's hashes. The native slot was
then released. This is additional cached-geometry evidence, not another candidate
history/rebuild test.

## Actual measurements and their limits

The two independent box controls passed: overlapping solids have zero minimum
distance; translated corner samples reach 0.25 mm, while the interior point's
nearest face is 0.75 mm away despite zero point-to-solid distance.

| Stored Body | Default unmeshed Zmax, mm | Optimal unmeshed Zmax, mm | Volume property, mm³ |
| --- | ---: | ---: | ---: |
| Pinned source | 161.561414121 | 161.489129231 | 298648.100446804 |
| Unaccepted candidate | 161.504866909 | 161.489129250 | 298644.443967783 |

The tighter unmeshed Z maxima differ by approximately **1.92754e-8 mm**, while the
old default-bound difference is **0.056547211 mm**. Both default X/Y ranges extend
to approximately ±81.179415 mm; tighter unmeshed ranges are approximately ±75 mm.
This directly demonstrates that the old default-bound delta is unsuitable as a
direct measurement of maximum surface displacement. It does not establish all
surfaces or features are equal. Both Bodies have the same surface-class counts,
including one offset surface and one surface of revolution; the specific face
responsible for each conservative bound was not isolated by this experiment.

After meshing, the default Zmax changes even though each fresh BRep's volume and
COM remain unchanged. For example, at the finest level it becomes
161.487297038 / 161.482276390 mm for source/candidate. These mesh-dependent values
lie below the tighter unmeshed Z maxima: after FreeCAD clears the output gap,
these observed mesh-dependent bounds are **not guaranteed conservative geometry
bounds**. They are recorded separately and are not substituted for tighter
numerical geometry bounds. The stored maximum subshape tolerances are approximately
0.001000100 / 0.000577877 mm; they are observations, not new acceptance tolerances.

Both directed Boolean results are non-null, empty compounds with **zero solids,
faces and edges**, and zero integrated volume. This strengthens the description
of what the Boolean actually returned, while leaving its numerical classification
and the other metric discrepancies unresolved.

| Linear / angular deflection | Source / candidate triangles | Source mesh integral, mm³ | Candidate mesh integral, mm³ |
| --- | ---: | ---: | ---: |
| 0.5 mm / 0.4 rad | 12032 / 12136 | 297231.781940 | 297260.725378 |
| 0.1 mm / 0.2 rad | 32378 / 32388 | 298348.194760 | 298346.587172 |
| 0.02 mm / 0.1 rad | 102816 / 102652 | 298594.533386 | 298594.536963 |

At the finest level the mesh integrals differ by approximately **0.003576422 mm³**,
whereas the native volume properties differ by **3.656479021 mm³**. Pairwise mesh
differences change sign across levels. Neither fine mesh integral has converged
to its native property within the existing acceptance thresholds, and no integration
error has been quantified. These observations support further investigation of
representation/integration effects; they do not prove that quadrature accounts
for the whole discrepancy or that the enclosed regions are equal.

At most 96 vertices per direction/level were queried against target boundary
faces; the actual six sample sets contain **95 distinct vertices** each because
selected extrema overlap the evenly indexed selections. Finest-level maxima are
approximately **6.70588e-6 / 6.61687e-6 mm**.
The coordinates come from FreeCAD's mesh kernel, whose
[MeshPoint derives from Vector3f](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/Mesh/App/Core/Elements.h#L95).
Consequently these samples also contain mesh-coordinate precision effects. They
are finite sampled point-to-boundary observations, not continuous surface maxima,
exact CAD point correspondence or a proven Hausdorff bound. Unsampled surfaces,
holes and thin features remain unbounded by this sampling scheme.

Every migration/candidate/manufacturing qualification remains false. The earlier
14 datum-threshold failures, unknown meanings of all 53 references, and failed
0.01772052329 mm³ radius roundtrip remain gates. Next useful work is a separately
bounded per-face bound attribution and integration-error study, then a continuous
surface-comparison method with a justified error bound; none is replaced by these
new sampled or mesh results.
