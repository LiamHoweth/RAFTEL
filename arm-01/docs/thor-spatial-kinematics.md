# Nominal frames, provisional constraints, Jacobian and bounded local IK

This desktop checkpoint adds **offline nominal kinematic analysis** while
preserving the existing FK, logical sorter and drive/transmission utilities.
It establishes no hardware calibration, collision clearance, safe trajectory,
physical travel limit or fabrication release. The mathematical model remains
the pinned [Thor-ROS source](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_urdf/urdf/thor.urdf.xacro).
Its byte SHA256 is
`19b83e26f86aae15fda5c21418f768d0e3ed1b0d1daa6d149abd9b45ceccd8b9`.
The original [native zero-axis evidence](../hardware/cad/thor-axis-evidence.json)
corroborates unsigned zero-pose lines. The later [Windows pose-frame check](thor-native-pose-frames.md)
also verifies three nonzero proximal-four-axis study poses with q5/q6 fixed at
zero. It checks axis lines, a fold frame and refreshed shape markers; 39 touched
objects remain, and full six-axis geometry, calibration and clearance are unverified.

## Frames and provenance

[thor-frames-v1.json](../config/thor-frames-v1.json) records a revision, SI units,
the exact nominal source pin and individually labeled source/unknown edges.
`thor_frames.py` validates proper rigid transforms, composition, inverse,
point transforms, an acyclic single-parent frame graph, and covariance
transport. It rejects reflected/scaled rotations, duplicate JSON keys,
boolean/noninteger schema versions and stale source metadata.

`parent_from_child` means `p_parent = R * p_child + t`; translations are metres.
The known source native-CAD conversion is `base_link_from_native_cad =
Rz(-pi/2)` with zero translation. Its direction matters: native +Y maps to
source +X. The nominal fixed offsets remain +0.043 m from `link_6` to
`gripper_base` and +0.075 m to the source `gripper_mid_point`.

The following are **null**, rather than guessed identities:

| Edge | Missing evidence |
| --- | --- |
| `world` â†’ `bench` | Workstation pose |
| `bench` â†’ logical `arm_base` | Removable mount survey |
| logical `arm_base` â†’ nominal `base_link` | Physical/source frame registration |
| `bench` â†’ `camera` | Camera extrinsics |
| source `gripper_mid_point` â†’ `tcp` | Measured grasp/contact TCP |

`FrameGraph.transform(target, source)` returns `target_from_source`; a query
whose path contains a null edge fails. A static graph deliberately does not
freeze the moving `base_link`â†’`link_6` edge. `with_nominal_pose(graph,q)` returns
a separate graph with the existing FK at the supplied six angles; it retains
all unknown extrinsics. That operation is mathematical articulation, not a
native-CAD or physical articulation test.

Covariances use six small **left perturbations**, ordered translation in m
then rotation in rad. `transform_covariance(T,C)` computes `Ad(T) C Ad(T)^T`
with `Ad(T) = [[R,[t]x R],[0,R]]`. `compose_covariance(T,A,B)` adds `A` and the
transported `B`, assuming independent inputs. Symmetry and positive
semidefiniteness are checked. Correlated calibration errors require their
cross-covariances and are outside that independent-input helper; null source
measurement uncertainty has not been turned into a zero covariance.

## Source, study and calibrated constraints

[thor-constraints-v1.json](../config/thor-constraints-v1.json) distinguishes
`source`, `study` and `calibrated` bounds for every joint. Its initial study
box copies source position/velocity values explicitly as a numerical
scenario. Study bounds must be a subset of declared source bounds. The exact
source Xacro PI literal is `3.14159265359`.

| Joint | Source position interval rad | Source velocity rad/s |
| --- | --- | --- |
| 1 | [-2.967, 2.967] | 0.58 |
| 2 | [-PI/2, PI/2] | 0.23 |
| 3 | [-PI/2, PI/2] | 0.23 |
| 4 | [-2.967, 2.967] | 0.58 |
| 5 | [-PI/2, PI/2] | 1.45 |
| 6 | [-2.967, 2.967] | 1.45 |

All calibrated records, acceleration limits, hard-stop evidence and coupled
cable/collision feasible regions remain null. The source generic effort
value is excluded; it is not an actuator capacity. Scalar position boxes
cannot describe the physical wrist's coupled feasible region.

