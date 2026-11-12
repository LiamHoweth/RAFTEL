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

## Subsequent numerical and source checkpoints

Covariance validation now normalizes before Schur products. Independent tests
cover 8,400 known-spectrum matrices using separate Householder rotations and
seven scales from 1e-300 to 1e300. Valid full-rank and semidefinite matrices pass;
negative spectra fail without changing the returned SI values. The 86 focused
frame/observation tests pass. A separate inertia fix normalizes before symmetric
averaging and triangle checks: 15,032 independent cases include positive and
negative true-minimum subnormal identities, a valid 1.7e308 identity, rank/triangle
controls and 600 rotations over five spectra and five scales. These checks close
the reproduced overflow/underflow bugs; they do not establish measured inertia.

The standalone native property worker passes the same 15,032 independent
extreme/spectral cases. A fresh matching-worker capture additionally repeats
all eight selected property/mesh records and all nine native fixtures exactly.
Its tracked normalized report is byte-identical to the actual capture, with
isolated paths, zero documents and preserved runtime/source/code/request/output
pins. The prior v1 and all six full-print batch captures remain unchanged and
bound to their earlier executed worker; the new capture does not retroactively
replace their code identities.

The copied-source GRBL warning candidate changes only `gcode.c`: it introduces
a defined uint32 value-word mask, widens the local value-word accumulator and
changes its three dynamic value-path masks. Independent token normalization
confirms that command masks, global `bit`, axis dispatch and other source files
are unchanged. All 72 baseline source blobs match their pins. A separate ELF
reader verifies four compiler-only AVR objects and the 22 static probe values,
including 17 distinct masks and Y/Z duplicate/cleanup controls. Twelve focused
tests pass. The remaining M95 warning is retained; no parser execution, linked
candidate, firmware installation or runtime repair is claimed.

Independent coupon review finds all three stepped annular meshes closed under
the declared exact-edge/vertex-link checks, with 576 vertices, 1,152 facets and
Euler characteristic zero each. Facet normals and the analytic polygonal annulus
volumes agree. Bore diameters 5.9/6.0/6.1 mm are dimension studies; outer diameter
and upper depth remain explicitly assumed. Strict source/profile/schema guards,
fresh output preservation and unchanged mesh/report reproduction pass 45 tests.
Blank measurements and physical fit remain unknown; coupon mass cannot become
installed arm mass.

The third-party notice audit passes 45 focused tests and separate negative
reprobes for receipt schema, source revision, path traversal, release identity,
incomplete creator attribution and nonfinite draft JSON. Its full report
reproduces exactly. The 57 native XML notices, 540 Fasteners entries, 49 Gears
entries and 17 retained generic drafts remain separately attributable. Root,
header, package and embedded declarations are observations, not a decision about
license applicability, company licensing or release permission.

The runtime configuration loader now explicitly decodes UTF-8 for external paths
and packaged defaults. Independent review of the two-file change and 54 sorting
tests confirms exact unescaped French, Scandinavian and Japanese category values,
without changing the schema, default configuration or hardware behavior. This
fixes Windows locale-dependent silent text corruption rather than normalizing
or replacing the supplied identifiers.

## Limited native wrist and pose evidence

The native three-pose wrist diagnostic is explicitly partial and failed closed.
Its raw capture and runner match the published byte hashes; all 57 original
source files and retained scripts remain unchanged. The three source gear
matrices agree with the historical handedness capture within 3.802e-18 per
element. Seven of ten pair rows, three of four rigid-fold checks and 11 of 14
planned Boolean operations were recorded. Independent checks reproduce each
side-angle equation and the three fold-volume residuals, whose maximum is
7.689e-9 mm³. The next common operation reported a negative volume before its
value or topology was checkpointed. They remain unknown in that original capture.
The final
in-memory placement comparison was not reached; its initial false flag does
not demonstrate a mutation. Forty-eight host tests pass. No contact, mesh,
constraint, retention or physical qualification follows from these observations.

A separate one-pair capture preserves the original operand order and pose:
plate fold -20 degrees, carried roll -15 degrees, positive-Y pinion +10 degrees.
It records aggregate signed volume -0.5552516265803887 mm³, while three Forward
solids have positive volumes summing to +0.10630907314212505 mm³. The difference
is -0.6615606997225137 mm³. The common reports Compound/Forward and native
`isValid=True`; this is a BRepCheck observation, not material-orientation proof.
Constituent membership, per-solid face/shell counts and the resulting common
BRep were not captured. Four primary source blobs support a possible volume
integration mechanism, but cannot establish this result's cause or exact
packaged-DLL/source correspondence.

