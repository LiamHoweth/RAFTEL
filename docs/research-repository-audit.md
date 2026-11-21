# Research repository audit

- **Audit date** 2026-11-21
- **Baseline** `origin/main` at `99171635400f845f33578e29ce204cdc3e90cadb`
- **Review branch** `codex/raftel-research-reproducibility`

## Baseline inventory

The audit covered the root instructions, roadmap and handoffs, the ARM-01
package, fixtures and tests, engineering tools, tracked hardware evidence and
the existing workflow. A clean detached Windows checkout with Python 3.14.6
passed 2,200 tests, dependency, Ruff, format, compilation and LF checks.
The seed-42 sorter completed ten mock placements. The assumed-load and floor
reach analysis ran successfully with its existing analytical evidence label.

| Existing work | What the evidence supports | Main gap |
| --- | --- | --- |
| Task, screening, mock backend and outcome replay | A hardware-free sort loop with failures, seeded layout evaluation and a separate observation scoring contract | Single-run exports lacked a reusable input scene, a view of the result and separately resolved placement destinations |
| Recorded observation ingestion | Offline shape, frame, clock/freshness and covariance validation on supplied samples | Camera acquisition, calibrated transforms and ground-truth localization |
| Thor kinematics and trajectories | Nominal source frames, FK/Jacobian, bounded local IK, scalar study limits and offline timed joint paths | Full nonzero native articulation, measured transforms and limits, moving-body and obstacle binding |
| Native CAD and mechanical analysis | Compatible assembly study with 53 documents and 3,001 objects, using a static Art1 snapshot and shape scope `none`. The corrected saved inventory covers 518 leaves. CAD-based mass, load and transmission results depend on declared assumptions. | Original Art1 feature repair, wrist contact, jaw closure, retention and qualified actuator capacity |
| Manufacturing and controller preparation | Cached print variants, generic draft plates, source-derived drive maps and synthetic controller replay | Process and fit qualification, calibrated feedback, fault response and physical commissioning |
| Advanced experiments | Analytical swept boxes, published research references and proposed integration paths | Dynamics/contact simulation, end-to-end manipulation learning, sim-to-real and measured hardware results |

The [engineering evidence index](../arm-01/docs/desktop-evidence-index.md)
links the existing reports and tests. Main's nonzero native frame check uses
three proximal-four-axis poses with both wrist coordinates fixed and leaves
touched objects. The saved-zero box study is a candidate screen. See the
[native pose report](../arm-01/docs/thor-native-pose-frames.md) and
[mounted pair study](../arm-01/docs/thor-mounted-collision-study.md).

The baseline includes the merged Mac workflow from PR #20. Art1 attachment
traces, later wrist marker experiments and Anycubic starter-slice receipts
remain in draft PR #19, which was inspected separately. Its reported adhesion
observations do not advance the baseline's fabrication gate. [Merged PR #20](https://github.com/LiamHoweth/RAFTEL/pull/20) · [Draft PR #19](https://github.com/LiamHoweth/RAFTEL/pull/19)

## Implemented changes and decisions

1. **Make the experiment reproducible.** Extend the installed sorter with
   versioned scene input, an expanded report and data-derived SVG. Keep the
   established event format and outcome codes. The same sorter services both
   CLI and benchmark, with placement observation read from mock backend state.
2. **Close input and evaluation gaps.** Reject duplicate fields, malformed
   configurations, nonfinite or boolean SI values and ambiguous logical bin
   coordinates. Regression fixtures force a misroute and a placement outside
   every bin. Both stay out of the verified-success count even when the task
   accepted the planned target.
3. **Establish a learning experiment with a measurable limit.** Fit a
   nearest-neighbor classifier to generated examples labeled by the existing
   planner. Hold out complete layout seeds and report false considers and false
   defers against rule and trivial baselines. Keep learning outside execution
   and keep the package free of runtime dependencies. See the
   [experiment and research plan](../arm-01/docs/learning-research.md).
