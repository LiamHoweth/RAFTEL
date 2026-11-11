# RAFTEL agent operating instructions

RAFTEL develops affordable, modular, repairable household robots. Prioritize useful manipulation, measurable evidence, manufacturability, and reusable interfaces. ARM-01 BenchSort is a stationary, removable bench arm: **six independent arm joints plus one gripper actuator; Liam permits eight total actuators for the Thor-first CAD study (seven arm motors including the coupled shoulder, plus gripper)**. Reuse Thor’s pinned existing CAD first; do not start a clean-sheet arm. Physical fabrication and purchasing remain gated. A mobile base is out of scope; preserve mechanical, electrical, communication, and coordinate-frame interfaces for it.

## Every session
1. Read this file, `nextSteps.md`, and `AGENT_NOTES.md` if present.
2. Inspect relevant architecture/product documentation, working-tree status, recent commits, and existing implementations. Preserve user changes and reuse existing architecture.
3. Resume the highest-priority actionable task. Distinguish implemented, tested, blocked, and proposed work.
4. Update `nextSteps.md` after meaningful tasks, test runs, blockers, or decisions. Before stopping, make its next actions, validation evidence, and branch/publication status accurate. It does not update while agents are inactive.

## Structure and conventions
- Company scope: `docs/`; project: `arm-01/`; Python package: `arm-01/src/raftel_arm01/`; tests: `arm-01/tests/`; configuration: `arm-01/config/`.
- Python 3.11+, SI units, explicit coordinate frames, typed small models and protocols. Keep control, modeling, perception, planning, task execution, and evaluation separate. Do not duplicate services or introduce unused frameworks.
- Mock simulation must remain runnable without hardware, ROS, internet, or camera access after installation. Optional integrations need independent setup and validation.
- Validate external input, finite numbers, bounds, payload, IDs, and failure paths. Do not bypass safety on exceptions. Use structured event records with honest outcomes.
- Add only meaningful directories; do not fabricate CAD, URDF, integrations, or datasets.

## Verification and documentation
Run from `arm-01`: `python -m pip install -r requirements-dev.lock -e '.[dev]'`, `python -m pytest`, `ruff check .`, `ruff format --check .`, `python -m compileall -q src`, `raftel-sort --seed 42`, and `python tools/engineering_analysis.py`. Exercise installed CLI and negative cases. Fix introduced failures. Record exact results and unavailable checks in `nextSteps.md`.
Use primary upstream research, record access dates and immutable revisions, validate exact servo variants and electrical bus types. Label supplier claims, estimates, analytical models, logical simulations, kinematic simulations, physics simulations, and physical tests separately. A reach sphere is not IK or collision checking; stall torque is not continuous torque. Document assumptions and revisit criteria in ADRs. Never infer hardware success from mock results.

## Physical safety
No real hardware backend or motion by default. Future backends require explicit arming, calibrated validated joint/velocity/current limits, feedback freshness, fault latching, supervised commissioning, and safe recovery. Hardware emergency stop must independently interrupt motor energy; assess gravity collapse and provide mechanical restraint/guarding. No energizing unverified assemblies. No purchases or financial commitments. Liam approves purchasing and performs physical assembly/measurement/inspection. Bench prototypes are not household-safe products.

## Git and handoff
Use `codex/` feature branches and reviewable logical commits. Keep `nextSteps.md` with related work; avoid timestamp-only commits. Never force-push, delete existing work, or merge without authorization. Push the working branch and open a PR when authorized; verify publication and report failures. Do not commit secrets, virtual environments, generated caches, large logs, or datasets. Do not select a company-wide license without Liam's decision; preserve all upstream license/NOTICE obligations before importing assets. Update concise `AGENT_NOTES.md` only for durable new implementation knowledge.
