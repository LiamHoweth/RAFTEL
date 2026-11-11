# Selected native solid properties and draft tessellation

The [retained native capture](../hardware/cad/thor-native-solid-properties-v1.json) measures **eight hash-pinned saved BReps** using portable FreeCAD **1.1.4**, Git `4fd3bf320d9566a27e60069fc8387448aaa3a094`, Python 3.11.14 and Open CASCADE 7.8.1. Nine native analytical fixtures establish units, centroid reference and frame behavior before source measurements are accepted. This is selected cached-geometry evidence, without a feature-history rebuild, whole-arm inertia model, physical mass/strength validation or fabrication release.

The inputs are the separately pinned [native export request](../hardware/print-planning/thor-native-export-inputs-v1.json): BaseTop, BaseBearingFix, CommonBearingFix, Art2BodyAWindow, Art3TensionerBody, Art4TransmissionColumn, nominal GripperFinger and the actual saved `AssemblyArt56::Unnamed1_GripperFinger_mirrored` shape. The reflected finger is an existing `Part::Mirroring` BRep, not an assumed proper rotation or invented replacement geometry.

## Native evidence and preservation

The accepted run began **2026-11-11 21:15:09 UTC** and completed in approximately **2.42 seconds**. It ran one FreeCAD console process after the CAD lane released the native queue. The capture records the actual and expected five FreeCAD preference/home/data/temp paths and **zero open CAD documents before and after**. Native executable SHA-256 was `1692e54224b48989974e8b91d3ac7a38d1d502d3db4dee1d4cf79ba91356e42d`; the retained worker snapshot SHA-256 is `3175d54684cca3b7eb4fad4490845f926b9c125060afa6d9ad2a64d7fe1d5d34`.

All eight original source archives, copied archives, request and worker snapshot retained their exact hashes. The worker reads only selected BRep members from copied FCStd ZIP archives. It opens no CAD document, restores no feature history, recalculates no features and saves no CAD file. Source XML object/type, internal Shape entry, BRep bytes and own XML placement are checked against the request before importing geometry. Native output and scratch mesh paths are fresh and never overwrite prior evidence; UTF-8 JSON writes explicitly use LF.

Run 02 is retained separately as an actual earlier capture. Run 03 repeated the same geometry with added runtime-path/document-count observations; all eight selected-property/mesh records and all nine native fixture records match Run 02 exactly. Run 01 was prepared but never launched. These distinctions prevent a prepared contract or successful process exit from being treated as geometry evidence.

The generic worker authenticates bytes against **caller-supplied pins**. It explicitly does not independently prove those bytes belong to the declared upstream Git revision. For this run, independent review authenticated all eight archives against the pinned Thor recursive Git tree's blob IDs/sizes, then checked archive SHA-256, object/type, BRep entry/hash, Document.xml hash and XML placements. The reviewed upstream source remains Thor revision `286b081fe6f056d87c379b884781ef77ff6a0159` with its existing CC-BY-SA-4.0 obligations.

## Matrix reference, units and aggregation