All 57 originals, 57 compatible copies, 589 addon files, runtime and four
executed snapshots match their pins; the raw capture/runner copies match exactly,
five paths remain isolated and document counts are zero. Ninety-four combined
host tests pass. The source and diagnostic gates preserve negative/invalid
observations without reversing/healing shapes, substituting absolute volume or
accepting geometric intersection, physical mesh or fabrication.

A further one-common topology capture retains the raw 900,661-byte debug BRep
and exact `isSame` membership/occurrence ledgers. Independent review reconciles
all 11 faces into three solids with 3/4/4 faces and one closed shell each;
no unowned faces or shells are observed. This does not support the proposed
free-face mechanism for this result. `isSame` ignores orientation, so common-face
membership does not authenticate owner-context orientations or identify the
integration cause. Twenty-nine host tests and actual runtime/source/copy/addon/
five-snapshot/context/BRep pins pass. The original signed result, failure
evidence and all physical/material gates remain unchanged.

The separate copied-assembly K1 capture uses four cases, including saved zero
and three bounded proximal-joint increments, with q5/q6 fixed at zero. Review
parses the pinned Xacro directly and uses an independent fixed-space
product-of-exponentials calculation, without the production chain/frame
helpers. Across 24 native axis observations, maximum axis-line error is
2.831e-16 m and direction error is 2.231e-15. The four observed fold matrices
agree within 8.327e-16 in matrix/translation components. A raw linked-shape
vertex moves with the observed parent delta within 2.275e-13 mm, with 6,129
vertices preserved; this guards against accepting placement-only stale geometry.

All 16 right-increment offset readbacks and unchanged placement expressions
were independently checked, with exact nominal reset. All 57 compatible source
and copied-file hashes, retained/current worker, helper, request, executable
and imported module pins match. The five actual paths resolve to their isolated
destinations; zero documents remain open. The fresh matching-worker run retains
53 documents/3,001 final object records, including 39 Touched states and no
Invalid/Error states. Eighteen host tests pass, including preserving documents
that caused the fresh-process guard to reject. This is limited source-frame
evidence, not a full six-axis forced-history rebuild or physical calibration.

## Full printed-variant preparation and native batches

Independent review authenticates all 57 original archives against the pinned
upstream Git tree and verifies all 47 requested XML objects, types, Shape entries,
BRep hashes and placements. The installed ID set independently equals the load
classifier's 65 printed instances. Art1 retains original source `8afa16…`, and
the reflected finger is the actual saved `Part::Mirroring` geometry. The six
requests preserve selections exactly in batches of 8/8/8/8/8/7 and pass the
unchanged eight-selection worker. Strict manifest schema negatives and the
focused preparation/source/worker suite pass 67 tests.

All six actual batches independently verify 47 distinct cached-geometry exports,
covering 65 installed instances and 325,810 triangles. Each run verifies nine
primitive fixtures, all source/copy/runtime/script/request/STL pins, five
isolated paths and zero CAD documents. Fixture tensor error is at most
4.402e-15 relative; unit conversions and positive-semidefinite/triangle checks
pass for every selected tensor. The eight overlapping earlier captures reproduce
both properties and STL bytes exactly. The reflected finger is the distinct
saved mirrored BRep, with matching X-reflection COM/tensor signs, rather than a
replacement invented by the export tool.

All twelve published capture/runner files are byte-identical to their retained
actual reports. Aggregate variant rows cover the same 47 IDs and 65 unique
installed IDs, with quantity-weighted cached volume 3,485,323.1228679037 mm³;
the difference from the prior inventory sum is -4.657e-10 mm³. Per-source tensor
frames remain distinct, density remains null and no cross-frame whole-arm tensor
is formed. These checks establish the declared cached exports and accounting,
not triangle topology, continuous surface fidelity or fabrication readiness.

The separate reusable join/host verifier passes 64 focused tests and independent
coherently rehashed negatives: contradictory native STL qualification, native
paths outside the batch root, unsafe provenance pointers, false earlier-capture
repeatability, static Art1 substitution and nominal-as-reflected substitution
all reject. Earlier-capture observations are separately hash-bound. Canonical
regeneration matches the frozen host report exactly.

