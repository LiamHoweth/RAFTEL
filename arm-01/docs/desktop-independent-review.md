# Desktop independent evidence review

This review concerns source records, analytical models and offline software on
Windows/Python 3.14.6, with subsequent isolated native CAD diagnostics described
separately below. It establishes no accepted CAD migration, gear contact,
physical mass, calibrated motion, printing qualification or hardware performance.
The original CAD and historical reports are preserved.

## Reproducible accounting audit

From `arm-01` after installing the development requirements:

```powershell
python tools/review_desktop_evidence.py --build-snapshot
python tools/review_desktop_evidence.py --math-checks
python -m pytest tests/test_desktop_evidence_review.py
python tools/check_evidence_line_endings.py --include-untracked
python -m pytest tests/test_evidence_line_endings.py
```

The tool's arithmetic and cross-artifact checks are separate from the load
builder. `--build-snapshot` obtains mass assignments from the existing builder,
then independently checks their ownership and aggregates; it does not constitute
an independent material-classification or native source traversal. `--snapshot`
can instead inspect an externally generated expanded zero-pose mass ledger.

The line-ending guard is separate because `.gitattributes` normalizes check-in
bytes without rewriting newly generated worktree files. This review found a
new CRLF jaw ledger whose Windows byte hash would differ from its published LF
blob. The coordinator normalized only new text artifacts, owners refreshed their
dependent bindings/reports, and generators now explicitly request LF. The guard
reads known text types and reports CR bytes without modifying any file; native
CAD and other binary assets are excluded. Source-hash verification still runs
separately after this guard passes.

The frozen revision passes these checks:

- The exact file-byte SHA-256 values match source bindings. Canonical JSON hashes
  are computed separately; line-ending normalization never repairs a byte hash.
- All 518 retained leaves have one wrist membership. The previous 516 leaf records
  are unchanged, and the only two additions have explicit belt-mass assumptions.
- 517 disjoint mass records cover the retained leaves. The seven whole motors
  retain 2.120 kg. The default conditional PLA model has 5.6547224855756 kg and
  zero-pose COM `(0.00010959106465048427, 0.010672595000322325,
  0.23263207530726504)` m in nominal source `base_link`.
- All 72 saved payload/pose cases conserve full-body gravitational force and
  support reactions. Zero-payload moments agree independently with mass-weighted
  COM. Full unresolved wrist gravity/holding totals remain null.

Twenty-six focused corruption/CLI tests cover duplicate and omitted ownership,
changed historical geometry, unknown motion classes, missing belt scenarios,
double-applied frame rotation, doubled purchased motor mass, stale provenance,
false numeric wrist totals, corrupted gravity/support wrenches, ambiguous JSON,
and evidence-path preservation. This is an
inventory-internal accounting check, not proof that an unobserved physical or
native component cannot be missing.

## Independent numerical checks

The initial spatial-kinematics API was checked separately over 300 seeded random
poses across `link_6`, `gripper_base` and `gripper_mid_point`, including off-axis
target offsets. Central differences of FK point positions agree with the
analytical Jacobian to 1.235e-10 m/rad; angular velocities computed independently
from `Rdot R^T` agree to 2.251e-10. Six hundred transform/inverse compositions and
300 scaled-Jacobian Gram trace identities pass. These are nominal mathematical
checks; they do not reconcile nonzero native assembly poses or physical zeros.

Additional independent session checks establish these bounded results:

