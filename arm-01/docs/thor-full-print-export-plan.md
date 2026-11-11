# Full printed-geometry cached export plan

[The full request](../hardware/print-planning/thor-full-print-export-inputs-v1.json)
describes **47 geometry variants, 46 source assets and 65 installed printed
instances**. Preparation reads original archives and XML only. It does not rebuild
feature history, export a mesh, qualify an orientation or authorize fabrication.

[The preparation tool](../tools/prepare_thor_full_print_exports.py) reuses
`prepare_thor_native_export_inputs.inspect_selection` and the existing fabrication
manifest. It reconciles every variant quantity and unique installed instance
against the preserved mounted inventory. Canonical hashes bind that inventory,
manifest, source inspection, each complete source-asset record, the full variant
registry, each instance set and saved object context.

All **57 original CAD archive hashes** are checked before and after descriptor
preparation against the existing pinned source inspection. The 47 selected objects
come from 47 archives; ten other original archives are also checked for preservation.
The authoritative upstream revision is Thor
`286b081fe6f056d87c379b884781ef77ff6a0159`. Raw byte matching authenticates against
the supplied inspection pins; the existing source acquisition evidence binds those
pins to upstream. It does not make a native rebuild or physical validation claim.

Each selection identifies its original archive/hash, internal object/type, exact
nonempty cached BRep member/hash, document XML hash, own XML placement and saved
support/link/group/expression context. Placement and context are retained as
evidence; they are not evaluated or applied again. Installed COMs remain explicitly
in their preserved assembly frame and no source-to-installed transform is inferred
from COM, bounds, an identity own placement or matching volume. Density is null.

The sole reflected variant selects the actual saved
`AssemblyArt56::Unnamed1_GripperFinger_mirrored` `Part::Mirroring` BRep, with its
saved Source-link context. It is not a second copy of the nominal finger mesh.
All 46 nominal variants select original final `PartDesign::Body` objects.

Art1 explicitly requires original archive SHA-256
`8afa16c8ff3adebd87e48b67dfb20d3224402bd517010dc112950a28f219690a` and its saved
Body member `PartShape.brp`. The unaccepted ThroughAll candidate is excluded even
if replacement metadata were made internally consistent. This cached export plan
does not close the original history, datum, roundtrip or 53-reference gates.
Art4TransmissionColumn also remains in this **inspection** request: its earlier
native cached mesh had three nonmanifold edges, so including its descriptor is
not print eligibility or a repair.

## Frozen worker limit and serialized batches

The existing native solid-properties worker remains unchanged and accepts at most
eight selections. The full 47-row request therefore intentionally fails that
worker's count bound. `worker_batches()` creates six independent compatible request
copies with **8 / 8 / 8 / 8 / 8 / 7** selections. Their concatenated rows exactly
equal the full registry, including quantities/context. Per-row full-registry counts
remain references to the 47/65 plan; they do not claim that one eight-row batch
captured all 65 instances.

From `arm-01`, prepare new output paths:

```powershell
.venv\Scripts\python.exe tools/prepare_thor_full_print_exports.py `
  --source-root ..\.work\native-foundation\Thor-original `
  --output C:\new-evidence\full-print-request.json `
  --batch-directory C:\new-evidence\full-print-batches