An independent counter over all 325,810 raw facets confirms two native mesh
blockers: Art23Optodisk has four boundary edges and represents two installed
instances; Art4TransmissionColumn has three nonmanifold edges and represents one.
The declared host criteria therefore yield 45 candidate geometry variants/62
instances and two blocked variants/three instances. These are topology/draft
classifications. Original Art1 history, self-intersections, source-surface
fidelity, actual fit and physical/process qualification remain separate gates.

The separate queue constructor passes 70 focused tests after reusing the existing
per-candidate preflight before returning or writing a plan. A coherently edited
host report that tries to admit blocked Art23 rejects before any output creation.
The valid queue still reproduces its original bytes: 44 variants/61 generic
one-part 3MF projects, with Art1 and both topology-failure variants blocked.
Independent ZIP/XML parsing checks every package's Core parts, millimetre units,
single build item, metadata, source/license pins, quantities and placements.
Reconstructed indices reproduce all 321,678 source facets' float32 coordinates,
order and winding exactly. No machine-native process project, GUI import,
slicing, G-code, cloud upload or printer command is established.

## Transmission-column mesh diagnostic

Independent struct-only STL parsing confirms 14,016 facets/6,988 exact vertices
in the selected native mesh and 42,604 facets/21,282 vertices upstream. Both
contain the same three four-facet nonmanifold edges at z=17 mm, with total chain
length 0.008910003714817056 mm. The selected native mesh has no boundary,
duplicate or zero-area facets. Its retained native point/facet arrays reproduce
every prior binary STL triangle in the same order.

The actual isolated native precision experiment completes in 5.53 seconds with
zero CAD documents and preserved original/copy/runtime/script/helper/launcher
pins. MeshPart's 20,964 coordinate components are already binary32-exact. The
separate `Part.tessellate` route returns double-coordinate arrays yet also has
three four-facet edges before explicit binary32 rounding. Rounding loses no
exact points and does not change incidence in that route. This excludes final
STL packing as the sole origin of the observed defect; it does not identify an
underlying mesher or source-surface cause. The two meshing routes have different
settings and are not controlled equivalents.

Eight exact-commit source files support the precision/API descriptions. The
full host report reproduces exactly, all nine retained raw-evidence hashes and
all eight source hashes match, and 54 focused tests pass. Future-run guards now
reject a conflicting generic-audit opt-in before helper execution and reject
contradictory repaired/release flags. Those guard patches remain distinct from
the immutable earlier executed snapshot. No mesh repair, continuous surface
fidelity, collision enclosure or fabrication release is established.

## Box-proxy mathematics fallback

The K4 fallback supplies reusable declared-box mathematics while reporting zero
verified mounted-body proxy bindings. Independent review uses corner/segment
clipping against the other box's local slabs, rather than another SAT
implementation. All 1,250 random oriented-box pairs agree across five scales
from 1e-100 to 1e100; swapping the pair preserves classification. Independent
corner projections reproduce the reported normalized-axis support gap within
8.882e-16 times the fixture scale. Forty-six focused tests cover the required
edge-cross-edge separator, tangency, near-parallel axes, tiny/large inputs,
overflow rejection, rigid-frame covariance, exact-pair exclusions and source
contract negatives.

Inventory/membership schema, revision, evidence classes and coordinate frames
are checked before reporting 518-identity coverage. Exact input bytes remain
hash-bound. A common supplied frame ID does not authenticate registration; a
caller must provide any required known transform. Intended-contact exclusions
retain their raw pair result and evidence, without automatic adjacency skips.
Synthetic fixture geometry and the arbitrary nominal-FK cube remain visibly
separate from real robot enclosures. No mounted collision witness, conservative
source enclosure, obstacle coverage or intersample swept-path result is claimed.

## Installed cached-geometry bounds

The separate mounted-bounds capture covers all 518 unique installed identities.
Independent review authenticates all 57 originals, the 57 compatible copies,
589 addon files, retained worker/helper/request/launcher/runtime pins and three
raw report references. Five nested/rotated LinkTransform fixtures pass before
source capture. All 518 quaternion/matrix and ancestor-times-own-placement
identities agree within 1.137e-13 mm; independent eight-corner SI AABBs agree
within 2.776e-17 m. Native-copy COMs agree with the walker within 3.615e-16 m and
the historical inventory within 3.332e-16 m. There are no missing identities,
five actual paths remain isolated and zero CAD documents remain open.

