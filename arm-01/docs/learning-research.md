# Learning research for ARM-01

## Reproduce the screening experiment

Start from the [quick start](../../README.md#quick-start). With the environment
active, run the experiment using the installed Python package and the standard library.

```sh
python -m raftel_arm01.learning --train-seed 42 --train-layouts 30 --eval-seed 1000 --eval-layouts 10
```

This experiment trains a small imitation policy on examples labeled by the existing
[waypoint planner](../src/raftel_arm01/planning/sorting.py). It measures how closely
the learned policy reproduces the planner's logical screening decisions on new
synthetic layouts. The experiment is isolated from the sorter and its control
backend. Its evidence is one-step supervised agreement with an oracle.

| Part | Definition |
| --- | --- |
| Initialization | Each layout uses its own seed and draws ten candidates from fixed ranges. Layout groups use consecutive seeds in each split, and the command rejects any overlap. |
| Sampling | In `arm_base`, draw integer millimetres uniformly from x = −300…300, y = −50…450, z = −20…340 and an integer mass of 10…140 g, then convert to SI. Cycle through valid configured categories. The broad distribution exercises planner rejections as well as accepted targets. |
| Observation | Horizontal distance from the arm-base z axis in metres, height in metres, and mass in kilograms. Geometry and mass are oracle-provided. |
| Action | `consider` or `defer` for the current candidate. The episode ends immediately after this decision. Sorting state, waypoint execution, contacts and camera images are outside the episode. |
| Objective | Match the original planner's decision. `consider` means the planner accepted the point-based proposal. `defer` means the planner rejected it. The experiment gives one point for agreement and zero for disagreement. |
| Learning | Fit a 3-nearest-neighbor classifier by retaining training examples with their oracle labels. Use Euclidean distance scaled by 0.60 m, 0.40 m and 0.15 kg on the three inputs, a majority vote, and training order to break distance ties. These parameters are fixed before evaluation. |
| Comparators | Always consider, always defer, and the original planner. The planner's agreement is 100% by definition because it supplies the labels. |
| Reporting | JSON includes the schema, split seeds and sizes, content hashes of labeled examples and planner configuration, confusion counts, accuracy, and both error rates. |

The default run on Windows/Python 3.14.6 fitted on 300 examples and evaluated on
100 examples from ten held-out layouts. The planner considered 33 held-out
candidates and deferred 67.

| Policy | Agreement | Considered despite planner defer | Deferred despite planner consider |
| --- | ---: | ---: | ---: |
| Learned 3-nearest-neighbor | 94/100 | 4/67 | 2/33 |
| Always consider | 33/100 | 67/67 | 0/33 |
| Always defer | 67/100 | 0/67 | 33/33 |
| Deterministic planner | 100/100 | 0/67 | 0/33 |

The reported error rates use the two planner-action denominators. An absent
action produces a null error rate. Same-seed runs reproduce these results with a
fixed implementation and Python runtime. Held-out seeds exercise the same fixed
distribution, and the results describe this sample. Physical success, safety,
model transfer and learning from camera input require separate experiments.
Keep the deterministic planner authoritative even if a learned policy agrees
with it on every evaluation example.

Run the [regression tests](../tests/test_learning.py) from `arm-01` with
`python -m pytest tests/test_learning.py`. The tests check data-dependent
predictions, tie-breaking, split isolation, reproducibility and error denominators.

## Imitation learning beyond screening

Start with a deterministic expert in a simulator that supports valid grasp
candidates and visible placement outcomes. Collect full episodes with revisioned
robot and scene identities, sensor time and frame, pre-action observation,
candidate object and grasp, commanded action, screened or executed action,
rejection reason and independently verified outcome. Record operator
interventions and issues such as occluded or lost objects. Define train,
validation and test groups by episode and object family or session so near-duplicate
frames from one run never cross splits.

First train a supervised policy to rank object or grasp candidates. Let
`defer` handle missing or uncertain observations. Compare a learned ranker with
analytical and fixed heuristics behind the same planning checks. Log disagreement,
failure recovery and correct-bin completion across complete episodes. Actions
change later observations in a sequential task, so good held-out action accuracy
can still yield failures during rollout. If offline cloning shows that gap,
extend the simulator experiment to label states visited by the learned policy
using a deterministic expert, as in DAgger. [Ross et al., AISTATS 2011](https://proceedings.mlr.press/v15/ross11a.html).

## Reinforcement learning environment

A useful environment needs resettable robot and object poses, gripper state,
geometry and collision, contact and friction, actuator bounds, sensor noise,
observable placement and consistent timing. Start with one object and one bin.
Use a bounded action space such as a choice among proposed grasps and a defer
action. Expand to continuous Cartesian increments only if a fixed controller
with independent constraints can evaluate those proposals. Provide only information
available to the candidate policy at inference time. Reserve privileged simulator
state for expert labels, evaluation and debugging.

Reward independently verified correct-bin placement with +1. End on success
or on unrecoverable task failures such as a lost object or a constraint fault.
Record why runs end and distinguish task termination from an external wall-time
or rollout budget. Log safety and failure rates separately from return. If
experiments add reward shaping, preserve the independently scored success metric
and compare with the same unshaped environment. [Gymnasium 1.4.0 guide to time limits](https://github.com/Farama-Foundation/Gymnasium/blob/8ba8c3a63bb4e000b7f33923f43d292acac07be1/docs/tutorials/gymnasium_basics/handling_time_limits.py).

Freeze the model-selection protocol and evaluation seeds before training.
Report results against deterministic planning on the same object, layout and noise
conditions. Include repeated training seeds and layout-level variation, present
both coverage and correct-bin completion, and preserve failed attempts, assists,
interventions, rejected proposals and solver timeouts. Reuse the existing
[outcome evaluation](../src/raftel_arm01/evaluation/replay.py) when the environment
can generate its independently observed outcome records. [Patterson et al., JMLR 2024](https://jmlr.org/papers/v25/23-0183.html).

## Vision and coordinate frames

Build on [offline observation replay](offline-observation-replay.md). With a
fixed camera, calibrate intrinsics and distortion and independently estimate
`arm_base_from_camera` from a measured target. Preserve transform direction,
frame names, units, calibration revision and acquisition timestamp. Evaluate
transformed point error throughout the workspace using target positions held
out from calibration. For a wrist-mounted camera, evaluate timestamped
kinematic transforms and hand-eye calibration as a separate setup.
[OpenCV 4.13.0 calibration and hand-eye reference](https://docs.opencv.org/4.13.0/d9/d0c/group__calib3d.html).

Set the tolerated position error from measured grasp and bin tolerances, then
measure detection coverage and spatial error across lighting, occlusion,
object surfaces and workspace regions. Preserve missed detections and stale,
uncertain or untransformable observations with distinct reasons. Propagate
position uncertainty into the arm frame and account separately for the
calibration and timing errors that the current replay excludes. Use an explicit
defer policy when uncertainty exceeds the task budget.

## Planning and transfer to hardware

Let a policy propose an object, grasp or goal. Deterministic software should
validate observation freshness, frame availability, payload, grasp constraints,
joint and velocity limits, IK convergence, and swept robot/environment clearance
before accepting a timed path. This requires an accepted robot and obstacle
model with calibrated limits and independently validated collision coverage.
The [nominal Thor study](thor-spatial-kinematics.md) supplies offline mathematical
components, and the [safety plan](safety.md) governs physical commissioning and
fault handling. [MoveIt planning scene example](https://github.com/moveit/moveit2_tutorials/blob/b8f954ce045b00f29de4da24146eb7732e7b2a9e/doc/examples/planning_scene/planning_scene_tutorial.rst).

Before physical transfer, measure geometry, masses, drive coupling, backlash,
friction, actuator response, camera timing, grasp retention and contact behavior.
Use measured ranges for simulator randomization and hold out physical trials for
error characterization. Begin physical integration with independent electrical
stop protection, an approved commissioning procedure and supervised deterministic
controls. A learned proposal remains behind the same calibrated checks and stop
conditions. Compare simulation and reality on pose error, grasp outcomes and
failure modes before expanding the task. Published transfer results provide
experimental starting points for [visual localization](https://arxiv.org/abs/1703.06907v1)
and [dynamics-randomized arm control](https://arxiv.org/abs/1710.06537v3).

Research references checked 2026-11-21. The
[research roadmap](../../docs/roadmap.md) tracks acceptance criteria for each
integration milestone.
