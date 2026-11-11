# Offline evaluation independent review

Review scope: the desktop run's new `evaluation/replay.py` and
`evaluation/benchmark.py`, their existing-sorter adapter, and evaluation tests.
This is software/source review and synthetic replay evidence. No robot,
camera, native CAD, physics engine or physical outcome was exercised.

## Independent checks

- An independent outcome oracle generated 100 seeded layouts containing
  2,000 objects. Cases included excluded and missed objects, detections without
  attempts, active attempts at log truncation, timeouts, exhausted failures,
  incorrect-bin placement followed by retry, first-attempt success and assisted
  placement. Every tested count and eligible end-to-end denominator agreed.
- An unequal-denominator fixture used ten successful objects in one layout
  and one failed object in another. The pooled cycle proportion was 10/11;
  it did not average the two layout proportions. Whole-layout resampling
  produced the expected [0, 1] percentile interval. A single layout produced
  a null bootstrap interval.
- Twenty independently checked seeds used the existing logical sorter with
  ten eligible objects, one unreachable object and one injected failed grasp.
  Each replay reported nine correct placements, ten attempted objects,
  eleven presented objects and two failed attempts. Eligibility was declared
  before the task ran; exclusion did not remove the object from the presented
  denominator.
- Input probes rejected scalar and nested exponent overflow (`1e309`),
  `NaN` and positive/negative `Infinity`, nested duplicate JSON keys and the
  configured total-file byte limit. Event ordering, verification requirements,
  retry bounds, unknown objects and schema/type rejection are also covered
  by the implementation's focused tests.
- Independent CLI probes exercised successful scoring (exit 0), an empty
  event log preserving all unresolved eligible objects (exit 1), malformed
  records and invalid bounds (exit 2), unknown fault IDs, and preservation of
  an existing output file. A two-layout benchmark with an unreachable object
  and failed grasp in each layout reported 4 correct / 6 eligible / 8 presented.
  These probes used `python -m raftel_arm01.evaluation.cli`; installed entry-point
  and wheel checks are separate integration checks.
- The twelve installed-source byte hashes and replay canonical digests were
  inspected. Wilson boundary checks now accept the advertised aggregate maximum
  of 10,000,000 objects. The latest reviewer-run focused replay suite passed
  32 tests, with scoped Ruff lint and format checks passing.

## Findings and disposition

1. The first parser rejected nonfinite JSON constants but initially accepted
   exponent overflow. The implementation now uses a finite `parse_float`
   guard; independent scalar and nested probes pass.
2. Per-line and record-count limits initially allowed an impractically large
   total file. A 64 MiB aggregate byte limit is now enforced; an independent
   reduced-limit probe passes.
3. The aggregate layout range can exceed the original one-run Wilson trial
   bound. The trial bound now matches the aggregate range; independent
   10,000,000-trial endpoint checks pass.
4. The logical fixture's canonical input hash binds its scene, configuration
   and injected failures. It initially omitted implementation bytes. The
   input now includes package version and installed source hashes, so those
   source revisions affect the input hash and run ID.
5. The first CLI implementation reopened the manifest to compute a raw hash
   after validation. That could bind different bytes after a concurrent edit.
   It now hashes the validated manifest model once, explicitly labeled as a
   model canonical digest, with no second file read.

No blocking finding remains in the reviewed evaluation worktree. Root still
owns installed entry-point/wheel verification, additional integration fixtures
and exact-head CI. This review does not itself approve an exact release head.

## Evidence limits

Correct placement requires a matching active attempt and an explicit
independent-observation claim. Commands or detections alone cannot score a
success. Assisted objects remain in denominators and do not count as
autonomous success. Misses, timeouts and incomplete logs remain visible.

Evidence class and observation provenance are input claims, not authenticated
physical evidence. The adapter fixes generated sorter runs to `logical_only`.
Object-level Wilson intervals ignore within-layout correlation; whole-layout
bootstrap summaries assume independently reset layouts, which unique IDs
cannot establish. No simulated proportion qualifies the physical sorting
target.

## Installed-wheel verifier review

The verifier, its guard tests and the `raftel-evaluate` entry point were reviewed
separately. Root reported a successful fresh-environment installation and CLI
smoke; this reviewer did not repeat that positive installation. The final
reviewer-run focused guard suite passed all twelve tests.

Review identified a mutable-path provenance gap between reading, inspecting and
installing the wheel. The verifier now takes one bounded byte snapshot, inspects
it through `BytesIO`, stages those same bytes for installation and checks the
staged hash after the smoke. The imported module origins are recorded and
required to lie within the fresh environment, rather than checking only the
root package path.

A synthetic archive reproduced acceptance of a Windows-drive metadata path.
The validator now requires the exact distribution metadata prefix and rejects
colon-containing member paths, including alternate-stream syntax. This review
performed no installation of a malformed archive.

The fresh working directory and cleared Python path environment establish a
source-free import check; the tool does not require the scratch directory to be
physically outside the checkout. `--isolated --no-index --no-deps` exercises a
local wheel installation without a package index. It is not a network-isolation
or hardware validation test.

Malformed INI and interpolation errors now normalize to input errors, and
duplicate identity headers are rejected. Focused negative fixtures cover
malformed INI, colon paths, drive-prefixed metadata and duplicate identity.
No blocking wheel-review finding remains. Exact-head CI and final integrated
publication remain root integration checks.
