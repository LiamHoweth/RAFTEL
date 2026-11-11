# RAFTEL — Engineering Next Steps

**Project:** ARM-01 BenchSort
**Current phase:** Phase 1 — CAD-derived engineering foundation and design gates
**Last updated:** 2026-11-11 21:47 UTC
**Overall status:** In Progress

## Current Objective
Continue all three design gates: wrist handedness/moving masses/jaw articulation, elbow pitch/routing/controller compensation and actuator capacity, and dimensioned fabrication interfaces/source editability. Preserve source CAD and previous reports; produce revised evidence where the expanded audit finds omissions. The analysis baseline does not establish physical performance, safe payload, printable-part release or repaired original Art1 history.

## Next 3 Actions for Liam
1. Measure bench dimensions, desk thickness/material, rear clamp clearance and camera mounting clearance. These determine the removable mount and reachable workstation layout.
2. Printer identified: **Anycubic Kobra 3 Max**, nominal **420 × 420 × 500 mm** build volume. Provide actual nozzle/slicer profile and PLA/PETG/ABS brands; see [fabrication record](arm-01/hardware/fabrication.md). All three material families are confirmed available; actual densities, sliced part masses, dimensional fit and printed strength remain unverified.
3. Review [load assumptions](arm-01/docs/thor-load-analysis.md), [material comparison](arm-01/hardware/cad/thor-material-comparison.json) and [incomplete Thor cost study](arm-01/hardware/thor-cost-study.md) before any purchase or fabrication decision. No orders or powered tests are approved by these calculations.

## Next Steps for Codex

### Active desktop run — 2026-11-11