The curated receipt preserves every numeric/state/matrix/bounds field from the
raw capture and references its exact bytes. Twenty-nine host tests pass,
including the 50 GiB plus 128 MiB reserve guards and preservation failures.
The capture deliberately does not force histories: final states include 1,147
Up-to-date and 1,854 Touched objects. Observed default/optimal extrema differ
by as much as 28.4118 mm. This adds a zero-pose numerical transform/bounds
ledger without establishing a conservative solid enclosure, nonzero rigid
ownership, collision margins or physical coverage.

The subsequent saved-zero AABB comparison passes 37 focused tests and exact
report regeneration. Independent endpoint arithmetic enumerates all 133,903
unordered pairs: 1,647 optimal-bound candidates, 1,692 default-bound candidates,
45 default-only, zero optimal-only and 132,211 neither. Every retained union row
has independently verified IDs/indices and both raw three-axis gap triplets;
grouping, deterministic ordering and separated witnesses agree. Separate SAT
arithmetic on the 1,647 selected optimal candidates finds no classification
disagreement, with at most 1.11e-16 m gap roundoff. All selected pairs classify
as interior box overlaps under the explicit numerical policy. Bounds are already
world-frame metres and receive no extra scaling or placement. These comparisons
neither exclude intended-contact pairs nor establish a real collision or clear
pose; saved geometry states and unknown enclosure/swept coverage remain visible.

## Declared linear swept-box primitive

The separate T2 preparation primitive passes 32 focused tests. Independent exact
`Fraction` arithmetic checks 2,000 cases across all 24 proper signed permutations
and five dyadic scales from 2^-800 to 2^800, including stationary coordinates,
zero widths, negative displacement and numerical padding. Every overlap predicate
and normalized interval endpoint agrees for these fixtures. The hand-computed
midpath witness retains [5/16,11/16] despite separated endpoints.

Both moving endpoints and the static obstacle must remain exactly axis-aligned;
identity, extents and frame declarations are checked. Unsupported rotations,
resizing, joint-path assumptions and unrepresentable widths/crossings reject.
Seven synthetic cases, input hashes and report reproduction pass. Caller frame
IDs and motion evidence are declarations, numerical padding is not a physical
margin, and arithmetic is not certified interval computation. No source body,
joint trajectory or measured obstacle is bound; full T2 and robot swept clearance
remain open.

## Optodisk tessellation diagnostic

The optodisk core passes 44 focused tests and independent supplied-scope negatives
for outside paths, unrequested isolation and wrong upstream bytes. All 14 raw
evidence pins and actual runtime/source/BRep/snapshot/path/zero-document records
verify. Each route begins with a fresh shape; retained point/facet arrays
reconstruct every exported STL triangle in order.

Independent binary parsing and exact rational arithmetic confirm the original
four boundary edges form a self-crossing planar cycle at z=5 mm, crossing near
(-27.9234264234,3.8759642307,5) mm. This is not a valid fill-area measurement or
a full self-intersection analysis. The linear-only Part alternative exactly
matches upstream oriented cyclic-facet and unindexed-vertex multisets, including
multiplicities; the refined alternative differs by 12 facets each way. Both
alternatives independently have 1,332 vertices, 4,002 edges and 2,668 facets,
opposite winding on every paired edge and one cycle per vertex link. Different
route/settings do not isolate the source of the original defect. No source
solid was edited, repaired-history acceptance granted or fabrication released.

## Independent-distributor integration study

The [adaptive study](thor-adaptive-metric-study.md) passes 31 host tests and
independent reconstruction of all eight actual capture/runner files. Both wheel
digests match primary PyPI metadata; all 932 RECORD/extracted-file bytes verify.
Before/after inventories authenticate 46 loaded TK DLLs inside the separate
wheel root, without FreeCAD/Part imports. The distributor binaries are distinct
from FreeCAD's kernel; version agreement alone is not source/build equivalence.
All original/copy/runtime/interpreter/PowerShell/package/code/request pins and
the earlier failed curations remain intact.