| Model | Check | Result |
| --- | --- | --- |
| Local nominal IK | 120 source-box/near-limit FK targets across three targets, nearby/random seeds; independent FK distance and rotation trace residuals | 78 converged, 39 stalled at limits, three stalled. Every returned joint vector stayed in the declared box; successful residuals were at most 8.347e-7 m and 7.731e-6 rad. Failures remain local failures, even though these generated targets are nominally feasible. |
| Jaw COM overlay | 200 random closing coordinates, all 66 Art56 records, central differences | Maximum derivative discrepancy 5.929e-11 m/rad. Saved and ideal-zero configurations remain distinct. |
| Whole conditional arm/jaw loads | Independent product of fixed-zero-axis transforms, both wrist phases, 12 poses and 84 coordinate gradients | Maximum per-body/payload position discrepancy 3.331e-16 m and effort discrepancy 1.450e-9 N m. `--math-checks` reproduces this check, with a fixed payload attachment independent of jaw angle. |
| Inertia helpers | 200 sets of 20 explicitly declared point masses; direct centroidal sums and transform/aggregation covariance | Tensor differences below 1e-12 kg m². This does not extract native solid tensors or infer purchased/printed internal inertia. |
| Sensitivity report | Rebuild all seven extrema witnesses with fresh payload points; inspect five matched one-parameter ranking witnesses | Holding differences at most 1.111e-16 N m. These are sampled conditional extrema, not physical uncertainty or capacity bounds. |
| Synthetic identification | 80 noisy paired-pose cases checked against an independent 3×3 normal-equation solve | Coefficient differences at most 4.386e-15. Covariance remains conditional on exact synthetic predictors and the declared output-noise model. |
| Scalar quintic paths | 300 random segments; independent critical-point derivative maxima and finite differences | Peak differences below 1e-12; derivative discrepancies at most 1.335e-9 rad/s and 2.237e-8 rad/s² with step `duration*1e-5`. Source acceleration remains unknown unless an explicit study supplies it. |
| Coupled rate boxes | 200 random declared transmission scenarios, velocity and acceleration boxes | Direct elbow/wrist interval formulas agree within 7.106e-15. Per-output witnesses are separate; they do not establish simultaneous path extrema or motor capacity. |
| Rigid interface equilibrium | 200 arbitrary six-component wrenches on symmetric rectangular supports | Closed-form minimum-force allocations agree within 1.422e-14 N. Chosen sign-invalid allocations remain distinct from proofs of global infeasibility. |
| Printed asset ledger | Compare every installed ID/quantity/volume/source hash independently | 65 installed leaves, 46 source assets, 47 geometry variants, one reflected finger; printed volume 3,485,323.122867902 mm³. No meshes were exported or physically qualified. |

Independent review identified and implementation owners corrected source integer
overflow/state guards, GRBL decimal-parser fidelity, duplicate JSON acceptance,
ambiguous saved-body capture binding, static drawing labels that could drift from
metadata, and extreme trajectory sampling cases. A correction's passing fixture
is software evidence, not a replacement for the unresolved native and physical
gates.

Further lane review and final integrated checks are recorded with their actual
results in [nextSteps.md](../../nextSteps.md). An implementation lane's passing
test count alone is not independent validation.

## Source and attribution boundaries

Thor source and native captures identify revision
`286b081fe6f056d87c379b884781ef77ff6a0159`. The source-data register declares
CC-BY-SA-4.0 and retains the explicit repository license link; original embedded
document metadata differs and remains a distribution-review gate. New print
manifests/drawings must retain creator/source/revision attribution, distinguish
annotations/proposals/reflections, and carry the outstanding export/fit gates.
No source CAD binary or addon implementation is vendored by this desktop work.

The pinned Fasteners/Gears/runtime versions remain recorded in the historical
[dependency study](thor-dependency-compatibility.md). That study identifies
Fasteners GPL-2.0-or-later and current Gears GPL-3.0-or-later source obligations;
it is not a fresh inspection of every historical addon file's terms. Retain exact
file-specific notices if tooling or derived assets are distributed. This review
does not choose a RAFTEL company-wide license or grant a fabrication release.

