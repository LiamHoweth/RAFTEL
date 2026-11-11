# RAFTEL — Engineering Next Steps

**Project:** ARM-01 BenchSort  
**Current phase:** Phase 1 — Engineering foundation  
**Last updated:** 2026-11-11 16:42 UTC  
**Overall status:** In Progress

## Current Objective
Establish a research-backed engineering foundation and executable logical sorting prototype without physical hardware. Audit: main contains only README.md at 48c19d6; no existing code, agent instructions, or notes.

## Next 3 Actions for Liam
1. Measure the available bench, rear clamp clearance, desk thickness/material, and camera mounting location.
2. Review Thor source-CAD study and provide bench/printer constraints before physical design or purchasing approval.
3. Confirm printer/tool access and available reusable hardware; nothing is approved for purchase.

## Next 3 Actions for Codex
1. Import the pinned Thor assembly and extract geometry/masses; dependency: FreeCAD availability and complete linked files; done when recompute errors, joint map, dimensions and material assumptions are recorded.
2. Produce executable mock sorting software and tests; dependency: architecture; done when installed CLI, deterministic and failure tests pass.
3. Produce torque/mobile analyses and candidate BOM; dependency: stated mass/geometry assumptions; done when calculations reproduce and no physical claims are inferred.

## In Progress
- Publication checkpoint requested by Liam: committing and pushing current foundation on `codex/arm01-engineering-bootstrap`; not merged into main. Work continues with Thor source audit and CAD tooling after this checkpoint.
- Integrating five agent contributions: CAD reuse, mechanics/mobile analysis, hardware/safety, research/ADR, foundation documentation.
- Python logical sorting implemented; final review, packaging and CI verification in progress.

## Completed and Verified
- Five specialist agents contributed CAD research, mechanics/mobile analysis, hardware/safety, research/ADR and foundation documentation.
- Thor pinned native source acquired in a separate reference checkout; 57 FreeCAD files passed ZIP/XML parsing. No FreeCAD installation found; application import and recompute remain blocked.
- Repository audit: only initial README; default branch main; clean starting tree.
- Root AGENTS.md establishes mandatory read/update policy.
- Installed Python mock sorting CLI, seeded object poses, bin configuration, bounded retries, event logs and fault latching; initial test suite passes.
- Reproducible full downstream static-torque and floor outer-bound analysis implemented (analytical estimates only).

## Blockers and Open Decisions
- Thor is the first CAD study baseline; Liam explicitly permits eight total actuators. Measured geometry/masses, Thor-specific BOM, sustainable actuator output, parallel-gripper fit, license provenance, and physical equipment inventory remain open.

## Hardware and Purchasing Status
No hardware approved, purchased, received, or tested in this session.

## Validation Results
65 tests passed locally on macOS/Python 3.14.4. Ruff lint and formatting, compile check, installed editable CLI and separate non-editable wheel smoke passed. Normal demo sorted 10 synthetic objects; unreachable scenario skipped one; injected grasp failure returned exit 1; invalid count returned exit 2. Analysis script ran. Local Markdown links resolve and JSON files parse. Remote CI not yet run. No CAD application import/recompute, hardware, IK or physics validation.

## Roadmap
- [ ] Phase 1 — Engineering foundation
- [ ] Phase 2 — Mechanical prototype
- [ ] Phase 3 — Hardware control
- [ ] Phase 4 — Manipulation
- [ ] Phase 5 — Vision-guided sorting
- [ ] Phase 6 — Learning/generalization
- [ ] Phase 7 — Reliability/mobile readiness

## Recent Engineering Log
- 2026-11-11: Liam approved eight total actuators and Thor-first CAD study. Requirements, ADR, BOM and safety documentation updated; no fabrication or purchase approval inferred.
- 2026-11-11: Implemented logical sorting package and CI; 65 local tests and wheel/CLI/static checks pass. Continuing CAD source audit after requested publication checkpoint.
- 2026-11-11: Audited original README and created feature branch codex/arm01-engineering-bootstrap. Established persistent operating workflow; implementation in progress.