The first capture fails before retaining its cylinder method row, which remains
unknown. The next capture preserves all 18 fixture rows: three regular adaptive
Gauss cylinder tensors fail the unchanged relative 1e-9 tensor gate, despite
small returned mass estimates. A separately versioned experiment retains that
failed gate and permits only default/GK after all 12 corresponding controls pass.
No threshold is relaxed. Default Art1 volume, COM and tensors exactly reproduce
the prior raw-BRep FreeCAD metrics. GK candidate-minus-source volumes vary from
-0.0279745804 to -0.9263827693 to -1.0069504928 mm³ as requested epsilon changes.
Returned estimates exceed requests at every setting. This does not prove equal
geometry, a limiting value or a complete quadrature explanation.

A distinct protocol reads only the self-generated wrist Common BRep. Default
`OnlyClosed=False` reproduces the negative aggregate; `True` reports
+0.106309073143 mm³, agreeing with the Solid sum within 1.39e-17 mm³. GK reports
+0.237115898415 mm³ versus a Solid sum +0.237115865417 mm³, a 3.30e-8 difference,
again with an estimate above its request. All 11 global/owner faces match both
`IsSame` and orientation-aware `IsEqual`, with 3/4/4 owner counts. Retained OCCT
source confirms the closed-only route also changes grouping/reference context.
The observations establish method/flag dependence without establishing a
physical penetration volume, orientation cause or accepted overlap. The final
reusable context pin is explicitly a later guard patch; immutable executed
snapshots remain intact. Prior failed migration gates and physical qualification
limits remain unchanged.

## Art1 semantic-support signatures

The semantic-support capture receives independent source and numerical review.
The original XML contains 53 dependent owners and 80 unique references: 69
Face/Edge selectors and 11 whole datum/axis references. All 19 geometry-provider
BReps match exact source ZIP entries and hashes, and all 19 source/native frame
traces have zero residual. Four native coordinate fixtures precede candidate-only
restore. Source/copy/candidate/runtime/nine-snapshot pins, isolated paths and zero
documents afterward verify; no recompute, save, remap or adoption occurs.

Independent matching arithmetic reproduces 62 unique candidates, six unmatched,
one unsupported BSpline and 11 whole datum/axis cases. All 80 curated native rows,
selected/literal descriptor joins and 38 removed-array counts/kinds/canonical
hashes match the raw report. Forty actual-evidence tests pass. There are 21
different raw selected indices and 41 literal strict matches; raw `Faces`/`Edges`
indices are not persistent-name or `getSubObject` resolution. They therefore do
not establish 21 attachment errors or validate migrated references. Ambiguity,
unsupported geometry and frame uncertainty remain explicit.

Actual Run02 remains bound to executed snapshot `ca5204…`. A later guard moves
request containment before its first read and bounds JSON allocation; those
controls have separate regressions and do not retroactively alter the capture.

Separate Run03 adds literal public getter and owner-property witnesses. Its 50
misses when reading the old `Support` name are not model defects or measured
native fallback types: `Part.Feature` in a Python exception is a wrapper class,
and `openDocument(..., True)` selects hidden mode rather than partial loading.
Run04 records all 90 native TypeIds, which exactly match the saved candidate XML.
Independent XML/runtime decoding authenticates 50 `Support`→`AttachmentSupport`
schema aliases and 19 unchanged `ExternalGeometry` entries. All 69 runtime
entries equal their saved XML; both public getter paths equal the raw current
selector, and all 62 unique descriptor matches equal that current selector.

All 80 prior base facts, retained curations and removed-array fingerprints remain
unchanged. Forty-eight tests and independent provenance/join checks pass. This
authenticates typed cached/readback behavior and resolves the property-name
capability question. It does not prove attachment-engine reevaluation, establish
21 broken attachments, remap supports or accept procedural migration.

## Installed printed-tensor reference model

The actual native capture authenticates all 65 installed printed copies from 47
source variants, including the actual saved reflected finger. Independent review
checks all 8,612 ordered vertices, noncollinear witnesses, proper placement
deltas, source/link identities and moments. Every one of 53 loaded documents
resolves to the private source path and pinned bytes. Source properties reproduce
the full47 capture exactly. Maximum vertex residual is 1.947e-13 mm, relative
volume residual 1.647e-15, COM residual 2.298e-13 mm and relative tensor covariance
residual 1.051e-14. World COM agrees with the mounted ledger within 2.511e-16 m.
Originals, compatible/private copies, addons, inputs, scripts, runtime, isolated
paths and zero-document cleanup verify; no assembly history is recomputed.