- Started at **19:36 UTC** (13:36 America/Chicago); target integration freeze **01:36 UTC November 12**, final handoff approximately **02:36 UTC**. Actual elapsed time will be recorded at completion.
- No existing RAFTEL checkout was found on this Windows host after checking the current workspace, project/worktree locations and user-directory checkout names/origins. Created `C:\Users\howet\Desktop\claudex\RAFTEL` from current `main` **6608d37**, fetched `origin/main`, and started `codex/arm01-desktop-seven-hour`. No pre-existing local changes were replaced.
- Six specialists own exclusive new files in CAD diagnostics (A1/A2→A7 fallback), wrist/jaw reconciliation (W1–W4), spatial kinematics (K1–K3), scenario/load tools (M1–M3), controller replay (C2–C4/C8), and fabrication preparation (F1/F2/F4/F6). A seventh specialist performs independent evidence/math review. Root owns Git, CI, shared integration, evaluation and this handoff.
- Native capability investigation succeeded using an official verified portable **FreeCAD 1.1.4** archive, pinned Fasteners and historical Gears 0.0.3 source checkouts, isolated preferences and copied inputs. No global installation or existing preferences were changed. A fresh exact static Art1 compatibility wrapper plus the other 56 unchanged siblings restored/recomputed **53 documents / 3,001 objects**, all final states up to date; shape scope was deliberately `none`, so this is compatibility/state evidence, not whole-shape validity or original-history repair. All **57 original CAD files + 589 addon files** remain hash-identical. See [Windows native foundation](arm-01/docs/thor-windows-native-foundation.md).
- First Windows/Python **3.14.6** baseline: **321 passed / 4 failed**. One failure was Git CRLF conversion invalidating a pinned JSON byte hash; exact unchanged Git blob bytes were restored and an LF checkout policy added. Three reproduction failures were platform math roundoff (~1e-15), not changed model inputs. Reproduction checks now retain exact types/structure/provenance and use 1e-12 relative/absolute tolerance only for finite floating values; meaningful-change negative fixtures added. Historical reports and model equations remain unchanged. **330 tests now pass**, with focused lint/format and whitespace checks passing; original installation/compilation/sorter/generic-analysis checks passed. Independent review found no blocking issue; mixed-case native CAD filenames are explicitly binary in the LF policy.
- **Published checkpoint:** [PR #8](https://github.com/LiamHoweth/RAFTEL/pull/8) merged as `905f0c257e41445dc079714565f669f7a414b6bb`; exact head `64068483b3bd9af9441c7fa3f2ee6746fe471075` passed all eight Linux/Windows Python 3.11–3.14 jobs in [run 43090175397](https://github.com/LiamHoweth/RAFTEL/actions/runs/43090175397). The working feature branch includes the merge and preserves ongoing new files.
- **Merged engineering checkpoint:** [PR #9](https://github.com/LiamHoweth/RAFTEL/pull/9) merged as `c3d72da929245366895b7b2af80e143db686cb9c`. Exact head `0ba5abf68a38d271a38595d77dda93a5598ba20b` passed all eight Linux/Windows Python 3.11–3.14 jobs in [run 43105339390](https://github.com/LiamHoweth/RAFTEL/actions/runs/43105339390). The earlier Linux fixture failures were fixed by controlling simulated disk capacity; the real 50 GiB native reserve is unchanged. The near-rank inertia validator fix also passed 20,000 independent rotated/scaled cases. Original evidence/model equations are unchanged.
- **Current follow-up validation:** **1,281 tests pass** on Windows/Python 3.14.6 (92.37 s), Ruff lint/format passes for 136 Python files, compilation passes, and 286 text files pass the LF guard. A newly built wheel SHA `b4ed6cdb5bb06217bb209e25a6b4496b5dda6807829370e9b935dc4d7e983ed3` imported **43 modules** from a fresh installed environment; both CLIs passed success/failure/invalid-input checks (0/1/2). Verification installed with no dependency/network package acquisition; wheel build backend acquisition was separate. Source-free working directory is under ignored `.work`, not outside the checkout.
- Independent review found CRLF in 15 newly generated text artifacts, including the raw-hash-bound jaw ledger. Root normalized only new text files; owners fixed deterministic LF writes and regenerated dependent bindings/reports. **241 text files now pass** the LF guard, and independent raw-hash/provenance checks match. Both fabrication CLIs also reject existing outputs, aliased destinations and protected-input collisions; race failures preserve existing evidence. Original CAD and historical report bytes remain unchanged.
- All initial lanes have independent review acceptance for their declared offline/source/conditional scope. Additional checks include 84 seven-coordinate potential comparisons (maximum 1.4491e-9 N·m), independent jaw/mating quaternion transforms, sampled IK successes and honest local failures, 300 trajectory segments, 80 separate identification regressions, 200 full-wrench mount cases and fresh sensitivity extremum witnesses. These are mathematical/source checks, not native rebuilds or hardware qualification.

| Lane | Implemented candidate and evidence | Still open |
| --- | --- | --- |
| A1/A2/A3/A7 | Pinned Art1 ZIP/XML/reference fingerprints; historical cut-loss analysis; guarded copied-document native probe and semantic circle/cylinder matching | Native unchanged/intersection/frame/length/ThroughAll experiments executed; ThroughAll restores hole but candidate fails exact metrics and nominal-return gates; no repaired history accepted |
| W2/W4 | 66-leaf jaw ownership, 18 moving COMs, distinct saved/ideal normalization, multi-pose repair predicates | Native loop closure, contact, retention and physical aperture |
| K1–K3/T1 | Revisioned frames/provisional constraints, nominal spatial Jacobian, bounded local pose IK, explicit-study quintic paths | Native nonzero poses, calibrated extrinsics/limits, collision and physical path acceptance |
| M1/M2/M3/M5 | Hash-bound scenarios, 12 saved/ideal jaw load cases, inertia algebra, 1,620-case sensitivity grid with witnesses | Eight native cached BRep geometric tensors extracted with nine primitive fixtures; physical density/purchased tensors and complete dynamic/capacity claims remain unknown |
| C2–C6/C8 | Exact source conversion/readback fixtures, bounded synthetic replay, uncommissioned calibration records, synthetic identification and conditional coupled demands | Real firmware identity, source-vs-hardware calibration, measured feedback and moving capacity |
| F1/F2/F4/F6 | Source-linked base/socket drawings, 65 printed instances/46 source assets/47 geometry variants, blank measurement imports | Native final-solid exports, actual machine/material/profile/fit evidence and fabrication release |
| R1/R2/E1/E2 | Independent mass/potential/frame checks; strict outcome replay, installed evaluation CLI and layout-aware summaries; wheel/offline checks | Final integrated regression/CI/publication and further review fixes |

- **Additional user instruction (active):** start print planning in the installed **Anycubic Slicer Next**. Root opened the existing app through the computer-use skill; two window captures timed out, including recovery, so GUI edits are paused pending an awake/unlocked visible desktop. Local profile/source-mesh audits and draft plate preparation continue independently. No printer start, cloud upload, hardware motion or fabrication release is authorized. Pinned upstream STLs must remain distinguishable from verified native final-solid exports; saved source-only extras and mirrored geometry must not inflate installed quantities.
- Saved-profile audit confirms Anycubic Slicer Next **2.0.0.3**, Kobra 3 Max **0.4 mm / 0.20 mm Standard / Anycubic PLA** software selections. Six inherited profile files/hashes and a redacted field whitelist pass independent review; physical nozzle/spool/bed confirmations remain null. Of 49 pinned nominal source STLs, 46 correspond to installed assets and three are source-only extras. Three source meshes fail exact-vertex topology checks; four installed instances from them plus the missing reflected-finger variant are blocked. The remaining 60 instances are draft-planning candidates, not print-qualified parts; native/STL geometric equivalence and self-intersection checks remain open.
- The bounded native capability and C7 compiler investigations both yielded actual evidence within their first windows. Follow-up work now uses those verified capabilities rather than installing a robotics stack. Native processes remain serialized; current bounded tasks check selected nonzero assembly frames and three wrist study poses. Host-only fit-coupon, orientation and source-notice work uses exclusive new files. None introduces a hardware/camera backend.

- **Native follow-up checkpoint in preparation (21:40 UTC):** current branch `codex/arm01-native-print-followup` preserves PR #9 plus native evidence, V1 replay and C7 compile-only work. All native runs use fresh paths; no hardware backend exists. Art1 ThroughAll candidate is retained as **UNACCEPTED**: it restores the bolt hole but nominal edit-return differs by 0.0177205 mm³, so no procedural migration or fabrication acceptance is claimed. A bounded kernel metric-semantics probe is underway.
- **M3/C7/V1:** nine native primitive inertia fixtures and eight selected cached BRep captures succeeded without opening/recomputing CAD documents; physical mass/inertia remains conditional. Two source-pinned AVR builds produced byte-identical ELF/HEX (31,640 flash bytes / 2,075 static SRAM bytes); six warnings have a source audit and remain firmware-review gates. No firmware was executed, flashed or connected to hardware. Strict recorded-observation replay is implemented with explicit clock/frame/uncertainty checks and preserved rejection evidence.
- **Print drafts:** six original source-STL generic 3MF drafts are preserved. Native cached-mesh auditing finds seven of eight selected variants closed/manifold by the declared exact-vertex checks; Art4 transmission column still has three nonmanifold edges. Eleven separate one-part native draft projects cover seven variants, including both actual saved gripper fingers. These are generic 3MF inspection drafts, not verified Anycubic imports or sliced/process-qualified jobs. Desktop capture/input remains blocked; no G-code, cloud upload or printer command was produced.

### Seven-hour desktop run: objective and operating rules

**Planned work, not a claim that these features exist.** Spend approximately seven hours of wall-clock time advancing the highest-value software/CAD work below, with at least five agents and one integration owner. The aim is a reviewed, reproducible improvement to the Thor model and engineering tools, with tested milestones pushed and merged. A seven-hour window is a work budget, not a promise to solve every mechanical or physical uncertainty.

Start from current GitHub `main`, read `AGENTS.md`, `AGENT_NOTES.md` and this file, inspect local changes, and verify available tools. The current implementation baseline is [PR #6](https://github.com/LiamHoweth/RAFTEL/pull/6): 325 passing tests,518 installed CAD leaves,517 mass records, source-supported ideal wrist handedness, offline transmission/jaw models and explicit remaining gates. Reuse these implementations. Preserve untouched upstream CAD, historical reports, user changes and the distinction between source inspection, conditional analysis and physical evidence.

- **Ownership:** give each agent a bounded task and exclusive files. Root owns shared manifests, `nextSteps.md`, cross-lane integration and Git. Independent review checks evidence and math rather than merely repeating implementation tests. Coordinate schema changes before producing dependent reports.
- **Native tooling:** reuse the pinned portable FreeCAD/addons when available. Permit one whole-assembly run at a time; prefer small selected-shape/feature probes. Use isolated preferences, fresh output paths and copied documents. Verify hashes before/after. If the runtime is absent, record the capability gap and advance pure-Python/report/drawing work; do not spend the run reinstalling an entire robotics stack.
- **Bounded investigations:** after 45–60 minutes without new evidence, record the attempted hypotheses/results and switch to another ready item. A difficult CAD repair must not idle the other agents. Keep failed candidates and useful evidence; reject cached shapes or empty cuts masquerading as rebuilt success.
- **Validation and publication:** update this file at milestones, blockers and handoffs. Push a logical, tested checkpoint about every 45–60 minutes when meaningful changes are ready. Run focused checks during development, then the full relevant suite and matching-head CI before merge. Merge is already authorized at a good verified checkpoint. Never force-push or overwrite existing evidence.
- **Boundaries:** no serial connections, hardware backend, real-motion flag, flashing, energizing, purchases, vendor messages or fabrication release. Agents may prepare source revisions, parametric proposals, simulated protocols, measurement forms and analytical test plans. Actual dimensions, calibration, printed properties and motor capacity must remain unknown until supported.

#### Parallel assignments for the next seven hours

| Lane | First work | Concrete target for this run | Fallback if the first investigation stalls |
| --- | --- | --- | --- |
| CAD migration | A1–A2 | Reproducible first-drift and disappearing-cut diagnostics; a repaired candidate only if semantic geometry is established | A3 reference fingerprints and A7 acceptance automation; report the precise unresolved cause |
| Wrist and gripper | W1–W3 | Multi-pose gear diagnostic and exact jaw/pivot ownership map; separate ideal and saved configurations | W4 repair specification and M2 moving-body ledger without claiming native loop closure |
| Frames and kinematics | K1–K3 | Revisioned frame/limit inputs, independently tested nominal spatial Jacobian, then bounded IK if time permits | Complete Jacobian/singularity/error fixtures; leave IK explicitly incomplete rather than adding an untested solver |
| Loads and dynamics | M1–M3 | Scenario manifest and jaw-coordinate COM/load extension with mass conservation and potential checks | M5 conditional sensitivity report and ranked missing measurements |
| Controller analysis | C2–C4 | Exact source-conversion fixtures, in-memory channel/protocol replay and calibration evidence schema | C5 synthetic identification and C7 source-build feasibility, without a real backend |
| Fabrication preparation | F1–F3 | Source-linked interface drawings, printable-asset export manifest and validated draft meshes/coupons where tools permit | F4 orientation/inspection matrix and F6 slicer/weight import fixtures using synthetic records |
| Integration and independent review | R1–R3, E1 | Own shared contracts; check source coverage, units, mass, derivatives and historical reproduction; publish verified PRs | E2–E3 deterministic evaluation/fault fixtures and improved evidence checks |

Use at least five simultaneous specialist agents where files and dependencies permit. Seven lanes are proposed; use a dedicated reviewer and avoid launching more native processes merely to occupy slots. The coordinator may implement an independent lane while integrating. Every lane should finish with a useful artifact or a specific evidenced blocker.

| Elapsed wall time | Integration checkpoint |
| --- | --- |
| 0:00–0:30 | Confirm branch/source/tool state, reserve disk space, assign files and schemas, record actual starting test baseline (325 at this handoff) and start independent work. Do not reset a dirty checkout. |
| 0:30–2:00 | Produce first native diagnostics and pure-math fixtures. Push the first meaningful tested checkpoint; freeze any shared schema needed by other lanes. |
| 2:00–3:30 | Integrate frame/Jacobian, moving-body and protocol results. Review candidate CAD geometry feature by feature. Publish a second checkpoint when independently checked. |
| 3:30–5:00 | Continue the strongest ready tasks: jaw/load integration, bounded IK, drawing/export validation or uncertainty studies. Replace stalled investigations with their listed fallbacks. |
| 5:00–6:00 | Freeze interfaces and candidate reports; run cross-lane source/mass/frame/potential/virtual-work checks. Resolve review findings and stop expanding scope. |
| 6:00–7:00 | Full relevant local checks, CLI/report reproduction, final PR, exact-head CI and authorized merge. Leave time for failures; finish with actual commit/run links, unresolved gates and a clean handoff. |

If tool/session availability ends the run early, report actual elapsed work and the next resumable action; do not claim seven hours were completed. This plan does not create an automation or imply agents keep working after a session ends.

### Full agentic backlog and completion criteria

**Readiness:** **Ready** can start with current repository/source evidence; **Conditional** can proceed with explicit modeled inputs; **Dependent** follows the stated prerequisite; **Input** allows preparation now but final acceptance needs external measurements or exact hardware data. All unchecked items below are planned. Do not attempt the entire backlog in seven hours; use the selected lanes above and pull fallback work from this list.

#### A — Restore Art1 source editability

Follow the [Art1 gate](arm-01/docs/thor-art1-editability-gate.md); the static snapshot remains the accepted analysis baseline.

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| A1 | Ready | [ ] Compare saved/rebuilt `Sketch→Pad→Sketch001→Pad001→Sketch002→Groove` with a compact per-feature native report. | Identify the earliest geometry drift; distinguish support, solver and kernel changes using dimensions, placements, volume and bounds. |
| A2 | Ready | [ ] Isolate why `Sketch003→Pad002→Sketch004→Pocket` loses the bolt cut despite Up-to-date states; run one-variable experiments. | Explain the missing approximately 119.383mm³ cut and demonstrate actual material removal in any proposed repair. |
| A3 | Dependent | [ ] Recover stable semantic supports for the saved 1.7mm-radius bolt hole, preserving spreadsheet expressions and mechanical meaning. | After A1–A2, center/axis/radius/cut extent match saved intent; no arbitrary replacement of `Edge13` by another index. |
| A4 | Dependent | [ ] Rebuild `DatumPlane001`, Sketch005 head recess, reversed pocket and mirrored cuts in a copied candidate. | A3 hole exists first; recess and patterns actually cut the intended geometry with no malformed constraints. |
| A5 | Dependent | [ ] Migrate the remaining recorded subshape-dependent objects in Body order (53 total across the full chain); retain an old-reference→semantic-reference ledger. | Every operation and attachment has a checked meaning; no empty operation or cached downstream Body is accepted as success. |
| A6 | Dependent | [ ] Add save/reopen/force-rebuild and small reversible spreadsheet/frame-driving edit fixtures. | Restoring nominal inputs returns nominal geometry; named datums follow intended edits instead of staying accidentally frozen. |
| A7 | Ready | [ ] Automate exact-compatibility comparison: solids, volume, bounds, COM, bidirectional differences, hole axes,24 datum matrices and25 assembly targets. | All checks agree; conflicting kernel results trigger investigation. Numerical comparison thresholds are not manufacturing tolerances. |
| A8 | Dependent | [ ] Substitute an accepted candidate into a new compatible assembly copy and regenerate affected geometry/load evidence. | A6–A7 pass first; installed transforms/recalculation pass. Label intentional redesign separately and preserve previous reports. |

#### W — Resolve wrist contact and gripper articulation

Reuse [handedness evidence](arm-01/docs/thor-wrist-handedness.md) and [jaw math](arm-01/docs/thor-gripper-kinematics.md).

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| W1 | Ready | [ ] Extend wrist perturbation diagnostics across multiple fold/roll phases, both directions and source tooth/contact regions. | Record both-side penetration/separation and witness configurations; retain existing apex/module discrepancies and avoid claiming conjugate contact from sign evidence. |
| W2 | Ready | [ ] Map every jaw gear, link, finger, horn, fastener and bearing to its pivot/trajectory and native→ideal frame transform. | Every leaf is accounted for once; saved 0.171/0.153mm loop residuals and phase offsets stay visible. |
| W3 | Conditional | [ ] Create a derived jaw assembly with explicit loop/gear constraints or independently evaluated closed-loop transforms. | Multiple configurations satisfy both loops and equal/opposite gear increments; source geometry changes and idealization are documented. |
| W4 | Conditional | [ ] Investigate a separate bevel design revision with compatible pitch-cone/apex placement and controlled tooth parameters. | Establish design intent first; compare native contact/interference across phases and changed interfaces. Do not relabel changed geometry as exact source migration. |
| W5 | Dependent | [ ] Add jaw-contact/clearance and ideal force-lever-arm studies for declared object sizes/contact forces. | W2–W3 supply trajectories; detect toggles/singularities, verify free-body/virtual-work identities, and leave real servo force/stroke unqualified. |

#### M — Complete conditional mass, inertia and demand models

Preserve the [v2 ledger](arm-01/hardware/cad/thor-wrist-membership-v2.json) and [moving-mass assumptions](arm-01/docs/thor-moving-mass-closure.md).

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| M1 | Ready | [ ] Bind inventory, membership, materials, belt masses, payload COM, jaw pose, source hashes and conventions in one versioned scenario manifest. | Units, provenance and evidence class are explicit; stale/missing inputs fail; historical studies still reproduce. |
| M2 | Dependent | [ ] Build a jaw-dependent whole-arm moving-body ledger and separate revised gravity study. | Use W2; conserve every old mass and purchased total. Verify all six arm plus jaw potential gradients; keep saved and ideal jaw configurations distinct. |
| M3 | Ready | [ ] Extract centroidal geometric inertia for density-modeled solids; transform/aggregate with explicit frames and parallel-axis terms. | Analytical primitive, symmetry, unit-scaling and frame-covariance checks pass. Purchased internal and nonuniform-print inertias remain unknown parameters. |
| M4 | Conditional | [ ] Parameterize rotor inertia/eccentricity, belt density/path effects and conditional rigid-body dynamic efforts. | Requires M3 inertias, K1 frames and per-body translational/angular Jacobians; conserve whole-motor masses, test kinetic-energy/mass-matrix/power identities, and report incompleteness when parameters are absent. |
| M5 | Conditional | [ ] Sweep defensible pose, jaw, payload/overhang, print fraction, material, radius, efficiency and shoulder-sharing scenarios. | Publish assumptions, seeds/ranges and extremum witness poses. Sampled maxima are labeled sampled, not certified travel or worst-case capacity. Rank useful measurements. |
| M6 | Dependent | [ ] Export coupled shaft torque–speed–acceleration–duty demand packages and structural interface load cases. | M3–M5 plus explicit rates/accelerations from T1/C6 provide dynamic inputs; global reactions and joint/shaft power agree. Missing friction/inertia or matching motor curves precludes complete capacity margins. |
| M7 | Dependent | [ ] Regenerate changed-part, mass/COM/inertia and load-delta reports whenever accepted derived CAD changes. | New CAD revision is bound to every downstream artifact; no changed geometry silently reuses previous load evidence. |

#### C — Reconcile controller coordinates without hardware access

Reuse [the source audit](arm-01/docs/thor-controller-compensation.md) and `thor_transmission.py`.

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| C1 | Ready | [ ] Resolve the official Fly firmware release to pinned RRF/TeamGloomy source and trace selected kinematics, drive mapping, stepping and readback. | Pair source/release/config hashes; locate or exclude mixing for that audited build. Record unavailable source precisely; installed firmware remains unknown. |
| C2 | Ready | [ ] Reproduce exact ROS degree conversion/truncation, offsets, ordering, command suppression and both readback branches in regression fixtures. | Boundary/negative-angle examples distinguish exact source behavior from the existing continuous approximation without silently changing it. |
| C3 | Ready | [ ] Implement bounded in-memory/file protocol replay for per-axis moves, G90/G91, offsets, scalar step rounding and synthetic status. | Source-matching shoulder/elbow/coupled cases and malformed/stale/partial inputs pass; outputs remain tagged diagnostics, with no port or hardware backend. |
| C4 | Ready | [ ] Define calibration evidence records for ratios, signs, carrier coefficient, scales, zeros, firmware/settings hashes and uncertainty. | Unknown/source/assumed/synthetic/physical states are distinct; incomplete records support analysis but cannot masquerade as commissioned settings. |
| C5 | Conditional | [ ] Fit identifiable ratio/carrier/sign parameters from synthetic observations, including noise, quantization, backlash-like hysteresis and insufficient excitation. | Recover known fixtures within stated tolerance; ambiguity and inconsistent samples fail visibly. Produce an unpowered measurement worksheet. |
| C6 | Dependent | [ ] Propagate joint rates, accelerations and provisional limits through coupled maps, including simultaneous shoulder/elbow demand. | Use K2/C4; finite differences and inverse/virtual-work identities agree. Source scalar limits are never called safe physical limits. |
| C7 | Ready | [ ] Cross-compile pinned GRBL without flashing if a bounded AVR toolchain is available within the disk reserve. | Record toolchain/macros/build hash and memory output, or exact compatibility blocker; preserve license obligations and avoid committing toolchains/binaries. |
| C8 | Ready | [ ] Audit sent/accepted/planned/completed/state-report semantics and simulate reset, mode/offset changes, lost acknowledgments and unequal shoulder channels. | No command-derived step count is falsely treated as measured pose; document the future backend contract without implementing real motion. |

#### F — Prepare fabrication and removable interfaces

Use the [dimensioned proposal](arm-01/docs/thor-fabrication-gate.md); actual profiles and bench data are still missing.

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| F1 | Ready | [ ] Produce dimensioned SVG/PDF interface views and datum/transform tables for the asymmetric base pattern, socket, radial retention and cable access. | Every source dimension traces to a pinned object/frame; source and proposed dimensions are visibly distinct; independent overlays/transforms pass. |
| F2 | Ready | [ ] Build an export manifest mapping 65 installed printed leaves to 46 unique assets, quantities, hashes, frames and the mirrored finger. | Reconcile quantities/volumes with the ledger; export final solids once; identify static Art1 and all derivative attribution obligations. |
| F3 | Ready | [ ] Export draft final-solid meshes and source-derived fit coupons where native tools are available; validate units, manifoldness, dimensions and tessellation. | Preserve nominal geometry and label offset variants. No export is described as print-qualified or a manufacturing release. |
| F4 | Ready | [ ] Record orientation/support/removal/inspection candidates for every printed asset, comparing alternatives at loaded pivots/gears/collars. | Each rationale identifies layer-sensitive features and inaccessible supports. Actual slicing/settings await the real machine/material profile. |
| F5 | Conditional | [ ] Parameterize the 300×320mm adapter draft and rigid-plate/bolt/clamp equilibrium model using full base wrenches. | Reactions balance forces/moments; singular support layouts fail. Thickness, clamp selection and desk crushing/slip remain dependent on actual data. |
| F6 | Ready | [ ] Create slicer/weight/fit import templates and synthetic fixtures linking per-part model/support/purge masses and measurement resolution to the ledger. | Provenance is required, purchased assets stay counted once, and baseline reports remain reproducible. Actual slicing/weighing values remain blank. |
| F7 | Input | [ ] Prepare actual-profile slicing and coupon comparison workflow, then execute computational slicing only after profile/nozzle/material inputs exist. | Capture slicer/version/profile hashes, usable area, orientations and mass/time; no invented settings or infill→whole-part-fraction equivalence. |
| F8 | Ready | [ ] Write unpowered assembly, remount-repeatability, clearance, restrained proof/deflection/creep and inspection specifications. | Each test names instruments, preconditions, measured outputs and acceptance-limit source. Physical execution/release remains a separate gate. |

#### K — Build spatial kinematics and useful workspace evidence

Nominal FK exists; IK, collision checks and calibrated limits do not.

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| K1 | Ready | [ ] Reconcile native/ROS/bench/mount/tool/TCP/camera frames in a revisioned transform schema with source and calibration provenance. | Composition/inverse/covariance and independent native nonzero-pose checks pass; unmeasured extrinsics/TCPs remain nullable or explicit scenarios. |
| K2 | Ready | [ ] Extract source joint limits, stops and interference evidence into separate source/study/calibrated fields and a pure validator. | Reject contradictions/nonfinite/unknown required inputs; provisional study ranges are not permissions for motion. |
| K3 | Ready / Dependent | [ ] Add an analytical or independently checked nominal spatial Jacobian and singularity diagnostics using existing FK. Add bounded pose IK after K1/K2 and Jacobian checks pass. | FK→IK→FK position/orientation residuals pass across generated, near-singular, limit and unreachable fixtures; timeouts/failure reasons are explicit. |
| K4 | Conditional | [ ] Derive conservative per-link collision proxies and bench/bin/tool obstacles, with documented intended-contact exclusions. | Test intersecting/tangent/separated fixtures and native poses; coarse proxies never imply unverified exact clearance. |
| K5 | Dependent | [ ] Sample joint/orientation/approach-constrained workstation coverage with IK and collision screening. | K1–K4; report resolution, seeds and accepted/rejected reasons with witness poses. The reach sphere is not substituted for usable workspace. |
| K6 | Dependent | [ ] Generate parameterized camera/source/bin/cable keepout layouts and compare task coverage/overhang sensitivity. | K5 supplies reachability; actual bench/bin/camera dimensions can replace scenarios. No layout is physically approved by a coverage plot. |

#### T — Plan offline manipulation trajectories

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| T1 | Dependent | [ ] Add joint-space timed paths with endpoint/continuity/velocity/acceleration checks using provisional constraints. | K2–K3; derivatives agree numerically, duration/failure limits are bounded, and no serial output exists. |
| T2 | Dependent | [ ] Check complete approach/grasp/retreat/transport/release paths for collision and IK branch jumps. | K4/T1; adaptive segment checks include counterexamples between endpoints; unknown clearance stays unknown. |
| T3 | Dependent | [ ] Generate geometric parallel-jaw grasp candidates for declared cubes/cylinders, jaw openings and object COMs. | W3/K3–K5; explicit no-grasp reasons, support/occlusion checks and no unsupported retention-force claim. |
| T4 | Dependent | [ ] Connect offline pose/path plans to the existing task planner through reusable models and a mock execution adapter. | Preserve current logical tests and failure semantics; classify results as kinematic simulation, never physical completion. |

#### V — Prepare perception and calibration offline

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| V1 | Ready | [ ] Add recorded/synthetic observation replay with timestamp, frame, uncertainty and data provenance. | Deterministic replay and missing/stale/wrong-unit inputs are tested; no real camera capability is claimed. |
| V2 | Conditional | [ ] Implement intrinsic/extrinsic calibration data contracts and synthetic camera/distortion/transform fixtures. | Held-out reprojection/world-point checks and wrong-transform tests pass; planar-height assumptions are explicit. Use optional pinned libraries only for concrete work. |
| V3 | Conditional | [ ] Prototype offline colored-cube/cylinder segmentation, pose estimation and occlusion/confidence rejection on labeled fixtures. | Separate held-out scenes; report errors/misses and lighting/height limits, rather than promoting synthetic detections to real accuracy. |
| V4 | Dependent | [ ] Fuse calibrated/replayed observations with K1 and T3 for object-to-base/grasp candidates and bin outcome verification. | Stale/missing extrinsics reject operation; incorrect-bin/drop/missed-detection cases are detected in fixtures. |
| V5 | Input | [ ] Prepare real camera/target capture and calibration-import workflows; process supplied data when available. | Actual device/images/target dimensions are required for measured accuracy; request camera access before starting a live device session. |

#### E — Strengthen evaluation and simulated failure handling

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| E1 | Ready | [ ] Build an offline JSONL scorer/replayer for presented/detected/eligible/attempted/correct/failed/assisted objects and first-attempt versus retry outcomes. | Hand-counted fixtures agree; skips, misses and timeouts never become successful sorts; evidence class stays in every run. |
| E2 | Ready | [ ] Add seeded multi-layout benchmark fixtures and confidence-interval/layout-level summaries matching the verification plan. | Report coverage and end-to-end outcomes separately; correlated layouts and observed proportions are not physical reliability proofs. |
| E3 | Ready | [ ] Extend mock fault injection for stale state, partial/out-of-order responses, inconsistent shoulder channels, resets and uncertain held-object state. | Bounded retries, idempotent stop and fault persistence pass; no automatic false recovery or verified physical pose. |
| E4 | Dependent | [ ] Add kinematic/vision replay scenario packs and regression comparisons for accepted model revisions. | T4/V4; preserve seed/config/source hashes and separate logical, kinematic, physics and physical results. |
| E5 | Ready | [ ] Prepare measurement forms and offline validators for zeros/limits, belt increments, jaw closure, fit/mass/COM, thermal duty and outcome observations. | Unknowns stay blank; units, instruments, uncertainty, conditions and invalidation triggers are explicit. Agents can score later supplied measurements. |

#### R — Make evidence and software reproducible

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| R1 | Ready | [ ] Reproduce baseline/current reports from pinned inputs; automate source-terminal,518-leaf/517-record and purchased-asset coverage checks. | Every retained/excluded terminal has a disposition; changed inputs invalidate stale output; no inventory-internal check is mislabeled physical completeness. |
| R2 | Ready | [ ] Add meaningful negative CLI/schema/provenance tests, installed-wheel/offline smoke checks and deterministic replay to existing CI. | Python 3.11–3.14 passes; missing/incomplete native captures fail clearly. Test only new behavior/risks, not duplicate implementation details. |
| R3 | Ready | [ ] Audit exact source/addon/data licenses, notices, derivative/export attribution and third-party version pins. | Retain obligations in generated artifacts; do not select RAFTEL's company-wide license without Liam's decision. |
| R4 | Ready | [ ] Refresh the exact-part BOM/CAD quantity reconciliation and researched delivered-cost scenarios, including safety, mount, consumables, tax/shipping and reuse assumptions. | Fresh primary sources/access dates and missing quotes are explicit; research is not purchasing approval and no vendor messages are sent. |
| R5 | Ready | [ ] Consolidate current-versus-historical documentation, requirement→artifact→check traceability and concise durable agent notes. | Links resolve, claims match code/evidence, no planned feature is called implemented, and next actions remain immediately resumable. |

#### H — Prepare electrical and commissioning designs

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| H1 | Ready | [ ] Reconcile exact candidate motor/driver/servo/controller revisions, pinouts, voltage domains, current conventions and primary specifications. | Separate peak/RMS/phase/supply current and static/moving ratings; preserve PG5 supplier conflicts and unverified servo variants. |
| H2 | Conditional | [ ] Draft power-domain, distribution, protection, cooling and keyed-connector/harness proposals with parameterized loads. | DC supply demand is not a naive sum of phase currents; every part rating/source and unknown transient/thermal input is explicit. No wiring release. |
| H3 | Ready | [ ] Prepare independent-stop, motor-energy isolation, restart-prevention and gravity-restraint requirements plus fault-tree/acceptance documents. | Cover every motor source and retained energy; software stop is not substituted for physical energy interruption. No circuitry is called protective before inspection/testing. |
| H4 | Ready | [ ] Compare actual-position, coupled-channel disagreement, object-presence and temperature/current sensing options using exact specifications. | Explain detectable/undetectable failures and future interfaces; step counts/homing/PWM alone never establish measured joint/grasp state. |

#### I — Optional integrations after the model supports them

| ID | Readiness | Agentic work and deliverable | Completion check / dependency |
| --- | --- | --- | --- |
| I1 | Dependent | [ ] Export a revisioned robot description with audited frames, collision proxies, conditional inertias/transmissions and attribution. | K1–K4/M3; independent loader/FK agrees. Do not reuse upstream 1 kg/identity placeholders as real inertia. |
| I2 | Dependent | [ ] Evaluate one bounded optional physics environment and/or separately pinned ROS/MoveIt adapter after model/export acceptance. | Import, axes, mass/COM/gravity and deterministic analytical fixtures agree; middleware stays outside the dependency-light core. Physics contact/friction results remain modeled. |
| I3 | Ready | [ ] Preserve detachable mount/power/data/frame and timestamp contracts for a future mobile base; recompute Thor-only conditional floor access when K5 exists. | No mobile platform build is added to ARM-01 scope; bench reach is not floor access or chassis stability evidence. |

### Inputs and decisions agents cannot manufacture

Continue ready/conditional work while these remain open. Agents can prepare forms, diagrams, parameterized models, source research and offline evaluators; Liam or physical evidence must supply final values and approvals.

| Needed input / decision | What agents can prepare before it arrives | What remains unverified |
| --- | --- | --- |
| Bench size, thickness/material, underside and clamp access; bin/camera dimensions | Parametric adapter/layouts, equilibrium models, measurement drawings | Final clamp/plate/desk suitability and workstation coverage |
| Actual Kobra nozzle, exported machine/material profiles and filament formulation | Export manifests, orientation candidates, coupon geometry, mass-import workflow | Sliced mass/time, usable print area, fit and printed material properties |
| Actual belt, bearings, fasteners, motor/gearbox/servo/driver/supply revisions | Exact-part research, compatibility tables, uncertainty and test plans | Pitch radius, clamp retention, phase/driver settings, measured shaft loads and moving capacity |
| Physical geometry/mass/COM, signs/zeros/stops, joint sensing, jaw loops and camera images | Synthetic identification, calibration schemas, uncertainty propagation and validation tools | As-built calibration, accuracy, travel, grip force and independent state feedback |
| Fabrication, purchases, powered commissioning and eventual operating approval | Reviewable proposals, quantities, cost/safety and acceptance packages | Orders, assembly, energizing, real-motion testing and safety qualification |
| Final distribution license and any external vendor contact | Source-license/attribution audit and draft questions | Legal/license selection or messages sent on Liam's behalf |

### Completion and handoff for each desktop run

Record the actual elapsed time, agents/ownership, implemented versus investigated work, tests/native modes, input/report hashes, PR/commit/CI links, remaining physical gates and the next three executable actions. Preserve originals, final evidence and useful active caches; remove only superseded task-created generated artifacts after checking ownership and disk use. Leave `main` synchronized after authorized verified merges, or clearly report any remaining branch/CI blocker. The desktop launch prompt is maintained in [docs/arm01-desktop-handoff.md](docs/arm01-desktop-handoff.md).

## In Progress
- Thirteen-agent expanded checkpoint is merged into `main` through [PR #6](https://github.com/LiamHoweth/RAFTEL/pull/6), merge commit `feee3164df21f389c384d57bd6666ce0c7bdd644`. Exact implementation head `fa5744300687e31676e01263238c14545f68e4c7` passed all four Python CI jobs before merge. All specialist lanes are complete; no ongoing background work is implied. Resume the next actions above.
- **Coverage correction:** the historical516-leaf inventory omitted two installed Art4 wrist belts. [Current v2 inventory](arm-01/docs/thor-geometry-completeness.md) has518 leaves; all516 old rows remain unchanged. Four existing input-pulley/screw leaves now have own-shaft motion. Exact conservation of the earlier inventory did not prove whole-assembly completeness.
- Earlier analytical baselines remain merged through [PR #1](https://github.com/LiamHoweth/RAFTEL/pull/1) and [PR #4](https://github.com/LiamHoweth/RAFTEL/pull/4). Original source CAD, baseline load snapshot, original load/material/wrist reports are unchanged historical evidence. The new reports supersede their coverage for current source analysis.

## Completed and Verified
- [Corrected geometry](arm-01/docs/thor-geometry-completeness.md) and [moving-mass closure](arm-01/docs/thor-moving-mass-closure.md):518 leaves/517 mass records, seven motors2.120kg once, two explicit unmeasured belt mass scenarios add4.833575g. Revised PLA/PETG/ABS masses5.654722/5.707002/5.306190kg. [V2 wrist report](arm-01/hardware/cad/thor-wrist-load-study-v2.json) has conditional self+payload holding fields under centered-rotor, uniform-belt, bearing-COM and saved-jaw assumptions; full physical holding fields remain null.
- [Native wrist handedness](arm-01/docs/thor-wrist-handedness.md) selects intended ideal s=+1 with spatial velocity and bidirectional small-angle diagnostics. [Offline transmission math](arm-01/docs/thor-transmission-coordinates.md) reconciles common-axis and opposed references. [Controller audit](arm-01/docs/thor-controller-compensation.md) traces the missing carrier term through pinned ROS/GRBL commands and readback; installed behavior and Fly core are not asserted.
- [Jaw study](arm-01/docs/thor-gripper-kinematics.md) verifies an ideal35mm parallelogram model and derivatives, while recording0.171/0.153mm saved-loop residuals. [Elbow clamp study](arm-01/docs/thor-elbow-belt-closure.md) traces open tails/radial pressing-screw intent without inventing pitch radius or retention capacity. [Actuator checkpoint](arm-01/docs/thor-actuator-feasibility.md) records exact-model electrical/static/thermal evidence, supplier conflicts and unavailable moving curves; no moving margin released.
- [Dimensioned fabrication plan](arm-01/docs/thor-fabrication-gate.md) and [Art1 editability gate](arm-01/docs/thor-art1-editability-gate.md) include source dimensions, nominal-printer fit, slicing/coupon/fit requirements and staged semantic reference migration. New native evidence rejects the Intersection workaround: an earlier bolt cut disappears despite Up-to-date states. Original parametric history is not repaired.
- Historical [wrist membership](arm-01/docs/thor-wrist-mechanism.md): exact516-leaf ledger;66 Art56 leaves split into carrier, roll/tool, own-axis side rotors and bearing COM approximations. [Wrist math](arm-01/docs/thor-wrist-model.md) uses explicit carried axes and analytic COM Jacobians. [Separate study](arm-01/hardware/cad/thor-wrist-load-study.json) evaluates3 reference materials ×2 handedness alternatives ×4 poses ×3 payloads, retaining null full wrist holding totals.
- [Elbow evidence](arm-01/docs/thor-elbow-mechanism.md) and [load tool/report](arm-01/docs/thor-elbow-loads.md): conditional carrier relation, virtual-work transpose, shoulder reaction and belt tension difference. In the explicit37mm pitch scenario with baseline200g horizontal load, ideal elbow rotor magnitude0.077803N·m and belt difference63.306N; neither qualifies physical capacity or pretension.
- Persistent `AGENTS.md`/`nextSteps.md` workflow, Python logical sorter, tests, CI, requirements, safety and workstation documentation.
- Pinned Fasteners plus saved-schema-compatible Gears0.0.3 restore normally through FreeCAD `-M`; no blanket trust or global security changes.
- Separate static Art1 snapshot preserves exact published final solid and24 datum frames, passes save/reopen/forced-recompute checks, and leaves original source unchanged. Original feature history is preserved separately, not repaired.
- Compatible whole assembly:53 referenced documents,2,129 recalculated features,all3,001 objects Up-to-date with no invalid/pending states. [Report](arm-01/hardware/cad/thor-compatible-assembly-validation.json).
- Native bearing/shaft geometry corroborates all six unsigned zero-pose joint-axis lines and CAD→ROS rotation Rz(-π/2). Commands, physical zeros and travel limits remain uncalibrated.
- Historical [geometry inventory](arm-01/hardware/cad/thor-mounted-geometry.json):516 retained installed solid instances, with14 hidden procedural inputs excluded; all retained source shapes passed selected topology checks. This is distinct from topology validation of every history feature.
- Nominal source FK and traceable mass/statics tools. Historical516 leaves are assigned exactly once by515 mass records; seven motors total2.120kg once, with a separate servo and horn. Independent ledger/COM/gravity sums match.
- Historical [conditional load study](arm-01/hardware/cad/thor-load-study.json) and [mass ledger](arm-01/config/thor-load-snapshot.json) reproduce exactly from saved geometry. Illustrative50% whole-part PLA case:5.650kg including base; 200g horizontal-shoulder case requires ideal joint holding magnitudes5.828N·m shoulder and2.342N·m elbow.
- PLA/PETG/ABS reference-density comparison and provenance-bearing density overrides. Same50% fraction gives modeled masses5.650/5.702/5.301kg respectively; reference products/editions do not identify Liam's actual filament or select a structural material.

## Blockers and Open Decisions
- Original Art1 procedural history still has thickness/external-sketch migration issues; use the validated static analysis snapshot while preserving that original.
- Intended ideal wrist handedness is selected, but saved gears interfere and inferred pitch apices differ. Conditional518-leaf static closure does not prove internal rotor balance, uniform real-belt behavior, manufactured COMs, gear contact or jaw motion. Full physical wrist holding values stay null; saved jaw loops require reconciliation.
- Elbow source route/clamp intent and missing upstream compensation are traced. Effective pitch radius, physical signs/scales/zeros, actual controller version, clamp/traction, shoulder load sharing, moving torque-speed/thermal behavior and dynamic loads remain unqualified. PG5 supplier2versus3N·m document conflict remains unresolved.
- Actual material/profile, printed mass/COM/stiffness/creep, fastener/fit tolerances, positive commands, joint stops, collision clearance, parallel-jaw behavior, mount and independent stop/gravity restraint require further evidence.
- Native CAD, analytical poses and logical sorting are not physical robot performance or a demonstrated90% sorting rate.

## Hardware and Purchasing Status
No hardware was purchased, assembled, energized or physically tested. Liam confirmed PLA, PETG and ABS print availability. The candidate BOM and supplier prices remain research; the complete delivered Thor build cost and structural material selection are open. Printer ownership/model is confirmed by Liam as Kobra 3 Max; published nominal volume is recorded. Actual printer/nozzle/material profiles and remaining computer/tool/camera inventory still need detail.

## Validation Results
- Expanded checkpoint:325 tests pass locally on macOS/Python3.14.4; Ruff lint/format and Python compilation pass. Installed sorter processes10 synthetic objects. Frozen v2 CLI report and original load/material reports reproduce exactly; prior tracked baseline files and original Thor checkout remain unchanged. Matching-head Linux CI passed on Python3.11–3.14, including325 tests and all CLI smoke checks: [run43084731160](https://github.com/LiamHoweth/RAFTEL/actions/runs/43084731160).
- Independent expanded review:518-leaf tree/517 records checked;2,000 wrist and2,000 elbow transmission models;1,000 ideal jaw models;96 integrated six-joint potential-gradient comparisons (maximum1.49e-9N·m); source hashes and108 documentation links. All pass for declared source/ideal models, not physical performance.
- New native evidence: cached selected Pad046 topology validates both installed belt instances; wrist contact/interference, saved-BRep moving masses, gripper, belt/clamp and46 printable source envelopes inspected. No source saves or whole-assembly history rebuild claimed. Approximately51GiB free; useful native runtime/source/evidence retained.
- Prior wrist/elbow implementation passed GitHub Actions on Linux/Python3.11–3.14, including270 tests and new wrist/elbow CLI smoke checks: [run43080568624](https://github.com/LiamHoweth/RAFTEL/actions/runs/43080568624). Exact checked head is `6f6f7278bbec096ce42d940b67cf053ffc825509`. Native evidence remains local source inspection, not CI or hardware testing.
- Prior checkpoint:270 tests pass locally on macOS/Python3.14.4; Ruff lint/format, Python compilation and whitespace checks pass. Installed mock CLI sorts10 synthetic objects. Generic engineering and new wrist/elbow CLI smoke checks pass; both new reports reproduce exactly. Original PLA study reproduction test remains passing.
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
- 2026-11-11: At Liam's request, expanded Next Steps for Codex into a detailed agentic backlog plus a seven-hour parallel execution plan, fallback tasks, dependencies, artifacts and done checks. Added a desktop implementation prompt; no seven-hour run or automation started in this chat.
- 2026-11-11: Verified all four CI jobs on exact headfa57443, then merged PR #6 into main asfeee316. This handoff records actual publication/run evidence. Original source and historical report files remain unchanged; task scratch evidence retained (~18MiB), superseded root comparison report removed, approximately51GiB free.
- 2026-11-11: Expanded checkpoint completed across all thirteen lanes: corrected518-leaf source inventory, intended wrist handedness, motor/belt gravity assumptions, ideal jaw model, full controller-source audit, clamp and actuator evidence, dimensioned fabrication plan and bounded Art1 migration gate.325 local tests and independent review pass; final implementation pushed, all four CI jobs passed and PR #6 merged asfeee316.
- 2026-11-11: First expanded evidence checkpoint: native contact arrangement plus bidirectional ±0.25° diagnostics support ideal wrist s=+1, while existing gear interference prevents an exact-mesh claim. Pinned ROS/GRBL pipeline has no elbow carrier compensation; official Fly configuration is diagonal but its core binary remains unaudited. Core offline forward/inverse/virtual-work models preserve the existing elbow API;44 focused tests and selected Ruff checks pass. Revised518-leaf load integration, jaw/fabrication plans and final suite remain in progress.
- 2026-11-11: Expanded the authorized continuation to all wrist/elbow/fabrication/editability actions with twelve agent lanes. New moving-mass audit found two omitted installed wrist belts and four phase-dependent input pulley/screw COMs; geometry extractor completeness and revised reports are now part of the checkpoint. Earlier reports remain preserved.
- 2026-11-11: Verified exact-head CI and merged PR #4 into main as4099515. Updated this handoff with actual merge/run evidence and next evidence gates. Source checkout remains clean; existing native runtime/evidence retained, approximately53GiB free.
- 2026-11-11: Six current lanes completed and froze the wrist/elbow checkpoint. All270 local tests and lint/format/compile/CLI checks pass; reports reproduce exactly. Added CI smoke checks and durable model contracts. Matching-head CI passed all four jobs; PR #4 is merged as4099515.
- 2026-11-11: Exact wrist ledger passes independent516-leaf/515-record conservation review. Wrist chain math passes an independent300-case transform/Jacobian check; elbow virtual-work/inverse math passes1,000 random cases. Native belt evidence establishes a conditional shoulder-carrier term, with schematic idler mismatches and physical pitch radius/signs retained as open gates. Integration and final suite/CI are in progress.
- 2026-11-11: Resumed wrist/elbow continuation with six agents after clean-main audit. Existing native runtime/source copies are available;53GiB free. No hardware motion or source-CAD changes authorized by analysis.
- 2026-11-11: Liam identified a Kobra 3 Max. Recorded published build volume and remaining profile/filament questions; refreshed today’s daily reading around Thor load paths, material assumptions and this printer. No printer operation or configuration change.
- 2026-11-11: Final implementation CI passed all four Python versions; independently verified the complete ledger/moments and reproduced reports. Merged PR #1 into main as024fe244. Original source/native working copies and useful runtime retained; temporary wheel builds removed, free-space reserve remains above50GiB.
- 2026-11-11: Liam confirmed PLA/PETG/ABS and authorized merging after a good verification checkpoint. Added reference-density comparisons and explicit override provenance; no structural material approval inferred.
- 2026-11-11: Extracted native axis lines and516 installed solids; corrected the90° frame mismatch and duplicate/helper geometry, then independently reviewed the mass ledger and gravity moments. Working-tree suite reaches222 tests.
- 2026-11-11: Published dependency checkpoint6c575ac and compatible-assembly checkpoint0869466. Whole assembly changed recomputation completed; original Art1 history remains separate from exact static geometry/datum snapshot.
- 2026-11-11: Initial bootstrap delivered logical sorting software and persistent engineering workflow; no physical success claimed.
