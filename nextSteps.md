# RAFTEL — Engineering Next Steps

**Project:** ARM-01 BenchSort
**Current phase:** Phase 1 — Engineering foundation
**Last updated:** 2026-11-11 18:04:03 UTC
**Overall status:** In Progress

## Current Objective
Complete the CAD-derived geometry and conditional mass/load study using the compatible Thor assembly. The dedicated snapshot now restores/recalculates successfully; preserve the original parametric source and clearly separate its remaining history migration from the usable analysis baseline. Liam approved eight total actuators for this study; the six-arm-axis and parallel-gripper requirements remain. The logical sorting foundation is implemented and tested.

## Next 3 Actions for Liam
1. Measure bench width/depth, desk thickness/material, rear clamp clearance and camera mounting clearance; provide measurements before mount design.
2. Confirm available printer build volume/materials, tools, camera, power supplies and reusable parts; no purchases are approved.
3. Review [Thor cost study](arm-01/hardware/thor-cost-study.md): current partial listings total $244.50; missing-cost sensitivity suggests ~$560–1,055, not a complete quote. Review the budget gap before any purchase decision.

## Next 3 Actions for Codex
1. **Native CAD baseline audit:** produce import/recompute diagnostics and dependency/shape inventory from a separate working copy. Why: cached ZIP/XML data cannot establish usable CAD. Dependency: resolve trusted addon/proxy compatibility and failing thickness features with a compatible CAD environment; runtime and linked files now available. Done: exact runtime/source versions, errors, valid/null geometry and unresolved dependencies recorded without changing upstream files.
2. **Thor-specific model:** extract six joint axes/transforms, link masses/COM assumptions, paired-drive loads and task workspace; produce a traced model and load report. Why: the existing lightweight-servo calculations do not size Thor. Dependency: usable native assembly and material/part assumptions. Done: independently checked transforms, limiting poses, torque-speed assumptions and reachable task/floor subsets; no simulated result labeled physical.
3. **Complete Thor BOM and tooling decision:** reconcile exact motor/controller/driver fits, parallel-jaw mechanism, mount/protection, tax/shipping and licensing. Why: the partial subtotal cannot prove budget feasibility. Dependencies: CAD interfaces and Liam's equipment inventory. Done: complete priced candidate list with remaining uncertainty/status, no orders.