Independent fixed-origin scalar quadratic moments, followed by a shift to the
combined COM, reproduce the uniform-solid reference tensor within 2.78e-17 kg·m².
At the explicitly assumed density 1,240 kg/m³, this printed subset has reference
mass 4.3218006723562015 kg and native-world COM approximately
(-0.01718382371637,-0.00028499723849,0.23423980985378) m. This is not a measured
print or slicer-infill model. Nonuniform prints, purchased interiors, physical
and whole-arm inertia remain unknown; the existing gravity ledger is unchanged.

The host gate passes 68 focused tests and independent coherent-poison reprobes
for schema, class, scopes, preserved maps, path containment, runtime/receipt
contradictions and COM unit identities. Bounded strict UTF-8 JSON rejects duplicate
or nonfinite input. Only two diagnostic floats receive a narrow reproduction
tolerance; the actual marker gate remains independently enforced. Raw/curated
capture and study bytes remain unchanged. Cached default-GProps uncertainty and
continuous-surface equivalence are not certified by these frame checks.

A final raw Git-blob audit against starting revision `6608d37` finds all 30
original CAD-evidence/config JSON or geometry files byte-identical and present.
This complements the downloaded-original CAD and addon ledgers; new results
remain separate from the historical inputs and reports.

## Offline fault and retry witnesses

The [fault-injection pack](thor-fault-injection-study.md) receives independent
review against the existing replay, mock and sorter contracts. Its eleven
cases preserve five protocol latches, demonstrate the unsafe doubled effect of
blindly retrying an unacknowledged increment, and distinguish ordinary false
grasps from aborting faults. Retry budgets 1, 2 and 5 exhaust exactly their
declared attempts while accounting for the next presented object.

Independent release-before/after-effect fixtures reproduce identical observer
traces and different privileged held/placement truth. Both abort with unknown
held state, no sorted claim and the second object pending. Repeated stop,
rejected operations and rerun preserve each world's oracle state and the pack's
explicit uncertainty. This bookkeeping is local to the diagnostic pack, not a
new core sensing or recovery capability. Thirty-five focused and 136 combined
tests pass; a separate ten-seed sweep reproduces all 110 expected case outcomes.
Strict bounded configuration, implementation fingerprints and exclusive output
preservation verify. These are synthetic fault witnesses, without real feedback,
physical stop validation or full E3 commissioning acceptance.

## Weighing metadata companion

The [measurement-readiness sidecar](thor-measurement-readiness.md) reuses the
existing fabrication validator and binds the complete fabrication document,
individual weighing rows and manifest. Independent review reproduces all three
reported canonical hashes and the unchanged 65-row unknown template. Fifty-five
focused tests pass independently; the owner reports 137 related tests passing.

Known declarations require finite positive uncertainty, a coverage factor at
least one, consistent expanded uncertainty and explicit contribution/applicability
evidence. Calibration windows use the measurement instant, with later expiry
reported separately; future records and applicable retrospective invalidation
block readiness. A finding cannot predate the declared calibration time. Unknown and
synthetic support cannot complete observed readiness. Bounded strict UTF-8 JSON,
contained nonsymlink artifact paths, byte hashes and overwrite refusal verify.
Readiness means matching declarations and local supporting bytes are available
for engineering review. It authenticates neither certificate contents nor
metrology, uncertainty adequacy, actual mass or manufacturing qualification.

## Evidence navigation and pending slicer inspection

The [evidence index](desktop-evidence-index.md) receives factual scope and local
link review against the C14 artifacts. All 46 local links resolve. In particular,
typed cached getters do not validate the attachment engine or accept a support
remap. The index separates 61 native-origin drafts from the two source-optodisk
drafts and preserves their independent qualification gates.

The [desktop inspection plan](thor-anycubic-desktop-planning.md) has five actual
one-object millimetre 3MF inputs. Independent ZIP/XML review checks filenames,
recorded dimensions, identity rotations, bottom placement, attribution and copy
counts: CommonBearingFix is one of four, and each listed ring, top and distinct
finger is one of one. The source-Z-up pose remains provisional. No successful
model import, rendered plate, native project save or slice is claimed by this
plan review. Live observations require a separate awake-desktop session; the
prepared inputs do not confer physical fit, print or fabrication acceptance.

## Declared radius, efficiency and sharing sensitivity

