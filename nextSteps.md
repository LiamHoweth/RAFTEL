# RAFTEL — Engineering Next Steps

**Project:** ARM-01 BenchSort
**Current phase:** Phase 1 — CAD-derived engineering foundation and design gates
**Last updated:** 2026-11-11 18:43:58 UTC
**Overall status:** In Progress

## Current Objective
Resolve the wrist moving-body model and elbow transmission/load relationship using the merged Thor geometry and conditional mass baseline. Preserve uncertainty where belt pitch, motion signs or physical properties cannot be established from sources. The analysis baseline is usable: it preserves upstream geometry with one explicit static Art1 compatibility snapshot. It does not establish a safe physical arm, an actuator payload rating, or repaired original Art1 feature history.

## Next 3 Actions for Liam
1. Measure bench dimensions, desk thickness/material, rear clamp clearance and camera mounting clearance. These determine the removable mount and reachable workstation layout.
2. Printer identified: **Anycubic Kobra 3 Max**, nominal **420 × 420 × 500 mm** build volume. Provide actual nozzle/slicer profile and PLA/PETG/ABS brands; see [fabrication record](arm-01/hardware/fabrication.md). All three material families are confirmed available; actual densities, sliced part masses, dimensional fit and printed strength remain unverified.
3. Review [load assumptions](arm-01/docs/thor-load-analysis.md), [material comparison](arm-01/hardware/cad/thor-material-comparison.json) and [incomplete Thor cost study](arm-01/hardware/thor-cost-study.md) before any purchase or fabrication decision. No orders or powered tests are approved by these calculations.

## Next 3 Actions for Codex
1. **Close wrist articulation and complete moving masses.** The exact source membership and conditional COM model are complete. Next establish bevel handedness with native mesh/contact or a checked articulation probe; reconcile opposed controller coordinates, decompose relevant motor/belt internals, and model jaw motion. Why: conditional component contributions do not establish complete wrist holding loads. Done: independently verified motion relations, nonzero-pose potential checks, conserved mass and explicit remaining omissions.
2. **Reconcile elbow controller compensation and actuator feasibility.** The source-backed conditional carrier Jacobian and reaction/load tool are complete. Next resolve the actual drum pitch line, routing/clamps and source-controller compensation, then obtain speed/duty/thermal capacity evidence for selected drives. Why: gravity demand and conditional rotor effort are not actuator ratings. Done: measured or source-verified signs/radius, explicit load sharing/losses and appropriate capacity evidence; no motion enabled.
3. **Prepare fabrication interfaces and source-editability gate.** Produce the mount/gripper interface proposal, sliced mass/fit plan and bounded Art1 history migration plan. Why: the snapshot supports analysis but loses original Art1 procedural edits, and native jaw motion has not proven the parallel-gripper requirement. Dependencies: Liam's measurements/profiles for fabrication; original source and geometry are available for continued software/CAD investigation. Done: dimensioned proposals and acceptance tests with no unsupported release/purchase claims.