The later native-foundation source inspection verified all 57 original native
files (122,885,970 bytes) against the pinned Thor Git blobs and all 589 addon
files against their exact clean checkouts: Fasteners
`fddd07af422b7d3a69098b32333711c5eeae184c` (540 files) and historical Gears
`ffe86c85e8061546a3fbaa598993d8e1be2b0de2` (49 files). Package-level labels
do not replace individual headers. The inspected Gears root LICENSE/README
declare GPLv3, while `freecad/gears/features.py` and `pygears` headers state
LGPLv2-or-later. Fasteners `package.xml` declares GPL-2.0-or-later, while
`screw_maker.py` and several `FsFunctions` headers state LGPLv2-or-later.
Both kinds of notice remain in the preserved checkouts. This is a factual
notice inventory, not a decision about licensing a redistributed combined work.

The older CAD adoption/readme/native audit documents describe earlier stages.
Their statements about unavailable assembly import or the 516-leaf inventory
must be read as historical evidence, alongside the current v2 inventory and
[active handoff](../../nextSteps.md), not as interchangeable current reports.

## Subsequent desktop checkpoint review

The outcome scorer and benchmark received a separate code review and 45 focused
test rerun. An independent enumeration of 128 success, misroute, failure, open
attempt and assistance traces agrees with hand-derived object/attempt counts.
Wilson interval endpoints satisfy the independent binomial-score boundary
equation within 2.221e-16 for trial counts from one through ten million.
Predeclared misses and unresolved/assisted objects remain in their denominators.
Unique layout IDs and common evidence classes are required for pooled reports;
the whole-layout bootstrap is explicitly descriptive and cannot establish
independence or physical reliability. Output creation preserves existing files.

The local slicer profile audit was checked independently against the selected
saved record, six inherited profile files, and the installed executable/DLL.
Only the documented selector/profile fields were inspected or exported. All six
cached profile files match their bundled counterparts byte for byte. The saved
Kobra 3 Max/0.4 mm/0.20 mm/PLA selections are software configuration evidence;
installed nozzle, filament, plate, density and mechanical performance remain
unconfirmed. The provisional usable envelope and margin are planning inputs.

The nominal STL audit covers 49 pinned sources and the original license. All
selected Git blob hashes and file-byte SHA-256 values were checked. Three source
topologies fail the declared closed-manifold tests: Art2BodyAWindow, the two
Art3TensionerBody instances, and Art4TransmissionColumn. Together with the missing
reflected finger, these are five blocked installed instances; 60 are source-mesh
candidates. Closed topology does not establish freedom from self-intersections,
equivalence to native CAD, fit or print qualification. Art1 remains independently
blocked from draft 3MF output by its exact-solid acceptance gate.

