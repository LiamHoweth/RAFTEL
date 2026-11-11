# Offline observation replay

[`perception/replay.py`](../src/raftel_arm01/perception/replay.py) replays supplied synthetic or recorded object observations using an explicit time, clock domain, frame and position uncertainty. It reads no camera, clock or hardware device. It preserves every predeclared presented object, every valid observation record and every policy rejection. Recorded data and provenance hashes remain supplied claims; replay does not establish calibrated accuracy or sorting outcomes.

This implements V1's data/replay boundary. Object detection, tracking identity, camera calibration, physical measurements and task eligibility remain separate work. The existing [logical sorter](architecture.md) and its synthetic generator remain unchanged.

## Input contract

The [versioned fixture](../tests/fixtures/observation-replay-v1.json) is a hand-counted synthetic example. Its manifest requires exactly these fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`; booleans and other versions are rejected. |
| `run_id` | Nonempty run identity. |
| `source_kind` | `synthetic` or `recorded`; neither asserts physical calibration or success. |
| `provenance` | Nonempty `description` and `source_id`, plus explicit `source_sha256`. A recorded source requires a declared SHA-256; a synthetic source may use `null`. Hashes identify a claimed external source artifact, without authenticating it. |
| `time_domain` | Explicit clock/domain identity, such as `simulation:layout-01` or a recording-specific monotonic-clock ID. |
| `units` | Exactly `{"position":"m","mass":"kg","timestamp":"s","position_covariance":"m^2"}`. |
| `coordinate_frame` | One source frame for all positions/covariances in this document. |
| `presented_ids` | Unique predeclared object IDs, including objects with no detections. |
| `observations` | Ordered detection claims, possibly empty. |

Each observation requires exactly `sequence`, `observation_id`, `object_id`, `timestamp_s`, `category`, `position_m`, `mass_kg`, `position_covariance_m2` and `uncertainty_evidence`. Sequences are contiguous from zero; observation IDs are unique. Object IDs must belong to `presented_ids`. A tracked object may have several observations; the source supplies that association and replay does not verify its correctness.

Positions contain three finite metre values, mass is finite and positive, and the acquisition timestamp is finite and nonnegative. Booleans and numeric strings are rejected as numbers. Position covariance is a symmetric positive-semidefinite 3×3 matrix in square metres, or explicit `null` for unknown uncertainty. `uncertainty_evidence` is required in both cases. A zero covariance is a supplied exact-noise scenario, not a replacement for unknown uncertainty.

Unknown fields, missing fields, wrong units, nonfinite numbers, malformed covariance, duplicate IDs and out-of-order acquisition timestamps invalidate the document. The bounded JSON reader additionally rejects duplicate keys, invalid UTF-8 and nonfinite JSON constants/exponent overflow. It reads at most 8 MiB. The replay API permits at most 10,000 presented objects and 100,000 records; it does not consume an unbounded stream.

## Time and repeated observations

The caller must supply `as_of_s`, `time_domain` and `max_age_s`. Replay reads no live clock. Caller and document domains must match exactly; there is no implicit conversion between Unix time, monotonic time, simulation time or different devices. Both `as_of_s` and the maximum age must be finite and nonnegative seconds.

An observation is current only when `timestamp_s <= as_of_s` and `as_of_s - timestamp_s <= max_age_s`. The age boundary is inclusive. Future timestamps are rejected, without clamping or offset correction. Stale rows are retained with `stale_observation`; future rows retain `future_timestamp`. A downstream tool must provide evidence for any clock synchronization or timestamp correction.

Acquisition timestamps are nondecreasing. Equal timestamps retain sequence order. **The latest sequence for each object determines its current disposition, including rejection.** A newest observation with unknown uncertainty or a future timestamp does not fall back to an older accepted position. All earlier records remain in the report. This policy avoids hiding bad current data behind a previous acceptable sample.

Unknown position covariance is rejected by default as `unknown_position_uncertainty`. An explicit `require_uncertainty=False` allows an analysis to retain that observation with covariance `null`. The report records this policy, and physical accuracy remains unqualified. Unknown noise is never silently converted to zero.

## Frames and covariance

`arm_base` is the existing logical sorter frame. Other frame names must be present in an explicitly supplied [`FrameGraph`](../src/raftel_arm01/kinematics/thor_frames.py). Requesting an unknown frame is an input error. Omitting `target_frame` preserves the source frame; it does not request calibration or conversion.

When conversion is requested, replay uses `FrameGraph.transform(target, source)` and the established `target_from_source` direction. Unknown/disconnected transforms produce `missing_or_unknown_transform` rejections for affected observations. The source coordinates and source frame remain in those rows; the requested frame is not assigned to an unconverted point. In particular, the source `base_link`, native CAD, camera and logical `arm_base` frames do not become aliases. The current revisioned frame manifest still contains unknown camera/bench/mount calibration edges.

For a supplied known transform, the point is transformed by `R*p+t`, and its position covariance by **`R*Σ*Rᵀ`**. Translation does not change position observation noise. The existing 6×6 covariance validator is reused only to validate a zero-extended positive-semidefinite matrix; the SE(3) pose adjoint is not used to transform point noise.

The propagated covariance includes only the supplied observation position noise. Extrinsic, clock, model and calibration uncertainty are excluded and explicitly reported as such. A source/assumed/synthetic/physical transform declaration carries coordinates without qualifying actual calibration accuracy. Frame records are bound into the result by a canonical content hash; replay does not authenticate their evidence.

## API and logical task values

```python
from raftel_arm01.perception.replay import (
    read_observation_document,
    replay_observations,
)

