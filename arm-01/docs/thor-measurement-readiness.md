# Cleaned-mass measurement metadata readiness

The existing `engineering/fabrication_records.py` validator already binds each installed printed instance to its source/variant, separates observed and synthetic records, and checks cleaned mass, instrument ID, scale resolution, repeat count, time, conditions and support/purge removal. The calibration-evidence schema covers transmission and channel parameters. Neither validates a weighing uncertainty declaration against an instrument's declared calibration validity or later invalidation.

`tools/thor_measurement_readiness.py` fills that narrow offline gap with a **companion sidecar**, reusing the existing fabrication validator. It introduces no second mass-entry form and changes no mass ledger. Readiness means only that the required declarations and matching local artifact bytes are available for engineering review. It does not authenticate certificate contents, instrument identity/metrology, uncertainty calculations, ambient conditions or a physical measurement. It grants no physical acceptance, hardware operation or manufacturing release.

## Blank template and identity

The [blank companion](../hardware/measurements/thor-measurement-readiness-template.json) corresponds to the existing 65-row fabrication template. All unknown uncertainty/calibration fields remain null, and no instrument is invented. Once existing weighing rows contain an instrument ID, template generation creates one blank calibration entry for each distinct declared instrument.

The sidecar binds the entire fabrication document by canonical JSON SHA-256 and separately binds every non-null weighing row by its own canonical SHA-256. Changes to mass, sample, instrument, conditions, source/variant, provenance or other fabrication content make the companion stale. Formatting-only changes preserve canonical identity. Manually rebinding a changed record requires reviewing its uncertainty and applicability evidence again; changing a digest alone supplies no physical evidence. The existing validator continues to reject sample reuse across installed instances and changed source/manifest identities.

Every supplied fabrication row must have exactly one companion row; instrument identities must exactly match its non-null weighing records. Unknown weighing cannot acquire a known uncertainty budget. Partial fabrication imports remain partial, with unreported installed IDs listed explicitly.

## Known declarations

A non-null uncertainty declaration requires:

- Positive finite standard uncertainty `u` and expanded uncertainty `U`, in kg, with finite coverage factor `k >= 1`.
- `U = k*u`, checked with **1e-12 relative tolerance and zero absolute tolerance**. Resolution alone does not supply uncertainty, and no confidence probability is inferred from `k`.
- A nonempty budget description and explicit true declarations that resolution, repeatability and calibration contributions are accounted for.
- References to uncertainty-budget and conditions-applicability artifacts. These record a human declaration; the tool does not judge their calculations or compare actual ambient conditions to the instrument specification.

A non-null instrument calibration declaration requires its declared observed/synthetic state, UTC calibration and validity-end times, applicable-conditions text and a local evidence reference. Its state must match the existing weighing record. This prevents synthetic calibration support from silently completing an observed weighing's readiness.

Each artifact reference is exactly `{"path": "relative/name", "sha256": "<lowercase SHA-256>"}`. Paths use contained relative POSIX names under an explicitly supplied evidence root. Absolute paths, traversal, backslashes, URI/drive syntax and symlinks are rejected. Files are hashed with a **32 MiB** read bound. Missing, changed or oversized artifact bytes block readiness. Matching hashes establish byte identity and availability only, without certificate-content authenticity or measurement qualification.

## Time and invalidation rules

An assessment requires an explicit UTC review instant, `as_of_utc`; it does not silently use the host clock. Sidecar calibration/invalidation times require UTC. Existing weighing timestamps retain their existing explicit-timezone contract and are normalized to UTC for comparison.

Declared calibration applicability is the half-open interval **[calibrated_at, valid_until)** at the measurement instant. A measurement exactly at validity end is outside the interval. A measurement made while the declared calibration was valid remains historically in-window if that calibration expires before review; current expiry is reported separately. This does not determine the instrument's true historical state.

Future measurements and future calibration declarations block readiness. An optional invalidation records its UTC finding time, the UTC time from which measurements are affected, a reason and an evidence reference. Measurements on or after that effective boundary are blocked, including retrospectively affected measurements previously inside the calibration window. A future invalidation finding or missing invalidation artifact also blocks the supplied assessment. The effective time cannot follow its finding time; no effective time is guessed.

Null calibration or uncertainty remains unknown and blocks observed readiness. Complete synthetic fixtures are counted separately and never count as observed-ready. Even an observed record with all metadata present is only **ready for engineering review**, with every qualification/operation flag false.

## Commands

From `arm-01`, using fresh output paths:

```powershell
python tools/thor_measurement_readiness.py template `
  --fabrication hardware/measurements/thor-fabrication-template.json `
  --output /path/to/new-companion.json

python tools/thor_measurement_readiness.py assess `
  --fabrication /path/to/existing-fabrication-records.json `
  --readiness /path/to/companion.json `
  --evidence-root /path/to/local-supporting-artifacts `
  --as-of-utc <explicit-UTC-review-instant> `
  --output /path/to/new-readiness-report.json
```

`--manifest` optionally selects the matching printable manifest. JSON inputs are bounded to one MiB before decoding and reject duplicate keys, nonfinite numbers and invalid UTF-8. Output uses UTF-8/LF and refuses overwrite. The tool opens no native application, hardware interface or remote service.

Tests use fabricated observations and files only. They cover stale whole-document/row identities, malformed uncertainty, unknown and synthetic states, calibration boundaries and expiry after measurement, future records, retrospective invalidation, missing/stale evidence, path escape attempts and strict JSON. No new physical mass, COM, thermal-duty or instrument qualification was obtained.
