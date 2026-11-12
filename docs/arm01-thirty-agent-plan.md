# Thirty-agent continuation: the three current next steps

**Stopped for the night at the owner's request, November 11, approximately
21:15 America/Chicago (03:15 UTC November 12).** All thirty lanes are frozen;
no autonomous continuation is scheduled. See the
[checkpoint record](arm01-swarm-checkpoint-2026-11-11.md) for completed diagnostics,
the incomplete slicer step and the next resume actions. The plan below is the
historical assignment contract, not an instruction to keep working tonight.

Liam resumed work on November 11, 2026 at approximately 20:32 America/Chicago
(02:32 UTC November 12), selected **only the three current next steps**, and
confirmed the desktop is ready. This supersedes the prior wrap-up for this new
continuation. Starting main is `c0e7deb`; baseline is 2,200 passing tests.

## Finish line

1. Observe the live Anycubic scene, preserve any existing work, check a small
   model's scale, import the reviewed eight-copy draft, and save a fresh local
   DRAFT project. Verify actual saved geometry/copy counts, observed software
   selectors and warnings. Slicing is optional; no upload or printer action.
2. Prepare and execute a fresh copied Art1 attachment-engine and documented
   parameter-return study. Verify fixture semantics, actual attachment targets,
   dependent frame/feature behavior and nominal-return results. Preserve failed
   migration gates; completing a diagnostic does not repair original history.
3. Execute and verify one copied nonzero wrist-coordinate marker/body-frame
   experiment. Authenticate source/link identities, actual cached-shape refresh,
   declared coordinate mapping and return behavior against independent math.
   Do not promote the result to physical calibration or full-body clearance.

No broader backlog expansion is authorized by this scope choice. Physical
measurements, fabrication approval and other real-world gates remain external.

## Coordination and ownership

Root owns Git/CI, shared documentation, live UI, integration and the serialized
native queue. Thirty specialist agents form three pods of ten. Read-only roles
produce findings to their pod and Root, not filler files. Every writer must
inspect existing implementations before coding and reuse them. Existing pinned
workers/reports are immutable. Only the explicit new paths below may be edited;
request a coordinated ownership change before touching any other path.

All paths in the table are below `arm-01/`. Tests/docs accompany real behavior,
not duplicated implementations. Agents may use their own ignored
`.work/swarm/<role>/` scratch directory. No Git mutations, native process launch,
UI input, serial/device access, firmware action or external messages by agents.
Root alone grants native slots after contract/fixture/preservation review.

| Agent | Responsibility | Exclusive write ownership |
| --- | --- | --- |
| s01_project | Saved Anycubic project structural audit | `tools/audit_anycubic_draft_project.py`, `tests/test_anycubic_draft_project.py`, `docs/thor-anycubic-project-audit.md` |
| s02_mesh | Source-to-saved mesh comparison | `tools/compare_anycubic_draft_meshes.py`, `tests/test_anycubic_draft_meshes.py` |
| s03_profile | Allowlisted process/profile observations | `tools/anycubic_process_observation.py`, `tests/test_anycubic_process_observation.py` |
| s04_source | Independent eight-copy source geometry check | Read-only |
| s05_quantity | Quantity/identity/hash preservation | Read-only |
| s06_profile | Software-profile assumptions and units | Read-only |
| s07_ui | Preserve-scene/UI sequence review | Read-only; no UI control |
| s08_geometry_review | Independent saved-geometry review | Read-only |
| s09_schema_review | Project/profile bounds and failure paths | Read-only |
| s10_acceptance | Pod evidence acceptance | Read-only |
| a01_engine | Actual copied attachment-engine worker | `tools/probe_thor_art1_attachment_engine.py`, `tests/test_art1_attachment_engine.py`, `docs/thor-art1-attachment-engine.md`, `hardware/cad/thor-art1-attachment-engine-v1.json` |
| a02_return | Copied parameter/return trace worker | `tools/probe_thor_art1_return_trace.py`, `tests/test_art1_return_trace.py`, `docs/thor-art1-return-trace.md`, `hardware/cad/thor-art1-return-trace-v1.json` |
| a03_api | Exact pinned native attachment API research | Read-only |
| a04_contract | Launch/isolation/input preservation review | Read-only |
| a05_analysis | Earliest feature/frame return analysis | `tools/thor_art1_return_analysis.py`, `tests/test_art1_return_analysis.py` |
| a06_semantics | Source/current semantic target joins | Read-only |
| a07_fixture_review | Independent attachment fixture oracle | Read-only |
| a08_return_review | Independent actual roundtrip review | Read-only |
| a09_guard_review | Worker guard/cleanup/bounds review | Read-only |
| a10_acceptance | Pod evidence acceptance | Read-only |
| w01_native | Nonzero wrist native marker worker | `tools/probe_thor_wrist_frames_desktop.py`, `tests/test_wrist_frames_desktop.py`, `docs/thor-wrist-native-frames.md`, `hardware/cad/thor-wrist-native-frames-v1.json` |
| w02_contract | Source wrist-coordinate contract | `tools/thor_wrist_pose_contract.py`, `tests/test_wrist_pose_contract.py` |
| w03_markers | Source markers and instance identity | Read-only |
| w04_oracle | Independent actual-frame mathematical tests | `tests/test_thor_wrist_native_frames.py` |
| w05_capture | Host capture identity/refresh validator | `tools/thor_wrist_frame_capture_review.py`, `tests/test_wrist_frame_capture_review.py` |
| w06_units | Units/frame covariance review | Read-only |
| w07_axes | Source axes/signs/hierarchy review | Read-only |
| w08_return | Perturbation/return frame review | Read-only |
| w09_guard | Native isolation/preservation review | Read-only |
| w10_acceptance | Pod evidence acceptance | Read-only |

## Execution and verification

Writers first publish small input/output contracts to their pod; dependent
reviewers inspect sources while awaiting stable implementations. Root supplies
a newly saved Anycubic project to the slicer pod. Native pods prepare fresh
copied inputs, request/worker/helper snapshots, actual five-path isolation and
before/after hash ledgers. Do not launch until Root grants the serialized slot.
Maintain at least 50 GiB reserve. Close only owned documents and preserve all
original CAD, historical reports, user projects and configured power policy.

Use explicit UTF-8/LF. Fix meaningful failures; never weaken gates to obtain a
green report. If an experiment stalls, narrow it within the same three-step
scope and retain its failures. Do not start unrelated backlog work.

Each step needs actual execution evidence, independent review, relevant tests
and preservation checks. Integration runs the relevant full suite, Ruff,
compilation, text/provenance checks and exact-head Linux/Windows CI before an
authorized merge. Root keeps `nextSteps.md` current and publishes meaningful
tested milestones. Continue through all three deliverables, then provide actual
elapsed time, implementation/results, tests, PRs and remaining external gates.