4. **Verify the installed experience.** Use one portable driver for local and
   GitHub checks. Reproduce analytical reports, exercise valid and failing
   commands and verify the wheel from a separate environment without acquiring
   dependencies. Preserve the existing Linux/Windows Python matrix.
5. **Make evidence and reuse decisions discoverable.** Index the engineering
   record, define measurable acceptance gates, and add contribution, security,
   and rights-review guidance. See the [documentation index](README.md),
   [roadmap](roadmap.md) and [owner checklist](licensing.md).

## Validation

The [demo guide](../arm-01/README.md) records exact success and failure
commands. Use `python scripts/verify.py` from the repository root to execute
the portable suite from the pinned development environment.

| Check | Result |
| --- | --- |
| Installed seed-42 sorter | 10 sorted, 0 skipped, 0 failed and exit 0. The separate ten-layout evaluation counted 100 correct placements, all on first attempt. Both are logical results. |
| Supplied failure fixture | 1 sorted, 2 skipped and 1 failed after two grasp attempts. Exit 1 preserved the report. Invalid input returns 2. |
| Reproduction and visual review | The seeded JSON and SVG were byte-identical across the Windows CPython 3.11–3.14 test interpreters. The regenerated SVG matches the README illustration and was visually inspected. |
| Learning | Fitted on 300 examples, the classifier matched 94 of 100 held-out planner decisions, with four false considers and two false defers. Repeated runs produced identical JSON. |
| Full portable suite | Windows CPython 3.11.18, 3.12.16, 3.13.18 and 3.14.6 each passed 2,249 tests, dependency consistency, Ruff lint and formatting, compilation, LF and the retained engineering CLI checks. Each fresh offline wheel environment discovered 50 modules and passed ten installed smoke steps. |
| Additional engineering studies | The nominal trajectory example with documented synthetic rate limits, the offline fault injection study and the sparse Thor drive sensitivity study each produced a fresh report on Python 3.14.6. |
| Workflow and independent review | Actionlint passed and all three GitHub Actions pins matched their upstream release refs. Independent review exercised a lean source install, 42 focused regressions and link checks. It found an invalid-scene exit-code issue and a stale documentation anchor, both fixed and retested. The final scan checked 620 relative links and local anchors. |

The [PR checks](https://github.com/LiamHoweth/RAFTEL/pull/21/checks) record the hosted
matrix. The local run used host software and retained engineering evidence. Native CAD, printer, and powered
robot experiments were outside this verification run.

## Remaining limitations

- Purchase, fabrication and motor testing require owner approval. Exact
  actuator variants, duty limits, power and stop behavior, gravity retention,
  mounted clearance, gripper geometry, actual print fit and material properties
  remain open. Native CAD history and evidence are preserved.
- `arm_base` logical coordinates and Thor's nominal `base_link` have no measured
  registration. The learner sees synthetic oracle features. Production
  camera observations, physical grasp and placement verification, contact
  simulation and hardware-in-the-loop studies require their own evidence.
- RAFTEL's distribution license remains undecided. The owner needs to confirm
  rights and decide the scope before a licensed release. The audit identifies
  Thor CAD and controller notice discrepancies and a tracked GRBL diff that
  require file-level treatment. [License review](licensing.md)

## Repository metadata for owner review

Replace the current GitHub description with “Reproducible bench experiments
for affordable robotic manipulation, starting with ARM-01 BenchSort.”
Topics such as `robotics`, `robotic-arm`, `kinematics`, `simulation` and
`embodied-ai` match the current research. Enable private vulnerability reporting
if the repository settings support it. Keep the license field aligned with the
eventual approved release scope.

## Next engineering milestone

Publish a versioned nominal target set in `base_link` with explicit tolerances,
solver initialization and deterministic success, joint-limit and singular cases.
Report translation and rotation residuals for converged FK/IK round trips and
retain capped iterations or failed constraints. Cross-check full-chain and
nonzero wrist markers before binding moving geometry. A measured mount, bench
and tool-center transform is needed before using the study to claim bench
coverage. [Spatial contract](../arm-01/docs/thor-spatial-kinematics.md) ·
[Kinematics and planning gates](roadmap.md)