## In Progress
- Six-agent wrist/elbow checkpoint on `codex/thor-wrist-elbow-loads` is complete and locally verified. Push, PR and CI verification precede the authorized merge; publication is pending at this checkpoint.
- Engineering implementation is merged into `main` through [PR #1](https://github.com/LiamHoweth/RAFTEL/pull/1), merge commit `024fe244d36ecabff296f69554fc43dc1821d957`. Implementation head `ac17570` passed all four CI jobs before the authorized merge; no implementation changes remain unmerged. This handoff records the verified publication state.
- Earlier geometry/native-compatibility work remains merged. This continuation adds separate evidence/reports; original source CAD, baseline load snapshot, full baseline study and material report are unchanged.

## Completed and Verified
- [Wrist membership](arm-01/docs/thor-wrist-mechanism.md): exact516-leaf ledger;66 Art56 leaves split into carrier, roll/tool, own-axis side rotors and bearing COM approximations. [Wrist math](arm-01/docs/thor-wrist-model.md) uses explicit carried axes and analytic COM Jacobians. [Separate study](arm-01/hardware/cad/thor-wrist-load-study.json) evaluates3 reference materials ×2 handedness alternatives ×4 poses ×3 payloads, retaining null full wrist holding totals.
- [Elbow evidence](arm-01/docs/thor-elbow-mechanism.md) and [load tool/report](arm-01/docs/thor-elbow-loads.md): conditional carrier relation, virtual-work transpose, shoulder reaction and belt tension difference. In the explicit37mm pitch scenario with baseline200g horizontal load, ideal elbow rotor magnitude0.077803N·m and belt difference63.306N; neither qualifies physical capacity or pretension.
- Persistent `AGENTS.md`/`nextSteps.md` workflow, Python logical sorter, tests, CI, requirements, safety and workstation documentation.
- Pinned Fasteners plus saved-schema-compatible Gears0.0.3 restore normally through FreeCAD `-M`; no blanket trust or global security changes.
- Separate static Art1 snapshot preserves exact published final solid and24 datum frames, passes save/reopen/forced-recompute checks, and leaves original source unchanged. Original feature history is preserved separately, not repaired.
- Compatible whole assembly:53 referenced documents,2,129 recalculated features,all3,001 objects Up-to-date with no invalid/pending states. [Report](arm-01/hardware/cad/thor-compatible-assembly-validation.json).
- Native bearing/shaft geometry corroborates all six unsigned zero-pose joint-axis lines and CAD→ROS rotation Rz(-π/2). Commands, physical zeros and travel limits remain uncalibrated.
- [Geometry inventory](arm-01/hardware/cad/thor-mounted-geometry.json):516 retained installed solid instances, with14 hidden procedural inputs excluded; all retained source shapes passed selected topology checks. This is distinct from topology validation of every history feature.
- Nominal source FK and traceable mass/statics tools. All516 leaves are assigned exactly once by515 mass records; seven motors total2.120kg once, with a separate servo and horn. Independent ledger/COM/gravity sums match.
- [Conditional load study](arm-01/hardware/cad/thor-load-study.json) and [mass ledger](arm-01/config/thor-load-snapshot.json) reproduce exactly from saved geometry. Illustrative50% whole-part PLA case:5.650kg including base; 200g horizontal-shoulder case requires ideal joint holding magnitudes5.828N·m shoulder and2.342N·m elbow.
- PLA/PETG/ABS reference-density comparison and provenance-bearing density overrides. Same50% fraction gives modeled masses5.650/5.702/5.301kg respectively; reference products/editions do not identify Liam's actual filament or select a structural material.

## Blockers and Open Decisions
- Original Art1 procedural history still has thickness/external-sketch migration issues; use the validated static analysis snapshot while preserving that original.
- Wrist source membership now covers all516 leaves:450 upstream,7 fold carrier,47 roll/tool,10 side rotors and2 bearing COM approximations. Differential handedness, motor internals and jaw motion remain conditional; exact full q5/q6 holding values stay null while component contributions are being integrated.
- Elbow source evidence supports a conditional moving-carrier model, including reaction at the shoulder. Smooth-drum effective pitch radius, physical routing signs, controller compensation, motor torque-speed/thermal behavior, shoulder load sharing and dynamic loads remain unqualified.
- Actual material/profile, printed mass/COM/stiffness/creep, fastener/fit tolerances, positive commands, joint stops, collision clearance, parallel-jaw behavior, mount and independent stop/gravity restraint require further evidence.
- Native CAD, analytical poses and logical sorting are not physical robot performance or a demonstrated90% sorting rate.

## Hardware and Purchasing Status
No hardware was purchased, assembled, energized or physically tested. Liam confirmed PLA, PETG and ABS print availability. The candidate BOM and supplier prices remain research; the complete delivered Thor build cost and structural material selection are open. Printer ownership/model is confirmed by Liam as Kobra 3 Max; published nominal volume is recorded. Actual printer/nozzle/material profiles and remaining computer/tool/camera inventory still need detail.

## Validation Results
- 270 tests pass locally on macOS/Python3.14.4; Ruff lint/format, Python compilation and whitespace checks pass. Installed mock CLI sorts10 synthetic objects. Generic engineering and new wrist/elbow CLI smoke checks pass; both new reports reproduce exactly. Original PLA study reproduction test remains passing.
- Mock installed CLI sorts10 synthetic objects; failures/skips remain explicit. Separate installed-wheel checks validate packaged defaults and Python modules.
- Saved load snapshot, full load study and material comparison reproduce exactly. JSON parses and local documentation targets resolve.
- Native FreeCAD1.1.4: compatible assembly changed-recompute complete;53docs/3,001 Up-to-date objects. Selected topology run validates all516 retained mounted source shapes. Source checkout remains clean.
- Independent current review: all516 IDs/515 records conserved, motor mass2.120kg;300 random wrist transform/Jacobian chains,1,000 random elbow inverse/virtual-work models, and96 integrated potential-gradient comparisons across both handedness alternatives pass (maximum integrated discrepancy1.996e-9N·m). These verify declared math, not physical motion.
- Earlier failed attempts and cached-state results remain historical evidence. A valid cached shape, zero process exit or restored assembly alone is not feature-rebuild proof.
- GitHub Actions passed the final integrated implementation `ac17570` on Linux/Python3.11–3.14:222 tests, installation, Ruff/format, compilation, sorting and load/material CLI checks. [Passing run](https://github.com/LiamHoweth/RAFTEL/actions/runs/43076558249). Native FreeCAD was exercised locally, not in CI.

## Roadmap
- [ ] Phase 1 — Engineering foundation: core software/research verified; remaining design gates explicit
  - [x] Persistent workflow, requirements, architecture, research, mock sorter and CI
  - [x] Reproducible native compatibility baseline and six-axis geometry evidence
  - [x] Traceable conditional mass/load/material studies
  - [ ] Complete wrist/transmission/actuator feasibility, compatible final BOM and fabrication gate
- [ ] Phase 2 — Mechanical prototype: finalize CAD/mount/limits, print, inspect and assemble
- [ ] Phase 3 — Explicitly armed hardware control, calibration, feedback and fault tests
- [ ] Phase 4 — Validated IK/trajectories/gripper and supervised fixed-location manipulation
- [ ] Phase 5 — Calibrated vision-guided variable-position sorting and independent verification
- [ ] Phase 6 — Recorded demonstrations, learning/generalization and held-out evaluation
- [ ] Phase 7 — Reliability benchmarks, detachable mount and mobile readiness

## Recent Engineering Log
- 2026-11-11: Six current lanes completed and froze the wrist/elbow checkpoint. All270 local tests and lint/format/compile/CLI checks pass; reports reproduce exactly. Added CI smoke checks and durable model contracts. Ready to push and merge after matching-head CI succeeds.
- 2026-11-11: Exact wrist ledger passes independent516-leaf/515-record conservation review. Wrist chain math passes an independent300-case transform/Jacobian check; elbow virtual-work/inverse math passes1,000 random cases. Native belt evidence establishes a conditional shoulder-carrier term, with schematic idler mismatches and physical pitch radius/signs retained as open gates. Integration and final suite/CI are in progress.
- 2026-11-11: Resumed wrist/elbow continuation with six agents after clean-main audit. Existing native runtime/source copies are available;53GiB free. No hardware motion or source-CAD changes authorized by analysis.
- 2026-11-11: Liam identified a Kobra 3 Max. Recorded published build volume and remaining profile/filament questions; refreshed today’s daily reading around Thor load paths, material assumptions and this printer. No printer operation or configuration change.
- 2026-11-11: Final implementation CI passed all four Python versions; independently verified the complete ledger/moments and reproduced reports. Merged PR #1 into main as024fe244. Original source/native working copies and useful runtime retained; temporary wheel builds removed, free-space reserve remains above50GiB.
- 2026-11-11: Liam confirmed PLA/PETG/ABS and authorized merging after a good verification checkpoint. Added reference-density comparisons and explicit override provenance; no structural material approval inferred.
- 2026-11-11: Extracted native axis lines and516 installed solids; corrected the90° frame mismatch and duplicate/helper geometry, then independently reviewed the mass ledger and gravity moments. Working-tree suite reaches222 tests.
- 2026-11-11: Published dependency checkpoint6c575ac and compatible-assembly checkpoint0869466. Whole assembly changed recomputation completed; original Art1 history remains separate from exact static geometry/datum snapshot.
- 2026-11-11: Initial bootstrap delivered logical sorting software and persistent engineering workflow; no physical success claimed.
