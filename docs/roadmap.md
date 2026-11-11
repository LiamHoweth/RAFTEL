# ARM-01 development roadmap

This roadmap describes acceptance gates. [nextSteps.md](../nextSteps.md) records the current checked status and evidence; the roadmap alone is not a completion record.

| Phase | Deliverables | Gate before advancing |
| --- | --- | --- |
| 1 — Engineering foundation | Requirements, source-backed mechanical comparison, Thor-first CAD reuse study under the eight-actuator allowance, preliminary geometry/load analysis, candidate BOM, executable logical sorter and CI | Software tests pass; design uncertainty is explicit; six-arm-axis and actuator feasibility questions have actionable closure plans |
| 2 — Mechanical prototype | Licensed/revisioned CAD baseline and focused adaptations, mount design, joint limits, wiring clearances, printed parts and assembled arm | Physical inspection and mount/load evidence; exact actuator variant compatibility; documented as-built dimensions/masses |
| 3 — Hardware control | Driver, joint feedback, calibration, explicit arming, limit enforcement, fault handling and independent motor emergency stop | Supervised individual-joint tests pass; feedback/communications loss and stop behavior verified; gravity-fall risk controlled |
| 4 — Manipulation | Validated robot model, inverse kinematics, collision-aware trajectory planning, gripper control, fixed-location pick/place | Repeatable supervised motion with measured positional and grasp/release outcomes; limits and failure recovery demonstrated |
| 5 — Vision-guided sorting | Camera mounting/calibration, object detection/classification, pose transforms, variable-position sorting, outcome verification | Defined randomized trial protocol; measured perception/calibration errors; no fixed-coordinate substitution for observation |
| 6 — Learning and generalization | Consent-appropriate demonstrations, versioned datasets, policy integration or training, held-out-object evaluation | Improvement measured against a deterministic baseline; training/test separation; policy remains behind independent safety checks |
| 7 — Reliability and mobile readiness | Randomized benchmarks, failure analysis, detachable mount tests, analytical/simulated mobile-clearance study | Reported physical success rate with sample size and uncertainty; reconnect/recalibration procedure; no implied mobile validation without mobile tests |

## Working sequence

Finish dependencies before dependent physical work. Research and mock software can proceed while Liam measures the bench and reviews the mechanical direction. Begin with Thor's existing editable source and study its actual geometry, coupled shoulder drive and gripper. Liam's eight-actuator allowance supersedes the initial seven-total-actuator target; six arm axes plus a gripper remain required. This is study authorization, not approval for fabrication or purchases. CAD changes follow a selected baseline and load model. Actuator purchases follow compatibility, electrical, budget, and safety review. Powered tests follow secure mounting and independent protections.

## Evidence at each gate

Keep source revisions, configuration, test commands, measured results, failures, and unresolved assumptions alongside the corresponding implementation. Update [nextSteps.md](../nextSteps.md) after meaningful milestones and before every handoff. A file existing, a simulation succeeding, or an upstream demonstration does not independently satisfy a physical acceptance gate.
