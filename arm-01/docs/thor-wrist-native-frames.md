# Copied native wrist marker and body-frame experiment

The [native capture](../hardware/cad/thor-wrist-native-frames-v1.json) records
saved zero, one fold/roll perturbation (`q5=0.2`, `q6=0.15` radians), then saved
return. Actual existing AppLink expressions propagate the declared coordinates
to the observed body geometry. Independent source-marker, frame and return
reviews pass within this copied-offset diagnostic scope. This is not a solved
differential mechanism or physical calibration.

## Actual run and limits

Root executed the frozen worker in the serialized native queue using isolated
FreeCAD 1.1.4 / Open CASCADE 7.8.1. Native observation elapsed time was
141.015 seconds; the independently retained launcher measured 141.9477167
seconds, exit code 0, with no timeout. Three poses contain four bodies each,
with three noncollinear actual markers per body. The complete 53-document /
3,001-object final state has 2,969 Up-to-date and 32 Touched objects, with no
Invalid/Error states. Touched states remain visible; this is no whole-history
rebuild claim.

The selected raw Shape markers on the 360-vertex plate move by up to
5.782843824 mm in wrist subassembly coordinates; the selected raw Shape
markers on the 226-vertex GripperBot move by up to 4.900515253 mm. Their marker
indices are respectively `[0,112,320]` and
`[0,150,30]`. The 130-vertex ring (`[0,22,8]`) remains fixed inside the wrist
while its world markers follow q5. The wholly stationary Art4 compound has
6,898 vertices (`[0,778,964]`) and zero observed marker motion.

Independent source-axis Rodrigues replay has maximum marker error
1.160e-13 mm; the reusable capture review using existing wrist algebra reports
1.177e-13 mm. Fresh cached BRep and linked-source marker coordinates match the
independently pinned source vertex tables exactly. Source-to-installed marker
covariance is below 6e-14 mm across independent replays. All four bodies return with
exactly zero observed marker/frame/placement error and equal raw ordered-vertex
digests. Driver offsets and the master wrist ancestor also return exactly.
These floating-point residuals are numerical consistency evidence, not
manufacturing tolerances.

