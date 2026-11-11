# Saved-zero mounted shape bounds

The [native probe](../tools/probe_thor_mounted_bounds_freecad.py) captured restored
saved-zero coordinate/bounds inputs for all **518 installed geometry leaves**.
Actual Run04 completed in **121.38 seconds**, with no bounds gaps, errors or
saved CAD changes. Its host tests do not execute FreeCAD; the separate actual
outcome is recorded in
[the versioned receipt](../hardware/cad/thor-native-mounted-bounds-v1.json).

**This run performed no recomputation.** Final states were 1,147 Up-to-date and
1,854 Touched, with no Invalid/Error tokens. These are restored cached Shape
observations, not a newly recomputed baseline, repaired Art1 history, a continuous
enclosure proof or accepted collision model. All enclosure/clearance gates remain
false.

## Coordinate contract

The existing `extract_thor_geometry.installed_leaf_instances` walker owns the
physical-leaf identities, hidden construction exclusions and complete ancestor
chain. The probe does not introduce a second assembly traversal. The historical
v2 inventory supplies the expected 518 identities, not replacement geometric
measurements or a physical calibration.

Raw `Shape` coordinates include the leaf's own Placement/LinkPlacement and exclude
ancestor App::Part placements. The worker copies each available raw leaf Shape,
then premultiplies **only** the walker's ancestor transform onto that copy's
Shape.Placement. Source/object placement is not applied a second time. The result
is expressed in the native master document's saved-zero frame, including the
Model group's saved placement. It is not a ROS, bench, camera or calibrated TCP
frame.

Five native synthetic box cases must pass before the Thor master is opened:
direct nested child, rotated leaf link with LinkTransform false/true, and group
links with LinkTransform false/true. A translated/rotated parent and noncommuting
source/link rotations make duplicate own-placement and reversed matrix-order
errors visible. Expected corner extrema are closed-form constants; the 2e-6 mm
fixture comparison allowance is numerical, not a manufacturing tolerance.

For each available leaf, the probe records raw Shape.Placement, complete ancestor
matrix, copied world Shape.Placement, object/link metadata, default bounds and
`optimalBoundingBox(False, True)` bounds. The latter disables triangulation and
enables shape-tolerance expansion. It also transforms all eight corners of the
raw optimal box to obtain a separate axis-aligned box, and crosschecks the copied
native world COM against the existing walker's transform arithmetic.

Default boxes can depend on mesh cache; see the separate
[metric-semantics audit](thor-native-metric-semantics.md). Neither returned box
is asserted to enclose manufactured material, deformation, cables or motion
between poses. This dataset will keep `enclosure_verified=false` and cannot
establish collision clearance. A missing raw leaf Shape remains an explicit
coverage gap; no body box is invented from its COM or another part's bounds.

## Preservation and evidence mode

The probe uses the exact original source inspection and v2 identity-inventory
bytes. The copied source contract permits the separately validated static Art1
wrapper and the other 56 unchanged source files. It does not adopt the failed
ThroughAll candidate or rebuild original procedural history. The source/copy
hashes, retained helper/extractor/worker/request snapshots, actual configuration
paths and open-document counts are checked. Cleanup closes only documents created
after the initial set, including when a guard rejects the session.

The outer retained launcher checks all 57 original CAD files, the copied sources
and 589 pinned addon files before and after the bounded process. Addon module
origins are checked inside the native process. No original is saved, no global
preferences are changed, and no hardware is accessed. Cached/restored Shape
observations and object states remain distinct from forced feature rebuilds and
whole-model geometry validity.

Preparation-only attempts remain under `.work/native-mounted-bounds`; a fresh
run path is required for every actual invocation. The coordinator serializes the
native queue and granted the 480-second slot for Run04. Process exit zero alone
does not establish a complete capture: inspect the report status, identity and
bounds coverage, fixture results, frame/COM checks, final object states and every
preservation check together.

## Actual checks and retained evidence

All five native fixtures passed, with maximum extremum residual approximately
1.000000083e-7 mm. The copied-world native COM versus walker-arithmetic residual
was at most 3.615e-16 m. Independent review reconstructed all 518 raw quaternion
matrices and ancestor-times-own transforms, recomputed the transformed eight-corner
AABBs, and compared COMs with the prior inventory. Identity coverage is exact;
source geometry, root-subassembly membership and physical collision qualification
remain distinct questions.

All 57 original CAD files, all copied inputs, 589 addon files, executed snapshots,
request, launcher and executable retained their expected bytes. The five actual
FreeCAD configuration/data/temp paths stayed inside the new run, with zero open
documents before and after. The raw 3.43 MB capture stays in ignored scratch; the
tracked receipt preserves its hash and all 518 numerical coordinate/bounds rows.
Earlier Run01–03 preparations were not launched and remain intact.