`validate_joint_state(q,constraints,family="study", velocities_rad_s=...,
accelerations_rad_s2=...)` returns explicit scalar violations. Unknown
required limits, nonfinite values and malformed inputs raise `ValueError`.
Passing this check grants no permission for motion. With a separately obtained
local Xacro, `audit_source_constraints(path,constraints)` first checks its
exact SHA256, then parses and compares all six source position/velocity
limits. The manifest loader validates declared source provenance; the
optional byte audit independently checks actual source contents.

## Geometric Jacobian and singularity study

`spatial_jacobian(q,target="link_6",point_offset_m=(0,0,0))` returns a 6Ã—6
geometric Jacobian expressed in nominal `base_link`. Top rows are the chosen
target point's linear velocity in m/rad; bottom rows are spatial angular
velocity in rad/rad. Column `j` is `[axis_j Ã— (point-origin_j); axis_j]`.
This is neither an Euler-angle derivative nor a spatial twist's translational
component referenced at the base origin. Targets are the three existing FK
targets. A supplied offset is fixed in the selected target frame and is an
explicit scenario, not a measured TCP.

`singularity_diagnostic(J,characteristic_length_m=L)` divides linear rows by
the explicit positive characteristic length before evaluating dimensionless
singular values. It uses a small symmetric Jacobi eigensolve of the scaled
Gram matrix, without a runtime dependency. Rank threshold is an explicit
relative numerical study parameter (minimum 1e-6); it is not a physical safety
margin. A rank-deficient condition number is JSON null. The zero pose has
rank 3. The mixed pose `(0.4,-0.5,0.6,-0.7,0.8,-0.9)` has rank 6 and condition
number about 17.0223 when L=0.3 m. A different L changes that numerical study.

## Bounded local pose IK

`solve_pose_ik(target_pose,seed,constraints,target="link_6",family="study",
options=IKOptions(...))` solves a pose in nominal `base_link` using projected
damped least squares and bounded backtracking. It preserves finite work
bounds (iterations, line-search evaluations and wall time); it never sends
commands or connects to the mock backend. The caller supplies a seed inside
the declared source/study box. A converged result requires independent
position and orientation residual tests; default tolerances are 1e-6 m and
1e-5 rad. They are numerical solver thresholds, not manufacturing tolerances.

The orientation residual is the shortest SO(3) logarithm of
`R_target R_current^T`, expressed in the base frame. Quaternion extraction
handles small angles and half-turns without division by sin(theta). The
Jacobian maps base-frame angular velocities in that same convention.

Results retain source/constraint revisions, the chosen family, residuals,
iteration count and one of these reasons:

| Reason | Meaning |
| --- | --- |
| `converged` | Both nominal residual tolerances passed inside the box |
| `outside_nominal_reach_bound` | Triangle-inequality position rejection only |
| `stalled` | No tested improving local step from this seed |
| `stalled_at_limits` | Local improvement stopped while a scalar bound was active |
| `iteration_limit` | Explicit iteration budget exhausted |
| `time_limit` | Explicit wall-time budget exhausted |

Local failure does not prove global infeasibility. Conversely, a converged
pose says nothing about collision, joint-to-drive feasibility, actual stops,
paths, cable twist, dynamics or a physical grasp. There is no multi-start
global search, collision model or trajectory connection in this checkpoint.

## Reproduction and evidence boundaries

From an installed development environment in `arm-01`:

```powershell
python -m pytest tests/test_thor_frames.py tests/test_thor_constraints.py tests/test_thor_jacobian.py tests/test_thor_ik.py
python tools/thor_kinematics.py --output new-nominal-report.json
python tools/thor_kinematics.py --source-xacro /path/to/pinned/thor.urdf.xacro --output new-source-audit.json
```

The report includes manifest hashes, nominal pose/Jacobian, scaled singularity
diagnostics, unknown-frame edges, optional source audit and explicit remaining
gates. Output uses exclusive creation so existing evidence is preserved.
`--ik-pose` accepts a JSON object with exactly `frame: "base_link"`, a matching
`target` and `pose_matrix_m`; `--joints` supplies its seed. Wrong frames and
stale source bytes fail explicitly. A diagnostic report may successfully
record a failed IK attempt: consumers must inspect `ik.converged` and its
reason rather than treating process exit 0 as an IK success.

Tests check analytic planar columns, seeded position and `Rdot R^T` angular
finite differences at off-axis points, differential virtual work, scaled-unit
invariance, known singular/full-rank cases, frame direction/inverse/composition,
covariance lever arms, input/provenance failures and FKâ†’IKâ†’FK residuals.
Independent review uses separate FK difference calculations. These checks
verify the declared mathematics and software behavior. Native nonzero-pose
geometry, calibrated transforms, real joint limits, collision screening and
physical operation remain separate gates.