Native `Document.recompute()` returns object counts: wrist/master are
302/1,920 at saved zero and 60/2 at perturbation and return. The raw values are
retained. Initial host review incorrectly expected booleans; the reviewer was
corrected against the [exact pinned native API](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/App/DocumentPyImp.cpp#L714-L723),
which returns `Py::Long(objectCount)`, without changing the worker or raw
capture. No new native run was needed for that host schema correction.

No CAD document was saved. The raw report is copied byte-for-byte into the
tracked capture (SHA-256
`256b31900edbfedb83c5821ffc6da5c996f8a0d35bee12955fcf1e5037641acb`).
The original local report, launcher result and before/after ledgers remain
unchanged under `.work/swarm/w01_native/run-01/`. The separate Root launcher
receipt SHA-256 is
`33029668e69f77e9a3c001bb63724c122fd1346d1a212ec793eb9a9dd6c2f4fc`;
its 843 before/after file hashes agree. This includes 57 original CAD files,
57 retained compatible inputs, 57 fresh copied inputs, 589 addon source files,
16 pre-existing addon cache files, 60 addon Git files, four code snapshots,
request, envelope and executable. All 843 current hashes were rechecked before
publication. Five actual isolated runtime paths, addon module identities and
zero documents before/after the native run are retained in the native report.

The executed worker SHA-256 is
`7cb6d2f2411eea8af70c9663f99865da5c726f8bcbcd1a24c56a33c1a86645d4`;
request SHA-256 is
`7dc28968946cdbc49170925d9a1e315aa91b4ece3559995200cc103f5c5285cf`.
Root's concrete launch-contract SHA-256 is
`a6462d5aceff7333d11699c17e6a4ecf095cf3f9a293a4ca1dfa9a0cd1122398`.
The executable was independently checked against
`1692e54224b48989974e8b91d3ac7a38d1d502d3db4dee1d4cf79ba91356e42d`.
Launcher/preservation summaries in this section are host-derived receipt
interpretations, separate from the unchanged native observations.

## Source operations

The existing master `AssemblyArt56` AppLink receives
`saved_AttachmentOffset * Rotation(local +X,q5)`. Its saved mating-datum chain
maps this right increment to native +Y through z=556 mm. The existing internal
`Art56GearPlate_Art56GearPlate` AppLink receives
`Rotation(parent-datum +Z,q6) * saved_AttachmentOffset`. Its parent datum maps
+Z to native +Z through z=575.5 mm. The original placement expressions remain
intact; recomputing the wrist and master documents evaluates those expressions.
Angles are converted to degrees only at the native Rotation constructor.

These are imposed mathematical coordinates on existing source attachments.
The side differential gears are not driven and no differential, mesh, physical
sign, calibration, gripper linkage, contact or TCP claim follows. The plate
origin, mating datum and ROS joint origin are different points along the same
zero roll axis; their complete frames must not be identified with one another.

## Native witnesses and independent review

The plate and attached GripperBot supply roll-and-fold witnesses. The motor
cover ring supplies a q6-stationary witness carried by q5. Master AssemblyArt4
supplies a wholly stationary compound-shape witness. Each has three
noncollinear existing native Shape vertices, with fixed zero-based indices
selected at saved zero and retained through perturbation and return. Triad
frames are recovered from those actual vertices rather than created at an FK
target. Raw Shape vertices already include their own object placement: only
the master wrist ancestor is applied to wrist objects, and no ancestor is
added to the master Art4 raw Shape. Vertex distances are in mm and triangle
area is in mm²; the marker degeneracy thresholds apply to this fixed unit.

The three direct source Bodies also receive a fresh independent cached BRep
read, authenticated through original archive bytes, source object and Shape
entry. Source markers, linked-source markers, installed raw markers, complete
body/marker frames and source/instance identities remain separate fields.
The stationary Art4 witness is an existing AppLink compound, not an additional
direct printed-part BRep claim.

Host capture review compares the actual coordinates with declared source-axis
math, verifies source-to-installed marker correspondence, detects stale raw
geometry, checks the stationary witness and quantifies nominal return. Neither
the requested offsets nor native placement readbacks alone establish shape
refresh. Ordered-vertex hashes are retained observations; numeric marker/frame
return determines the return result despite possible last-bit hash changes.

## Preservation and reproduction

Only Root may launch this worker in the serialized native queue. Host
`prepare_contract(source_root,arm01_root)` authenticates the established full
57-file compatible tree and wraps the separately pinned seven-document wrist
source contract. The retained static Art1 replacement remains an unrepaired
compatibility fixture. Every worker/helper/request snapshot is pinned; actual
five-path isolation and pinned addon module origins are checked before opening
CAD. A fresh run needs at least 50 GiB reserve plus scratch budget.

Set `RAFTEL_RUN_THOR_WRIST_FRAMES=1`, `RAFTEL_WRIST_FRAMES_RUN_DIR` and
`RAFTEL_WRIST_FRAMES_ENVELOPE` only for the dedicated process. Clear other
native entry flags. The envelope must bind a new report, copied source,
snapshots of this worker, `audit_freecad_assembly.py`, the prior pose helper and
`thor_wrist_pose_contract.py`, plus distinct run-local user/system cfg,
home/data/temp paths. Use the verified isolated FreeCAD 1.1.4 executable and
existing pinned addon roots, with a bounded outer timeout.

The worker saves no CAD document, does not force source feature histories and
closes only documents it created. Full source hashes, actual loaded filenames,
document-qualified states, cleanup and nominal-return readbacks are retained
even when a comparison fails. A successful process exit is not acceptance.
