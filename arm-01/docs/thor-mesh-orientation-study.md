# Thor geometric orientation study

This host-only study measures **42 unranked orientation candidates for seven
eligible cached-native mesh variants**. It selects no printing orientation,
support strategy, material, strength allowance or manufacturing release. The
Art4 transmission column remains excluded because its separate native export
has three nonmanifold edges. Existing upstream-STL and cached-native 3MF drafts
are preserved unchanged; this study generates no meshes or slicer projects.

Inputs are the exact bytes of
[the native mesh audit](../hardware/print-planning/thor-native-mesh-audit-v1.json),
SHA-256 `74e82d136de667304e1ff5733b2c46aa450ca27210ef3762ca9fd10663d13379`,
and its seven eligible Run03 STL files. Each STL's raw SHA-256, byte count,
triangle count, units, storage frame and exact-vertex topology are checked
again. The audit's native capture, launcher, request and source bindings remain
in [the resulting study](../hardware/print-planning/thor-mesh-orientation-study-v1.json).
The nominal and reflected fingers are separate actual saved BRep exports with
different source bindings and mesh hashes; this tool performs no reflection.
The eight-row source audit must retain exactly seven eligible variants and the
blocked column. Extra, substituted or duplicate variant identities fail closed.

## Coordinates and measurements

Source coordinates are the saved BRep storage coordinates in millimeters, with
no additional XML, object, link or mounted-assembly placement applied. A study
point uses column-vector arithmetic `p_study = R p_source + (0, 0, -min_z)`.
Every `R` is an explicit orthonormal signed-permutation matrix with determinant
**+1**. The six candidates put source +Z, -Z, +X, -X, +Y or -Y along study +Z.
These are six fixed representatives; the other yaw variants of the 24 proper
axis permutations are not enumerated. Translation grounds the minimum study Z
at zero and does not recenter X/Y. No installed-frame correspondence or bed fit
is inferred.

The output records the following geometric measurements for every candidate:

- Axis extents, signed winding volume and triangle surface area. Proper rigid
  transforms must preserve volume and area within relative `1e-12` or absolute
  `1e-9` numerical tolerance. Calculations retain the parsed coordinates in
  Python double precision; no transformed float32 STL is written.
- Full-triangle area at the bed: a triangle contributes its whole area only
  when all three grounded vertices have `z <= 0.00001 mm`. Partial triangles
  are not clipped or integrated. This is a numerical classification threshold,
  unrelated to first-layer thickness, adhesion or an accepted contact tolerance.
- The convex hull of all mesh vertices within that numerical bed threshold.
  This hull can span holes and disconnected patches. Whether a centroid's XY
  projection falls inside it is a geometric comparison, **not a stability,
  adhesion or load-bearing result**. Fewer than three hull vertices gives a null
  containment result.
- The native raw BRep geometric volume centroid transformed into the study
  coordinates, its XY projection, and an independently integrated triangle
  winding-volume centroid. The native centroid is a provisional uniform-volume
  COM only. Actual infill, wall distribution, density and attached hardware are
  unknown. Its difference from the mesh centroid diagnoses numerical geometry;
  it is not a surface-distance acceptance metric.
- Downward-facing triangle area in explicit angle bins. Normals come from
  triangle winding, build-up is +Z, and a triangle is downward-facing when
  `n_z < -1e-12`. The angle is `atan2(-n_z, hypot(n_x,n_y))`, mathematically
  equivalent to `asin(-n_z)`, evaluated this way to retain exact 45-degree
  boundaries: **0 degrees is a vertical wall; 90 degrees is a downward
  horizontal face**. Bins are `[0,30)`, `[30,45)`,
  `[45,60)`, and `[60,90]` degrees. Full triangles classified at the bed are
  recorded separately and excluded from these above-bed bins. These areas do
  not account for underlying geometry, bridging, occlusion, slicer rules or
  support generation; they are not unsupported areas or required support areas.

## Observed source +Z candidate

These are examples of the measurements, not a selected orientation. The full
artifact contains all six candidates for each variant. Values below are rounded
only for presentation; the JSON retains the computed values.

| Variant | Full-triangle bed area, mm² | Native centroid projection XY, mm | Above-bed downward-facing area, mm² |
| --- | ---: | --- | ---: |
| Base top | 7228.971 | (0, 0) | 3500.344 |
| Base bearing fix | 10096.069 | (0, 0) | 0 |
| Common bearing fix | 272.977 | (0, 0) | 0 |
| Art2 window | 7075.605 | (0, 0) | 1273.012 |
| Art3 tensioner body | 136.493 | (0, -6.744) | 75.264 |
| Nominal finger | 821.819 | (9.682, 32.168) | 758.243 |
| Actual saved reflected finger | 821.819 | (-9.682, 32.168) | 758.243 |

The largest absolute native-versus-mesh centroid coordinate difference in this
set is approximately **0.008801 mm**, on the fingers. This remains a tessellation
diagnostic. Self-intersections, bidirectional native surface distance, printed
fit/strength and actual slicer process behavior remain unverified. The saved
software profile from the separate profile audit is not used to select an
orientation, and actual process settings remain unconfirmed.

## Reproduction and validation

From `arm-01`, with the preserved Run03 exports available, write to a **new**
output path; existing evidence is never overwritten:

```powershell
.\.venv\Scripts\python.exe tools\thor_mesh_orientations.py `
  --mesh-root ..\.work\native-solid-properties\run-03\draft-stl `
  --output ..\.work\print-planning\orientation-study-repeat.json
.\.venv\Scripts\python.exe -m pytest -q tests\test_thor_mesh_orientations.py
```

The focused suite covers a known rectangular box and polygonal cylinder,
centroid/volume/area invariants, every named axis transform, a known downward
sloped-face bin and exact 45-degree boundary, translation without XY recentering,
null centroid handling,
reflection/invalid rotation rejection, numerical tolerance bounds, strict input
pins, blocked/duplicate variants, distinct actual fingers and preserved outputs.
These are host mathematical/source checks; they do not establish slicing,
rendered Anycubic import, physical support or fabrication acceptance.