```

The CLI refuses existing output/batch paths and any output inside the original
source tree. It imports no FreeCAD runtime and launches no process. Host preparation
has produced the tracked request and six local batches under
`.work/full-print-export-batches-v1`; each batch passes the frozen worker's strict
request validator. Malformed identities, duplicate membership, unknown variants,
quantity disagreement, wrong source pins and source changes are rejected.

Native execution requires the root coordinator's explicit process-slot permission.
Each batch must use a fresh directory, retained exact worker/request/launcher,
verified executable hash, fresh source copies, isolated user/system/home/data/temp
paths, at least 50 GiB free and a bounded timeout. Preserve stdout/stderr and every
failure; verify all 57 original archives, copied inputs and retained snapshots
again afterward. Do not open CAD documents or recompute/save history.

Requested tessellation is 0.1 mm absolute linear / 0.2 rad angular deflection.
Those settings are diagnostics, not manufacturing tolerances. The native worker's
primitive fixtures and geometric property checks do not establish mesh topology,
self-intersection absence, surface fidelity, print settings or physical strength.
A subsequent host audit must retain actual failures and compare saved/raw/mesh
frames before any additional generic slicer drafts are prepared.

The full-series aggregate and six raw capture/runner pairs are separate new
evidence paths, preserving the original eight-selection capture and all earlier
drafts. Until all six independently checked captures exist, the full-series status
must remain incomplete. No G-code, printer/cloud contact, CAD repair, accepted
native migration or fabrication release is authorized by these records.

## Native series progress

Batch 1 completed between **22:03:46 and 22:03:57 UTC**, taking **11.378 seconds**.
Its [raw capture](../hardware/print-planning/thor-full-print-export-rawcapture-batch-01-v1.json)
and [runner receipt](../hardware/print-planning/thor-full-print-export-rawrunner-batch-01-v1.json)
are byte-exact retained evidence. Eight selected cached Bodies yielded eight draft
STLs containing 77,402 total triangles. Those eight variants represent ten of the
65 installed instances. All nine runtime primitive fixtures passed, all five
actual configuration/data paths were isolated, and zero CAD documents were open
before/after. No CAD document was opened, recomputed or saved. All 57 original
archive hashes, input copies and retained worker/request/launcher hashes stayed
unchanged. The source Art1 Body volume is 298648.100446804 mm³, confirming this
capture uses the original cached Body rather than the unaccepted candidate.

After the next root-authorized native slot, batches 2–6 ran **serially** between
22:11:36 and 22:12:05 UTC. All six batches completed with no errors, preserving
all 57 originals, input copies and retained snapshots. Every batch records its
own five actual isolated paths, zero open documents and nine passing primitive
fixtures. The native slot was released after batch 6; no prior batch or original
eight-selection baseline was rerun or overwritten.

| Batch | Cached variants | Represented installed instances | Native process seconds |
| --- | ---: | ---: | ---: |
| 1 | 8 | 10 | 11.378 |
| 2 | 8 | 10 | 5.082 |
| 3 | 8 | 12 | 3.655 |
| 4 | 8 | 10 | 5.421 |
| 5 | 8 | 15 | 6.891 |
| 6 | 7 | 8 | 4.629 |
| **Total** | **47** | **65** | **37.057** |

[The full-series receipt](../hardware/print-planning/thor-full-print-export-native-v1.json)
binds all twelve raw capture/runner file hashes, the full request hash, exact
selection order, 47 distinct source objects and all 65 unique installed-instance
IDs. It records **47 draft STLs / 325,810 triangles**. Each selection retains its
source binding, separate storage frame and geometric properties; there is no
cross-asset COM or tensor sum. Physical density/inertia remain null.

Quantity-weighted component volume is 3485323.122867904 mm³, matching the preserved
installed component-volume sum to about `4.66e-10 mm³`. This is a component sum,
not an assembled union, material usage, physical mass or print-time estimate.
All eight sources previously selected by the earlier native capture reproduce
their source bindings, cached properties and STL hashes exactly. That establishes
cached import/tessellation repeatability, not feature-history or surface-fidelity
acceptance. The original eight-selection report remains unchanged.

**Current capture coverage: 6/6 batches, 47/47 variants, 65/65 represented instances.**
This closes cached export coverage only. Full-registry host topology/fidelity
audit, actual slicer import/process behavior, orientation/support selection,
physical fit/strength and fabrication release remain separate gates. All such
qualification flags remain false; the original Art1 history gates remain open.

## Variant quantities

The request's source/context hashes and complete instance IDs are authoritative;
this table is a compact review aid.

| Source asset | Nominal | Saved reflected |
| --- | ---: | ---: |
| Art1Body::Body | 1 | 0 |
| Art1Bot::Body001 | 1 | 0 |
| Art1FanHolder::Body | 2 | 0 |
| Art1GearMotor::Body | 1 | 0 |
| Art1Top::Body | 1 | 0 |
| Art23Optodisk::Body | 2 | 0 |
| Art2BodyA::Body001 | 1 | 0 |
| Art2BodyACover1::Body | 1 | 0 |
| Art2BodyACover2::Body | 1 | 0 |
| Art2BodyAWindow::Body | 1 | 0 |
| Art2BodyB::Body001 | 1 | 0 |
| Art2BodyBCover::Body | 1 | 0 |
| Art2BodyUnion::Body | 1 | 0 |
| Art2MotorGear::Body | 2 | 0 |
| Art2SideCover::Body | 2 | 0 |
| Art3Body::Body002 | 1 | 0 |
| Art3Pulley::Body | 1 | 0 |
| Art3TensionerBody::Body | 2 | 0 |
| Art3TensionerPulley::Body | 2 | 0 |
| Art4BearingFix::Body | 2 | 0 |
| Art4BearingRing::Body | 1 | 0 |
| Art4Body::Body | 1 | 0 |
| Art4BodyBot::Body | 1 | 0 |
| Art4BodyFan::Body | 2 | 0 |
| Art4MotorFix::Body | 1 | 0 |
| Art4MotorGear::Body | 1 | 0 |
| Art4Optodisk::Body | 1 | 0 |
| Art4TransmissionColumn::Body | 1 | 0 |
| Art56GearPlate::Body | 1 | 0 |
| Art56MotorCoverRing::Body | 1 | 0 |
| Art56MotorHolderA::Body | 2 | 0 |
| Art56MotorHolderB::Body | 2 | 0 |
| Art56SmallGear::Body | 2 | 0 |
| BaseBearingFix::Body | 1 | 0 |
| BaseBot::Body002 | 1 | 0 |
| BaseBoxBody::Body002 | 1 | 0 |
| BaseBoxCover::Body | 1 | 0 |
| BaseTop::Body | 1 | 0 |
| CommonBearingFix::Body | 4 | 0 |
| CommonBearingFixThrough::Body | 4 | 0 |
| GripperActiveArm::Body | 1 | 0 |
| GripperArm::Body | 2 | 0 |
| GripperBot::Body | 1 | 0 |
| GripperFinger::Body | 1 | 1 |
| GripperPassiveArm::Body | 1 | 0 |
| GripperTop::Body | 1 | 0 |
| **Total installed instances** | **64** | **1** |

Thor/AngelLM and contributors retain attribution at the pinned revision, with its
repository-declared CC-BY-SA-4.0 and the existing embedded-metadata discrepancy
gate. Source license links and obligations remain in every selection's manifest
context. This plan selects no RAFTEL-wide license and flattens no upstream notices.