## In Progress
- Published branch `codex/arm01-engineering-bootstrap`; [PR #1](https://github.com/LiamHoweth/RAFTEL/pull/1) open, not merged. Latest implementation checkpoint `eb2171a` is pushed and CI passes; session handoff is saved with this follow-up.
- Official portable FreeCAD 1.1.4 runtime is operational under the workspace tools directory; no system-wide installation or global security-setting changes. Whole-assembly compatibility remains open.
- Active continuation: five agents investigate addon trust, failed features, incremental audit tooling, CAD/ROS geometry, and traceable load analysis. Root coordinates full native runs, integration, validation and publication.

## Completed and Verified
- Whole compatible assembly:53 referenced documents,2,129 recomputed features,all3,001 objects Up-to-date; no audit/native feature errors. Uses pinned addons and exact static Art1 geometry/datum snapshot, not a rebuilt original Art1 history. See `arm-01/docs/thor-assembly-compatibility.md`.
- Native bearing/shaft evidence corroborates all six zero-pose joint-axis lines and the CAD-to-ROS quarter-turn frame convention; actuator signs/limits remain uncalibrated. Geometry/load report integration is ongoing.
- Continuation milestone: native addon trust resolved via standard `-M` registration, with pinned Fasteners and version-matched Gears0.0.3. Original involute and bevel gear parts forcibly recomputed successfully; no global trust changes or source saves. See `arm-01/docs/thor-dependency-compatibility.md`.
- Incremental native audit/outer timeout runner now preserve checkpoints, feature state, proxy/placement evidence and logs; restore, changed and forced modes are separate. Focused guard/runner tests pass.
- Pure Thor joint/channel conversion utility and 21 tests: paired shoulder validation, differential wrist modes, seeded algebraic round trips, finite input/overflow handling; no hardware commands. See `arm-01/docs/thor-joint-map.md`.
- Thor-specific motor/controller/driver listing study with reproducible subtotal; compatibility, missing components and total cost remain unverified. See `arm-01/hardware/thor-cost-study.md`.
- Five specialist agents contributed CAD research, mechanics/mobile analysis, hardware/safety, research/ADR and foundation documentation.
- Thor pinned native source acquired in a separate reference checkout; 57 FreeCAD files passed ZIP/XML parsing; all file hashes/versions/dependencies reproduced against committed inventory. Found 33 unique filename-case mismatches; Linux reference portability needs resolution. Portable FreeCAD now runs. BaseTop imported and forcibly recomputed to one valid solid; whole assembly timed out after180seconds and logged FastenersCmd permission and thickness-feature errors. See `arm-01/docs/thor-native-validation.md`.
- Repository audit: only initial README; default branch main; clean starting tree.
- Root AGENTS.md establishes mandatory read/update policy.
- Installed Python mock sorting CLI, seeded object poses, bin configuration, bounded retries, event logs and fault latching; initial test suite passes.
- Reproducible full downstream static-torque and floor outer-bound analysis implemented (analytical estimates only).

## Blockers and Open Decisions
- Original Art1 editable history still needs legacy thickness/sketch migration. The separate static shape/datum snapshot is validated and the complete compatibility assembly recalculates; this is not a procedural repair of the original. Mass/COM assumptions, wrist downstream membership and physical calibration remain distinct open gates.
- Thor is the first CAD study baseline; Liam explicitly permits eight total actuators. Measured geometry/masses, Thor-specific BOM, sustainable actuator output, parallel-gripper fit, license provenance, and physical equipment inventory remain open.

## Hardware and Purchasing Status
No hardware approved, purchased, received, or tested in this session.

## Validation Results
94 tests passed locally on macOS/Python 3.14.4. Ruff lint and formatting, compile check, installed editable CLI and separate non-editable wheel smoke passed. Normal demo sorted 10 synthetic objects; unreachable scenario skipped one; injected grasp failure returned exit 1; invalid count returned exit 2. Analysis script ran. Local Markdown links resolve and JSON files parse. GitHub Actions passed on Linux/Python 3.11–3.14 at `eb2171a`: package install, 94 tests, Ruff lint/format, compile, mock demo and engineering analysis. [Passing run](https://github.com/LiamHoweth/RAFTEL/actions/runs/43065277693). Initial inspector import-order failure was fixed. Native BaseTop import/recompute passed, but whole-assembly import/recompute did not complete. No hardware, spatial FK/IK or physics validation.

## Roadmap
- [ ] Phase 1 — Engineering foundation (CAD-derived model and complete Thor BOM still open)
  - [x] Persistent workflow, requirements, architecture, research and ADR
  - [x] Executable logical sorter, tests and lightweight CI
  - [x] Explicit preliminary load/mobile analytical examples
  - [x] Pinned existing CAD source inventory and nominal drive-coordinate study
  - [ ] Native CAD recompute, joint-constrained model and Thor-specific loads
  - [ ] Complete compatible Thor BOM and budget decision
- [ ] Phase 2 — Mechanical prototype
- [ ] Phase 3 — Hardware control
- [ ] Phase 4 — Manipulation
- [ ] Phase 5 — Vision-guided sorting
- [ ] Phase 6 — Learning/generalization
- [ ] Phase 7 — Reliability/mobile readiness

## Recent Engineering Log
- 2026-11-11: Compatible whole-assembly changed recomputation completed:53documents,3,001 Up-to-date objects. Validated static Art1 geometry/datums, originalsource preserved; added Linux case-alias helper and documented operational CAD recipe. All current working-tree tests pass; geometry/mass/load integration continues.
- 2026-11-11: Verified original gear parts with version-matched addon, implemented checkpointed cached/changed/forced audit and bounded outer runner, and identified Art1Body legacy rebuild failures separately from valid cached geometry. Publishing this tested tooling/dependency checkpoint while geometry/load work continues.
- 2026-11-11: Resumed on Liam’s instruction with five agents; clean starting tree, preserved source baseline and55GiB free. Investigating native addon registration, exact thickness features and safer restore/recompute modes before extracting geometry/load results.
- 2026-11-11: All four Linux Python CI jobs passed for eb2171a (94 tests). Saved final native diagnostics, preserved source checkouts and active tools, removed superseded installer and scratch helpers; free-space reserve remains above50GiB.
- 2026-11-11: Verified official FreeCAD1.1.4 download checksum/signature; portable console works. Whole-assembly native attempt timed out with actionable diagnostics; original BaseTop imported/forced-recomputed with one valid solid. No source saved. Added native-audit guard tests (94 total) and retained reports.
- 2026-11-11: Added verified-source Thor motor coupling algebra and 21 tests (91 total); researched actual linked motor prices and incomplete total. CI at5ac3b6d passed all four Python versions. Continuing native CAD runtime/import study.
- 2026-11-11: Published requested checkpoint and opened PR #1; added read-only Thor inspector with five tests (70 total). Corrected inspector import formatting discovered by remote CI; all local static checks now pass.
- 2026-11-11: Liam approved eight total actuators and Thor-first CAD study. Requirements, ADR, BOM and safety documentation updated; no fabrication or purchase approval inferred.
- 2026-11-11: Implemented logical sorting package and CI; 65 local tests and wheel/CLI/static checks pass. Continuing CAD source audit after requested publication checkpoint.
- 2026-11-11: Audited original README and created feature branch codex/arm01-engineering-bootstrap. Established persistent operating workflow; implementation in progress.
