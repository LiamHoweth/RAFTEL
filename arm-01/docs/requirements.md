# ARM-01 proposed requirements

All physical values below are **design targets**, pending feasibility and as-built validation. The initial software milestone proves only task behavior against a mock backend.

## Product targets and verification

| ID | Requirement / proposed target | Verification method | Current evidence boundary |
| --- | --- | --- | --- |
| MECH-01 | Six independently controlled arm joints plus one motorized parallel gripper; **up to eight actuators allowed** | CAD joint-tree/drive-mapping inspection, actuator inventory, supervised independent movement | Liam superseded the initial seven-total-actuator target and directed a Thor-first study: seven arm motors, including a coupled shoulder drive, plus one gripper motor. Physical selection remains gated |
| MECH-02 | Approximately 350–450 mm useful reach | Measured geometry, joint-limited IK and collision sampling, physical endpoint tests | Outer reach alone does not establish usable workspace/orientation |
| MECH-03 | Initially manipulate 100–200 g objects | Full downstream load calculation, actuator duty/thermal tests, retained-grasp tests | Payload-only torque is insufficient; current calculations use stated estimates |
| MECH-04 | Rigid removable clamped/bolted workstation mount | Load-transfer calculation, desk suitability inspection, guarded static test | No fabricated mount approved by this document |
| TASK-01 | Three category-specific destination boxes; initially 6–10 objects | Configuration checks; deterministic mock tests; later physical trials | Logical configuration and synthetic categories are not physical classification |
| TASK-02 | Use observed object positions that vary across trials | Seeded scene tests; later randomized physical layouts and camera logs | Initial observations are synthetic; no camera claimed |
| TASK-03 | Detect and report unreachable objects, failed grasps and unsuccessful placements | Failure-injection tests and event/summary checks | Reach-envelope checks are necessary screening only |
| TASK-04 | Target at least 90% successful physical sorting cycles in a defined protocol | Predeclared trial set, per-cycle outcomes, confidence interval and failure report | Mock success rate cannot satisfy this target |
| SPACE-01 | Approximately 800 × 600 mm workstation | Desk measurement and joint/collision-constrained coverage map | This is a workstation envelope, not a promise of complete coverage |
| COST-01 | Aim near US$500; initial planning range US$350–725 | Line-item BOM with shipping/tax, tooling/reuse assumptions and approvals | Budget is provisional; infeasible capability must be reported openly |
| SW-01 | Python core runs without physical hardware or robotics middleware | Clean virtual-environment install and installed CLI smoke test | Python 3.11+ intended; record actually tested versions/platforms |
| SW-02 | Separate hardware, observation, planning, task and evaluation responsibilities | Code review and backend/failure tests | No task logic may issue model-specific servo commands |
| SAFE-01 | Real motion unavailable by default | Entry-point/config inspection; future backend tests | Initial package exposes mock operation only |
| SAFE-02 | Before real motion: explicit arming, calibrated limits, reliable feedback and latched fault behavior | Future integration tests and supervised commissioning | Mock checks do not establish physical safety |
| SAFE-03 | Independent motor-energy emergency stop with controlled gravity-collapse risk | Electrical/mechanical design review and physical stop tests | Software stop alone is inadequate |
| MOB-01 | Preserve detachable mechanical/electrical/data interfaces and frame definitions | Interface specification and later reconnection/load tests | No mobile platform is built or verified |
| MOB-02 | Study floor access with shoulder mounting heights of 150–300 mm | Analytical geometry, then joint/collision-aware model and chassis tests | Desktop reach does not prove floor access |

## Demonstration contract

Within a defined, reachable source region, scatter ten lightweight, graspable objects from the approved test set. The eventual robot must observe, classify, estimate poses in the robot frame, select a reachable target, select a grasp, plan a collision-aware approach, grasp, transport, release into the assigned bin, verify the outcome, and continue. It must report exclusions and failures, with bounded recovery rather than hiding them.

A physical cycle succeeds only when an independent observation confirms the intended object ended in the correct bin without a safety violation. An attempted grasp is not a successful cycle. Initial objects may be colored cubes/cylinders; arbitrary household-object capability is not an initial acceptance requirement.

## Required evidence before finalizing the design

Record editable CAD availability and license, complete joint tree, masses and centers of mass, exact servo variants, voltage/bus compatibility, rated versus peak torque, thermal-duty evidence, gripper aperture/force, structural deflection, cable clearance, joint limits, and mount reactions. Revisit reach, payload, or budget when those conflict; do not silently lower the six-arm-axis requirement.

## Current study direction and open decisions

Study Thor first using its existing editable source. The allowance of eight actuators does not validate source geometry, mechanical fit, gripper parallelism, load capacity, compatibility, budget, or safety, and does not approve fabrication or purchasing. The approximately $500 target and $350–725 planning range remain unchanged and unverified.

Final mechanical baseline and modifications; nominal link geometry; initial payload/reach operating envelope; actuator allocation and counterbalance; camera and calibration method; acceptable object set and bin dimensions; final company distribution license; as-built safety limits. Owners and next actions belong in [nextSteps.md](../../nextSteps.md).