document = read_observation_document("tests/fixtures/observation-replay-v1.json")
replay = replay_observations(
    document,
    as_of_s=10.0,
    time_domain="simulation:observation-fixture-v1",
    max_age_s=1.0,
)
report = replay.to_dict()
objects = replay.objects()
```

`ObservationReplay.decisions` contains every record and its reasons. `current_decisions` returns each detected object's latest record in predeclared presented-object order, including rejected rows. `objects()` reuses existing `ObjectPose`/`Position` values for current accepted observations **only in `arm_base`**. Calling it on an accepted raw camera or source-model observation raises an error instead of silently discarding frame information. It does not screen task categories, payload limits, reachability, IK or collision; those remain the appropriate planning/model layers.

For the committed fixture at 10 seconds with a 1-second maximum age:

| Count | Expected value |
| --- | --- |
| Presented objects | 4 |
| Unique supplied detection IDs | 3 |
| Current accepted objects | 1 (`object-a`, latest record) |
| Current rejected objects | 2 (`object-b` uncertainty unknown, `object-d` timestamp future) |
| Never observed objects | 1 (`object-c`) |
| Observation records | 4, including the earlier stale `object-a` record |
| Rejected records | 3 |

The report preserves presented and supplied-detected denominators separately from current acceptance. Acceptance means the explicit offline data policy passed. It is not task eligibility, an attempted pick or a correctly sorted object. Future E1 integration must use independent task/outcome observations rather than generating success from an accepted perception row. No eligibility, attempt or correctness metric is manufactured by this module.

## Verification and remaining gates

```powershell
python -m pytest tests/test_observation_replay.py
ruff check src/raftel_arm01/perception/replay.py tests/test_observation_replay.py
ruff format --check src/raftel_arm01/perception/replay.py tests/test_observation_replay.py
```

Tests cover hand-counted denominators and misses, deterministic replay, repeated/newest-bad observations, equal timestamp ordering, exact age boundaries, unknown-uncertainty policy, direct point/full-correlated-covariance rotation, translation invariance, missing extrinsics, raw-frame rejection, the existing unknown `base_link`→`arm_base` relation, source provenance and malformed/bounded input cases. Tests and the fixture use synthetic values; they do not claim camera or physical validation.

Before using recorded observations for physical decisions, establish actual source identity/clock synchronization, camera intrinsics/extrinsics and their uncertainty, tracking/detection error and task eligibility. Validate those against held-out measured points and observations. This replay implementation grants no camera access, hardware control or physical operating permission.
