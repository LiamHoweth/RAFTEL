# ARM-01 seven-hour desktop implementation prompt

Copy the text below into the Codex session running on the desktop. This document is a handoff, not an active background run. Read the live `main` version of `nextSteps.md` before executing it.

```text
Continue implementation of ARM-01 BenchSort in the private GitHub repository https://github.com/LiamHoweth/RAFTEL.

Work autonomously for approximately the next SEVEN HOURS of wall-clock time. Implement and validate useful changes; do not stop at a plan or after the first checkpoint. Use at least FIVE specialist agents plus coordinated integration/review, with exclusive file ownership. The seven-hour plan and detailed task backlog are in nextSteps.md under “Next Steps for Codex.” This is a work budget, not a requirement to fabricate completion of every task.

Start by finding the existing checkout whose origin is LiamHoweth/RAFTEL. Read AGENTS.md, AGENT_NOTES.md, nextSteps.md, the relevant architecture/requirements and existing implementation. Inspect local changes before fetching current main; preserve user work and do not reset, force-push or replace a dirty checkout. Use a codex/ feature branch. If no checkout exists, create a scoped working checkout and inspect it first.

Current verified implementation baseline: PR #6 is merged. The suite has 325 tests; the corrected source inventory has 518 installed CAD leaves and 517 mass records. Intended ideal wrist handedness is s=+1, but native gears have interference/noncoincident pitch apices. Two previously omitted wrist belts are now included; four input pulley/screw COM trajectories are corrected. The pinned ROS/GRBL pipeline has no elbow carrier compensation; pure offline transmission math represents it. An ideal jaw model exists, while saved native loops have small residuals. Art1's Intersection workaround loses a bolt cut; its original history is not repaired. Full physical load/capacity/calibration claims remain open.

Execute the seven-hour lane plan in nextSteps.md. Priorities are:
1. Art1 first-drift/disappearing-cut diagnostics and justified semantic repairs in copied CAD only.
2. Wrist/jaw contact and pivot/moving-body reconciliation, keeping ideal and saved configurations separate.
3. Revisioned frames/provisional constraints and a tested nominal Jacobian, then bounded IK if prerequisites and time allow.
4. Scenario/provenance consolidation, jaw-dependent COM/load modeling and independent mass/potential checks.
5. Exact controller conversion fixtures, in-memory protocol replay and calibration evidence records, without any hardware backend.
6. Source-linked interface drawings, printable-asset/export validation, fit-coupon drafts and measurement-ready mass/fit tooling.
7. Independent review, evaluation fixtures, CI/reproduction and integration.

Reuse existing modules and reports. Coordinate shared schemas before producing dependent artifacts. Follow the task IDs, dependencies, completion checks and fallback items in nextSteps.md. If an investigation yields no new evidence for 45–60 minutes, record the hypotheses/results and move to another ready task. Missing bench measurements or print profiles should not idle unrelated software/CAD work. Keep unsupported parameters unknown or clearly conditional.

Native source copies and portable FreeCAD are not guaranteed to be tracked in Git. Discover and reuse local pinned sources/runtime/addons where available; verify hashes. Use isolated preferences, fresh evidence paths and copied documents; one whole-assembly run at a time. Preserve upstream originals and historical reports. Maintain at least 50 GiB free on the build volume; if native tooling cannot fit or is unavailable, proceed with pure-Python, source-audit, report and drawing lanes rather than spending the run installing a whole robotics stack.

Update nextSteps.md after meaningful milestones, tests, blockers and decisions. Push logical tested progress about every 45–60 minutes when a real checkpoint is ready. Use focused tests while developing, then relevant full tests, Ruff lint/format, compilation, installed CLI/report reproduction and exact-head GitHub CI before merging. You are authorized to push, open PRs and merge at verified good checkpoints. Inspect the diff yourself and preserve meaningful independent evidence. Reserve the final hour for integration, fixes, CI and handoff.

No serial ports, real hardware backend, arming/real-motion flag, firmware flashing, energizing, purchases, vendor messages, physical fabrication or manufacturing release. Prepare models, copied CAD revisions, diagrams, measurement forms, simulated tests and reviewable proposals only. Do not substitute holding torque for running capacity, conditional geometry for physical calibration, or mock success for physical performance. Do not change company-wide licensing. Preserve existing architecture and optional-integration boundaries.

Finish with actual elapsed work, implemented versus investigated results, agent ownership, tests and native evidence modes, merged PR/commit/CI links, clean/synchronized repository status or the precise remaining publication blocker, unresolved gates and the next three executable actions. If session/tool availability ends early, leave a resumable handoff and report actual time honestly. Do not create reminders or claim work will continue after the session ends.
```