The [drive sensitivity study](thor-drive-sensitivity-study.md) adds 63 explicit
samples: nine parameter points and seven instantaneous rate cases for one
`shoulder_horizontal_saved` gravity row. Source countertorques retain their
signs. Independent rational arithmetic verifies 1,200 cases spanning both belt
signs, carrier coefficients, shoulder allocations and individual efficiencies.
Output virtual work and per-port input power agree; carrier reaction uses the
elbow output effort rather than a loss-scaled rotor effort. Mixed power flow and
zero-net-joint-power cases still retain their nonnegative modeled losses.

Forty-four focused and 88 combined tests pass. Independent report reconstruction
matches SHA-256 `50d0fe2b2e4b65d373f29f87866493a77410a9cd5d89137b49b71661df2a01c2`.
All four code pins, raw/canonical source hashes, 63 unchanged source effort
pairs, mass summary and five-file UTF-8/LF boundaries verify. Coherently rebound
inputs with changed units, revisions or qualification claims reject. Excessive
nesting and nonrepresentable moving/static intermediates fail clearly instead
of turning a nonzero demand into a known zero.

Independent maxima and witness joins reproduce B 0.286597450018833, C
0.21874236480542295 and E 0.16044372546060848 N·m among known samples. Their
14/14/9 unknown static samples remain visible and are not bounded by those
maxima. Nonzero effort at zero port rate has null input effort; zero mechanical
power supplies no holding-current or thermal-loss model. Explicit zero branch
allocation is a zero contribution only within this partial model. These are
declared quasi-static gravity contributions, without inertia, duty, measured
radius/sharing/efficiency, regeneration qualification or rated capacity.

## Current-document integration review

The final read-only documentation sweep verifies 154 local Markdown targets
across the 14 staged checkpoint files, with no missing targets. README,
architecture, spatial and fabrication descriptions distinguish implemented
offline studies from physical integration, preserve the 518/516 inventory
history and reconcile 47/65 exports, 45/62 host screening and 44/61 draft counts.
Saved-zero printed frames and three proximal-four-coordinate native cases do
not imply bench calibration, full six-axis geometry or accepted fabrication.
The evidence index separates the merged PR15 snapshot from the independently
accepted drive integration; the current handoff retains pending exact-head CI.
The accepted drive-report byte pin is unchanged. This sweep changes no code or
historical evidence and adds no native, UI or physical acceptance.

## Combined inspection-plate artifact

A separate ignored one-off composer prepares an eight-object generic Core 3MF
inspection plate; it does not extend or reuse the accepted single-object
inspector as a multiobject validator. Independent OPC/XML parsing checks its
three package parts, relationship/content types, millimetre units, eight unique
resource/build-item and installed-copy identities, and all 7,524 vertices and
15,112 triangles. Every source mesh XML, index order and winding is unchanged.
Identity rotations, XY-only rearrangement and the original zero-bottom Z
corrections verify. All eight complete source metadata/license/provenance maps
and nominal/reflected copy bindings remain intact.

Independent interval calculations check all 28 mesh-AABB pairs: minimum gap is
20 mm, and minimum margin inside the provisional saved-profile bed rectangle is
20 mm. All 63 original draft-directory files match the reviewer's separate
before snapshot. Package SHA-256 is
`68f4e0b621b3552b80e673125ab6eb98352e795b2bfa063ef9a7cc154f313bbb`.
The creation-time pending-review receipt remains unchanged; this record supplies
the separate artifact review. No process settings, G-code, GUI import, slice,
physical fit, support/toolhead clearance or fabrication qualification is obtained.

The tracked inspection-plate curation independently matches the immutable raw
receipt and package, composer/curator byte pins, all eight copy subsets and
metadata/native-binding digests, counts, translations and spacing. Its 63-file
preservation-map digest agrees with the separate before snapshot. The raw
creation-time pending review state is retained; GUI, slicing, physical and full
format-certification flags remain false.

The refreshed desktop handoff, inspection plan and evidence index pass a
read-only scope review with all 58 local links resolving. The original launch
prompt exists at Git revision `6608d37`; current merged commit `8f415ce` and
its exact implementation head `8576807` agree with the handoff. Native frame
capture and separate host reference aggregation are distinguished. Current
receipt pins are unchanged, and the refresh promotes no cached, logical or
artifact observation into engine, GUI, physical or release acceptance.
