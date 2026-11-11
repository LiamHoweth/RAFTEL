# Desktop independent evidence review

This review concerns source records, analytical models and offline software on
Windows/Python 3.14.6. It establishes no new native CAD recompute, gear contact,
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

The older CAD adoption/readme/native audit documents describe earlier stages.
Their statements about unavailable assembly import or the 516-leaf inventory
must be read as historical evidence, alongside the current v2 inventory and
[active handoff](../../nextSteps.md), not as interchangeable current reports.