Six actual generic draft 3MF archives were independently unpacked and compared
against a separate STL reader: BaseTop, BaseBearingFix and four CommonBearingFix
instances, totaling 9,870 triangles. Every source triangle vertex and winding,
zero-based index, millimetre unit, build translation, source/profile binding and
full upstream license text agrees. The packages contain only the three expected
Core/OPC parts and one nominal object/build item each. The transform convention
was checked against the pinned [3MF Core 1.4 specification](https://github.com/3MFConsortium/spec_core/blob/1.4.0/3MF%20Core%20Specification.md).
This establishes generic archive structure and preserved mesh coordinates; an
Anycubic import, slicing, toolpath generation or fabrication release was not
observed in this review.

The observation replay passed 52 focused tests and 202 independent policy/frame
cases. A three-presented/two-supplied case retains never-observed objects and
rejects a newest future observation without falling back to an older accepted
pose. Explicitly allowing unknown observation noise leaves its covariance null.
For 200 random planar rotations and translations, hand-expanded point and
correlated covariance formulas agree within 1.085e-19. Exact age boundaries are
inclusive. Only accepted current values resolved into logical `arm_base` can
become sorter objects. Supplied detection claims, current policy acceptance and
physical detection performance remain separate concepts; recorded hashes do not
authenticate a camera or calibration.

The GRBL diagnostic cross-build passed 16 focused guard tests. Independent raw
checks covered all 72 original/copied source blobs and all 1,628 extracted
toolchain files in two build directories. The archive size and SHA-256 agree with
the [official Arduino package index](https://downloads.arduino.cc/packages/package_index.json).
The 23 commands per successful build invoke only compiler, object conversion and
size tools. ELF and HEX bytes reproduce exactly across both builds. A separate
ELF32 reader identifies AVR machine code with 31,640 text bytes, no initialized
data and 2,075 BSS bytes. An independent Intel HEX checksum/address reader
reconstructs every text byte exactly. The compiler retained six warnings,
including the 16-bit `int` shift at `bit(WORD_Z)`, potentially uninitialized parser
state, a spindle signature mismatch and EEPROM checksum boolean operations.
These remain source correctness investigations. A successful cross-build proves
neither firmware execution semantics nor hardware behavior; no produced firmware
was executed or flashed, and the binaries remain ignored local scratch.

The subsequent [source-warning audit](thor-grbl-source-warnings.md) passed 16
independently rerun tests. A separate ELF reader decoded all 11 named constants
in both relocatable AVR probe objects; the ordinary and stricter-diagnostic
builds have identical data. Source inspection confirms the distinct Z
`axis_words` target path, M95's unassigned/stale modal bit, the empty recovery
spindle function and the checksum collision/compatibility issue. Signed bit 15
has a separate diagnostic from bit 16's width overflow; matching signed and
unsigned object bytes does not make their C semantics interchangeable. The
source was not repaired, and these object-data probes execute no AVR code.
Review also closed an output-overlap guard that could otherwise add scratch
files inside the preserved compiler tree.

Preparing the native inertia probe uncovered a near-rank validation defect in
the original normalized principal-minor heuristic. For example,
`[[1,-1e-7,0],[-1e-7,1,0],[0,0,0]]` was accepted despite principal moments
`1-1e-7`, `1+1e-7`, `0`, which violate an inertia triangle inequality by 2e-7.
The core and standalone worker now use bounded normalized Jacobi rotations and
a converged Gershgorin lower bound. Independent known-spectrum checks cover
20,000 classifications over 500 quaternion rotations and scales 1e-240 through
1e240: valid tensors and exact semidefinite rods pass, while negative moments
and the previous near-rank triangle defect reject. All 51 focused core/worker
tests pass. This validates the mathematical guard; native selected-solid
properties require their own actual capture and frame/unit fixtures.

## Isolated native Art1 diagnostic review

The [official portable FreeCAD 1.1.4 Windows archive](https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4) was independently checked
against its published checksum and release-asset digest:
`4828741fc91ee37fafcdb97a1abacb18b04ba451ac4372d9ff7a7349b36f4d6d`.
The executable has a valid FreeCAD association signature and SHA-256
`1692e54224b48989974e8b91d3ac7a38d1d502d3db4dee1d4cf79ba91356e42d`.
Its actual capability capture reports source revision
`4fd3bf320d9566a27e60069fc8387448aaa3a094`, Python 3.11.14 and OpenCascade
7.8.1. Actual user/system configuration and home/data/temp paths resolve inside
each fresh scratch run. The global FreeCAD AppData directory remained absent
when inspected. This verifies the selected executable/capture, not every addon
or runtime dependency.

Five fresh copied-document controls retain and invoke identical byte-hashed
capture scripts, diagnostic helpers and migration-evidence inputs. Independent
checks verified these snapshots before/after, all source/copy hashes and actual
configuration paths. Earlier exploratory runs lacked retained code snapshots;
their recorded hashes are retained with that limitation instead of inventing
retroactive snapshots. All 16 captured source BRep member digests agree with the
pinned source ZIP. No source document was saved or modified.

| Control | Algebraic Pad002−Pocket volume delta, mm³ | Bolt circle/cylinder | Bounded conclusion |
| --- | ---: | --- | --- |
| Original settings | 119.383168675 cached | Present in cached shapes | Thickness remains invalid and downstream objects touched; this does not prove successful recomputation. |
| Thickness Intersection only | 0 | Missing | An Up-to-date Pocket can still perform no cut. |
| Intersection plus exact saved bolt-sketch frame | 0 | Missing | Freezing this frame alone does not recover the cut. |
| Intersection plus Pocket Length | 45.497757130 | Unique matches | This declared depth produces only a partial cut. |
| Intersection plus Pocket ThroughAll | 119.386256152 | Unique matches | The type-only control recovers a hole, but changes source geometry. |

The source saved algebraic volume delta is 119.383168675 mm³. The ThroughAll
control's head-recess algebraic delta is 98.212169356 mm³ versus the saved
98.214414086 mm³, and its final Body is
3.656479064 mm³ smaller than the saved 298,648.100446804 mm³ Body. Groove remains
the first changed bounded feature captured by these controls; the true earliest
semantic drift remains unknown. The diagnostics do not establish exact shape
equivalence, complete dependency cleanliness, all 25 assembly targets,
save/reopen stability, native assembly substitution or fabrication acceptance.

A subsequent retained-script ThroughAll audit captures all object states and
24 datum matrices. Independent XML name/type comparison finds all 89 originals
preserved plus one extra `Origin001`; all 90 report their own state Up-to-date.
The exact object-contract equality flag remains false. Independent Hamilton
quaternion evaluation of all saved datum matrices agrees within 2.221e-16;
recomputed matrices differ by up to 1.056e-11, with 14 exceeding the declared
1e-12 element threshold. This threshold is a comparison policy, not a physical
manufacturing tolerance.

Crucially, the actual Boolean removed-solid volumes are 118.555755904 mm³ saved
and 118.555756131 mm³ attempted. These do not equal the algebraic volume deltas
above. Both directional Body Boolean differences return zero despite a
3.656479036 mm³ volume difference and 0.056547211 mm Z-maximum difference.
Both directional removed-solid differences also return zero despite different
metrics. These conflicting native measurements require investigation and
cannot establish equivalent shapes. The report correctly keeps equivalence
and migration acceptance false rather than relaxing the comparison gates.

A separate partial-A6 procedure saved one visibly `UNACCEPTED` derived candidate
once, then reopened and perturbed its spreadsheet radius without saving again.
Independent checks match all four retained tool/input snapshots and the
unchanged original/input-copy hashes. Candidate SHA-256
`6b8e6ad3e6d7b6c0165d3cf2758b7a6e4ce4a30e92c53b86a7256f5b6904a1dd`
remains unchanged afterward. Saved XML confirms the two declared changes,
ThroughAll and Intersection. Across five phases, the observed radii follow
`1.7, 1.7, 1.69, 1.71, 1.7` mm; all five affected expression sets, constraint
structures and uncontrolled constraint values remain unchanged. Reopening
changes Body volume by 1.747e-10 mm³, but the radius roundtrip changes it by
**0.01772052329 mm³**, failing the declared 1e-6 mm³ return gate despite all
90 own-object states reporting Up-to-date. This is a recorded unsuccessful
reversibility test. New-candidate-save flags are distinct from source-save
flags, and default no-save probe completion correctly remains false.

## Selected cached-solid property capture

The separate native solid-properties capture reads eight exact cached BReps;
it opens no CAD documents, rebuilds no history and applies no extra XML/link
placement. Independent source authentication checks each archive against the
pinned upstream Git blob and size, then checks its XML object/type/Shape entry,
raw BRep hash and declared placement. The generic worker explicitly notes that
a request's revision/hash declarations cannot authenticate themselves.

Nine actual native fixtures cover boxes, a cylinder, unequal disjoint boxes,
translations, nontrivial rotations and two length scales. An independent
Hamilton-quaternion calculation and reduced-volume parallel-axis derivation
agree with the capture to 2.824e-16 relative volume, 4.441e-16 mm COM and
4.402e-15 relative tensor error. These fixtures establish the selected runtime's
centroidal `Solid.MatrixOfInertia` convention in parallel raw-storage axes,
with geometric units mm⁵. Conversion to m⁵ multiplies by 1e-15; a separately
declared uniform density would produce a conditional kg·m² tensor.

An independent closed-form invariant eigenvalue calculation, separate from the
production Jacobi validator, finds positive principal moments and satisfied
triangle inequalities for all eight captured tensors. The nominal/reflected
finger volumes agree exactly, and their COMs and tensor signs satisfy the
expected X-reflection map exactly. All conditional density, physical,
purchased-internal and nonuniform-print tensors remain null in this run.
Per-BRep frame IDs remain distinct; no whole-arm or cross-asset inertia is
assembled. Source archives/copies, retained worker/request bytes and generated
STL hashes match. Mesh topology, surface fidelity, installed-pose reconciliation
and printing qualification remain separate checks.

A fresh retained-worker capture additionally records all five actual native
configuration/home/data/temp paths. Each resolves to its expected isolated run
path, and the native process has zero open documents before and after capture.
Its eight selected geometry/mesh records and nine fixture records reproduce
the preceding successful capture exactly. No fields were retrospectively added
to the earlier raw report.

## Windows compatibility foundation

The isolated addon smoke records actual imported module paths within the pinned
Fasteners/Gears checkouts and the bundled numerical-library paths. It prepares
a separate static Art1 wrapper from the original cached Body and interface
placements. This is the prior static compatibility route, not adoption of the
unsuccessful procedural candidate. Independent source-versus-wrapper XML checks
find zero difference in the 24 interface datum positions and quaternion basis
rotations; all datum types are preserved.

The subsequent Windows assembly audit completes 53 documents and 3,001 objects,
all reporting their own state Up-to-date, with no recorded errors and zero open
documents afterward. Its five actual native paths remain inside the fresh run,
and both retained worker/runner hashes agree. Independent after-run checks find
all 57 original native files and 589 addon blobs unchanged, with clean addon
worktrees. In the compatible working copy, the other 56 native files remain
byte-identical and only Art1 has the recorded static wrapper. This audit uses
`recompute=changed` and `shape_scope=none`: it establishes restore/state/software
compatibility evidence, not force-all recomputation, whole-shape validity,
contact, kinematics or physical performance.

## Cached metric semantics follow-up

The [metric-definition audit](thor-native-metric-semantics.md) received separate
source and numerical review. All 21 primary-source files were independently
fetched from their exact FreeCAD/OCCT commit URLs; all 700,377 bytes agree with
the local receipt. The source explains the API's integration, bounding and
distance definitions, without reconstructing every distributor patch or proving
the cause of the observed Art1 discrepancies. All 149 combined CAD/metric tests
pass in the reviewer-run suite.

The actual cached-geometry experiment preserves original/candidate/input-copy
and retained code/helper/request hashes, five isolated paths and zero open
documents. Independent box formulas confirm its translated-boundary and interior
point controls. All six directed sample sets contain 95 vertices; their reported
maxima reproduce from the recorded rows, whose coordinates are float32
representable. These are sampled mesh-point observations, not continuous surface
separation or a Hausdorff bound.

Optimal unmeshed Z maxima differ by 1.927540438e-8 mm. Meshing changes default
bounds while leaving volume, COM and geometric inertia unchanged. Some observed
post-mesh bounds lie inside the tighter unmeshed extrema, so they cannot be
treated as guaranteed conservative geometry envelopes. Both Boolean differences
are non-null empty compounds with no solids, faces or edges. Across the three
mesh settings, candidate-minus-source triangle-volume integrals are approximately
`28.943437889`, `-1.607588449` and `0.0035764224` mm³; they change sign and do not
quantify integration error. The native volume discrepancy persists.

These observations narrow the interpretation of old metrics. They do not prove
that numerical integration explains the entire difference, that all surfaces
coincide, or that the candidate is acceptable. The existing datum, reference,
volume and failed radius-roundtrip gates remain intact. No original/historical
report was rewritten and no CAD, physical or fabrication acceptance was granted.