The [FreeCAD 1.1.4 Solid wrapper](https://github.com/FreeCAD/FreeCAD/blob/1.1.4/src/Mod/Part/App/TopoShapeSolidPyImp.cpp) obtains inertia from Open CASCADE volume properties. The [Open CASCADE GProp reference](https://occt3d.com/dev/doc/refman/html/class_g_prop.html) identifies its returned matrix as centroidal. These primary references were accessed 2026-11-11; the actual installed-runtime fixtures below establish the observed behavior used here.

For a solid with coordinates in millimetres, unit-density geometric inertia is:

```text
J_geo = integral_volume (|r|^2 I - r r^T) dV,  r measured from its centroid
J_geo units = mm^5
J_geo[m^5] = J_geo[mm^5] * 1e-15
V[m^3] = V[mm^3] * 1e-9
```

For an explicitly declared **uniform** density scenario, `J[kg*m^2] = rho[kg/m^3] * J_geo[m^5]`, and mass equals density times volume. An optional effective uniform fraction scales both quantities uniformly; it is not slicer infill and does not model nonuniform wall/skin/infill distribution. This capture requests geometry only, so all density scenarios and all physical/purchased-internal/nonuniform-print inertia fields remain **null**. No motor or other purchased mass is subdivided or inferred from its outer CAD shape.

The worker measures each native **Solid** wrapper, avoiding unsupported generic-Shape COM/inertia access. Each solid must be native-valid, closed and positive-volume. Per-solid tensors aggregate with volume weighting and the parallel-axis theorem **only inside the one BRep's existing common storage frame**. No cross-asset aggregation occurs. A multiple-solid member sum does not establish disjoint union volume without an overlap check; that caveat is explicit. All eight selected captures contain one solid.

Each selection has a unique BRep-bound frame ID. The raw shape placement and the saved own XML placement are recorded separately and **neither is applied again**. Raw BRep storage coordinates are not automatically mounted assembly, ROS, bench or tool coordinates. Whole-arm inertia integration requires independently verified transforms into a common frame, complete body coverage and appropriate material/internal models.

The nine primitive fixtures cover a 2×3×4 mm box, translated/rotated box, a radius-2/height-5 mm cylinder, rotated/translated cylinder, box scales 0.01 and 10, and a two-disjoint-box compound before/after parent rotation/translation. They test translation invariance of centroidal inertia, rotation covariance, `length^3` volume scaling, `length^5` geometric inertia scaling and same-frame member aggregation. Maximum observed relative errors were **2.824e-16 volume**, **4.402e-15 inertia**, and maximum COM error was **8.882e-16 mm**.

The core and standalone-worker tensor validators additionally reject nonsymmetric, indefinite and inertia-triangle violations. Independent review caught a near-rank-deficient counterexample to tolerant principal-minor checks. The corrected bounded normalized Jacobi/Gershgorin checks fail closed on nonconvergence and were independently tested on 20,000 rotated/scaled known-spectrum classifications. Host tests of these validators do not substitute for the native fixtures.

## Selected results and draft exports

| Cached source | Volume, mm³ | Draft STL facets |
| --- | ---: | ---: |
| BaseTop | 222336.231600 | 2104 |
| BaseBearingFix | 50341.940969 | 2152 |
| CommonBearingFix | 983.171648 | 1220 |
| Art2BodyAWindow | 39011.938014 | 3370 |
| Art3TensionerBody | 872.481294 | 804 |
| Art4TransmissionColumn | 78484.257609 | 14016 |
| GripperFinger nominal | 12593.042563 | 2988 |
| GripperFinger saved reflection | 12593.042563 | 2988 |

The two finger COMs have X coordinates ±9.682448263 mm, with identical Y/Z coordinates. Their captured centroidal tensors obey the corresponding X-reflection sign map and their volumes agree. These invariant checks corroborate the actual saved reflection; they are not a surface-deviation or physical fit test.

Eight binary draft STL files were tessellated separately from preserved upstream STLs using explicit **0.1 mm absolute linear deflection** and **0.2 rad angular deflection**. Their headers/records label coordinate interpretation as millimetres and the files as unreleased drafts; STL itself does not encode units. These numerical tessellation settings are not manufacturing fit tolerances. The native capture records each output's SHA-256, exact byte count, triangle count, frame and parameters.

The native worker does not promote mesh export into manifoldness, winding, self-intersection, surface-fidelity or print acceptance. A separate host audit uses the existing mesh analyzer for exact-vertex topology, normals, bounds and volume comparisons. Self-intersections, support/brim/orientation choices, loaded fits, printed strength and actual printer/material qualification remain separate gates. No G-code, print upload, printer contact or physical fabrication was requested.

## Reproduce within the coordinated native queue

Use the tested standalone worker `tools/probe_thor_solid_properties_freecad.py` from a retained script snapshot. The launch coordinator must verify the executable, copy and authenticate the request/source archives into a new run directory, preserve at least 50 GiB free, select dedicated `-u`/`-s` preferences and set:

```text
RAFTEL_RUN_THOR_SOLID_PROPERTIES=1
RAFTEL_SOLID_RUN_DIR=<fresh run directory>
RAFTEL_SOLID_REQUEST=<request snapshot inside run>
RAFTEL_SOLID_SOURCE_ROOT=<copied source hierarchy inside run>
RAFTEL_SOLID_REPORT=<new JSON path inside run, outside source hierarchy>
RAFTEL_SOLID_USER_CFG=<run-local user.cfg>
RAFTEL_SOLID_SYSTEM_CFG=<run-local system.cfg>
FREECAD_USER_HOME=<run-local existing directory>
FREECAD_USER_DATA=<run-local existing directory>
FREECAD_USER_TEMP=<run-local existing directory>
PYTHONNOUSERSITE=1
RAFTEL_SOLID_EXECUTABLE_SHA256=<coordinator-verified executable SHA-256>
```

The worker checks actual runtime paths, empty document state, request/schema/size bounds and source pins. Invalid guarded inputs are rejected before native import; native measurement exceptions yield a failed status. It verifies primitive semantics before selected capture. Preserve earlier runs, inspect the complete report and separately validate the draft meshes; do not infer native success from exit code zero.
